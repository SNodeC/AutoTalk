# SPDX-License-Identifier: MIT
import copy
import inspect
import sys
from collections import Counter
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMenu

from autotalk.app import MainWindow
from autotalk.project import Project
from autotalk.settings import ScopedSettingsDialog
from tools.bench_ui import prepared_project
from test_surface_refresh import equivalent, snapshot


def window(qtbot, tmp_path, count=6):
    p = prepared_project(tmp_path / 'talk', count)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(p); w.show()
    w.elapsed_timer.stop(); w.transport.timer.stop()
    return w


def edit(w, field):
    inspector = w.inspector
    if field == 'after':
        inspector.slide_after.setCurrentIndex(inspector.slide_after.findData('pause'))
    elif field == 'pause_seconds':
        inspector.slide_pause.setValue(1.2)
    elif field == 'budget_seconds':
        inspector.slide_budget.setValue(75)
    elif field == 'included':
        inspector.slide_include.setChecked(False)
    elif field == 'duration':
        w.minutes.setValue(12)
    elif field == 'record':
        w.record.setChecked(True)
    elif field in ('mode', 'quick'):
        w.mode.setCurrentText('Quick' if field == 'quick' else 'Realtime')


@pytest.mark.parametrize('field', ['after', 'pause_seconds', 'budget_seconds', 'included'])
def test_inspector_edits_only_owned_field(qtbot, tmp_path, field):
    w = window(qtbot, tmp_path)
    p = w.project; slide = p.slides[0]
    slide.overrides['delivery.instructions'] = 'Keep this direction'
    before = asdict(p)
    edit(w, field)
    after = asdict(p)
    first_before = before['versions']['main']['slides'][0]
    first_after = after['versions']['main']['slides'][0]
    if field in ('after', 'pause_seconds'):
        first_before['overrides'][field] = first_after['overrides'][field]
    else:
        first_before[field] = first_after[field]
    assert after == before
    assert w.isWindowModified()
    equivalent(w)


@pytest.mark.parametrize('field', ['after', 'pause_seconds', 'budget_seconds', 'included', 'duration', 'record', 'mode', 'quick'])
def test_edit_has_one_refresh_no_hidden_loads_and_two_readiness_passes(qtbot, tmp_path, field):
    w = window(qtbot, tmp_path, 60)
    codes = {inspect.unwrap(method).__code__: name for name, method in
             [('refresh', MainWindow.refresh), ('loads', ScopedSettingsDialog.load_settings),
              ('ready', Project.ready), ('changed', MainWindow.configuration_changed)]}
    counts = Counter()
    def trace(frame, event, arg):
        if event == 'call' and frame.f_code in codes:
            counts[codes[frame.f_code]] += 1
    sys.setprofile(trace)
    try:
        edit(w, field)
    finally:
        sys.setprofile(None)
    assert counts['refresh'] == 1
    assert counts['loads'] == 0
    assert counts['changed'] == 1
    assert counts['ready'] <= 120
    equivalent(w)


def test_inclusion_notice_identifies_changed_pause(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.select_slide(5)
    edit(w, 'included')
    assert 'Slide 5 audio needs updating' in w.status.text()
    assert 'trailing pause changed' in w.status.text()
    assert w.status.text() in w.log.toPlainText()
    equivalent(w)


def test_talk_pause_notice_is_capped_and_noop_is_silent(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.edit_setting('pause_seconds', 2)
    assert w.status.text() == 'Slides 1, 2, 3 and 2 more audio needs updating after this change.'
    before = w.log.toPlainText()
    w.edit_setting('pause_seconds', 2)
    assert w.log.toPlainText() == before
    w.narration.insertPlainText('x')
    assert w.log.toPlainText() == before


@pytest.mark.parametrize('state', ['stopped', 'finished', 'playing', 'paused', 'buffering', 'job'])
def test_presenter_navigation_with_stale_audio(qtbot, tmp_path, state, monkeypatch):
    w = window(qtbot, tmp_path)
    w.project.set_narration(w.project.slides[2], 'Edited')
    w.project.slides[1].included = False
    w.transport.index = 2
    w.transport._state = state if state != 'job' else 'stopped'
    if state == 'job':
        w.job = SimpleNamespace(title='Test', preserve_playback=False)
    monkeypatch.setattr(w.speech, 'load', lambda *a, **kw: pytest.fail('loaded model'), raising=False)
    w.workspace.setCurrentWidget(w.presenter)
    w.show_slide(2); w.refresh()
    allowed = state in ('stopped', 'finished')
    assert w.previous_button.isEnabled() == allowed
    assert w.next_button.isEnabled() == allowed
    if allowed:
        w.previous_button.click()
        assert w.transport.index == w.slide_list.currentRow() == 0
        assert w.transport.state == 'stopped' and w.job is None
        assert not w.previous_button.isEnabled()
        w.next_button.click()
        assert w.transport.index == 2
        w.select_slide(5)
        assert not w.next_button.isEnabled()
    w.job = None
    w.transport.stop()


@pytest.mark.parametrize('state', ['stopped', 'preview', 'job'])
def test_editor_navigation_matches_list_including_excluded(qtbot, tmp_path, state):
    w = window(qtbot, tmp_path)
    w.project.slides[1].included = False
    def prepare():
        w.job = None
        w.transport.stop(); w.select_slide(0)
        if state == 'preview':
            w.transport.preview_path = w.project.audio(w.project.slides[0])
            w.transport._state = 'playing'
        elif state == 'job':
            w.job = SimpleNamespace(title='Preparing', preserve_playback=False)
        w.refresh()
    prepare()
    assert w.editor_next.isEnabled() == w.slide_list.isEnabled()
    untouched = snapshot(w)
    w.editor_next.click()
    if state == 'job':
        current = snapshot(w)
        w.job = None
        assert current == untouched
        return
    assert w.transport.index == (0 if state == 'job' else 1)
    assert w.job is not None if state == 'job' else w.job is None
    if state != 'job':
        assert w.transport.state == 'stopped'
        assert not w.transport.preview_path
    first = snapshot(w)
    prepare()
    if w.slide_list.isEnabled():
        w.slide_list.setCurrentRow(1)
    assert snapshot(w) == first
    w.job = None; w.transport.stop()
    equivalent(w)


@pytest.mark.parametrize('focus', ['narration', 'slide_list'])
def test_navigation_shortcuts_views_and_modal_guard(qtbot, tmp_path, focus):
    w = window(qtbot, tmp_path)
    w.project.slides[1].included = False
    w.refresh(); w.raise_(); w.activateWindow()
    target = getattr(w, focus); target.setFocus()
    qtbot.waitUntil(lambda: target.hasFocus())
    QTest.keyClick(target, Qt.Key.Key_PageDown, Qt.KeyboardModifier.ControlModifier)
    assert w.transport.index == 1
    QTest.keyClick(target, Qt.Key.Key_PageUp, Qt.KeyboardModifier.ControlModifier)
    assert w.transport.index == 0
    w.workspace.setCurrentWidget(w.presenter)
    w.next_action.trigger(); assert w.transport.index == 2
    w.previous_action.trigger(); assert w.transport.index == 0
    dialog = QDialog(w); dialog.setModal(True); dialog.show()
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is dialog)
    QTest.keyClick(dialog, Qt.Key.Key_PageDown, Qt.KeyboardModifier.ControlModifier)
    w.next_action.trigger()
    assert w.transport.index == 0
    dialog.reject()
    w.mode.setCurrentText('Quick'); w.view_switch.setCurrentIndex(0)
    assert not w.next_action.isEnabled() and not w.previous_action.isEnabled()
    menus = {m.title(): m for m in w.menuBar().findChildren(QMenu)}
    for label in ('Previous slide', 'Next slide'):
        assert label in [a.text() for a in menus['View'].actions()]
        assert label not in [a.text() for a in menus['Presentation'].actions()]


def test_inspector_refresh_restores_guard_on_failure(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(w.inspector.slide_budget, 'setValue', lambda _: (_ for _ in ()).throw(RuntimeError('failed')))
        with pytest.raises(RuntimeError):
            w.inspector.refresh(w.project, w.project.slides[0])
        assert not w.inspector.loading


def test_application_default_edit_without_talk_is_not_document_edit(qtbot):
    w = MainWindow(); qtbot.addWidget(w)
    w.edit_setting('pause_seconds', 2, scope=0)
    assert w.defaults['pause_seconds'] == 2
    assert not w.isWindowModified()
    assert not w.previous_action.isEnabled() and not w.next_action.isEnabled()
