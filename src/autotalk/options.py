"""Editors for the project's delivery and workflow configuration."""
import json
import uuid
from dataclasses import asdict
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget)

from .project import Delivery, STYLES, SETTING_DEFAULTS, read_settings
from .runtime import data_dir

ATTRIBUTES = {
    "pitch": ("Low", "Medium", "High"),
    "texture": ("Clear", "Warm", "Breathy", "Raspy"),
    "energy": ("Low", "Moderate", "High"),
    "pace": ("Slow", "Moderate", "Brisk"),
    "age": ("Young adult", "Middle-aged adult", "Older adult"),
    "articulation": ("Natural", "Precise", "Relaxed"),
    "projection": ("Soft", "Conversational", "Confident"),
    "accent": ("Beijing Mandarin", "Sichuan Mandarin"),
    "expression": ("Restrained laughter", "Audible sigh", "Thoughtful hesitation", "Enthusiastic interjection"),
}
SAMPLING = {"temperature": (0.0, 2.0, 0.9), "top_k": (1, 200, 50),
            "top_p": (0.01, 1.0, 1.0), "repetition_penalty": (1.0, 2.0, 1.05),
            "max_new_tokens": (128, 2048, 2048)}


class SettingsPanel(QWidget):
    changed = Signal()

    def __init__(self, window):
        from .ui import disclosure
        super().__init__()
        self.window = window
        self.inheritance = {}
        self.project = None
        self.loading = False
        self.fields = {}
        self.vocal = []
        box = QVBoxLayout(self)
        self.form = QFormLayout()
        box.addLayout(self.form)
        self.combo("language_policy", "Language arrangement", [
            ("Separate versions and mixed passages", "mixed"),
            ("Separate versions; one language per slide", "slide"),
            ("Separate single-language versions", "version")])
        self.combo("quick_timing", "Quick timing policy", [
            ("Fit, then start (up to three revisions)", "fit"),
            ("Generate once, then start", "once"),
            ("Require timing match before start", "require")])
        self.combo("realtime_script", "Realtime narration", [
            ("Write the complete script first", "whole"),
            ("Plan the deck; write ahead by slide", "ahead")])
        self.combo("speech_priority", "Realtime speech priority", [("Consistency first", "consistency"), ("Earliest playback", "earliest")])
        buffer = QDoubleSpinBox()
        buffer.setRange(2, 30)
        buffer.setSuffix(" seconds")
        self.bind("buffer_seconds", "Realtime startup/refill buffer", buffer, buffer.valueChanged)
        main_form = self.form
        self.delivery_widget = QWidget()
        delivery_box = QVBoxLayout(self.delivery_widget)
        self.form = QFormLayout()
        delivery_box.addLayout(self.form)
        self.combo("writing_style", "Writing style", [(s, s) for s in STYLES])
        self.combo("delivery.style", "Spoken delivery", [(s, s) for s in STYLES])
        self.presets = QComboBox()
        self.form.addRow("Delivery presets — shared by all talks", self.presets)
        row = QHBoxLayout()
        self.use_preset_button = QPushButton("Use preset")
        for button, callback in ((QPushButton("Save delivery preset…"), self.save_preset), (self.use_preset_button, self.use_preset)):
            button.clicked.connect(callback)
            row.addWidget(button)
        self.form.addRow(row)
        self.refresh_presets()
        advanced = QWidget()
        self.form = QFormLayout(advanced)
        disclosure(self.delivery_widget, "More vocal attributes", advanced)
        for name, values in ATTRIBUTES.items():
            widget = self.combo("delivery.attributes." + name, name.capitalize(),
                                [("Model default", "")] + [(v, v) for v in values])
            self.vocal.append(widget)
        for field, title, placeholder in (
            ("delivery.attributes.persona", "Speaker background / persona", "For example: an experienced software researcher"),
            ("delivery.instructions", "Custom vocal directions", "Combine attributes and optional expressive cues"),
            ("delivery.progression", "Gradual delivery across slides", "For example: calm opening, build energy, reflective conclusion")):
            widget = QLineEdit()
            widget.setPlaceholderText(placeholder)
            self.bind(field, title, widget, widget.textChanged)
            self.vocal.append(widget)
        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        self.form.addRow(self.explanation)
        self.synthesis_widget = QWidget()
        self.form = QFormLayout(self.synthesis_widget)
        self.override = QCheckBox("Override main speech generator sampling defaults")
        self.override.toggled.connect(self.sampling_changed)
        self.form.addRow("Advanced synthesis", self.override)
        self.sampling = {}
        for name, (low, high, default) in SAMPLING.items():
            spin = QSpinBox() if isinstance(default, int) else QDoubleSpinBox()
            spin.setRange(low, high)
            if isinstance(spin, QDoubleSpinBox):
                spin.setSingleStep(0.05)
            spin.setValue(default)
            spin.valueChanged.connect(self.sampling_changed)
            self.sampling[name] = spin
            self.form.addRow(name.replace("_", " ").capitalize(), spin)
        self.recording_widget = QWidget()
        self.form = QFormLayout(self.recording_widget)
        self.record = QCheckBox("Record presentation as a video")
        self.fields["record_presentation"] = self.record
        self.record.toggled.connect(lambda value: self.window.edit_setting("record_presentation", value))
        self.record.setToolTip("Recording begins when the presentation starts. Choose slides or screen recording in Presentation settings → Recording.")
        self.combo("recording_source", "Recording source", [("Slide video + narration", "slides"), ("Screen + system audio (Linux)", "screen")])
        microphone = QCheckBox("Include microphone in screen recording")
        self.bind("capture_microphone", "Live commentary", microphone, microphone.toggled)
        self.combo("recording_policy", "Recording pauses", [
            ("Keep fullscreen pauses; omit time outside fullscreen", "fullscreen"),
            ("Keep all elapsed time", "all"),
            ("Omit manual pauses, buffering, and time outside fullscreen", "content")])
        path = QLineEdit()
        path.setPlaceholderText("Default: a new video in this project's recordings folder")
        self.bind("recording_destination", "Video destination", path, path.textChanged)
        self.destination_button = QPushButton("Choose video destination…")
        self.destination_button.clicked.connect(self.choose_destination)
        self.form.addRow(self.destination_button)
        self.combo("export_rate", "Export audio sample rate", [("24 kHz (native)", 24000), ("44.1 kHz", 44100), ("48 kHz", 48000)])
        self.combo("export_bitrate", "MP4 / M4A audio encoding", [("AAC 96 kbit/s", 96000), ("AAC 128 kbit/s", 128000), ("AAC 192 kbit/s", 192000)])
        self.form = main_form

    def bind(self, path, label, widget, signal):
        self.fields[path] = widget
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.form.addRow(label, widget)
        signal.connect(lambda *args, p=path: self.edit(p))
        return widget

    def combo(self, path, label, choices):
        widget = QComboBox()
        for text, value in choices:
            widget.addItem(text, value)
        return self.bind(path, label, widget, widget.currentIndexChanged)

    def add_inheritance(self, path, widget):
        parent = widget.parentWidget()
        container = QWidget(parent)
        parent.layout().replaceWidget(widget, container)
        box = QHBoxLayout(container)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(widget, 1)
        reset = QPushButton()
        reset.setToolTip("Remove this override and use the parent setting")
        reset.clicked.connect(lambda: self.window.edit_setting(path, None, inherit=True))
        box.addWidget(reset)
        self.inheritance[path] = (container, reset)

    def edit(self, path):
        if self.loading:
            return
        widget = self.fields[path]
        value = widget.currentData() if isinstance(widget, QComboBox) else widget.isChecked() if isinstance(widget, QCheckBox) else widget.text() if isinstance(widget, QLineEdit) else widget.value()
        if path in SETTING_DEFAULTS:
            self.window.edit_setting(path, value)
        elif self.project:
            setattr(self.project, path, value)
            self.changed.emit()

    def sampling_changed(self, *_):
        if not self.loading:
            self.window.edit_setting("delivery.sampling", {k: v.value() for k, v in self.sampling.items()} if self.override.isChecked() else {})

    def load(self, project):
        self.project, self.loading = project, True
        w = self.window
        scope = w.scope
        for path, widget in self.fields.items():
            value = w.setting_value(path) if path in SETTING_DEFAULTS else getattr(project, path, "")
            if path == "background_gain":
                value *= 100
            if isinstance(widget, QComboBox):
                index = widget.findData(value)
                widget.setCurrentIndex(index if index >= 0 else max(0, widget.findText(str(value))))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(value)
            else:
                widget.setValue(value)
            if path in self.inheritance:
                container, reset = self.inheritance[path]
                applicable = scope in SETTING_DEFAULTS[path][1]
                container.setVisible(applicable)
                layout = container.parentWidget().layout()
                caption = layout.labelForField(container) if isinstance(layout, QFormLayout) else None
                if caption:
                    caption.setVisible(applicable)
                source = w.setting_source(path)
                inherited = source != ("Slide override" if scope == 2 else "Talk setting")
                reset.setText("From " + ("app" if source == "Application default" else "talk") if inherited else "Use " + ("talk" if scope == 2 else "app"))
                reset.setVisible(scope > 0)
                reset.setEnabled(not inherited)
        voice = w.setting_value("voice")
        supported = voice.source != "Base"
        self.fields["delivery.style"].setEnabled(supported)
        for widget in self.vocal:
            widget.setEnabled(supported)
        self.fields["delivery.attributes.accent"].setEnabled(supported and w.setting_value("language") == "Chinese")
        self.fields["delivery.attributes.age"].setEnabled(voice.source == "VoiceDesign")
        self.explanation.setText("Reference voices reuse the recorded delivery; direct vocal controls are unavailable. Writing style still applies to new text." if not supported else "Delivery instructions guide speech; listen to assess the result.")
        sampling = w.setting_value("delivery.sampling")
        self.override.setChecked(bool(sampling))
        for name, spin in self.sampling.items():
            spin.setValue(sampling.get(name, SAMPLING[name][2]))
            spin.setEnabled(bool(sampling))
        self.fields["capture_microphone"].setEnabled(w.setting_value("recording_source") == "screen")
        self.fields["recording_policy"].setEnabled(w.setting_value("recording_source") == "slides")
        destination = self.fields["recording_destination"]
        destination.setVisible(scope == 1)
        self.recording_widget.layout().labelForField(destination).setVisible(scope == 1)
        self.destination_button.setVisible(scope == 1)
        for path, applicable in (("quick_timing", w.setting_value("mode") == "Quick"), ("realtime_script", w.setting_value("mode") == "Realtime"), ("speech_priority", w.setting_value("mode") == "Realtime")):
            container = self.inheritance.get(path, (self.fields[path],))[0]
            container.setVisible(applicable)
            caption = self.form.labelForField(container)
            if caption:
                caption.setVisible(applicable)
        self.fields["language"].setEnabled(scope != 2 or w.setting_value("language_policy") != "version")
        self.setVisible(w.setting_value("mode") != "Prepared")
        self.loading = False

    def choose_destination(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save presentation video", "presentation.mp4", "MP4 video (*.mp4)")
        if path:
            self.fields["recording_destination"].setText(path)

    def refresh_presets(self):
        self.presets.clear()
        for path in sorted((data_dir() / "delivery").glob("*.json")):
            try:
                self.presets.addItem(json.loads(path.read_text(encoding="utf-8"))["name"], path)
            except (OSError, ValueError, KeyError):
                continue

        self.use_preset_button.setEnabled(bool(self.presets.count()))

    def save_preset(self):
        name, accepted = QInputDialog.getText(self, "Save delivery", "Preset name")
        if accepted and name.strip():
            try:
                directory = data_dir() / "delivery"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (uuid.uuid4().hex + ".json")).write_text(json.dumps({
                    "name": name.strip(), "delivery": {k: v for k, v in asdict(self.window.voice_context().delivery).items() if k != "sampling"}}, ensure_ascii=False), encoding="utf-8")
                self.refresh_presets()
            except OSError as error:
                QMessageBox.warning(self, "Save preset", str(error))

    def use_preset(self):
        if not self.presets.currentData():
            return
        try:
            value = json.loads(self.presets.currentData().read_text(encoding="utf-8"))["delivery"]
            delivery = Delivery(**(value | {"sampling": {}}))
            settings = {key: delivery.attributes.get(key.split(".")[2], "") if key.startswith("delivery.attributes.") else getattr(delivery, key.split(".")[1])
                        for key in SETTING_DEFAULTS if key.startswith("delivery.") and key != "delivery.sampling"}
            for key, setting in read_settings(settings).items():
                self.window.edit_setting(key, setting)
        except (OSError, ValueError, TypeError, KeyError) as error:
            QMessageBox.warning(self, "Load preset", str(error))
