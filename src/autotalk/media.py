"""Normalized local audio and recoverable presentation recording."""

import json
import math
import shutil
import time
import uuid
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtPdf import QPdfDocument
from shiboken6 import delete

from .project import Clip, file_hash

RATE = 48000


def import_clip(project, source, task, placement="before"):
    import av
    directory = project.asset("media")
    directory.mkdir(exist_ok=True)
    temporary = directory / (uuid.uuid4().hex + ".tmp.wav")
    try:
        with av.open(str(source)) as container, wave.open(str(temporary), "wb") as output:
            if not container.streams.audio:
                raise ValueError("The selected file has no audio track.")
            output.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
            resampler = av.AudioResampler(format="s16", layout="stereo", rate=RATE)
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
    """One open asset; reads use absolute 48 kHz stereo frame coordinates."""
    def __init__(self, path, *, frames=None, offset=None, gain=1.0, loop=False):
        self.path, self.gain, self.loop = Path(path), gain, loop
        self.stream = self.path.open("rb")
        if offset is None:
            with wave.open(self.stream, "rb") as wav:
                self.source_rate, self.channels = wav.getframerate(), wav.getnchannels()
                if wav.getsampwidth() != 2 or self.channels not in (1, 2):
                    raise ValueError("Audio assets must be mono or stereo PCM16 WAV.")
                self.source_frames, self.offset = wav.getnframes(), self.stream.tell()
        else:
            self.source_frames, self.offset, self.source_rate, self.channels = frames, offset, 24000, 1
        self.frames = round(self.source_frames * RATE / self.source_rate)

    def __del__(self):
        if hasattr(self, "stream"):
            self.stream.close()

    def read(self, start, count):
        if count <= 0 or self.frames <= 0:
            return np.empty((0, 2), dtype=np.int16)
        parts = []
        while count > 0:
            if start >= self.frames:
                if not self.loop:
                    break
                start %= self.frames
            take = min(count, self.frames-start)
            positions = np.arange(start, start+take) * self.source_rate / RATE
            first, last = int(positions[0]), min(self.source_frames, int(positions[-1])+2)
            self.stream.seek(self.offset + first*self.channels*2)
            raw = np.frombuffer(self.stream.read((last-first)*self.channels*2), dtype="<i2").reshape(-1, self.channels)
            if not len(raw):
                break
            # Absolute positions plus a lookahead sample preserve interpolation
            # across read boundaries and seeks (no per-chunk resampler reset).
            samples = np.column_stack([np.interp(positions-first, np.arange(len(raw)), raw[:, c]) for c in range(self.channels)])
            if self.channels == 1:
                samples = np.repeat(samples, 2, axis=1)
            parts.append(samples)
            start += take
            count -= take
        if not parts:
            return np.empty((0, 2), dtype=np.int16)
        return np.clip(np.concatenate(parts)*self.gain, -32768, 32767).astype("<i2")


class Mix:
    """The shared prepared/live timeline used by playback and offline export."""
    def __init__(self, project):
        self.project = project
        self.parts = [[] for _ in project.slides]
        self.complete = [False for _ in project.slides]
        self.background = None
        self.update()

    def update(self, index=None, event=None):
        p = self.project
        if index is None:
            self.background = AudioFile(p.asset(p.background.file), gain=p.background_gain, loop=p.background_loop) if p.background else None
        for i in range(len(p.slides)) if index is None else [index]:
            slide = p.slides[i]
            if not slide.included:
                self.parts[i], self.complete[i] = [], True
                continue
            ready = p.ready(slide)
            parts = [AudioFile(p.asset(c.file), gain=c.gain) for c in slide.clips if c.placement == "before"]
            if ready:
                parts.append(AudioFile(p.audio(slide)))
            elif event and slide.text_ready and event["key"] == p.speech_key(slide):
                parts.append(AudioFile(event["path"], frames=event["frames"], offset=event["offset"]))
            if ready:
                parts.extend(AudioFile(p.asset(c.file), gain=c.gain) for c in slide.clips if c.placement == "after")
            self.parts[i], self.complete[i] = parts, ready

    def frames(self, index):
        return sum(part.frames for part in self.parts[index])

    def read(self, index, start, count):
        values, offset = [], start
        for part in self.parts[index]:
            if offset >= part.frames:
                offset -= part.frames
                continue
            samples = part.read(offset, count)
            values.append(samples)
            count -= len(samples)
            offset = 0
            if not count:
                break
        result = np.concatenate(values) if values else np.empty((0, 2), dtype=np.int16)
        if self.background and len(result):
            prior = sum(self.frames(i) for i in range(index))
            extra = self.background.read(prior + start, len(result))
            if len(extra):
                mixed = result.astype(np.int32)
                mixed[:len(extra)] += extra.astype(np.int32)
                result = np.clip(mixed, -32768, 32767).astype("<i2")
        return result


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
            "version": 2, "channels": 2, "format": "s16le", "status": "recording",
            "destination": self.destination, "policy": self.policy, "rate": RATE,
            "title": project.title, "started_at": time.time(),
            "slides": len(project.slides), "export_rate": project.export_rate,
            "export_bitrate": project.export_bitrate}, indent=2), encoding="utf-8")
        # Recording remains exportable after the talk is moved or edited.
        shutil.copy2(project.asset("slides.pdf"), self.root / "slides.pdf")

    def append(self, samples, slide):
        if self.audio.closed or not len(samples):
            return
        if slide != self.last_slide:
            self.journal.write(json.dumps({"frame": self.frames, "slide": slide}) + "\n")
            self.journal.flush()
            self.last_slide = slide
        samples = np.asarray(samples, dtype="<i2")
        if samples.ndim == 1:
            samples = np.repeat(samples[:, None], 2, axis=1)
        self.audio.write(samples.tobytes())
        self.audio.flush()
        self.frames += len(samples)

    def waiting(self, seconds, slide, fullscreen):
        if self.policy == "all" or (self.policy == "fullscreen" and fullscreen):
            self.append(np.zeros(round(seconds * RATE), dtype=np.int16), slide)

    def close(self):
        if not self.audio.closed:
            self.audio.close()
            self.journal.close()
            info = json.loads((self.root / "session.json").read_text())
            info["status"] = "pending"
            (self.root / "session.json").write_text(json.dumps(info, indent=2))
        return self.root


def export_recording(root, task, destination=None):
    """Render only committed PCM; interrupted recording/export can be retried."""
    import av
    root = Path(root)
    info = json.loads((root / "session.json").read_text(encoding="utf-8"))
    destination = Path(destination or info["destination"])
    info.update(destination=str(destination.resolve()), status="pending")
    (root / "session.json").write_text(json.dumps(info, indent=2))
    desktop = info.get("source") == "screen"
    events = [{"frame": 0, "slide": 0}] if desktop else []
    lines = (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            if i != len(lines)-1:
                raise ValueError("The recording journal is damaged.")
    channels, rate = info.get("channels", 1), info.get("rate", 24000)
    layout = "stereo" if channels == 2 else "mono"
    samples = (root / "audio.pcm").stat().st_size // (2*channels)
    if not samples or not events:
        raise ValueError("This session contains no recorded presentation.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix.lower() not in (".mp4", ".wav", ".m4a"):
        raise ValueError("Choose MP4 video, WAV audio, or M4A audio.")
    stage = "Export video" if destination.suffix.lower() == ".mp4" else "Export audio"
    temporary = destination.with_name(destination.stem + ".partial" + destination.suffix)
    frames = math.ceil(samples / rate * 30)
    document = QPdfDocument()
    container = screen_input = microphone = None
    try:
        if (root / "slides.pdf").exists() and document.load(str(root / "slides.pdf")) != QPdfDocument.Error.None_:
            raise ValueError("The recorded source PDF cannot be opened.")
        if desktop:
            screen_input = av.open(str(root / "screen.mkv"))
            pictures = iter(screen_input.decode(video=0))
            upcoming = next(pictures, None)
            current_picture = upcoming
            if upcoming is None:
                raise ValueError("No screen frames were recorded.")
            if (root / "microphone.pcm").exists():
                microphone = (root / "microphone.pcm").open("rb")
        container = av.open(str(temporary), "w", format="wav" if destination.suffix.lower() == ".wav" else "mp4")
        video = None
        if destination.suffix.lower() == ".mp4":
            video = container.add_stream("libx264", rate=30)
            video.width, video.height, video.pix_fmt = 1920, 1080, "yuv420p"
            video.options = {"preset": "veryfast", "crf": "20"}
        audio = container.add_stream("pcm_s16le" if destination.suffix.lower() == ".wav" else "aac", rate=info.get("export_rate", RATE))
        audio.layout = layout
        audio.bit_rate = info.get("export_bitrate", 128000)
        event_index, picture, last_page, audio_position = 0, None, None, 0
        with (root / "audio.pcm").open("rb") as source:
            for i in range(frames):
                task.check()
                at = i * rate // 30
                while event_index + 1 < len(events) and events[event_index + 1]["frame"] <= at:
                    event_index += 1
                page = events[event_index]["slide"]
                if video and desktop:
                    while upcoming is not None and float(upcoming.time or 0) <= i / 30:
                        current_picture, upcoming = upcoming, next(pictures, None)
                    pixels = np.ascontiguousarray(current_picture.to_ndarray(format="rgb24"))
                    image = QImage(pixels.data, pixels.shape[1], pixels.shape[0], pixels.strides[0], QImage.Format.Format_RGB888)
                if video and (desktop or page != last_page):
                    if not desktop:
                        size = document.pagePointSize(page-1)
                        if not size.isEmpty():
                            scale = min(1920/size.width(), 1080/size.height())
                            image = document.render(page-1, QSize(round(size.width()*scale), round(size.height()*scale)))
                        else:
                            image = QImage(str(root / f"{page:04d}.png"))
                    if image.isNull():
                        raise ValueError(f"Recorded image {page} is missing.")
                    canvas = QImage(1920, 1080, QImage.Format.Format_RGB888)
                    canvas.fill(QColor("black"))
                    scaled = image.scaled(QSize(1920, 1080), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
                    painter = QPainter(canvas)
                    painter.drawImage((1920-scaled.width())//2, (1080-scaled.height())//2, scaled)
                    painter.end()
                    picture = np.frombuffer(canvas.bits(), dtype=np.uint8).reshape(1080, canvas.bytesPerLine())[:, :1920*3].reshape(1080, 1920, 3).copy()
                    last_page = page
                if video:
                    frame = av.VideoFrame.from_ndarray(picture, format="rgb24")
                    frame.pts, frame.time_base = i, Fraction(1, 30)
                    for packet in video.encode(frame):
                        container.mux(packet)
                # Interleave audio and video to keep muxing bounded for long talks.
                target = min(samples, (i + 1) * rate // 30)
                if target > audio_position:
                    raw = source.read((target-audio_position)*2*channels)
                    pcm = np.frombuffer(raw, dtype="<i2").reshape(1, -1)
                    if microphone:
                        mic = np.frombuffer(microphone.read(len(raw)), dtype="<i2")
                        mixed = pcm.astype(np.int32)
                        mixed[0, :len(mic)] += mic.astype(np.int32)
                        pcm = np.clip(mixed, -32768, 32767).astype("<i2")
                    aframe = av.AudioFrame.from_ndarray(pcm, format="s16", layout=layout)
                    aframe.sample_rate = rate
                    aframe.pts, aframe.time_base = audio_position, Fraction(1, rate)
                    for packet in audio.encode(aframe):
                        container.mux(packet)
                    audio_position = target
                if i % 30 == 0:
                    task.event({"type": "progress", "stage": stage, "completed": i, "total": frames})
            for stream in ([video] if video else []) + [audio]:
                for packet in stream.encode():
                    container.mux(packet)
        container.close()
        container = None
        temporary.replace(destination)
        info.update(status="exported", output=str(destination.resolve()))
        (root / "session.json").write_text(json.dumps(info, indent=2))
        task.event({"type": "progress", "stage": stage, "completed": frames, "total": frames})
        return destination
    finally:
        delete(document)
        for resource in (container, screen_input, microphone):
            if resource:
                resource.close()
        temporary.unlink(missing_ok=True)


def export_prepared(project, task, destination):
    if not project.prepared:
        raise ValueError("Accept the current script and generate all audio before exporting.")
    mix = Mix(project)
    capture = Capture(project)
    try:
        for index in range(len(project.slides)):
            for start in range(0, mix.frames(index), RATE):
                task.check()
                capture.append(mix.read(index, start, min(RATE, mix.frames(index)-start)), index+1)
            task.event({"type": "progress", "stage": "Mix audio", "completed": index+1, "total": len(project.slides)})
    except BaseException:
        capture.close()
        shutil.rmtree(capture.root)
        raise
    root = capture.close()
    return export_recording(root, task, destination)
