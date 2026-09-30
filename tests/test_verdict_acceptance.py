# SPDX-License-Identifier: MIT
"""Regression checks for the independent review, through the actual Qt controls."""
import threading
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QToolButton

from autotalk.app import MainWindow
from autotalk.project import Voice
from conftest import make_audio
from test_gpu_lifecycle import engine


@pytest.mark.parametrize('source', ['CustomVoice', 'Base'])
def test_conference_completion_restores_activity_without_erasing_capabilities(qtbot, project, monkeypatch, source):
    from autotalk import app
    release = threading.Event()
    project.voice = Voice(source=source)
    project.conference_url = 'https://conference.example'
    monkeypatch.setattr(app, 'extract_scope', lambda *args: (
        release.wait(5), {'scope': 'Verified conference topics', 'sources': [project.conference_url]})[1])
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    qtbot.mouseClick(next(b for b in w.overview.findChildren(QPushButton) if b.text() == 'Talk settings…'), Qt.MouseButton.LeftButton)
    dialog = w.settings[1]
    try:
        qtbot.mouseClick(w.conference_button, Qt.MouseButton.LeftButton)
        assert w.job is not None and not w.settings[1].tolerance.isEnabled()
        release.set()
        qtbot.waitUntil(lambda: w.job is None)
        assert dialog.isVisible()
        assert w.scope.toPlainText() == 'Verified conference topics'
        assert w.settings[1].tolerance.isEnabled() and w.mode.isEnabled()
        w.settings[1].tolerance.setFocus(); w.settings[1].tolerance.selectAll()
        qtbot.keyClicks(w.settings[1].tolerance, '23')
        qtbot.keyClick(w.settings[1].tolerance, Qt.Key.Key_Tab)
        assert w.project.tolerance_seconds == 23
        if directory := os.environ.get('AUTOTALK_EVIDENCE_DIR'):
            target = Path(directory); target.mkdir(parents=True, exist_ok=True)
            dialog.grab().save(str(target / f'F1-recovered-{source}.png'))
        item = dialog.navigation.findItems('Voice & language', Qt.MatchFlag.MatchExactly)[0]
        qtbot.mouseClick(dialog.navigation.viewport(), Qt.MouseButton.LeftButton,
                         pos=dialog.navigation.visualItemRect(item).center())
        assert w.settings[1].options.fields['writing_style'].isEnabled()
        assert w.settings[1].options.fields['delivery.style'].isEnabled() == (source != 'Base')
        dialog.accept()
    finally:
        release.set()
        qtbot.waitUntil(lambda: w.job is None)


def test_editor_has_one_primary_action(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    qtbot.waitExposed(w)
    assert w.slide_audio_button.isEnabled() and w.slide_audio_button.isVisible()
    assert [b for b in w.findChildren(QPushButton) if b.isVisible() and b.property('primary')] == [w.start_button]
    if directory := os.environ.get('AUTOTALK_EVIDENCE_DIR'):
        target = Path(directory); target.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(target / 'F10-editor-primary.png'))


def test_disclosure_arrows_follow_actual_pointer_interaction(qtbot, project):
    project.slides[0].notes = 'Check this statement against the conference programme.'
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert isinstance(w.notes_toggle, QToolButton)
    for expanded in (True, False):
        qtbot.mouseClick(w.notes_toggle, Qt.MouseButton.LeftButton)
        assert w.notes.isVisible() == expanded
        assert w.notes_toggle.arrowType() == (Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
    qtbot.mouseClick(w.voice_button, Qt.MouseButton.LeftButton)
    dialog = w.settings[1]
    toggle = next(b for b in dialog.findChildren(QToolButton) if b.text() == 'More vocal attributes')
    dialog.pages.currentWidget().ensureWidgetVisible(toggle)
    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)
    assert toggle.arrowType() == Qt.ArrowType.DownArrow
    assert w.settings[1].options.fields['delivery.attributes.pitch'].isVisible()
    if directory := os.environ.get('AUTOTALK_EVIDENCE_DIR'):
        target = Path(directory); target.mkdir(parents=True, exist_ok=True)
        dialog.grab().save(str(target / 'disclosure-expanded.png'))
    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)
    assert not w.settings[1].options.fields['delivery.attributes.pitch'].isVisible()
    assert toggle.arrowType() == Qt.ArrowType.RightArrow
    dialog.reject()


@pytest.mark.audio_device
def test_recording_export_queued_restart_completes_second_recording(qtbot, project, monkeypatch):
    from autotalk import app
    make_audio(project, seconds=2)
    project.record_presentation = True
    project.recording_source = 'slides'
    failures = []
    monkeypatch.setattr(MainWindow, 'error', lambda self, message: failures.append(message))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    release = threading.Event()
    export = app.export_recording
    def held_export(*args, **kwargs):
        assert release.wait(10)
        return export(*args, **kwargs)
    monkeypatch.setattr(app, 'export_recording', held_export)
    try:
        qtbot.mouseClick(w.start_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: w.transport.position > .1)
        first = w.transport.capture.root
        qtbot.keyClick(w.presentation, Qt.Key.Key_Escape)
        qtbot.mouseClick(w.end_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: w.job is not None)
        assert not w.mode.isEnabled() and w.start_button.isEnabled()
        qtbot.mouseClick(w.start_button, Qt.MouseButton.LeftButton)
        assert 'including a new recording' in w.status.text()
        assert 'saving the video' in w.status.text()
        release.set()
        qtbot.waitUntil(lambda: w.presentation is not None and w.transport.position > .1, timeout=10000)
        assert w.transport.capture.root != first
        second = w.transport.capture.root
        qtbot.keyClick(w.presentation, Qt.Key.Key_Escape)
        qtbot.mouseClick(w.end_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: w.job is None and not w.pending_exports, timeout=10000)
        assert not failures and w.after_job is None
        assert w.mode.isEnabled() and w.talk_audio_button.isEnabled()
        for recording in (first, second):
            session = json.loads((recording / 'session.json').read_text())
            assert session['status'] == 'exported'
            assert Path(session['output']).stat().st_size > 0
    finally:
        release.set()
        w.close_requested = True
        w.stop_presentation()
        qtbot.waitUntil(lambda: w.job is None, timeout=10000)


def test_subprocess_logs_and_error_details_strip_ansi():
    from autotalk import runtime
    lines = []
    script = "import sys; print('\\x1b[36mreadable message\\x1b[0m'); sys.exit(1)"
    with pytest.raises(RuntimeError, match='readable message') as error:
        runtime.run([sys.executable, '-c', script], runtime.Task(log=lines.append))
    assert lines == ['readable message']
    assert '\x1b' not in str(error.value)


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux terminal signal and process cleanup acceptance')
def test_real_sigint_runs_cleanup_and_reaps_speech_child(project, engine, tmp_path):
    from autotalk.project import Project
    project.save()
    pid_file = tmp_path / 'speech.pid'
    probe = tmp_path / 'interrupt.py'
    probe.write_text('''import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from autotalk import app, runtime
runtime.ensure_speech = lambda task: Path(sys.executable)
runtime.worker_path = lambda: Path(sys.argv[2])
window_init = app.MainWindow.__init__
def initialize(self):
    window_init(self)
    self.adopt(app.Project.load(Path(sys.argv[1])))
    def loaded():
        if self.speech.process and self.speech.state == 'ready':
            Path(sys.argv[3]).write_text(str(self.speech.process.pid))
        else:
            QTimer.singleShot(20, loaded)
    QTimer.singleShot(0, self.load_gpu)
    QTimer.singleShot(20, loaded)
app.MainWindow.__init__ = initialize
app.MainWindow.connect_chatgpt = lambda *a, **kw: None
original_main = app.argparse.ArgumentParser.parse_args
app.argparse.ArgumentParser.parse_args = lambda self: original_main(self, [])
raise SystemExit(app.main())
''')
    with (tmp_path / 'process.log').open('w') as log:
        process = subprocess.Popen([sys.executable, str(probe), str(project.manifest), str(engine), str(pid_file)],
                                   stdout=log, stderr=subprocess.STDOUT,
                                   env={**os.environ, 'XDG_CONFIG_HOME': str(tmp_path / 'config')})
        try:
            deadline = time.monotonic() + 10
            while not pid_file.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            assert pid_file.exists(), (tmp_path / 'process.log').read_text()
            child = int(pid_file.read_text())
            process.send_signal(signal.SIGINT)
            assert process.wait(timeout=10) == 0
            with pytest.raises(ProcessLookupError):
                os.kill(child, 0)
            assert Project.load(project.manifest).title == project.title
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            if pid_file.exists():
                try: os.kill(int(pid_file.read_text()), signal.SIGTERM)
                except ProcessLookupError: pass


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux PulseAudio capture')
@pytest.mark.audio_device
def test_real_monitor_read_and_cancellation_release_the_worker():
    from autotalk.screen_capture import PulseInput
    stop, received = threading.Event(), threading.Event()
    failures, packets = [], []
    def record():
        source = None
        try:
            source = PulseInput(b'@DEFAULT_MONITOR@', stop)
            while not stop.is_set():
                packet = source.read()
                if packet:
                    packets.append(packet)
                    received.set()
        except Exception as error:
            failures.append(error)
        finally:
            if source:
                source.close()
    worker = threading.Thread(target=record)
    worker.start()
    try:
        assert received.wait(5), failures
    finally:
        started = time.monotonic()
        stop.set(); worker.join(1)
    assert not worker.is_alive() and time.monotonic()-started < 1
    assert not failures and len(packets[0][0]) % 4 == 0
    assert abs(packets[0][1]) < 2


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux desktop capture')
def test_end_with_stalled_audio_source_releases_owned_workers(qtbot, project, monkeypatch):
    from autotalk import screen_capture
    from PySide6.QtGui import QImage
    from PySide6.QtMultimedia import QVideoFrame
    entered, released = threading.Event(), threading.Event()
    class SilentSource:
        def __init__(self, device, stopping): self.stopping = stopping
        def read(self): entered.set(); self.stopping.wait(5); return None
        def close(self): released.set()
    monkeypatch.setattr(screen_capture, 'PulseInput', SilentSource)
    monkeypatch.setattr(screen_capture.QScreenCapture, 'start', lambda self: None)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    capture = screen_capture.ScreenCapture(project)
    image = QImage(320, 240, QImage.Format.Format_RGB888); image.fill(Qt.GlobalColor.blue)
    capture.frame(QVideoFrame(image))
    assert entered.wait(2)
    w.transport.capture = capture
    w.transport.state = 'buffering'
    w.workspace.setCurrentWidget(w.presenter)
    w.refresh()
    started = time.monotonic()
    qtbot.mouseClick(w.end_button, Qt.MouseButton.LeftButton)
    assert time.monotonic()-started < 1
    assert released.is_set() and all(not thread.is_alive() for thread in capture.workers)
    assert w.transport.capture is None and w.transport.state == 'stopped'
    assert w.mode.isEnabled() and w.talk_audio_button.isEnabled()
    assert json.loads((capture.root / 'session.json').read_text())['status'] == 'pending'


def test_capture_finalize_failure_keeps_ownership_until_retry(qtbot, project, monkeypatch):
    from autotalk.media import Capture
    import numpy as np
    failures = []
    monkeypatch.setattr(MainWindow, 'error', lambda self, message: failures.append(message))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    capture = Capture(project)
    capture.append(np.zeros((4800, 2), dtype='<i2'), 1)
    write = Path.write_text
    def cannot_commit(path, *args, **kwargs):
        if path == capture.root / 'session.json':
            raise OSError('Recording filesystem temporarily unavailable')
        return write(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', cannot_commit)
    w.transport.capture = capture
    w.transport.state = 'paused'
    w.workspace.setCurrentWidget(w.presenter); w.refresh()
    qtbot.mouseClick(w.end_button, Qt.MouseButton.LeftButton)
    assert len(failures) == 1 and 'retry saving' in failures[0]
    assert w.transport.capture is capture and not w.mode.isEnabled()
    assert w.end_action.isEnabled() and w.end_button.isVisible()
    assert capture.audio.closed and capture.journal.closed
    monkeypatch.setattr(Path, 'write_text', write)
    w.end_action.trigger()
    qtbot.waitUntil(lambda: w.job is None and not w.pending_exports, timeout=10000)
    assert w.transport.capture is None and w.mode.isEnabled()
    info = json.loads((capture.root / 'session.json').read_text())
    assert info['status'] == 'exported' and Path(info['output']).is_file()


@pytest.mark.parametrize('size', [(940, 680), (1100, 850)])
def test_pointer_navigation_all_fixed_scopes_and_native_disclosures(qtbot, project, size):
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
    from test_ux_placement import visible_inside
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.resize(*size); w.show()
    directory = Path(os.environ['AUTOTALK_EVIDENCE_DIR']) if os.environ.get('AUTOTALK_EVIDENCE_DIR') else None
    def snapshot(widget, name):
        qtbot.wait(30)
        if directory:
            directory.mkdir(parents=True, exist_ok=True)
            widget.grab().save(str(directory / f'{size[0]}-{name}.png'))
    for mode in ('Prepared', 'Quick', 'Realtime'):
        w.mode.setFocus()
        qtbot.keyClick(w.mode, Qt.Key.Key_Home)
        for _ in range(w.mode.findText(mode)):
            qtbot.keyClick(w.mode, Qt.Key.Key_Down)
        assert w.project.mode == mode
        assert w.start_button.text() == ('Prepare and start' if mode == 'Prepared' else 'Start')
        for control in (w.start_button, w.minutes, w.language, w.voice_button, w.record):
            visible_inside(control, w)
        snapshot(w, mode)
    # Open actual native menus with the pointer, including a real submenu arrow.
    # Keep Qt action wrappers alive during inspection: PySide ties menu wrappers
    # to their action wrapper even though the native menubar owns the menu.
    held_actions = w.menuBar().actions()
    for action in held_actions:
        qtbot.mouseClick(w.menuBar(), Qt.LeftButton, pos=w.menuBar().actionGeometry(action).center())
        menu = action.menu()
        qtbot.waitUntil(menu.isVisible)
        snapshot(menu, 'menu-' + action.text())
        assert all(a.menu() is None or not a.text().endswith('…') for a in menu.actions())
        qtbot.keyClick(menu, Qt.Key.Key_Escape)
    routes = [(0, ('Settings', 'Application settings…')),
              (1, ('Talk', 'Talk settings…')),
              (2, ('Talk', 'Selected slide', 'Additional audio…'))]
    for scope, path in routes:
        container = w.menuBar()
        for caption in path:
            actions = container.actions()
            held_actions.extend(actions)
            action = next(a for a in actions if a.text() == caption)
            qtbot.mouseClick(container, Qt.LeftButton, pos=container.actionGeometry(action).center())
            if action.menu():
                container = action.menu()
                qtbot.waitUntil(container.isVisible)
        dialog = w.settings[scope]
        qtbot.waitUntil(dialog.isVisible)
        assert QApplication.activeModalWidget() is dialog
        dialog.resize(760 if size[0] == 940 else 920, 580 if size[0] == 940 else 760)
        assert not hasattr(dialog, 'scope_selector')
        for index in range(dialog.navigation.count()):
            item = dialog.navigation.item(index)
            if item.isHidden():
                continue
            qtbot.mouseClick(dialog.navigation.viewport(), Qt.LeftButton,
                             pos=dialog.navigation.visualItemRect(item).center())
            assert dialog.pages.currentIndex() == index
            assert dialog.voice_audition.isVisible() == (index == 0)
            snapshot(dialog, f'scope-{scope}-page-{index}')
            visible_inside(dialog.buttons, dialog)
            for toggle in dialog.pages.currentWidget().findChildren(QToolButton):
                if not toggle.isVisible() or not toggle.isCheckable():
                    continue
                dialog.pages.currentWidget().ensureWidgetVisible(toggle)
                qtbot.mouseClick(toggle, Qt.LeftButton)
                assert toggle.isChecked() and toggle.arrowType() == Qt.DownArrow
                qtbot.mouseClick(toggle, Qt.LeftButton)
                assert not toggle.isChecked() and toggle.arrowType() == Qt.RightArrow
        qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel), Qt.LeftButton)
        assert not dialog.isVisible()


@pytest.mark.parametrize('choice', ['Cancel', 'Close and save later', 'Finish saving and close'])
def test_recording_close_choices_use_actual_dialog_buttons(qtbot, project, choice):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from autotalk.media import Capture
    import numpy as np
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    capture = Capture(project)
    capture.append(np.zeros((4800, 2), dtype='<i2'), 1)
    w.transport.capture = capture
    selected = []
    def choose():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        try:
            control = next(b for b in dialog.buttons() if b.text().replace('&', '') == choice)
            qtbot.mouseClick(control, Qt.LeftButton)
            selected.append(choice)
        finally:
            if dialog.isVisible():
                dialog.reject()
    QTimer.singleShot(50, choose)
    w.close()
    assert selected == [choice]
    if choice == 'Cancel':
        assert w.isVisible() and w.transport.capture is capture
        w.close_requested = True
        w.close()
    qtbot.waitUntil(lambda: w.job is None and not w.isVisible(), timeout=10000)
    status = json.loads((capture.root / 'session.json').read_text())['status']
    assert status == ('exported' if choice == 'Finish saving and close' else 'pending')
    assert w.transport.capture is None
