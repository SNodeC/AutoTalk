"""Regression tests at project, user-interaction and exported-media boundaries."""
import copy
import json
import time
import wave
from pathlib import Path
from unittest.mock import patch

import av
import numpy as np
import pytest
from PySide6.QtCore import Qt

from conftest import make_audio
from autotalk.app import MainWindow
from autotalk.media import AudioFile, Capture, Mix, RATE, export_prepared, export_recording, import_clip
from autotalk.project import Project
from autotalk.runtime import Cancelled, Task
from autotalk.services import apply_narration, split_speech


def test_partial_revision_never_approves_later_slides(project):
    make_audio(project)
    project.scope = 'A different conference'
    old = project.slides[1].narration
    events = []
    apply_narration(project, {'title': 'Revised', 'slides': [
        {'page': 1, 'narration': 'New introduction.', 'notes': '', 'budget_seconds': 2}]}, Task(event=events.append))
    assert not project.script_current
    assert project.slides[1].narration == old
    assert project.slides[0].narration_context == project.context_key()
    assert project.slides[1].narration_context != project.context_key()
    assert not Project.load(project.manifest).prepared
    assert events[-1]['completed'] == 1


def test_manual_edit_requires_review_and_preserves_other_slides(project):
    make_audio(project)
    stamp = project.slides[1].narration_context
    project.slides[0].narration += ' An important correction.'
    assert not project.script_current
    assert project.slides[0].narration_origin == 'manual'
    assert project.slides[1].narration_context == stamp
    project.accept_script()
    assert project.script_current
    assert not project.ready(project.slides[0])
    assert project.ready(project.slides[1])


def test_v2_import_requires_review_without_erasing_work(project):
    make_audio(project)
    old = json.loads(project.manifest.read_text())
    old['version'] = 2
    for version in old['versions'].values():
        version['narration_context'] = 'unreliable-old-version-wide-stamp'
        for slide in version['slides']:
            slide.pop('narration_context')
            slide.pop('narration_origin')
    project.manifest.write_text(json.dumps(old))
    loaded = Project.load(project.manifest)
    assert not loaded.script_current
    assert all(loaded.ready(s) for s in loaded.slides)
    loaded.accept_script();loaded.save()
    assert loaded.manifest.with_suffix('.v2-backup.json').exists()
    assert Project.load(loaded.manifest).prepared


def test_language_selection_creates_translation_and_preserves_original(qtbot,project):
    make_audio(project)
    original = project.active_version
    texts = [s.narration for s in project.slides]
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    w.language.setCurrentText('German')
    assert project.active_version != original
    assert project.language == project.version.name == 'German'
    assert not project.script_current
    assert all(s.narration_origin == 'translation' for s in project.slides)
    w.language.setCurrentText('English')
    assert project.active_version == original
    assert [s.narration for s in project.slides] == texts
    assert project.prepared


def test_delivery_keeps_style_and_sets_override_precedence(project):
    project.delivery.style='Professional'
    project.delivery.attributes={'pitch':'Low'}
    project.delivery.instructions='Speak slowly'
    project.slides[0].directions='Speak briskly'
    direction=project.directions(project.slides[0])
    assert 'Professional' in direction and 'pitch: Low' in direction
    assert 'slide directions override custom global directions' in direction
    assert 'Speak slowly' in direction and 'Speak briskly' in direction


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
def test_common_delivery_reaches_every_synthesis_passage(project, mode):
    from autotalk.services import synthesize
    project.mode = mode
    project.slides[0].narration = 'One sentence about reliable software. ' * 20
    project.slides[1].directions = 'Use more energy for the conclusion'
    requests = []
    class Session:
        def generate(self, request, on_event=None):
            requests.append(request)
    synthesize(project, Task(), session=Session())
    items = requests[0]['items']
    assert len(items[0]['passages']) > 1
    for item in items:
        instructions = {p['instructions'] for p in item['passages']}
        assert len(instructions) == 1
        direction = instructions.pop()
        assert 'steady pace' in direction and 'consistent vocal character' in direction
        assert all(len(p['text']) <= 300 for p in item['passages'])
    assert ('Use more energy for the conclusion' in items[1]['passages'][0]['instructions']) == (mode != 'Quick')


def test_new_common_delivery_invalidates_previous_audio(project, monkeypatch):
    # A previously generated talk used the old effective vocal instruction.
    with monkeypatch.context() as old:
        old.setattr(Project, 'directions', lambda self, slide: 'Professional')
        make_audio(project)
        paths = [project.audio(s) for s in project.slides]
    assert project.script_current
    assert not project.prepared
    assert all(p.exists() for p in paths)
    project.save()
    assert not Project.load(project.manifest).prepared


def test_base_does_not_receive_unsupported_delivery_instructions(project):
    project.voice.source = 'Base'
    project.delivery.instructions = 'Very energetic'
    project.slides[0].directions = 'Whisper'
    assert project.directions(project.slides[0]) == ''
    project.mode = 'Quick'
    assert project.effective_voice.source == 'CustomVoice'
    assert 'steady pace' in project.directions(project.slides[0])
    assert 'Whisper' not in project.directions(project.slides[0])


def test_speech_groups_sentences_without_losing_text():
    text='Welcome to this talk. We will examine the results. Then discuss their limitations.'
    assert split_speech(text)==[text]
    early=split_speech(text,earliest=True)
    assert early[0]=='Welcome to this talk.'
    assert ' '.join(early)==text
    long='A sentence with many words. '*50
    chunks=split_speech(long)
    assert all(len(c)<=300 for c in chunks)
    assert ' '.join(chunks)==long.strip()


def test_timing_display_does_not_scan_project_assets(qtbot,project,monkeypatch):
    make_audio(project)
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    def forbidden(*args,**kwargs): raise AssertionError('Timing display scanned files/configuration')
    with patch.object(project,'ready',forbidden), patch.object(project,'speech_key',forbidden), patch.object(Path,'open',forbidden):
        for _ in range(50): w.update_timing()
    assert 'Remaining' in w.play_time.text()


def test_unfinished_realtime_duration_is_not_zero(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    w.update_timing()
    assert 'Remaining estimating' in w.play_time.text()


def test_shared_mix_preserves_stereo_and_read_boundaries(project,tmp_path):
    source=tmp_path/'stereo.wav'
    samples=np.column_stack([np.full(4800,1500),np.full(4800,-700)]).astype('<i2')
    with wave.open(str(source),'wb') as f:
        f.setparams((2,2,48000,0,'NONE','not compressed'));f.writeframes(samples.tobytes())
    clip=import_clip(project,source,Task())
    audio=AudioFile(project.asset(clip.file))
    assert np.array_equal(audio.read(0,4800),samples)
    make_audio(project)
    project.slides[0].clips=[clip]
    project.accept_script()
    mix=Mix(project)
    assert np.array_equal(mix.read(0,0,4800),samples)
    mono=AudioFile(project.audio(project.slides[0]))
    assert np.array_equal(mono.read(0,960),np.concatenate([mono.read(0,480),mono.read(480,480)]))


@pytest.mark.parametrize('extension',['mp4','wav','m4a'])
def test_direct_export_requires_no_playback_device(project,tmp_path,extension):
    make_audio(project,seconds=0.2)
    path=export_prepared(project,Task(),tmp_path/f'talk.{extension}')
    with av.open(str(path)) as container:
        assert len(container.streams.video)==(1 if extension=='mp4' else 0)
        assert container.streams.audio[0].rate==project.export_rate
        assert abs(container.duration/av.time_base - 0.4)<0.05
    sessions=list(project.root.glob('recordings/*/session.json'))
    assert len(sessions)==1
    assert json.loads(sessions[0].read_text())['status']=='exported'


def test_recording_uses_source_pdf_and_is_recoverable(project,tmp_path):
    capture=Capture(project)
    capture.append(np.ones((RATE//10,2),dtype='<i2'),1)
    root=capture.close()
    assert (root/'slides.pdf').read_bytes()==project.asset('slides.pdf').read_bytes()
    assert not list(root.glob('*.png'))
    task=Task();task.cancelled.set()
    target=tmp_path/'recovered.mp4'
    with pytest.raises(Cancelled): export_recording(root,task,target)
    assert not target.exists()
    assert not target.with_name('recovered.partial.mp4').exists()
    info=json.loads((root/'session.json').read_text())
    assert info['status']=='pending' and info['destination']==str(target)
    assert export_recording(root,Task()).exists()


def test_recording_recovery_is_discovered_on_project_open(qtbot,project):
    capture=Capture(project);capture.append(np.zeros((100,2),dtype='<i2'),1);root=capture.close()
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    assert w.recordings.findData(str(root/'session.json'))>=0


def test_three_workspaces_and_remembered_policy(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    assert [w.tabs.tabText(i).replace('&&', '&') for i in range(w.tabs.count())]==['Setup','Script','Present & Export']
    w.gpu_retention.setCurrentIndex(w.gpu_retention.findData('idle'))
    assert w.speech.retention=='idle'
    w2=MainWindow();qtbot.addWidget(w2)
    assert w2.gpu_retention.currentData()=='idle'
    w.gpu_retention.setCurrentIndex(w.gpu_retention.findData('session'))


def test_selected_segmentation_invalidates_audio(project):
    make_audio(project)
    project.speech_priority='earliest'
    assert not project.ready(project.slides[0])
    make_audio(project)
    project.speech_priority='consistency'
    assert not project.ready(project.slides[0])


def test_paragraphs_are_separate_synthesis_units():
    assert split_speech('Opening. More opening.\n\nConclusion. More conclusion.')==['Opening. More opening.','Conclusion. More conclusion.']


def test_adaptive_buffer_accounts_for_slow_production(qtbot,project):
    project.mode='Realtime';project.target_minutes=1
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    now=time.monotonic()
    w.transport.production_samples.extend([(now-4,0),(now,2)])
    assert w.transport.required_buffer > project.buffer_seconds
    project.speech_priority='earliest'
    assert w.transport.required_buffer==project.buffer_seconds


def test_closing_and_saving_later_keeps_recoverable_recording(qtbot,project,monkeypatch):
    from autotalk import app
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    capture=Capture(project);capture.append(np.ones((100,2),dtype='<i2'),1)
    w.transport.capture=capture
    class Choice:
        class ButtonRole: AcceptRole=0;DestructiveRole=1
        class StandardButton: Cancel=2
        def __init__(self,*args): self.selected=None
        def setWindowTitle(self,*args): pass
        def setText(self,*args): pass
        def addButton(self,label,*args):
            if label=='Close and save later': self.selected=label
            return label
        def exec(self): pass
        def clickedButton(self): return self.selected
    monkeypatch.setattr(app,'QMessageBox',Choice)
    w.close()
    assert not Path(capture.destination).exists()
    assert (capture.root/'audio.pcm').stat().st_size==400
    w2=MainWindow();qtbot.addWidget(w2);w2.adopt(project)
    assert w2.recordings.findData(str(capture.root/'session.json'))>=0


def test_finishing_export_before_close_creates_final_file(qtbot,project,monkeypatch):
    from autotalk import app
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    capture=Capture(project);capture.append(np.ones((RATE//10,2),dtype='<i2'),1)
    w.transport.capture=capture
    class Choice:
        class ButtonRole: AcceptRole=0;DestructiveRole=1
        class StandardButton: Cancel=2
        def __init__(self,*args): pass
        def setWindowTitle(self,*args): pass
        def setText(self,*args): pass
        def addButton(self,label,*args): return label
        def exec(self): pass
        def clickedButton(self): return 'Finish saving and close'
    monkeypatch.setattr(app,'QMessageBox',Choice)
    w.close()
    qtbot.waitUntil(lambda: w.job is None and not w.isVisible(),timeout=10000)
    assert Path(capture.destination).exists()
    assert json.loads((capture.root/'session.json').read_text())['status']=='exported'


def test_loaded_model_reuse_has_one_owner_and_changes_speaker_without_reload(monkeypatch):
    from autotalk import runtime
    entries=[]
    class Process:
        def poll(self): return None
    original=runtime.SpeechSession.__enter__
    def enter(self):
        if self.process:
            return original(self)
        entries.append(copy.deepcopy(self.config))
        self.process=Process()
        return self
    monkeypatch.setattr(runtime.SpeechSession,'__enter__',enter)
    owner=runtime.SpeechSession(Task(),{})
    config={'backend':'vllm','model':{'repo':'model','revision':'pinned'},'source':'CustomVoice','speaker':'Ryan','sampling':{}}
    task=Task(report=lambda _:None);task.speech=owner
    with runtime.speech_session(task,config) as first: process=first.process
    with runtime.speech_session(task,{**config,'speaker':'Aiden','items':[{'text':'Different request'}]}) as second:
        assert second is first and second.process is process
        assert second.config['speaker']=='Aiden'
    assert len(entries)==1
    owner.process=None


def test_parallel_startup_preserves_original_failure(project, monkeypatch):
    from autotalk import services
    from contextlib import contextmanager
    project.mode = 'Realtime'
    for slide in project.slides:
        slide.narration = ''
    @contextmanager
    def loading(task, config):
        assert task.cancelled.wait(3)
        raise Cancelled('Secondary loading cancellation')
        yield
    class Client:
        def __init__(self, task):
            raise ValueError('Original account failure')
    monkeypatch.setattr(services, 'speech_session', loading)
    monkeypatch.setattr(services, 'Codex', Client)
    with pytest.raises(ValueError, match='Original account failure'):
        services.workflow(project, Task())


def test_realtime_planning_receives_translation_style_and_timing(project):
    from autotalk.services import narration_result
    project.add_version('German', translate=True)
    project.mode = 'Realtime'
    project.delivery.style = 'Conversational'
    class Client:
        def generate(self, prompt, schema, images, **options):
            data = json.loads(prompt.split('INPUT:\n')[1])
            assert 'FINAL natural spoken narration for slide 1' in prompt
            assert data['language'] == 'German'
            assert data['style'] == 'Conversational'
            assert data['transition_pause_seconds'] == project.pause_seconds
            assert 'preserving its meaning' in data['translation_instruction']
            assert len(images) == len(project.slides)
            return {'title': 'Translated', 'slides': [
                {'page': s.page, 'narration': 'Willkommen.', 'notes': '', 'budget_seconds': 1}
                for s in project.slides]}
    narration_result(project, Task(), Client(), opening=1)


def test_accepted_designed_voice_uses_exact_preview(qtbot, project, monkeypatch, tmp_path):
    from autotalk import app
    from autotalk.project import Slide, file_hash
    from autotalk.services import preview_text
    monkeypatch.setattr(app, 'data_dir', lambda: tmp_path)
    project.voice.source = 'VoiceDesign'
    project.voice.description = 'A calm warm voice'
    sample = Slide(0)
    sample.narration = preview_text(project)
    preview = tmp_path / 'previews' / (project.speech_key(sample) + '.wav')
    preview.parent.mkdir()
    with wave.open(str(preview), 'wb') as f:
        f.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        f.writeframes(b'\1\0' * 24000 * 4)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    assert w.accept_designed_voice()
    assert project.voice.source == 'Base'
    assert file_hash(project.asset(project.reference().file)) == file_hash(preview)
    assert w.job is None


def test_manual_edits_in_realtime_require_explicit_review(qtbot, project):
    project.mode = 'Realtime'
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    assert w.start_button.text() == 'Review script'
    w.start_mode()
    assert w.tabs.currentIndex() == 1 and w.job is None


def test_expired_idle_timer_cannot_release_a_new_model_lease(monkeypatch):
    from autotalk import runtime
    timers, closed = [], []
    class Timer:
        def __init__(self, seconds, function):
            self.function = function
            timers.append(self)
        def cancel(self): pass
        def start(self): pass
    class Process:
        def poll(self): return None
    monkeypatch.setattr(runtime.threading, 'Timer', Timer)
    monkeypatch.setattr(runtime.SpeechSession, '__enter__', lambda self: self)
    config = {'backend': 'vllm', 'model': {}, 'source': 'CustomVoice', 'speaker': 'Ryan', 'sampling': {}}
    task = Task(); owner = runtime.SpeechSession(task, config); task.speech = owner
    owner.process = Process(); owner.retention = 'idle'
    monkeypatch.setattr(owner, 'close', lambda: closed.append(True))
    owner.schedule_release()
    old = timers[-1]
    with runtime.speech_session(task, config): pass
    current = timers[-1]
    monkeypatch.setattr(runtime.threading, 'current_thread', lambda: old)
    old.function()
    assert not closed
    monkeypatch.setattr(runtime.threading, 'current_thread', lambda: current)
    current.function()
    assert closed == [True]


def test_writing_next_slide_preserves_current_stream_buffer(qtbot, project):
    make_audio(project, seconds=2)
    project.mode = 'Realtime'
    first = project.slides[0]
    first.audio_key = ''  # Simulate audio that is streaming but not yet committed.
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    asset = AudioFile(project.audio(first))
    w.transport.receive_audio({'version': project.active_version, 'page': 1,
        'key': project.speech_key(first), 'path': str(project.audio(first)),
        'frames': asset.source_frames, 'offset': asset.offset})
    before = w.transport.buffered_seconds
    updated = copy.deepcopy(project.slides[1])
    updated.narration = 'The next slide is now written.'
    updated.narration_context = project.context_key()
    w.job = object()  # Deliver a producer event through the GUI's public handler.
    try:
        w.job_event({'type': 'narration', 'version': project.active_version,
                     'title': project.title, 'slides': [updated]})
        assert w.transport.buffered_seconds == before > 0
    finally:
        w.job = None
