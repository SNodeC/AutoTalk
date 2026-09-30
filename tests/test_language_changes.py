"""Language validity across real settings, persistence and presentation starts."""
import copy
import json

import pytest

from autotalk import services
from autotalk.app import MainWindow
from autotalk.project import Project, Voice
from autotalk.runtime import Task
from PySide6.QtWidgets import QFormLayout
from conftest import make_audio
from test_modes import local_speech


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
@pytest.mark.parametrize('scope', [0, 1, 2])
def test_language_change_generates_fresh_text_before_start(qtbot, project, monkeypatch, local_speech, mode, scope):
    project.mode = mode
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.edit_setting('language', 'Chinese', scope=0 if scope == 0 else 1)
    for index in range(2):
        w.transport.select(index)
        w.narration.setPlainText('这是中文演讲。')
    w.transport.select(0)
    make_audio(project)
    untouched = copy.deepcopy(project.slides[1])
    dialog = w.settings[scope]
    dialog.show_section('Voice & language')
    dialog.settings_language.setCurrentText('German')
    dialog.accept()
    assert w.narration_progress.value() == (1 if scope == 2 else 0)
    assert w.slide_progress.value() == (1 if scope == 2 else 0)
    assert w.regenerate_button.text() == 'Create slide text'
    assert not w.narration.toPlainText() and not w.presenter_narration.toPlainText()
    assert 'German' in w.slide_info.text()
    assert w.talk_text_button.isEnabled() == (mode != 'Quick')
    assert not w.slide_audio_button.isEnabled()
    assert w.preview_button.text() == ('Play audio' if scope == 1 else 'Play previous audio')
    requests, started, errors = [], [], []
    class Client:
        def __init__(self, task): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, prompt, *args, **kwargs):
            data = json.loads(prompt.split('INPUT:\n')[1]); requests.append(data)
            return {'title': 'Talk', 'slides': [
                {'page': page, 'narration': 'Guten Tag.', 'notes': '', 'budget_seconds': 1}
                for page in data['requested_pages']]}
    monkeypatch.setattr(services, 'Codex', Client)
    monkeypatch.setattr(w, 'error', errors.append)
    def present(**kwargs):
        started.append(True)
        w.live_autostart = False
    monkeypatch.setattr(w, 'present', present)
    w.start_button.click()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert not errors and requests and started
    assert all('translation_instruction' not in request for request in requests)
    assert all(not s['current_narration'] for request in requests for s in request['slides'] if s['page'] == 1)
    assert w.project.slides[0].narration == 'Guten Tag.' and w.project.prepared
    if scope == 2:
        assert w.project.slides[1] == untouched
    assert w.narration_progress.value() == w.slide_progress.value() == 2
    assert w.preview_button.text() == 'Play audio'
    loaded = Project.load(project.manifest)
    loaded.defaults = copy.deepcopy(w.defaults)
    assert loaded.prepared and loaded.slides[0].narration == 'Guten Tag.'


@pytest.mark.parametrize('scope', [0, 1, 2])
def test_language_cancel_and_reset_restore_readiness(qtbot, project, scope):
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[scope]
    dialog.show_section('Voice & language')
    dialog.settings_language.setCurrentText('German')
    assert w.narration_progress.value() == (1 if scope == 2 else 0)
    dialog.reject()
    assert w.project.prepared and w.narration_progress.value() == 2
    assert w.narration.toPlainText() == w.project.slides[0].narration
    dialog.show_section('Voice & language')
    dialog.settings_language.setCurrentText('German')
    if scope:
        dialog.options.inheritance['language'][1].click()
        assert w.project.prepared and w.narration_progress.value() == 2
    dialog.accept()


def test_reopen_after_default_change_keeps_authored_language(project):
    project.defaults = {'language': 'Chinese'}
    for slide in project.slides:
        project.set_narration(slide, '这是中文演讲。')
    make_audio(project)
    loaded = Project.load(project.manifest)
    loaded.defaults = {'language': 'German'}
    assert loaded.version.language == ''  # Still inherits, never silently pinned.
    assert all(not loaded.text_ready(s) and not loaded.ready(s) for s in loaded.slides)
    assert all(s.narration == '这是中文演讲。' for s in loaded.slides)
    loaded.defaults = {'language': 'Chinese'}
    assert loaded.prepared


def test_new_version_keeps_slide_settings_but_no_narration_or_audio(project):
    project.set_setting('language', 'French', project.slides[0])
    project.set_narration(project.slides[0], 'Bonjour.')
    project.set_narration(project.slides[1], '[Chinese] 保留这段话。')
    make_audio(project)
    original = project.active_version
    old = copy.deepcopy(project.slides)
    project.select_language('German')
    assert not project.prepared and all(not s.passages and not s.audio_file for s in project.slides)
    assert [s.overrides for s in project.slides] == [s.overrides for s in old]
    project.active_version = original
    assert project.prepared and project.slides == old


def test_regeneration_of_changed_slide_language_preserves_explicit_portions_atomically(project):
    for slide in project.slides:
        project.set_narration(slide, 'Original words.\n\n[Chinese] 保留这段话。\n\n[French] Bonjour.')
    for slide in project.slides:
        project.set_setting('language', 'German', slide)
    original = copy.deepcopy(project.slides)
    requests = []
    class Client:
        def generate(self, prompt, *args, **kwargs):
            data = json.loads(prompt.split('INPUT:\n')[1]); requests.append(data)
            return {'title': 'Talk', 'slides': [
                {'page': s.page, 'narration': 'Neue Worte.', 'notes': '', 'budget_seconds': 1}
                for s in project.slides]}
    result = services.narration_result(project, Task(), Client())
    assert all(s['current_narration'] == '' for s in requests[0]['slides'])
    broken = copy.deepcopy(result)
    broken['slides'][1]['narration'] = '[French] Unexpected override.'
    with pytest.raises(ValueError, match='Narration'):
        services.apply_narration(project, broken, Task())
    assert project.slides == original
    services.apply_narration(project, result, Task())
    for before, after in zip(original, project.slides):
        assert after.passages[1:] == before.passages[1:]
        assert after.passages[0].text == 'Neue Worte.' and after.passages[0].language == ''
        assert project.text_ready(after)


def test_voice_and_delivery_change_only_affected_audio(project):
    make_audio(project)
    original = [s.narration for s in project.slides]
    project.set_setting('voice', Voice('Aiden', speaker='Aiden'), project.slides[0])
    assert not project.ready(project.slides[0]) and project.ready(project.slides[1])
    project.set_setting('delivery.style', 'Conversational', project.slides[1])
    assert all(project.text_ready(s) for s in project.slides)
    assert not any(project.ready(s) for s in project.slides)
    assert [s.narration for s in project.slides] == original
    project.set_setting('voice', None, project.slides[0], inherit=True)
    project.set_setting('delivery.style', None, project.slides[1], inherit=True)
    assert project.prepared


@pytest.mark.parametrize('existing', [True, False])
def test_model_target_language_marker_does_not_become_a_user_override(project, existing):
    if not existing:
        project.set_narration(project.slides[0], '')
    services.apply_narration(project, {'title': 'Talk', 'slides': [
        {'page': 1, 'narration': '[English] Generated words.', 'notes': '', 'budget_seconds': 1}]}, Task())
    slide = project.slides[0]
    assert slide.narration == 'Generated words.' and project.text_ready(slide)
    project.language = 'German'
    assert not project.text_ready(slide)


def test_manual_language_markers_remain_explicit(project):
    project.set_narration(project.slides[0], '[English] My deliberate English passage.')
    project.set_setting('language', 'German', project.slides[0])
    assert project.text_ready(project.slides[0])


@pytest.mark.parametrize('scope', [0, 1, 2])
def test_language_arrangement_caption_follows_its_scope(qtbot, project, scope):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[scope]; dialog.show_section('Voice & language')
    container, _ = dialog.options.inheritance['language_policy']
    form = next(form for form in container.parentWidget().findChildren(QFormLayout) if form.indexOf(container) >= 0)
    assert form.labelForField(container).isVisible() == container.isVisible() == (scope != 2)
