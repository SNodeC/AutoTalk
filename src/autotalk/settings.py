# SPDX-License-Identifier: MIT
"""Draft-owned scoped settings. Project remains the resolution authority.

The controller interface is project, edit_setting, codex_settings, error,
log_message, start_job, voice_context, configuration_changed, transport,
recorder (read-only), refresh/request_refresh. Begin/finish callbacks own live
state and persistence; signals route preferences, fitting and voice recording.
Components see only the draft. apply_edit is shared by drafting and Save replay.
"""
import copy
from dataclasses import asdict

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QScrollArea, QWidget
from .project import SETTING_DEFAULTS
from .ui import SectionDialog, label, button, form, disclosure, column
from .settings_schema import SCHEMA, PAGES
from .settings_fields import SettingField
from .settings_components import VoiceEditor, CodexModelPicker, AudioAssets, ConferencePanel
from .options import DeliveryPresets


def apply_edit(project, scope, index, operation):
    key, value, inherit = copy.deepcopy(operation)
    if key in SETTING_DEFAULTS:
        if scope == 0:
            values = dict(project.defaults)
            values.pop(key, None) if inherit else values.update({key: value})
            project.set_defaults(values)
        else:
            project.set_setting(key, value, project.slides[index] if scope == 2 else None, inherit)
    elif key == 'clips':
        project.slides[index].clips = value
    else:
        setattr(project, key, value)


def inheritance(project, key, scope, slide=None):
    local = (key in project.defaults if scope == 0 else key in slide.overrides if scope == 2 else
             key in project.overrides or key == 'language' and bool(project.version.language))
    if local:
        return 'set here', True
    if scope == 2 and project.setting_source(key) == 'Talk setting':
        return 'from talk', False
    return ('from app' if scope and key in project.defaults else 'built-in'), False


class ScopedSettingsDialog(SectionDialog):
    preferences_requested = Signal(str, str)
    record_requested = Signal(object)
    fit_requested = Signal()

    def __init__(self, window, scope, begin, finish):
        super().__init__(window, 'Settings')
        self.scope, self.slide_index = scope, 0
        self.begin, self.finish = begin, finish
        self.project = None
        self.operations, self.fields = [], {}
        self.loading, self.operation = False, None
        self.buttons.setStandardButtons(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.hint = label('')
        self.hint.setContentsMargins(12, 0, 12, 0)
        self.layout().insertWidget(self.layout().count()-1, self.hint)
        self.build_pages()
        self.order_focus()
        self.navigation.currentRowChanged.connect(self.page_changed)
        self.navigation.setCurrentRow(0)

    def order_focus(self):
        # Derive keyboard order from the same layouts as the schema pages.
        widgets = []
        def collect(layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                widget = item.widget()
                if isinstance(widget, QScrollArea):
                    collect(widget.widget().layout())
                elif widget and widget.focusPolicy() & Qt.FocusPolicy.TabFocus:
                    widgets.append(widget)
                elif widget and widget.layout():
                    collect(widget.layout())
                elif item.layout():
                    collect(item.layout())
        collect(self.layout())
        for previous, following in zip(widgets, widgets[1:]):
            QWidget.setTabOrder(previous, following)

    @property
    def pending(self):
        return self.operation if self.operation and self.operation.project_returning else None

    @property
    def slide(self):
        return self.project.slides[self.slide_index] if self.scope == 2 and self.project else None

    def setting_value(self, key):
        if key not in SETTING_DEFAULTS:
            return getattr(self.project, key)
        if self.scope == 0:
            return self.project.defaults.get(key, copy.deepcopy(SETTING_DEFAULTS[key][0]))
        return self.project.setting(key, self.slide)

    def add_field(self, spec, parent):
        field = SettingField(spec, self.scope, self.edit_setting)
        self.fields[spec.key] = field
        caption = {'language': ('Default narration language', 'Language', 'Language of this slide'),
                   'mode': ('Default mode', 'Mode', 'Mode')}.get(spec.key)
        layout = self.field_layout(parent)
        layout.addRow(caption[self.scope] if caption else spec.label, field)
        return field

    @staticmethod
    def field_layout(parent):
        return next((parent.layout().itemAt(i).layout() for i in range(parent.layout().count())
                     if isinstance(parent.layout().itemAt(i).layout(), QFormLayout)), None) or form(parent)

    def build_pages(self):
        for page in PAGES:
            self.build_page(page)
        for index in range(self.pages.count()):
            self.pages.widget(index).widget().layout().addStretch()

    def build_page(self, page):
        rows = [s for s in SCHEMA.values() if s.page == page and self.scope in s.scopes]
        if page == 'Talk':
            if self.scope == 1:
                section = self.add('Talk & conference', page)
                self.conference = ConferencePanel(self)
                section.layout().addWidget(self.conference)
                section = self.add('Inherited settings', page)
                section.layout().addWidget(label('Keep the currently inherited values with this talk so future changes to Talk defaults do not affect it.'))
                section.layout().addWidget(button('Keep these settings for this talk', self.pin))
            return
        sections = {}
        if page == 'Voice & language':
            self.voice = VoiceEditor(self)
            self.add('Voice', page).layout().addWidget(self.voice)
        if page == 'AI model' and self.scope < 2:
            self.models = CodexModelPicker(self)
            self.add('Narration AI — Codex', page).layout().addWidget(self.models)
        for spec in rows:
            if spec.kind == 'custom':
                continue
            if spec.section not in sections:
                if spec.section == "Vocal attributes":
                    parent = self.add("Vocal attributes", page)
                    sections[spec.section] = column(margin=0)
                    disclosure(parent, "More vocal attributes", sections[spec.section])
                else:
                    sections[spec.section] = self.add(spec.section, page)
            self.add_field(spec, sections[spec.section])
            if spec.key == "recording_destination":
                sections[spec.section].layout().addWidget(button("Choose video destination…", self.choose_destination))
        self.build_extras(page, sections)

    def build_extras(self, page, sections):
        if page == 'Writing & delivery':
            self.presets = DeliveryPresets(self)
            self.add('Delivery library', page).layout().addWidget(self.presets)
        elif page == 'Timing & playback' and self.scope < 2:
            section = self.add('Measured timing' if self.scope == 1 else 'This computer', page)
            if self.scope == 1:
                self.timing_summary = label('')
                self.fit_button = button('Save and fit…', self.save_and_fit)
                section.layout().addWidget(self.timing_summary)
                section.layout().addWidget(self.fit_button)
            section.layout().addWidget(button('Display & sound settings…', lambda: self.preferences_requested.emit('Display & sound', 'screen')))
        elif page == 'Audio & recording' and self.scope:
            self.assets = AudioAssets(self)
            section = sections.get('Background audio') if self.scope == 1 else None
            section = section or self.add('Slide clips', page)
            section.layout().insertWidget(1, self.assets)
        elif page == 'AI model' and self.scope < 2:
            section = self.add('Speech model — Qwen', page)
            self.voice_model = label('')
            section.layout().addWidget(self.voice_model)
            section.layout().addWidget(button('Speech engine settings…', lambda: self.preferences_requested.emit('Speech engine', 'engine_state')))
            section.layout().addWidget(self.voice.synthesis_widget)

    def show_section(self, section=None, focus=None):
        if self.scope and not self.window.project:
            return
        if not self.isVisible():
            self.slide_index = self.window.transport.index
            self.begin(self)
            self.operations = []
            self.existing_files = self.media_files()
        self.setWindowTitle('Talk defaults' if self.scope == 0 else 'Talk settings — '+self.project.title if self.scope == 1 else f'Slide sound — slide {self.slide_index+1}')
        self.load_settings()
        self.voice.refresh_library()
        self.presets.refresh_presets()
        if isinstance(focus, str):
            focus = self.fields[focus].editor
        super().show_section(section or ('Talk' if self.scope == 1 else 'Voice & language'), focus)

    def load_settings(self, *_, preserve_candidate=False):
        if not self.project:
            return
        self.loading = True
        try:
            with self.project.pass_cache():
                for key, field in self.fields.items():
                    source, overridden = inheritance(self.project, key, self.scope, self.slide) if key in SETTING_DEFAULTS else ('', False)
                    field.load(self.setting_value(key), source, overridden)
                self.voice.load(preserve_candidate)
                if self.scope < 2:
                    self.models.refresh_models()
                if self.scope:
                    self.assets.load()
        finally:
            self.loading = False
        self.page_changed()

    def page_changed(self):
        self.sync(not self.operation)
        if self.scope == 1 and self.project and self.navigation.currentItem().text() == 'Timing & playback':
            self.sync_timing()

    def edit_setting(self, name, value, inherit=False):
        self.edit_many([(name, value, inherit)])

    def edit_many(self, operations):
        if self.loading or not self.project:
            return
        for operation in copy.deepcopy(operations):
            apply_edit(self.project, self.scope, self.slide_index, operation)
            self.operations.append(operation)
        self.load_settings(preserve_candidate=True)

    def choose_destination(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save presentation video", "presentation.mp4", "MP4 video (*.mp4)")
        if path:
            self.edit_setting("recording_destination", path)

    def pin(self):
        self.edit_many([(key, self.project.setting(key), False) for key, (_, scopes) in SETTING_DEFAULTS.items() if 1 in scopes])

    def sync(self, editable, job=None):
        if not self.project:
            return
        self.buttons.setEnabled(True)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(not self.pending and not self.window.recorder.source)
        self.cancel_job.setVisible(job is not None or bool(self.window.recorder.source))
        self.cancel_job.setText('Stop voice recording' if self.window.recorder.source else 'Cancel operation')
        if not self.isVisible():
            return
        page = self.navigation.currentItem().text()
        self.pages.setEnabled(editable and not self.pending)
        self.voice.voice_audition.setVisible(page == 'Voice & language')
        if page == 'Voice & language':
            self.voice.sync(editable and not self.operation)
        self.hint.setText('Save applies to talks and slides that inherit these values.' if self.scope == 0 else 'Save applies to this talk.' if self.scope == 1 else 'Save applies to this slide.')
        if page in ('Voice & language', 'Writing & delivery'):
            self.hint.setText(self.hint.text()+' Library actions save to the shared library immediately.')
        self.sync_fields()
        if self.scope < 2:
            self.models.refresh_models()
            self.models.connection.setText(self.window.codex_settings.get('account','Not signed in to ChatGPT.'))
            self.voice_model.setText('Qwen3-TTS 1.7B — '+self.setting_value('voice').source)
        if self.scope == 1:
            self.conference.load()

    def sync_fields(self):
        voice = self.setting_value('voice')
        for key, field in self.fields.items():
            if key.startswith('delivery.') and key != 'delivery.sampling':
                field.setEnabled(voice.source != 'Base')
        self.fields['delivery.attributes.age'].setEnabled(voice.source == 'VoiceDesign')
        self.fields['delivery.attributes.accent'].setEnabled(voice.source != 'Base' and self.setting_value('language') == 'Chinese')
        self.fields['language'].setEnabled(self.scope != 2 or self.setting_value('language_policy') != 'version')
        for key, mode in [('quick_timing','Quick'),('realtime_script','Realtime'),('speech_priority','Realtime'),('buffer_seconds','Realtime')]:
            if key in self.fields:
                self.fields[key].setEnabled(self.setting_value('mode') == mode)
        if self.scope < 2:
            screen = self.setting_value('recording_source') == 'screen'
            self.fields['capture_microphone'].setEnabled(screen)
            self.fields['recording_policy'].setEnabled(not screen)

    def sync_timing(self):
        from .app import clock
        p = self.project
        with p.pass_cache():
            ready = sum(p.ready(s) for s in p.included_slides)
            self.timing_summary.setText(f'Target {clock(p.target_minutes*60)} · Audio {clock(p.total_seconds)}\n{ready}/{len(p.included_slides)} included slides have current audio.')
            self.fit_button.setEnabled(not self.pending and all(p.text_ready(s) for s in p.included_slides))

    def start_job(self, title, function, callback, *, project_returning=False):
        draft, existing = self.project, self.existing_files
        def delivered(result):
            if self.isVisible() and self.project is draft:
                callback(result)
        job = self.window.start_job(title, function, delivered, save_before=False)
        if job:
            self.operation = job
            job.project_returning = project_returning
            def finished():
                if self.operation is job:
                    self.operation = None
                if job.task.cancelled.is_set():
                    self.clean_media(draft, existing)
                if self.isVisible():
                    self.sync(True)
            job.finished.connect(finished)
            self.sync(False, job)
        return job

    def media_files(self, project=None):
        project = project or self.project
        return set(project.root.glob('media/*.wav')) | set(project.root.glob('voice/**/*.wav'))

    def clean_media(self, draft, existing):
        def references(value):
            if isinstance(value, dict):
                return {value.get('file', '')} | set().union(*(references(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(references(v) for v in value))
            return set()
        live = self.window.project
        protected = references(asdict(live)) if live and live.root == draft.root else set()
        for path in self.media_files(draft) - existing:
            if str(path.relative_to(draft.root)) not in protected:
                path.unlink(missing_ok=True)

    def done(self, result):
        if self.project is None:
            QDialog.done(self, result)
            return
        if result == QDialog.DialogCode.Accepted and self.pending:
            self.status.setText('Wait for the current import or conference operation before saving.')
            return
        if not self.finish(self, result):
            return
        if result != QDialog.DialogCode.Accepted:
            if self.operation:
                self.operation.task.cancelled.set()
            self.clean_media(self.project, self.existing_files)
        QDialog.done(self, result)

    def save_and_fit(self):
        self.accept()
        if not self.isVisible():
            self.fit_requested.emit()


class TalkDefaultsDialog(ScopedSettingsDialog):
    def __init__(self, window, begin, finish):
        super().__init__(window, 0, begin, finish)


class TalkSettingsDialog(ScopedSettingsDialog):
    def __init__(self, window, begin, finish):
        super().__init__(window, 1, begin, finish)


class SlideSettingsDialog(ScopedSettingsDialog):
    def __init__(self, window, begin, finish):
        super().__init__(window, 2, begin, finish)
