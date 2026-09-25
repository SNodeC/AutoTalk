import copy
import json
import shutil

import pytest

from conftest import make_audio
from autotalk.project import Project, digest


def test_language_versions_roundtrip_without_losing_prepared_audio(project, tmp_path):
    make_audio(project)
    first = project.active_version
    second = project.add_version("German")
    project.slides[0].narration = "[German] Willkommen.\n\n[English] Welcome."
    project.slides[1].narration = "Vielen Dank."
    make_audio(project)
    target = tmp_path / "portable"
    shutil.copytree(project.root, target)
    loaded = Project.load(target / "talk.autotalk.json")
    assert loaded.active_version == second
    assert [p.language for p in loaded.effective_passages(loaded.slides[0])] == ["German", "English"]
    assert loaded.prepared
    loaded.active_version = first
    assert loaded.language == "English"
    assert loaded.prepared
    loaded.slides[0].narration += " Edited."
    assert not loaded.ready(loaded.slides[0])
    loaded.active_version = second
    assert loaded.prepared


def test_language_policies_validate_passages(project):
    slide = project.slides[0]
    slide.narration = "[German] Hallo.\n[English] Hello."
    project.language_policy = "slide"
    with pytest.raises(ValueError, match="one language"):
        project.effective_passages(slide)
    project.language_policy = "version"
    with pytest.raises(ValueError, match="only English"):
        project.effective_passages(slide)
    project.language_policy = "mixed"
    assert len(project.effective_passages(slide)) == 2


def test_effective_voice_and_slide_directions_invalidate_only_affected_audio(project):
    make_audio(project)
    project.slides[0].directions = "Start calmly"
    assert not project.ready(project.slides[0])
    assert project.ready(project.slides[1])
    project.voice.speaker = "Aiden"
    assert not project.ready(project.slides[1])


def test_legacy_project_migrates_without_destroying_source_or_audio(project):
    make_audio(project)
    # Construct the actual v1 wire format and its legacy artifact names/keys.
    legacy = {name: copy.deepcopy(getattr(project, name)) for name in (
        "title", "target_minutes", "tolerance_seconds", "pause_seconds", "scope",
        "conference_url", "sources", "audience", "objective", "language", "pdf_hash",
        "voice_file", "voice_hash", "voice_transcript", "narration_context")}
    legacy.update(version=1, slides=[])
    for slide in project.slides:
        key = digest(["qwen3-0.6b-base-v1", slide.narration, project.language,
                      "qwen-customvoice-ryan-v1", "", project.pause_seconds if slide.page == 1 else 0])
        path = project.asset(f"audio/{slide.page:04d}-{key}.wav")
        shutil.copy2(project.audio(slide), path)
        legacy["slides"].append({"page": slide.page, "source_text": slide.source_text,
            "narration": slide.narration, "notes": "", "budget_seconds": 0,
            "audio_key": key, "audio_sha256": slide.audio_sha256, "duration": slide.duration})
    raw = json.dumps(legacy)
    project.manifest.write_text(raw)
    loaded = Project.load(project.manifest)
    assert project.manifest.read_text() == raw
    assert loaded.prepared
    assert all(s.audio_provenance["imported"] for s in loaded.slides)
    loaded.save()
    assert project.manifest.with_suffix(".v1-backup.json").read_text() == raw
    assert Project.load(project.manifest).prepared
    loaded.slides[0].narration += " Updated."
    assert not loaded.ready(loaded.slides[0])
