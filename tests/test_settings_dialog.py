"""One settings transaction, reached through every user-facing shortcut."""
import copy
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QPushButton

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
def test_menu_shortcuts_open_one_settings_dialog_at_the_target(qtbot, project, caption, section, scope):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings_dialog
    next(a for a in w.findChildren(QAction) if a.text() == caption).trigger()
    assert QApplication.activeModalWidget() is dialog
    assert dialog.navigation.currentItem().text() == section
    assert dialog.scope_selector.currentIndex() == scope
    assert dialog.pages.count() == 5
    assert [d for d in w.dialogs if d.transactional] == [dialog]
    assert dialog.pages.currentWidget().isVisible()
    dialog.reject()


def test_buttons_and_internal_links_keep_the_same_dialog_and_pending_edits(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings_dialog
    for control, section in ((w.voice_button, 'Voice & language'), (w.presentation_button, 'Presentation & recording'),
                             (w.engine_status, 'AI & speech engine')):
        qtbot.mouseClick(control, Qt.LeftButton)
        assert QApplication.activeModalWidget() is dialog
        assert dialog.navigation.currentItem().text() == section
        dialog.reject()
    w.talk_action.trigger()
    w.audience.setText('A changed audience')
    snapshot = dialog.before
    dialog.show_section("AI & speech engine", 1)
    next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Account settings…').click()
    assert dialog.navigation.currentItem().text() == "Application"
    assert QApplication.activeModalWidget() is dialog and dialog.before is snapshot
    dialog.show_section("AI & speech engine", 1)
    next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Speech engine settings…').click()
    assert dialog.navigation.currentItem().text() == "AI & speech engine"
    assert dialog.before is snapshot and w.project.audience == 'A changed audience'
    dialog.reject()
    assert w.project.audience == snapshot.audience


@pytest.mark.parametrize('save', [False, True])
def test_save_and_cancel_apply_across_all_settings_sections(qtbot, project, save):
    make_audio(project)
    original = copy.deepcopy(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.screen.addItem('Second test display', 1)
    dialog = w.settings_dialog
    w.talk_action.trigger()
    w.audience.setText('Conference speakers')
    dialog.show_section("Voice & language", 1)
    w.speaker.setCurrentIndex(w.speaker.findData('Aiden'))
    dialog.show_section("Application", 0)
    w.screen.setCurrentIndex(1)
    dialog.show_section("Presentation & recording", 1)
    w.pause.setValue(2)
    w.background_loop.setChecked(True)
    w.background_gain.setValue(35)
    dialog.show_section("Voice & language", 1)
    w.options.fields['language_policy'].setCurrentIndex(2)
    dialog.show_section("AI & speech engine", 0)
    next(b for b in w.gpu_retention.buttons() if b.property('value') == 'operation').click()
    assert w.speech.retention == 'session'
    (dialog.accept if save else dialog.reject)()
    reopened = Project.load(project.manifest)
    assert reopened.audience == ('Conference speakers' if save else original.audience)
    assert reopened.voice.speaker == ('Aiden' if save else original.voice.speaker)
    assert reopened.pause_seconds == (2 if save else original.pause_seconds)
    assert reopened.background_loop == save
    assert reopened.background_gain == (.35 if save else .15)
    assert reopened.language_policy == ('version' if save else original.language_policy)
    assert w.screen.currentIndex() == (1 if save else 0)
    assert w.speech.retention == ('operation' if save else 'session')
    if not save:
        assert reopened.prepared and w.project.prepared


def test_application_settings_work_without_a_talk(qtbot):
    w = MainWindow(); qtbot.addWidget(w); w.show()
    dialog = w.settings_dialog
    dialog.show_section()
    assert dialog.navigation.currentItem().text() == "Application"
    assert dialog.scope_selector.currentIndex() == 0
    assert not dialog.scope_selector.model().item(1).isEnabled()
    assert not dialog.scope_selector.model().item(2).isEnabled()
    dialog.show_section("AI & speech engine", 0)
    next(b for b in w.gpu_retention.buttons() if b.property('value') == 'idle').click()
    dialog.accept()
    assert w.speech.retention == 'idle' and w.project is None


def test_cancel_after_background_work_preserves_completed_result(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    updated = copy.deepcopy(project); updated.audience = 'Newly prepared context'
    release = threading.Event()
    try:
        w.start_job('Preparing…', lambda task: (release.wait(3), updated)[1], w.accept_result)
        w.settings_dialog.show_section("AI & speech engine", 0)
        assert w.settings_dialog.before is None
        release.set(); qtbot.waitUntil(lambda: w.job is None)
        w.settings_dialog.show_section("Talk & preparation", 1)
        w.audience.setText('Unwanted later edit')
        w.settings_dialog.reject()
        assert w.project.audience == 'Newly prepared context'
        assert Project.load(project.manifest).audience == 'Newly prepared context'
    finally:
        release.set()
        qtbot.waitUntil(lambda: w.job is None)


@pytest.mark.parametrize("mode", ["Prepared", "Quick", "Realtime"])
@pytest.mark.parametrize("save", [False, True])
def test_duration_is_editable_inside_settings_and_shares_talk_state(qtbot, project, mode, save):
    project.mode = mode
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.minutes.setFocus()
    w.minutes.selectAll()
    qtbot.keyClicks(w.minutes, "8.5")
    qtbot.keyClick(w.minutes, Qt.Key.Key_Tab)
    w.save()
    w.talk_action.trigger()
    spin = w.settings_minutes
    assert spin.isVisible() and spin.isEnabled() and spin.value() == 8.5
    spin.setFocus()
    spin.selectAll()
    qtbot.keyClicks(spin, '12.5')
    qtbot.keyClick(spin, Qt.Key.Key_Tab)
    assert project.target_minutes == w.minutes.value() == spin.value() == 12.5
    w.audience.setText('A different audience')
    w.settings_dialog.show_section('Voice & language', 1)
    w.settings_dialog.show_section('Talk & preparation', 1)
    assert spin.value() == project.target_minutes == 12.5
    w.settings_dialog.scope_selector.setCurrentIndex(0)
    assert not spin.isVisible()  # A talk target is not an application default.
    w.settings_dialog.scope_selector.setCurrentIndex(1)
    assert spin.isVisible() and spin.value() == 12.5
    (w.settings_dialog.accept if save else w.settings_dialog.reject)()
    expected = 12.5 if save else 8.5
    assert Project.load(project.manifest).target_minutes == expected
    assert w.project.target_minutes == w.minutes.value() == spin.value() == expected
