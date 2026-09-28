"""Desktop audio timing and backpressure at the recording-source boundary."""
import ctypes
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
