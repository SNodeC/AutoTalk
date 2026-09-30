# SPDX-License-Identifier: MIT
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
    ('Talk settings…', 'Talk', 1),
    ('Voice && speech…', 'Voice & language', 1),
    ('Presentation settings…', 'Audio & recording', 1),
    ('Language options…', 'Voice & language', 1),
    ('Additional audio…', 'Audio & recording', 2),
    ('Talk defaults…', 'Voice & language', 0),
    ('Preferences…', 'Display & sound', None),
    ('Account…', 'Account', None),
    ('Speech engine…', 'Speech engine', None),
])
def test_menu_shortcuts_open_the_fixed_scope_and_target(qtbot, project, caption, section, scope):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.preferences if scope is None else w.settings[scope]
    next(a for a in w.findChildren(QAction) if a.text() == caption).trigger()
    assert QApplication.activeModalWidget() is dialog
    assert dialog.navigation.currentItem().text() == section
    if scope is not None:
        assert dialog.scope == scope
    assert dialog.windowTitle() == ('Preferences' if scope is None else 'Talk defaults' if scope == 0 else
                                     f'Talk settings — {project.title}' if scope == 1 else 'Slide sound — slide 1')
    assert not hasattr(dialog, 'scope_selector')
    assert dialog.pages.currentWidget().isVisible()
    assert [dialog.navigation.item(i).text() for i in range(dialog.navigation.count()) if not dialog.navigation.item(i).isHidden()] == {
        None: ['Display & sound', 'Account', 'Speech engine'],
        0: ['Voice & language', 'Writing & delivery', 'Timing & playback', 'Audio & recording', 'AI model'],
        1: ['Talk', 'Voice & language', 'Writing & delivery', 'Timing & playback', 'Audio & recording', 'AI model'],
        2: ['Voice & language', 'Writing & delivery', 'Audio & recording'],
    }[scope]
    qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Close if scope is None else QDialogButtonBox.StandardButton.Cancel), Qt.LeftButton)


def test_buttons_and_nested_account_window_preserve_independent_transactions(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    for control, section, dialog in ((w.voice_button, 'Voice & language', w.settings[1]),
                                     (w.presentation_button, 'Audio & recording', w.settings[1]),
                                     (w.engine_status, 'Speech engine', w.preferences)):
        qtbot.mouseClick(control, Qt.LeftButton)
        assert QApplication.activeModalWidget() is dialog
        assert dialog.navigation.currentItem().text() == section
        dialog.reject()
    w.talk_action.trigger(); talk = w.settings[1]
    original, manifest = w.project.audience, project.manifest.read_bytes()
    talk.fields['audience'].editor.setText('A changed audience')
    talk.show_section('AI model')
    qtbot.mouseClick(next(b for b in talk.findChildren(QPushButton) if b.text() == 'Account settings…'), Qt.LeftButton)
    assert QApplication.activeModalWidget() is w.preferences and talk.isVisible()
    assert w.preferences.buttons.standardButtons() == QDialogButtonBox.StandardButton.Close
    w.preferences.show_section('Speech engine')
    next(b for b in w.preferences.gpu_retention.buttons() if b.property('value') == 'idle').click()
    w.preferences.reject()
    assert w.project.audience == original and talk.project.audience == 'A changed audience'
    talk.reject()
    assert w.project.audience == original and w.speech.retention == 'idle'
    assert project.manifest.read_bytes() == manifest


@pytest.mark.parametrize('save', [False, True])
def test_talk_save_cancel_applies_across_its_sections_only(qtbot, project, save):
    make_audio(project)
    original = copy.deepcopy(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[1]
    w.talk_action.trigger()
    w.settings[1].fields['audience'].editor.setText('Conference speakers')
    dialog.show_section('Voice & language')
    dialog.voice.speaker.setCurrentIndex(dialog.voice.speaker.findData('Aiden'))
    dialog.show_section('Audio & recording')
    dialog.fields['pause_seconds'].editor.setValue(2)
    dialog.fields['background_loop'].editor.setChecked(True)
    dialog.fields['background_gain'].editor.setValue(35)
    dialog.show_section('Voice & language')
    dialog.fields['language_policy'].editor.setCurrentIndex(2)
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
    d=w.preferences; d.screen.addItem('Second test display',1);d.show_section()
    d.screen.setCurrentIndex(1);d.show_section('Speech engine',focus='engine_state')
    next(b for b in d.gpu_retention.buttons() if b.property('value')=='operation').click()
    assert w.speech.retention=='operation'
    (d.accept if save else d.reject)()
    assert d.screen.currentIndex()==1 and w.speech.retention=='operation'
    assert w.config.value('presentation_display')=='Second test display'


def test_application_settings_work_without_a_talk(qtbot):
    w=MainWindow();qtbot.addWidget(w);w.show()
    d=w.settings[0];d.show_section()
    assert d.navigation.currentItem().text()=='Voice & language'
    assert d.scope==0 and not hasattr(d,'scope_selector')
    w.settings[1].show_section();w.settings[2].show_section()
    assert not w.settings[1].isVisible() and not w.settings[2].isVisible()
    d.fields['language'].editor.setCurrentText('German');d.accept()
    assert w.defaults['language']=='German'
    w.preferences.show_section('Speech engine')
    next(b for b in w.preferences.gpu_retention.buttons() if b.property('value')=='idle').click()
    w.preferences.reject();assert w.speech.retention=='idle'


def test_slide_binding_stays_pinned_and_cancel_does_not_revert_other_scopes(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    slide=w.settings[2];slide.show_section('Voice & language')
    slide.fields['language'].editor.setCurrentText('Spanish')
    w.transport.select(1)
    assert slide.slide_index==0 and slide.setting_value('language')=='Spanish'
    w.preferences.show_section('Speech engine')
    next(b for b in w.preferences.gpu_retention.buttons() if b.property('value')=='idle').click()
    w.preferences.reject();slide.reject()
    assert w.project.setting('language',w.project.slides[0])=='English'
    assert w.project.setting('language',w.project.slides[1])=='English'
    assert w.speech.retention=='idle'


@pytest.mark.parametrize('scope', [0, 1])
def test_mode_edit_updates_main_window_from_resolved_setting(qtbot, project, scope):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[scope]
    if scope == 1:
        w.mode.setCurrentText('Quick')
    dialog.show_section('Timing & playback')
    if scope == 0:
        dialog.fields['mode'].editor.setCurrentText('Quick')
    dialog.accept()
    assert w.mode.currentText() == w.project.mode == 'Quick'
    assert w.workspace.currentWidget() is w.quick_page
    assert w.start_button.text() == 'Start'


def test_cancel_after_background_work_preserves_completed_result(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    updated = copy.deepcopy(project); updated.audience = 'Newly prepared context'
    release = threading.Event()
    try:
        w.start_job('Preparing…', lambda task: (release.wait(3), updated.save(), updated)[2], w.accept_result)
        w.preferences.show_section('Speech engine')
        release.set(); qtbot.waitUntil(lambda: w.job is None)
        w.preferences.reject()
        w.settings[1].show_section('Talk')
        w.settings[1].fields['audience'].editor.setText('Unwanted later edit')
        w.settings[1].reject()
        assert w.project.audience == 'Newly prepared context'
        assert Project.load(project.manifest).audience == 'Newly prepared context'
    finally:
        release.set()
        qtbot.waitUntil(lambda: w.job is None)


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
@pytest.mark.parametrize('save', [False, True])
def test_main_duration_persists_independently_of_talk_dialog(qtbot, project, mode, save):
    project.mode = mode
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.minutes.setFocus(); w.minutes.selectAll()
    qtbot.keyClicks(w.minutes, '8.5'); qtbot.keyClick(w.minutes, Qt.Key.Key_Tab)
    w.save()
    spin = w.minutes
    spin.setFocus(); spin.selectAll()
    qtbot.keyClicks(spin, '12.5'); qtbot.keyClick(spin, Qt.Key.Key_Tab)
    assert project.target_minutes == spin.value() == 12.5
    w.save()
    w.talk_action.trigger()
    assert not hasattr(w, 'settings_minutes')
    w.settings[1].fields['audience'].editor.setText('A different audience')
    w.settings[1].show_section('Voice & language')
    w.settings[1].show_section('Talk')
    for dialog in w.settings.values():
        assert spin not in dialog.findChildren(type(spin))
    (w.settings[1].accept if save else w.settings[1].reject)()
    assert Project.load(project.manifest).target_minutes == 12.5
    assert w.project.target_minutes == w.minutes.value() == 12.5


def test_clip_controls_stay_bound_to_the_open_slide(qtbot, project):
    from autotalk.project import Clip
    make_audio(project)
    for slide in project.slides:
        slide.clips = [Clip(slide.audio_file, slide.audio_sha256, slide.duration)]
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[2]
    dialog.show_section('Audio & recording')
    w.transport.select(1)
    w.settings[2].assets.clip_gain.setFocus(); w.settings[2].assets.clip_gain.selectAll(); qtbot.keyClicks(w.settings[2].assets.clip_gain, '0.5')
    qtbot.keyClick(w.settings[2].assets.clip_gain, Qt.Key.Key_Tab)
    assert dialog.project.slides[0].clips[0].gain == .5
    assert w.project.slides[0].clips[0].gain == 1
    assert w.project.slides[1].clips[0].gain == 1
    dialog.accept()
    saved = Project.load(project.manifest)
    assert saved.slides[0].clips[0].gain == .5 and saved.slides[1].clips[0].gain == 1
