"""Qt desktop application. Heavy preparation always runs outside the GUI thread."""

import argparse
import html
import sys
import wave
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QKeySequence, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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
from .project import LANGUAGES, Project, wav_duration
from .recording import Recorder
from .runtime import Cancelled, Task, data_dir, ensure_codex, ensure_speech
from .services import extract_scope, import_pdf, narrate, prepare, synthesize

STYLE = """
QMainWindow, QDialog { background: #101722; color: #e7edf5; }
QWidget { color: #e7edf5; font-size: 14px; }
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

    def __init__(self, function, parent):
        super().__init__(parent)
        self.function = function
        self.task = Task(self.message.emit, self.url.emit, self.detail.emit)

    def run(self):
        try:
            self.succeeded.emit(self.function(self.task))
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
        self.presentation = None
        self.loading = False
        self.close_requested = False
        self.setWindowTitle("AutoTalk")
        self.resize(1240, 880)
        self.setMinimumSize(940, 680)
        self.transport = Playback(self)
        self.transport.slide_changed.connect(self.show_slide)
        self.transport.changed.connect(self.update_timing)
        self.transport.failed.connect(self.error)
        self.transport.finished.connect(lambda: self.log_message("Presentation finished."))
        self.preview = QMediaPlayer(self)
        self.preview_output = QAudioOutput(self)
        self.preview.setAudioOutput(self.preview_output)
        self.preview.errorOccurred.connect(lambda _, text: self.error(text))
        self.recorder = Recorder()
        self.record_timer = QTimer(self)
        self.record_timer.setSingleShot(True)
        self.record_timer.timeout.connect(self.toggle_recording)
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
            ("Prepare runtime", self.setup_runtime, "")]:
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

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self._details_tab()
        self._narration_tab()
        self._voice_tab()
        self._presentation_tab()

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
        self.statusBar().showMessage("AutoTalk 0.1 • Linux prototype")

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
        self.audience = QLineEdit("General conference audience")
        form.addRow("Audience", self.audience)
        self.objective = QLineEdit("Explain the key ideas and takeaways")
        form.addRow("Talk objective", self.objective)
        urlrow = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://conference.example/call-for-papers")
        urlrow.addWidget(self.url)
        urlrow.addWidget(button("Read conference website", self.read_conference))
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
        content_box.addWidget(QLabel("Spoken narration"))
        self.narration = QPlainTextEdit()
        self.narration.setPlaceholderText("Generate narration or write your own text for this slide.")
        self.narration.textChanged.connect(self.narration_changed)
        content_box.addWidget(self.narration, 2)
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
        box.addWidget(description("Use Qwen's built-in Ryan voice, or provide a clean WAV recording of your own voice. A 10–30 second sample in a quiet room is a useful starting point. No voice training commands are required."))
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
        box.addWidget(description("Speech is synthesized locally on the NVIDIA GPU. The first use downloads the selected model and its runtime. Presentations should disclose that the narration is AI-generated."))
        row = QHBoxLayout()
        row.addWidget(button("Preview voice", self.preview_voice, True))
        row.addWidget(button("Stop preview", self.preview.stop))
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
        self.screen = QComboBox()
        for i, screen in enumerate(QApplication.screens()):
            self.screen.addItem(f"Display {i+1}: {screen.name()}", i)
        box.addWidget(self.screen)
        row = QHBoxLayout()
        self.previous_button = button("Previous", partial(self.transport.step, -1))
        self.play_button = button("Play / pause", self.transport.toggle)
        self.next_button = button("Next", partial(self.transport.step, 1))
        self.present_button = button("Present fullscreen", self.present, True)
        for widget in (self.previous_button, self.play_button, self.next_button,
                       button("Stop", self.transport.stop), self.present_button):
            row.addWidget(widget)
        box.addLayout(row)
        self.play_time = description("Elapsed 0:00 • Remaining 0:00")
        box.addWidget(self.play_time)
        box.addWidget(description("Fullscreen controls: Space pauses/resumes • Arrow keys change slides • Esc stops and returns to the editor. Playback uses saved audio and works offline."))
        self.tabs.addTab(page, "4  Present")

    def error(self, message):
        self.log_message(message)
        QMessageBox.warning(self, "AutoTalk", message)

    def log_message(self, message):
        self.log.appendPlainText(message)
        self.status.setText(message.splitlines()[-1][:220] if message else "")

    def start_job(self, title, function, callback=None):
        if self.job:
            return
        if not self.save():
            return
        self.transport.stop()
        self.preview.stop()
        self.log_message(title)
        self.tabs.setEnabled(False)
        for action in self.actions:
            action.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.job = Job(function, self)
        self.job.message.connect(self.log_message)
        self.job.detail.connect(self.log.appendPlainText)
        self.job.url.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.job.failed.connect(self.error)
        if callback:
            self.job.succeeded.connect(callback)
        self.job.finished.connect(self.job_finished)
        self.job.start()

    def job_finished(self):
        self.job.deleteLater()
        self.job = None
        self.progress.hide()
        self.cancel_button.hide()
        for action in self.actions:
            action.setEnabled(True)
        self.refresh()
        if self.project:
            self.show_slide(self.transport.index)
        if self.close_requested:
            self.close()

    def cancel(self):
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
        self.loading = False
        self.refresh()

    def refresh(self):
        p = self.project
        self.tabs.setEnabled(p is not None and self.job is None)
        if not p:
            return
        self.title_label.setText(p.title or "Untitled talk")
        self.voice_label.setText("My voice • reference recording ready" if p.voice_file else "Built-in voice: Ryan")
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
        self.play_button.setEnabled(p.prepared)
        self.present_button.setEnabled(p.prepared and self.presentation is None)
        self.prepare_button.setEnabled(self.presentation is None)
        self.fit_button.setEnabled(self.presentation is None)
        self.update_timing()

    def update_timing(self):
        if not hasattr(self, "play_time"):
            return
        total = self.project.total_seconds if self.project else 0
        elapsed = self.transport.elapsed
        self.play_time.setText(f"Elapsed {clock(elapsed)} • Remaining {clock(total-elapsed)}")

    def connect_chatgpt(self):
        def connect(task):
            with Codex(task) as codex:
                return codex.login()
        self.start_job("Connecting to ChatGPT…", connect, self.connection.setText)

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
        self.start_job("Reading conference scope…", partial(extract_scope, self.url.text().strip()), done)

    def create_narration(self):
        if not self.project:
            return
        if not self.project.scope.strip():
            self.error("Enter the conference scope or extract it from a website first.")
            return
        if (any(s.narration.strip() for s in self.project.slides)
                and QMessageBox.question(self, "Replace narration?", "Regenerate the complete narration? This replaces your current script edits.") != QMessageBox.StandardButton.Yes):
            return
        def done(project):
            self.adopt(project)
            self.tabs.setCurrentIndex(1)
            self.log_message("Narration is ready to review.")
        self.start_job("Creating narration…", partial(narrate, self.project), done)

    def generate_speech(self):
        self.start_job("Preparing speech…", partial(prepare, self.project),
                       lambda _: self.log_message("Speech preparation finished. Check the measured duration."))

    def fit_duration(self):
        if QMessageBox.question(self, "Fit duration", "AutoTalk will revise your narration and regenerate audio, up to three times, using your Codex allowance. Continue?") != QMessageBox.StandardButton.Yes:
            return
        self.start_job("Fitting the talk to its duration…", lambda task: prepare(self.project, task, fit=True),
                       lambda _: self.log_message("Duration adjustment finished. Review the result."))

    def default_voice(self):
        self.transport.stop()
        self.project.voice_file = self.project.voice_hash = self.project.voice_transcript = ""
        self.transcript.clear()
        self.refresh()

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
            self.refresh()
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
                self.transport.stop()
                self.preview.stop()
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
            self.preview.setSource(QUrl.fromLocalFile(str(path)))
            self.preview.play()
            self.log_message("Playing your voice preview.")
        self.start_job("Generating voice preview…", lambda task: synthesize(self.project, task, preview=True), done)

    def present(self):
        if not self.project.prepared:
            return
        if not self.save():
            return
        self.preview.stop()
        self.transport.select(0)
        self.presentation = Presentation(self.transport)
        screen = QApplication.screens()[min(self.screen.currentIndex(), len(QApplication.screens())-1)]
        self.presentation.setScreen(screen)
        self.presentation.setGeometry(screen.geometry())
        self.presentation.closed.connect(self.presentation_closed)
        self.tabs.setCurrentIndex(3)
        for index in range(3):
            self.tabs.setTabEnabled(index, False)
        self.present_button.setEnabled(False)
        self.prepare_button.setEnabled(False)
        self.fit_button.setEnabled(False)
        for action in self.actions:
            action.setEnabled(False)
        self.presentation.showFullScreen()
        self.transport.play()

    def presentation_closed(self):
        self.presentation.deleteLater()
        self.presentation = None
        for index in range(3):
            self.tabs.setTabEnabled(index, True)
        for action in self.actions:
            action.setEnabled(True)
        self.refresh()

    def closeEvent(self, event):
        if self.job:
            self.close_requested = True
            self.cancel()
            event.ignore()
            return
        if self.recorder.source:
            self.toggle_recording()
        if self.presentation:
            self.presentation.close()
        self.preview.stop()
        self.transport.stop()
        if self.save():
            event.accept()
        else:
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
