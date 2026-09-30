# SPDX-License-Identifier: MIT
"""Linux portal video and PulseAudio recording on one monotonic session timeline."""
import ctypes
import json
import queue
import sys
import threading
import time
from fractions import Fraction

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink

from .media import Capture, RATE


class SampleSpec(ctypes.Structure):
    _fields_ = [("format", ctypes.c_int), ("rate", ctypes.c_uint32), ("channels", ctypes.c_uint8)]


class BufferAttr(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ("maxlength", "tlength", "prebuf", "minreq", "fragsize")]


class PulseInput:
    """A worker-owned nonblocking PulseAudio connection, including cancellation."""
    def __init__(self, device, stopping):
        self.stopping = stopping
        self.library = ctypes.CDLL("libpulse.so.0")
        pointer, integer = ctypes.c_void_p, ctypes.c_int
        signatures = {
            "mainloop_new": (pointer, []), "mainloop_get_api": (pointer, [pointer]),
            "mainloop_iterate": (integer, [pointer, integer, ctypes.POINTER(integer)]),
            "mainloop_free": (None, [pointer]),
            "context_new": (pointer, [pointer, ctypes.c_char_p]),
            "context_connect": (integer, [pointer, ctypes.c_char_p, integer, pointer]),
            "context_get_state": (integer, [pointer]),
            "context_disconnect": (None, [pointer]), "context_unref": (None, [pointer]),
            "stream_new": (pointer, [pointer, ctypes.c_char_p, ctypes.POINTER(SampleSpec), pointer]),
            "stream_connect_record": (integer, [pointer, ctypes.c_char_p, ctypes.POINTER(BufferAttr), integer]),
            "stream_get_state": (integer, [pointer]),
            "stream_peek": (integer, [pointer, ctypes.POINTER(pointer), ctypes.POINTER(ctypes.c_size_t)]),
            "stream_drop": (integer, [pointer]),
            "stream_get_latency": (integer, [pointer, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(integer)]),
            "stream_disconnect": (integer, [pointer]), "stream_unref": (None, [pointer]),
        }
        for name, (result, arguments) in signatures.items():
            function = getattr(self.library, "pa_" + name)
            function.restype, function.argtypes = result, arguments
        self.loop = self.library.pa_mainloop_new()
        self.context = self.library.pa_context_new(self.library.pa_mainloop_get_api(self.loop), b"AutoTalk")
        self.stream = None
        try:
            if self.library.pa_context_connect(self.context, None, 0, None) < 0:
                raise RuntimeError("Cannot connect to the recording audio server.")
            deadline = time.monotonic() + 10
            while self.library.pa_context_get_state(self.context) != 4:
                if not self.poll(deadline):
                    return
            spec, attr = SampleSpec(3, RATE, 2), BufferAttr(*([2**32-1]*4), 3840)
            self.stream = self.library.pa_stream_new(self.context, b"Presentation recording", ctypes.byref(spec), None)
            # INTERPOLATE_TIMING | AUTO_TIMING_UPDATE: measured device latency.
            if self.library.pa_stream_connect_record(self.stream, device, ctypes.byref(attr), 0xA) < 0:
                raise RuntimeError("Cannot open the recording audio source.")
            while self.library.pa_stream_get_state(self.stream) != 2:
                if not self.poll(deadline):
                    return
        except Exception:
            self.close()
            raise

    def poll(self, deadline):
        if self.stopping.is_set():
            return False
        dispatched = self.library.pa_mainloop_iterate(self.loop, 0, None)
        if (dispatched < 0
                or self.library.pa_context_get_state(self.context) >= 5
                or self.stream and self.library.pa_stream_get_state(self.stream) >= 3):
            raise RuntimeError("Recording audio source disconnected.")
        if time.monotonic() > deadline:
            raise RuntimeError("Recording audio source stopped responding.")
        # Drain ready events without throttling the audio source behind video.
        if not dispatched:
            self.stopping.wait(.005)
        return not self.stopping.is_set()

    def read(self):
        deadline = time.monotonic() + 10
        while self.stream and (self.poll(deadline) or self.stopping.is_set()):
            if self.stopping.is_set():
                self.library.pa_mainloop_iterate(self.loop, 0, None)
            latency, negative = ctypes.c_uint64(), ctypes.c_int()
            if self.library.pa_stream_get_latency(self.stream, ctypes.byref(latency), ctypes.byref(negative)) < 0:
                if self.stopping.is_set():
                    break
                continue
            data, size = ctypes.c_void_p(), ctypes.c_size_t()
            if self.library.pa_stream_peek(self.stream, ctypes.byref(data), ctypes.byref(size)) < 0:
                raise RuntimeError("Recording audio source failed.")
            if size.value:
                raw = ctypes.string_at(data, size.value) if data else bytes(size.value)
                self.library.pa_stream_drop(self.stream)
                return raw, latency.value / 1e6 * (-1 if negative.value else 1)
            if self.stopping.is_set():
                break
        return None

    def close(self):
        if self.stream:
            self.library.pa_stream_disconnect(self.stream)
            self.library.pa_stream_unref(self.stream)
            self.stream = None
        if self.context:
            self.library.pa_context_disconnect(self.context)
            self.library.pa_context_unref(self.context)
            self.context = None
        if self.loop:
            self.library.pa_mainloop_free(self.loop)
            self.loop = None


class ScreenCapture(Capture):
    """Capture stays alive across narration pauses and live demonstrations.

    Qt owns portal permission and frame delivery. Workers own encoding and audio
    files. A bounded video queue drops late frames without changing elapsed time.
    The exporter reads these committed tracks using the same session journal.
    """
    def __init__(self, project, on_error=lambda message: None):
        if sys.platform != "linux":
            raise RuntimeError("Desktop audio recording currently requires Linux; choose slide recording on this platform.")
        Capture.__init__(self, project)
        self.audio.close()
        self.journal.close()
        self.on_error = on_error
        self.ready = False
        self.started = None
        self.error = ""
        self.stopping = threading.Event()
        self.frames_queue = queue.Queue(maxsize=3)
        self.workers = []
        self.microphone = project.capture_microphone
        self.session, self.screen, self.sink = QMediaCaptureSession(), QScreenCapture(), QVideoSink()
        self.session.setScreenCapture(self.screen)
        self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self.frame)
        self.screen.errorOccurred.connect(lambda code, message: self.fail(message))
        info = json.loads((self.root / "session.json").read_text())
        info.update(source="screen", microphone=self.microphone, policy="all")
        (self.root / "session.json").write_text(json.dumps(info, indent=2))
        QTimer.singleShot(0, lambda: self.screen.start() if not self.stopping.is_set() else None)

    def fail(self, message):
        if not self.error:
            self.error = message
            self.on_error(message)

    def frame(self, value):
        if self.stopping.is_set() or not value.isValid():
            return
        image = value.toImage().convertToFormat(QImage.Format.Format_RGB888)
        if image.isNull():
            return
        if self.started is None:
            self.started = time.monotonic()
            jobs = [(self.video, ()), (self.sound, (b"@DEFAULT_MONITOR@", "audio.pcm"))]
            if self.microphone:
                jobs.append((self.sound, (None, "microphone.pcm")))
            for target, args in jobs:
                worker = threading.Thread(target=target, args=args, daemon=True)
                self.workers.append(worker)
                worker.start()
        image = image.scaled(QSize(1920, 1080), Qt.AspectRatioMode.KeepAspectRatio)
        item = (round((time.monotonic()-self.started)*1e6), image)
        try:
            self.frames_queue.put_nowait(item)
        except queue.Full:
            pass  # Timestamps preserve the real interval; encoding stays bounded.

    def video(self):
        import av
        try:
            with av.open(str(self.root / "screen.mkv"), "w", format="matroska") as output:
                stream = None
                while not self.stopping.is_set() or not self.frames_queue.empty():
                    try:
                        pts, image = self.frames_queue.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if stream is None:
                        stream = output.add_stream("libx264", rate=30)
                        stream.width, stream.height = image.width()//2*2, image.height()//2*2
                        stream.pix_fmt = "yuv420p"
                        stream.options = {"preset": "ultrafast", "crf": "20", "tune": "zerolatency"}
                    data = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())[:, :image.width()*3].reshape(image.height(), image.width(), 3)
                    frame = av.VideoFrame.from_ndarray(data, format="rgb24")
                    frame.pts, frame.time_base = pts, Fraction(1, 1_000_000)
                    for packet in stream.encode(frame):
                        output.mux(packet)
                if stream:
                    for packet in stream.encode():
                        output.mux(packet)
        except Exception as error:
            self.fail(f"Screen encoder: {error}")

    def sound(self, device, filename):
        source = None
        try:
            source = PulseInput(device, self.stopping)
            with (self.root / filename).open("wb") as output:
                committed = 0
                while True:
                    packet = source.read()
                    if packet is None:
                        break
                    raw, latency = packet
                    at = max(0, round((time.monotonic()-latency-self.started)*RATE))
                    # Pulse latency locates the first unread sample, not the packet's end.
                    if at > committed:
                        output.write(b"\0" * ((at-committed)*4))
                    elif at < committed:
                        raw = raw[min(len(raw), (committed-at)*4):]
                    output.write(raw)
                    committed = max(at, committed) + len(raw)//4
                    output.flush()
                    if filename == "audio.pcm":
                        self.frames = committed
                        self.ready = True
        except Exception as error:
            self.fail(f"Screen audio: {error}")
        finally:
            if source:
                source.close()

    def append(self, samples, slide):
        pass  # System audio already contains AutoTalk; adding its mix would double it.

    def waiting(self, seconds, slide, fullscreen):
        pass  # The real clock and device streams continue during pauses.

    def close(self):
        self.screen.stop()
        self.stopping.set()
        for worker in self.workers:
            worker.join(timeout=3)
        if any(worker.is_alive() for worker in self.workers):
            raise RuntimeError("A recording device is not responding; the partial session is retained.")
        info = json.loads((self.root / "session.json").read_text())
        info.update(status="pending", error=self.error, duration=self.frames/RATE)
        (self.root / "session.json").write_text(json.dumps(info, indent=2))
        return self.root
