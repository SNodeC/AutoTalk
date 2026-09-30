"""A missing language is authored from the deck, never copied or translated."""
import copy
import json

import pytest

from autotalk import services
from autotalk.app import MainWindow
from autotalk.project import Project
from autotalk.runtime import Task
from conftest import make_audio
from test_modes import local_speech


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
@pytest.mark.parametrize('control', ['main', 'settings'])
def test_missing_language_is_empty_then_authored_from_pdf(qtbot, project, monkeypatch, local_speech, mode, control):
    project.mode = mode
    project.quick_timing = 'once'
    project.language = 'Chinese'
    for slide in project.slides:
        project.set_narration(slide, '只属于中文版本。')
        slide.notes = 'Chinese-only uncertainty notes'
    make_audio(project)
    chinese = project.active_version
    original = copy.deepcopy(project.version)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    if control == 'main':
        w.language.setCurrentText('German')
    else:
        dialog = w.settings[1]; dialog.show_section('Voice & language')
        dialog.settings_language.setCurrentText('German'); dialog.accept()
    assert project.versions[chinese] == original
    assert not w.narration.toPlainText() and not w.presenter_narration.toPlainText()
    assert w.regenerate_button.text() == 'Create slide text'
    assert not w.preview_button.isEnabled()
    assert all(not s.passages and not s.notes and not s.audio_file and not s.audio_key and s.duration == 0 for s in project.slides)
    prompts, started = [], []
    class Client:
        def __init__(self, task): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, prompt, *args, **kwargs):
            prompts.append(prompt)
            data = json.loads(prompt.split('INPUT:\n')[1])
            assert 'translation_instruction' not in data
            assert all(not s['current_narration'] and s['source_text'] for s in data['slides'])
            assert '只属于中文版本' not in prompt and 'Chinese-only' not in prompt
            assert data['language'] == 'German'
            if mode != 'Quick': assert data['scope'] == project.scope
            return {'title': 'New German talk', 'slides': [{'page': page, 'narration': 'Neu aus den Folien erstellt.', 'notes': '', 'budget_seconds': 1} for page in data['requested_pages']]}
    monkeypatch.setattr(services, 'Codex', Client)
    monkeypatch.setattr(w, 'present', lambda **kwargs: started.append(True))
    w.start_button.click()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert prompts and started and w.project.prepared
    assert w.narration.toPlainText() == 'Neu aus den Folien erstellt.'
    assert w.project.versions[chinese] == original
    loaded = Project.load(project.manifest)
    loaded.language = 'Chinese'
    assert loaded.prepared and loaded.version == original


def test_old_unfinished_copy_is_not_shown_or_sent_as_translation_source(qtbot, project):
    source = copy.deepcopy(project.slides)
    project.language = 'German'
    project.version.slides = source  # Reproduce a saved draft from the former implementation.
    project.save()
    project = Project.load(project.manifest)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert not w.narration.toPlainText() and not w.presenter_narration.toPlainText()
    assert w.regenerate_button.text() == 'Create slide text'
    class Client:
        def generate(self, prompt, *args, **kwargs):
            assert 'spoken explanation' not in prompt and 'translation_instruction' not in prompt
            return {'title': 'Fresh talk', 'slides': [{'page': s.page, 'narration': 'Frische Worte.', 'notes': '', 'budget_seconds': 1} for s in project.slides]}
    services.apply_narration(project, services.narration_result(project, Task(), Client()), Task())
    assert all(s.narration == 'Frische Worte.' for s in project.slides)
    assert all(s.narration == before.narration for s, before in zip(project.versions['main'].slides, source))
