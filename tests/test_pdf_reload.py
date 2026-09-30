# SPDX-License-Identifier: MIT
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QImage, QPainter, QPdfWriter
from PySide6.QtWidgets import QMessageBox

from autotalk.app import MainWindow
from autotalk.project import Project, file_hash
from autotalk.runtime import Cancelled, Task
from autotalk.services import import_pdf, reload_pdf, install_pdf_reload
from conftest import make_audio


def deck(path, titles):
    writer = QPdfWriter(str(path))
    writer.setResolution(96)
    painter = QPainter(writer)
    for i, title in enumerate(titles):
        if i:
            writer.newPage()
        painter.drawText(100, 100, title)
    painter.end()
    del writer
    return path


@pytest.fixture
def talk(tmp_path, qapp):
    pdf = deck(tmp_path / 'source.pdf', ['First', 'Second'])
    p = import_pdf(pdf, tmp_path / 'talk', Task(lambda _: None))
    p.select_language('English')
    for slide in p.slides:
        p.set_narration(slide, 'English ' + slide.source_text)
    make_audio(p)
    p.select_language('German')
    for slide in p.slides:
        p.set_narration(slide, 'Deutsch ' + slide.source_text)
    make_audio(p)
    return p


def test_unchanged_reload_rebuilds_images_preserves_all_versions(talk):
    original = talk.manifest.read_bytes()
    png = talk.image(talk.slides[0]).read_bytes()
    staged = reload_pdf(talk, Path(talk.source_pdf), Task(lambda _: None))
    assert talk.manifest.read_bytes() == original
    updated = install_pdf_reload(staged)
    assert updated.image(updated.slides[0]).read_bytes() == png
    assert staged[3].joinpath('talk.autotalk.json').read_bytes() == original
    for key, version in updated.versions.items():
        assert version == talk.versions[key]
        updated.active_version = key
        assert updated.prepared
    assert Project.load(updated.manifest).source_pdf == talk.source_pdf


def test_reorder_and_insertion_match_content_in_every_language(talk):
    deck(Path(talk.source_pdf), ['Second', 'New', 'First'])
    updated = install_pdf_reload(reload_pdf(talk, Path(talk.source_pdf), Task(lambda _: None)))
    for key, version in updated.versions.items():
        before = talk.versions[key].slides
        assert version.slides[0].narration == before[1].narration
        assert version.slides[2].narration == before[0].narration
        assert not version.slides[1].narration and not version.slides[1].audio_file
        assert version.slides[0].audio_file == before[1].audio_file
        assert updated.audio(version.slides[0]).exists()
    assert len(Project.load(updated.manifest).slides) == 3


def test_changed_and_ambiguous_slides_get_no_old_speech(talk):
    deck(Path(talk.source_pdf), ['Changed', 'Second', 'Second'])
    updated = install_pdf_reload(reload_pdf(talk, Path(talk.source_pdf), Task(lambda _: None)))
    assert all(not s.narration and not s.audio_file for v in updated.versions.values() for s in v.slides)


@pytest.mark.parametrize('failure', ['invalid', 'cancel', 'install'])
def test_failed_reload_preserves_saved_project(talk, monkeypatch, failure):
    manifest, pdf = talk.manifest.read_bytes(), talk.asset('slides.pdf').read_bytes()
    task = Task(lambda _: None)
    if failure == 'invalid':
        Path(talk.source_pdf).write_bytes(b'not PDF')
    if failure == 'cancel':
        task.cancelled.set()
    if failure == 'install':
        staged = reload_pdf(talk, Path(talk.source_pdf), task)
        rename = Path.rename
        def fail(path, target):
            if path == staged[1].root:
                raise OSError('simulated install failure')
            return rename(path, target)
        monkeypatch.setattr(Path, 'rename', fail)
        with pytest.raises(OSError):
            install_pdf_reload(staged)
    else:
        with pytest.raises((ValueError, Cancelled)):
            reload_pdf(talk, Path(talk.source_pdf), task)
    assert talk.manifest.read_bytes() == manifest
    assert talk.asset('slides.pdf').read_bytes() == pdf
    assert not list(talk.root.parent.glob('.autotalk-reload-*'))
    Project.load(talk.manifest)


def test_missing_original_and_legacy_project_open_normally(talk, qtbot):
    Path(talk.source_pdf).unlink()
    loaded = Project.load(talk.manifest)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(loaded); w.show()
    qtbot.wait(20)
    assert not w.check_source_pdf() and w.start_button.isEnabled()
    loaded.source_pdf = ''
    assert not w.check_source_pdf()
    assert w.reload_pdf_action.isEnabled()


def test_change_prompt_deferred_and_not_repeated_after_decline(talk, qtbot, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(talk)
    deck(Path(talk.source_pdf), ['Changed', 'Second'])
    prompts = []
    monkeypatch.setattr(QMessageBox, 'exec', lambda box: prompts.append(box.text()))
    w.job = object()
    assert not w.check_source_pdf() and not prompts
    w.job = None
    w.transport.state = 'paused'
    assert not w.check_source_pdf() and not prompts
    w.transport.state = 'stopped'
    assert not w.check_source_pdf() and len(prompts) == 1
    assert not w.check_source_pdf() and len(prompts) == 1
    w.event(QEvent(QEvent.Type.WindowActivate))
    qtbot.wait(10)
    assert len(prompts) == 1


def test_accepted_prompt_and_manual_unchanged_reload(talk, qtbot, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(talk); w.show()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    w.reload_pdf_action.trigger()
    qtbot.waitUntil(lambda: w.job is None, timeout=10000)
    assert list(talk.root.parent.glob('talk-before-pdf-*'))
    deck(Path(talk.source_pdf), ['Changed', 'Second'])
    def accept(box):
        next(b for b in box.buttons() if b.text() == 'Reload').click()
    monkeypatch.setattr(QMessageBox, 'exec', accept)
    assert w.check_source_pdf()
    qtbot.waitUntil(lambda: w.job is None, timeout=10000)
    assert w.project.pdf_hash == file_hash(Path(talk.source_pdf))
    assert not w.project.slides[0].narration


def test_manual_reload_repairs_missing_preview(talk):
    talk.image(talk.slides[0]).unlink()
    updated = install_pdf_reload(reload_pdf(talk, Path(talk.source_pdf), Task(lambda _: None)))
    assert updated.image(updated.slides[0]).is_file()
    assert updated.slides[0].narration == talk.slides[0].narration


def test_cancel_after_staging_does_not_install(talk, qtbot):
    from autotalk.app import Job
    manifest = talk.manifest.read_bytes()
    def prepare(task):
        result = reload_pdf(talk, Path(talk.source_pdf), task)
        task.cancelled.set()
        return result
    w = Job(prepare, None)
    w.start()
    qtbot.waitUntil(w.isFinished)
    assert w.outcome == 'cancelled' and talk.manifest.read_bytes() == manifest
    assert not list(talk.root.parent.glob('.autotalk-reload-*'))


def test_legacy_source_can_be_located(talk, qtbot, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    source = talk.source_pdf
    talk.source_pdf = ''
    w = MainWindow(); qtbot.addWidget(w); w.adopt(talk)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (source, ''))
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    w.reload_pdf_action.trigger()
    qtbot.waitUntil(lambda: w.job is None, timeout=10000)
    assert w.project.source_pdf == source


def test_live_reload_dialog_and_updated_editor(talk, qtbot):
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication
    w = MainWindow(); qtbot.addWidget(w); w.adopt(talk); w.resize(1100, 850); w.show()
    qtbot.wait(20)
    deck(Path(talk.source_pdf), ['Updated opening', 'Second'])
    evidence = Path('artifacts/pdf-reload'); evidence.mkdir(parents=True, exist_ok=True)
    seen = []
    def share_answer():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            dialog.grab().save(str(evidence / 'reload-prompt.png'))
            seen.append(dialog.text())
            qtbot.mouseClick(next(b for b in dialog.buttons() if b.text() == 'Reload'), Qt.MouseButton.LeftButton)
    timer = QTimer(); timer.timeout.connect(share_answer); timer.start(50)
    try:
        assert w.check_source_pdf()
    finally:
        timer.stop()
    qtbot.waitUntil(lambda: w.job is None, timeout=10000)
    assert seen and not w.narration.toPlainText()
    assert w.project.slides[0].source_text.strip() == 'Updated opening'
    assert w.image.original.toImage().convertToFormat(QImage.Format.Format_ARGB32) == QImage(str(w.project.image(w.project.slides[0])))
    w.grab().save(str(evidence / 'reloaded-editor.png'))
