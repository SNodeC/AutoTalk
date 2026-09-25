"""Portable project state. Audio validity is derived, never a second mutable flag."""

import hashlib
import json
import math
import shutil
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path

ENGINE = "qwen3-0.6b-base-v1"
LANGUAGES = ("English", "German", "French", "Spanish", "Italian", "Portuguese",
             "Russian", "Chinese", "Japanese", "Korean")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        if audio.getnframes() == 0:
            raise ValueError("The audio file is empty.")
        return audio.getnframes() / audio.getframerate()


@dataclass
class Slide:
    page: int
    source_text: str = ""
    narration: str = ""
    notes: str = ""
    budget_seconds: float = 0
    audio_key: str = ""
    audio_sha256: str = ""
    duration: float = 0


@dataclass
class Project:
    root: Path
    title: str = "Untitled talk"
    target_minutes: float = 10
    tolerance_seconds: float = 15
    pause_seconds: float = 0.6
    scope: str = ""
    conference_url: str = ""
    sources: list[str] = field(default_factory=list)
    audience: str = "General conference audience"
    objective: str = "Explain the key ideas and takeaways"
    language: str = "English"
    voice_file: str = ""
    voice_hash: str = ""
    voice_transcript: str = ""
    pdf_hash: str = ""
    narration_context: str = ""
    slides: list[Slide] = field(default_factory=list)

    @property
    def manifest(self):
        return self.root / "talk.autotalk.json"

    def asset(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Project asset is outside the project directory.")
        return path

    def image(self, slide: Slide) -> Path:
        return self.asset(f"slides/{slide.page:04d}.png")

    def audio(self, slide: Slide) -> Path:
        return self.asset(f"audio/{slide.page:04d}-{slide.audio_key}.wav")

    def context_key(self) -> str:
        return digest([self.pdf_hash, self.scope, self.audience, self.objective,
                       self.language, self.target_minutes, self.pause_seconds])

    def speech_key(self, slide: Slide) -> str:
        return digest([ENGINE, slide.narration.strip(), self.language,
                       self.voice_hash or "qwen-customvoice-ryan-v1", self.voice_transcript,
                       self.pause_seconds if slide.page < len(self.slides) else 0])

    def ready(self, slide: Slide) -> bool:
        return bool(slide.narration.strip() and slide.audio_key == self.speech_key(slide)
                    and slide.duration > 0 and self.audio(slide).is_file())

    @property
    def prepared(self):
        return bool(self.slides) and all(self.ready(s) for s in self.slides)

    @property
    def total_seconds(self):
        return sum(s.duration for s in self.slides if self.ready(s))

    @property
    def within_target(self):
        return self.prepared and abs(self.total_seconds - self.target_minutes * 60) <= self.tolerance_seconds

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data.pop("root")
        data["version"] = 1
        temporary = self.manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        temporary.replace(self.manifest)

    def set_voice(self, source: Path, transcript: str = ""):
        wav_duration(source)
        fingerprint = file_hash(source)
        destination = self.asset(f"voice/{fingerprint}.wav")
        destination.parent.mkdir(exist_ok=True)
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        self.voice_file = str(destination.relative_to(self.root))
        self.voice_hash = fingerprint
        self.voice_transcript = transcript.strip()

    @classmethod
    def load(cls, manifest: Path):
        data = json.loads(manifest.read_text())
        if data.pop("version", None) != 1:
            raise ValueError("Unsupported AutoTalk project version.")
        slides = [Slide(**s) for s in data.pop("slides")]
        project = cls(root=manifest.resolve().parent, slides=slides, **data)
        numbers = [project.target_minutes, project.tolerance_seconds, project.pause_seconds]
        if any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in numbers):
            raise ValueError("Invalid project timing.")
        if not 0.1 <= project.target_minutes <= 240 or not 0 <= project.pause_seconds <= 10:
            raise ValueError("Project timing is outside supported bounds.")
        if project.language not in LANGUAGES or not 0 <= project.tolerance_seconds <= 600:
            raise ValueError("Unsupported project language or tolerance.")
        if [s.page for s in slides] != list(range(1, len(slides) + 1)):
            raise ValueError("The slide sequence is invalid.")
        if not slides or file_hash(project.asset("slides.pdf")) != project.pdf_hash:
            raise ValueError("The original slide PDF is missing or has changed.")
        if project.voice_file and file_hash(project.asset(project.voice_file)) != project.voice_hash:
            raise ValueError("The reference voice recording is missing or has changed.")
        for slide in slides:
            if not project.image(slide).is_file():
                raise ValueError(f"Slide image {slide.page} is missing.")
            if slide.audio_key:
                audio = project.audio(slide)
                if not audio.is_file() or file_hash(audio) != slide.audio_sha256:
                    slide.audio_key = ""
                else:
                    slide.duration = wav_duration(audio)
        return project


def validate_narration(result: dict, count: int) -> list[dict]:
    slides = result.get("slides", [])
    if len(slides) != count or [s.get("page") for s in slides] != list(range(1, count + 1)):
        raise ValueError("Codex did not return exactly one narration for every slide in order.")
    if not isinstance(result.get("title"), str):
        raise TypeError("Codex did not return a talk title.")
    for slide in slides:
        if not isinstance(slide.get("narration"), str) or not slide["narration"].strip():
            raise ValueError("Codex returned an empty slide narration.")
        budget = slide.get("budget_seconds")
        if not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget <= 0:
            raise ValueError("Codex returned an invalid slide time budget.")
        if not isinstance(slide.get("notes"), str):
            raise TypeError("Codex did not return slide notes.")
    return slides
