# SPDX-License-Identifier: MIT
"""Scoped dialog components. Only a draft crosses the component boundary.

Controller access: project, edit_setting, codex_settings, error, log_message,
start_job, voice_context, configuration_changed, transport (previews), recorder
(read-only), refresh/request_refresh. Dialog-owned jobs and edits use the draft.
"""

import copy
import html
import json
import wave
from functools import partial
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabBar,
    QPlainTextEdit,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QFileDialog,
    QInputDialog,
    QCheckBox,
    QDoubleSpinBox,
    QSpinBox,
)
from .project import Voice, SETTING_DEFAULTS, LANGUAGES, SPEAKERS, read_settings, wav_duration
from .services import synthesize, preview_path, preview_text, extract_scope
from .media import import_clip
from .voices import library, load_voice, save_voice
from .ui import label, button, column, combo, number, row, form
from .settings_schema import SCHEMA, Setting
from .settings_fields import SettingField

SAMPLING = {
    "temperature": (0.0, 2.0, 0.9),
    "top_k": (1, 200, 50),
    "top_p": (0.01, 1.0, 1.0),
    "repetition_penalty": (1.0, 2.0, 1.05),
    "max_new_tokens": (128, 2048, 2048),
}


class VoiceEditor(QWidget):
    def __init__(self, dialog):
        super().__init__()
        self.dialog, self.loading = dialog, True
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.voice_identity = label('')
        self.layout().addWidget(self.voice_identity)
        self.voice_source = QTabBar()
        for title, source in (
            ("Predefined", "CustomVoice"),
            ("My voice", "Base"),
            ("Design", "VoiceDesign"),
            ("Saved", "Saved"),
        ):
            self.voice_source.setTabData(self.voice_source.addTab(title), source)
        self.voice_source.currentChanged.connect(self.voice_settings_changed)
        voice_field = SettingField(
            Setting('voice', 'Voice', 'Voice & language', 'Voice', kind='custom'),
            dialog.scope,
            dialog.edit_setting,
            self.voice_source,
        )
        dialog.fields['voice'] = voice_field
        self.layout().addWidget(voice_field)
        self.voice_panels = column(margin=0)
        self.layout().addWidget(self.voice_panels)
        predefined, personal, designed, saved = (column(margin=0) for _ in range(4))
        for page in (predefined, personal, designed, saved):
            self.voice_panels.layout().addWidget(page)
        self.speaker = combo(
            [(f"{name} — {description}", name) for name, description in SPEAKERS.items()], self.voice_settings_changed
        )
        form(predefined).addRow('Voice', self.speaker)
        predefined.layout().addWidget(
            label(
                'Every voice supports the talk language. Native languages indicate strongest pronunciation. '
                'Listen before choosing; no personal recording is needed.'
            )
        )
        personal.layout().addWidget(
            label('Record or import 10–30 seconds, then enter the exact words. Recording stops after 30 seconds.')
        )
        self.record_button = button('Record my voice', self.toggle_recording)
        personal.layout().addLayout(row(self.record_button, button('Import voice recording…', self.import_voice)))
        self.transcript = QPlainTextEdit()
        self.transcript.setMaximumHeight(100)
        self.transcript.setPlaceholderText('The exact words in your reference recording')
        self.transcript.textChanged.connect(self.voice_changed)
        personal.layout().addWidget(self.transcript)
        self.voice_description = QLineEdit()
        self.voice_description.setPlaceholderText('For example: warm, calm, clear pronunciation')
        self.voice_description.textChanged.connect(self.voice_settings_changed)
        form(designed).addRow('Describe the voice', self.voice_description)
        self.accept_voice_button = button('Use this designed voice', self.accept_designed_voice)
        designed.layout().addWidget(self.accept_voice_button)
        self.library_language = combo(['All languages', *LANGUAGES], self.refresh_library)
        saved.layout().addWidget(self.library_language)
        self.voice_library = QTableWidget(0, 3)
        self.voice_library.setHorizontalHeaderLabels(['Voice', 'Description', 'Languages'])
        self.voice_library.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.voice_library.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.voice_library.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.voice_library.verticalHeader().hide()
        self.voice_library.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.voice_library.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.voice_library.setMaximumHeight(120)
        self.voice_library.itemSelectionChanged.connect(lambda: self.sync(True))
        self.library_use = button('Use selected voice', self.use_saved_voice)
        saved.layout().addWidget(self.library_use)
        saved.layout().addWidget(self.voice_library)
        self.voice_audition = column(margin=12)
        self.voice_audition.layout().addWidget(
            label('First speech use downloads several GB; progress and cancellation appear here.')
        )
        self.voice_preview_button = button('Listen to a sample', self.preview_voice, True)
        self.save_voice_button = button('Save reusable voice…', self.save_personal_voice)
        self.voice_audition.layout().addLayout(row(self.voice_preview_button, self.save_voice_button))
        dialog.layout().insertWidget(dialog.layout().indexOf(dialog.status), self.voice_audition)
        if dialog.scope < 2:
            self.synthesis_widget = column(margin=0)
            self.sampling = {}
            self.override = QCheckBox('Override main speech generator sampling defaults')
            self.override.toggled.connect(self.sampling_changed)
            field = SettingField(
                Setting('delivery.sampling', 'Sampling', 'AI model', 'Speech model', kind='custom'),
                dialog.scope,
                dialog.edit_setting,
                self.override,
            )
            dialog.fields['delivery.sampling'] = field
            self.synthesis_widget.layout().addWidget(field)
            fields = form(self.synthesis_widget)
            for name, (low, high, default) in SAMPLING.items():
                spin = QSpinBox() if isinstance(default, int) else QDoubleSpinBox()
                spin.setRange(low, high)
                spin.setValue(default)
                spin.valueChanged.connect(self.sampling_changed)
                self.sampling[name] = spin
                fields.addRow(name.replace('_', ' ').capitalize(), spin)
        self.loading = False

    def load(self, preserve_candidate=False):
        self.loading = True
        try:
            voice = self.dialog.setting_value('voice')
            if not preserve_candidate or self.voice_source.currentIndex() != 3:
                self.voice_source.setCurrentIndex(
                    2
                    if voice.origin == 'designed' and voice.source == 'Base'
                    else ['CustomVoice', 'Base', 'VoiceDesign'].index(voice.source)
                )
            self.speaker.setCurrentIndex(self.speaker.findData(voice.speaker))
            self.voice_description.setText(voice.description)
            self.voice_identity.setText(voice.label)
            ref = voice.references.get(self.dialog.setting_value('language'), voice.references.get('default'))
            if self.transcript.toPlainText() != (ref.transcript if ref else ''):
                self.transcript.setPlainText(ref.transcript if ref else '')
            if self.dialog.scope < 2:
                sampling = self.dialog.setting_value('delivery.sampling')
                self.override.setChecked(bool(sampling))
                for key, spin in self.sampling.items():
                    if spin.value() != sampling.get(key, SAMPLING[key][2]):
                        spin.setValue(sampling.get(key, SAMPLING[key][2]))
                    spin.setEnabled(bool(sampling))
        finally:
            self.loading = False

    def sampling_changed(self):
        if not self.loading:
            self.dialog.edit_setting(
                'delivery.sampling',
                {k: v.value() for k, v in self.sampling.items()} if self.override.isChecked() else {},
            )

    def voice_context(self):
        candidate = copy.deepcopy(self.dialog.project)
        candidate.overrides = {
            key: copy.deepcopy(self.dialog.setting_value(key)) for key in SETTING_DEFAULTS if key != 'language'
        }
        candidate.language = self.dialog.setting_value('language')
        return candidate

    def toggle_recording(self):
        self.dialog.record_requested.emit(self)

    def sync(self, editable):
        w = self.dialog.window
        voice = self.dialog.setting_value("voice")
        for i in range(self.voice_panels.layout().count()):
            self.voice_panels.layout().itemAt(i).widget().setVisible(i == self.voice_source.currentIndex())
        for widget in (self.voice_source, self.voice_panels, self.voice_audition):
            widget.setEnabled(editable)
        self.library_use.setEnabled(editable and self.voice_library.currentRow() >= 0)
        self.voice_preview_button.setText(
            "Stop sample"
            if w.transport.preview_path
            else "Listen to selected voice" if self.voice_source.currentIndex() == 3 else "Listen to a sample"
        )
        context = self.voice_context()
        self.voice_preview_button.setEnabled(
            editable
            and (
                self.voice_library.currentRow() >= 0
                if self.voice_source.currentIndex() == 3
                else (
                    bool(context.voice_file)
                    if voice.source == "Base"
                    else bool(voice.description.strip()) if voice.source == "VoiceDesign" else True
                )
            )
        )
        self.accept_voice_button.setVisible(voice.source == "VoiceDesign")
        self.accept_voice_button.setEnabled(
            editable and voice.source == "VoiceDesign" and preview_path(context).is_file()
        )
        self.save_voice_button.setEnabled(
            editable
            and self.voice_source.currentIndex() != 3
            and (
                self.accept_voice_button.isEnabled()
                if voice.source == "VoiceDesign"
                else self.voice_preview_button.isEnabled()
            )
        )
        self.transcript.setEnabled(bool(context.voice_file) and editable)

    def voice_changed(self):
        if not self.loading:
            voice = copy.deepcopy(self.dialog.setting_value("voice"))
            ref = voice.references.get(self.dialog.setting_value("language"), voice.references.get("default"))
            if ref:
                ref.transcript = self.transcript.toPlainText()
                self.dialog.edit_setting("voice", voice)

    def import_voice(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import your voice", "", "PCM WAV recording (*.wav)")
        if path:
            self.set_voice(Path(path))

    def set_voice(self, path):
        try:
            self.dialog.window.transport.stop()
            duration = wav_duration(path)
            if not 3 <= duration <= 60:
                raise ValueError("Use a WAV reference recording between 3 and 60 seconds.")
            candidate = self.voice_context()
            candidate.set_voice(path)
            self.dialog.edit_setting("voice", candidate.voice)
        except (OSError, ValueError, EOFError, wave.Error) as error:
            self.dialog.window.error(str(error))

    def preview_voice(self):
        if self.dialog.window.transport.preview_path:
            self.dialog.window.transport.stop()
            return
        if self.dialog.window.recorder.source:
            self.dialog.window.error("Stop recording before previewing the voice.")
            return

        def done(path):
            self.dialog.window.transport.preview(path)
            self.dialog.window.log_message("Playing your voice preview.")

        candidate = self.voice_context()
        if self.voice_source.currentIndex() == 3:
            item = self.voice_library.item(self.voice_library.currentRow(), 0)
            if item is None:
                return
            try:
                load_voice(candidate, item.data(Qt.ItemDataRole.UserRole))
            except (OSError, ValueError) as error:
                self.dialog.window.error(str(error))
                return
        self.dialog.start_job("Generating voice preview…", partial(synthesize, candidate, preview=True), done)

    def voice_settings_changed(self):
        if self.loading:
            return
        voice = copy.deepcopy(self.dialog.setting_value("voice"))
        if self.voice_source.currentIndex() == 3:
            self.sync(True)
            return
        source = self.voice_source.tabData(self.voice_source.currentIndex())
        if source != voice.source:
            voice = Voice(source=source)
        voice.source = source
        voice.speaker = self.speaker.currentData()
        voice.description = self.voice_description.text()
        voice.name = (
            voice.speaker
            if voice.source == "CustomVoice"
            else "Designed voice" if voice.source == "VoiceDesign" else "My voice"
        )
        voice.origin = "designed" if voice.source == "VoiceDesign" else voice.origin
        self.dialog.edit_setting("voice", voice)

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
            if (
                self.library_language.currentText() not in ("All languages", languages)
                and self.library_language.currentText() not in languages
                and languages != "Multilingual"
            ):
                continue
            row = self.voice_library.rowCount()
            self.voice_library.insertRow(row)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self.voice_library.setItem(row, col, item)
        self.voice_library.resizeRowsToContents()
        self.voice_library.selectRow(
            next(
                (
                    row
                    for row in range(self.voice_library.rowCount())
                    if self.voice_library.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected
                ),
                0,
            )
        )

    def use_saved_voice(self):
        item = self.voice_library.item(self.voice_library.currentRow(), 0)
        if item:
            try:
                candidate = self.voice_context()
                load_voice(candidate, item.data(Qt.ItemDataRole.UserRole))
                self.dialog.edit_setting("voice", candidate.voice)
            except (OSError, ValueError) as error:
                self.dialog.window.error(str(error))

    def save_personal_voice(self):
        name, ok = QInputDialog.getText(
            self, "Save reusable voice", "Voice name", text=self.dialog.setting_value("voice").name
        )
        if not ok or not name.strip():
            return
        if self.dialog.setting_value("voice").source == "VoiceDesign" and not self.accept_designed_voice():
            return
        try:
            save_voice(self.voice_context(), name)
            self.refresh_library()
        except (OSError, ValueError) as error:
            self.dialog.window.error(str(error))

    def accept_designed_voice(self):
        candidate = self.voice_context()
        if candidate.voice.source != "VoiceDesign":
            return False
        path = preview_path(candidate)
        if not path.exists():
            self.dialog.window.error("Preview this design first, then accept the voice you heard.")
            return False
        description = candidate.voice.description
        try:
            candidate.set_voice(path, preview_text(candidate))
        except (OSError, ValueError) as error:
            self.dialog.window.error(str(error))
            return False
        voice = copy.deepcopy(candidate.voice)
        voice.name, voice.origin, voice.description = "Designed voice", "designed", description
        self.dialog.edit_setting("voice", voice)
        return True


class CodexModelPicker(QWidget):
    def __init__(self, dialog):
        super().__init__()
        self.dialog, self.loading = dialog, True
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.connection = label('')
        self.layout().addWidget(self.connection)
        self.layout().addWidget(
            button('Account settings…', lambda: dialog.preferences_requested.emit('Account', 'codex_signin'))
        )
        self.codex_model = combo([('Account default', '')], self.model_changed)
        self.codex_effort = combo([('Codex default', '')], self.model_settings_changed)
        fields = form(self)
        for key, editor in [('codex_model', self.codex_model), ('codex_effort', self.codex_effort)]:
            field = SettingField(SCHEMA[key], dialog.scope, dialog.edit_setting, editor)
            dialog.fields[key] = field
            fields.addRow(SCHEMA[key].label, field)
        self.loading = False

    def refresh_models(self):
        previous = self.loading
        self.loading = True
        wanted = self.dialog.setting_value("codex_model")
        self.codex_model.clear()
        default = next(
            (
                m.get("displayName") or m["model"]
                for m in self.dialog.window.codex_settings.get("models", [])
                if m["model"] == self.dialog.window.codex_settings.get("model")
            ),
            self.dialog.window.codex_settings.get("model", ""),
        )
        self.codex_model.addItem("Account default" + (f" ({default})" if default else ""), "")
        for model in self.dialog.window.codex_settings.get("models", []):
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
        model = self.codex_model.currentData() or self.dialog.window.codex_settings.get("model")
        selected = next((m for m in self.dialog.window.codex_settings.get("models", []) if m["model"] == model), {})
        wanted = self.dialog.setting_value("codex_effort")
        self.codex_effort.clear()
        default = self.dialog.window.codex_settings.get("effort") or selected.get("defaultReasoningEffort", "")
        self.codex_effort.addItem("Codex default" + (f" ({default})" if default else ""), "")
        for option in selected.get("supportedReasoningEfforts", []):
            effort = option["reasoningEffort"]
            self.codex_effort.addItem(effort, effort)
            self.codex_effort.setItemData(
                self.codex_effort.count() - 1, option.get("description", ""), Qt.ItemDataRole.ToolTipRole
            )
        if wanted and self.codex_effort.findData(wanted) < 0:
            self.codex_effort.addItem(wanted + " (refresh availability)", wanted)
        self.codex_effort.setCurrentIndex(max(0, self.codex_effort.findData(wanted)))
        self.loading = previous

    def model_changed(self):
        if not self.loading:
            self.dialog.edit_many(
                [('codex_model', self.codex_model.currentData() or '', False), ('codex_effort', '', False)]
            )

    def model_settings_changed(self):
        if not self.loading:
            self.dialog.edit_setting("codex_effort", self.codex_effort.currentData() or "")


class AudioAssets(QWidget):
    def __init__(self, dialog):
        super().__init__()
        self.dialog, self.loading = dialog, False
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        if dialog.scope == 2:
            self.clip_select = combo([], self.show_clip)
            self.layout().addWidget(self.clip_select)
            self.clip_gain = number(0, 2, 1, self.clip_changed)
            self.clip_gain.setSingleStep(0.05)
            self.clip_placement = combo(
                [('Before narration', 'before'), ('After narration', 'after')], self.clip_changed
            )
            fields = form(self)
            fields.addRow('Volume', self.clip_gain)
            fields.addRow('Play', self.clip_placement)
            self.remove_clip_button = button('Remove', self.remove_clip)
            self.layout().addLayout(row(button('Add…', self.add_clip), self.remove_clip_button))
        else:
            self.background_button = button('Add background track…', self.add_background)
            self.remove_background_button = button('Remove background', lambda: dialog.edit_setting('background', None))
            self.layout().addLayout(row(self.background_button, self.remove_background_button))

    def load(self):
        if self.dialog.scope != 2:
            background = self.dialog.project.background
            self.background_button.setText(
                'Background: ' + Path(background.file).name[:16] + '…' if background else 'Add background track…'
            )
            self.remove_background_button.setEnabled(background is not None)
            return
        self.loading = True
        try:
            selected = self.clip_select.currentIndex()
            self.clip_select.clear()
            self.clip_select.addItems([Path(c.file).name for c in self.dialog.slide.clips])
            self.clip_select.setCurrentIndex(min(max(0, selected), len(self.dialog.slide.clips) - 1))
        finally:
            self.loading = False
        self.show_clip()

    def show_clip(self):
        if self.loading or not self.dialog.project:
            return
        self.loading = True
        try:
            clips = self.dialog.slide.clips
            index = self.clip_select.currentIndex()
            valid = 0 <= index < len(clips)
            for widget in (self.clip_gain, self.clip_placement, self.remove_clip_button):
                widget.setEnabled(valid)
            if valid:
                if self.clip_gain.value() != clips[index].gain:
                    self.clip_gain.setValue(clips[index].gain)
                self.clip_placement.setCurrentIndex(self.clip_placement.findData(clips[index].placement))
        finally:
            self.loading = False

    def clip_changed(self):
        if self.loading or not self.dialog.project:
            return
        clips = copy.deepcopy(self.dialog.slide.clips)
        index = self.clip_select.currentIndex()
        if 0 <= index < len(clips):
            clips[index].gain = self.clip_gain.value()
            clips[index].placement = self.clip_placement.currentData()
            self.dialog.edit_setting('clips', clips)

    def remove_clip(self):
        clips = copy.deepcopy(self.dialog.slide.clips)
        index = self.clip_select.currentIndex()
        if 0 <= index < len(clips):
            clips.pop(index)
            self.dialog.edit_setting('clips', clips)

    def add_clip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Choose presentation audio', '', 'Audio (*.wav *.mp3 *.flac *.ogg *.m4a *.mp4);;All files (*)'
        )
        if path:
            self.dialog.start_job(
                'Importing audio clip…',
                partial(import_clip, self.dialog.project, Path(path)),
                lambda clip: self.dialog.edit_setting('clips', self.dialog.slide.clips + [clip]),
                project_returning=True,
            )

    def add_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Choose background audio', '', 'Audio (*.wav *.mp3 *.flac *.ogg *.m4a);;All files (*)'
        )
        if path:
            self.dialog.start_job(
                'Importing background track…',
                partial(import_clip, self.dialog.project, Path(path), placement='background'),
                self.install_background,
                project_returning=True,
            )

    def install_background(self, clip):
        clip.gain = self.dialog.project.background_gain
        clip.loop = self.dialog.project.background_loop
        self.dialog.edit_setting('background', clip)


class ConferencePanel(QWidget):
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        for spec in SCHEMA.values():
            if spec.page == 'Talk':
                dialog.add_field(spec, self)
                if spec.key == 'conference_url':
                    self.read_button = button('Read conference website', self.read_conference)
                    dialog.field_layout(self).addRow(self.read_button)
        self.sources = label('')
        self.sources.setOpenExternalLinks(True)
        self.layout().addWidget(self.sources)

    def load(self):
        p = self.dialog.project
        self.read_button.setEnabled(p.mode != 'Quick')
        for key in ('audience', 'objective', 'conference_url', 'scope'):
            self.dialog.fields[key].setEnabled(p.mode != 'Quick')
        self.sources.setText(
            'Sources: '
            + ' · '.join(f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>' for url in p.sources)
            if p.sources
            else ''
        )

    def read_conference(self):
        url = self.dialog.project.conference_url.strip()
        if not url:
            self.dialog.window.error('Enter a conference website URL, or type the scope directly below.')
            return

        def done(result):
            self.dialog.edit_many([('scope', result['scope'], False), ('sources', result['sources'], False)])

        self.dialog.start_job(
            'Reading conference website…',
            partial(extract_scope, url, model=self.dialog.project.codex_model, effort=self.dialog.project.codex_effort),
            done,
            project_returning=True,
        )
