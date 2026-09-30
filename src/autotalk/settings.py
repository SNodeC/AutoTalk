# SPDX-License-Identifier: MIT
"""Fixed-scope owners; Project remains the settings resolution authority.

Controller reads/calls are restricted to project, edit_setting, codex_settings,
error, log_message, start_job, voice_context, configuration_changed, transport
(selection/previews), recorder (read-only), and refresh/request_refresh.
Application defaults are borrowed input, never a second authority. Transaction
begin/finish callbacks and operation/navigation signals keep application-level
persistence, session lifetime and sibling navigation in the controller.
"""
import copy
import json
import html
import wave
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QTableWidgetItem,
    QFileDialog, QInputDialog, QTabBar, QPlainTextEdit, QLineEdit, QTableWidget,
    QButtonGroup, QRadioButton, QCheckBox, QAbstractItemView, QHeaderView, QScrollArea, QWidget)

from .project import Project, Voice, SETTING_DEFAULTS, LANGUAGES, SPEAKERS, read_settings, wav_duration
from .runtime import data_dir
from .services import synthesize, preview_path, preview_text, extract_scope
from .media import import_clip
from .voices import library, load_voice, save_voice
from .options import SettingsPanel
from .ui import SectionDialog, label, button, column, combo, number, row, form, disclosure


class SettingsDialog(SectionDialog):
    details_changed = Signal()
    sign_in_requested = Signal()
    sign_out_requested = Signal()
    load_requested = Signal()
    unload_requested = Signal()
    model_check_requested = Signal()
    engine_policy_changed = Signal()
    test_audio_requested = Signal()
    audio_settings_requested = Signal()
    fit_requested = Signal()
    save_requested = Signal()
    record_requested = Signal(object)
    application_requested = Signal(str, str)

    def __init__(self, window, scope, defaults, display_name, begin, finish):
        super().__init__(window, "Settings")
        self.scope, self.slide_index = scope, 0
        self.defaults, self.display_name = defaults, display_name
        self.begin, self.finish = begin, finish
        self.loading = True
        self.before = None
        self.options = SettingsPanel(self)
        self.options.changed.connect(window.configuration_changed)
        self.buttons.setStandardButtons(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        for name in ("Voice & language", "Talk & preparation", "Presentation & recording", "AI & speech engine", "Application"):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(column("paper", 16))
            self.navigation.addItem(name)
            self.pages.addWidget(scroll)
        build_settings(self)
        for builder in ((build_display, build_account, build_engine) if scope == 0 else
                        (build_conference, build_timing) if scope == 1 else (build_clips,)):
            builder(self)
        self.navigation.setCurrentRow(0)
        self.hint = label(("Application defaults affect talks and slides inheriting them. " if scope == 0 else
                           "Save applies only to this talk. " if scope == 1 else "Save applies only to this slide. ") +
                          "Account, manual model and library actions take effect immediately.")
        self.layout().insertWidget(self.layout().count()-1, self.hint)
        self.loading = False

    @property
    def slide(self):
        return self.window.project.slides[self.slide_index] if self.scope == 2 and self.window.project else None

    def setting_value(self, name):
        w = self.window
        return w.project.setting(name, self.slide) if self.scope and w.project else self.defaults.get(name, copy.deepcopy(SETTING_DEFAULTS[name][0]))

    def setting_source(self, name):
        return self.window.project.setting_source(name, self.slide) if self.scope and self.window.project else "Application default"

    def edit_setting(self, name, value, inherit=False):
        if not self.loading:
            self.window.edit_setting(name, value, inherit, scope=self.scope, slide=self.slide_index)

    def load_settings(self, *_, preserve_candidate=False):
        if not self.isVisible():
            self.slide_index = self.window.transport.index
        previous, self.loading = self.loading, True
        voice = self.setting_value("voice")
        if not preserve_candidate or self.voice_source.currentIndex() != 3:
            self.voice_source.setCurrentIndex(2 if voice.origin == "designed" and voice.source == "Base" else ["CustomVoice", "Base", "VoiceDesign"].index(voice.source))
        self.speaker.setCurrentIndex(self.speaker.findData(voice.speaker))
        self.voice_description.setText(voice.description)
        self.voice_identity.setText(voice.label + " · " + self.setting_source("voice"))
        self.voice_inherit.setText("Use talk voice" if self.scope == 2 else "Use application voice")
        self.voice_inherit.setVisible(self.scope > 0)
        self.voice_inherit.setEnabled(self.setting_source("voice") == ("Slide override" if self.scope == 2 else "Talk setting"))
        ref = voice.references.get(self.setting_value("language"), voice.references.get("default"))
        if self.transcript.toPlainText() != (ref.transcript if ref else ""):
            self.transcript.setPlainText(ref.transcript if ref else "")
        if self.scope == 2 and self.slide:
            selected = self.clip_select.currentIndex()
            self.clip_select.blockSignals(True)
            self.clip_select.clear()
            self.clip_select.addItems([Path(clip.file).name for clip in self.slide.clips])
            self.clip_select.setCurrentIndex(min(max(0, selected), len(self.slide.clips)-1))
            self.clip_select.blockSignals(False)
            self.show_clip()
        self.options.load(self.window.project)
        self.refresh_models()
        self.loading = previous

    def show_section(self, section=None, focus=None):
        w = self.window
        if self.scope and not w.project:
            return
        if not self.isVisible():
            self.slide_index = w.transport.index
            self.begin(self)
        self.setWindowTitle("Application defaults" if self.scope == 0 else
                            f"Talk settings — {w.project.title}" if self.scope == 1 else
                            f"Slide settings — {self.slide_index + 1}")
        self.load_settings()
        self.refresh_library()
        self.options.refresh_presets()
        self.show()
        super().show_section(section or ("Application" if self.scope == 0 else "Talk & preparation" if self.scope == 1 else "Voice & language"),
                             getattr(self, focus) if isinstance(focus, str) else focus)

    def sync(self, editable, job=None, engine=""):
        w = self.window
        super().sync(editable, job)
        for index in range(self.pages.count()):
            sections = self.pages.widget(index).widget().findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
            applicable = [s for s in sections if self.scope in (s.property("scopes") or ())]
            self.navigation.item(index).setHidden(not applicable)
            for section in sections:
                section.setVisible(section in applicable)
                section.setEnabled(not w.recorder.source and (list(section.property("scopes") or ()) == [0] or editable))
        for container, _ in self.options.inheritance.values():
            container.setEnabled(editable)
        self.voice_audition.setVisible(self.navigation.currentItem() is not None and self.navigation.currentItem().text() == "Voice & language")
        if self.isVisible() and self.scope and editable and w.project and self.before is None:
            self.before = copy.deepcopy(w.project)
        if self.isVisible():
            self.sync_voice(editable)
        self.buffer_toggle.setVisible(self.scope < 2 and self.setting_value("mode") == "Realtime")
        self.codex_connection.setText(self.window.codex_settings.get("account", "Not signed in to ChatGPT."))
        if self.scope == 0:
            self.connection.setText(self.codex_connection.text())
            self.codex_signin.setEnabled(editable and not self.window.codex_settings.get("signed_in", False))
            self.codex_signout.setEnabled(editable and bool(self.window.codex_settings.get("signed_in")))
        elif self.scope == 1 and self.window.project:
            self.sync_talk(editable)
        self.voice_model.setText("Qwen3-TTS 1.7B — " + self.setting_value("voice").source + ("\n" + engine if self.scope == 1 else ""))

    def sync_voice(self, editable):
        w = self.window
        voice = self.setting_value("voice")
        for i in range(self.voice_panels.layout().count()):
            self.voice_panels.layout().itemAt(i).widget().setVisible(i == self.voice_source.currentIndex())
        for widget in (self.voice_source, self.voice_panels, self.voice_audition, self.codex_model, self.codex_effort, self.options.synthesis_widget):
            widget.setEnabled(editable)
        self.library_use.setEnabled(editable and self.voice_library.currentRow() >= 0)
        self.voice_preview_button.setText("Stop sample" if w.transport.preview_path else "Listen to selected voice" if self.voice_source.currentIndex() == 3 else "Listen to a sample")
        context = self.voice_context()
        self.voice_preview_button.setEnabled(editable and (self.voice_library.currentRow() >= 0 if self.voice_source.currentIndex() == 3 else bool(context.voice_file) if voice.source == "Base" else bool(voice.description.strip()) if voice.source == "VoiceDesign" else True))
        self.accept_voice_button.setVisible(voice.source == "VoiceDesign")
        self.accept_voice_button.setEnabled(editable and voice.source == "VoiceDesign" and preview_path(context).is_file())
        self.save_voice_button.setEnabled(editable and self.voice_source.currentIndex() != 3 and (self.accept_voice_button.isEnabled() if voice.source == "VoiceDesign" else self.voice_preview_button.isEnabled()))
        self.transcript.setEnabled(bool(context.voice_file) and editable)

    def sync_engine(self, owner, config, job, preferences):
        state = owner.state
        ready = owner.matches(config) if config else False
        descriptions = {"unloaded": "Not loaded", "loading": "Loading speech model…", "ready": "Ready on GPU",
                        "generating": "Generating speech", "in_use": "Speech model in use", "unloading": "Unloading model…", "failed": "Speech engine stopped or failed"}
        consequence = {"session": "Kept until AutoTalk closes.", "presentation": "Will unload at the next presentation end.",
                       "idle": "Will unload after five idle minutes.", "operation": "Will unload after the next preparation or preview finishes."}
        status = descriptions[state]
        if state == "ready":
            status += " · " + owner.config["model"]["repo"].rsplit("/", 1)[-1]
            status += " · " + ("Unloading requested." if owner.release_requested else consequence[owner.retention])
        self.engine_state.setText(status)
        self.engine_model.setText((f"Selected slide {self.window.transport.index + 1}: " if self.window.project else "Application default: ") + config["model"]["repo"].rsplit("/", 1)[-1] if config else
                                  "Open a talk and configure its voice to select a speech model.")
        self.load_gpu_button.setText("Load selected model" if owner.process and not ready else "Load model now")
        self.load_gpu_button.setEnabled(bool(config and not job and not owner.release_requested and state not in ("loading", "generating", "unloading") and not ready))
        self.unload_gpu_button.setEnabled(bool(owner.process and not owner.guard.locked() and not owner.release_requested and state in ("ready", "failed")))
        self.check_model_button.setEnabled(bool(config and not job and not self.window.transport.active and not self.window.transport.preview_path))
        dirty = any(getattr(self, name).checkedButton().property("value") != preferences.value(name, default)
                    for name, default in (("gpu_loading", "needed"), ("gpu_retention", "session")))
        self.engine_policy_note.setText("Automatic settings have unsaved changes. Load/unload actions take effect immediately." if dirty else
                                       "Automatic settings are saved. Load/unload actions take effect immediately.")
        return descriptions[state]

    def sync_talk(self, editable):
        from .app import clock
        p = self.window.project
        for widget in (self.url, self.conference_scope, self.audience, self.objective, self.conference_button):
            widget.setEnabled(p.mode != "Quick")
        self.background_button.setText("Background: " + Path(p.background.file).name[:16] + "…" if p.background else "Add background track…")
        for widget in (self.remove_background_button,):
            widget.setEnabled(editable and p.background is not None)
        self.sources.setText("Sources: " + " · ".join(
            f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>' for url in p.sources) if p.sources else "")
        ready = sum(p.ready(s) for s in p.included_slides)
        self.timing_summary.setText(f"Target {clock(p.target_minutes*60)} · {clock(p.total_seconds)} prepared audio\n{ready}/{len(p.included_slides)} included slides have current audio. " +
            ("Within requested tolerance." if p.within_target else
             f"Difference: {p.total_seconds-p.target_minutes*60:+.1f} seconds (tolerance ±{p.tolerance_seconds:g}s)." if p.prepared
             else "Start prepares missing text and audio automatically."))
        self.fit_button.setEnabled(editable and all(p.text_ready(s) for s in p.included_slides))

    def done(self, result):
        if self.finish(self, result):
            self.before = None
            QDialog.done(self, result)


    def voice_context(self):
        # A synthesis request snapshot; never adopted as the UI's document.
        candidate = Project(data_dir()) if self.scope == 0 or not self.window.project else copy.deepcopy(self.window.project)
        candidate.overrides = {key: copy.deepcopy(self.setting_value(key)) for key in SETTING_DEFAULTS if key != "language"}
        candidate.language = self.setting_value("language")
        return candidate


    def voice_changed(self):
        if not self.loading:
            voice = copy.deepcopy(self.setting_value("voice"))
            ref = voice.references.get(self.setting_value("language"), voice.references.get("default"))
            if ref:
                ref.transcript = self.transcript.toPlainText()
                self.edit_setting("voice", voice)


    def import_voice(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import your voice", "", "PCM WAV recording (*.wav)")
        if path:
            self.set_voice(Path(path))


    def set_voice(self, path):
        try:
            self.window.transport.stop()
            duration = wav_duration(path)
            if not 3 <= duration <= 60:
                raise ValueError("Use a WAV reference recording between 3 and 60 seconds.")
            candidate = self.voice_context()
            candidate.set_voice(path)
            self.edit_setting("voice", candidate.voice)
        except (OSError, ValueError, EOFError, wave.Error) as error:
            self.window.error(str(error))


    def toggle_recording(self):
        self.record_requested.emit(self)


    def preview_voice(self):
        if self.window.transport.preview_path:
            self.window.transport.stop()
            return
        if self.window.recorder.source:
            self.window.error("Stop recording before previewing the voice.")
            return
        def done(path):
            self.window.transport.preview(path)
            self.window.log_message("Playing your voice preview.")
        candidate = self.voice_context()
        if self.voice_source.currentIndex() == 3:
            item = self.voice_library.item(self.voice_library.currentRow(), 0)
            if item is None:
                return
            try:
                load_voice(candidate, item.data(Qt.ItemDataRole.UserRole))
            except (OSError, ValueError) as error:
                self.window.error(str(error))
                return
        self.window.start_job("Generating voice preview…", partial(synthesize, candidate, preview=True), done)


    def refresh_models(self):
        previous = self.loading
        self.loading = True
        wanted = self.setting_value("codex_model")
        self.codex_model.clear()
        default = next((m.get("displayName") or m["model"] for m in self.window.codex_settings.get("models", []) if m["model"] == self.window.codex_settings.get("model")), self.window.codex_settings.get("model", ""))
        self.codex_model.addItem("Account default" + (f" ({default})" if default else ""), "")
        for model in self.window.codex_settings.get("models", []):
            if "image" in model.get("inputModalities", ["text", "image"]):
                self.codex_model.addItem(model.get("displayName") or model["model"], model["model"])
        if wanted and self.codex_model.findData(wanted) < 0:
            self.codex_model.addItem(wanted + " (refresh availability)", wanted)
        self.codex_model.setCurrentIndex(max(0, self.codex_model.findData(wanted)))
        self.refresh_efforts()
        self.loading = previous


    def refresh_efforts(self):
        previous = self.loading
        self.loading = True
        model = self.codex_model.currentData() or self.window.codex_settings.get("model")
        selected = next((m for m in self.window.codex_settings.get("models", []) if m["model"] == model), {})
        wanted = self.setting_value("codex_effort")
        self.codex_effort.clear()
        default = self.window.codex_settings.get("effort") or selected.get("defaultReasoningEffort", "")
        self.codex_effort.addItem("Codex default" + (f" ({default})" if default else ""), "")
        for option in selected.get("supportedReasoningEfforts", []):
            effort = option["reasoningEffort"]
            self.codex_effort.addItem(effort, effort)
            self.codex_effort.setItemData(self.codex_effort.count()-1, option.get("description", ""), Qt.ItemDataRole.ToolTipRole)
        if wanted and self.codex_effort.findData(wanted) < 0:
            self.codex_effort.addItem(wanted + " (refresh availability)", wanted)
        self.codex_effort.setCurrentIndex(max(0, self.codex_effort.findData(wanted)))
        self.loading = previous


    def model_changed(self):
        if not self.loading:
            self.edit_setting("codex_model", self.codex_model.currentData() or "")
            self.edit_setting("codex_effort", "")


    def model_settings_changed(self):
        if not self.loading:
            self.edit_setting("codex_effort", self.codex_effort.currentData() or "")


    def voice_settings_changed(self):
        if self.loading:
            return
        voice = copy.deepcopy(self.setting_value("voice"))
        if self.voice_source.currentIndex() == 3:
            self.window.refresh()
            return
        source = self.voice_source.tabData(self.voice_source.currentIndex())
        if source != voice.source:
            voice = Voice(source=source)
        voice.source = source
        voice.speaker = self.speaker.currentData()
        voice.description = self.voice_description.text()
        voice.name = voice.speaker if voice.source == "CustomVoice" else "Designed voice" if voice.source == "VoiceDesign" else "My voice"
        voice.origin = "designed" if voice.source == "VoiceDesign" else voice.origin
        self.edit_setting("voice", voice)


    def refresh_library(self):
        selected = self.voice_library.item(self.voice_library.currentRow(), 0)
        selected = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        self.voice_library.setRowCount(0)
        for path in library():
            try:
                voice = json.loads(path.read_text(encoding="utf-8"))
                languages = ", ".join(k for k in voice["references"] if k != "default") or "Multilingual"
                values = (voice["name"], read_settings({"voice": voice})["voice"].label.split(":", 1)[0], languages)
            except (OSError, ValueError, KeyError):
                continue
            if self.library_language.currentText() not in ("All languages", languages) and self.library_language.currentText() not in languages and languages != "Multilingual":
                continue
            row = self.voice_library.rowCount()
            self.voice_library.insertRow(row)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self.voice_library.setItem(row, col, item)
        self.voice_library.resizeRowsToContents()
        self.voice_library.selectRow(next((row for row in range(self.voice_library.rowCount())
            if self.voice_library.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected), 0))


    def use_saved_voice(self):
        item = self.voice_library.item(self.voice_library.currentRow(), 0)
        if item:
            try:
                candidate = self.voice_context()
                load_voice(candidate, item.data(Qt.ItemDataRole.UserRole))
                self.edit_setting("voice", candidate.voice)
            except (OSError, ValueError) as error:
                self.window.error(str(error))


    def save_personal_voice(self):
        name, ok = QInputDialog.getText(self, "Save reusable voice", "Voice name", text=self.setting_value("voice").name)
        if not ok or not name.strip():
            return
        if self.setting_value("voice").source == "VoiceDesign" and not self.accept_designed_voice():
            return
        try:
            save_voice(self.voice_context(), name)
            self.refresh_library()
        except (OSError, ValueError) as error:
            self.window.error(str(error))


    def accept_designed_voice(self):
        candidate = self.voice_context()
        if candidate.voice.source != "VoiceDesign":
            return False
        path = preview_path(candidate)
        if not path.exists():
            self.window.error("Preview this design first, then accept the voice you heard.")
            return False
        description = candidate.voice.description
        try:
            candidate.set_voice(path, preview_text(candidate))
        except (OSError, ValueError) as error:
            self.window.error(str(error))
            return False
        voice = copy.deepcopy(candidate.voice)
        voice.name, voice.origin, voice.description = "Designed voice", "designed", description
        self.edit_setting("voice", voice)
        return True


    def background_changed(self, *_):
        if not self.loading:
            gain, loop = self.background_gain.value() / 100, self.background_loop.isChecked()
            self.edit_setting("background_gain", gain)
            self.edit_setting("background_loop", loop)


    def pin_settings(self):
        if self.window.project and self.scope == 1:
            for name in SETTING_DEFAULTS:
                self.window.project.set_setting(name, self.window.project.setting(name))
            for version in self.window.project.versions.values():
                if not version.language:
                    version.language = self.window.project.defaults.get("language", "English")
                    version.name = version.language
            self.load_settings()
            self.window.configuration_changed()




    def read_conference(self):
        if not self.url.text().strip():
            self.window.error("Enter a conference website URL, or type the scope directly below.")
            return
        def done(result):
            self.window.project.sources = result["sources"]
            self.conference_scope.setPlainText(result["scope"])
            self.window.project.save()
            self.window.log_message("Review the extracted conference scope before writing the talk text.")
        self.window.start_job("Reading conference scope…", lambda task: extract_scope(self.url.text().strip(), task, self.window.project.codex_model, self.window.project.codex_effort), done)



    def show_clip(self, *_):
        if not self.window.project:
            return
        previous = self.loading
        self.loading = True
        clips = self.slide.clips
        index = self.clip_select.currentIndex()
        self.remove_clip_button.setEnabled(0 <= index < len(clips))
        self.clip_gain.setEnabled(0 <= index < len(clips))
        self.clip_placement.setEnabled(0 <= index < len(clips))
        if 0 <= index < len(clips):
            if self.clip_gain.value() != clips[index].gain:
                self.clip_gain.setValue(clips[index].gain)
            self.clip_placement.setCurrentIndex(self.clip_placement.findData(clips[index].placement))
        self.loading = previous



    def clip_changed(self, *_):
        if not self.loading and self.window.project:
            clips = self.slide.clips
            index = self.clip_select.currentIndex()
            if 0 <= index < len(clips):
                clips[index].gain = self.clip_gain.value()
                clips[index].placement = self.clip_placement.currentData()
                self.window.configuration_changed()



    def add_clip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose presentation audio", "", "Audio (*.wav *.mp3 *.flac *.ogg *.m4a *.mp4);;All files (*)")
        if not path:
            return
        index = self.slide_index
        def done(clip):
            self.window.project.slides[index].clips.append(clip)
            self.load_settings()
        self.window.start_job("Importing audio clip…", partial(import_clip, self.window.project, Path(path)), done)



    def remove_clip(self):
        clips = self.slide.clips
        index = self.clip_select.currentIndex()
        if 0 <= index < len(clips):
            clips.pop(index)
            self.load_settings()
            self.window.configuration_changed()



    def add_background(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose background audio", "", "Audio (*.wav *.mp3 *.flac *.ogg *.m4a);;All files (*)")
        if path:
            def done(clip):
                clip.gain = self.window.project.background_gain
                clip.loop = self.window.project.background_loop
                self.window.project.background = clip
                self.window.transport.refresh_audio()
                self.window.refresh()
                self.save_requested.emit()
            self.window.start_job("Importing background track…", partial(import_clip, self.window.project, Path(path), placement="background"), done)



    def remove_background(self):
        self.window.project.background = None
        self.window.configuration_changed()



def build_settings(w):
    codex = w.add("Narration AI — Codex", "AI & speech engine", (0, 1))
    codex.layout().addWidget(label("Model and reasoning for the selected scope. Slide images, text and conference context are sent to Codex; voice references stay local."))
    w.codex_connection = label("")
    codex.layout().addWidget(w.codex_connection)
    codex.layout().addWidget(button("Account settings…", lambda: w.application_requested.emit("Application", "codex_signin")))
    w.codex_model = combo([("Account default", "")], w.model_changed)
    w.codex_effort = combo([("Codex default", "")], w.model_settings_changed)
    fields = form(codex)
    fields.addRow("Model", w.options.field("codex_model", w.codex_model))
    fields.addRow("Reasoning effort", w.options.field("codex_effort", w.codex_effort))
    codex.layout().addStretch()
    timing = w.add("Preparation & timing", "Talk & preparation", (0, 1))
    w.tolerance = number(0, 600, 15, lambda: w.edit_setting("tolerance_seconds", w.tolerance.value()), " sec")
    form(timing).addRow("Allowed timing difference", w.options.field("tolerance_seconds", w.tolerance))
    timing.layout().addWidget(w.options)
    w.settings_mode = w.options.read_only() if w.scope == 1 else combo(["Prepared", "Quick", "Realtime"], lambda: w.edit_setting("mode", w.settings_mode.currentText()))
    form(timing).addRow("Default mode" if w.scope == 0 else "Mode", w.options.field("mode", w.settings_mode))
    language = w.add("Language", "Voice & language")
    w.settings_language = w.options.read_only() if w.scope == 1 else combo(LANGUAGES, lambda: w.edit_setting("language", w.settings_language.currentText()))
    w.settings_language.setToolTip("Selecting a talk language restores its saved version or starts an empty version. Create talk text or Start generates missing narration from the slides and talk context, without translating another version. A slide language change affects only that slide.")
    form(language).addRow(("Default narration language", "Language", "Language of this slide")[w.scope], w.options.field("language", w.settings_language))
    language.layout().addWidget(label("Talk language selection preserves separate versions automatically. Slide language overrides and explicit passages keep their own language."))
    buffer = column(margin=0)
    for name, destination in (("language_policy", language), ("buffer_seconds", buffer)):
        w.options.place(name, form(destination))
    w.buffer_toggle = disclosure(timing, "Advanced Realtime buffering", buffer)
    timing.layout().addStretch()
    language.layout().addStretch()

    voice = w.add("Voice", "Voice & language")
    w.voice_source = QTabBar()
    for title, source in (("Predefined", "CustomVoice"), ("My voice", "Base"), ("Design", "VoiceDesign"), ("Saved", "Saved")):
        w.voice_source.setTabData(w.voice_source.addTab(title), source)
    w.voice_source.currentChanged.connect(w.voice_settings_changed)
    w.voice_identity = label("")
    w.voice_inherit = button("Use parent voice", lambda: w.edit_setting("voice", None, inherit=True))
    voice.layout().addLayout(row(w.voice_identity, w.voice_inherit))
    voice.layout().addWidget(w.voice_source)
    w.voice_panels = column(margin=0)
    voice.layout().addWidget(w.voice_panels)
    predefined, personal, designed, library_page = (column(margin=0) for _ in range(4))
    for page in (predefined, personal, designed, library_page):
        w.voice_panels.layout().addWidget(page)
    w.speaker = combo([(f"{name} — {description}", name) for name, description in SPEAKERS.items()], w.voice_settings_changed)
    form(predefined).addRow("Voice", w.speaker)
    predefined.layout().addWidget(label("Every voice supports the talk language. Native languages indicate strongest pronunciation. Listen before choosing; no personal recording is needed."))
    predefined.layout().addStretch()
    personal.layout().addWidget(label("Record or import 10–30 seconds, then enter the exact words. Recording stops after 30 seconds."))
    w.record_button = button("Record my voice", w.toggle_recording)
    personal.layout().addLayout(row(w.record_button, button("Import voice recording…", w.import_voice)))
    w.transcript = QPlainTextEdit()
    w.transcript.setPlaceholderText("The exact words in your reference recording")
    w.transcript.textChanged.connect(w.voice_changed)
    personal.layout().addWidget(w.transcript)
    w.voice_description = QLineEdit()
    w.voice_description.setPlaceholderText("For example: warm, calm, clear pronunciation")
    w.voice_description.textChanged.connect(w.voice_settings_changed)
    design_form = form(designed)
    design_form.addRow("Describe the voice", w.voice_description)
    w.options.place("delivery.attributes.age", design_form)
    w.accept_voice_button = button("Use this designed voice", w.accept_designed_voice)
    designed.layout().addWidget(w.accept_voice_button)
    designed.layout().addStretch()
    w.library_language = combo(["All languages", *LANGUAGES], w.refresh_library)
    library_page.layout().addWidget(label("Choose a saved voice to audition or use. To add one, choose Predefined, My voice or Design, then Save reusable voice."))
    library_page.layout().addWidget(w.library_language)
    w.voice_library = QTableWidget(0, 3)
    w.voice_library.setHorizontalHeaderLabels(["Voice", "Description", "Languages"])
    w.library_use = button("Use selected voice", w.use_saved_voice)
    w.voice_library.itemSelectionChanged.connect(w.window.refresh)
    library_page.layout().addWidget(w.library_use)
    library_page.layout().addWidget(w.voice_library, 1)
    delivery = w.add("Writing & delivery", "Voice & language")
    delivery.layout().addWidget(label("Writing style guides new text; spoken delivery guides audio. Save delivery preset stores delivery directions immediately in the shared library, without voice identity or synthesis sampling. Cancel does not remove saved presets."))
    delivery.layout().addWidget(w.options.delivery_widget)
    delivery.layout().addStretch()
    model = w.add("Speech model — Qwen", "AI & speech engine", (0, 1))
    w.voice_model = label("")
    model.layout().addWidget(w.voice_model)
    model.layout().addWidget(label("The voice workflow selects the Qwen3-TTS 1.7B variant. Base reuses reference delivery; CustomVoice and VoiceDesign support vocal directions."))
    if w.scope > 0:
        model.layout().addWidget(button("Speech engine settings…", lambda: w.application_requested.emit("AI & speech engine", "engine_state")))
    disclosure(model, "Advanced synthesis", w.options.synthesis_widget)
    model.layout().addStretch()
    w.voice_audition = column(margin=12)
    w.voice_audition.layout().addWidget(label("Listen before choosing. Save reusable voice stores the voice identity and references immediately in the shared library; Cancel does not remove it. First use downloads several GB. Progress and Cancel appear here."))
    w.voice_preview_button = button("Listen to a sample", w.preview_voice, True)
    w.save_voice_button = button("Save reusable voice…", w.save_personal_voice)
    w.voice_audition.layout().addLayout(row(w.voice_preview_button, w.save_voice_button))
    w.layout().insertWidget(w.layout().indexOf(w.status), w.voice_audition)

    w.pause = number(0, 10, .6, lambda: w.edit_setting("pause_seconds", w.pause.value()), " sec")
    w.pause.setSingleStep(.1)
    playback = w.add("Playback", "Presentation & recording", (0, 1))
    form(playback).addRow("Pause after slide", w.options.field("pause_seconds", w.pause))
    w.settings_after = combo([("Advance automatically", "advance"), ("Pause for live demo", "demo"), ("Wait for presenter", "pause")], lambda: w.edit_setting("after", w.settings_after.currentData()))
    form(playback).addRow("After slide", w.options.field("after", w.settings_after))
    if w.scope == 1:
        playback.layout().addWidget(button("Display && sound settings…", lambda: w.application_requested.emit("Application", "screen")))
    recording = w.add("Recording", "Presentation & recording", (0, 1))
    form(recording).addRow("Record presentation as a video" if w.scope == 1 else "Recording", w.options.field("record_presentation", w.options.record))
    recording.layout().addWidget(label("Screen capture continues until End presentation and save video. Slides-and-speech recordings finish after the last slide. Screen sharing is authorized separately from the presentation display."))
    recording.layout().addWidget(w.options.recording_widget)
    for title, names in (("Advanced recording", ("recording_policy",)), ("Output quality", ("export_rate", "export_bitrate"))):
        panel = column(margin=0)
        fields = form(panel)
        for name in names:
            w.options.place(name, fields)
        disclosure(recording, title, panel)
    recording.layout().addStretch()
    background = w.add("Background audio", "Presentation & recording", (0, 1))
    if w.scope == 1:
        w.background_button = button("Add background track…", w.add_background)
        w.remove_background_button = button("Remove background", w.remove_background)
        background.layout().addLayout(row(w.background_button, w.remove_background_button))
    w.background_gain = number(0, 100, 15, w.background_changed, " %")
    w.background_gain.setSingleStep(5)
    w.background_loop = QCheckBox("Loop")
    w.background_loop.toggled.connect(w.background_changed)
    form(background).addRow("Background volume", w.options.field("background_gain", w.background_gain))
    background.layout().addWidget(w.options.field("background_loop", w.background_loop))
    background.layout().addStretch()

    voice.parentWidget().layout().removeWidget(language)
    voice.parentWidget().layout().insertWidget(1, language)
    # Keep keyboard traversal independent of section construction/parenting order.
    QWidget.setTabOrder(w.tolerance, w.options.fields["language_policy"])
    QWidget.setTabOrder(w.options.fields["language_policy"], w.options.fields["quick_timing"])
    tail = ("delivery.sampling", "after", "language", "mode", "pause_seconds", "tolerance_seconds",
            "codex_model", "codex_effort", "background_gain", "background_loop")
    previous = w.background_loop
    for path in [p for p in w.options.fields if p not in tail and p in w.options.inheritance] + list(tail):
        reset = w.options.inheritance[path][1]
        QWidget.setTabOrder(previous, reset)
        previous = reset
    assert not w.options.rows
    del w.options.rows
    w.pages.currentChanged.connect(lambda: (w.load_settings(), w.window.refresh()))
    for table in (w.voice_library,):
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)


def build_conference(w):
    conference = w.add("Talk & conference", "Talk & preparation", (1,))
    conference.parentWidget().layout().removeWidget(conference)
    conference.parentWidget().layout().insertWidget(0, conference)
    fields = form(conference)
    for attr, title, default in (("talk_title", "Talk title", ""), ("audience", "Audience", "General conference audience"),
                                ("objective", "Talk objective", "Explain the key ideas and takeaways"), ("url", "Conference website", "")):
        field = QLineEdit(default)
        field.textChanged.connect(w.details_changed)
        setattr(w, attr, field)
        fields.addRow(title, field)
    w.url.setPlaceholderText("https://conference.example/call-for-papers")
    w.conference_button = button("Read conference website", w.read_conference)
    conference.layout().addWidget(w.conference_button)
    conference.layout().addWidget(label("Optional conference scope: enter topics or review the website summary."))
    w.conference_scope = QPlainTextEdit()
    w.conference_scope.setPlaceholderText("Themes, tracks, typical topics, edition/year…")
    w.conference_scope.textChanged.connect(w.details_changed)
    conference.layout().addWidget(w.conference_scope, 1)
    w.sources = label("")
    w.sources.setOpenExternalLinks(True)
    conference.layout().addWidget(w.sources)


def build_display(w):
    presentation = w.add("Display & sound", "Application", (0,))
    w.screen = combo([(f"Display {i+1}: {screen.name()}", i) for i, screen in enumerate(QApplication.screens())])
    w.screen.setCurrentIndex(max(0, w.screen.findText(w.display_name)))
    fields = form(presentation)
    fields.addRow("Fullscreen display on this computer", w.screen)
    w.audio_test_button = button("Test audio", w.test_audio_requested.emit)
    presentation.layout().addLayout(row(button("System audio settings…", w.audio_settings_requested.emit), w.audio_test_button))
    presentation.layout().addWidget(label("System sound routing changes immediately. Cancel restores the display selection; external sound settings take effect immediately."))
    presentation.layout().addStretch()


def build_timing(w):
    timing = w.add("Measured timing", "Talk & preparation", (1,))
    w.timing_summary = label("")
    timing.layout().addWidget(w.timing_summary)
    w.fit_button = button("Fit duration…", w.fit_requested.emit)
    timing.layout().addWidget(w.fit_button)
    timing.layout().addWidget(button("Keep these settings for this talk", w.pin_settings))


def build_account(w):
    account = w.add("Account — Codex", "Application", (0,))
    w.connection = label("Not signed in to ChatGPT.")
    account.layout().addWidget(w.connection)
    w.codex_signin = button("Sign in", w.sign_in_requested.emit)
    w.codex_signout = button("Sign out", lambda: w.sign_out_requested.emit())
    account.layout().addLayout(row(w.codex_signin, w.codex_signout))
    account.layout().addWidget(label("Sign-in and sign-out act immediately on the shared Codex account on this computer. Model and reasoning use application defaults with optional talk overrides."))
    account.layout().addStretch()


def build_engine(w):
    speech = w.add("Speech engine — Qwen", "AI & speech engine", (0,))
    w.engine_state, w.engine_model = label("Not loaded"), label("")
    speech.layout().addWidget(w.engine_state)
    speech.layout().addWidget(w.engine_model)
    w.load_gpu_button = button("Load model now", w.load_requested.emit, True)
    w.unload_gpu_button = button("Unload model now", w.unload_requested.emit)
    speech.layout().addLayout(row(w.load_gpu_button, w.unload_gpu_button))
    w.check_model_button = button("Check for model updates…", w.model_check_requested.emit)
    speech.layout().addWidget(w.check_model_button)
    for name, title, choices in (
        ("gpu_loading", "When to load an unloaded model", [("When speech is first needed (recommended)", "needed"), ("When I start a presentation", "start")]),
        ("gpu_retention", "When to release a loaded model", [("Never — keep loaded until I close AutoTalk", "session"),
            ("When the presentation ends", "presentation"), ("After 5 minutes without speech generation", "idle"),
            ("After each preparation or voice preview", "operation")])):
        speech.layout().addWidget(label(title, "title"))
        group = QButtonGroup(speech)
        setattr(w, name, group)
        for index, (title, value) in enumerate(choices):
            choice = QRadioButton(title)
            choice.setProperty("value", value)
            group.addButton(choice, index)
            speech.layout().addWidget(choice)
        group.buttons()[0].setChecked(True)
        group.buttonClicked.connect(lambda: w.engine_policy_changed.emit())
    speech.layout().addWidget(label("Prepared audio can play during background loading. Previews always load a needed model. Manual loading follows the saved release policy; leaving fullscreen is not presentation end. Unloading keeps downloaded files."))
    w.engine_policy_note = label("")
    speech.layout().addWidget(w.engine_policy_note)
    speech.layout().addStretch()



def build_clips(w):
    extras = w.add("Slide audio clips", "Presentation & recording", (2,))
    w.clip_select = combo([], w.show_clip)
    extras.layout().addWidget(w.clip_select)
    w.clip_gain = number(0, 2, 1, w.clip_changed)
    w.clip_gain.setSingleStep(.05)
    w.clip_placement = combo([("Before narration", "before"), ("After narration", "after")], w.clip_changed)
    fields = form(extras)
    fields.addRow("Volume", w.clip_gain)
    fields.addRow("Play", w.clip_placement)
    w.remove_clip_button = button("Remove", w.remove_clip)
    extras.layout().addLayout(row(button("Add…", w.add_clip), w.remove_clip_button))
    extras.layout().addStretch()
