import shutil

import pytest
from conftest import make_audio

from autotalk.project import Project, validate_narration


def test_prepared_project_is_portable_and_detects_audio_corruption(project, tmp_path):
    make_audio(project)
    destination = tmp_path / "moved-talk"
    shutil.copytree(project.root, destination)
    loaded = Project.load(destination / "talk.autotalk.json")
    assert loaded.prepared
    assert loaded.total_seconds == pytest.approx(0.6)
    loaded.audio(loaded.slides[0]).write_bytes(b"broken")
    reopened = Project.load(loaded.manifest)
    assert not reopened.prepared
    assert reopened.ready(reopened.slides[1])


@pytest.mark.parametrize("change", ["narration", "language", "voice", "pause"])
def test_changes_never_reuse_stale_audio(project, change):
    make_audio(project)
    if change == "narration":
        project.slides[0].narration += " Changed."
    elif change == "language":
        project.language = "German"
    elif change == "voice":
        project.voice.speaker = "Aiden"
    else:
        project.pause_seconds = 1.5
    assert not project.prepared


def test_changed_pdf_is_rejected(project):
    project.save()
    project.asset("slides.pdf").write_bytes(b"changed")
    with pytest.raises(ValueError, match="PDF"):
        Project.load(project.manifest)


def test_project_cannot_reference_files_outside_directory(project):
    project.voice_file = "../outside.wav"
    project.save()
    with pytest.raises(ValueError, match="outside"):
        Project.load(project.manifest)


def test_narration_must_cover_all_pages_in_order():
    with pytest.raises(ValueError, match="every slide"):
        validate_narration({"slides": [{"page": 2, "narration": "text", "budget_seconds": 4}]}, 2)


def test_timing_uses_audio_and_not_word_estimates(project):
    make_audio(project, seconds=3)
    project.target_minutes = 0.1
    project.tolerance_seconds = 0
    assert project.total_seconds == 6
    assert project.within_target
