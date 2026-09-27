"""Fixed-scope windows share editors while keeping independent transactions."""
import copy
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QComboBox, QDialogButtonBox, QPushButton

from autotalk.app import MainWindow
from autotalk.project import Project
from conftest import make_audio


@pytest.mark.parametrize('caption, section, scope', [
    ('Talk settings…', 'Talk & preparation', 1),
    ('Voice & speech…', 'Voice & language', 1),
    ('Presentation settings…', 'Presentation & recording', 1),
    ('Language options…', 'Voice & language', 1),
    ('Additional audio…', 'Presentation & recording', 2),
    ('Application settings…', 'Application', 0),
    ('Account…', 'Application', 0),
    ('Speech engine…', 'AI & speech engine', 0),
])
def test_menu_shortcuts_open_the_fixed_scope_and_target(qtbot, project, caption, section, scope):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[scope]
    next(a for a in w.findChildren(QAction) if a.text() == caption).trigger()
    assert QApplication.activeModalWidget() is dialog
    assert dialog.navigation.currentItem().text() == section
    assert dialog.scope == scope
    assert dialog.windowTitle() == ('Application defaults' if scope == 0 else
                                     f'Talk settings — {project.title}' if scope == 1 else 'Slide settings — 1')
    assert not hasattr(dialog, 'scope_selector')
    assert dialog.pages.currentWidget().isVisible()
    assert [dialog.navigation.item(i).text() for i in range(dialog.navigation.count()) if not dialog.navigation.item(i).isHidden()] == {
        0: ['Voice & language', 'Talk & preparation', 'Presentation & recording', 'AI & speech engine', 'Application'],
        1: ['Voice & language', 'Talk & preparation', 'Presentation & recording', 'AI & speech engine'],
        2: ['Voice & language', 'Presentation & recording'],
    }[scope]
    qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel), Qt.LeftButton)


def test_buttons_and_nested_account_window_preserve_independent_transactions(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    for control, section, scope in ((w.voice_button, 'Voice & language', 1),
                                    (w.presentation_button, 'Presentation & recording', 1),
                                    (w.engine_status, 'AI & speech engine', 0)):
        qtbot.mouseClick(control, Qt.LeftButton)
        assert QApplication.activeModalWidget() is w.settings[scope]
        assert w.settings[scope].navigation.currentItem().text() == section
        w.settings[scope].reject()
    w.talk_action.trigger()
    talk = w.settings[1]
    original = w.project.audience
    w.audience.setText('A changed audience')
    talk.show_section('AI & speech engine')
    qtbot.mouseClick(next(b for b in talk.findChildren(QPushButton) if b.text() == 'Account settings…'), Qt.LeftButton)
    application = w.settings[0]
    assert QApplication.activeModalWidget() is application and talk.isVisible()
    application.show_section('Voice & language')
    application.settings_language.setCurrentText('German')
    qtbot.mouseClick(application.buttons.button(QDialogButtonBox.StandardButton.Save), Qt.LeftButton)
    assert w.defaults['language'] == 'German' and w.project.audience == 'A changed audience'
    qtbot.mouseClick(talk.buttons.button(QDialogButtonBox.StandardButton.Cancel), Qt.LeftButton)
    assert w.project.audience == original and w.defaults['language'] == 'German'
    assert Project.load(project.manifest).audience == original


@pytest.mark.parametrize('save', [False, True])
def test_talk_save_cancel_applies_across_its_sections_only(qtbot, project, save):
    make_audio(project)
    original = copy.deepcopy(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[1]
    w.talk_action.trigger()
    w.audience.setText('Conference speakers')
    dialog.show_section('Voice & language')
    dialog.speaker.setCurrentIndex(dialog.speaker.findData('Aiden'))
    dialog.show_section('Presentation & recording')
    dialog.pause.setValue(2)
    dialog.background_loop.setChecked(True)
    dialog.background_gain.setValue(35)
    dialog.show_section('Voice & language')
    dialog.options.fields['language_policy'].setCurrentIndex(2)
    qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Save if save else QDialogButtonBox.StandardButton.Cancel), Qt.LeftButton)
    reopened = Project.load(project.manifest)
    assert reopened.audience == ('Conference speakers' if save else original.audience)
    assert reopened.voice.speaker == ('Aiden' if save else original.voice.speaker)
    assert reopened.pause_seconds == (2 if save else original.pause_seconds)
    assert reopened.background_loop == save
    assert reopened.background_gain == (.35 if save else .15)
    assert reopened.language_policy == ('version' if save else original.language_policy)
    if not save:
        assert reopened.prepared and w.project.prepared


@pytest.mark.parametrize('save', [False, True])
def test_application_display_and_model_policies_are_transactional(qtbot, project, save):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.screen.addItem('Second test display', 1)
    dialog = w.settings[0]
    dialog.show_section('Application')
    w.screen.setCurrentIndex(1)
    dialog.show_section('AI & speech engine', focus=w.engine_state)
    next(b for b in w.gpu_retention.buttons() if b.property('value') == 'operation').click()
    assert w.speech.retention == 'session'
    (dialog.accept if save else dialog.reject)()
    assert w.screen.currentIndex() == (1 if save else 0)
    assert w.speech.retention == ('operation' if save else 'session')


def test_application_settings_work_without_a_talk(qtbot):
    w = MainWindow(); qtbot.addWidget(w); w.show()
    dialog = w.settings[0]
    dialog.show_section()
    assert dialog.navigation.currentItem().text() == 'Application'
    assert dialog.scope == 0 and not hasattr(dialog, 'scope_selector')
    w.settings[1].show_section(); w.settings[2].show_section()
    assert not w.settings[1].isVisible() and not w.settings[2].isVisible()
    dialog.show_section('AI & speech engine', focus=w.engine_state)
    next(b for b in w.gpu_retention.buttons() if b.property('value') == 'idle').click()
    dialog.accept()
    assert w.speech.retention == 'idle' and w.project is None


def test_slide_binding_stays_pinned_and_cancel_does_not_revert_other_scopes(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    slide = w.settings[2]
    slide.show_section('Voice & language')
    w.transport.select(1)  # A transport update must not redirect an open editor.
    slide.settings_language.setCurrentText('Spanish')
    assert project.setting('language', project.slides[0]) == 'Spanish'
    assert project.setting('language', project.slides[1]) == 'English'
    w.settings[0].show_section('Voice & language')
    w.settings[0].settings_language.setCurrentText('German')
    w.settings[0].accept()
    slide.reject()
    assert w.defaults['language'] == 'German'
    assert 'language' not in w.project.slides[0].overrides
    assert w.project.setting('language', w.project.slides[1]) == 'German'


@pytest.mark.parametrize('scope', [0, 1])
def test_mode_edit_updates_main_window_from_resolved_setting(qtbot, project, scope):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[scope]
    dialog.show_section('Talk & preparation')
    dialog.settings_mode.setCurrentText('Quick')
    dialog.accept()
    assert w.mode.currentText() == w.project.mode == 'Quick'
    assert w.workspace.currentWidget() is w.quick_page
    assert w.start_button.text() == 'Start'


def test_cancel_after_background_work_preserves_completed_result(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    updated = copy.deepcopy(project); updated.audience = 'Newly prepared context'
    release = threading.Event()
    try:
        w.start_job('Preparing…', lambda task: (release.wait(3), updated)[1], w.accept_result)
        w.settings[0].show_section('AI & speech engine')
        release.set(); qtbot.waitUntil(lambda: w.job is None)
        w.settings[0].reject()
        w.settings[1].show_section('Talk & preparation')
        w.audience.setText('Unwanted later edit')
        w.settings[1].reject()
        assert w.project.audience == 'Newly prepared context'
        assert Project.load(project.manifest).audience == 'Newly prepared context'
    finally:
        release.set()
        qtbot.waitUntil(lambda: w.job is None)


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
@pytest.mark.parametrize('save', [False, True])
def test_duration_is_editable_inside_talk_settings_and_shares_talk_state(qtbot, project, mode, save):
    project.mode = mode
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.minutes.setFocus(); w.minutes.selectAll()
    qtbot.keyClicks(w.minutes, '8.5'); qtbot.keyClick(w.minutes, Qt.Key.Key_Tab)
    w.save()
    w.talk_action.trigger()
    spin = w.settings_minutes
    assert spin.isVisible() and spin.isEnabled() and spin.value() == 8.5
    spin.setFocus(); spin.selectAll()
    qtbot.keyClicks(spin, '12.5'); qtbot.keyClick(spin, Qt.Key.Key_Tab)
    assert project.target_minutes == w.minutes.value() == spin.value() == 12.5
    w.audience.setText('A different audience')
    w.settings[1].show_section('Voice & language')
    w.settings[1].show_section('Talk & preparation')
    assert spin.isVisible() and spin.value() == project.target_minutes == 12.5
    assert spin not in w.settings[0].findChildren(type(spin))
    assert spin not in w.settings[2].findChildren(type(spin))
    (w.settings[1].accept if save else w.settings[1].reject)()
    expected = 12.5 if save else 8.5
    assert Project.load(project.manifest).target_minutes == expected
    assert w.project.target_minutes == w.minutes.value() == spin.value() == expected


def test_clip_controls_stay_bound_to_the_open_slide(qtbot, project):
    from autotalk.project import Clip
    make_audio(project)
    for slide in project.slides:
        slide.clips = [Clip(slide.audio_file, slide.audio_sha256, slide.duration)]
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[2]
    dialog.show_section('Presentation & recording')
    w.transport.select(1)
    w.clip_gain.setFocus(); w.clip_gain.selectAll(); qtbot.keyClicks(w.clip_gain, '0.5')
    qtbot.keyClick(w.clip_gain, Qt.Key.Key_Tab)
    assert w.project.slides[0].clips[0].gain == .5
    assert w.project.slides[1].clips[0].gain == 1
    dialog.accept()
    saved = Project.load(project.manifest)
    assert saved.slides[0].clips[0].gain == .5 and saved.slides[1].clips[0].gain == 1
