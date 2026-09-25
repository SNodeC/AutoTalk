"""Qt desktop application. Heavy preparation always runs outside the GUI thread."""

import argparse
import copy
import json
import platform
import subprocess
import html
import sys
import time
import wave
from functools import partial
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QMicrophonePermission, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCheckBox,
    QInputDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .codex import Codex
from .playback import Playback, Presentation
from .project import LANGUAGES, SPEAKERS, Project, Voice, wav_duration
from .recording import Recorder
from .runtime import SpeechSession, Cancelled, Task, child_env, data_dir
from .services import extract_scope, import_pdf, narrate, prepare, preview_text, synthesize, workflow
from .options import SettingsPanel
from .media import RATE, export_prepared, export_recording, import_clip
from .voices import library, load_voice, save_voice

def button(text, function, primary=False):
    widget = QPushButton(text)
    if primary:
        font = widget.font()
        font.setBold(True)
        widget.setFont(font)
    widget.clicked.connect(lambda: function())
    return widget


def description(text):
    label = QLabel(text)
    label.setWordWrap(True)
    return label


def clock(seconds):
    seconds = max(0, round(seconds))
    return f"{seconds//60}:{seconds%60:02d}"


class Job(QThread):
    message = Signal(str)
    detail = Signal(str)
    url = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    event = Signal(object)

    def __init__(self, function, parent):
        super().__init__(parent)
        self.function = function
        self.outcome = "running"
        self.task = Task(self.message.emit, self.url.emit, self.detail.emit, self.event.emit)

    def run(self):
        try:
            result = self.function(self.task)
            self.task.check()
            self.outcome = "completed"
            self.succeeded.emit(result)
        except Cancelled as error:
            self.outcome = "cancelled"
            self.message.emit(str(error))
        except Exception as error:  # noqa: BLE001 - report any worker failure at the UI boundary
            self.outcome = "failed"
            self.failed.emit(str(error))


class SlideImage(QLabel):
    def __init__(self):
        super().__init__("Open a PDF slide deck to begin")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 210)
        self.original = QPixmap()

    def show_file(self, path):
        self.original = QPixmap(str(path))
        self.rescale()

    def rescale(self):
        if not self.original.isNull():
            self.setPixmap(self.original.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        self.rescale()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = None
        self.preferences = QSettings()
        self.speech = SpeechSession(Task(), {})
        self.job = None
        self.job_live = False
        self.job_started = 0
        self.presentation = None
        self.loading = False
        self.close_requested = False
        self.setWindowTitle("AutoTalk")
        self.resize(1240, 880)
        self.setMinimumSize(940, 680)
        self.transport = Playback(self, producer_active=lambda: bool(self.job and self.job_live))
        self.transport.slide_changed.connect(self.show_slide)
        # Audio feeds independently; human-readable timing updates at 4 Hz.
        self.transport.state_changed.connect(self.playback_state_changed)
        self.transport.failed.connect(self.error)
        self.transport.finished.connect(lambda: self.log_message("Presentation finished."))
        self.model_catalog = []
        self.after_job = None
        self.live_autostart = False
        self.pending_exports = []
        self.measurements = {}
        self.transport.recording_ready.connect(self.queue_export)
        self.recorder = Recorder()
        self.record_timer = QTimer(self)
        self.record_timer.setSingleShot(True)
        self.record_timer.timeout.connect(self.toggle_recording)
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(250)
        self.elapsed_timer.timeout.connect(self.update_timing)
        self._build()
        self.retention_changed()
        self.refresh_recordings()
        self.elapsed_timer.start()
        self.refresh()

    def _build(self):
        toolbar = self.addToolBar("Project")
        toolbar.setMovable(False)
        self.actions = []
        for title, handler, shortcut in [
            ("New from PDF", self.new_project, "Ctrl+N"),
            ("Open talk", self.open_project, "Ctrl+O"),
            ("Save", self.save, "Ctrl+S"),
            ("Connect ChatGPT", self.connect_chatgpt, ""),
            ("Release GPU", self.release_gpu, ""),
            ("Export recorded session", self.recover_recording, "")]:
            action = QAction(title, self)
            action.triggered.connect(lambda checked=False, f=handler: f())
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            toolbar.addAction(action)
            self.actions.append(action)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 14)
        header = QHBoxLayout()
        brand = QLabel("AutoTalk")
        brand.setFont(QFont(brand.font().family(), 23, QFont.Weight.Bold))
        header.addWidget(brand)
        header.addWidget(description("Your slides. Your voice. A talk that fits."), 1)
        self.connection = description("ChatGPT subscription • Local speech")
        header.addWidget(self.connection)
        layout.addLayout(header)
        self.title_label = QLabel("Create a presentation from an existing PDF")
        self.title_label.setFont(QFont(self.title_label.font().family(), 14))
        layout.addWidget(self.title_label)
        mode_row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(["Prepared", "Quick", "Realtime"])
        self.mode.currentTextChanged.connect(self.mode_changed)
        mode_row.addWidget(QLabel("Mode"))
        mode_row.addWidget(self.mode)
        mode_row.addStretch()
        self.start_button = button("Prepare talk", self.start_mode, True)
        mode_row.addWidget(self.start_button)
        layout.addLayout(mode_row)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self._details_tab()
        self._voice_tab()
        self.options = SettingsPanel()
        self.options.changed.connect(self.configuration_changed)
        mode_row.insertWidget(2, self.options.record)
        self.setup_page.layout().addWidget(self.options)
        self._narration_tab()
        self._presentation_tab()
        for page, title in ((self.setup_page, "Setup"), (self.script_page, "Script"), (self.present_page, "Present & Export")):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, title.replace("&", "&&"))

        self.narration_progress = QProgressBar()
        layout.addWidget(self.narration_progress)
        self.slide_progress = QProgressBar()
        self.slide_progress.setRange(0, 1)
        self.slide_progress.setFormat("Slide progress")
        layout.addWidget(self.slide_progress)
        self.performance = description("")
        layout.addWidget(self.performance)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        status = QHBoxLayout()
        self.status = description("Start with New from PDF, or open a saved talk.")
        status.addWidget(self.status, 1)
        status.addWidget(button("Show / hide details", lambda: self.log.setVisible(not self.log.isVisible())))
        self.cancel_button = button("Cancel operation", self.cancel)
        self.cancel_button.hide()
        status.addWidget(self.cancel_button)
        layout.addLayout(status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setMaximumHeight(95)
        self.log.setPlaceholderText("Preparation progress appears here.")
        self.log.hide()
        layout.addWidget(self.log)
        self.statusBar().showMessage("AutoTalk 0.3 • " + platform.system())

    def _details_tab(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(20, 20, 20, 20)
        box.addWidget(description("Give the talk a destination. Conference context guides the emphasis; your slides remain the source of facts."))
        form = QFormLayout()
        self.talk_title = QLineEdit()
        form.addRow("Talk title", self.talk_title)
        timing = QHBoxLayout()
        self.minutes = QDoubleSpinBox()
        self.minutes.setRange(0.1, 240)
        self.minutes.setValue(10)
        self.minutes.setSuffix(" min")
        self.tolerance = QDoubleSpinBox()
        self.tolerance.setRange(0, 600)
        self.tolerance.setValue(15)
        self.tolerance.setSuffix(" sec tolerance")
        self.pause = QDoubleSpinBox()
        self.pause.setRange(0, 10)
        self.pause.setSingleStep(0.1)
        self.pause.setValue(0.6)
        self.pause.setSuffix(" sec between slides")
        for field in (self.minutes, self.tolerance, self.pause):
            timing.addWidget(field)
        form.addRow("Duration", timing)
        self.language = QComboBox()
        self.language.addItems(LANGUAGES)
        form.addRow("Spoken language", self.language)
        model_row = QHBoxLayout()
        self.codex_model = QComboBox()
        self.codex_model.addItem("Account default", "")
        self.codex_model.currentIndexChanged.connect(self.model_changed)
        self.codex_effort = QComboBox()
        self.codex_effort.addItem("Model default", "")
        self.codex_effort.currentIndexChanged.connect(self.model_settings_changed)
        model_row.addWidget(self.codex_model, 2)
        model_row.addWidget(self.codex_effort, 1)
        form.addRow("Codex model / reasoning", model_row)
        self.audience = QLineEdit("General conference audience")
        form.addRow("Audience", self.audience)
        self.objective = QLineEdit("Explain the key ideas and takeaways")
        form.addRow("Talk objective", self.objective)
        urlrow = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://conference.example/call-for-papers")
        urlrow.addWidget(self.url)
        self.conference_button = button("Read conference website", self.read_conference)
        urlrow.addWidget(self.conference_button)
        form.addRow("Conference URL", urlrow)
        box.addLayout(form)
        box.addWidget(QLabel("Conference scope — enter directly or edit the website summary"))
        self.scope = QPlainTextEdit()
        self.scope.setPlaceholderText("Conference themes, relevant tracks, typical topics, and the edition/year…")
        self.scope.setFixedHeight(110)
        box.addWidget(self.scope)
        self.sources = description("")
        self.sources.setOpenExternalLinks(True)
        box.addWidget(self.sources)
        box.addWidget(description("Generation sends slide images, text and conference context to Codex using your ChatGPT allowance. Voice recordings remain local."))

        self.setup_page = page
        for widget in (self.talk_title, self.audience, self.objective, self.url):
            widget.textChanged.connect(self.details_changed)
        for widget in (self.minutes, self.tolerance, self.pause):
            widget.valueChanged.connect(self.details_changed)
        self.language.currentTextChanged.connect(self.language_selected)
        self.scope.textChanged.connect(self.details_changed)

    def _narration_tab(self):
        page = QWidget()
        box = QVBoxLayout(page)
        versions = QHBoxLayout()
        self.version_select = QComboBox()
        self.version_select.currentIndexChanged.connect(self.version_changed)
        versions.addWidget(QLabel("Talk version"))
        versions.addWidget(self.version_select, 1)
        versions.addWidget(button("Add language version", self.add_version))
        box.addLayout(versions)
        self.context_warning = description("")
        box.addWidget(self.context_warning)
        split = QSplitter()
        self.slide_list = QListWidget()
        self.slide_list.setMaximumWidth(230)
        self.slide_list.currentRowChanged.connect(self.select_slide)
        split.addWidget(self.slide_list)
        content = QWidget()
        content_box = QVBoxLayout(content)
        self.image = SlideImage()
        content_box.addWidget(self.image, 3)
        self.slide_info = description("No slide selected")
        content_box.addWidget(self.slide_info)
        passage_row = QHBoxLayout()
        passage_row.addWidget(QLabel("Spoken narration"))
        self.passage_language = QComboBox()
        self.passage_language.addItems(LANGUAGES)
        passage_row.addWidget(self.passage_language)
        passage_row.addWidget(button("Insert language passage", self.insert_passage))
        content_box.addLayout(passage_row)
        self.narration = QPlainTextEdit()
        self.narration.setPlaceholderText("Generate narration or write your own text for this slide.")
        self.narration.textChanged.connect(self.narration_changed)
        content_box.addWidget(self.narration, 2)
        self.slide_directions = QLineEdit()
        self.slide_directions.setPlaceholderText("Optional delivery directions for this slide")
        self.slide_directions.textChanged.connect(self.slide_directions_changed)
        content_box.addWidget(self.slide_directions)
        clip_row = QHBoxLayout()
        self.clip_select = QComboBox()
        self.clip_select.currentIndexChanged.connect(self.show_clip)
        self.clip_gain = QDoubleSpinBox()
        self.clip_gain.setRange(0, 2)
        self.clip_gain.setSingleStep(0.05)
        self.clip_gain.valueChanged.connect(self.clip_changed)
        self.clip_placement = QComboBox()
        self.clip_placement.addItems(["before", "after"])
        self.clip_placement.currentTextChanged.connect(self.clip_changed)
        for widget in (self.clip_select, self.clip_gain, self.clip_placement,
                       button("Add clip", self.add_clip), button("Remove", self.remove_clip)):
            clip_row.addWidget(widget)
        content_box.addLayout(clip_row)
        self.notes = description("")
        content_box.addWidget(self.notes)
        split.addWidget(content)
        split.setStretchFactor(1, 1)
        box.addWidget(split, 1)
        controls = QHBoxLayout()
        controls.addWidget(button("Regenerate narration", self.create_narration))
        controls.addStretch()
        controls.addWidget(button("Accept script for current context", self.accept_script))
        box.addLayout(controls)
        self.script_page = page

    def _voice_tab(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(22, 22, 22, 22)
        box.addWidget(QLabel("Choose how your talk sounds"))
        box.addWidget(description("Choose a predefined voice, design a new voice, or provide a clean WAV reference. A 10–30 second sample in a quiet room is a useful starting point. No voice training commands are required."))
        voice_form = QFormLayout()
        self.voice_source = QComboBox()
        for name, value in (("Predefined voice", "CustomVoice"), ("My voice", "Base"), ("Design a voice", "VoiceDesign")):
            self.voice_source.addItem(name, value)
        self.voice_source.currentIndexChanged.connect(self.voice_settings_changed)
        self.speaker = QComboBox()
        self.speaker.addItems(SPEAKERS)
        for index, native in enumerate(("English", "English", "Chinese", "Chinese", "Chinese",
                                         "Chinese (Beijing)", "Chinese (Sichuan)", "Japanese", "Korean")):
            self.speaker.setItemData(index, "Native voice profile: " + native + ". Preview when using another language.", Qt.ItemDataRole.ToolTipRole)
        self.speaker.currentTextChanged.connect(self.voice_settings_changed)
        self.voice_description = QLineEdit()
        self.voice_description.setPlaceholderText("Describe the voice's age, timbre, character, and background")
        self.voice_description.textChanged.connect(self.voice_settings_changed)
        voice_form.addRow("Voice source / 1.7B variant", self.voice_source)
        voice_form.addRow("Predefined voice", self.speaker)
        voice_form.addRow("Voice design", self.voice_description)
        self.voice_library = QComboBox()
        voice_form.addRow("Saved personal voices", self.voice_library)
        box.addLayout(voice_form)
        library_row = QHBoxLayout()
        library_row.addWidget(button("Use saved voice", self.use_saved_voice))
        library_row.addWidget(button("Save reusable voice", self.save_personal_voice))
        box.addLayout(library_row)
        self.voice_label = QLabel("Built-in voice: Ryan")
        self.voice_label.setFont(QFont(self.voice_label.font().family(), 14))
        box.addWidget(self.voice_label)
        row = QHBoxLayout()
        row.addWidget(button("Use built-in voice", self.default_voice))
        row.addWidget(button("Import voice WAV", self.import_voice))
        self.record_button = button("Record my voice", self.toggle_recording)
        row.addWidget(self.record_button)
        box.addLayout(row)
        box.addWidget(description("Recording stops automatically after 30 seconds. You can stop sooner. For a useful reference, speak naturally as you would at your conference."))
        box.addWidget(QLabel("Exact words in your recording (optional, recommended for voice similarity)"))
        self.transcript = QPlainTextEdit()
        self.transcript.setPlaceholderText("Enter what you said in the recording. If empty, Qwen uses speaker identity alone.")
        self.transcript.textChanged.connect(self.voice_changed)
        self.transcript.setFixedHeight(85)
        box.addWidget(self.transcript)
        box.addWidget(description("Speech is synthesized on your local GPU. Designed voices are saved as a reference before the talk to keep one identity. The first use downloads the selected model and its runtime. Presentations should disclose that the narration is AI-generated."))
        row = QHBoxLayout()
        row.addWidget(button("Preview voice", self.preview_voice, True))
        row.addWidget(button("Stop preview", self.transport.stop))
        row.addWidget(button("Accept designed voice", self.accept_designed_voice))
        row.addStretch()
        box.addLayout(row)
        retention = QHBoxLayout()
        retention.addWidget(QLabel("Keep speech model loaded"))
        self.gpu_retention = QComboBox()
        for label, value in (("Until exit", "session"), ("Five idle minutes", "idle"), ("During each operation", "operation")):
            self.gpu_retention.addItem(label, value)
        self.gpu_retention.setCurrentIndex(max(0, self.gpu_retention.findData(self.preferences.value("gpu_retention", "session"))))
        self.gpu_retention.currentIndexChanged.connect(self.retention_changed)
        retention.addWidget(self.gpu_retention)
        box.addLayout(retention)
        self.setup_page.layout().addWidget(page)

    def _presentation_tab(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(22, 22, 22, 22)
        self.duration_label = QLabel("Prepare speech to measure the talk")
        self.duration_label.setFont(QFont(self.duration_label.font().family(), 17))
        box.addWidget(self.duration_label)
        self.fit_label = description("")
        box.addWidget(self.fit_label)
        self.play_image = SlideImage()
        box.addWidget(self.play_image, 1)
        row = QHBoxLayout()
        self.fit_button = button("Fit narration to duration", self.fit_duration)
        row.addWidget(self.fit_button)
        row.addStretch()
        box.addLayout(row)
        audio_row = QHBoxLayout()
        audio_row.addWidget(button("System audio settings", self.system_audio_settings))
        self.audio_test_button = button("Test audio", self.test_audio)
        audio_row.addWidget(self.audio_test_button)
        self.background_button = button("Add background track", self.add_background)
        audio_row.addWidget(self.background_button)
        self.background_gain = QDoubleSpinBox()
        self.background_gain.setRange(0, 1)
        self.background_gain.setSingleStep(0.05)
        self.background_gain.setValue(0.15)
        self.background_gain.valueChanged.connect(self.background_changed)
        audio_row.addWidget(self.background_gain)
        self.background_loop = QCheckBox("Loop")
        self.background_loop.toggled.connect(self.background_changed)
        audio_row.addWidget(self.background_loop)
        self.remove_background_button = button("Remove background", self.remove_background)
        audio_row.addWidget(self.remove_background_button)
        box.addLayout(audio_row)
        self.screen = QComboBox()
        for i, screen in enumerate(QApplication.screens()):
            self.screen.addItem(f"Display {i+1}: {screen.name()}", i)
        box.addWidget(self.screen)
        row = QHBoxLayout()
        self.previous_button = button("Previous", partial(self.transport.step, -1))
        self.play_button = button("Play / pause", self.transport.toggle)
        self.next_button = button("Next", partial(self.transport.step, 1))
        self.present_button = button("Present fullscreen", self.present, True)
        self.continue_button = button("Continue presentation", self.continue_presentation)
        self.restart_button = button("Restart from beginning", self.restart_presentation)
        for widget in (self.previous_button, self.play_button, self.next_button, button("Stop and edit", self.stop_presentation)):
            row.addWidget(widget)
        box.addLayout(row)
        row = QHBoxLayout()
        for widget in (self.present_button, self.continue_button, self.restart_button):
            row.addWidget(widget)
        box.addLayout(row)
        self.play_time = description("Elapsed 0:00 • Remaining 0:00")
        box.addWidget(self.play_time)
        box.addWidget(description("Space: pause/resume • Arrows: slides • Esc: return, then Continue. Stop and edit unlocks authoring. Prepared audio plays offline; Realtime writing needs a connection."))
        box.insertWidget(2, self.options.recording_widget)
        self.recordings = QComboBox()
        box.addWidget(self.recordings)
        exports = QHBoxLayout()
        self.export_button = button("Export prepared talk…", self.export_talk, True)
        exports.addWidget(self.export_button)
        exports.addWidget(button("Recover recording…", self.recover_recording))
        self.output_button = button("Open saved file", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path)))
        self.folder_button = button("Open folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.output_path).parent))))
        self.output_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        exports.addWidget(self.output_button)
        exports.addWidget(self.folder_button)
        box.insertLayout(2, exports)
        self.present_page = page

    def error(self, message):
        self.log_message(message)
        QMessageBox.warning(self, "AutoTalk", message)

    def log_message(self, message):
        self.log.appendPlainText(message)
        self.status.setText(message.splitlines()[-1][:220] if message else "")

    def start_job(self, title, function, callback=None, live=False):
        if self.job:
            return
        if self.recorder.source:
            self.error("Stop the reference recording before starting another operation.")
            return
        if not self.save():
            return
        self.transport.stop()
        self.log_message(title)
        self.tabs.setEnabled(live)
        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(i, not live or i == 2)
        for widget in (self.mode, self.start_button, self.options.record, self.options.recording_widget):
            widget.setEnabled(False)
        if not title.startswith(("Saving", "Export")):
            self.measurements = {}
        self.slide_progress.setRange(0, len(self.project.slides) if self.project else 1)
        self.slide_progress.setValue(0)
        for action in self.actions:
            action.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.job_started = time.monotonic()
        self.elapsed_timer.start()
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.job_live = live
        self.job = Job(function, self)
        self.job.title = title
        self.job.task.speech = self.speech
        self.job.message.connect(self.log_message)
        self.job.detail.connect(self.log.appendPlainText)
        self.job.url.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.job.failed.connect(self.job_error)
        self.job.event.connect(lambda value, job=self.job: self.job_event(value) if self.job is job else None)
        if callback:
            self.job.succeeded.connect(callback)
        self.job.finished.connect(self.job_finished)
        self.job.start()

    def job_finished(self):
        if self.project:
            try:
                directory = self.project.asset("runs")
                directory.mkdir(exist_ok=True)
                (directory / f"{time.time_ns()}.json").write_text(json.dumps({
                    "operation": self.job.title, "outcome": self.job.outcome,
                    "elapsed": time.monotonic()-self.job_started,
                    "measurements": self.measurements}, indent=2))
            except OSError as error:
                self.log_message(f"Could not save timing summary: {error}")
        self.job.deleteLater()
        self.job = None
        self.job_live = False
        self.progress.hide()
        self.cancel_button.hide()
        for action in self.actions:
            action.setEnabled(True)
        self.refresh()
        if self.project:
            self.show_slide(self.transport.index)
        self.refresh_recordings()
        if self.close_requested == "saving" and self.pending_exports:
            self.export_next()
        elif self.close_requested:
            self.close()
        elif self.after_job:
            callback, self.after_job = self.after_job, None
            callback()
        elif self.pending_exports:
            self.export_next()

    def cancel(self):
        self.live_autostart = False
        if self.job_live and self.transport.active:
            self.transport.pause()
        if self.job:
            self.job.task.cancelled.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling…")

    def save(self):
        if self.project:
            try:
                self.project.save()
                self.statusBar().showMessage(f"Saved • {self.project.manifest}")
            except OSError as error:
                self.error(f"Could not save the project: {error}")
                return False
        return True

    def adopt(self, project):
        self.project = project
        self.loading = True
        self.mode.setCurrentText(project.mode)
        self.version_select.clear()
        for key, value in project.versions.items():
            self.version_select.addItem(value.name + " — " + value.language, key)
        self.version_select.setCurrentIndex(self.version_select.findData(project.active_version))
        self.voice_source.setCurrentIndex(self.voice_source.findData(project.voice.source))
        self.speaker.setCurrentText(project.voice.speaker)
        self.voice_description.setText(project.voice.description)
        self.background_gain.setValue(project.background.gain if project.background else 0.15)
        self.background_loop.setChecked(project.background.loop if project.background else False)
        self.options.load(project)
        self.refresh_models()
        self.refresh_library()
        self.talk_title.setText(project.title)
        self.minutes.setValue(project.target_minutes)
        self.tolerance.setValue(project.tolerance_seconds)
        self.pause.setValue(project.pause_seconds)
        self.language.setCurrentText(project.language)
        self.scope.setPlainText(project.scope)
        self.url.setText(project.conference_url)
        self.audience.setText(project.audience)
        self.objective.setText(project.objective)
        self.transcript.setPlainText(project.voice_transcript)
        self.slide_list.clear()
        self.slide_list.addItems([f"{s.page:02d}  Slide {s.page}" for s in project.slides])
        self.loading = False
        self.transport.load(project)
        self.refresh()
        self.log_message(f"Talk loaded: {project.title}")
        recent = self.preferences.value("recent_projects", [])
        recent = recent if isinstance(recent, list) else [recent]
        self.preferences.setValue("recent_projects", [str(project.root)] + [v for v in recent if v != str(project.root)][:9])
        self.refresh_recordings()

    def new_project(self):
        if not self.save():
            return
        pdf, _ = QFileDialog.getOpenFileName(self, "Choose slide deck", "", "PDF slides (*.pdf)")
        if not pdf:
            return
        parent = QFileDialog.getExistingDirectory(self, "Choose where to save the new talk")
        if not parent:
            return
        base = Path(parent) / (Path(pdf).stem + "-AutoTalk")
        destination = base
        index = 2
        while destination.exists():
            destination = base.with_name(f"{base.name}-{index}")
            index += 1
        def imported(project):
            project.quick_timing = self.preferences.value("quick_timing", "once")
            project.speech_priority = self.preferences.value("speech_priority", "consistency")
            project.buffer_seconds = 2 if project.speech_priority == "earliest" else 5
            self.adopt(project)
        self.start_job("Importing PDF…", lambda task: import_pdf(Path(pdf), destination, task), imported)

    def open_project(self, path=None):
        if not self.save():
            return
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open prepared talk", "", "AutoTalk project (*.autotalk.json)")
        if path:
            self.start_job("Opening talk…", lambda task: Project.load(Path(path)), self.adopt)

    def details_changed(self, *_):
        if self.loading or not self.project:
            return
        self.transport.stop()
        p = self.project
        p.title, p.scope = self.talk_title.text(), self.scope.toPlainText()
        p.target_minutes, p.tolerance_seconds = self.minutes.value(), self.tolerance.value()
        p.pause_seconds = self.pause.value()
        p.audience, p.objective = self.audience.text(), self.objective.text()
        p.conference_url = self.url.text().strip()
        self.options.load(p)
        self.transport.refresh_audio()
        self.refresh()

    def narration_changed(self):
        if not self.loading and self.project:
            self.project.slides[self.transport.index].narration = self.narration.toPlainText()
            self.transport.stop()
            self.refresh()

    def voice_changed(self):
        if not self.loading and self.project:
            self.transport.stop()
            self.project.voice_transcript = self.transcript.toPlainText()
            self.refresh()

    def select_slide(self, index):
        if not self.loading and index >= 0:
            self.transport.select(index)

    def show_slide(self, index):
        if not self.project:
            return
        self.loading = True
        slide = self.project.slides[index]
        self.slide_list.setCurrentRow(index)
        self.image.show_file(self.project.image(slide))
        self.play_image.show_file(self.project.image(slide))
        self.narration.setPlainText(slide.narration)
        self.notes.setText(slide.notes)
        self.slide_directions.setText(slide.directions)
        self.clip_select.clear()
        for clip in slide.clips:
            self.clip_select.addItem(Path(clip.file).name)
        self.show_clip()
        self.loading = False
        self.refresh()

    def refresh(self):
        p = self.project
        live = bool(self.job and self.job_live)
        self.tabs.setEnabled(p is not None and (self.job is None or live))
        editable = self.job is None and not self.transport.active and self.presentation is None
        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(i, i == 2 or editable)
        self.mode.setEnabled(editable)
        self.options.record.setEnabled(p is not None and editable)
        self.options.recording_widget.setEnabled(editable)
        resumable = bool(p and p.mode == "Realtime" and not p.prepared and self.transport.state == "paused" and self.presentation is None and not self.job)
        self.start_button.setEnabled(p is not None and (editable or resumable))
        for action in self.actions:
            action.setEnabled(editable)
        if not p:
            return
        self.title_label.setText(p.title or "Untitled talk")
        self.voice_label.setText(f"Qwen3-TTS 1.7B {p.effective_voice.source} • {p.effective_voice.name}")
        self.speaker.parentWidget().setVisible(p.mode != "Quick")
        self.codex_model.setEnabled(p.mode != "Quick")
        self.codex_effort.setEnabled(p.mode != "Quick")
        self.voice_source.setEnabled(p.mode != "Quick")
        self.speaker.setEnabled(p.voice.source == "CustomVoice" and p.mode != "Quick")
        self.voice_description.setEnabled(p.voice.source == "VoiceDesign" and p.mode != "Quick")
        self.slide_directions.setEnabled(p.voice.source != "Base" and p.mode != "Quick")
        label = "Start " + p.mode
        if p.mode == "Prepared":
            label = "Create script" if not any(s.passages for s in p.slides) else "Review script" if not p.script_current else "Generate audio" if not p.prepared else "Start presentation"
        elif any(s.passages for s in p.slides) and not p.prepared:
            label = "Resume " + p.mode
        if resumable:
            label = "Resume preparation"
        if p.manual_review_required:
            label = "Review script"
        self.start_button.setText(label)
        for widget in (self.url, self.scope, self.audience, self.objective, self.conference_button):
            widget.setEnabled(p.mode != "Quick")
        self.audio_test_button.setEnabled(editable)
        self.background_button.setText("Background: " + Path(p.background.file).name[:16] if p.background else "Add background track")
        for widget in (self.background_button, self.background_gain, self.background_loop, self.remove_background_button):
            widget.setEnabled(editable)

        self.transcript.setEnabled(bool(p.voice_file))
        self.sources.setText("Sources: " + " · ".join(
            f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>' for url in p.sources) if p.sources else "")
        context = p.context_key()
        self.narration_progress.setRange(0, len(p.slides))
        self.narration_progress.setValue(sum(bool(s.passages) and s.narration_context == context for s in p.slides))
        self.narration_progress.setFormat("Accepted script: %v / %m")
        ready = sum(p.ready(s) for s in p.slides)
        self.duration_label.setText(f"{clock(p.total_seconds)} prepared  /  {clock(p.target_minutes*60)} target")
        self.fit_label.setText(f"{ready}/{len(p.slides)} slides have current audio. " +
            ("Within requested tolerance." if p.within_target else
             f"Difference: {p.total_seconds-p.target_minutes*60:+.1f} seconds (tolerance ±{p.tolerance_seconds:g}s)." if p.prepared
             else "Review and accept the script." if not p.script_current else "Generate audio to measure the complete talk."))
        self.context_warning.setText("Conference context or timing has changed since narration generation. Review or regenerate the script."
            if not p.script_current else "Script accepted for the current context.")
        for i, slide in enumerate(p.slides):
            item = self.slide_list.item(i)
            if item:
                item.setText(f"{slide.page:02d}  {'✓' if p.ready(slide) else '○'}  " +
                             (clock(slide.duration) if p.ready(slide) else "Needs audio"))
        slide = p.slides[self.transport.index]
        self.slide_info.setText(f"Slide {slide.page} of {len(p.slides)} • " +
            (f"Audio {clock(slide.duration)}" if p.ready(slide) else "Audio needs generation") +
            (f" • Planned {slide.budget_seconds:.0f}s" if slide.budget_seconds else ""))
        can_play = p.prepared or (p.mode == "Realtime" and live)
        self.play_button.setEnabled(can_play)
        self.present_button.setEnabled(can_play and self.presentation is None and not self.transport.active)
        self.continue_button.setEnabled(can_play and self.presentation is None and self.transport.state == "paused" and not self.transport.preview_path)
        self.restart_button.setEnabled(can_play and self.presentation is None)
        if self.job is None:
            self.slide_progress.setRange(0, len(p.slides))
            self.slide_progress.setValue(ready)
            self.slide_progress.setFormat("Prepared slides: %v / %m")
        self.fit_button.setEnabled(editable and bool(p.slides) and all(s.passages for s in p.slides))
        self.export_button.setEnabled(editable and p.prepared)
        self.update_timing()

    def update_timing(self):
        if not hasattr(self, "play_time"):
            return
        capture = self.transport.capture
        self.options.record.setText(f"Recording video • {clock(capture.frames / RATE)}" if capture else "Record presentation as a video")
        total = self.transport.total_seconds
        elapsed = self.transport.elapsed
        remaining = clock(total-elapsed) if self.transport.complete else "estimating…"
        self.play_time.setText(f"{self.transport.state.capitalize()} • Elapsed {clock(elapsed)} • Remaining {remaining} • Buffered {self.transport.buffered_seconds:.1f}s")
        if self.job:
            self.statusBar().showMessage(f"Operation elapsed: {clock(time.monotonic()-self.job_started)}")

    def playback_state_changed(self):
        if self.job_live and self.transport.state == "playing":
            self.measurements.setdefault("First playback", time.monotonic()-self.job_started)
        self.refresh()

    def connect_chatgpt(self):
        def connect(task):
            with Codex(task) as codex:
                account = codex.login()
                return {"account": account, "models": codex.models()}
        def connected(result):
            self.connection.setText(result["account"])
            self.model_catalog = result["models"]
            self.refresh_models()
        self.start_job("Connecting to ChatGPT…", connect, connected)

    def read_conference(self):
        if not self.url.text().strip():
            self.error("Enter a conference website URL, or type the scope directly below.")
            return
        def done(result):
            self.project.sources = result["sources"]
            self.scope.setPlainText(result["scope"])
            self.project.save()
            self.log_message("Review the extracted conference scope before creating narration.")
        self.start_job("Reading conference scope…", lambda task: extract_scope(self.url.text().strip(), task, self.project.codex_model, self.project.codex_effort), done)

    def create_narration(self):
        if not self.project:
            return
        if (any(s.narration.strip() for s in self.project.slides)
                and QMessageBox.question(self, "Replace narration?", "Regenerate the complete narration? This replaces your current script edits.") != QMessageBox.StandardButton.Yes):
            return
        def done(project):
            self.adopt(project)
            self.tabs.setCurrentIndex(1)
            self.log_message("Narration is ready to review.")
        self.start_job("Creating narration…", partial(narrate, copy.deepcopy(self.project)), done)

    def generate_speech(self):
        self.start_job("Preparing speech…", partial(prepare, copy.deepcopy(self.project)), self.accept_result)

    def fit_duration(self):
        if QMessageBox.question(self, "Fit duration", "AutoTalk will revise your narration and regenerate audio, up to three times, using your Codex allowance. Continue?") != QMessageBox.StandardButton.Yes:
            return
        self.start_job("Fitting the talk to its duration…", partial(prepare, copy.deepcopy(self.project), fit=True), self.accept_result)

    def default_voice(self):
        self.transport.stop()
        self.project.voice = Voice()
        self.adopt(self.project)

    def import_voice(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import your voice", "", "PCM WAV recording (*.wav)")
        if path:
            self.set_voice(Path(path))

    def set_voice(self, path):
        try:
            self.transport.stop()
            duration = wav_duration(path)
            if not 3 <= duration <= 60:
                raise ValueError("Use a WAV reference recording between 3 and 60 seconds.")
            self.project.set_voice(path)
            self.transcript.clear()
            self.project.save()
            self.adopt(self.project)
        except (OSError, ValueError, EOFError, wave.Error) as error:
            self.error(str(error))

    def toggle_recording(self):
        try:
            if self.recorder.source:
                self.record_timer.stop()
                path = self.recorder.stop(data_dir() / "recording.wav")
                self.record_button.setText("Record my voice")
                for action in self.actions:
                    action.setEnabled(True)
                self.tabs.tabBar().setEnabled(True)
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
                self.transport.stop()
                self.recorder.start()
                self.record_button.setText("Stop recording")
                for action in self.actions:
                    action.setEnabled(False)
                self.tabs.tabBar().setEnabled(False)
                self.record_timer.start(30000)
        except (RuntimeError, OSError, ValueError, wave.Error) as error:
            self.record_timer.stop()
            self.record_button.setText("Record my voice")
            for action in self.actions:
                action.setEnabled(True)
            self.tabs.tabBar().setEnabled(True)
            self.error(str(error))

    def preview_voice(self):
        if self.recorder.source:
            self.error("Stop recording before previewing the voice.")
            return
        def done(path):
            self.transport.preview(path)
            self.log_message("Playing your voice preview.")
        self.start_job("Generating voice preview…", partial(synthesize, copy.deepcopy(self.project), preview=True), done)

    def present(self, resume=False):
        if self.presentation or not self.project:
            return
        if not self.project.prepared and not (self.project.mode == "Realtime" and self.job and self.job_live):
            return
        if not self.job and not self.save():
            return
        if not resume:
            self.transport.select(0)
        self.live_autostart = False
        self.presentation = Presentation(self.transport)
        screens = QApplication.screens()
        screen = screens[min(self.screen.currentIndex(), len(screens)-1)]
        self.presentation.setScreen(screen)
        self.presentation.setGeometry(screen.geometry())
        self.presentation.closed.connect(self.presentation_closed)
        self.tabs.setCurrentIndex(2)
        for action in self.actions:
            action.setEnabled(False)
        self.transport.fullscreen = True
        self.presentation.showFullScreen()
        self.transport.play()
        self.refresh()

    def presentation_closed(self):
        self.presentation.deleteLater()
        self.presentation = None
        self.live_autostart = False
        for action in self.actions:
            action.setEnabled(self.job is None and not self.transport.active)
        self.refresh()

    def continue_presentation(self):
        self.present(resume=True)

    def restart_presentation(self):
        self.transport.stop()
        self.present()

    def stop_presentation(self):
        self.live_autostart = False
        if self.job and self.job_live:
            self.cancel()
        if self.presentation:
            self.presentation.close()
        self.transport.stop()
        self.refresh()

    def configuration_changed(self):
        if self.loading or not self.project:
            return
        self.transport.stop()
        self.transport.refresh_audio()
        for name in ("quick_timing", "speech_priority"):
            self.preferences.setValue(name, getattr(self.project, name))
        self.refresh()

    def mode_changed(self, value):
        if self.loading or not self.project:
            return
        self.project.mode = value
        self.options.load(self.project)
        self.configuration_changed()

    def start_mode(self):
        if not self.project or self.job:
            return
        if self.project.manual_review_required:
            self.tabs.setCurrentIndex(1)
            self.log_message("Review and accept your edited script, or explicitly regenerate it.")
            return
        if self.project.mode == "Prepared":
            if not any(s.passages for s in self.project.slides):
                self.create_narration()
            elif not self.project.script_current:
                self.tabs.setCurrentIndex(1)
                self.log_message("Review the script, then accept it for this context.")
            elif not self.project.prepared:
                self.generate_speech()
            else:
                self.present()
            return
        if self.transport.state != "paused":
            self.transport.select(0)
        else:
            self.log_message("Resuming preparation; an unfinished slide restarts from its beginning.")
        snapshot = copy.deepcopy(self.project)
        self.live_autostart = snapshot.mode == "Realtime"
        def done(result):
            self.accept_result(result)
            if result.mode == "Quick":
                if result.quick_timing == "require" and not result.within_target:
                    self.log_message("Timing does not match. Review or revise the talk before starting.")
                else:
                    self.after_job = self.present
            elif result.mode == "Realtime" and self.live_autostart:
                self.after_job = partial(self.present, resume=True)
        self.start_job("Preparing " + snapshot.mode + " presentation…", partial(workflow, snapshot), done,
                       live=snapshot.mode == "Realtime")

    def accept_result(self, project):
        if self.transport.active or self.presentation:
            self.project = self.transport.project = project
            self.transport.refresh_audio()
            self.options.load(project)
            self.show_slide(self.transport.index)
        else:
            self.adopt(project)
        self.refresh()

    def job_error(self, message):
        self.close_requested = False
        self.live_autostart = False
        if self.transport.active:
            self.transport.pause()
        self.error(message)

    def job_event(self, value):
        if self.job is None:
            return
        kind = value.get("type")
        if kind == "progress":
            progress = self.narration_progress if value["stage"] == "Narration" else self.slide_progress
            progress.setRange(0, max(1, value["total"]))
            progress.setValue(value["completed"])
            progress.setFormat(value["stage"] + ": %v / %m")
        elif kind == "measurement":
            stage = value["stage"]
            self.measurements[stage] = self.measurements.get(stage, 0) + value["seconds"]
            if value.get("audio_seconds"):
                self.measurements["Audio produced"] = self.measurements.get("Audio produced", 0) + value["audio_seconds"]
            text = " • ".join(f"{stage}: {seconds:.1f}s" for stage, seconds in self.measurements.items())
            generated = self.measurements.get("Audio produced", 0)
            cost = self.measurements.get("Speech", 0)
            if generated and cost and self.project:
                remaining = max(0, self.project.target_minutes*60-self.project.total_seconds)
                text += f" • Speech {generated/cost:.2f}× realtime • Estimated remaining synthesis {remaining*cost/generated:.0f}s"
            self.performance.setText(text)
        elif self.project and value.get("version") == self.project.active_version:
            if kind == "voice":
                self.project.voice = value["voice"]
                self.adopt(self.project)
            elif kind == "narration":
                self.project.title = value["title"]
                for slide in value["slides"]:
                    self.project.slides[slide.page-1] = slide
                    self.transport.refresh_audio(slide.page-1)
                self.show_slide(self.transport.index)
            elif kind == "slide_ready":
                slide = value["slide"]
                if slide.audio_key == self.project.speech_key(slide):
                    self.project.slides[slide.page-1] = slide
                    self.transport.refresh_audio(slide.page-1)
                    self.refresh()
            elif kind == "audio":
                self.measurements.setdefault("First audio", time.monotonic()-self.job_started)
                self.transport.receive_audio(value)
            if self.live_autostart:
                buffered = self.transport.buffered_seconds
                if buffered >= self.transport.required_buffer or (self.project.prepared and buffered > 0):
                    self.present(resume=True)

    def refresh_models(self):
        previous = self.loading
        self.loading = True
        wanted = self.project.codex_model if self.project else ""
        self.codex_model.clear()
        self.codex_model.addItem("Account default", "")
        for model in self.model_catalog:
            if "image" in model.get("inputModalities", ["text", "image"]):
                self.codex_model.addItem(model.get("displayName", model["model"]), model["model"])
        if wanted and self.codex_model.findData(wanted) < 0:
            self.codex_model.addItem(wanted + " (refresh availability)", wanted)
        self.codex_model.setCurrentIndex(max(0, self.codex_model.findData(wanted)))
        self.refresh_efforts()
        self.loading = previous

    def refresh_efforts(self):
        previous = self.loading
        self.loading = True
        model = self.codex_model.currentData()
        selected = next((m for m in self.model_catalog if m["model"] == model), None) if model else next(
            (m for m in self.model_catalog if m.get("isDefault")), None)
        wanted = self.project.codex_effort if self.project else ""
        self.codex_effort.clear()
        self.codex_effort.addItem("Model default" + (" (" + selected.get("defaultReasoningEffort", "") + ")" if selected else ""), "")
        for option in (selected or {}).get("supportedReasoningEfforts", []):
            effort = option["reasoningEffort"]
            self.codex_effort.addItem(effort, effort)
            self.codex_effort.setItemData(self.codex_effort.count()-1, option.get("description", ""), Qt.ItemDataRole.ToolTipRole)
        if wanted and self.codex_effort.findData(wanted) < 0:
            self.codex_effort.addItem(wanted + " (refresh availability)", wanted)
        self.codex_effort.setCurrentIndex(max(0, self.codex_effort.findData(wanted)))
        self.loading = previous

    def model_changed(self):
        if not self.loading and self.project:
            self.project.codex_model = self.codex_model.currentData() or ""
            self.project.codex_effort = ""
            self.refresh_efforts()
            self.configuration_changed()

    def model_settings_changed(self):
        if not self.loading and self.project:
            self.project.codex_effort = self.codex_effort.currentData() or ""
            self.configuration_changed()

    def version_changed(self):
        if not self.loading and self.project and self.version_select.currentData():
            self.project.active_version = self.version_select.currentData()
            self.adopt(self.project)

    def add_version(self):
        language, ok = QInputDialog.getItem(self, "New language version", "Language", LANGUAGES, editable=False)
        if ok:
            self.project.add_version(language, translate=True)
            self.adopt(self.project)
            self.save()

    def insert_passage(self):
        if self.project:
            self.narration.insertPlainText("\n\n[" + self.passage_language.currentText() + "] ")
            self.narration.setFocus()

    def slide_directions_changed(self, value):
        if not self.loading and self.project:
            self.project.slides[self.transport.index].directions = value
            self.configuration_changed()

    def voice_settings_changed(self):
        if self.loading or not self.project:
            return
        voice = self.project.voice
        voice.source = self.voice_source.currentData()
        voice.speaker = self.speaker.currentText()
        voice.description = self.voice_description.text()
        voice.name = voice.speaker if voice.source == "CustomVoice" else "Designed voice" if voice.source == "VoiceDesign" else "My voice"
        self.options.load(self.project)
        self.configuration_changed()

    def refresh_library(self):
        self.voice_library.clear()
        for path in library():
            try:
                name = json.loads(path.read_text(encoding="utf-8"))["name"]
                self.voice_library.addItem(name, str(path))
            except (OSError, ValueError, KeyError):
                continue

    def use_saved_voice(self):
        path = self.voice_library.currentData()
        if path:
            try:
                load_voice(self.project, path)
                self.adopt(self.project)
                self.save()
            except (OSError, ValueError) as error:
                self.error(str(error))

    def save_personal_voice(self):
        name, ok = QInputDialog.getText(self, "Save reusable voice", "Voice name", text=self.project.voice.name)
        if not ok or not name.strip():
            return
        def save_current():
            try:
                save_voice(self.project, name)
                self.refresh_library()
                self.save()
            except (OSError, ValueError) as error:
                self.error(str(error))
        if self.project.voice.source != "VoiceDesign" or self.accept_designed_voice():
            save_current()


    def show_clip(self, *_):
        if not self.project:
            return
        previous = self.loading
        self.loading = True
        clips = self.project.slides[self.transport.index].clips
        index = self.clip_select.currentIndex()
        self.clip_gain.setEnabled(0 <= index < len(clips))
        self.clip_placement.setEnabled(0 <= index < len(clips))
        if 0 <= index < len(clips):
            self.clip_gain.setValue(clips[index].gain)
            self.clip_placement.setCurrentText(clips[index].placement)
        self.loading = previous

    def clip_changed(self, *_):
        if not self.loading and self.project:
            clips = self.project.slides[self.transport.index].clips
            index = self.clip_select.currentIndex()
            if 0 <= index < len(clips):
                clips[index].gain = self.clip_gain.value()
                clips[index].placement = self.clip_placement.currentText()
                self.configuration_changed()

    def add_clip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose presentation audio", "", "Audio (*.wav *.mp3 *.flac *.ogg *.m4a *.mp4);;All files (*)")
        if not path:
            return
        index = self.transport.index
        def done(clip):
            self.project.slides[index].clips.append(clip)
            self.show_slide(index)
            self.save()
        self.start_job("Importing audio clip…", partial(import_clip, self.project, Path(path)), done)

    def remove_clip(self):
        clips = self.project.slides[self.transport.index].clips
        index = self.clip_select.currentIndex()
        if 0 <= index < len(clips):
            clips.pop(index)
            self.show_slide(self.transport.index)
            self.configuration_changed()

    def add_background(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose background audio", "", "Audio (*.wav *.mp3 *.flac *.ogg *.m4a);;All files (*)")
        if path:
            def done(clip):
                clip.gain = self.background_gain.value()
                clip.loop = self.background_loop.isChecked()
                self.project.background = clip
                self.transport.refresh_audio()
                self.refresh()
                self.save()
            self.start_job("Importing background track…", partial(import_clip, self.project, Path(path), placement="background"), done)

    def remove_background(self):
        self.project.background = None
        self.configuration_changed()

    def background_changed(self, *_):
        if not self.loading and self.project and self.project.background:
            self.project.background.gain = self.background_gain.value()
            self.project.background.loop = self.background_loop.isChecked()
            self.configuration_changed()

    def system_audio_settings(self):
        import shutil
        if sys.platform == "win32":
            QDesktopServices.openUrl(QUrl("ms-settings:apps-volume"))
        elif sys.platform == "darwin":
            QDesktopServices.openUrl(QUrl("x-apple.systempreferences:com.apple.Sound-Settings.extension"))
        else:
            choices = [("systemsettings", "kcm_pulseaudio"), ("gnome-control-center", "sound"), ("pavucontrol",)]
            for command in choices:
                executable = shutil.which(command[0])
                if executable:
                    subprocess.Popen([executable, *command[1:]], env=child_env(), start_new_session=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
            self.error("Open your desktop's Sound settings to choose AutoTalk's audio output.")

    def test_audio(self):
        import numpy as np
        path = data_dir() / "test-output.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        samples = (np.sin(np.arange(24000) * (2*np.pi*440/24000)) * 3000).astype("<i2")
        samples[:480] = (samples[:480] * np.linspace(0, 1, 480)).astype("<i2")
        samples[-480:] = (samples[-480:] * np.linspace(1, 0, 480)).astype("<i2")
        with wave.open(str(path), "wb") as output:
            output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            output.writeframes(samples.tobytes())
        self.transport.preview(path)

    def queue_export(self, root):
        self.pending_exports.append(root)
        if not self.job and not self.close_requested:
            QTimer.singleShot(0, self.export_next)

    def export_next(self):
        if self.job or self.transport.active or not self.pending_exports or self.close_requested is True:
            return
        root = self.pending_exports.pop(0)
        self.start_job("Saving presentation video…", partial(export_recording, root),
                       self.export_saved)

    def refresh_recordings(self):
        self.recordings.clear()
        roots = self.preferences.value("recent_projects", [])
        roots = roots if isinstance(roots, list) else [roots]
        for root in roots:
            for path in sorted(Path(root).glob("recordings/*/session.json")):
                try:
                    info = json.loads(path.read_text())
                    if info.get("status") != "exported" and (path.parent / "audio.pcm").stat().st_size:
                        self.recordings.addItem(f"Unfinished: {Path(root).name} / {path.parent.name[:8]}", str(path))
                except (OSError, ValueError):
                    continue
        if not self.recordings.count():
            self.recordings.addItem("No unfinished recordings", "")

    def recover_recording(self):
        path = self.recordings.currentData()
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Export a recorded session", "", "Recording metadata (session.json)")
        if path:
            destination, _ = QFileDialog.getSaveFileName(self, "Export recording", "presentation.mp4", "Video (*.mp4);;WAV audio (*.wav);;M4A audio (*.m4a)")
            if destination:
                self.start_job("Exporting recorded session…", partial(export_recording, Path(path).parent, destination=destination), self.export_saved)

    def accept_script(self):
        try:
            self.project.accept_script()
            self.save()
            self.transport.refresh_audio()
            self.refresh()
        except ValueError as error:
            self.error(str(error))

    def language_selected(self, language):
        if self.loading or not self.project or language == self.project.language:
            return
        existing = next((key for key, version in self.project.versions.items() if version.language == language), None)
        if existing:
            self.project.active_version = existing
        elif not any(s.passages for s in self.project.slides):
            self.project.language = language
        else:
            self.project.add_version(language, translate=True)
            self.log_message("New language version created. Create its script to translate the talk; your original version is preserved.")
        self.adopt(self.project)
        self.save()

    def accept_designed_voice(self):
        if self.project.voice.source != "VoiceDesign":
            return False
        from .project import Slide
        sample = Slide(0)
        sample.narration = preview_text(self.project)
        path = data_dir() / "previews" / (self.project.speech_key(sample) + ".wav")
        if not path.exists():
            self.error("Preview this design first, then accept the voice you heard.")
            return False
        try:
            self.project.set_voice(path, sample.narration)
        except (OSError, ValueError) as error:
            self.error(str(error))
            return False
        self.project.voice.name = "Designed voice"
        self.adopt(self.project)
        self.save()
        return True

    def retention_changed(self):
        policy = self.gpu_retention.currentData()
        self.preferences.setValue("gpu_retention", policy)
        self.speech.set_retention(policy)

    def release_gpu(self):
        if not self.job and self.speech.process:
            self.start_job("Releasing speech GPU…", lambda task: self.speech.release())

    def export_talk(self):
        destination, _ = QFileDialog.getSaveFileName(self, "Export prepared talk", "presentation.mp4", "Video (*.mp4);;WAV audio (*.wav);;M4A audio (*.m4a)")
        if destination:
            self.start_job("Exporting prepared talk…", partial(export_prepared, copy.deepcopy(self.project), destination=destination), self.export_saved)

    def export_saved(self, path):
        self.output_path = str(Path(path).resolve())
        self.output_button.setEnabled(True)
        self.folder_button.setEnabled(True)
        self.log_message("Saved: " + self.output_path)
        self.refresh_recordings()

    def closeEvent(self, event):
        if not self.close_requested and (self.transport.capture or self.pending_exports or (self.job and self.job.title.startswith(("Saving", "Export")))):
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Save presentation")
            dialog.setText("A recording or export is unfinished.")
            finish = dialog.addButton("Finish saving and close", QMessageBox.ButtonRole.AcceptRole)
            later = dialog.addButton("Close and save later", QMessageBox.ButtonRole.DestructiveRole)
            dialog.addButton(QMessageBox.StandardButton.Cancel)
            dialog.exec()
            if dialog.clickedButton() not in (finish, later):
                event.ignore()
                return
            self.close_requested = "saving" if dialog.clickedButton() == finish else True
            if self.job_live:
                self.cancel()
            self.transport.stop()
        if self.close_requested == "saving":
            if not self.job and self.pending_exports:
                self.export_next()
            if self.job:
                event.ignore()
                return
        self.close_requested = True
        if self.job:
            self.cancel()
            event.ignore()
            return
        if self.recorder.source:
            self.toggle_recording()
        if self.presentation:
            self.presentation.close()
        self.transport.stop()
        if self.save():
            self.speech.release()
            event.accept()
        else:
            self.close_requested = False
            event.ignore()


def main():
    parser = argparse.ArgumentParser(description="AutoTalk — timed PDF presentations in your own voice")
    parser.add_argument("project", nargs="?", help="Saved talk.autotalk.json to open")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("AutoTalk")
    app.setOrganizationName("SNodeC")
    window = MainWindow()
    window.show()
    if args.project:
        QTimer.singleShot(0, lambda: window.open_project(args.project))
    if args.smoke_test:
        QTimer.singleShot(1000, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
