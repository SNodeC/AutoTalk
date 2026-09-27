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
SPEAKERS = {
    "Ryan": "Energetic male · English native",
    "Aiden": "Clear, upbeat male · American English",
    "Vivian": "Bright female · Chinese native",
    "Serena": "Gentle, warm female · Chinese native",
    "Uncle_Fu": "Low, mellow male · Chinese native",
    "Dylan": "Clear, youthful male · Beijing Chinese",
    "Eric": "Lively, husky male · Sichuan Chinese",
    "Ono_Anna": "Light, playful female · Japanese native",
    "Sohee": "Warm, expressive female · Korean native",
}
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
    origin: str = "reference"

    @property
    def label(self):
        kind = "Predefined" if self.source == "CustomVoice" else "Designed" if self.source == "VoiceDesign" or self.origin == "designed" else "Own" if self.origin == "own" else "Reference"
        return f"{kind}: {self.name}"

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


# Editable scopes: application=0, talk=1, slide=2; the declarations use their maximum.
SETTING_DEFAULTS = {
    "voice": (Voice(), 2), "language": ("English", 2),
    "writing_style": ("Professional", 2), "delivery.style": ("Professional", 2),
    "delivery.instructions": ("", 2), "delivery.progression": ("", 1),
    "delivery.sampling": ({}, 1), "pause_seconds": (.6, 2), "after": ("advance", 2),
    "mode": ("Prepared", 1), "language_policy": ("mixed", 1),
    "quick_timing": ("once", 1), "realtime_script": ("ahead", 1),
    "speech_priority": ("consistency", 1), "buffer_seconds": (5, 1),
    "tolerance_seconds": (15, 1), "codex_model": ("", 1), "codex_effort": ("", 1),
    "record_presentation": (False, 1), "recording_source": ("slides", 1),
    "capture_microphone": (False, 1), "recording_policy": ("fullscreen", 1),
    "export_rate": (24000, 1), "export_bitrate": (128000, 1),
    "background_gain": (.15, 1), "background_loop": (False, 1),
}
for _attribute in ("pitch", "texture", "energy", "pace", "age", "articulation", "projection", "accent", "expression", "persona"):
    SETTING_DEFAULTS["delivery.attributes." + _attribute] = ("", 2)

SETTING_DEFAULTS = {name: (value, tuple(range(maximum + 1))) for name, (value, maximum) in SETTING_DEFAULTS.items()}
SETTING_DEFAULTS["delivery.progression"] = ("", (1,))

SETTING_CHOICES = {
    "language": LANGUAGES, "writing_style": STYLES, "delivery.style": STYLES,
    "mode": ("Prepared", "Quick", "Realtime"), "language_policy": ("mixed", "slide", "version"),
    "quick_timing": ("fit", "once", "require"), "realtime_script": ("whole", "ahead"),
    "speech_priority": ("consistency", "earliest"), "recording_source": ("slides", "screen"),
    "recording_policy": ("fullscreen", "all", "content"), "after": ("advance", "pause", "demo"),
    "export_rate": (24000, 44100, 48000), "export_bitrate": (96000, 128000, 192000),
}
SAMPLING_LIMITS = {"temperature": (0, 2), "top_k": (1, 200), "top_p": (.01, 1),
                   "repetition_penalty": (1, 2), "max_new_tokens": (128, 2048)}


def read_settings(values):
    values = copy.deepcopy(values)
    if set(values) - SETTING_DEFAULTS.keys():
        raise ValueError("Unsupported settings override.")
    if isinstance(values.get("voice"), dict):
        voice = values["voice"]
        voice["references"] = {k: Reference(**v) for k, v in voice.get("references", {}).items()}
        values["voice"] = Voice(**voice)
    for name, value in values.items():
        default = SETTING_DEFAULTS[name][0]
        if isinstance(default, (int, float)) and not isinstance(default, bool):
            valid = type(value) in (int, float) and math.isfinite(value)
        else:
            valid = isinstance(value, type(default))
        if not valid or name in SETTING_CHOICES and value not in SETTING_CHOICES[name]:
            raise ValueError(f"Unsupported setting: {name}.")
        bounds = {"pause_seconds": (0, 10), "buffer_seconds": (2, 30), "tolerance_seconds": (0, 600), "background_gain": (0, 1)}
        if name in bounds and not bounds[name][0] <= value <= bounds[name][1]:
            raise ValueError(f"Setting outside supported bounds: {name}.")
        if name == "voice":
            value.validate()
        if name == "delivery.sampling":
            for key, number in value.items():
                if key not in SAMPLING_LIMITS or type(number) not in (int, float) or not math.isfinite(number) or not SAMPLING_LIMITS[key][0] <= number <= SAMPLING_LIMITS[key][1]:
                    raise ValueError(f"Unsupported synthesis setting: {key}.")
                if key in ("top_k", "max_new_tokens") and not isinstance(number, int):
                    raise ValueError(f"{key} must be an integer.")
    return values


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
    included: bool = True
    overrides: dict = field(default_factory=dict)
    narration_origin: str = "manual"
    audio_key: str = ""
    audio_file: str = ""
    audio_sha256: str = ""
    audio_provenance: dict = field(default_factory=dict)
    duration: float = 0
    clips: list[Clip] = field(default_factory=list)

    @property
    def text_ready(self):
        return bool(self.passages) and self.narration_origin != "translation"

    @property
    def narration(self):
        return "\n\n".join((f"[{p.language}] " if p.language else "") + p.text for p in self.passages)

    @narration.setter
    def narration(self, text):
        self.passages = parse_passages(text)
        self.narration_origin = "manual"


@dataclass
class TalkVersion:
    name: str = ""
    language: str = ""
    slides: list[Slide] = field(default_factory=list)


@dataclass
class Project:
    root: Path
    title: str = "Untitled talk"
    target_minutes: float = 10
    scope: str = ""
    conference_url: str = ""
    sources: list[str] = field(default_factory=list)
    audience: str = "General conference audience"
    objective: str = "Explain the key ideas and takeaways"
    pdf_hash: str = ""
    versions: dict[str, TalkVersion] = field(default_factory=lambda: {"main": TalkVersion()})
    active_version: str = "main"
    recording_destination: str = ""
    background: Clip | None = None
    overrides: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict, repr=False, compare=False)

    def setting(self, name, slide=None):
        if slide is not None and name in slide.overrides:
            return slide.overrides[name]
        if name == "language" and self.version.language:
            return self.version.language
        if name in self.overrides:
            return self.overrides[name]
        if name in self.defaults:
            return self.defaults[name]
        return copy.deepcopy(SETTING_DEFAULTS[name][0])

    def set_setting(self, name, value, slide=None, inherit=False):
        if name not in SETTING_DEFAULTS or slide is not None and 2 not in SETTING_DEFAULTS[name][1]:
            raise ValueError("This setting is not available at this scope.")
        if not inherit:
            value = read_settings({name: value})[name]
        target = slide.overrides if slide is not None else self.overrides
        if name == "language" and slide is None:
            if self.version.name in ("", self.version.language) or not self.version.language and self.version.name == "English":
                self.version.name = "" if inherit else value
            self.version.language = "" if inherit else value
            return
        target.pop(name, None) if inherit else target.update({name: copy.deepcopy(value)})

    def setting_source(self, name, slide=None):
        return "Slide override" if slide and name in slide.overrides else "Talk setting" if name in self.overrides or name == "language" and self.version.language else "Application default"

    @property
    def delivery(self):
        return Delivery(**{name: self.setting("delivery." + name) for name in ("style", "instructions", "progression", "sampling")},
                        attributes={key.removeprefix("delivery.attributes."): self.setting(key) for key in SETTING_DEFAULTS if key.startswith("delivery.attributes.") and self.setting(key)})

    @delivery.setter
    def delivery(self, value):
        for name in SETTING_DEFAULTS:
            if name.startswith("delivery."):
                parts = name.split(".")
                self.set_setting(name, value.attributes.get(parts[2], "") if len(parts) == 3 else getattr(value, parts[1]))

    @property
    def version(self):
        return self.versions[self.active_version]

    @property
    def slides(self):
        return self.version.slides

    @property
    def included_slides(self):
        return [s for s in self.slides if s.included]

    @property
    def language(self):
        return self.setting("language")

    @language.setter
    def language(self, value):
        self.version.language = value
        self.version.name = value

    def reference(self, language=None, slide=None):
        refs = self.setting("voice", slide).references
        return refs.get(language or self.language, refs.get("default", Reference()))

    def _set_reference(self, name, value):
        voice = copy.deepcopy(self.voice)
        ref = voice.references.setdefault(self.language, copy.copy(self.reference()))
        setattr(ref, name, value)
        self.voice = voice

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

    def effective_passages(self, slide):
        values = [Passage(p.text, p.language or self.setting("language", slide)) for p in slide.passages]
        languages = {p.language for p in values}
        if self.language_policy == "version" and languages - {self.language}:
            raise ValueError(f"Slide {slide.page}: this version permits only {self.language}.")
        if self.language_policy == "slide" and len(languages) > 1:
            raise ValueError(f"Slide {slide.page}: choose one language per slide or enable mixed passages.")
        return values

    def vocal_attributes(self, slide):
        return {k.removeprefix("delivery.attributes."): self.setting(k, slide) for k in SETTING_DEFAULTS
                if k.startswith("delivery.attributes.") and self.setting(k, slide)
                and (not k.endswith("accent") or all(p.language == "Chinese" for p in self.effective_passages(slide)))
                and (not k.endswith("age") or self.setting("voice", slide).source == "VoiceDesign")}

    def directions(self, slide):
        voice = self.setting("voice", slide)
        if voice.source == "Base":
            return ""
        continuity = "Maintain a steady pace, restrained expression and consistent vocal character throughout the talk, unless the selected style or explicit directions call for a change"
        parts = [continuity, self.setting("delivery.style", slide),
                 ", ".join(f"{k}: {v}" for k, v in self.vocal_attributes(slide).items()),
                 self.setting("delivery.instructions", slide)]
        parts.insert(0, "Resolve conflicts in this order: slide directions override custom global directions; custom global directions override attributes and style; attributes and style override baseline delivery guidance")
        if self.delivery.progression:
            parts.append(f"Slide {slide.page} of {len(self.slides)}. Progression: {self.delivery.progression}")
        if voice.source == "VoiceDesign":
            parts.insert(0, voice.description)
        return ". ".join(p.strip() for p in parts if p.strip())

    def pause_after(self, slide):
        return self.setting("pause_seconds", slide) if self.included_slides and 0 < slide.page < self.included_slides[-1].page else 0

    def speech_key(self, slide: Slide, *, instructions=None) -> str:
        passages = [asdict(p) for p in self.effective_passages(slide)]
        selected = self.setting("voice", slide)
        voice = {"source": selected.source}
        if selected.source == "CustomVoice":
            voice["speaker"] = selected.speaker
        elif selected.source == "Base":
            voice["references"] = {p["language"]: [self.reference(p["language"], slide).sha256,
                                    self.reference(p["language"], slide).transcript] for p in passages}
        key = digest([ENGINE, passages, voice, self.directions(slide) if instructions is None else instructions, self.delivery.sampling,
                      self.pause_after(slide)])
        return digest([key, "earliest"]) if self.speech_priority == "earliest" else key

    def ready(self, slide: Slide) -> bool:
        try:
            return bool(slide.text_ready and slide.audio_key == self.speech_key(slide)
                        and slide.duration > 0 and self.audio(slide).is_file())
        except ValueError:
            return False

    @property
    def prepared(self):
        return bool(self.included_slides) and all(self.ready(s) for s in self.included_slides)

    @property
    def total_seconds(self):
        return sum(s.duration + sum(c.seconds for c in s.clips) for s in self.included_slides if self.ready(s))

    @property
    def within_target(self):
        return self.prepared and abs(self.total_seconds - self.target_minutes * 60) <= self.tolerance_seconds

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        # Preserve an older schema exactly once before its first replacement.
        previous = json.loads(self.manifest.read_text(encoding="utf-8")).get("version") if self.manifest.exists() else 4
        if previous < 4:
            backup = self.manifest.with_suffix(f".v{previous}-backup.json")
            if not backup.exists():
                shutil.copy2(self.manifest, backup)
        data = asdict(self)
        data.pop("root")
        data.pop("defaults")
        data["version"] = 4
        temporary = self.manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(self.manifest)

    def add_version(self, language, translate=False):
        if language not in LANGUAGES:
            raise ValueError("Unsupported language.")
        key = uuid.uuid4().hex[:12]
        # Source text is an immutable extraction snapshot from the common PDF.
        slides = [Slide(s.page, s.source_text, included=s.included, overrides=copy.deepcopy(s.overrides), budget_seconds=s.budget_seconds) for s in self.slides]
        if translate:
            for source, slide in zip(self.slides, slides):
                slide.narration = source.narration
                slide.narration_origin = "translation"
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
        voice = copy.deepcopy(self.voice) if self.voice.source == "Base" and self.voice.origin == "own" else Voice("My voice", "Base", origin="own")
        voice.references[self.language] = ref
        voice.references.setdefault("default", copy.copy(ref))
        self.voice = voice

    @classmethod
    def load(cls, manifest: Path):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        version = data.pop("version", None)
        if version not in (1, 2, 3, 4):
            raise ValueError("Unsupported AutoTalk project version.")
        root = manifest.resolve().parent
        legacy = None
        overrides = read_settings(data.pop("overrides", {}))
        if version < 4:
            for key in SETTING_DEFAULTS:
                if key != "language" and key in data:
                    overrides.update(read_settings({key: data.pop(key)}))
            delivery = data.pop("delivery", {})
            for key in SETTING_DEFAULTS:
                if key.startswith("delivery."):
                    parts = key.split(".")
                    overrides[key] = delivery.get("attributes", {}).get(parts[2], "") if len(parts) == 3 else delivery.get(parts[1], SETTING_DEFAULTS[key][0])
            overrides["writing_style"] = overrides["delivery.style"]
        data["overrides"] = overrides
        if version == 1:
            legacy = data.pop("slides")
            language = data.pop("language")
            reference = Reference(data.pop("voice_file"), data.pop("voice_hash"), data.pop("voice_transcript"))
            data.pop("narration_context")
            project = cls(root=root, **data)
            project.language = project.version.name = language
            if reference.file:
                project.voice = Voice("My voice", "Base", references={"default": reference})
            for value in legacy:
                text = value.pop("narration")
                value["overrides"] = {"after": value.pop("after", "advance"), "delivery.instructions": value.pop("directions", "")}
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
                value.pop("narration_context", None)
                slides = []
                for s in value.pop("slides"):
                    s.pop("narration_context", None)
                    s["overrides"] = read_settings(s.get("overrides", {}))
                    if version < 4:
                        s["overrides"]["after"] = s.pop("after", "advance")
                        directions = s.pop("directions", "")
                        if directions:
                            s["overrides"]["delivery.instructions"] = directions
                    s["passages"] = [Passage(**p) for p in s["passages"]]
                    s["clips"] = [Clip(**c) for c in s.get("clips", [])]
                    slides.append(Slide(**s))
                versions[key] = TalkVersion(slides=slides, **value)
            background = Clip(**data.pop("background")) if data.get("background") else data.pop("background", None)
            project = cls(root=root, versions=versions, background=background, **data)
        if version < 4 and project.background:
            project.background_gain, project.background_loop = project.background.gain, project.background.loop
        project.validate()
        for key, talk in project.versions.items():
            context = copy.copy(project)
            context.active_version = key
            for slide in talk.slides:
                if version in (2, 3) and project.mode != "Quick" and "delivery.instructions" not in slide.overrides:
                    # v3 hashed the attribute insertion order. Preserve verified audio
                    # when migration merely canonicalizes that order; never bless stale audio.
                    attributes = context.vocal_attributes(slide)
                    canonical = ", ".join(f"{k}: {v}" for k, v in attributes.items())
                    original = ", ".join(f"{k}: {v}" for k, v in delivery.get("attributes", {}).items() if k in attributes)
                    if canonical and original != canonical:
                        instructions = context.directions(slide).replace(canonical, original, 1)
                        if slide.audio_key == context.speech_key(slide, instructions=instructions):
                            slide.audio_key = context.speech_key(slide)
                if slide.audio_key:
                    audio = project.asset(slide.audio_file) if slide.audio_file else project.audio(slide)
                    if not audio.is_file() or file_hash(audio) != slide.audio_sha256:
                        slide.audio_key = ""
                    else:
                        slide.duration = wav_duration(audio)
        return project

    def validate(self):
        if not isinstance(self.target_minutes, (int, float)) or not math.isfinite(self.target_minutes) or not .1 <= self.target_minutes <= 240:
            raise ValueError("Project timing is outside supported bounds.")
        if self.active_version not in self.versions:
            raise ValueError("The selected language version is missing.")
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key) for key in self.versions):
            raise ValueError("Invalid language version identifier.")
        read_settings(self.defaults)
        for values in [self.overrides, *(slide.overrides for version in self.versions.values() for slide in version.slides)]:
            read_settings(values)
            voice = values.get("voice")
            if voice:
                for ref in voice.references.values():
                    if ref.file and file_hash(self.asset(ref.file)) != ref.sha256:
                        raise ValueError("The reference voice recording is missing or has changed.")
        if not self.slides or file_hash(self.asset("slides.pdf")) != self.pdf_hash:
            raise ValueError("The original slide PDF is missing or has changed.")
        for talk in self.versions.values():
            if talk.language and talk.language not in LANGUAGES:
                raise ValueError("Unsupported project language.")
            if [s.page for s in talk.slides] != list(range(1, len(self.slides) + 1)):
                raise ValueError("The slide sequence is invalid.")
            if not any(s.included for s in talk.slides):
                raise ValueError("Include at least one slide in the presentation.")
            for slide in talk.slides:
                if any(2 not in SETTING_DEFAULTS[key][1] for key in slide.overrides):
                    raise ValueError("A talk-only setting cannot be overridden by a slide.")
                if not isinstance(slide.included, bool) or self.setting("after", slide) not in ("advance", "pause", "demo"):
                    raise ValueError("Invalid slide presentation policy.")
                if not math.isfinite(slide.budget_seconds) or not 0 <= slide.budget_seconds <= 14400:
                    raise ValueError("Invalid slide duration budget.")
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


# These public fields resolve through the same authority as scoped generation.
def setting_property(name):
    return property(lambda self: self.setting(name), lambda self, value: self.set_setting(name, value))


for _setting in SETTING_DEFAULTS:
    if "." not in _setting and _setting != "language":
        setattr(Project, _setting, setting_property(_setting))


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
