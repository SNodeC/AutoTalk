"""A reusable local library; projects receive independent reference snapshots."""
import copy
import json
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path

from .project import Reference, Voice, file_hash
from .runtime import data_dir


def library():
    directory = data_dir() / "voices"
    if not directory.exists():
        return []
    return sorted(directory.glob("*/voice.json"))


def save_voice(project, name):
    voice = copy.deepcopy(project.voice)
    voice.validate()
    voice.name = name.strip() or voice.name
    directory = data_dir() / "voices" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    for language, ref in voice.references.items():
        if not ref.file:
            continue
        source = project.asset(ref.file)
        if file_hash(source) != ref.sha256:
            raise ValueError("The voice reference has changed. Import it again.")
        destination = directory / language / f"{ref.sha256}.wav"
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(source, destination)
        ref.file = destination.relative_to(directory).as_posix()
    manifest = directory / "voice.json"
    manifest.write_text(json.dumps(asdict(voice), indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def load_voice(project, manifest):
    manifest = Path(manifest)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    Voice(**value).validate()
    references = {}
    for language, ref in value.pop("references").items():
        reference = Reference(**ref)
        if reference.file:
            source = (manifest.parent / reference.file).resolve()
            if not source.is_relative_to(manifest.parent.resolve()) or file_hash(source) != reference.sha256:
                raise ValueError("The saved voice reference is missing or changed.")
            destination = project.asset(f"voice/{language}/{reference.sha256}.wav")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            reference.file = destination.relative_to(project.root).as_posix()
        references[language] = reference
    project.voice = Voice(references=references, **value)
