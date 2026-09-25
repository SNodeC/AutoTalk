"""Voice recording uses Qt's microphone API and writes a portable PCM WAV."""

import wave
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


class Recorder:
    def __init__(self):
        self.source = None
        self.buffer = None
        self.format = None

    def start(self):
        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            raise RuntimeError("No microphone is available. Import a WAV recording instead.")
        fmt = QAudioFormat()
        fmt.setSampleRate(24000)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()
        if fmt.sampleFormat() not in (QAudioFormat.SampleFormat.Int16, QAudioFormat.SampleFormat.Int32,
                                      QAudioFormat.SampleFormat.Float, QAudioFormat.SampleFormat.UInt8):
            raise RuntimeError("This microphone's audio format is unsupported. Import a WAV recording instead.")
        self.format = fmt
        self.buffer = QBuffer()
        self.buffer.open(QIODevice.OpenModeFlag.ReadWrite)
        self.source = QAudioSource(device, fmt)
        self.source.start(self.buffer)

    def stop(self, path: Path):
        if not self.source:
            raise RuntimeError("Recording has not started.")
        self.source.stop()
        raw = bytes(self.buffer.data())
        fmt = self.format
        self.source = None
        if not raw:
            raise RuntimeError("No microphone audio was captured. Check microphone access and try again.")
        if fmt.sampleFormat() == QAudioFormat.SampleFormat.Float:
            import array
            values = array.array("f")
            values.frombytes(raw)
            pcm = array.array("h", [round(max(-1, min(1, v))*32767) for v in values])
            raw, width = pcm.tobytes(), 2
        else:
            width = fmt.bytesPerSample()
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as out:
            out.setnchannels(fmt.channelCount())
            out.setsampwidth(width)
            out.setframerate(fmt.sampleRate())
            out.writeframes(raw)
        return path
