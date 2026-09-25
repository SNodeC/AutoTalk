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

from PySide6.QtCore import Qt, QMicrophonePermission, QThread, QTimer, QUrl, Signal
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .codex import Codex
from .playback import Playback, Presentation
from .project import LANGUAGES, SPEAKERS, Project, Voice, wav_duration
from .recording import Recorder
from .runtime import Cancelled, Task, child_env, data_dir, ensure_codex, ensure_speech
from .services import extract_scope, import_pdf, narrate, prepare, preview_text, synthesize, workflow
from .options import SettingsPanel
from .media import export_recording, import_clip
from .voices import library, load_voice, save_voice

STYLE = """
QWidget { background: #101722; color: #e7edf5; font-size: 14px; }
QToolBar { background: #172231; border: none; padding: 8px; spacing: 12px; }
QToolButton { padding: 8px 12px; border-radius: 5px; }
QToolButton:hover { background: #2b3d52; }
QPushButton { background: #26384d; border: 1px solid #38516b; padding: 9px 15px; border-radius: 6px; }
QPushButton:hover { background: #344b65; }
QPushButton:disabled, QToolButton:disabled { color: #748397; background: #1b2634; }
QPushButton[primary="true"] { background: #ed9a4c; border-color: #ed9a4c; color: #101722; font-weight: 600; }
QPushButton[primary="true"]:disabled { background: #715033; color: #baa18a; }
QLineEdit, QPlainTextEdit, QDoubleSpinBox, QComboBox { background: #172231; border: 1px solid #34465c; border-radius: 5px; padding: 7px; selection-background-color: #466889; }
QListWidget { background: #131e2c; border: 1px solid #2b3b50; border-radius: 6px; padding: 6px; }
QListWidget::item { padding: 12px 8px; border-radius: 4px; }
QListWidget::item:selected { background: #31465e; color: #fff; }
QTabWidget::pane { border: 1px solid #2b3b50; border-radius: 6px; }
QTabBar::tab { background: #172231; padding: 12px 20px; margin-right: 3px; }
QTabBar::tab:selected { background: #30455f; }
QProgressBar { background: #172231; border: 0; border-radius: 3px; min-height: 6px; }
QProgressBar::chunk { background: #ed9a4c; }
QProgressBar#slideProgress { min-height: 24px; max-height: 24px; text-align: center; }
QProgressBar#slideProgress::chunk { background: #38516b; }
QLabel#muted { color: #a7b5c6; }
QLabel#brand { font-size: 30px; font-weight: 700; }
QLabel#talkTitle { font-size: 19px; }
QLabel#duration { font-size: 23px; }
QLabel#voiceName { font-size: 19px; }
QStatusBar { background: #172231; }
QScrollArea { border: none; background: transparent; }
QMessageBox { background: #172231; }
"""


def button(text, function, primary=False):
    widget = QPushButton(text)
    widget.setProperty("primary", primary)
    widget.clicked.connect(lambda: function())
    return widget


def description(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName("muted")
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
        self.task = Task(self.message.emit, self.url.emit, self.detail.emit, self.event.emit)

    def run(self):
        try:
            result = self.function(self.task)
            self.task.check()
            self.succeeded.emit(result)
        except Cancelled as error:
            self.message.emit(str(error))
        except Exception as error:  # noqa: BLE001 - report any worker failure at the UI boundary
            self.failed.emit(str(error))


class SlideImage(QLabel):
    def __init__(self):
        super().__init__("Open a PDF slide deck to begin")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 210)
        self.setStyleSheet("background: #090e16; border-radius: 8px; color: #91a4ba;")
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
        self.transport.changed.connect(self.update_timing)
        self.transport.state_changed.connect(self.refresh)
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
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self.update_timing)
        self._build()
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
            ("Prepare runtime", self.setup_runtime, ""),
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
        brand.setObjectName("brand")
        brand.setFont(QFont("sans-serif", 27, QFont.Weight.Bold))
        header.addWidget(brand)
        header.addWidget(description("Your slides. Your voice. A talk that fits."), 1)
        self.connection = description("ChatGPT subscription • Local speech")
        header.addWidget(self.connection)
        layout.addLayout(header)
        self.title_label = QLabel("Create a presentation from an existing PDF")
        self.title_label.setObjectName("talkTitle")
        self.title_label.setFont(QFont("sans-serif", 16))
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
        self._narration_tab()
        self._voice_tab()
        self._presentation_tab()
        self.options = SettingsPanel()
        self.options.changed.connect(self.configuration_changed)
        self.tabs.addTab(self.options, "5  Delivery & recording")

        self.slide_progress = QProgressBar()
        self.slide_progress.setObjectName("slideProgress")
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
        self.statusBar().showMessage("AutoTalk 0.2 • " + platform.system())

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
        box.addWidget(self.scope, 1)
        self.sources = description("")
        self.sources.setOpenExternalLinks(True)
        box.addWidget(self.sources)
        box.addWidget(description("Generation sends slide images, text and conference context to Codex using your ChatGPT allowance. Voice recordings remain local."))
        box.addWidget(button("Create narration", self.create_narration, True))
        self.tabs.addTab(page, "1  Talk details")
        for widget in (self.talk_title, self.audience, self.objective, self.url):
            widget.textChanged.connect(self.details_changed)
        for widget in (self.minutes, self.tolerance, self.pause):
            widget.valueChanged.connect(self.details_changed)
        self.language.currentTextChanged.connect(self.details_changed)
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
        controls.addWidget(button("Generate speech", self.generate_speech, True))
        box.addLayout(controls)
        self.tabs.addTab(page, "2  Review narration")

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
        self.voice_label.setObjectName("voiceName")
        self.voice_label.setFont(QFont("sans-serif", 17))
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
        box.addWidget(self.transcript, 1)
        box.addWidget(description("Speech is synthesized on your local GPU. Designed voices are saved as a reference before the talk to keep one identity. The first use downloads the selected model and its runtime. Presentations should disclose that the narration is AI-generated."))
        row = QHBoxLayout()
        row.addWidget(button("Preview voice", self.preview_voice, True))
        row.addWidget(button("Stop preview", self.transport.stop))
        row.addStretch()
        box.addLayout(row)
        self.tabs.addTab(page, "3  Voice")

    def _presentation_tab(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(22, 22, 22, 22)
        self.duration_label = QLabel("Prepare speech to measure the talk")
        self.duration_label.setObjectName("duration")
        self.duration_label.setFont(QFont("sans-serif", 22))
        box.addWidget(self.duration_label)
        self.fit_label = description("")
        box.addWidget(self.fit_label)
        self.play_image = SlideImage()
        box.addWidget(self.play_image, 1)
        row = QHBoxLayout()
        self.prepare_button = button("Generate / update audio", self.generate_speech)
        self.fit_button = button("Fit narration to duration", self.fit_duration)
        row.addWidget(self.prepare_button)
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
        for widget in (self.previous_button, self.play_button, self.next_button, button("Stop", self.stop_presentation)):
            row.addWidget(widget)
        box.addLayout(row)
        row = QHBoxLayout()
        for widget in (self.present_button, self.continue_button, self.restart_button):
            row.addWidget(widget)
        box.addLayout(row)
        self.play_time = description("Elapsed 0:00 • Remaining 0:00")
        box.addWidget(self.play_time)
        box.addWidget(description("Fullscreen controls: Space pauses/resumes • Arrow keys change slides • Esc pauses and returns to the editor; Continue preserves your position. Playback uses saved audio and works offline."))
        self.tabs.addTab(page, "4  Present")

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
            self.tabs.setTabEnabled(i, not live or i == 3)
        self.mode.setEnabled(False)
        self.start_button.setEnabled(False)
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
        self.job.message.connect(self.log_message)
        self.job.detail.connect(self.log.appendPlainText)
        self.job.url.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.job.failed.connect(self.job_error)
        self.job.event.connect(self.job_event)
        if callback:
            self.job.succeeded.connect(callback)
        self.job.finished.connect(self.job_finished)
        self.job.start()

    def job_finished(self):
        self.elapsed_timer.stop()
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
        if self.close_requested:
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
        self.start_job("Importing PDF…", lambda task: import_pdf(Path(pdf), destination, task), self.adopt)

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
        p.pause_seconds, p.language = self.pause.value(), self.language.currentText()
        p.audience, p.objective = self.audience.text(), self.objective.text()
        p.conference_url = self.url.text().strip()
        self.options.load(p)
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
            self.tabs.setTabEnabled(i, i == 3 or editable)
        self.mode.setEnabled(editable)
        self.start_button.setEnabled(p is not None and editable)
        for action in self.actions:
            action.setEnabled(editable)
        if not p:
            return
        self.title_label.setText(p.title or "Untitled talk")
        self.voice_label.setText(f"Qwen3-TTS 1.7B {p.effective_voice.source} • {p.effective_voice.name}")
        self.tabs.setTabEnabled(2, editable and p.mode != "Quick")
        self.codex_model.setEnabled(p.mode != "Quick")
        self.codex_effort.setEnabled(p.mode != "Quick")
        self.voice_source.setEnabled(p.mode != "Quick")
        self.speaker.setEnabled(p.voice.source == "CustomVoice" and p.mode != "Quick")
        self.voice_description.setEnabled(p.voice.source == "VoiceDesign" and p.mode != "Quick")
        self.slide_directions.setEnabled(p.voice.source != "Base" and p.mode != "Quick")
        self.start_button.setText("Prepare talk" if p.mode == "Prepared" else "Start " + p.mode)
        for widget in (self.url, self.scope, self.audience, self.objective, self.conference_button):
            widget.setEnabled(p.mode != "Quick")
        self.audio_test_button.setEnabled(editable)
        self.background_button.setText("Background: " + Path(p.background.file).name[:16] if p.background else "Add background track")
        for widget in (self.background_button, self.background_gain, self.background_loop, self.remove_background_button):
            widget.setEnabled(editable)

        self.transcript.setEnabled(bool(p.voice_file))
        self.sources.setText("Sources: " + " · ".join(
            f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>' for url in p.sources) if p.sources else "")
        ready = sum(p.ready(s) for s in p.slides)
        self.duration_label.setText(f"{clock(p.total_seconds)} prepared  /  {clock(p.target_minutes*60)} target")
        self.fit_label.setText(f"{ready}/{len(p.slides)} slides have current audio. " +
            ("Within requested tolerance." if p.within_target else
             f"Difference: {p.total_seconds-p.target_minutes*60:+.1f} seconds (tolerance ±{p.tolerance_seconds:g}s)." if p.prepared
             else "Generate audio to measure the complete talk."))
        self.context_warning.setText("Conference context or timing has changed since narration generation. Review or regenerate the script."
            if p.narration_context and p.narration_context != p.context_key() else "Review each slide's narration before generating speech.")
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
        self.prepare_button.setEnabled(editable)
        self.fit_button.setEnabled(editable)
        self.update_timing()

    def update_timing(self):
        if not hasattr(self, "play_time"):
            return
        total = self.project.total_seconds if self.project else 0
        elapsed = self.transport.elapsed
        self.play_time.setText(f"{self.transport.state.capitalize()} • Elapsed {clock(elapsed)} • Remaining {clock(total-elapsed)} • Buffered {self.transport.buffered_seconds:.1f}s")
        if self.job:
            self.statusBar().showMessage(f"Operation elapsed: {clock(time.monotonic()-self.job_started)}")

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

    def setup_runtime(self):
        def setup(task):
            ensure_codex(task)
            ensure_speech(task)
            task.report("Runtime installed. Preview a voice to download its model and verify GPU synthesis.")
        self.start_job("Preparing AutoTalk runtimes…", setup)

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
        self.tabs.setCurrentIndex(3)
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
        if self.project.mode == "Prepared" and not all(s.passages for s in self.project.slides):
            self.create_narration()
            return
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
                self.after_job = self.present
        self.start_job("Preparing " + snapshot.mode + " presentation…", partial(workflow, snapshot), done,
                       live=snapshot.mode == "Realtime")

    def accept_result(self, project):
        if self.transport.active or self.presentation:
            self.project = self.transport.project = project
            self.options.load(project)
            self.show_slide(self.transport.index)
        else:
            self.adopt(project)
        self.refresh()

    def job_error(self, message):
        self.live_autostart = False
        if self.transport.active:
            self.transport.pause()
        self.error(message)

    def job_event(self, value):
        if self.job is None:
            return
        kind = value.get("type")
        if kind == "progress":
            self.slide_progress.setRange(0, max(1, value["total"]))
            self.slide_progress.setValue(value["completed"])
            self.slide_progress.setFormat(value["stage"] + ": %v / %m")
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
                self.project.narration_context = value["context"]
                for slide in value["slides"]:
                    self.project.slides[slide.page-1] = slide
                self.show_slide(self.transport.index)
            elif kind == "slide_ready":
                slide = value["slide"]
                if slide.audio_key == self.project.speech_key(slide):
                    self.project.slides[slide.page-1] = slide
                    self.refresh()
            elif kind == "audio":
                self.transport.receive_audio(value)
            if self.live_autostart:
                buffered = self.transport.buffered_seconds
                first_ready = self.project.ready(self.project.slides[0])
                if buffered >= self.project.buffer_seconds or (first_ready and buffered > 0):
                    self.present()

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
            self.project.add_version(language)
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
        if self.project.voice.source == "VoiceDesign":
            snapshot = copy.deepcopy(self.project)
            def designed(path):
                self.project.set_voice(path, preview_text(snapshot))
                self.project.voice.name = name
                save_current()
                self.adopt(self.project)
                self.log_message("Designed identity saved as a reference voice. Future speech reuses this identity through Base cloning.")
            self.start_job("Creating a reusable voice identity…", partial(synthesize, snapshot, preview=True), designed)
        else:
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
        if self.job or self.transport.active or not self.pending_exports or self.close_requested:
            return
        root = self.pending_exports.pop(0)
        self.start_job("Saving presentation video…", partial(export_recording, root),
                       lambda path: self.log_message("Video saved: " + str(path)))

    def recover_recording(self):
        path, _ = QFileDialog.getOpenFileName(self, "Export a recorded session", "", "Recording metadata (session.json)")
        if path:
            destination, _ = QFileDialog.getSaveFileName(self, "Export recording", "presentation.mp4", "MP4 video (*.mp4)")
            if destination:
                self.start_job("Exporting recorded session…", partial(export_recording, Path(path).parent, destination=destination),
                               lambda result: self.log_message("Video saved: " + str(result)))

    def closeEvent(self, event):
        self.close_requested = True
        if self.job:
            self.close_requested = True
            self.cancel()
            event.ignore()
            return
        if self.recorder.source:
            self.toggle_recording()
        if self.presentation:
            self.presentation.close()
        self.transport.stop()
        if self.save():
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
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    if args.project:
        QTimer.singleShot(0, lambda: window.open_project(args.project))
    if args.smoke_test:
        QTimer.singleShot(1000, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
