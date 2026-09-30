# SPDX-License-Identifier: MIT
"""Each scope has one value editor; moving controls preserves resolved behavior."""
import copy
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QLabel, QComboBox, QToolButton

from autotalk.app import MainWindow, clock
from autotalk.project import Project
from autotalk.media import RATE
from conftest import make_audio


def action(window, menu, text):
    actions = window.menuBar().actions()
    target = next(a for a in actions if a.text() == menu).menu()
    return next(a for a in target.actions() if a.text() == text)


def reveal_timing(w):
    next(b for b in w.editor.findChildren(QToolButton) if b.text() == 'Timing').setChecked(True)


def test_single_editor_ownership(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert not hasattr(w, 'settings_minutes')
    assert not hasattr(w, 'slide_directions') and not hasattr(w, 'inherit_delivery')
    for name, main in [('mode', w.mode), ('language', w.language), ('record_presentation', w.record)]:
        field = w.settings[1].options.fields[name]
        assert isinstance(field, QLabel) and not isinstance(main, QLabel)
        assert not isinstance(w.settings[0].options.fields[name], QLabel)
    assert isinstance(w.settings[2].settings_language, QComboBox)
    slide = w.settings[2]; slide.show_section('Presentation & recording'); qtbot.wait(10)
    assert not slide.pause.isVisible() and not slide.settings_after.isVisible()
    slide.reject()
    reveal_timing(w)
    assert w.slide_pause.isVisible() and w.inherit_pause.isVisible()
    assert not any(b.text() == 'Delivery' for b in w.editor.findChildren(QToolButton))


@pytest.mark.parametrize('name,default,override,page', [
    ('mode', 'Prepared', 'Quick', 'Talk & preparation'),
    ('language', 'English', 'German', 'Voice & language'),
    ('record_presentation', False, True, 'Presentation & recording')])
@pytest.mark.parametrize('save', [False, True])
def test_readonly_reset_save_cancel(qtbot, project, name, default, override, page, save):
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    if name == 'language':
        w.language.setCurrentText(override)
    elif name == 'mode':
        w.mode.setCurrentText(override)
    else:
        w.record.setChecked(override)
    before = copy.deepcopy(w.project)
    dialog = w.settings[1]; dialog.show_section(page)
    field = dialog.options.fields[name]
    assert 'Talk setting' in field.text()
    assert (str(override) if not isinstance(override, bool) else 'On') in field.text()
    reset = dialog.options.inheritance[name][1]
    assert reset.text() == 'Use app' and reset.isEnabled()
    reset.click()
    assert w.project.setting(name) == default
    assert 'Application default' in field.text()
    assert reset.text() == 'From app' and not reset.isEnabled()
    if name == 'language':
        assert w.project.active_version == 'main' and w.project.prepared
    (dialog.accept if save else dialog.reject)()
    loaded = Project.load(project.manifest)
    assert loaded.setting(name) == (default if save else override)
    if not save:
        assert loaded.versions == before.versions and loaded.active_version == before.active_version


@pytest.mark.parametrize('entrance', ['combo', 'menu'])
def test_language_options_focus_arrangement(qtbot, project, entrance):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    if entrance == 'combo':
        w.language.setCurrentIndex(w.language.findData('options'))
    else:
        action(w, 'Talk', 'Language options…').trigger()
    qtbot.wait(30)
    assert w.settings[1].options.fields['language_policy'].hasFocus()
    w.settings[1].reject()


@pytest.mark.parametrize('talk_override', [False, True])
def test_inspector_source_pause_and_delivery_independence(qtbot, project, talk_override):
    project.defaults['after'] = 'demo'
    if talk_override:
        project.set_setting('after', 'pause')
    project.set_setting('delivery.instructions', 'Speak softly', project.slides[0])
    w = MainWindow(); qtbot.addWidget(w); w.defaults['after'] = 'demo'; w.adopt(project); w.show(); reveal_timing(w)
    source = 'talk' if talk_override else 'app'
    assert w.slide_after.itemText(0) == f'Use {source} setting'
    assert f'From {source}: ' + ('Wait for presenter' if talk_override else 'Pause for live demo') in w.slide_after_source.text()
    assert not w.slide_pause.isEnabled()
    w.inherit_pause.setChecked(False); w.slide_pause.setValue(0)
    w.slide_after.setCurrentIndex(w.slide_after.findData('advance'))
    assert project.slides[0].overrides['delivery.instructions'] == 'Speak softly'
    w.save()
    loaded = Project.load(project.manifest); w.adopt(loaded)
    assert loaded.slides[0].overrides['pause_seconds'] == 0 and w.slide_pause.isEnabled()
    w.inherit_pause.setChecked(True); w.save()
    assert 'pause_seconds' not in Project.load(project.manifest).slides[0].overrides
    assert w.slide_pause.value() == loaded.setting('pause_seconds')
    assert not w.slide_pause.isEnabled()
    assert loaded.slides[0].overrides['delivery.instructions'] == 'Speak softly'


def test_readouts_recording_and_progress_position(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert w.summary.text() == 'Audio not ready'
    target = clock(project.target_minutes*60)
    assert w.timing_summary.text().count(target) == 1
    w.record.setChecked(True)
    assert not w.record_status.isVisible()
    capture = SimpleNamespace(frames=17*RATE, ready=True)
    w.transport.capture = capture
    try:
        w.update_timing()
        assert w.record.text() == 'Record presentation as a video'
        assert '0:17' in w.record_status.text() and w.record_status.isVisible()
        assert sum('0:17' in x.text() for x in w.findChildren(QLabel) if x.isVisible()) == 1
        capture.ready = False; w.update_timing()
        assert w.record_status.text() == 'Waiting for screen sharing…'
    finally:
        w.transport.capture = None
    w.pending_exports.append('dummy'); w.update_timing()
    assert w.record_status.text() == 'Saving video…'
    w.pending_exports.clear(); w.update_timing()
    assert not w.record_status.isVisible()
    w.progress.show(); w.place_progress()
    assert w.footer.layout().indexOf(w.progress) < w.footer.layout().indexOf(w.log)


def test_menu_focus_status_and_background(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert not w.statusBar().currentMessage()
    action(w, 'Settings', 'Account…').trigger(); qtbot.wait(30)
    assert w.codex_signin.hasFocus()
    w.settings[0].reject()
    menus = w.menuBar().actions()
    help_menu = next(a for a in menus if a.text() == 'Help').menu()
    assert 'Operation details' not in [a.text() for a in help_menu.actions()]
    assert action(w, 'View', 'Operation details')
    parent = w.background_button.parentWidget()
    assert w.remove_background_button.parentWidget() is parent
    assert w.settings[1].background_gain.isAncestorOf(parent) is False
    assert parent.isAncestorOf(w.settings[1].background_gain)
    assert w.settings[0].voice_model.text().count(w.engine_state.text()) == 0


def test_unchanged_values_preserve_text_audio_keys_and_settings(qtbot, project):
    make_audio(project)
    project.set_setting('delivery.instructions', 'Steady delivery', project.slides[0])
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    baseline = [(project.speech_key(s), project.text_ready(s), project.ready(s)) for s in project.slides]
    versions = copy.deepcopy(project.versions)
    w.minutes.setValue(project.target_minutes)
    w.mode.setCurrentText(project.mode)
    w.language.setCurrentIndex(w.language.findData(project.active_version))
    w.record.setChecked(project.record_presentation)
    w.slide_after.setCurrentIndex(w.slide_after.currentIndex())
    w.slide_pause.setValue(w.slide_pause.value())
    dialog = w.settings[2]; dialog.show_section('Voice & language')
    field = dialog.options.fields['delivery.instructions']; field.setText(field.text())
    dialog.accept()
    assert project.versions == versions
    assert [(project.speech_key(s), project.text_ready(s), project.ready(s)) for s in project.slides] == baseline
