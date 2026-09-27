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
from PySide6.QtWidgets import QToolBar, QWidget

from .media import AudioFile, Capture, Mix, RATE


class Playback(QObject):
    changed = Signal()
    state_changed = Signal()
    slide_changed = Signal(int)
    failed = Signal(str)
    finished = Signal()
    presentation_ended = Signal()
    recording_ready = Signal(object)
    demo_requested = Signal()

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
        self.mix = None
        self.preview_audio = None
        self.production_samples = deque(maxlen=32)
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
        return bool(self.capture) or not self.preview_path and self.state not in ("stopped", "finished")

    @property
    def elapsed(self):
        if not self.project or self.preview_path:
            return self.position
        return sum(self.mix.frames(i) for i in range(self.index)) / RATE + self.position

    def load(self, project):
        self.stop()
        self.project = project
        self.mix = Mix(project)
        self.production_samples.clear()
        self.preview_path = None
        self.index = 0
        self.slide_changed.emit(0)
        self.changed.emit()

    @property
    def total_seconds(self):
        return sum(self.mix.frames(i) for i in range(len(self.mix.parts))) / RATE if self.mix else 0

    @property
    def complete(self):
        return bool(self.mix and all(self.mix.complete))

    def refresh_audio(self, index=None):
        if self.project:
            if self.mix:
                self.mix.project = self.project
                self.mix.update(index)
            else:
                self.mix = Mix(self.project)

    def _parts(self, index=None):
        if self.preview_path:
            return [self.preview_audio], True
        if not self.mix:
            return [], False
        index = self.index if index is None else index
        return self.mix.parts[index], self.mix.complete[index]

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

    @property
    def required_buffer(self):
        if not self.project or self.preview_path:
            return 0
        minimum = self.project.buffer_seconds
        if self.project.speech_priority == "earliest" or len(self.production_samples) < 2:
            return minimum
        start, amount = self.production_samples[0]
        elapsed = time.monotonic() - start
        if elapsed < 1:
            return minimum
        rate = max(0, self.production_samples[-1][1]-amount) / elapsed
        remaining = max(0, self.project.target_minutes*60-self.elapsed)
        return min(max(minimum, remaining), minimum + max(0, 1-rate)*remaining)

    def receive_audio(self, event):
        if not self.project or event.get("version") != self.project.active_version:
            return
        page = event["page"]
        if not 1 <= page <= len(self.project.slides):
            return
        if event["key"] != self.project.speech_key(self.project.slides[page-1]):
            return
        self.mix.update(page-1, event)
        self.production_samples.append((time.monotonic(), self.total_seconds))
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
            fmt.setChannelConfig(QAudioFormat.ChannelConfig.ChannelConfigStereo)
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
        samples = self.preview_audio.read(start, count) if self.preview_path else self.mix.read(self.index, start, count)
        return samples, sum(p.frames for p in parts), complete

    def _encode_output(self, samples):
        fmt = self.sink.format()
        if fmt.sampleRate() != RATE:
            count = round(len(samples) * fmt.sampleRate() / RATE)
            samples = np.column_stack([np.interp(np.arange(count) * RATE / fmt.sampleRate(), np.arange(len(samples)), samples[:, c]) for c in range(2)])
        if fmt.channelCount() == 1:
            samples = samples.mean(axis=1)
        elif fmt.channelCount() > 2:
            samples = np.pad(samples, ((0, 0), (0, fmt.channelCount()-2)))
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
            if self.capture and hasattr(self.capture, "ready"):
                if self.capture.error:
                    raise RuntimeError(self.capture.error)
                if not self.capture.ready:
                    self.changed.emit()
                    return
            parts, complete = self._parts()
            available = sum(p.frames for p in parts)
            if self.state == "buffering":
                current = round(self.position * RATE)
                threshold = RATE * self.required_buffer
                if available <= current or (self.buffered_seconds*RATE < threshold and not complete):
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
                    if self.preview_path:
                        self._finish()
                    elif self.project.setting("after", self.project.slides[self.index]) != "advance":
                        self.pause()
                        if self.project.setting("after", self.project.slides[self.index]) == "demo":
                            self.demo_requested.emit()
                    else:
                        self.step(1)
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
            if not self.project.slides[self.index].included:
                following = next((s.page-1 for s in self.project.included_slides if s.page-1 > self.index), self.project.included_slides[0].page-1)
                self.select(following)
            elif self.mix.complete[self.index] and self.position > 0 and round(self.position * RATE) >= self.mix.frames(self.index):
                self.step(1, play=True)
                return
            if self.project.record_presentation and self.capture is None:
                try:
                    if self.project.recording_source == "screen":
                        from .screen_capture import ScreenCapture
                        self.capture = ScreenCapture(self.project, self.failed.emit)
                    else:
                        self.capture = Capture(self.project)
                except (OSError, RuntimeError) as error:
                    self.failed.emit(str(error))
                    return
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

    def step(self, amount, play=None):
        if not self.project:
            return
        indices = [s.page-1 for s in self.project.included_slides if (s.page-1-self.index)*amount > 0]
        if indices:
            self.select(min(indices) if amount > 0 else max(indices), play=self.playing if play is None else play)
        elif amount > 0:
            self._finish()

    def preview(self, path):
        self.stop()
        self.preview_path = Path(path)
        self.preview_audio = AudioFile(path)
        self.play()

    def _finalize_capture(self):
        if self.capture:
            try:
                root = self.capture.close()
            except (OSError, RuntimeError) as error:
                self.failed.emit(f"Recording could not finish: {error} Use End presentation to retry saving.")
                return False
            frames = self.capture.frames
            self.capture = None
            if frames:
                self.recording_ready.emit(root)
        return True

    def stop(self):
        was_presenting = self.active and not self.preview_path
        self._reset_sink()
        if not self._finalize_capture():
            self.state = "paused"
            self.changed.emit()
            return
        self._offset = 0
        self.preview_path = None
        self.preview_audio = None
        self.state = "stopped"
        self.changed.emit()
        if was_presenting:
            self.presentation_ended.emit()

    def _finish(self):
        if self.preview_path:
            self.stop()
            return
        was_presenting = self.active and not self.preview_path
        if not self.capture or not hasattr(self.capture, "ready"):
            if not self._finalize_capture():
                self.state = "paused"
                self.changed.emit()
                return
        self.state = "finished"
        self.finished.emit()
        self.changed.emit()
        if was_presenting and not self.capture:
            self.presentation_ended.emit()


def math_chunk_bytes(fmt):
    return round(480 * fmt.sampleRate() / RATE) * fmt.bytesPerFrame()

class Presentation(QWidget):
    closed = Signal()

    def __init__(self, transport, previous_action, next_action, end_action, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.transport = transport
        self.setWindowTitle("AutoTalk — Presentation")
        self.controls = QToolBar(self)
        self.controls.setAutoFillBackground(True)
        self.controls.addAction(previous_action)
        self.toggle_action = self.controls.addAction("Pause", transport.toggle)
        self.controls.addAction(next_action)
        self.controls.addAction("Pause and return to controls (Esc)", self.close)
        self.controls.addAction(end_action)
        self.document = QPdfDocument(self)
        self.document.load(str(transport.project.asset("slides.pdf")))
        self.rendered = None
        transport.slide_changed.connect(self.refresh)
        transport.state_changed.connect(self.refresh)

    def refresh(self, *_):
        self.toggle_action.setText("Pause" if self.transport.playing else "Continue")
        self.toggle_action.setEnabled(self.transport.state in ("playing", "buffering", "paused"))
        self.controls.adjustSize()
        self.controls.move(16, self.height()-self.controls.height()-6)
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
        ratio = min(self.width()/size.width(), (self.height()-55)/size.height())
        target = QSize(round(size.width()*ratio), round(size.height()*ratio))
        if self.rendered is None:
            self.rendered = self.document.render(page, target)
        painter.drawImage((self.width()-target.width())//2, (self.height()-55-target.height())//2, self.rendered)
        if self.transport.state != "playing":
            painter.fillRect(0, 0, self.width(), 48, QColor(0, 0, 0, 190))
            painter.setPen(QColor("white"))
            painter.drawText(self.rect().adjusted(16, 8, -16, -8), Qt.AlignmentFlag.AlignTop,
                             ("Slides finished — recording continues" if self.transport.capture else "Presentation finished") if self.transport.state in ("finished", "stopped") else self.transport.state.capitalize() + " • Space: continue • Esc: return")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Space and self.transport.state in ("playing", "buffering", "paused"):
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
