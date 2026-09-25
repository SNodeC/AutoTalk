"""Normalized local audio and recoverable presentation recording."""

import json
import math
import shutil
import uuid
import wave
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from .project import Clip, file_hash

RATE = 24000


def import_clip(project, source, task, placement="before"):
    directory = project.asset("media")
    directory.mkdir(exist_ok=True)
    temporary = directory / (uuid.uuid4().hex + ".tmp.wav")
    try:
        with av.open(str(source)) as container, wave.open(str(temporary), "wb") as output:
            if not container.streams.audio:
                raise ValueError("The selected file has no audio track.")
            output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
            frames = 0
            for frame in container.decode(audio=0):
                task.check()
                for normalized in resampler.resample(frame):
                    output.writeframes(normalized.to_ndarray().tobytes())
                    frames += normalized.samples
            for normalized in resampler.resample(None):
                output.writeframes(normalized.to_ndarray().tobytes())
                frames += normalized.samples
        if not frames:
            raise ValueError("The selected audio is empty.")
        checksum = file_hash(temporary)
        destination = directory / f"{checksum}.wav"
        temporary.replace(destination)
        return Clip(destination.relative_to(project.root).as_posix(), checksum, frames / RATE, placement)
    finally:
        temporary.unlink(missing_ok=True)


class AudioFile:
    """Read short frame ranges, keeping long talks and background tracks on disk."""
    def __init__(self, path, *, frames=None, offset=None, gain=1.0, loop=False):
        self.path = Path(path)
        self.gain = gain
        self.loop = loop
        if offset is None:
            with self.path.open("rb") as stream, wave.open(stream, "rb") as wav:
                if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, RATE):
                    raise ValueError("Playback needs normalized 24 kHz mono PCM audio.")
                self.frames = wav.getnframes()
                self.offset = stream.tell()
        else:
            self.frames, self.offset = frames, offset

    def read(self, start, count):
        if count <= 0 or self.frames <= 0:
            return np.empty(0, dtype=np.int16)
        parts = []
        with self.path.open("rb") as stream:
            while count > 0:
                if start >= self.frames:
                    if not self.loop:
                        break
                    start %= self.frames
                take = min(count, self.frames - start)
                stream.seek(self.offset + start * 2)
                raw = stream.read(take * 2)
                samples = np.frombuffer(raw, dtype="<i2").copy()
                if not samples.size:
                    break
                parts.append(samples)
                count -= samples.size
                start += samples.size
        if not parts:
            return np.empty(0, dtype=np.int16)
        result = np.concatenate(parts)
        return np.clip(result.astype(np.float32) * self.gain, -32768, 32767).astype("<i2")


class Capture:
    """The consumed audio stream is the authority for exported video frame timing."""
    def __init__(self, project):
        self.root = project.asset("recordings/" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.policy = project.recording_policy
        # Distinct sessions must never silently replace an earlier recording.
        destination = Path(project.recording_destination) if project.recording_destination else self.root / "presentation.mp4"
        if project.recording_destination:
            destination = destination.with_name(destination.stem + "-" + self.root.name[:8] + ".mp4")
        self.destination = str(destination)
        self.frames = 0
        self.last_slide = None
        self.audio = (self.root / "audio.pcm").open("wb")
        self.journal = (self.root / "events.jsonl").open("w", encoding="utf-8")
        (self.root / "session.json").write_text(json.dumps({
            "destination": self.destination, "policy": self.policy, "rate": RATE,
            "slides": len(project.slides), "export_rate": project.export_rate,
            "export_bitrate": project.export_bitrate}, indent=2), encoding="utf-8")
        # Recording remains exportable after the talk is moved or edited.
        for slide in project.slides:
            shutil.copy2(project.image(slide), self.root / f"{slide.page:04d}.png")

    def append(self, samples, slide):
        if self.audio.closed or not len(samples):
            return
        if slide != self.last_slide:
            self.journal.write(json.dumps({"frame": self.frames, "slide": slide}) + "\n")
            self.journal.flush()
            self.last_slide = slide
        self.audio.write(np.asarray(samples, dtype="<i2").tobytes())
        self.audio.flush()
        self.frames += len(samples)

    def waiting(self, seconds, slide, fullscreen):
        if self.policy == "all" or (self.policy == "fullscreen" and fullscreen):
            self.append(np.zeros(round(seconds * RATE), dtype=np.int16), slide)

    def close(self):
        if not self.audio.closed:
            self.audio.close()
            self.journal.close()
        return self.root


def export_recording(root, task, destination=None):
    """Render only committed PCM; interrupted recording/export can be retried."""
    root = Path(root)
    info = json.loads((root / "session.json").read_text(encoding="utf-8"))
    destination = Path(destination or info["destination"])
    events = []
    lines = (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            if i != len(lines)-1:
                raise ValueError("The recording journal is damaged.")
    samples = (root / "audio.pcm").stat().st_size // 2
    if not samples or not events:
        raise ValueError("This session contains no recorded presentation.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.stem + ".partial.mp4")
    frames = math.ceil(samples / RATE * 30)
    container = None
    try:
        container = av.open(str(temporary), "w", format="mp4")
        video = container.add_stream("libx264", rate=30)
        video.width, video.height, video.pix_fmt = 1920, 1080, "yuv420p"
        video.options = {"preset": "veryfast", "crf": "20"}
        audio = container.add_stream("aac", rate=info.get("export_rate", RATE))
        audio.layout = "mono"
        audio.bit_rate = info.get("export_bitrate", 128000)
        event_index, picture, last_page, audio_position = 0, None, None, 0
        with (root / "audio.pcm").open("rb") as source:
            for i in range(frames):
                task.check()
                at = i * RATE // 30
                while event_index + 1 < len(events) and events[event_index + 1]["frame"] <= at:
                    event_index += 1
                page = events[event_index]["slide"]
                if page != last_page:
                    image = QImage(str(root / f"{page:04d}.png"))
                    if image.isNull():
                        raise ValueError(f"Recorded slide {page} is missing.")
                    canvas = QImage(1920, 1080, QImage.Format.Format_RGB888)
                    canvas.fill(QColor("black"))
                    scaled = image.scaled(QSize(1920, 1080), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
                    painter = QPainter(canvas)
                    painter.drawImage((1920-scaled.width())//2, (1080-scaled.height())//2, scaled)
                    painter.end()
                    picture = np.frombuffer(canvas.bits(), dtype=np.uint8).reshape(1080, canvas.bytesPerLine())[:, :1920*3].reshape(1080, 1920, 3).copy()
                    last_page = page
                frame = av.VideoFrame.from_ndarray(picture, format="rgb24")
                frame.pts, frame.time_base = i, Fraction(1, 30)
                for packet in video.encode(frame):
                    container.mux(packet)
                # Interleave audio and video to keep muxing bounded for long talks.
                target = min(samples, (i + 1) * RATE // 30)
                if target > audio_position:
                    raw = source.read((target-audio_position)*2)
                    pcm = np.frombuffer(raw, dtype="<i2").reshape(1, -1)
                    aframe = av.AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
                    aframe.sample_rate = RATE
                    aframe.pts, aframe.time_base = audio_position, Fraction(1, RATE)
                    for packet in audio.encode(aframe):
                        container.mux(packet)
                    audio_position = target
                if i % 30 == 0:
                    task.event({"type": "progress", "stage": "Export video", "completed": i, "total": frames})
            for stream in (video, audio):
                for packet in stream.encode():
                    container.mux(packet)
        container.close()
        container = None
        temporary.replace(destination)
        task.event({"type": "progress", "stage": "Export video", "completed": frames, "total": frames})
        return destination
    finally:
        if container:
            container.close()
        temporary.unlink(missing_ok=True)
