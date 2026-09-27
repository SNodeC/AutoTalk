"""User-visible scope changes, persisted ownership and resolved generation inputs."""
import copy
import json
from dataclasses import asdict

import pytest
from PySide6.QtCore import QSettings

from autotalk import settings
from autotalk.app import MainWindow
from autotalk.project import Project, Voice
from autotalk.services import narration_result, synthesize, speech_config
from autotalk.runtime import Task, SpeechSession, speech_session
from test_gpu_lifecycle import engine
from conftest import make_audio


def test_precedence_empty_overrides_and_audio_identity(project):
    first, second = project.slides
    project.overrides.pop('voice')
    project.defaults = {'voice': Voice('Aiden', speaker='Aiden'), 'pause_seconds': 1.5,
                        'delivery.instructions': 'Speak calmly'}
    make_audio(project)
    project.set_setting('voice', project.voice)  # Same value, different source.
    assert project.prepared
    project.set_setting('pause_seconds', 0, first)
    project.set_setting('delivery.instructions', '', first)
    assert project.pause_after(first) == 0 and project.setting('delivery.instructions', first) == ''
    assert not project.ready(first) and project.ready(second)
    project.set_setting('pause_seconds', None, first, inherit=True)
    project.set_setting('delivery.instructions', None, first, inherit=True)
    assert project.prepared
    project.defaults['voice'] = Voice('Ryan')
    assert project.prepared  # Explicit talk voice shields its slides.
    project.set_setting('voice', None, inherit=True)
    assert not project.prepared


@pytest.mark.parametrize('save', [False, True])
def test_scopes_save_cancel_and_config_separation(qtbot, project, save):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    for scope, language in enumerate(('German', 'French', 'Spanish')):
        dialog = w.settings[scope]
        dialog.show_section('Voice & language')
        dialog.settings_language.setCurrentText(language)
        if scope == 2:
            dialog.speaker.setCurrentIndex(dialog.speaker.findData('Aiden'))
            assert w.project.setting('language', w.project.slides[0]) == 'Spanish'
            assert w.project.setting('language', w.project.slides[1]) == ('French' if save else 'English')
        (dialog.accept if save else dialog.reject)()
    stored = json.loads(QSettings().value('setting_defaults', '{}'))
    reopened = Project.load(project.manifest)
    assert stored.get('language', 'English') == ('German' if save else 'English')
    assert reopened.language == ('French' if save else 'English')
    assert reopened.setting('language', reopened.slides[0]) == ('Spanish' if save else 'English')
    assert reopened.setting('voice', reopened.slides[0]).speaker == ('Aiden' if save else 'Ryan')
    assert 'defaults' not in json.loads(project.manifest.read_text())


def test_defaults_without_talk_then_pin_portable_settings(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.show()
    w.settings[0].show_section('Voice & language')
    w.settings[0].settings_language.setCurrentText('German')
    w.settings[0].speaker.setCurrentIndex(w.settings[0].speaker.findData('Aiden'))
    w.settings[0].accept()
    project.overrides.clear()
    w.adopt(project)
    assert project.language == 'German' and project.voice.speaker == 'Aiden'
    w.settings[1].show_section('Talk & preparation')
    w.settings[1].pin_settings(); w.settings[1].accept()
    reopened = Project.load(project.manifest)
    assert reopened.language == 'German' and reopened.voice.speaker == 'Aiden'
    reopened.defaults = {'language': 'French', 'voice': Voice('Ryan')}
    assert reopened.language == 'German' and reopened.voice.speaker == 'Aiden'


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
def test_slide_voice_language_and_writing_reach_generation(project, mode):
    project.mode = mode
    first, second = project.slides
    project.set_setting('voice', Voice('Aiden', speaker='Aiden'), second)
    project.set_setting('language', 'German', second)
    project.set_setting('writing_style', 'Academic', second)
    requests = []
    class Speech:
        def generate(self, request, on_event=None): requests.append(request)
    synthesize(project, Task(), session=Speech())
    assert [request['speaker'] for request in requests] == ['Ryan', 'Aiden']
    assert requests[1]['items'][0]['passages'][0]['language'] == 'German'
    class Narration:
        def generate(self, prompt, schema, images, **kwargs):
            data = json.loads(prompt.split('INPUT:\n')[1])
            assert data['slides'][1]['language'] == 'German'
            assert data['slides'][1]['style'] == 'Academic'
            return {'title': 'Talk', 'slides': [{'page': s.page, 'narration': 'Text', 'notes': '', 'budget_seconds': 1} for s in project.slides]}
    narration_result(project, Task(), Narration())


def test_voice_type_transitions_reuse_single_engine_without_deadlock(engine, project):
    task = Task(report=lambda _: None); owner = task.speech = SpeechSession(task, {})
    first = speech_config(project)
    try:
        with speech_session(task, first) as session:
            original = session.process
            session.generate({**first, 'speaker': 'Aiden', 'items': []})
            assert session.process is original and session.config['speaker'] == 'Aiden'
            second = {**first, 'source': 'Base', 'model': {**first['model'], 'repo': 'test-base'}}
            session.generate({**second, 'items': []})
            assert session is owner and session.process is not original
            assert original.poll() is not None
    finally:
        owner.release()


def test_designed_origin_survives_accept_library_and_reopen(qtbot, project, monkeypatch, tmp_path):
    from autotalk import app, services, voices
    monkeypatch.setenv('AUTOTALK_DATA_DIR', str(tmp_path / 'data'))
    project.voice = Voice('Designed narrator', 'VoiceDesign', description='Calm and clear', origin='designed')
    # A verified reference-length WAV stands in for the completed design preview.
    make_audio(project, seconds=3)
    audio = project.audio(project.slides[0])
    monkeypatch.setattr(settings, 'preview_path', lambda p: audio)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings[1].show_section('Voice & language')
    assert w.settings[1].accept_designed_voice()
    assert w.project.voice.source == 'Base' and w.project.voice.label.startswith('Designed:')
    assert w.settings[1].voice_source.currentIndex() == 2
    assert w.settings[1].voice_description.text() == 'Calm and clear'
    assert not w.settings[1].options.fields['delivery.style'].isEnabled()
    assert w.settings[1].options.fields['writing_style'].isEnabled()
    w.settings[1].accept()
    reopened = Project.load(project.manifest)
    saved = voices.save_voice(reopened, 'Conference narrator')
    voices.load_voice(reopened, saved)
    assert reopened.voice.label == 'Designed: Conference narrator'


def test_language_rule_and_generation_snapshot_remain_authoritative(project):
    project.defaults = {'language': 'German'}
    project.language_policy = 'version'
    project.set_setting('language', 'French', project.slides[0])
    with pytest.raises(ValueError, match='only German'):
        project.effective_passages(project.slides[0])
    snapshot = copy.deepcopy(project)
    project.defaults['language'] = 'English'
    assert snapshot.language == 'German'


def test_v3_migration_preserves_valid_audio_and_detects_stale_settings(project):
    from autotalk.project import SETTING_DEFAULTS
    project.set_setting('delivery.attributes.energy', 'Low')
    project.set_setting('delivery.attributes.texture', 'Warm')
    make_audio(project)
    raw = json.loads(project.manifest.read_text())
    raw.pop('overrides'); raw['version'] = 3
    for key in SETTING_DEFAULTS:
        if '.' not in key and key not in ('language', 'after', 'writing_style', 'background_gain', 'background_loop'):
            value = project.setting(key)
            raw[key] = asdict(value) if key == 'voice' else value
    raw['voice'].pop('origin')
    raw['delivery'] = asdict(project.delivery)
    raw['delivery']['attributes'] = {'energy': 'Low', 'texture': 'Warm'}
    for version in raw['versions'].values():
        version['language'] = 'English'
        for slide in version['slides']:
            slide.pop('overrides'); slide['directions'] = ''; slide['after'] = 'advance'
            current = project.slides[slide['page'] - 1]
            old = project.directions(current).replace('texture: Warm, energy: Low', 'energy: Low, texture: Warm')
            slide['audio_key'] = project.speech_key(current, instructions=old)
    project.manifest.write_text(json.dumps(raw))
    migrated = Project.load(project.manifest)
    assert migrated.prepared
    migrated.save()
    assert project.manifest.with_suffix('.v3-backup.json').exists()
    assert Project.load(project.manifest).prepared
    raw['delivery']['attributes']['energy'] = 'High'
    project.manifest.write_text(json.dumps(raw))
    assert not Project.load(project.manifest).prepared


def test_own_voice_keeps_references_for_multiple_languages(project):
    make_audio(project, seconds=3)
    reference = project.audio(project.slides[0])
    project.set_voice(reference, 'Exact English reference words')
    project.language = 'German'
    project.set_voice(reference, 'Exact German reference words')
    assert set(project.voice.references) == {'English', 'German', 'default'}
    project.save()
    loaded = Project.load(project.manifest)
    assert loaded.voice.origin == 'own'
    assert loaded.reference('English').transcript == 'Exact English reference words'
    assert loaded.reference('German').transcript == 'Exact German reference words'


@pytest.mark.parametrize('name,value', [('mode', 'Realtime'), ('export_rate', 44100), ('codex_model', 'model')])
def test_talk_only_settings_cannot_be_stored_as_slide_overrides(project, name, value):
    with pytest.raises(ValueError, match='scope'):
        project.set_setting(name, value, project.slides[0])
    project.slides[0].overrides[name] = value
    project.save()
    with pytest.raises(ValueError, match='talk-only'):
        Project.load(project.manifest)


def test_delivery_preset_validation_is_atomic(qtbot, project, monkeypatch, tmp_path):
    from autotalk import options
    monkeypatch.setattr(options, 'data_dir', lambda: tmp_path)
    directory = tmp_path / 'delivery'; directory.mkdir()
    (directory / 'bad.json').write_text(json.dumps({'name': 'Invalid', 'delivery': {
        'style': 'Conversational', 'attributes': {'pitch': 42}}}))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings[1].show_section('Voice & language')
    before = copy.deepcopy(project.overrides)
    errors = []
    monkeypatch.setattr(options.QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    w.settings[1].options.use_preset()
    assert errors and project.overrides == before
    w.settings[1].reject()


def test_editing_reference_transcript_preserves_cursor(qtbot, project):
    make_audio(project, seconds=3)
    project.set_voice(project.audio(project.slides[0]), 'Original words')
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings[1].show_section('Voice & language')
    w.settings[1].transcript.moveCursor(w.settings[1].transcript.textCursor().MoveOperation.End)
    qtbot.keyClicks(w.settings[1].transcript, ' appended')
    assert w.settings[1].transcript.toPlainText() == 'Original words appended'
    assert w.settings[1].transcript.textCursor().position() == len('Original words appended')
    assert project.voice_transcript == 'Original words appended'
    w.settings[1].reject()
