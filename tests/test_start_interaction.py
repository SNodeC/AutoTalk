# SPDX-License-Identifier: MIT
"""Start commands and editor controls through real Qt/worker boundaries."""
import copy
import json
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton

from autotalk import app, services
from autotalk.app import MainWindow
from autotalk.project import Project
from conftest import make_audio
from test_modes import local_speech


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
@pytest.mark.parametrize('content', ['empty', 'manual', 'partial', 'new_language', 'saved'])
def test_start_prepares_and_presents_without_review(qtbot, project, monkeypatch, local_speech, mode, content):
    project.mode = mode
    original_version = None
    if content == 'saved':
        make_audio(project)
        project.scope += ' revised'
        project.codex_effort = 'high'
        project.target_minutes += 1
    elif content == 'empty':
        for s in project.slides: s.narration = ''
    elif content == 'partial':
        make_audio(project)
        project.slides[1].narration = ''
    elif content == 'new_language':
        original_version = project.active_version
        project.select_language('German')
        project.set_narration(project.slides[0], 'Meine eigene Einleitung.')
    existing = {s.page: copy.deepcopy(s) for s in project.slides if project.text_ready(s)}
    requested, started = [], []
    class Client:
        def __init__(self, task): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, prompt, *args, **kwargs):
            pages = json.loads(prompt.split('INPUT:\n')[1])['requested_pages']
            requested.extend(pages)
            return {'title': 'Test talk', 'slides': [{'page': p, 'narration': 'Neue Worte.' if content == 'new_language' else 'Generated words.', 'notes': '', 'budget_seconds': 2} for p in pages]}
    monkeypatch.setattr(services, 'Codex', Client)
    monkeypatch.setattr(app.QMessageBox, 'question', lambda *a: pytest.fail('Start must not request text approval'))
    if content == 'saved':
        monkeypatch.setattr(services, 'speech_session', lambda *a: pytest.fail('Saved audio must start without Qwen'))
    project.save()
    w = MainWindow(); qtbot.addWidget(w); w.adopt(Project.load(project.manifest)); w.show()
    def present(**kwargs):
        started.append(w.project.prepared)
        w.live_autostart = False
    monkeypatch.setattr(w, 'present', present)
    expected = 'Prepare and start' if mode == 'Prepared' else 'Start'
    assert w.start_button.text() == w.start_action.text() == expected
    w.start_button.click()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert len(started) == 1 and w.project.prepared
    if mode != 'Realtime': assert started == [True]
    # Realtime's opening request plans the whole deck; only missing pages are applied.
    assert set(requested) == ({1, 2} if content == 'empty' or mode == 'Realtime' and content in ('partial', 'new_language') else {2} if content in ('partial', 'new_language') else set())
    for page, slide in existing.items():
        assert w.project.slides[page-1].narration == slide.narration
        if slide.audio_key:
            assert w.project.slides[page-1].audio_sha256 == slide.audio_sha256
    assert w.start_button.text() == expected and w.start_button.isEnabled()
    assert Project.load(w.project.manifest).prepared
    if original_version:
        assert w.project.versions[original_version] == project.versions[original_version]


@pytest.mark.parametrize('outcome', ['success', 'failure', 'cancel'])
def test_start_during_operation_waits_once_and_never_starts_after_failure(qtbot, project, monkeypatch, outcome):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    release = threading.Event()
    errors, starts = [], []
    monkeypatch.setattr(w, 'error', errors.append)
    monkeypatch.setattr(w, 'prepare_and_present', lambda: starts.append(True))
    def operation(task):
        assert release.wait(5)
        task.check()
        if outcome == 'failure': raise RuntimeError('Test failure')
    w.start_job('Existing operation', operation)
    try:
        worker = w.job
        assert w.start_button.isVisible() and w.start_button.isEnabled()
        w.start_button.click(); w.start_action.trigger(); w.start_button.click()
        assert w.job is worker and not starts
        if outcome == 'cancel': w.cancel()
    finally:
        release.set()
        qtbot.waitUntil(lambda: w.job is None)
    assert starts == ([True] if outcome == 'success' else [])
    assert w.after_job is None


@pytest.mark.audio_device
@pytest.mark.parametrize('ending', ['stop', 'natural'])
def test_audio_preview_restores_play_label_without_refresh(qtbot, project, ending):
    make_audio(project, seconds=.25 if ending == 'natural' else 3)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    for _ in range(2):
        w.preview_button.click()
        qtbot.waitUntil(lambda: w.transport.position > .03, timeout=5000)
        assert w.preview_button.text() == w.preview_action.text() == 'Stop audio'
        if ending == 'stop': w.preview_button.click()
        qtbot.waitUntil(lambda: not w.transport.preview_path, timeout=5000)
        assert w.preview_button.text() == w.preview_action.text() == 'Play audio'
        assert w.settings[1].voice_preview_button.text() == 'Listen to a sample'
        assert w.transport.state == 'stopped'
        assert w.preview_button.isEnabled()
        assert 'Presentation finished' not in w.duration_label.text()


def test_dialog_labels_have_ellipses_and_direct_actions_do_not(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    labels = {a.text() for a in w.findChildren(QAction)} | {b.text() for b in w.findChildren(QPushButton)}
    for text in ('Open PDF', 'Open saved talk', 'Talk settings', 'Application settings', 'Save delivery preset',
                 'Rewrite slide text', 'Fit duration', 'Getting started', 'Keyboard shortcuts', 'About AutoTalk'):
        assert text + '…' in labels and text not in labels
    for text in ('Create slide audio', 'Play audio', 'Prepare and start', 'Save', 'Operation details'):
        assert text in labels and text + '…' not in labels
    w.narration.clear()
    assert w.regenerate_button.text() == 'Create slide text'
    assert not w.slide_audio_button.isEnabled()


@pytest.mark.parametrize('display', ['GPT-6-Astra', '', None])
def test_account_default_and_explicit_model_use_identical_name(qtbot, display):
    w = MainWindow(); qtbot.addWidget(w)
    w.codex_settings = {'model': 'gpt-6-astra', 'models': [{'model': 'gpt-6-astra', 'displayName': display}]}
    w.settings[1].refresh_models()
    name = display or 'gpt-6-astra'
    assert w.settings[1].codex_model.itemText(0) == f'Account default ({name})'
    assert w.settings[1].codex_model.itemText(1) == name
    assert w.settings[1].codex_model.itemData(0) == '' and w.settings[1].codex_model.itemData(1) == 'gpt-6-astra'


def test_save_shortcut_persists_edited_narration(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show(); w.activateWindow()
    qtbot.waitUntil(w.isActiveWindow)
    w.narration.setFocus()
    w.narration.setPlainText('My saved correction.')
    qtbot.keyClick(w.narration, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert Project.load(project.manifest).slides[0].narration == 'My saved correction.'
