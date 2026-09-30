# SPDX-License-Identifier: MIT
import copy
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QMessageBox

from autotalk.app import MainWindow
from autotalk.project import file_hash


def window(qtbot, project, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    hashes = []
    def hashed(path):
        hashes.append(path)
        return file_hash(path)
    monkeypatch.setattr('autotalk.app.file_hash', hashed)
    return w, hashes


def test_activation_stats_unchanged_source_without_hash(qtbot, project, monkeypatch):
    w, hashes = window(qtbot, project, monkeypatch)
    assert not w.check_source_pdf()
    assert len(hashes) == 1
    w.event(QEvent(QEvent.Type.WindowActivate)); qtbot.wait(20)
    assert not w.check_source_pdf() and len(hashes) == 1
    path = Path(project.source_pdf)
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    monkeypatch.setattr(QMessageBox, 'exec', lambda _: pytest.fail('Same content must not prompt'))
    assert not w.check_source_pdf() and len(hashes) == 2
    assert not w.check_source_pdf() and len(hashes) == 2


def test_changed_source_prompts_once_and_errors_retry(qtbot, project, monkeypatch):
    w, hashes = window(qtbot, project, monkeypatch)
    prompts = []
    monkeypatch.setattr(QMessageBox, 'exec', lambda box: prompts.append(box.text()))
    assert not w.check_source_pdf()
    path = Path(project.source_pdf)
    original = path.read_bytes()
    path.write_bytes(original + b'\nchanged')
    assert not w.check_source_pdf()
    assert len(prompts) == 1 and len(hashes) == 2
    assert not w.check_source_pdf(force=True)
    assert len(prompts) == 1 and len(hashes) == 3
    path.unlink()
    assert not w.check_source_pdf()
    path.write_bytes(original)
    assert not w.check_source_pdf() and len(hashes) == 4


@pytest.mark.parametrize('entry', ['create_narration', 'prepare_talk', 'fit_duration',
                                  'start_mode', 'regenerate_slide', 'prepare_slide'])
def test_generation_always_hashes(qtbot, project, monkeypatch, entry):
    w, hashes = window(qtbot, project, monkeypatch)
    assert not w.check_source_pdf()
    monkeypatch.setattr(w, 'start_job', lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    getattr(w, entry)()
    assert len(hashes) == 2


def test_adopt_another_project_forgets_signature(qtbot, project, monkeypatch):
    w, hashes = window(qtbot, project, monkeypatch)
    assert not w.check_source_pdf()
    other = copy.deepcopy(project)
    other.root = project.root.parent / 'other'
    other.root.mkdir()
    w.adopt(other)
    assert not w.check_source_pdf() and len(hashes) == 2
    assert 'source_signature' not in project.manifest.read_text()
