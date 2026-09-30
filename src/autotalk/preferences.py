# SPDX-License-Identifier: MIT
"""Machine preferences apply immediately; no document transaction lives here.

Controller reads are limited to project, transport, recorder and codex_settings.
Operations use signals; the controller owns engine lifetime and persistence.
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QDialog, QButtonGroup, QRadioButton
from .ui import SectionDialog, label, button, row, combo, form


class PreferencesDialog(SectionDialog):
    sign_in_requested = Signal()
    sign_out_requested = Signal()
    load_requested = Signal()
    unload_requested = Signal()
    model_check_requested = Signal()
    engine_policy_changed = Signal()
    test_audio_requested = Signal()
    audio_settings_requested = Signal()

    def __init__(self, window, config):
        super().__init__(window, 'Preferences')
        self.config = config
        self.display_name = config.value('presentation_display', '')
        build_display(self); build_account(self); build_engine(self)
        self.screen.currentTextChanged.connect(lambda value: config.setValue('presentation_display', value))
        self.navigation.setCurrentRow(0)

    def done(self, result):
        QDialog.done(self, result)

    def show_section(self, section='Display & sound', focus=None):
        super().show_section(section, getattr(self, focus) if isinstance(focus,str) else focus)

    def sync(self, editable, job=None):
        super().sync(editable, job)
        self.connection.setText(self.window.codex_settings.get('account', 'Not signed in to ChatGPT.'))
        self.codex_signin.setEnabled(editable and not self.window.codex_settings.get('signed_in',False))
        self.codex_signout.setEnabled(editable and bool(self.window.codex_settings.get('signed_in')))
        self.audio_test_button.setEnabled(editable)

    def sync_engine(self, owner, config, job):
        state = owner.state
        ready = owner.matches(config) if config else False
        descriptions = {"unloaded": "Not loaded", "loading": "Loading speech model…", "ready": "Ready on GPU",
                        "generating": "Generating speech", "in_use": "Speech model in use", "unloading": "Unloading model…", "failed": "Speech engine stopped or failed"}
        consequence = {"session": "Kept until AutoTalk closes.", "presentation": "Will unload at the next presentation end.",
                       "idle": "Will unload after five idle minutes.", "operation": "Will unload after the next preparation or preview finishes."}
        status = descriptions[state]
        if state == "ready":
            status += " · " + owner.config["model"]["repo"].rsplit("/", 1)[-1]
            status += " · " + ("Unloading requested." if owner.release_requested else consequence[owner.retention])
        self.engine_state.setText(status)
        self.engine_model.setText((f"Selected slide {self.window.transport.index + 1}: " if self.window.project else "Application default: ") + config["model"]["repo"].rsplit("/", 1)[-1] if config else
                                  "Open a talk and configure its voice to select a speech model.")
        self.load_gpu_button.setText("Load selected model" if owner.process and not ready else "Load model now")
        self.load_gpu_button.setEnabled(bool(config and not job and not owner.release_requested and state not in ("loading", "generating", "unloading") and not ready))
        self.unload_gpu_button.setEnabled(bool(owner.process and not owner.guard.locked() and not owner.release_requested and state in ("ready", "failed")))
        self.check_model_button.setEnabled(bool(config and not job and not self.window.transport.active and not self.window.transport.preview_path))
        self.engine_policy_note.setText("Changes apply immediately. Automatic release follows the next safe boundary; closing Preferences does not unload the model.")
        return descriptions[state]



def build_display(w):
    presentation = w.add("Display & sound", "Display & sound")
    w.screen = combo([(f"Display {i+1}: {screen.name()}", i) for i, screen in enumerate(QApplication.screens())])
    w.screen.setCurrentIndex(max(0, w.screen.findText(w.display_name)))
    fields = form(presentation)
    fields.addRow("Fullscreen display on this computer", w.screen)
    w.audio_test_button = button("Test audio", w.test_audio_requested.emit)
    presentation.layout().addLayout(row(button("System audio settings…", w.audio_settings_requested.emit), w.audio_test_button))
    presentation.layout().addWidget(label("Display and sound choices apply immediately on this computer."))
    presentation.layout().addStretch()



def build_account(w):
    account = w.add("Account — Codex", "Account")
    w.connection = label("Not signed in to ChatGPT.")
    account.layout().addWidget(w.connection)
    w.codex_signin = button("Sign in", w.sign_in_requested.emit)
    w.codex_signout = button("Sign out", lambda: w.sign_out_requested.emit())
    account.layout().addLayout(row(w.codex_signin, w.codex_signout))
    account.layout().addWidget(label("Sign-in and sign-out act immediately on the shared Codex account on this computer. Model and reasoning use application defaults with optional talk overrides."))
    account.layout().addStretch()



def build_engine(w):
    speech = w.add("Speech engine — Qwen", "Speech engine")
    w.engine_state, w.engine_model = label("Not loaded"), label("")
    speech.layout().addWidget(w.engine_state)
    speech.layout().addWidget(w.engine_model)
    w.load_gpu_button = button("Load model now", w.load_requested.emit, True)
    w.unload_gpu_button = button("Unload model now", w.unload_requested.emit)
    speech.layout().addLayout(row(w.load_gpu_button, w.unload_gpu_button))
    w.check_model_button = button("Check for model updates…", w.model_check_requested.emit)
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
        group.buttonClicked.connect(lambda: w.engine_policy_changed.emit())
    speech.layout().addWidget(label("Prepared audio can play during background loading. Previews always load a needed model. Manual loading follows the saved release policy; leaving fullscreen is not presentation end. Unloading keeps downloaded files."))
    w.engine_policy_note = label("")
    speech.layout().addWidget(w.engine_policy_note)
    speech.layout().addStretch()
