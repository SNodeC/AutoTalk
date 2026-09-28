"""Fixed-scope settings editors; Project remains the settings resolution authority."""
import copy
import json
import wave
from dataclasses import asdict
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, QMicrophonePermission
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QTableWidgetItem,
    QFileDialog, QInputDialog, QTabBar, QPlainTextEdit, QLineEdit, QTableWidget,
    QCheckBox, QAbstractItemView, QHeaderView, QScrollArea, QWidget)

from .project import Project, Voice, SETTING_DEFAULTS, LANGUAGES, SPEAKERS, read_settings, wav_duration
from .runtime import data_dir
from .services import synthesize, preview_path, preview_text
from .voices import library, load_voice, save_voice
from .options import SettingsPanel
from .ui import SectionDialog, label, button, column, combo, number, row, form, disclosure


class SettingsDialog(SectionDialog):
    def __init__(self, window, scope):
        super().__init__(window, "Settings")
        self.scope, self.slide_index = scope, 0
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
        return w.project.setting(name, self.slide) if self.scope and w.project else w.defaults.get(name, copy.deepcopy(SETTING_DEFAULTS[name][0]))

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
            selected = self.window.clip_select.currentIndex()
            self.window.clip_select.blockSignals(True)
            self.window.clip_select.clear()
            self.window.clip_select.addItems([Path(clip.file).name for clip in self.slide.clips])
            self.window.clip_select.setCurrentIndex(min(max(0, selected), len(self.slide.clips)-1))
            self.window.clip_select.blockSignals(False)
            self.window.show_clip()
        self.options.load(self.window.project)
        self.refresh_models()
        self.loading = previous

    def show_section(self, section=None, focus=None):
        w = self.window
        if self.scope and not w.project:
            return
        if not self.isVisible():
            self.slide_index = w.transport.index
            self.defaults_before = copy.deepcopy(w.defaults)
            self.screen_before = w.screen.currentIndex()
            self.before = copy.deepcopy(w.project) if self.scope and not w.job else None
        self.setWindowTitle("Application defaults" if self.scope == 0 else
                            f"Talk settings — {w.project.title}" if self.scope == 1 else
                            f"Slide settings — {self.slide_index + 1}")
        self.load_settings()
        self.refresh_library()
        self.options.refresh_presets()
        self.show()
        super().show_section(section or ("Application" if self.scope == 0 else "Talk & preparation" if self.scope == 1 else "Voice & language"),
                             getattr(self, focus) if isinstance(focus, str) else focus)

    def sync(self, editable):
        w = self.window
        super().sync(editable)
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
        self.buffer_toggle.setVisible(self.scope < 2 and self.setting_value("mode") == "Realtime")
        self.codex_connection.setText(w.connection.text())
        self.voice_model.setText("Qwen3-TTS 1.7B — " + voice.source + "\n" + w.engine_state.text())

    def done(self, result):
        w = self.window
        if w.recorder.source or w.job and self.before is not None and not getattr(w.job, "preserve_playback", False):
            self.status.setText("Stop the current operation or voice recording before closing.")
            return
        if w.transport.preview_path:
            w.transport.stop()
        accepted = result == QDialog.DialogCode.Accepted
        if self.scope == 0:
            if accepted:
                w.preferences.setValue("setting_defaults", json.dumps(w.defaults, default=lambda v: asdict(v)))
                w.preferences.setValue("presentation_display", w.screen.currentText())
            else:
                w.defaults = self.defaults_before
                w.screen.setCurrentIndex(self.screen_before)
            w.speech_preferences(accepted)
            if w.project:
                w.apply_defaults(w.project)
        elif self.before is not None:
            if not accepted:
                if self.scope == 2:
                    w.project.slides[self.slide_index] = self.before.slides[self.slide_index]
                else:
                    w.project = self.before
                w.adopt(w.project)
            if not w.save():
                return
        self.before = None
        QDialog.done(self, result)
        w.load_settings()
        w.refresh()

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
        try:
            if self.window.recorder.source:
                self.window.record_timer.stop()
                path = self.window.recorder.stop(data_dir() / "recording.wav")
                self.record_button.setText("Record my voice")
                self.window.refresh()
                self.set_voice(path)
            else:
                permission = QMicrophonePermission()
                application = QApplication.instance()
                status = application.checkPermission(permission)
                if status == Qt.PermissionStatus.Undetermined:
                    application.requestPermission(permission, self, lambda _: self.toggle_recording())
                    return
                if status == Qt.PermissionStatus.Denied:
                    raise RuntimeError("Allow microphone access for AutoTalk in system privacy settings, or import a reference recording.")
                self.window.transport.stop()
                self.window.recorder.editor = self
                self.window.recorder.start()
                self.record_button.setText("Stop recording")
                self.window.refresh()
                self.window.record_timer.start(30000)
        except (RuntimeError, OSError, ValueError, wave.Error) as error:
            self.window.record_timer.stop()
            self.record_button.setText("Record my voice")
            self.window.refresh()
            self.window.error(str(error))


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



def build_settings(w):
    codex = w.add("Narration AI — Codex", "AI & speech engine", (0, 1))
    codex.layout().addWidget(label("Model and reasoning for the selected scope. Slide images, text and conference context are sent to Codex; voice references stay local."))
    w.codex_connection = label("")
    codex.layout().addWidget(w.codex_connection)
    codex.layout().addWidget(button("Account settings…", lambda: w.window.settings[0].show_section("Application")))
    w.codex_model = combo([("Account default", "")], w.model_changed)
    w.codex_effort = combo([("Codex default", "")], w.model_settings_changed)
    fields = form(codex)
    fields.addRow("Model", w.codex_model)
    fields.addRow("Reasoning effort", w.codex_effort)
    codex.layout().addStretch()
    timing = w.add("Preparation & timing", "Talk & preparation", (0, 1))
    w.tolerance = number(0, 600, 15, lambda: w.edit_setting("tolerance_seconds", w.tolerance.value()), " sec")
    form(timing).addRow("Allowed timing difference", w.tolerance)
    timing.layout().addWidget(w.options)
    w.settings_mode = combo(["Prepared", "Quick", "Realtime"], lambda: w.edit_setting("mode", w.settings_mode.currentText()))
    form(timing).addRow("Preparation mode", w.settings_mode)
    language = w.add("Language", "Voice & language")
    w.settings_language = combo(LANGUAGES, lambda: w.edit_setting("language", w.settings_language.currentText()))
    w.settings_language.setToolTip("Changing language keeps existing words. Create or translate text explicitly. A single-language version fixes its slides to the talk language.")
    form(language).addRow("Narration language", w.settings_language)
    language.layout().addWidget(label("Choose how language versions and passages are organized. Add language version creates a separate version; selecting a version preserves the others."))
    buffer = column(margin=0)
    for name, destination in (("language_policy", language), ("buffer_seconds", buffer)):
        taken = w.options.form.takeRow(w.options.fields[name])
        form(destination).addRow(taken.labelItem.widget(), taken.fieldItem.widget())
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
    age = w.options.fields["delivery.attributes.age"]
    taken = age.parentWidget().layout().takeRow(age)
    design_form.addRow(taken.labelItem.widget(), age)
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
        model.layout().addWidget(button("Speech engine settings…", lambda: w.window.settings[0].show_section("AI & speech engine", focus=w.window.engine_state)))
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
    playback = w.add("Playback", "Presentation & recording")
    form(playback).addRow("Pause after slide", w.pause)
    w.settings_after = combo([("Advance automatically", "advance"), ("Pause for live demo", "demo"), ("Wait for presenter", "pause")], lambda: w.edit_setting("after", w.settings_after.currentData()))
    form(playback).addRow("After slide", w.settings_after)
    if w.scope == 1:
        playback.layout().addWidget(button("Display && sound settings…", lambda: w.window.settings[0].show_section("Application", focus=w.window.screen)))
    recording = w.add("Recording", "Presentation & recording", (0, 1))
    form(recording).addRow("Recording", w.options.record)
    recording.layout().addWidget(label("Screen capture continues until End presentation and save video. Slides-and-speech recordings finish after the last slide. Screen sharing is authorized separately from the presentation display."))
    recording.layout().addWidget(w.options.recording_widget)
    for title, names in (("Advanced recording", ("recording_policy",)), ("Output quality", ("export_rate", "export_bitrate"))):
        panel = column(margin=0)
        fields = form(panel)
        for name in names:
            taken = w.options.recording_widget.layout().takeRow(w.options.fields[name])
            fields.addRow(taken.labelItem.widget(), taken.fieldItem.widget())
        disclosure(recording, title, panel)
    recording.layout().addStretch()
    background = w.add("Background audio", "Presentation & recording", (0, 1))
    w.background_gain = number(0, 100, 15, w.background_changed, " %")
    w.background_gain.setSingleStep(5)
    w.background_loop = QCheckBox("Loop")
    w.background_loop.toggled.connect(w.background_changed)
    form(background).addRow("Background volume", w.background_gain)
    background.layout().addWidget(w.background_loop)
    background.layout().addStretch()

    voice.parentWidget().layout().removeWidget(language)
    voice.parentWidget().layout().insertWidget(1, language)
    for path, widget in (("delivery.sampling", w.options.override), ("after", w.settings_after), ("language", w.settings_language), ("mode", w.settings_mode), ("pause_seconds", w.pause),
                         ("tolerance_seconds", w.tolerance), ("codex_model", w.codex_model), ("codex_effort", w.codex_effort),
                         ("background_gain", w.background_gain), ("background_loop", w.background_loop)):
        w.options.fields[path] = widget
    for path, widget in w.options.fields.items():
        if path in SETTING_DEFAULTS:
            w.options.add_inheritance(path, widget)
    w.pages.currentChanged.connect(lambda: (w.load_settings(), w.window.refresh()))
    for table in (w.voice_library,):
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
