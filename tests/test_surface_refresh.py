# SPDX-License-Identifier: MIT
import inspect
import sys
from collections import Counter
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget, QComboBox, QListWidget, QTableWidget

from autotalk.app import MainWindow
from autotalk.project import Project
from conftest import make_audio


def snapshot(window):
    states = []
    for widget in [window] + window.findChildren(QWidget):
        state = {'type': type(widget).__name__}
        for attr in ('text', 'toPlainText', 'toolTip', 'isEnabled', 'isVisible', 'isChecked', 'currentIndex', 'value'):
            method = getattr(widget, attr, None)
            if callable(method):
                state[attr] = method()
        if isinstance(widget, QComboBox):
            state['items'] = [(widget.itemText(i), widget.itemData(i, Qt.ItemDataRole.ToolTipRole)) for i in range(widget.count())]
        if isinstance(widget, QListWidget):
            state['items'] = [(widget.item(i).text(), widget.item(i).toolTip()) for i in range(widget.count())]
        if isinstance(widget, QTableWidget):
            state['items'] = [(widget.item(r,c).text(), widget.item(r,c).toolTip()) if widget.item(r,c) else None
                              for r in range(widget.rowCount()) for c in range(widget.columnCount())]
        states.append(state)
    return states


def equivalent(window):
    window.flush_refresh()
    before = snapshot(window)
    window.refresh()
    assert snapshot(window) == before


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
def test_incremental_journey_matches_full_refresh(qtbot, project, monkeypatch, mode):
    make_audio(project)
    project.mode = mode
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.elapsed_timer.stop()
    equivalent(w)
    w.editor_next.click(); equivalent(w)
    w.editor_previous.click(); equivalent(w)
    w.select_slide(1); equivalent(w)
    w.inspector.slide_budget.setValue(75); equivalent(w)
    w.minutes.setValue(12); equivalent(w)
    w.record.setChecked(True); equivalent(w)
    w.mode.setCurrentText('Realtime'); equivalent(w)
    w.workspace.setCurrentWidget(w.presenter)
    w.previous_button.click(); equivalent(w)
    w.next_button.click(); equivalent(w)
    w.mode.setCurrentText(mode)
    w.view_switch.setCurrentIndex(0); equivalent(w)
    # Quick has no editor, but programmatic edits must still keep the surfaces equivalent.
    w.narration.insertPlainText(' Revised.'); equivalent(w)
    w.inspector.slide_include.setChecked(False); equivalent(w)
    w.inspector.slide_include.setChecked(True); equivalent(w)
    w.inspector.slide_after.setCurrentIndex(w.inspector.slide_after.findData('pause')); equivalent(w)
    w.inspector.inherit_pause.setChecked(False); w.inspector.slide_pause.setValue(0); equivalent(w)
    w.language.setCurrentIndex(w.language.findData('German')); equivalent(w)
    w.job = SimpleNamespace(title='Fake preparation', outcome='completed', deleteLater=lambda: None)
    w.job_started = __import__('time').monotonic()
    w.job_finished(); equivalent(w)
    # Exercise the same preview notifications without touching real output devices.
    w.transport.preview_path = project.audio(project.slides[0]); w.playback_state_changed(); equivalent(w)
    w.transport.preview_path = None; w.playback_state_changed(); equivalent(w)
    for dialog in w.settings.values():
        dialog.show_section(); equivalent(w)
        dialog.reject(); equivalent(w)


def test_keystroke_is_local_and_aggregates_coalesce(qtbot, tmp_path):
    from tools.bench_ui import prepared_project
    p = prepared_project(tmp_path/'large', 60)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(p)
    codes = {inspect.unwrap(getattr(Project, name)).__code__: name for name in ('ready', 'speech_key', 'asset')}
    counts = Counter()
    def trace(frame, event, arg):
        if event == 'call' and frame.f_code in codes:
            counts[codes[frame.f_code]] += 1
    sys.setprofile(trace)
    try:
        w.narration.insertPlainText('x')
    finally:
        sys.setprofile(None)
    assert counts['speech_key'] <= 2
    assert w.aggregate_timer.isActive() and w.aggregate_timer.interval() <= 150
    assert w.slide_audio_button.isEnabled()
    counts.clear()
    sys.setprofile(trace)
    try:
        w.flush_refresh()
    finally:
        sys.setprofile(None)
    assert counts['speech_key'] <= 60 and counts['ready'] <= 60 and counts['asset'] <= 120
    assert not w.aggregate_timer.isActive()
    equivalent(w)


@pytest.mark.parametrize('boundary', ['focus', 'save', 'refresh', 'start', 'close', 'job'])
def test_pending_aggregates_flush_at_boundaries(qtbot, project, monkeypatch, boundary):
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    w.narration.insertPlainText('x')
    assert w.aggregate_timer.isActive()
    if boundary == 'focus':
        QApplication.sendEvent(w.narration, QEvent(QEvent.Type.FocusOut))
    elif boundary == 'start':
        monkeypatch.setattr(w, 'check_source_pdf', lambda **kw: True)
        w.start_mode()
    elif boundary == 'job':
        monkeypatch.setattr('autotalk.app.Job.start', lambda self: None)
        w.start_job('Test', lambda task: None)
        w.job = None
    else:
        getattr(w, boundary)()
    assert not w.aggregate_timer.isActive()
