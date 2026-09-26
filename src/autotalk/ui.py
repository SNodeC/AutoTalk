"""Desktop workspace and section dialogs; project and playback remain in the controller."""
import copy
import wave
import numpy as np
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QIcon, QDesktopServices, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QApplication, QAbstractSpinBox, QButtonGroup, QRadioButton, QComboBox, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget,
    QPlainTextEdit, QProgressBar, QPushButton, QMessageBox, QScrollArea,
    QTableWidget, QHeaderView, QAbstractItemView, QSizePolicy, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from .options import SettingsPanel
from .project import LANGUAGES, SPEAKERS

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
QListWidget#sections, QListWidget#slides { background: palette(window); border: 0; }
QListWidget#sections::item { padding: 10px 8px; }
QListWidget#slides::item { padding: 5px; border: 1px solid transparent; border-radius: 3px; }
QListWidget#slides::item:selected, QListWidget#sections::item:selected {
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
    """Edits use existing bindings, with one short-lived before-image for Cancel.

    Workers can write project artifacts. Cancel therefore restores the manifest as
    well as the controls, but never deletes explicitly saved library assets.
    """
    def __init__(self, window, title, transactional=True):
        super().__init__(window)
        self.window, self.transactional = window, transactional
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(780, 700)
        self.setMinimumSize(660, 550)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        body = QHBoxLayout()
        body.setSpacing(0)
        self.navigation = QListWidget()
        self.navigation.setObjectName("sections")
        self.navigation.setFixedWidth(158)
        self.pages = QStackedWidget()
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        body.addWidget(self.navigation)
        body.addWidget(self.pages, 1)
        outer.addLayout(body, 1)
        self.status = label("")
        self.status.setContentsMargins(12, 0, 12, 0)
        outer.addWidget(self.status)
        self.cancel_job = button("Cancel operation", lambda: window.toggle_recording() if window.recorder.source else window.cancel())
        self.cancel_job.hide()
        outer.addWidget(self.cancel_job)
        kinds = QDialogButtonBox.StandardButton
        self.buttons = QDialogButtonBox(kinds.Save | kinds.Cancel if transactional else kinds.Close)
        self.buttons.setContentsMargins(12, 0, 12, 0)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

    def add(self, title):
        page = column("paper", 22)
        page.layout().addWidget(label(title, "heading"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(page)
        self.navigation.addItem(title)
        self.pages.addWidget(scroll)
        return page

    def show_section(self, index=0):
        if not self.isVisible():
            self.before = copy.deepcopy(self.window.project) if self is self.window.talk_dialog else None
            self.selected = self.window.transport.index
            self.defaults = {key: self.window.preferences.value(key) for key in
                             ("quick_timing", "speech_priority")}
        self.navigation.setCurrentRow(index)
        self.show()
        self.window.place_settings_fields()
        self.window.refresh()
        self.raise_()

    def done(self, result):
        w = self.window
        if w.job and self is not w.preferences_dialog or w.recorder.source:
            self.status.setText("Stop the current operation or voice recording before closing.")
            return
        if w.transport.preview_path and self is not w.preferences_dialog:
            w.transport.stop()
        if self is w.preferences_dialog:
            w.speech_preferences(result == QDialog.DialogCode.Accepted)
        elif self.transactional:
            if result == QDialog.DialogCode.Accepted:
                if not w.save():
                    return
            else:
                w.transport.stop()
                for key, value in self.defaults.items():
                    w.preferences.remove(key) if value is None else w.preferences.setValue(key, value)
                if self.before is not None:
                    w.adopt(self.before)
                    w.transport.select(min(self.selected, len(w.project.slides)-1))
                    if not w.save():
                        return
        super().done(result)
        self.before = None
        w.place_settings_fields()
        w.refresh()


def build(w):
    from .app import SlideImage

    w.setStyleSheet(STYLE)
    w.actions, w.control_actions = [], []
    w.options = SettingsPanel()
    w.options.changed.connect(w.configuration_changed)
    w.talk_dialog = SectionDialog(w, "Talk settings")
    w.preferences_dialog = SectionDialog(w, "Preferences")
    w.talk_dialog.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save and return to talk")
    w.export_dialog = SectionDialog(w, "Export / recordings", transactional=False)
    w.general_form = w.talk_dialog.add("General")
    w.basics = column(margin=0)
    w.basics.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
    basics = form(w.basics)
    w.minutes = number(.1, 240, 10, w.details_changed, " min")
    w.language = combo(LANGUAGES)
    w.language.currentTextChanged.connect(w.language_selected)
    basics.addRow("Talk duration", w.minutes)
    basics.addRow("Spoken language", w.language)
    w.general_form.layout().addWidget(w.basics)
    general = form(w.general_form)
    w.talk_title = QLineEdit()
    w.talk_title.textChanged.connect(w.details_changed)
    w.tolerance = number(0, 600, 15, w.details_changed, " sec")
    w.pause = number(0, 10, .6, w.details_changed, " sec")
    w.pause.setSingleStep(.1)
    general.addRow("Talk title", w.talk_title)
    w.general_form.layout().addWidget(label("Choose duration, language and audience, then Save and return to talk. There you can write and review the text. Conference details and voice selection are optional; sign-in is guided when needed."))
    w.general_form.layout().addStretch()

    conference = w.talk_dialog.add("Conference")
    conference.layout().addWidget(label("Optional: align the talk with a conference. Enter its topics, read its website, or combine both."))
    fields = form(conference)
    for attr, title, default in (("audience", "Audience", "General conference audience"),
                                  ("objective", "Talk objective", "Explain the key ideas and takeaways"),
                                  ("url", "Conference website", "")):
        field = QLineEdit(default)
        field.textChanged.connect(w.details_changed)
        setattr(w, attr, field)
        (general if attr == "audience" else fields).addRow(title, field)
    w.url.setPlaceholderText("https://conference.example/call-for-papers")
    w.conference_button = button("Read conference website", w.read_conference)
    conference.layout().addWidget(w.conference_button)
    conference.layout().addWidget(label("Conference scope · review the website summary before use"))
    w.scope = QPlainTextEdit()
    w.scope.setPlaceholderText("Themes, tracks, typical topics, edition/year…")
    w.scope.textChanged.connect(w.details_changed)
    conference.layout().addWidget(w.scope, 1)
    w.sources = label("")
    w.sources.setOpenExternalLinks(True)
    conference.layout().addWidget(w.sources)

    voice = w.talk_dialog.add("Voice")
    w.voice_source = combo([("Choose a voice", "CustomVoice"), ("Use my own voice", "Base"), ("Design a new voice", "VoiceDesign")], w.voice_settings_changed)
    voice.layout().addWidget(w.voice_source)
    w.voice_panels = QStackedWidget()
    voice.layout().addWidget(w.voice_panels)
    predefined, personal, designed = (column(margin=0) for _ in range(3))
    for page in (predefined, personal, designed):
        w.voice_panels.addWidget(page)
    w.speaker = combo([(f"{name} — {description}", name) for name, description in SPEAKERS.items()], w.voice_settings_changed)
    form(predefined).addRow("Voice", w.speaker)
    predefined.layout().addWidget(label("All these voices can speak the selected language. Native languages indicate their strongest pronunciation. Listen before choosing; no personal recording is needed."))
    predefined.layout().addStretch()
    personal.layout().addWidget(label("1. Record or import 10–30 seconds of your voice. Recording stops after 30 seconds."))
    w.record_button = button("Record my voice", w.toggle_recording)
    personal.layout().addLayout(row(w.record_button, button("Import voice recording…", w.import_voice)))
    personal.layout().addWidget(label("2. Enter the exact words you recorded, then listen to a sample."))
    w.transcript = QPlainTextEdit()
    w.transcript.setPlaceholderText("The words in your recording help match your voice.")
    w.transcript.textChanged.connect(w.voice_changed)
    personal.layout().addWidget(w.transcript)
    w.voice_description = QLineEdit()
    w.voice_description.setPlaceholderText("For example: a warm, calm voice with clear pronunciation")
    w.voice_description.textChanged.connect(w.voice_settings_changed)
    form(designed).addRow("Describe the voice", w.voice_description)
    designed.layout().addWidget(label("Listen to a sample. When you like it, keep that voice for the whole talk."))
    designed.layout().addStretch()
    voice.layout().addWidget(label("First use downloads several GB automatically. Starting the voice engine can also take a minute on later launches. Progress and Cancel appear below while you wait."))
    w.voice_preview_button = button("Listen to a sample", w.preview_voice, True)
    voice.layout().addWidget(w.voice_preview_button)
    w.accept_voice_button = button("Use this designed voice", w.accept_designed_voice)
    voice.layout().addWidget(w.accept_voice_button)
    w.save_voice_button = button("Save reusable voice…", w.save_personal_voice)
    voice.layout().addLayout(row(button("Saved voices…", lambda: w.talk_dialog.show_section(7)), w.save_voice_button))
    voice.layout().addStretch()
    delivery = w.talk_dialog.add("Delivery")
    delivery.layout().addWidget(label("Talk-wide delivery applies to all slides. The slide inspector can supply deliberate overrides."))
    delivery.layout().addWidget(w.options.delivery_widget)
    delivery.layout().addStretch()
    presentation = w.talk_dialog.add("Presentation")
    w.screen = combo([(f"Display {i+1}: {screen.name()}", i) for i, screen in enumerate(QApplication.screens())])
    form(presentation).addRow("Fullscreen display", w.screen)
    w.audio_test_button = button("Test audio", w.test_audio)
    presentation.layout().addLayout(row(button("System audio settings…", w.system_audio_settings), w.audio_test_button))
    w.background_button = button("Add background track…", w.add_background)
    w.background_gain = number(0, 100, 15, w.background_changed, " %")
    w.background_gain.setSingleStep(5)
    w.background_loop = QCheckBox("Loop")
    w.background_loop.toggled.connect(w.background_changed)
    w.remove_background_button = button("Remove background", w.remove_background)
    presentation.layout().addWidget(w.background_button)
    presentation.layout().addLayout(row(label("Background volume"), w.background_gain, w.background_loop, w.remove_background_button))
    presentation.layout().addStretch()

    recording = w.recording_form = w.talk_dialog.add("Recording")
    recording.layout().addWidget(label("Record just the slides and speech, or share your screen to include live demos. Screen recording continues until you choose End presentation and save video. Slides-and-speech recordings finish automatically after the last slide."))
    recording.layout().addWidget(w.options.recording_widget)
    recording.layout().addStretch()

    appearance = w.preferences_dialog.add("General")
    appearance.layout().addWidget(label("Appearance follows your system", "title"))
    appearance.layout().addWidget(label("AutoTalk uses the platform widget style, fonts and light/dark palette, including Breeze on KDE Plasma. File and audio selection use system dialogs."))
    appearance.layout().addWidget(label("New talks are saved inside the autotalk folder beside the source PDF. Use File → Save a copy to choose another location. Talk-specific options are under Talk settings → Advanced."))
    appearance.layout().addStretch()
    codex = w.talk_dialog.add("Advanced")
    codex.layout().addWidget(label("These options affect this talk. The defaults work for most presentations."))
    advanced_form = form(codex)
    advanced_form.addRow("Allowed timing difference", w.tolerance)
    advanced_form.addRow("Pause between slides", w.pause)
    codex.layout().addWidget(w.options)
    for name in ("recording_policy", "export_rate", "export_bitrate"):
        taken = w.options.recording_widget.layout().takeRow(w.options.fields[name])
        advanced_form.addRow(taken.labelItem.widget(), taken.fieldItem.widget())
    w.connection = label("Sign in to ChatGPT when preparing your first talk. You can also sign in here.")
    codex.layout().addWidget(w.connection)
    w.codex_signin = button("Sign in", w.connect_chatgpt)
    w.codex_signout = button("Sign out", lambda: w.connect_chatgpt(sign_out=True))
    w.codex_signout.setToolTip("Sign out of the shared Codex account on this computer.")
    codex.layout().addLayout(row(w.codex_signin, w.codex_signout))
    codex.layout().addWidget(label("Model and reasoning for the current talk. Quick uses account defaults. Slide images, text and conference context are sent to Codex; voice references stay local."))
    w.codex_model = combo([("Account default", "")], w.model_changed)
    w.codex_effort = combo([("Codex default", "")], w.model_settings_changed)
    fields = form(codex)
    fields.addRow("Model", w.codex_model)
    fields.addRow("Reasoning effort", w.codex_effort)
    codex.layout().addWidget(w.options.synthesis_widget)
    codex.layout().addStretch()
    speech = w.preferences_dialog.add("Speech engine")
    speech.layout().addWidget(label("Current model", "title"))
    w.engine_state, w.engine_model = label("Not loaded"), label("")
    speech.layout().addWidget(w.engine_state)
    speech.layout().addWidget(w.engine_model)
    w.load_gpu_button = button("Load model now", w.load_gpu, True)
    w.unload_gpu_button = button("Unload model now", w.release_gpu)
    speech.layout().addLayout(row(w.load_gpu_button, w.unload_gpu_button))
    w.check_model_button = button("Check for model updates…", w.check_model_updates)
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
        group.buttonClicked.connect(w.update_speech_controls)
    speech.layout().addWidget(label("Loading at Start happens in the background; prepared audio can play immediately. Preparation and previews always load a needed model. Manual loading follows the same unloading policy."))
    speech.layout().addWidget(label("Presentation end excludes pauses and leaving fullscreen. Screen recording ends with End presentation. Per-operation unloading waits for the next preparation or preview; it does not undo Load now. Unloading keeps downloaded files."))
    w.engine_policy_note = label("")
    speech.layout().addWidget(w.engine_policy_note)
    speech.layout().addStretch()

    library_page = w.talk_dialog.add("Saved voices")
    library_page.layout().addWidget(label("Your reusable voices. Choose and listen here, then save the talk settings. Save a voice on the Voice page to add it here."))
    w.library_language = combo(["All languages", *LANGUAGES], w.refresh_library)
    library_page.layout().addWidget(w.library_language)
    w.voice_library = QTableWidget(0, 3)
    w.voice_library.setHorizontalHeaderLabels(["Voice", "Description", "Languages"])
    library_page.layout().addWidget(w.voice_library, 1)
    w.library_preview = button("Listen to selected voice", lambda: (w.use_saved_voice(), w.preview_voice()))
    w.library_use = button("Use selected voice", lambda: (w.use_saved_voice(), w.talk_dialog.show_section(2)))
    w.library_preview.setEnabled(False)
    w.library_use.setEnabled(False)
    w.voice_library.itemSelectionChanged.connect(lambda: [b.setEnabled(w.voice_library.currentRow() >= 0) for b in (w.library_preview, w.library_use)])
    library_page.layout().addLayout(row(w.library_preview, w.library_use, None))

    exports = w.export_dialog.add("Export / recordings")
    exports.layout().addWidget(label("Saved and unfinished recordings", "title"))
    w.recordings = QTableWidget(0, 4)
    w.recordings.setHorizontalHeaderLabels(["Talk", "Date", "Duration", "Status"])
    for table, stretch in ((w.voice_library, 1), (w.recordings, 0)):
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
    w.recordings.itemSelectionChanged.connect(w.recording_selected)
    exports.layout().addWidget(w.recordings, 1)
    w.recordings_empty = label("No recordings yet. Enable recording before presenting. You can also create a slides-only video below.")
    exports.layout().addWidget(w.recordings_empty)
    w.recover_button = button("Save selected recording…", w.recover_recording)
    exports.layout().addWidget(w.recover_button)
    w.output_button = button("Open video / audio", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(w.output_path)), True)
    w.folder_button = button("Open folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(w.output_path).parent))))
    w.output_button.setEnabled(False)
    w.folder_button.setEnabled(False)
    exports.layout().addLayout(row(w.output_button, w.folder_button))
    exports.layout().addWidget(label("Create a separate video from the prepared slides and speech. Live demos are not included."))
    w.export_button = button("Create slides-and-speech video or audio…", w.export_talk)
    exports.layout().addWidget(w.export_button)

    root = column("chrome", 0)
    root.layout().setSpacing(0)
    w.setCentralWidget(root)
    toolbar = w.toolbar = column("chrome", 10)
    toolbar.layout().setDirection(QVBoxLayout.Direction.LeftToRight)
    root.layout().addWidget(toolbar)
    menus = {name: w.menuBar().addMenu(name) for name in ("File", "Edit", "View", "Talk", "Presentation", "Settings", "Help")}

    def command(menu, title, callback, shortcut="", locked=False, control=None):
        action = QAction(title, w)
        action.triggered.connect(lambda checked=False: callback())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        menus[menu].addAction(action)
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
    toolbar.layout().addStretch()
    toolbar.layout().addWidget(label("Mode"))
    w.mode = combo(["Prepared", "Quick", "Realtime"])
    for i, explanation in enumerate(("Prepare all slides before presenting; editing is optional", "Prepare and start automatically", "Start while speech for later slides is prepared")):
        w.mode.setItemData(i, explanation, Qt.ItemDataRole.ToolTipRole)
    w.mode.currentTextChanged.connect(w.mode_changed)
    toolbar.layout().addWidget(w.mode)
    w.talk_action = command("Talk", "Talk settings…", w.talk_dialog.show_section, "Ctrl+T")
    talk_button = button("Talk settings…", w.talk_action.trigger)
    w.talk_action.changed.connect(lambda: talk_button.setEnabled(w.talk_action.isEnabled()))
    toolbar.layout().addWidget(talk_button)
    w.start_button = button("Start", w.start_mode, True)
    toolbar.layout().addWidget(w.start_button)
    summary = w.overview = column("paper", 12)
    w.title_label = label("Welcome to AutoTalk", "title")
    w.summary = label("")
    w.fit_button = button("Fit duration…", w.fit_duration)
    summary.layout().addLayout(row(w.title_label, w.summary, w.fit_button, None, button("Videos / recordings…", w.export_dialog.show_section)))
    w.mode_description = label("")
    summary.layout().addWidget(w.mode_description)
    root.layout().addWidget(summary)
    w.workspace = QStackedWidget()
    root.layout().addWidget(w.workspace, 1)

    w.editor = QSplitter()
    w.editor.setObjectName("workspace")
    w.editor.setChildrenCollapsible(False)
    navigation = column("chrome", 8)
    navigation.layout().addWidget(label("Slides", "title"))
    w.version_select = combo([], w.version_changed)
    navigation.layout().addWidget(w.version_select)
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
    center = column("paper", 15)
    w.image = SlideImage()
    center.layout().addWidget(w.image, 5)
    w.slide_info = label("Talk text · select a slide")
    center.layout().addLayout(row(w.slide_info, button("Enlarge slide…", lambda: w.enlarge_action.trigger())))
    w.narration = QPlainTextEdit()
    w.narration.setMinimumHeight(100)
    w.narration.setPlaceholderText("Write the talk text, or type what you want to say on this slide.")
    w.narration.textChanged.connect(w.narration_changed)
    center.layout().addWidget(w.narration, 2)
    w.regenerate_button = button("Create slide text", w.regenerate_slide)
    w.slide_audio_button = button("Create slide audio", w.prepare_slide, True)
    w.preview_button = button("Play audio", w.preview_slide)
    w.preview_time = label("0:00")
    w.preview_time.setWordWrap(False)
    w.waveform = Waveform()
    center.layout().addLayout(row(w.regenerate_button, w.slide_audio_button, w.preview_button, w.waveform, w.preview_time))
    inspector = column("chrome", 12)
    inspector.layout().addWidget(label("Slide settings", "title"))
    w.delivery_summary = label("Using talk delivery")
    w.slide_budget = number(0, 14400, 0, w.slide_policy_changed, " sec")
    w.slide_budget.setSpecialValueText("Automatic")
    advanced_slide = column(margin=0)
    advanced_slide.hide()
    slide_toggle = button("Advanced slide options ▸", lambda: advanced_slide.setVisible(not advanced_slide.isVisible()))
    inspector.layout().addWidget(w.delivery_summary)
    inspector.layout().addWidget(slide_toggle)
    inspector.layout().addWidget(advanced_slide)
    advanced_slide.layout().addWidget(label("Target duration for this slide"))
    advanced_slide.layout().addWidget(w.slide_budget)
    w.inherit_delivery = QCheckBox("Use talk delivery")
    w.inherit_delivery.toggled.connect(w.slide_policy_changed)
    advanced_slide.layout().addWidget(w.inherit_delivery)
    advanced_slide.layout().addWidget(label("Delivery override"))
    w.slide_directions = QLineEdit()
    w.slide_directions.setPlaceholderText("Optional directions for this slide")
    w.slide_directions.textChanged.connect(w.slide_directions_changed)
    advanced_slide.layout().addWidget(w.slide_directions)
    w.slide_after = combo([("Advance automatically", "advance"), ("Pause for live demo", "demo"), ("Wait for presenter", "pause")], w.slide_policy_changed)
    advanced_slide.layout().addWidget(label("After this slide"))
    advanced_slide.layout().addWidget(w.slide_after)
    w.slide_include = QCheckBox("Include in presentation")
    w.slide_include.toggled.connect(w.slide_policy_changed)
    inspector.layout().addWidget(w.slide_include)
    extras = QDialog(w)
    extras.setWindowTitle("Slide language and audio clips")
    extras.resize(500, 440)
    extras.setLayout(QVBoxLayout())
    advanced_slide.layout().addWidget(button("Language / audio clips…", extras.open))
    extras.layout().addWidget(label("Language passage"))
    w.passage_language = combo(LANGUAGES)
    extras.layout().addWidget(w.passage_language)
    extras.layout().addWidget(button("Insert language passage", w.insert_passage))
    extras.layout().addWidget(label("Slide audio clips", "title"))
    w.clip_select = combo([], w.show_clip)
    extras.layout().addWidget(w.clip_select)
    w.clip_gain = number(0, 2, 1, w.clip_changed)
    w.clip_gain.setSingleStep(.05)
    w.clip_placement = combo(["before", "after"])
    w.clip_placement.currentTextChanged.connect(w.clip_changed)
    fields = form(extras)
    fields.addRow("Volume", w.clip_gain)
    fields.addRow("Play", w.clip_placement)
    extras.layout().addLayout(row(button("Add…", w.add_clip), button("Remove", w.remove_clip)))
    w.notes = label("")
    advanced_slide.layout().addWidget(w.notes)
    advanced_slide.layout().addWidget(label("Changes here apply to this slide. Talk settings control the whole presentation."))
    inspector.layout().addStretch()
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
    w.authoring_widgets = [w.version_select, w.regenerate_button, w.slide_audio_button, inspector, extras]
    w.workspace.addWidget(w.editor)

    w.presenter = column("paper", 15)
    w.duration_label, w.fit_label = label("Prepare speech to measure the talk", "heading"), label("")
    w.presenter.layout().addWidget(w.duration_label)
    w.presenter.layout().addWidget(w.fit_label)
    slides = QHBoxLayout()
    current, following = column(margin=0), column(margin=0)
    current.layout().addWidget(label("Current slide", "title"))
    w.next_label = label("Up next", "title")
    following.layout().addWidget(w.next_label)
    w.play_image, w.next_image = SlideImage(), SlideImage()
    current.layout().addWidget(w.play_image, 1)
    following.layout().addWidget(w.next_image, 1)
    slides.addWidget(current, 2)
    slides.addWidget(following, 1)
    w.presenter.layout().addLayout(slides, 3)
    w.presenter_narration = QPlainTextEdit()
    w.presenter_narration.setReadOnly(True)
    w.presenter.layout().addWidget(w.presenter_narration, 1)
    w.play_time = label("Stopped · Elapsed 0:00")
    w.presenter.layout().addWidget(w.play_time)
    w.previous_button = button("Previous", lambda: w.transport.step(-1))
    w.play_button = button("Pause", w.transport.toggle, True)
    w.next_button = button("Next", lambda: w.transport.step(1))
    w.present_button = button("Start presentation", w.present, True)
    w.continue_button = button("Continue", w.continue_presentation, True)
    w.end_button = button("End presentation", w.stop_presentation)
    w.demo_button = button("Pause for a live demo", w.live_demo)
    w.presenter.layout().addLayout(row(w.present_button, w.play_button, w.continue_button, None, w.end_button))
    w.presenter.layout().addLayout(row(w.previous_button, w.next_button, None, w.demo_button))
    w.presenter.layout().addWidget(label("Esc pauses and returns here. Continue resumes at the same position. End presentation returns to editing."))
    w.workspace.addWidget(w.presenter)

    w.quick_page = w.quick_form = column("paper", 24)
    w.quick_form.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
    w.quick_summary = label("")
    w.quick_form.layout().addWidget(w.quick_summary)
    w.quick_form.layout().addWidget(label("Quick uses the default voice and no conference context. Choose the highlighted action above to begin."))
    w.quick_page.layout().addStretch()
    w.workspace.addWidget(w.quick_page)
    welcome = w.welcome = column("paper", 36)
    welcome.layout().addWidget(label("Turn your slides into a talk", "heading"))
    welcome.layout().addWidget(label("Open a PDF, choose a duration and language, then prepare or start presenting. Your projects keep narration, voices and recordings together."))
    welcome.layout().addLayout(row(button("Open PDF…", w.new_project, True), button("Open saved talk…", w.open_project), None))
    welcome.layout().addStretch()
    w.workspace.addWidget(welcome)
    w.workspace.setCurrentWidget(welcome)

    footer = w.footer = column("chrome", 10)
    root.layout().addWidget(footer)
    w.record_status = label("Recording off")
    w.record_status.linkActivated.connect(lambda target: (w.output_button if target == "video" else w.folder_button).click())
    w.record_footer = column(margin=0)
    w.record_footer.layout().setDirection(QVBoxLayout.Direction.LeftToRight)
    w.record_footer.layout().addWidget(w.options.record)
    w.record_footer.layout().addWidget(w.record_status, 1)
    footer.layout().addWidget(w.record_footer)
    w.narration_progress, w.slide_progress = QProgressBar(), QProgressBar()
    footer.layout().addLayout(row(w.narration_progress, w.slide_progress))
    w.progress = QProgressBar()
    w.progress.hide()
    footer.layout().addWidget(w.progress)
    w.status = label("Open a PDF or a saved talk to begin.")
    w.cancel_button = button("Cancel operation", w.cancel)
    w.cancel_button.hide()
    status_row = row(w.status, button("Preparation details", lambda: w.log.setVisible(not w.log.isVisible())), w.cancel_button)
    status_row.setStretch(0, 1)
    footer.layout().addLayout(status_row)
    w.log = QPlainTextEdit()
    w.log.setReadOnly(True)
    w.log.setMaximumBlockCount(500)
    w.log.setMaximumHeight(95)
    w.log.hide()
    footer.layout().addWidget(w.log)
    w.performance = label("")
    w.performance.setMaximumHeight(40)
    w.performance.hide()
    footer.layout().addWidget(w.performance)
    w.statusBar().showMessage("AutoTalk · local speech · system appearance")

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
    command("File", "Save a copy…", w.save_as, "Ctrl+Shift+S", control=w.regenerate_button)
    command("File", "Open talk folder", w.open_talk_folder, control=w.regenerate_button)
    menus["File"].addSeparator()
    command("File", "Export / recordings…", w.export_dialog.show_section)
    command("File", "Quit", w.close, "Ctrl+Q")
    for title, method, shortcut in (("Undo", "undo", "Ctrl+Z"), ("Redo", "redo", "Ctrl+Shift+Z"),
            ("Cut", "cut", "Ctrl+X"), ("Copy", "copy", "Ctrl+C"), ("Paste", "paste", "Ctrl+V"), ("Select all", "selectAll", "Ctrl+A")):
        command("Edit", title, lambda m=method: getattr(QApplication.focusWidget(), m, lambda: None)(), shortcut, control=w.regenerate_button)
    command("Edit", "Find in talk text…", w.find_narration, "Ctrl+F", control=w.regenerate_button)
    command("Edit", "Add language version…", w.add_version, control=w.regenerate_button)
    for title, pane in (("Slide navigator", navigation), ("Slide inspector", inspector_scroll)):
        action = command("View", title, lambda p=pane: p.setVisible(p.isHidden()))
        action.setCheckable(True)
        action.setChecked(True)
        menus["View"].aboutToShow.connect(lambda a=action, p=pane: a.setChecked(not p.isHidden()))
    command("View", "Restore default layout", lambda: (navigation.show(), inspector_scroll.show(), w.editor.setSizes([154, 644, 226])))
    def enlarge():
        dialog = QDialog(w)
        dialog.setWindowTitle("Slide " + str(w.transport.index+1))
        dialog.resize(1000, 720)
        dialog.setLayout(QVBoxLayout())
        image = SlideImage()
        image.show_file(w.project.image(w.project.slides[w.transport.index]))
        dialog.layout().addWidget(image)
        dialog.exec()
        dialog.deleteLater()
    w.enlarge_action = command("View", "Enlarge slide…", enlarge, control=w.image)
    command("View", "Slide editor", lambda: w.workspace.setCurrentWidget(w.editor), control=w.image)
    command("View", "Presenter view", lambda: w.workspace.setCurrentWidget(w.presenter), control=w.image)
    command("View", "Preparation details", lambda: w.log.setVisible(not w.log.isVisible()))
    command("Talk", "Saved voices…", lambda: w.talk_dialog.show_section(7), control=talk_button)
    w.start_action = command("Talk", "Start", w.start_mode, control=w.start_button)
    command("Talk", "Write or translate talk text…", w.create_narration, control=w.regenerate_button)
    w.regenerate_action = command("Talk", "Rewrite slide text…", w.regenerate_slide, control=w.regenerate_button)
    command("Talk", "Regenerate slide audio", w.prepare_slide, control=w.slide_audio_button)
    w.preview_action = command("Talk", "Play audio", w.preview_slide, control=w.preview_button)
    for mode in ("Prepared", "Quick", "Realtime"):
        command("Talk", "Mode: " + mode, lambda m=mode: w.mode.setCurrentText(m), control=w.mode)
    for title, callback, control, shortcut in (
        ("Present fullscreen", w.present, w.present_button, "F5"),
        ("Continue presentation", w.continue_presentation, w.continue_button, "F6"),
        ("Pause", w.transport.pause, w.play_button, ""),
        ("Restart from beginning", w.restart_presentation, w.present_button, "")):
        command("Presentation", title, callback, shortcut, control=control)
    command("Presentation", "Start from selected slide", lambda: w.present(selected=True), "Shift+F5", control=w.present_button)
    command("Presentation", "Live demo / leave fullscreen", w.live_demo, control=w.demo_button)
    w.previous_action = command("Presentation", "Previous slide", lambda: w.transport.step(-1), control=w.previous_button)
    w.next_action = command("Presentation", "Next slide", lambda: w.transport.step(1), control=w.next_button)
    w.end_action = command("Presentation", "End presentation", w.stop_presentation, control=w.end_button)
    command("Presentation", "System audio settings…", w.system_audio_settings)
    command("Settings", "Preferences…", w.preferences_dialog.show_section, "Ctrl+,", locked=True)
    command("Settings", "Codex model & reasoning…", lambda: w.talk_dialog.show_section(6), control=talk_button)
    w.engine_action = command("Settings", "Speech engine…", lambda: w.preferences_dialog.show_section(1))
    w.load_gpu_action = command("Settings", "Load speech model now", w.load_gpu)
    w.unload_gpu_action = command("Settings", "Unload speech model now", w.release_gpu)
    w.engine_status = button("Speech engine: Not loaded…", w.engine_action.trigger)
    w.engine_status.setMaximumWidth(330)
    w.statusBar().addPermanentWidget(w.engine_status)
    command("Help", "Getting started…", lambda: QMessageBox.information(w, "Getting started", "Open PDF creates a project inside the autotalk folder beside that PDF. Choose duration and language in Talk settings, then choose Prepare and start (Prepared) or Start (Quick/Realtime). Prepared prepares every slide before presenting; Quick starts automatically; Realtime prepares later speech while presenting. Enable recording before Start and end the presentation to save it."))
    command("Help", "Keyboard shortcuts…", lambda: QMessageBox.information(w, "Keyboard shortcuts", "Ctrl+N: New PDF · Ctrl+O: Open · Ctrl+S: Save\nCtrl+T: Talk settings · Ctrl+,: Preferences\nF5: Start · Shift+F5: Start selected · F6: Continue\nFullscreen: Space pauses/resumes, arrows change slides, Esc returns."))
    command("Help", "Diagnostics", lambda: (w.log.show(), w.log.setFocus()))
    command("Help", "About AutoTalk…", lambda: QMessageBox.about(w, "About AutoTalk", "AutoTalk 0.3\nPDF-to-talk preparation and presentation.\nCodex narration · Qwen3-TTS local speech\n\nPrepared, Quick and Realtime modes."))

    # Size outer controls only; the platform style owns embedded editor geometry.
    for widget in w.findChildren(QWidget):
        if isinstance(widget, (QComboBox, QLineEdit, QAbstractSpinBox)) and not isinstance(widget.parentWidget(), (QComboBox, QAbstractSpinBox)):
            widget.setMinimumHeight(32)
    for layout in w.findChildren(QFormLayout):
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

    w.workspace.currentChanged.connect(w.refresh)
