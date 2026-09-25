"""Portable talk state. Versions own narration; artifact validity is derived."""

import copy
import hashlib
import json
import math
import re
import shutil
import uuid
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path

LANGUAGES = ("English", "German", "French", "Spanish", "Italian", "Portuguese",
             "Russian", "Chinese", "Japanese", "Korean")
SPEAKERS = ("Ryan", "Aiden", "Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ono_Anna", "Sohee")
STYLES = ("Professional", "Conversational", "Energetic", "Calm and understated",
          "Lightly humorous", "Academic", "Storytelling", "Inspirational")
ENGINE = "qwen3-1.7b-v2"


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
class Passage:
    text: str
    language: str = ""


def parse_passages(text):
    """The narration editor uses explicit [Language] paragraph markers."""
    passages = []
    language, lines = "", []
    for line in text.splitlines():
        match = re.match(r"^\[(" + "|".join(LANGUAGES) + r")\]\s*(.*)$", line)
        if match:
            if "\n".join(lines).strip():
                passages.append(Passage("\n".join(lines).strip(), language))
            language, lines = match[1], [match[2]]
        else:
            lines.append(line)
    if "\n".join(lines).strip():
        passages.append(Passage("\n".join(lines).strip(), language))
    return passages


@dataclass
class Reference:
    file: str = ""
    sha256: str = ""
    transcript: str = ""


@dataclass
class Voice:
    name: str = "Ryan"
    source: str = "CustomVoice"
    speaker: str = "Ryan"
    description: str = ""
    references: dict[str, Reference] = field(default_factory=dict)

    def validate(self):
        if self.source not in ("Base", "CustomVoice", "VoiceDesign") or self.speaker not in SPEAKERS:
            raise ValueError("Unsupported voice source or speaker.")
        if set(self.references) - (set(LANGUAGES) | {"default"}):
            raise ValueError("Unsupported reference language.")


@dataclass
class Delivery:
    style: str = "Professional"
    attributes: dict[str, str] = field(default_factory=dict)
    instructions: str = ""
    progression: str = ""
    sampling: dict = field(default_factory=dict)


@dataclass
class Clip:
    file: str
    sha256: str
    seconds: float
    placement: str = "before"
    gain: float = 1.0
    loop: bool = False


@dataclass
class Slide:
    page: int
    source_text: str = ""
    passages: list[Passage] = field(default_factory=list)
    notes: str = ""
    budget_seconds: float = 0
    directions: str = ""
    audio_key: str = ""
    audio_file: str = ""
    audio_sha256: str = ""
    audio_provenance: dict = field(default_factory=dict)
    duration: float = 0
    clips: list[Clip] = field(default_factory=list)

    @property
    def narration(self):
        return "\n\n".join((f"[{p.language}] " if p.language else "") + p.text for p in self.passages)

    @narration.setter
    def narration(self, text):
        self.passages = parse_passages(text)


@dataclass
class TalkVersion:
    name: str = "English"
    language: str = "English"
    narration_context: str = ""
    slides: list[Slide] = field(default_factory=list)


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
    pdf_hash: str = ""
    versions: dict[str, TalkVersion] = field(default_factory=lambda: {"main": TalkVersion()})
    active_version: str = "main"
    voice: Voice = field(default_factory=Voice)
    delivery: Delivery = field(default_factory=Delivery)
    mode: str = "Prepared"
    language_policy: str = "mixed"
    quick_timing: str = "fit"
    realtime_script: str = "whole"
    buffer_seconds: float = 5
    codex_model: str = ""
    codex_effort: str = ""
    record_presentation: bool = False
    recording_policy: str = "fullscreen"
    recording_destination: str = ""
    export_rate: int = 24000
    export_bitrate: int = 128000
    background: Clip | None = None

    @property
    def version(self):
        return self.versions[self.active_version]

    @property
    def slides(self):
        return self.version.slides

    @property
    def language(self):
        return self.version.language

    @language.setter
    def language(self, value):
        self.version.language = value

    @property
    def narration_context(self):
        return self.version.narration_context

    @narration_context.setter
    def narration_context(self, value):
        self.version.narration_context = value

    def reference(self, language=None):
        refs = self.voice.references
        return refs.get(language or self.language, refs.get("default", Reference()))

    @property
    def effective_voice(self):
        return Voice() if self.mode == "Quick" else self.voice

    def _set_reference(self, name, value):
        ref = self.voice.references.setdefault(self.language, copy.copy(self.reference()))
        setattr(ref, name, value)

    @property
    def voice_file(self):
        return self.reference().file

    @voice_file.setter
    def voice_file(self, value):
        self._set_reference("file", value)

    @property
    def voice_hash(self):
        return self.reference().sha256

    @voice_hash.setter
    def voice_hash(self, value):
        self._set_reference("sha256", value)

    @property
    def voice_transcript(self):
        return self.reference().transcript

    @voice_transcript.setter
    def voice_transcript(self, value):
        self._set_reference("transcript", value)

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
        return self.asset(slide.audio_file or self.audio_name(slide))

    def audio_name(self, slide, key=None):
        return f"audio/{self.active_version}/{self.language}/{slide.page:04d}-{key or slide.audio_key}.wav"

    def context_key(self) -> str:
        context = [self.scope, self.audience, self.objective, self.delivery.style, self.codex_model, self.codex_effort]
        return digest([self.pdf_hash, [] if self.mode == "Quick" else context,
                       self.language, self.language_policy, self.target_minutes, self.pause_seconds,
                       [[c.seconds for c in s.clips] for s in self.slides]])

    def effective_passages(self, slide):
        values = [Passage(p.text, p.language or self.language) for p in slide.passages]
        languages = {p.language for p in values}
        if self.language_policy == "version" and languages - {self.language}:
            raise ValueError(f"Slide {slide.page}: this version permits only {self.language}.")
        if self.language_policy == "slide" and len(languages) > 1:
            raise ValueError(f"Slide {slide.page}: choose one language per slide or enable mixed passages.")
        return values

    def directions(self, slide):
        if self.mode == "Quick":
            return "Professional"
        if self.voice.source == "Base":
            return ""
        parts = [", ".join(f"{k}: {v}" for k, v in self.delivery.attributes.items()
                          if (k != "accent" or all(p.language == "Chinese" for p in self.effective_passages(slide)))
                          and (k != "age" or self.voice.source == "VoiceDesign")) or self.delivery.style,
                 self.delivery.instructions, slide.directions]
        if self.delivery.progression:
            parts.append(f"Slide {slide.page} of {len(self.slides)}. Progression: {self.delivery.progression}")
        if self.voice.source == "VoiceDesign":
            parts.insert(0, self.voice.description)
        return ". ".join(p.strip() for p in parts if p.strip())

    def speech_key(self, slide: Slide) -> str:
        passages = [asdict(p) for p in self.effective_passages(slide)]
        selected = self.effective_voice
        voice = {"source": selected.source}
        if selected.source == "CustomVoice":
            voice["speaker"] = selected.speaker
        elif selected.source == "Base":
            voice["references"] = {p["language"]: [self.reference(p["language"]).sha256,
                                    self.reference(p["language"]).transcript] for p in passages}
        return digest([ENGINE, passages, voice, self.directions(slide), {} if self.mode == "Quick" else self.delivery.sampling,
                       self.pause_seconds if slide.page < len(self.slides) else 0])

    def ready(self, slide: Slide) -> bool:
        try:
            return bool(slide.passages and slide.audio_key == self.speech_key(slide)
                        and slide.duration > 0 and self.audio(slide).is_file())
        except ValueError:
            return False

    @property
    def prepared(self):
        return bool(self.slides) and all(self.ready(s) for s in self.slides)

    @property
    def total_seconds(self):
        return sum(s.duration + sum(c.seconds for c in s.clips) for s in self.slides if self.ready(s))

    @property
    def within_target(self):
        return self.prepared and abs(self.total_seconds - self.target_minutes * 60) <= self.tolerance_seconds

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        # Preserve the v1 source exactly once, immediately before its first replacement.
        if self.manifest.exists() and json.loads(self.manifest.read_text(encoding="utf-8")).get("version") == 1:
            backup = self.manifest.with_suffix(".v1-backup.json")
            if not backup.exists():
                shutil.copy2(self.manifest, backup)
        data = asdict(self)
        data.pop("root")
        data["version"] = 2
        temporary = self.manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(self.manifest)

    def add_version(self, language):
        if language not in LANGUAGES:
            raise ValueError("Unsupported language.")
        key = uuid.uuid4().hex[:12]
        # Source text is an immutable extraction snapshot from the common PDF.
        slides = [Slide(s.page, s.source_text) for s in self.slides]
        self.versions[key] = TalkVersion(language, language, slides=slides)
        self.active_version = key
        return key

    def set_voice(self, source: Path, transcript: str = ""):
        duration = wav_duration(source)
        if not 3 <= duration <= 60:
            raise ValueError("Use a WAV reference recording between 3 and 60 seconds.")
        fingerprint = file_hash(source)
        destination = self.asset(f"voice/{self.language}/{fingerprint}.wav")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        ref = Reference(destination.relative_to(self.root).as_posix(), fingerprint, transcript.strip())
        self.voice.references[self.language] = ref
        self.voice.references.setdefault("default", copy.copy(ref))
        self.voice.source = "Base"
        self.voice.name = "My voice"

    @classmethod
    def load(cls, manifest: Path):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        version = data.pop("version", None)
        if version not in (1, 2):
            raise ValueError("Unsupported AutoTalk project version.")
        root = manifest.resolve().parent
        legacy = None
        if version == 1:
            legacy = data.pop("slides")
            language = data.pop("language")
            reference = Reference(data.pop("voice_file"), data.pop("voice_hash"), data.pop("voice_transcript"))
            context = data.pop("narration_context")
            project = cls(root=root, **data)
            project.language = project.version.name = language
            project.narration_context = context
            if reference.file:
                project.voice = Voice("My voice", "Base", references={"default": reference})
            for value in legacy:
                text = value.pop("narration")
                slide = Slide(**value)
                slide.narration = text
                slide.audio_file = f"audio/{slide.page:04d}-{slide.audio_key}.wav" if slide.audio_key else ""
                project.slides.append(slide)
                old_key = digest(["qwen3-0.6b-base-v1", text.strip(), language,
                                  reference.sha256 or "qwen-customvoice-ryan-v1", reference.transcript,
                                  project.pause_seconds if slide.page < len(legacy) else 0])
                if slide.audio_key == old_key:
                    slide.audio_provenance = {"engine": "qwen3-0.6b-v1", "imported": True}
                else:
                    slide.audio_key = ""
            # Compute keys after the complete slide sequence exists (last-slide pause).
            for slide in project.slides:
                if slide.audio_provenance:
                    slide.audio_key = project.speech_key(slide)
        else:
            versions = {}
            for key, value in data.pop("versions").items():
                slides = []
                for s in value.pop("slides"):
                    s["passages"] = [Passage(**p) for p in s["passages"]]
                    s["clips"] = [Clip(**c) for c in s.get("clips", [])]
                    slides.append(Slide(**s))
                versions[key] = TalkVersion(slides=slides, **value)
            voice = data.pop("voice")
            voice["references"] = {k: Reference(**v) for k, v in voice["references"].items()}
            delivery = Delivery(**data.pop("delivery"))
            background = Clip(**data.pop("background")) if data.get("background") else data.pop("background", None)
            project = cls(root=root, versions=versions, voice=Voice(**voice), delivery=delivery,
                          background=background, **data)
        project.validate()
        for talk in project.versions.values():
            for slide in talk.slides:
                if slide.audio_key:
                    audio = project.asset(slide.audio_file) if slide.audio_file else project.audio(slide)
                    if not audio.is_file() or file_hash(audio) != slide.audio_sha256:
                        slide.audio_key = ""
                    else:
                        slide.duration = wav_duration(audio)
        return project

    def validate(self):
        numbers = [self.target_minutes, self.tolerance_seconds, self.pause_seconds, self.buffer_seconds]
        if any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in numbers):
            raise ValueError("Invalid project timing.")
        if not 0.1 <= self.target_minutes <= 240 or not 0 <= self.pause_seconds <= 10:
            raise ValueError("Project timing is outside supported bounds.")
        if not 0 <= self.tolerance_seconds <= 600 or not 2 <= self.buffer_seconds <= 30:
            raise ValueError("Unsupported tolerance or startup buffer.")
        if self.active_version not in self.versions:
            raise ValueError("The selected language version is missing.")
        self.voice.validate()
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key) for key in self.versions):
            raise ValueError("Invalid language version identifier.")
        for value, allowed in (
            (self.mode, ("Prepared", "Quick", "Realtime")),
            (self.language_policy, ("mixed", "slide", "version")),
            (self.quick_timing, ("fit", "once", "require")),
            (self.realtime_script, ("whole", "ahead")),
            (self.recording_policy, ("fullscreen", "all", "content")),
            (self.delivery.style, STYLES),
            (self.export_rate, (24000, 44100, 48000)), (self.export_bitrate, (96000, 128000, 192000))):
            if value not in allowed:
                raise ValueError(f"Unsupported project option: {value}.")
        limits = {"temperature": (0, 2), "top_k": (1, 200), "top_p": (0.01, 1),
                  "repetition_penalty": (1, 2), "max_new_tokens": (128, 2048)}
        for name, value in self.delivery.sampling.items():
            if name not in limits or not isinstance(value, (int, float)) or not math.isfinite(value) or not limits[name][0] <= value <= limits[name][1]:
                raise ValueError(f"Unsupported synthesis setting: {name}.")
            if name in ("top_k", "max_new_tokens") and not isinstance(value, int):
                raise ValueError(f"{name} must be an integer.")
        for ref in self.voice.references.values():
            if ref.file and file_hash(self.asset(ref.file)) != ref.sha256:
                raise ValueError("The reference voice recording is missing or has changed.")
        if not self.slides or file_hash(self.asset("slides.pdf")) != self.pdf_hash:
            raise ValueError("The original slide PDF is missing or has changed.")
        for talk in self.versions.values():
            if talk.language not in LANGUAGES:
                raise ValueError("Unsupported project language.")
            if [s.page for s in talk.slides] != list(range(1, len(self.slides) + 1)):
                raise ValueError("The slide sequence is invalid.")
            for slide in talk.slides:
                if not self.image(slide).is_file():
                    raise ValueError(f"Slide image {slide.page} is missing.")
                if any(p.language and p.language not in LANGUAGES for p in slide.passages):
                    raise ValueError("Unsupported passage language.")
                for clip in slide.clips:
                    if clip.placement not in ("before", "after") or not math.isfinite(clip.gain) or not 0 <= clip.gain <= 2:
                        raise ValueError("Invalid clip placement or gain.")
                    if file_hash(self.asset(clip.file)) != clip.sha256:
                        raise ValueError("An audio clip is missing or has changed.")
                    clip.seconds = wav_duration(self.asset(clip.file))
        if self.background and file_hash(self.asset(self.background.file)) != self.background.sha256:
            raise ValueError("The background track is missing or has changed.")
        if self.background:
            if not math.isfinite(self.background.gain) or not 0 <= self.background.gain <= 2:
                raise ValueError("Invalid background gain.")
            self.background.seconds = wav_duration(self.asset(self.background.file))


def validate_narration(result: dict, count: int, pages=None) -> list[dict]:
    slides = result.get("slides", [])
    expected = pages or list(range(1, count + 1))
    if len(slides) != count or [s.get("page") for s in slides] != expected:
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
