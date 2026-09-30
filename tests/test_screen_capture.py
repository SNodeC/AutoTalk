# SPDX-License-Identifier: MIT
"""Desktop audio timing and backpressure at the recording-source boundary."""
import ctypes
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from autotalk import screen_capture
from autotalk.media import RATE


@pytest.mark.parametrize('cancelled', [False, True, 'during_wait'])
def test_audio_reader_drains_ready_events_before_waiting_and_remains_cancellable(cancelled):
    source = object.__new__(screen_capture.PulseInput)
    source.loop = source.context = source.stream = 1
    source.stopping = threading.Event()
    payload = ctypes.create_string_buffer(b'\x01\x00\x02\x00')
    events, waits = [1, 1, 1, 0], []
    available = False
    if cancelled is True:
        source.stopping.set()
    if cancelled == 'during_wait':
        events.insert(0, 0)
    def dispatch(*args):
        nonlocal available
        available = bool(events.pop(0)) if events else False
        return int(available)
    def idle_wait(delay):
        waits.append(delay)
        source.stopping.set()
        return True
    source.stopping.wait = idle_wait
    def peek(stream, data, size):
        data._obj.value, size._obj.value = ctypes.addressof(payload), 4 if available else 0
        return 0
    source.library = SimpleNamespace(
        pa_mainloop_iterate=dispatch,
        pa_context_get_state=lambda *args: 4, pa_stream_get_state=lambda *args: 2,
        pa_stream_get_latency=lambda *args: 0, pa_stream_peek=peek,
        pa_stream_drop=lambda *args: 0)
    assert [source.read() for _ in range(3)] == [(payload.raw[:4], 0)] * 3
    assert source.read() is None and waits == ([] if cancelled is True else [.005])
    # Shutdown drains already available data without blocking for new audio.
    assert source.read() is None and not events


@pytest.mark.parametrize('latency', [.1, -.1])
def test_recorded_packet_uses_latency_of_first_unread_sample(tmp_path, monkeypatch, latency):
    capture = object.__new__(screen_capture.ScreenCapture)
    capture.root, capture.started = tmp_path, 10
    capture.stopping, capture.frames, capture.ready = threading.Event(), 0, False
    failures, closed = [], []
    capture.fail = failures.append
    raw = b'\x01\x00\x02\x00' * 480
    packets = iter([(raw, latency), None])
    class Source:
        def __init__(self, *args): pass
        def read(self): return next(packets)
        def close(self): closed.append(True)
    monkeypatch.setattr(screen_capture, 'PulseInput', Source)
    monkeypatch.setattr(time, 'monotonic', lambda: 11)
    capture.sound(b'@DEFAULT_MONITOR@', 'audio.pcm')
    first = round((11 - latency - capture.started) * RATE)
    assert (tmp_path / 'audio.pcm').read_bytes() == bytes(first * 4) + raw
    assert capture.frames == first + 480 and capture.ready
    assert closed == [True] and not failures


@pytest.mark.skipif(sys.platform != "linux", reason="Linux desktop capture")
@pytest.mark.parametrize("paused", [False, True])
def test_capture_failure_closes_once_on_ui_thread_and_allows_retry(qtbot, project, monkeypatch, paused):
    from PySide6.QtCore import QThread
    from PySide6.QtMultimedia import QScreenCapture
    from PySide6.QtWidgets import QMessageBox
    from autotalk.app import MainWindow
    from conftest import make_audio

    make_audio(project)
    project.record_presentation, project.recording_source = True, "screen"
    monkeypatch.setattr(QScreenCapture, "start", lambda self: None)
    errors = []
    def warning(*args):
        assert QThread.currentThread() == window.thread()
        assert window.transport.capture is None
        assert window.presentation is None
        errors.append(args[2])
    monkeypatch.setattr(QMessageBox, "warning", warning)
    window = MainWindow(); qtbot.addWidget(window); window.adopt(project)
    window.start_button.click()
    capture = window.transport.capture
    if paused:
        window.transport.pause()
    # Audio/encoder failures can arrive while narration is paused, off the UI thread.
    worker = threading.Thread(target=capture.fail, args=("Capture failed",))
    worker.start(); worker.join()
    qtbot.waitUntil(lambda: bool(errors))
    qtbot.wait(50)
    assert errors == ["Capture failed"]
    assert window.transport.state == "stopped" and not window.transport.active
    assert not window.pending_exports
    window.start_button.click()
    assert window.transport.capture is not None and window.transport.capture is not capture
    assert not window.transport.capture.error
    window.stop_presentation()
    assert window.transport.capture is None


def test_closed_capture_releases_qt_objects_without_garbage_collection(qtbot, project, monkeypatch):
    import shiboken6
    from PySide6.QtMultimedia import QScreenCapture
    monkeypatch.setattr(QScreenCapture, 'start', lambda self: None)
    capture = screen_capture.ScreenCapture(project)
    objects = (capture.session, capture.screen, capture.sink)
    capture.close()
    qtbot.waitUntil(lambda: all(not shiboken6.isValid(obj) for obj in objects), timeout=1000)
    assert capture.stopping.is_set()
