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
    project.accept_script()
    assert project.total_seconds == 6
    assert project.within_target


@pytest.mark.parametrize('outcome', ['success', 'cancel', 'invalid', 'page_limit', 'render_error'])
def test_pdf_is_released_before_staging_move_or_cleanup(sample_pdf, tmp_path, monkeypatch, outcome):
    from autotalk import services
    from autotalk.runtime import Cancelled, Task
    from PySide6.QtGui import QImage
    from shiboken6 import isValid
    documents = []
    original_document = services.QPdfDocument
    original_temporary = services.tempfile.TemporaryDirectory
    original_move = services.shutil.move
    class Document(original_document):
        def __init__(self):
            super().__init__()
            documents.append(self)  # Keep Python references, as exception tracebacks can.
        def pageCount(self):
            return 81 if outcome == 'page_limit' else super().pageCount()
        def render(self, *args):
            return QImage() if outcome == 'render_error' else super().render(*args)
    class Temporary(original_temporary):
        def cleanup(self):
            assert documents and all(not isValid(d) for d in documents)
            super().cleanup()
    def move(*args, **kwargs):
        assert documents and all(not isValid(d) for d in documents)
        return original_move(*args, **kwargs)
    monkeypatch.setattr(services, 'QPdfDocument', Document)
    monkeypatch.setattr(services.tempfile, 'TemporaryDirectory', Temporary)
    monkeypatch.setattr(services.shutil, 'move', move)
    task = Task(report=lambda _: None)
    if outcome == 'cancel':
        task.event = lambda _: task.cancelled.set()
    if outcome == 'invalid':
        sample_pdf.write_bytes(b'not a pdf')
    destination = tmp_path / 'imported'
    if outcome == 'success':
        imported = services.import_pdf(sample_pdf, destination, task)
        assert len(imported.slides) == 2
        assert Project.load(imported.manifest).pdf_hash == imported.pdf_hash
    else:
        with pytest.raises(Cancelled if outcome == 'cancel' else ValueError):
            services.import_pdf(sample_pdf, destination, task)
        assert not list(destination.iterdir())
    assert not list(tmp_path.glob('.autotalk-import-*'))
