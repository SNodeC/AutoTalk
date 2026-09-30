# SPDX-License-Identifier: MIT
"""Desktop workspace and section dialogs; project and playback remain in the controller."""
import wave
import numpy as np
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QIcon, QDesktopServices, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QApplication, QAbstractSpinBox, QComboBox, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLayout, QLabel, QLineEdit, QListView, QListWidget,
    QPlainTextEdit, QProgressBar, QPushButton, QToolButton, QMessageBox, QScrollArea,
    QTableWidget, QHeaderView, QAbstractItemView, QSizePolicy, QSplitter, QStackedWidget, QTabBar, QMenu, QVBoxLayout, QWidget,
)


# Geometry is deliberately scoped to our surfaces. Native dialogs and the platform
# checkbox indicators keep their system style; every color follows the Qt palette.
STYLE = """
QWidget#workspace, QWidget#paper { background: palette(base); }
QWidget#chrome { background: palette(window); }
QLabel#heading { font-size: 17px; font-weight: 600; }
QLabel#title { font-weight: 600; }
QPushButton { padding: 6px 10px; border-radius: 3px;
    border: 1px solid palette(mid); background: palette(button); }
QPushButton:hover { border-color: palette(highlight); }
QPushButton:pressed { background: palette(midlight); }
QPushButton[primary="true"]:enabled {
    background: palette(highlight); color: palette(highlighted-text);
    border: 1px solid palette(highlight); font-weight: 600;
}
QCheckBox { spacing: 7px; min-height: 28px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QListWidget#sections::item { padding: 8px; }
QListWidget#sections, QListWidget#slides { background: palette(window); border: 0; }
QListWidget#slides::item { padding: 5px; border: 1px solid transparent; border-radius: 3px; }
QListWidget#slides::item:selected {
    border: 1px solid palette(highlight); background: palette(alternate-base); color: palette(text);
}
QProgressBar { max-height: 17px; border: 1px solid palette(mid); border-radius: 2px; text-align: center; }
QProgressBar::chunk { background: palette(highlight); }
QSplitter::handle { background: palette(mid); }
"""


def label(text, name=""):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setObjectName(name)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.setProperty("primary", primary)
    widget.clicked.connect(lambda: callback())
    return widget


def column(name="", margin=12):
    widget = QWidget()
    widget.setObjectName(name)
    box = QVBoxLayout(widget)
    box.setContentsMargins(margin, margin, margin, margin)
    box.setSpacing(10)
    return widget


def row(*widgets):
    box = QHBoxLayout()
    box.setSpacing(6)
    for widget in widgets:
        box.addStretch() if widget is None else box.addWidget(widget)
    return box


def form(parent):
    box = QFormLayout()
    box.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    box.setVerticalSpacing(12)
    parent.layout().addLayout(box)
    return box


def combo(values, callback=None):
    widget = QComboBox()
    for value in values:
        widget.addItem(*value) if isinstance(value, tuple) else widget.addItem(value)
    widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    widget.setMinimumContentsLength(10)
    if callback:
        widget.currentIndexChanged.connect(callback)
    return widget


def number(low, high, value, callback, suffix=""):
    widget = QDoubleSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    widget.setSuffix(suffix)
    widget.valueChanged.connect(callback)
    return widget


def disclosure_button(title, content):
    toggle = QToolButton(text=title, checkable=True, arrowType=Qt.ArrowType.RightArrow,
                         toolButtonStyle=Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.toggled.connect(lambda shown: (content.setVisible(shown), toggle.setArrowType(Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow)))
    content.hide()
    return toggle


def disclosure(parent, title, content):
    toggle = disclosure_button(title, content)
    parent.layout().addWidget(toggle)
    parent.layout().addWidget(content)
    return toggle


class ElidedLabel(QLabel):
    def setText(self, text):
        self.setToolTip(text)
        super().setText(self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, self.width()))

    def resizeEvent(self, event):
        self.setText(self.toolTip())
        super().resizeEvent(event)


class Waveform(QWidget):
    def __init__(self):
        super().__init__()
        self.peaks, self.progress = [], 0
        self.path = None
        self.setMinimumSize(60, 30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, path):
        if path == self.path:
            return
        self.peaks = []
        if path and path.is_file():
            with wave.open(str(path), "rb") as audio:
                values = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(float)
            if len(values):
                peaks = [np.max(np.abs(v)) for v in np.array_split(values, min(60, len(values)))]
                self.peaks = np.asarray(peaks) / max(1, max(peaks))
        self.path = path
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        color = self.palette().highlight().color()
        for i, value in enumerate(self.peaks):
            color.setAlpha(255 if i / len(self.peaks) <= self.progress else 130)
            height = max(2, round(value * (self.height()-4)))
            width = self.width() / len(self.peaks)
            painter.fillRect(round(i*width), (self.height()-height)//2, max(1, round(width)-2), height, color)


class SectionDialog(QDialog):
    """Shared flat navigation and operation feedback, without settings policy."""
    def __init__(self, window, title):
        super().__init__(window)
        self.window = window
        window.dialogs.append(self)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(920, 760)
        self.setMinimumSize(760, 580)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        body = QHBoxLayout()
        body.setSpacing(0)
        self.navigation = QListWidget()
        self.navigation.setObjectName("sections")
        self.navigation.setFixedWidth(205)
        self.navigation.setWordWrap(True)
        self.pages = QStackedWidget()
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        body.addWidget(self.navigation)
        body.addWidget(self.pages, 1)
        outer.addLayout(body, 1)
        self.status = label("")
        self.status.setContentsMargins(12, 0, 12, 0)
        outer.addWidget(self.status)
        self.cancel_job = button("Cancel operation", lambda: window.recorder.editor.toggle_recording() if window.recorder.source else window.cancel())
        self.cancel_job.hide()
        outer.addWidget(self.cancel_job)
        kinds = QDialogButtonBox.StandardButton
        self.buttons = QDialogButtonBox(kinds.Close)
        self.buttons.setContentsMargins(12, 0, 12, 0)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

    def add(self, title, page_name="", scopes=(0, 1, 2)):
        name = page_name or title
        matches = self.navigation.findItems(name, Qt.MatchFlag.MatchExactly)
        if matches:
            body = self.pages.widget(self.navigation.row(matches[0])).widget()
        else:
            body = column("paper", 16)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(body)
            self.pages.addWidget(scroll)
            self.navigation.addItem(name)
        section = column(margin=0)
        section.setProperty("scopes", scopes)
        section.layout().addWidget(label(title, "title"))
        body.layout().addWidget(section)
        return section

    def show_section(self, section="Recordings", focus=None):
        self.navigation.setCurrentRow(self.navigation.row(self.navigation.findItems(section, Qt.MatchFlag.MatchExactly)[0]))
        self.show()
        self.window.refresh()
        self.pages.currentWidget().verticalScrollBar().setValue(0)
        if focus:
            self.pages.currentWidget().ensureWidgetVisible(focus)
            focus.setFocus()
        self.raise_()

    def sync(self, editable, job=None, **_):
        w = self.window
        self.buttons.setEnabled(not w.recorder.source)
        self.cancel_job.setVisible(job is not None or bool(w.recorder.source))
        self.cancel_job.setText("Stop voice recording" if w.recorder.source else "Cancel operation")
        if not job:
            self.status.clear()

    def done(self, result):
        if self.window.job or self.window.recorder.source:
            self.status.setText("Stop the current operation or voice recording before closing.")
            return
        super().done(result)
        self.window.refresh()


def build(w):
    from .app import SlideImage

    w.setStyleSheet(STYLE)
    w.actions, w.control_actions, w.dialogs = [], [], []
    from .settings import SettingsDialog
    w.settings = {scope: SettingsDialog(w, scope, w.defaults, w.preferences.value("presentation_display", ""), w.begin_settings, w.finish_settings) for scope in (0, 1, 2)}
    for dialog in w.settings.values():
        dialog.application_requested.connect(lambda page, focus: w.settings[0].show_section(page, focus=focus))
        dialog.record_requested.connect(w.record_voice)
        dialog.save_requested.connect(w.save)
        dialog.finished.connect(w.settings_closed)
    w.settings[1].details_changed.connect(w.details_changed)
    application = w.settings[0]
    for requested, action in ((application.sign_in_requested, w.connect_chatgpt),
            (application.sign_out_requested, lambda: w.connect_chatgpt(sign_out=True)),
            (application.load_requested, w.load_gpu), (application.unload_requested, w.release_gpu),
            (application.model_check_requested, w.check_model_updates),
            (application.engine_policy_changed, w.update_speech_controls),
            (application.test_audio_requested, w.test_audio), (application.audio_settings_requested, w.system_audio_settings),
            (w.settings[1].fit_requested, w.fit_duration)):
        requested.connect(action)
    w.export_dialog = SectionDialog(w, "Recordings & export")
    exports = w.export_dialog.add("Recordings")
    exports.layout().addWidget(label("Saved and unfinished recordings", "title"))
    w.recordings = QTableWidget(0, 4)
    w.recordings.setHorizontalHeaderLabels(["Talk", "Date", "Duration", "Status"])
    for table, stretch in ((w.recordings, 0),):
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
    w.recordings.itemSelectionChanged.connect(w.recording_selected)
    exports.layout().addWidget(w.recordings, 1)
    w.recordings_empty = label("No recordings yet. Enable recording before presenting, or export a prepared talk below.")
    exports.layout().addWidget(w.recordings_empty)
    exports.layout().addWidget(button("Presentation settings…", lambda: w.settings[1].show_section("Presentation & recording")))
    w.recover_button = button("Save selected recording…", w.recover_recording)
    exports.layout().addWidget(w.recover_button)
    w.output_button = button("Open video / audio", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(w.output_path)), True)
    w.folder_button = button("Open folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(w.output_path).parent))))
    w.output_button.setEnabled(False)
    w.folder_button.setEnabled(False)
    exports.layout().addLayout(row(w.output_button, w.folder_button))
    exports.layout().addWidget(label("Create a separate video from the prepared slides and speech. Live demos are not included."))
    w.export_button = button("Export prepared talk…", w.export_talk)
    exports.layout().addWidget(w.export_button)

    root = column("chrome", 0)
    root.layout().setSpacing(0)
    w.setCentralWidget(root)
    toolbar = w.toolbar = column("chrome", 8)
    toolbar.layout().setDirection(QVBoxLayout.Direction.LeftToRight)
    root.layout().addWidget(toolbar)
    menus = {name: w.menuBar().addMenu(name) for name in ("File", "Edit", "View", "Talk", "Presentation", "Settings", "Help")}

    def command(menu, title, callback, shortcut="", locked=False, control=None):
        action = QAction(title, w)
        action.triggered.connect(lambda checked=False: callback())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        (menus[menu] if isinstance(menu, str) else menu).addAction(action)
        if locked:
            w.actions.append(action)
        if control:
            w.control_actions.append((action, control))
        return action

    for title, callback, shortcut in (("Open PDF…", w.new_project, "Ctrl+N"), ("Open saved talk…", w.open_project, "Ctrl+O"), ("Save", w.save, "Ctrl+S")):
        action = command("File", title, callback, shortcut, locked=True)
        control = button(title, action.trigger)
        action.changed.connect(lambda a=action, b=control: b.setEnabled(a.isEnabled()))
        control.setIcon(QIcon.fromTheme({"Open PDF…": "document-new", "Open saved talk…": "document-open", "Save": "document-save"}[title]))
        toolbar.layout().addWidget(control)
    w.reload_pdf_action = command("File", "Reload PDF…", w.reload_source_pdf)
    toolbar.layout().addStretch()
    toolbar.layout().addWidget(label("Mode"))
    w.mode = combo(["Prepared", "Quick", "Realtime"])
    for i, explanation in enumerate(("Prepare all slides before presenting; editing is optional", "Prepare and start automatically", "Start while speech for later slides is prepared")):
        w.mode.setItemData(i, explanation, Qt.ItemDataRole.ToolTipRole)
    w.mode.currentTextChanged.connect(w.mode_changed)
    toolbar.layout().addWidget(w.mode)
    w.talk_action = command("Talk", "Talk settings…", lambda: w.settings[1].show_section("Talk & preparation"), "Ctrl+T")
    talk_button = button("Talk settings…", w.talk_action.trigger)
    w.talk_action.changed.connect(lambda: talk_button.setEnabled(w.talk_action.isEnabled()))
    w.start_button = button("Start", w.start_mode, True)
    toolbar.layout().addWidget(w.start_button)
    summary = w.overview = column("paper", 8)
    summary.layout().setSpacing(6)
    w.title_label, w.summary = label("", "title"), label("")
    w.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    w.view_switch = QTabBar()
    w.view_switch.setExpanding(False)
    for title in ("Editor", "Presenter"):
        w.view_switch.addTab(title)
    summary.layout().addLayout(row(w.title_label, w.summary, w.view_switch))
    w.minutes = number(.1, 240, 10, w.details_changed, " min")
    w.minutes.setMaximumWidth(125)
    w.language = combo([], w.language_selected)
    w.language.setMaximumWidth(190)
    w.voice_button = button("Voice && speech…", lambda: w.settings[1].show_section("Voice & language"))
    summary.layout().addLayout(row(label("Duration"), w.minutes, None, label("Language"), w.language, None, w.voice_button, talk_button))
    w.preparation = column(margin=0)
    w.talk_text_button = button("Create talk text", w.create_narration)
    w.talk_audio_button = button("Create talk audio", w.prepare_talk)
    w.preparation.layout().addLayout(row(w.talk_text_button, w.talk_audio_button, None))
    root.layout().addWidget(summary)
    w.workspace = QStackedWidget()
    root.layout().addWidget(w.workspace, 1)

    w.editor = QSplitter()
    w.editor.setObjectName("workspace")
    w.editor.setChildrenCollapsible(False)
    navigation = column("chrome", 8)
    navigation.layout().addWidget(label("Slides", "title"))
    w.slide_list = QListWidget()
    w.slide_list.setObjectName("slides")
    w.slide_list.setViewMode(QListView.ViewMode.IconMode)
    w.slide_list.setFlow(QListView.Flow.TopToBottom)
    w.slide_list.setWrapping(False)
    w.slide_list.setMovement(QListView.Movement.Static)
    w.slide_list.setIconSize(QSize(90, 50))
    w.slide_list.setGridSize(QSize(116, 125))
    w.slide_list.setWordWrap(True)
    w.slide_list.setTextElideMode(Qt.TextElideMode.ElideNone)
    w.slide_list.currentRowChanged.connect(w.select_slide)
    navigation.layout().addWidget(w.slide_list, 1)
    center = column("paper", 10)
    center.layout().setSpacing(6)
    w.image = SlideImage()
    editor_split = QSplitter(Qt.Orientation.Vertical)
    editor_split.setChildrenCollapsible(False)
    editor_split.addWidget(w.image)
    text_panel = column(margin=0)
    text_panel.layout().setSpacing(center.layout().spacing())
    text_panel.layout().setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    center.layout().addWidget(editor_split, 1)
    w.slide_info = ElidedLabel()
    w.slide_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    w.editor_previous = button("Previous", lambda: w.navigate_slide(-1))
    w.editor_next = button("Next", lambda: w.navigate_slide(1))
    for control, title, key in ((w.editor_previous, "Previous", "PgUp"), (w.editor_next, "Next", "PgDn")):
        control.setToolTip(f"{title} slide (Ctrl+{key})")
    info_row = row(w.slide_info, w.editor_previous, w.editor_next)
    info_row.setStretch(0, 1)
    text_panel.layout().addLayout(info_row)
    w.narration = QPlainTextEdit()
    w.narration.setMinimumHeight(110)
    w.narration.setPlaceholderText("Write the talk text, or type what you want to say on this slide.")
    w.narration.textChanged.connect(w.narration_changed)
    text_panel.layout().addWidget(w.narration, 1)
    editor_split.addWidget(text_panel)
    editor_split.setMinimumHeight(w.image.minimumHeight() + text_panel.minimumSizeHint().height() + editor_split.handleWidth())
    editor_split.setSizes([300, 330])
    w.regenerate_button = button("Create slide text", w.regenerate_slide)
    w.slide_audio_button = button("Create slide audio", w.prepare_slide)
    w.preview_button = button("Play audio", w.preview_slide)
    w.preview_time = label("0:00")
    w.preview_time.setWordWrap(False)
    w.waveform = Waveform()
    center.layout().addLayout(row(w.regenerate_button, w.slide_audio_button, w.preview_button, w.waveform, w.preview_time))
    w.notes = label("")
    w.notes_toggle = disclosure_button("AI notes", w.notes)
    w.notes_toggle.setToolTip("Codex’s interpretation notes for this slide. These are not spoken.")
    center.layout().addLayout(row(w.notes_toggle, button("Insert language passage…", w.insert_passage), None))
    center.layout().addWidget(w.notes)
    from .inspector import InspectorPanel
    w.inspector = InspectorPanel(w)
    w.inspector.open_settings.connect(lambda page: w.settings[2].show_section(page))
    inspector = w.inspector
    inspector_scroll = QScrollArea()
    inspector_scroll.setWidgetResizable(True)
    inspector_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    inspector.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
    inspector_scroll.setWidget(inspector)
    inspector_scroll.setMinimumWidth(200)
    for pane in (navigation, center, inspector_scroll):
        w.editor.addWidget(pane)
    w.editor.setSizes([154, 644, 226])
    w.editor.setStretchFactor(1, 1)
    w.authoring_widgets = [inspector, w.preparation, w.image] + [c for c in center.findChildren(QPushButton) if c not in (w.editor_previous, w.editor_next)]
    w.workspace.addWidget(w.editor)

    w.presenter = column("paper", 15)
    w.duration_label = label("Prepare speech to measure the talk", "heading")
    w.play_time = label("Stopped · Elapsed 0:00")
    w.presenter.layout().addLayout(row(w.duration_label, w.play_time))
    slides_panel = QWidget()
    slides = QHBoxLayout(slides_panel)
    slides.setContentsMargins(0, 0, 0, 0)
    current, following = column(margin=0), column(margin=0)
    current.layout().addWidget(label("Current slide", "title"))
    w.next_label = label("Up next", "title")
    following.layout().addWidget(w.next_label)
    w.play_image, w.next_image = SlideImage(), SlideImage()
    current.layout().addWidget(w.play_image, 1)
    following.layout().addWidget(w.next_image, 1)
    slides.addWidget(current, 2)
    slides.addWidget(following, 1)
    presenter_split = QSplitter(Qt.Orientation.Vertical)
    presenter_split.setChildrenCollapsible(False)
    presenter_split.addWidget(slides_panel)
    w.presenter.layout().addWidget(presenter_split, 1)
    w.presenter_narration = QPlainTextEdit()
    w.presenter_narration.setReadOnly(True)
    presenter_split.addWidget(w.presenter_narration)
    presenter_split.setSizes([450, 150])
    w.previous_button = button("Previous", lambda: w.navigate_slide(-1))
    w.play_button = button("Pause", w.transport.toggle, True)
    w.next_button = button("Next", lambda: w.navigate_slide(1))
    w.continue_button = button("Continue", w.continue_presentation, True)
    w.end_button = button("End presentation", w.stop_presentation)
    w.demo_button = button("Pause for a live demo", w.live_demo)
    w.more_presentation = button("More actions", lambda: None)
    w.more_presentation.setMenu(QMenu(w.more_presentation))
    w.presenter.layout().addLayout(row(w.previous_button, w.play_button, w.continue_button, w.next_button, w.more_presentation, None, w.demo_button, w.end_button))
    w.continue_button.setToolTip("Continue resumes at the retained position. Esc pauses and returns here.")
    w.workspace.addWidget(w.presenter)

    w.quick_page = column("paper", 24)
    w.quick_summary = label("")
    w.quick_page.layout().addWidget(w.quick_summary)
    w.quick_page.layout().addWidget(label("Quick uses the selected voice, language and inherited settings without conference setup. Choose the highlighted action above to begin."))
    w.quick_page.layout().addStretch()
    w.workspace.addWidget(w.quick_page)
    welcome = w.welcome = column("paper", 36)
    welcome.layout().addWidget(label("Turn your slides into a talk", "heading"))
    welcome.layout().addWidget(label("Open a PDF, choose a duration and language, then prepare or start presenting. Your projects keep narration, voices and recordings together."))
    welcome.layout().addLayout(row(button("Open PDF…", w.new_project, True), button("Open saved talk…", w.open_project), None))
    welcome.layout().addStretch()
    w.workspace.addWidget(welcome)
    w.workspace.setCurrentWidget(welcome)

    footer = w.footer = column("chrome", 8)
    footer.layout().setSpacing(6)
    root.layout().addWidget(footer)
    w.record_status = label("", "title")
    w.record = QCheckBox("Record presentation as a video")
    w.record.toggled.connect(lambda value: w.edit_setting("record_presentation", value))
    w.record_footer = column(margin=0)
    w.record_footer.layout().setDirection(QVBoxLayout.Direction.LeftToRight)
    w.record_footer.layout().addWidget(w.preparation)
    w.record_footer.layout().addWidget(w.record)
    w.presentation_button = button("Presentation settings…", lambda: w.settings[1].show_section("Presentation & recording"))
    w.record_footer.layout().addWidget(w.presentation_button)
    summary.layout().addWidget(w.record_footer)
    w.view_switch.currentChanged.connect(lambda i: w.workspace.setCurrentWidget(w.presenter if i else w.quick_page if w.project and w.project.mode == "Quick" else w.editor))
    w.saved_output = label("")
    w.saved_output.linkActivated.connect(lambda target: (w.output_button if target == "video" else w.folder_button).click())
    footer.layout().addLayout(row(w.record_status, w.saved_output))
    w.narration_progress, w.slide_progress = QProgressBar(), QProgressBar()
    footer.layout().addLayout(row(w.narration_progress, w.slide_progress))
    w.progress = QProgressBar()
    w.progress.hide()
    footer.layout().addWidget(w.progress)
    w.status = label("Open a PDF or a saved talk to begin.")
    w.cancel_button = button("Cancel operation", w.cancel)
    w.cancel_button.hide()
    w.signin_button = button("Sign in to ChatGPT", w.connect_chatgpt)
    status_row = row(w.status, w.signin_button, button("Operation details", lambda: w.log.setVisible(not w.log.isVisible())), w.cancel_button)
    status_row.setStretch(0, 1)
    footer.layout().addLayout(status_row)
    w.log = QPlainTextEdit()
    w.log.setReadOnly(True)
    w.log.setMaximumBlockCount(500)
    w.log.setMaximumHeight(95)
    w.log.hide()
    footer.layout().addWidget(w.log)

    recent_menu = menus["File"].addMenu("Open recent")
    def recent():
        recent_menu.clear()
        roots = w.preferences.value("recent_projects", [])
        for path in roots if isinstance(roots, list) else [roots]:
            manifest = Path(path) / "talk.autotalk.json"
            if manifest.exists():
                action = recent_menu.addAction(Path(path).name)
                action.triggered.connect(lambda checked=False, p=manifest: w.open_project(p))
    recent_menu.aboutToShow.connect(recent)
    w.actions.append(recent_menu.menuAction())
    command("File", "Save a copy…", w.save_as, "Ctrl+Shift+S", control=talk_button)
    command("File", "Open talk folder", w.open_talk_folder, control=talk_button)
    command("File", "Recordings && export…", w.export_dialog.show_section)
    command("File", "Export prepared talk…", w.export_talk, control=w.export_button)
    command("File", "Quit", w.close, "Ctrl+Q")
    for title, method, shortcut in (("Undo", "undo", "Ctrl+Z"), ("Redo", "redo", "Ctrl+Shift+Z"),
            ("Cut", "cut", "Ctrl+X"), ("Copy", "copy", "Ctrl+C"), ("Paste", "paste", "Ctrl+V"), ("Select all", "selectAll", "Ctrl+A")):
        action = command("Edit", title, lambda m=method: getattr(QApplication.focusWidget(), m, lambda: None)(), shortcut)
        menus["Edit"].aboutToShow.connect(lambda a=action, m=method: a.setEnabled(callable(getattr(QApplication.focusWidget(), m, None))))
    command("Edit", "Find in slide text…", w.find_narration, "Ctrl+F", control=w.regenerate_button)
    for title, pane in (("Slide navigator", navigation), ("Slide inspector", inspector_scroll)):
        action = command("View", title, lambda p=pane: p.setVisible(p.isHidden()))
        action.setCheckable(True)
        menus["View"].aboutToShow.connect(lambda a=action, p=pane: a.setChecked(not p.isHidden()))
    command("View", "Restore default layout", lambda: (navigation.show(), inspector_scroll.show(), w.editor.setSizes([154, 644, 226]), editor_split.setSizes([300, 330]), presenter_split.setSizes([450, 150])))
    def enlarge(source=w.image):
        dialog = QDialog(w)
        dialog.setWindowTitle("Slide preview")
        dialog.resize(1000, 720)
        dialog.setLayout(QVBoxLayout())
        image = SlideImage()
        image.original = source.original
        image.rescale()
        dialog.layout().addWidget(image)
        dialog.exec()
        dialog.deleteLater()
    w.enlarge_action = command("View", "Enlarge slide…", enlarge, control=w.image)
    for preview in (w.image, w.play_image, w.next_image):
        preview.setCursor(Qt.CursorShape.PointingHandCursor)
        preview.setToolTip("Click to enlarge this slide")
        preview.clicked.connect(lambda p=preview: enlarge(p))
    w.editor_action = command("View", "Editor", lambda: w.view_switch.setCurrentIndex(0), control=w.regenerate_button)
    presenter_action = command("View", "Presenter", lambda: w.view_switch.setCurrentIndex(1), control=w.image)
    for index, action in enumerate((w.editor_action, presenter_action)):
        action.setCheckable(True)
        menus["View"].aboutToShow.connect(lambda a=action, i=index: a.setChecked(w.view_switch.currentIndex() == i))
    command("View", "Operation details", lambda: w.log.setVisible(not w.log.isVisible()))
    command("Talk", "Voice && speech…", lambda: w.settings[1].show_section("Voice & language"), control=w.voice_button)
    command("Talk", "Create talk text", w.create_narration, control=w.talk_text_button)
    command("Talk", "Rewrite all talk text…", lambda: w.create_narration(rewrite=True), control=w.regenerate_button)
    command("Talk", "Create talk audio", w.prepare_talk, control=w.talk_audio_button)
    command("Talk", "Fit duration…", w.fit_duration, control=w.settings[1].fit_button)
    command("Talk", "Language options…", lambda: w.settings[1].show_section("Voice & language", focus=w.settings[1].options.fields["language_policy"]), control=talk_button)
    slides_menu = menus["Talk"].addMenu("Selected slide")
    w.regenerate_action = command(slides_menu, "Rewrite slide text…", w.regenerate_slide, control=w.regenerate_button)
    command(slides_menu, "Create slide audio", w.prepare_slide, control=w.slide_audio_button)
    w.preview_action = command(slides_menu, "Play audio", w.preview_slide, control=w.preview_button)
    include = command(slides_menu, "Include in presentation", w.inspector.slide_include.toggle, control=w.inspector.slide_include)
    include.setCheckable(True)
    slides_menu.aboutToShow.connect(lambda: include.setChecked(w.inspector.slide_include.isChecked()))
    command(slides_menu, "Insert language passage…", w.insert_passage, control=w.regenerate_button)
    command(slides_menu, "Additional audio…", lambda: w.settings[2].show_section("Presentation & recording"), control=w.regenerate_button)
    modes = menus["Talk"].addMenu("Mode")
    for mode in ("Prepared", "Quick", "Realtime"):
        action = command(modes, mode, lambda m=mode: w.mode.setCurrentText(m), control=w.mode)
        action.setCheckable(True)
        modes.aboutToShow.connect(lambda a=action, m=mode: a.setChecked(w.mode.currentText() == m))
    w.start_action = command("Presentation", "Start", w.start_mode, "F5", control=w.start_button)
    command("Presentation", "Continue", w.continue_presentation, "F6", control=w.continue_button)
    command("Presentation", "Pause", w.transport.pause, control=w.play_button)
    for title, callback, shortcut in (("Start from selected slide", lambda: w.present(selected=True), "Shift+F5"),
                                      ("Restart from beginning", w.restart_presentation, "")):
        action = command("Presentation", title, callback, shortcut, control=w.more_presentation)
        w.more_presentation.menu().addAction(action)
    command("Presentation", "Pause for a live demo", w.live_demo, control=w.demo_button)
    w.previous_action = command("View", "Previous slide", lambda: w.navigate_slide(-1), "Ctrl+PgUp")
    w.next_action = command("View", "Next slide", lambda: w.navigate_slide(1), "Ctrl+PgDown")
    w.end_action = command("Presentation", "End presentation", w.stop_presentation, control=w.end_button)
    command("Presentation", "Presentation settings…", lambda: w.settings[1].show_section("Presentation & recording"), control=w.presentation_button)
    command("Presentation", "System audio settings…", w.system_audio_settings)
    command("Settings", "Application settings…", lambda: w.settings[0].show_section("Application"), "Ctrl+,")
    command("Settings", "Account…", lambda: w.settings[0].show_section("Application", focus=w.settings[0].codex_signin))
    w.engine_action = command("Settings", "Speech engine…", lambda: w.settings[0].show_section("AI & speech engine", focus=w.settings[0].engine_state))
    w.load_gpu_action = command("Settings", "Load speech model now", w.load_gpu)
    w.unload_gpu_action = command("Settings", "Unload speech model now", w.release_gpu)
    w.engine_status = button("Speech engine: Not loaded…", w.engine_action.trigger)
    w.engine_status.setMaximumWidth(330)
    w.statusBar().addPermanentWidget(w.engine_status)
    command("Help", "Getting started…", lambda: QMessageBox.information(w, "Getting started", "Open a PDF, choose duration and language, then prepare text/audio or start. Voice & speech selects the voice; Talk settings supplies audience and conference context. The main checkbox enables recording; Presentation settings configures it. Application settings selects display and sound. File → Recordings & export finds saved results. Appearance follows the system."))
    command("Help", "Keyboard shortcuts…", lambda: QMessageBox.information(w, "Keyboard shortcuts", "Ctrl+N: Open PDF · Ctrl+O: Open saved talk · Ctrl+S: Save\nCtrl+T: Talk settings (audience and preparation) · Ctrl+,: Application settings\nF5: Start / Prepare and start · Shift+F5: Start selected · F6: Continue\nCtrl+PgUp / Ctrl+PgDn: Previous / next slide in the current view\nFullscreen: Space pauses/resumes, arrows change slides, Esc returns."))
    command("Help", "About AutoTalk…", lambda: QMessageBox.about(w, "About AutoTalk", "AutoTalk 0.3\nPDF-to-talk preparation and presentation.\nCodex narration · Qwen3-TTS local speech\nPrepared, Quick and Realtime. System style and palette."))

    # Size outer controls only; the platform style owns embedded editor geometry.
    for widget in w.findChildren(QWidget):
        if isinstance(widget, (QComboBox, QLineEdit, QAbstractSpinBox)) and not isinstance(widget.parentWidget(), (QComboBox, QAbstractSpinBox)):
            widget.setMinimumHeight(32)
    for layout in w.findChildren(QFormLayout):
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

    w.workspace.currentChanged.connect(w.refresh)
