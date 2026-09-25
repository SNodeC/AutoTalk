"""Editors for the project's delivery and workflow configuration."""
import json
import uuid
from dataclasses import asdict
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget)

from .project import Delivery, STYLES
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


class SettingsPanel(QScrollArea):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.project = None
        self.loading = False
        self.fields = {}
        self.vocal = []
        self.setWidgetResizable(True)
        body = QWidget()
        box = QVBoxLayout(body)
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
            ("Plan the deck; write ahead in two-slide batches", "ahead")])
        buffer = QDoubleSpinBox()
        buffer.setRange(2, 30)
        buffer.setSuffix(" seconds")
        self.bind("buffer_seconds", "Realtime startup/refill buffer", buffer, buffer.valueChanged)
        self.combo("delivery.style", "Writing / delivery style", [(s, s) for s in STYLES])
        self.presets = QComboBox()
        self.form.addRow("Saved delivery presets", self.presets)
        row = QHBoxLayout()
        for title, callback in (("Save preset", self.save_preset), ("Use preset", self.use_preset)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        self.form.addRow(row)
        self.refresh_presets()
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
        self.override = QCheckBox("Override model sampling defaults")
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
        self.record = QCheckBox("Record presentation as a video")
        self.bind("record_presentation", "Presentation recording", self.record, self.record.toggled)
        self.combo("recording_policy", "Recording pauses", [
            ("Keep fullscreen pauses; omit time outside fullscreen", "fullscreen"),
            ("Keep all elapsed time", "all"),
            ("Omit manual pauses, buffering, and time outside fullscreen", "content")])
        path = QLineEdit()
        path.setPlaceholderText("Default: a new video in this project's recordings folder")
        self.bind("recording_destination", "Video destination", path, path.textChanged)
        choose = QPushButton("Choose video destination…")
        choose.clicked.connect(self.choose_destination)
        self.form.addRow(choose)
        self.combo("export_rate", "Export audio sample rate", [("24 kHz (native)", 24000), ("44.1 kHz", 44100), ("48 kHz", 48000)])
        self.combo("export_bitrate", "Video audio encoding", [("AAC 96 kbit/s", 96000), ("AAC 128 kbit/s", 128000), ("AAC 192 kbit/s", 192000)])
        quality = QLabel("Synthesis remains at its native rate. Resampling and encoding affect export; they do not add voice detail. Expression and age are model instructions—preview their effect.")
        quality.setWordWrap(True)
        box.addWidget(quality)
        box.addStretch()
        self.setWidget(body)

    def bind(self, path, label, widget, signal):
        self.fields[path] = widget
        self.form.addRow(label, widget)
        signal.connect(lambda *args, p=path: self.edit(p))
        return widget

    def combo(self, path, label, choices):
        widget = QComboBox()
        for text, value in choices:
            widget.addItem(text, value)
        return self.bind(path, label, widget, widget.currentIndexChanged)

    def owner(self, path):
        parts = path.split(".")
        current = self.project
        for part in parts[:-1]:
            current = current[part] if isinstance(current, dict) else getattr(current, part)
        return current, parts[-1]

    def edit(self, path):
        if self.loading or not self.project:
            return
        widget = self.fields[path]
        if isinstance(widget, QComboBox):
            value = widget.currentData()
        elif isinstance(widget, QCheckBox):
            value = widget.isChecked()
        elif isinstance(widget, QLineEdit):
            value = widget.text()
        else:
            value = widget.value()
        owner, key = self.owner(path)
        if isinstance(owner, dict):
            if value:
                owner[key] = value
            else:
                owner.pop(key, None)
        else:
            setattr(owner, key, value)
        if path == "delivery.style":
            presets = {
                "Professional": {"energy": "Moderate", "articulation": "Precise", "projection": "Confident"},
                "Conversational": {"projection": "Conversational", "articulation": "Natural"},
                "Energetic": {"energy": "High", "pace": "Brisk"},
                "Calm and understated": {"energy": "Low", "pace": "Slow", "projection": "Soft"},
                "Lightly humorous": {"projection": "Conversational", "expression": "Restrained laughter"},
                "Academic": {"pace": "Moderate", "articulation": "Precise"},
                "Storytelling": {"texture": "Warm", "projection": "Conversational"},
                "Inspirational": {"energy": "High", "projection": "Confident"},
            }
            self.project.delivery.attributes = presets[value].copy()
            self.load(self.project)
        self.changed.emit()

    def sampling_changed(self, *_):
        if self.loading or not self.project:
            return
        self.project.delivery.sampling = {k: v.value() for k, v in self.sampling.items()} if self.override.isChecked() else {}
        for spin in self.sampling.values():
            spin.setEnabled(self.override.isChecked())
        self.changed.emit()

    def load(self, project):
        self.project, self.loading = project, True
        for path, widget in self.fields.items():
            owner, name = self.owner(path)
            value = owner.get(name, "") if isinstance(owner, dict) else getattr(owner, name)
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(max(0, widget.findData(value)))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)
            else:
                widget.setValue(value)
        self.override.setChecked(bool(project.delivery.sampling))
        self.override.setEnabled(project.mode != "Quick")
        self.fields["delivery.style"].setEnabled(project.mode != "Quick")
        for name, spin in self.sampling.items():
            spin.setValue(project.delivery.sampling.get(name, SAMPLING[name][2]))
            spin.setEnabled(self.override.isChecked() and project.mode != "Quick")
        supported = project.voice.source != "Base" and project.mode != "Quick"
        for widget in self.vocal:
            widget.setEnabled(supported)
        self.fields["delivery.attributes.accent"].setEnabled(supported and project.language == "Chinese")
        self.fields["delivery.attributes.age"].setEnabled(supported and project.voice.source == "VoiceDesign")
        self.explanation.setText("Base cloning reuses the reference identity and delivery; direct vocal controls are unavailable. Writing style still applies to narration."
            if project.voice.source == "Base" else "CustomVoice and VoiceDesign accept delivery instructions. Dialect presets apply to Chinese; use previews to assess pronunciation and expression.")
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

    def save_preset(self):
        if not self.project:
            return
        name, accepted = QInputDialog.getText(self, "Save delivery", "Preset name")
        if accepted and name.strip():
            try:
                directory = data_dir() / "delivery"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (uuid.uuid4().hex + ".json")).write_text(json.dumps({
                    "name": name.strip(), "delivery": asdict(self.project.delivery)}, ensure_ascii=False), encoding="utf-8")
                self.refresh_presets()
            except OSError as error:
                QMessageBox.warning(self, "Save preset", str(error))

    def use_preset(self):
        if not self.project or not self.presets.currentData():
            return
        previous = self.project.delivery
        try:
            value = json.loads(self.presets.currentData().read_text(encoding="utf-8"))["delivery"]
            self.project.delivery = Delivery(**value)
            self.project.validate()
            self.load(self.project)
            self.changed.emit()
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.project.delivery = previous
            QMessageBox.warning(self, "Load preset", str(error))
