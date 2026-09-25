"""One PCM transport owns preview, presentation timing, mixing, and capture."""

import time
import wave
import os
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtMultimedia import QtAudio, QAudioFormat, QAudioSink, QMediaDevices
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QWidget

from .media import AudioFile, Capture, RATE


class Playback(QObject):
    changed = Signal()
    state_changed = Signal()
    slide_changed = Signal(int)
    failed = Signal(str)
    finished = Signal()
    recording_ready = Signal(object)

    def __init__(self, parent=None, producer_active=lambda: False):
        super().__init__(parent)
        self.producer_active = producer_active
        if sys.platform == "linux":
            # Qt's PipeWire backend pins a node and forbids reconnects. Leave
            # destination selection and per-application restoration to the OS.
            os.environ.setdefault("PIPEWIRE_PROPS", '{ application.name = "AutoTalk" node.dont-reconnect = false node.target = null }')
        self.project = None
        self.index = 0
        self.state = "stopped"
        self.fullscreen = False
        self.preview_path = None
        self.streams = {}
        self.capture = None
        self.sink = None
        self.device = None
        self.writer = None
        self._offset = self._written = self._consumed = 0
        self._pending = deque()
        self._last_tick = time.monotonic()
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self._device_changed)
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        if getattr(self, "_state", None) != value:
            self._state = value
            self.state_changed.emit()

    @property
    def position(self):
        consumed = min(self._written, round(self.sink.processedUSecs() * RATE / 1e6)) if self.writer else 0
        return (self._offset + consumed) / RATE

    @property
    def playing(self):
        return self.state in ("playing", "buffering")

    @property
    def active(self):
        return not self.preview_path and self.state not in ("stopped", "finished")

    @property
    def elapsed(self):
        if not self.project or self.preview_path:
            return self.position
        return sum(s.duration + sum(c.seconds for c in s.clips) for s in self.project.slides[:self.index]) + self.position

    def load(self, project):
        self.stop()
        self.project = project
        self.streams.clear()
        self.preview_path = None
        self.index = 0
        self.slide_changed.emit(0)
        self.changed.emit()

    def _parts(self, index=None):
        if self.preview_path:
            audio = AudioFile(self.preview_path)
            return [audio], True
        if not self.project:
            return [], False
        slide = self.project.slides[self.index if index is None else index]
        parts = [AudioFile(self.project.asset(c.file), gain=c.gain) for c in slide.clips if c.placement == "before"]
        complete = self.project.ready(slide)
        if complete:
            parts.append(AudioFile(self.project.audio(slide)))
        else:
            stream = self.streams.get(slide.page)
            if stream and stream["key"] == self.project.speech_key(slide) and Path(stream["path"]).exists():
                parts.append(AudioFile(stream["path"], frames=stream["frames"], offset=stream["offset"]))
        if complete:
            parts.extend(AudioFile(self.project.asset(c.file), gain=c.gain) for c in slide.clips if c.placement == "after")
        return parts, complete

    @property
    def buffered_seconds(self):
        if not self.project or self.preview_path:
            return 0
        available = -self.position
        for i in range(self.index, len(self.project.slides)):
            parts, complete = self._parts(i)
            available += sum(p.frames for p in parts) / RATE
            if not complete:
                break
        return max(0, available)

    def receive_audio(self, event):
        if not self.project or event.get("version") != self.project.active_version:
            return
        page = event["page"]
        if not 1 <= page <= len(self.project.slides):
            return
        if event["key"] != self.project.speech_key(self.project.slides[page-1]):
            return
        self.streams[page] = event
        self.changed.emit()

    def _consume(self):
        if not self.writer:
            return
        consumed = min(self._written, round(self.sink.processedUSecs() * RATE / 1e6))
        count = max(0, consumed-self._consumed)
        while count and self._pending:
            samples = self._pending.popleft()
            take = min(count, len(samples))
            if self.capture:
                self.capture.append(samples[:take], self.index+1)
            if take < len(samples):
                self._pending.appendleft(samples[take:])
            count -= take
        self._consumed = consumed

    def _reset_sink(self):
        self._consume()
        position = round(self.position * RATE)
        if self.sink:
            self.sink.reset()
        self.writer = None
        self._offset = position
        self._written = self._consumed = 0
        self._pending.clear()

    def _open_sink(self):
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            raise RuntimeError("No audio output is available. Choose an output in system audio settings.")
        if not self.sink or self.device.id() != device.id():
            if self.sink:
                self.sink.deleteLater()
            fmt = QAudioFormat()
            fmt.setSampleRate(RATE)
            fmt.setChannelConfig(QAudioFormat.ChannelConfig.ChannelConfigMono)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            if not device.isFormatSupported(fmt):
                fmt = device.preferredFormat()
            if fmt.sampleFormat() not in (QAudioFormat.SampleFormat.Int16, QAudioFormat.SampleFormat.Int32,
                                           QAudioFormat.SampleFormat.Float, QAudioFormat.SampleFormat.UInt8):
                raise RuntimeError("This output's PCM format is unsupported. Choose another system output.")
            self.sink = QAudioSink(device, fmt, self)
            self.device = device
            self.sink.setBufferSize(round(fmt.sampleRate() * fmt.bytesPerFrame() * 0.1))
        self.writer = self.sink.start()
        if self.writer is None or self.sink.error() != QtAudio.Error.NoError:
            self.writer = None
            raise RuntimeError("Could not open the system audio output.")

    def _device_changed(self):
        if not self.sink:
            return
        device = QMediaDevices.defaultAudioOutput()
        if device.id() == self.device.id():
            return
        wanted = self.playing
        self._reset_sink()
        self.sink.deleteLater()
        self.sink = None
        if device.isNull():
            self.state = "paused"
            self.failed.emit("Audio output disconnected. Select an output, then Continue presentation.")
        elif wanted:
            self.state = "buffering"
        self.changed.emit()

    def _read(self, start, count):
        parts, complete = self._parts()
        values = []
        offset = start
        for part in parts:
            if offset >= part.frames:
                offset -= part.frames
                continue
            samples = part.read(offset, count)
            values.append(samples)
            count -= len(samples)
            offset = 0
            if not count:
                break
        result = np.concatenate(values) if values else np.empty(0, dtype=np.int16)
        if self.project and self.project.background and not self.preview_path and len(result):
            background = self.project.background
            asset = AudioFile(self.project.asset(background.file), gain=background.gain, loop=background.loop)
            prior = sum(s.duration + sum(c.seconds for c in s.clips) for s in self.project.slides[:self.index])
            extra = asset.read(round(prior * RATE) + start, len(result))
            if len(extra):
                mixed = result.astype(np.int32)
                mixed[:len(extra)] += extra.astype(np.int32)
                result = np.clip(mixed, -32768, 32767).astype("<i2")
        return result, sum(p.frames for p in parts), complete

    def _encode_output(self, samples):
        fmt = self.sink.format()
        if fmt.sampleRate() != RATE:
            count = round(len(samples) * fmt.sampleRate() / RATE)
            samples = np.interp(np.arange(count) * RATE / fmt.sampleRate(), np.arange(len(samples)), samples)
        samples = np.repeat(samples[:, None], fmt.channelCount(), axis=1)
        if fmt.sampleFormat() == QAudioFormat.SampleFormat.Float:
            return (samples.astype(np.float32) / 32768).tobytes()
        if fmt.sampleFormat() == QAudioFormat.SampleFormat.Int32:
            return (samples.astype(np.int32) * 65536).tobytes()
        if fmt.sampleFormat() == QAudioFormat.SampleFormat.UInt8:
            return np.clip(samples / 256 + 128, 0, 255).astype(np.uint8).tobytes()
        return samples.astype("<i2").tobytes()

    def _tick(self):
        now = time.monotonic()
        elapsed = now-self._last_tick
        self._last_tick = now
        try:
            self._consume()
            if self.capture and self.state in ("paused", "buffering"):
                self.capture.waiting(elapsed, self.index+1, self.fullscreen)
            if not self.playing:
                return
            parts, complete = self._parts()
            available = sum(p.frames for p in parts)
            if self.state == "buffering":
                current = round(self.position * RATE)
                threshold = RATE * (self.project.buffer_seconds if self.project and not self.preview_path else 0)
                if available <= current or (available-current < threshold and not complete):
                    if not self.producer_active():
                        raise RuntimeError("Preparation has stopped before this slide finished. Stop playback and prepare the remaining slides.")
                    self.changed.emit()
                    return
                self._open_sink()
                self.state = "playing"
            fmt = self.sink.format()
            while self.sink.bytesFree() >= math_chunk_bytes(fmt):
                start = self._offset+self._written
                samples, available, complete = self._read(start, 480)
                if not len(samples):
                    break
                raw = self._encode_output(samples)
                if self.writer.write(raw) != len(raw):
                    raise RuntimeError("Audio output stopped accepting data. Check system audio settings.")
                self._written += len(samples)
                self._pending.append(samples)
            # A drained sink is the boundary, never an estimated slide timer.
            if self._offset + self._consumed >= available and self.sink.state() == QtAudio.State.IdleState:
                self._reset_sink()
                if complete:
                    if self.preview_path or self.index+1 == len(self.project.slides):
                        self._finish()
                    else:
                        self.select(self.index+1, play=True)
                else:
                    self.state = "buffering"
            elif self.sink.error() not in (QtAudio.Error.NoError, QtAudio.Error.UnderrunError):
                raise RuntimeError("The audio device reported an error. Check system audio settings.")
            self.changed.emit()
        except (OSError, ValueError, RuntimeError, wave.Error) as error:
            self._reset_sink()
            self.state = "paused"
            self.failed.emit(str(error))

    def select(self, index, play=False):
        if not self.project or not 0 <= index < len(self.project.slides):
            return
        previous = self.state
        self._reset_sink()
        self.preview_path = None
        self.index = index
        self._offset = 0
        self.state = "paused" if previous not in ("stopped", "finished") else "stopped"
        self.slide_changed.emit(index)
        self.changed.emit()
        if play:
            self.play()

    def play(self):
        if not self.preview_path:
            if not self.project:
                return
            if not self.project.prepared and (self.project.mode != "Realtime" or not self.producer_active()):
                self.failed.emit("Generate current audio for every slide before presenting.")
                return
            if self.project.record_presentation and self.capture is None:
                self.capture = Capture(self.project)
        if self.writer:
            self.sink.resume()
            self.state = "playing"
        else:
            self.state = "buffering"
        self._last_tick = time.monotonic()
        self.changed.emit()

    def pause(self):
        self._consume()
        if self.writer:
            self.sink.suspend()
        self.state = "paused"
        self._last_tick = time.monotonic()
        self.changed.emit()

    def toggle(self):
        self.pause() if self.playing else self.play()

    def step(self, amount):
        self.select(self.index+amount, play=self.playing)

    def preview(self, path):
        self.stop()
        self.preview_path = Path(path)
        self.play()

    def _finalize_capture(self):
        if self.capture:
            root = self.capture.close()
            self.capture = None
            self.recording_ready.emit(root)

    def stop(self):
        self._reset_sink()
        self._finalize_capture()
        self.state = "stopped"
        self._offset = 0
        self.preview_path = None
        self.changed.emit()

    def _finish(self):
        self._finalize_capture()
        self.state = "finished"
        self.preview_path = None
        self.finished.emit()
        self.changed.emit()


def math_chunk_bytes(fmt):
    return round(480 * fmt.sampleRate() / RATE) * fmt.bytesPerFrame()

class Presentation(QWidget):
    closed = Signal()

    def __init__(self, transport, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.transport = transport
        self.setWindowTitle("AutoTalk — Presentation")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.document = QPdfDocument(self)
        self.document.load(str(transport.project.asset("slides.pdf")))
        self.rendered = None
        transport.slide_changed.connect(self.refresh)

    def refresh(self, *_):
        self.rendered = None
        self.update()

    def resizeEvent(self, event):
        self.refresh()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#06090f"))
        page = self.transport.index
        size = self.document.pagePointSize(page)
        if size.isEmpty():
            return
        ratio = min(self.width()/size.width(), self.height()/size.height())
        target = QSize(round(size.width()*ratio), round(size.height()*ratio))
        if self.rendered is None:
            self.rendered = self.document.render(page, target)
        painter.drawImage((self.width()-target.width())//2, (self.height()-target.height())//2, self.rendered)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Space:
            self.transport.toggle()
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self.transport.step(1)
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self.transport.step(-1)

    def closeEvent(self, event):
        if self.transport.playing:
            self.transport.pause()
        self.transport.fullscreen = False
        self.closed.emit()
        super().closeEvent(event)
