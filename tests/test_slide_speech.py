# SPDX-License-Identifier: MIT
"""Per-slide authoring and persisted audio reuse through the public workflows."""
import copy
import json
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from conftest import make_audio
from test_modes import local_speech
from autotalk import app, services
from autotalk.app import MainWindow
from autotalk.project import Project, file_hash
from autotalk.runtime import Cancelled, Task


@pytest.mark.parametrize('mode', ['Prepared', 'Realtime'])
def test_one_slide_audio_accepts_only_selected_text_and_persists(project, local_speech, mode):
    project.mode = mode
    project.slides[1].narration = ''
    other = copy.deepcopy(project.slides[1])
    services.prepare(project, Task(), pages=[1])
    reopened = Project.load(project.manifest)
    assert reopened.ready(reopened.slides[0])
    assert reopened.slides[0].text_ready
    assert reopened.slides[1] == other
    assert not reopened.prepared


@pytest.mark.parametrize('mode', ['Prepared', 'Realtime'])
def test_editor_creates_text_then_audio_without_audio_approval(qtbot, project, local_speech, monkeypatch, mode):
    project.mode = mode
    for slide in project.slides:
        slide.narration = ''
    requests, played = [], []
    class Client:
        def __init__(self, task): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, prompt, *args, **kwargs):
            pages = json.loads(prompt.split('INPUT:\n')[1])['requested_pages']
            requests.append(pages)
            return {'title': 'Kept title', 'slides': [{'page': p, 'narration': 'Words for this slide.', 'notes': '', 'budget_seconds': 12} for p in pages]}
    monkeypatch.setattr(services, 'Codex', Client)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: pytest.fail('No confirmation for empty text or audio creation'))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.resize(940, 680); w.show()
    monkeypatch.setattr(w.transport, 'preview', played.append)
    w.transport.select(1)
    assert w.regenerate_button.text() == 'Create slide text'
    assert w.regenerate_button.isVisible() and w.slide_audio_button.isVisible()
    assert not w.slide_audio_button.isEnabled()
    w.prepare_slide()
    assert not requests and w.job is None
    w.regenerate_button.click()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert requests == [[2]] and not played
    assert w.transport.index == 1
    assert w.regenerate_button.text() == 'Rewrite slide text…'
    assert w.slide_audio_button.isEnabled()
    w.narration.setPlainText('My edited words.')
    w.slide_audio_button.click()
    assert not w.regenerate_button.isEnabled() and not w.slide_audio_button.isEnabled()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert requests == [[2]]
    assert w.project.slides[1].narration == 'My edited words.'
    assert w.project.ready(w.project.slides[1])
    assert played == [w.project.audio(w.project.slides[1])]
    assert w.regenerate_button.isVisible() and w.slide_audio_button.isVisible()
    assert w.preview_button.text() == 'Play audio' and w.preview_button.isEnabled()
    assert 'Audio ready' in w.slide_info.text() and 'Start reuses current audio' in w.status.text()
    assert w.preview_time.fontMetrics().horizontalAdvance(w.preview_time.text()) <= w.preview_time.width()
    for button in (w.regenerate_button, w.slide_audio_button, w.preview_button):
        assert not button.geometry().intersects(w.narration.geometry())
        assert button.parentWidget().rect().contains(button.geometry())
    assert not w.project.slides[0].passages
    w.narration.setPlainText('Changed wording needs new audio.')
    assert len(w.waveform.peaks) and w.preview_button.isEnabled()
    assert not w.project.ready(w.project.slides[1])
    assert w.regenerate_button.text() == 'Rewrite slide text…'
    assert w.slide_audio_button.isEnabled()
    w.narration.setPlainText('My edited words.')
    assert len(w.waveform.peaks) and w.preview_button.isEnabled()
    assert w.regenerate_button.text() == 'Rewrite slide text…'
    w.slide_audio_button.click()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert w.regenerate_button.isVisible() and w.slide_audio_button.isVisible()
    assert len(played) == 2 and played[-1] == w.project.audio(w.project.slides[1])
    assert played[0] != played[1] and all(path.is_file() for path in played)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.No)
    w.regenerate_button.click()
    assert w.project.slides[1].narration == 'My edited words.' and requests == [[2]]
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    w.regenerate_button.click()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert requests == [[2], [2]]
    assert w.project.slides[1].narration == 'Words for this slide.'
    assert w.slide_audio_button.isEnabled() and w.preview_button.isEnabled()
    assert not w.project.slides[0].passages
    w.narration.setPlainText('   ')
    assert not w.slide_audio_button.isEnabled() and w.regenerate_button.isEnabled()


def test_regeneration_replaces_only_completed_recording(project, local_speech, monkeypatch):
    make_audio(project)
    first, other = project.slides
    original_path, original_hash = project.audio(first), first.audio_sha256
    untouched = copy.deepcopy(other)
    def cancel(task, request):
        assert Path(request['items'][0]['output']) != original_path
        Path(request['items'][0]['output']).write_bytes(b'incomplete')
        raise Cancelled()
    with monkeypatch.context() as patch:
        patch.setattr(services, 'speech_command', cancel)
        with pytest.raises(Cancelled):
            services.prepare(project, Task(), pages=[1], force=True)
    reopened = Project.load(project.manifest)
    assert reopened.ready(reopened.slides[0])
    assert reopened.audio(reopened.slides[0]) == original_path
    assert file_hash(original_path) == original_hash
    services.prepare(project, Task(), pages=[1], force=True)
    assert project.audio(first) != original_path
    assert file_hash(original_path) == original_hash
    assert project.ready(first) and project.slides[1] == untouched
    assert Project.load(project.manifest).audio(first) == project.audio(first)


def test_context_changes_keep_valid_audio_without_review(project, monkeypatch):
    make_audio(project)
    for slide in project.slides: slide.narration_origin = 'generated'
    project.mode = 'Realtime'
    project.scope = 'Changed conference'
    project.codex_effort = 'high'
    project.target_minutes += 1
    monkeypatch.setattr(services, 'speech_session', lambda *a: pytest.fail('Current audio must be reused'))
    monkeypatch.setattr(services, 'Codex', lambda *a: pytest.fail('Existing text must be preserved'))
    assert services.workflow(project, Task()).prepared
    project.save()
    assert Project.load(project.manifest).prepared

@pytest.mark.parametrize('mode', ['Prepared', 'Realtime', 'Quick'])
def test_reopened_complete_talk_does_not_start_generation(project, monkeypatch, mode):
    project.mode = mode
    make_audio(project)
    reopened = Project.load(project.manifest)
    monkeypatch.setattr(services, 'Codex', lambda *a: pytest.fail('No text generation needed'))
    monkeypatch.setattr(services, 'speech_session', lambda *a: pytest.fail('No speech engine needed'))
    assert services.workflow(reopened, Task()).prepared


def test_realtime_generates_only_missing_slide_and_preserves_cached_audio(project, local_speech, monkeypatch):
    make_audio(project)
    project.mode = 'Realtime'
    first = copy.deepcopy(project.slides[0])
    project.slides[1].narration = ''
    project.save()
    reopened = Project.load(project.manifest)
    requested = []
    class Client:
        def __init__(self, task): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, prompt, *args, **kwargs):
            pages = json.loads(prompt.split('INPUT:\n')[1])['requested_pages']
            requested.append(pages)
            return {'title': 'Talk', 'slides': [{'page': p, 'narration': f'New page {p}', 'notes': '', 'budget_seconds': 3} for p in pages]}
    monkeypatch.setattr(services, 'Codex', Client)
    events = []
    services.workflow(reopened, Task(event=events.append))
    assert reopened.prepared and reopened.slides[0] == first
    assert file_hash(reopened.audio(first)) == first.audio_sha256
    assert [e['slide'].page for e in events if e['type'] == 'slide_ready'] == [2]
    assert requested and all(2 in pages for pages in requested)


def test_saved_opening_starts_before_background_preparation_finishes(qtbot, project, monkeypatch):
    make_audio(project, seconds=8)
    project.mode = 'Realtime'
    project.slides[1].narration = ''
    project.save()
    w = MainWindow(); qtbot.addWidget(w); w.adopt(Project.load(project.manifest))
    release, entered = threading.Event(), threading.Event()
    started = []
    def slow_work(p, task):
        entered.set()
        assert release.wait(5)
        return p
    def present(**kwargs):
        started.append(time.monotonic())
        w.live_autostart = False
    monkeypatch.setattr(app, 'workflow', slow_work)
    monkeypatch.setattr(w, 'present', present)
    before = time.monotonic()
    w.start_button.click()
    try:
        qtbot.waitUntil(entered.is_set)
        qtbot.wait(100)
        early = bool(started)
    finally:
        release.set()
        qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert early, 'Cached opening waited for a generation event or worker completion'
    assert len(started) == 1 and started[0] - before < .5


def test_quick_switch_preserves_voice_and_audio_without_confirmation(qtbot, project, monkeypatch):
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    original = copy.deepcopy(project.slides)
    def question(*args):
        pytest.fail('Quick must not override the selected voice or ask to discard it')
    monkeypatch.setattr(QMessageBox, 'question', question)
    w.mode.setCurrentText('Quick')
    assert project.mode == w.mode.currentText() == 'Quick'
    assert project.prepared
    assert project.slides == original


def test_mode_switch_and_unrelated_settings_preserve_audio(project):
    make_audio(project)
    first, second = project.slides
    path = project.audio(first)
    project.mode = 'Realtime'
    project.record_presentation = True
    project.target_minutes += 1
    assert project.ready(first) and project.ready(second)
    first.narration = 'An intentional edit.'
    assert not project.ready(first) and project.ready(second)
    assert path.is_file()


def test_write_remaining_text_does_not_replace_prepared_slide(qtbot, project, monkeypatch, local_speech):
    make_audio(project)
    original = copy.deepcopy(project.slides[0])
    project.slides[1].narration = ''
    requested = []
    class Client:
        def __init__(self, task): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, prompt, *args, **kwargs):
            pages = json.loads(prompt.split('INPUT:\n')[1])['requested_pages']
            requested.extend(pages)
            return {'title': 'Talk', 'slides': [{'page': p, 'narration': 'Remaining words.', 'notes': '', 'budget_seconds': 3} for p in pages]}
    monkeypatch.setattr(services, 'Codex', Client)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: pytest.fail('Filling empty slides is not rewriting'))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    assert w.start_button.text() == 'Prepare and start'
    started = []
    monkeypatch.setattr(w, 'present', lambda: started.append(True))
    w.start_button.click()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert requested == [2]
    assert w.project.slides[0] == original and w.project.ready(original)
    assert w.project.slides[1].narration == 'Remaining words.'
    assert w.project.prepared and started == [True]


def test_selected_language_audio_does_not_change_original_version(project, local_speech):
    make_audio(project)
    original_version = project.active_version
    original = copy.deepcopy(project.slides)
    translated_version = project.add_version('German', translate=True)
    with pytest.raises(ValueError, match='translate'):
        services.prepare(project, Task(), pages=[1])
    project.slides[0].narration = 'Guten Tag.'
    services.prepare(project, Task(), pages=[1])
    reopened = Project.load(project.manifest)
    assert reopened.active_version == translated_version
    assert reopened.ready(reopened.slides[0]) and not reopened.ready(reopened.slides[1])
    reopened.active_version = original_version
    assert reopened.slides == original and reopened.prepared


def test_slide_audio_disabled_until_translation_has_usable_narration(qtbot, project):
    project.add_version('German', translate=True)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert w.regenerate_button.text() == 'Translate slide text'
    assert w.regenerate_button.isVisible() and w.regenerate_button.isEnabled()
    assert w.slide_audio_button.isVisible() and not w.slide_audio_button.isEnabled()
    w.narration.setPlainText('Guten Tag.')
    assert w.regenerate_button.text() == 'Rewrite slide text…'
    assert w.slide_audio_button.isEnabled()
