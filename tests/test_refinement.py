"""Regression tests at project, user-interaction and exported-media boundaries."""
import copy
import json
import sys
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


def test_partial_revision_preserves_other_text_and_audio(project):
    make_audio(project)
    project.scope = 'A different conference'
    other = copy.deepcopy(project.slides[1])
    events = []
    apply_narration(project, {'title': 'Revised', 'slides': [
        {'page': 1, 'narration': 'New introduction.', 'notes': '', 'budget_seconds': 2}]}, Task(event=events.append))
    assert all(s.text_ready for s in project.included_slides)
    assert project.slides[1] == other and project.ready(other)
    assert not project.ready(project.slides[0])
    assert not Project.load(project.manifest).prepared
    assert events[-1]['completed'] == 2

def test_manual_edit_only_invalidates_its_audio(project):
    make_audio(project)
    other = copy.deepcopy(project.slides[1])
    project.slides[0].narration += ' An important correction.'
    assert all(s.text_ready for s in project.included_slides)
    assert project.slides[0].narration_origin == 'manual'
    assert project.slides[1] == other
    assert not project.ready(project.slides[0])
    assert project.ready(project.slides[1])

@pytest.mark.parametrize('version_number', [2, 3])
def test_old_context_stamps_do_not_block_saved_audio(project, version_number):
    make_audio(project)
    old = json.loads(project.manifest.read_text())
    old['version'] = version_number
    for version in old['versions'].values():
        version['narration_context'] = 'obsolete-version-stamp'
        for slide in version['slides']:
            slide['narration_context'] = 'obsolete-slide-stamp'
            slide.pop('narration_origin')
    project.manifest.write_text(json.dumps(old))
    loaded = Project.load(project.manifest)
    assert loaded.prepared
    assert all(loaded.ready(s) for s in loaded.slides)
    loaded.save()
    if version_number == 2:
        assert loaded.manifest.with_suffix('.v2-backup.json').exists()
    assert Project.load(loaded.manifest).prepared
    assert 'narration_context' not in loaded.manifest.read_text()

def test_language_selection_creates_translation_and_preserves_original(qtbot,project, monkeypatch):
    make_audio(project)
    original = project.active_version
    texts = [s.narration for s in project.slides]
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    monkeypatch.setattr('autotalk.app.QInputDialog.getItem', lambda *a, **kw: ('German', True))
    w.add_version()
    assert project.active_version != original
    assert project.language == project.version.name == 'German'
    assert not all(s.text_ready for s in project.included_slides)
    assert all(s.narration_origin == 'translation' for s in project.slides)
    w.language.setCurrentText('English')
    assert project.active_version == original
    assert [s.narration for s in project.slides] == texts
    assert project.prepared


def test_delivery_keeps_style_and_sets_override_precedence(project):
    project.set_setting("delivery.style", 'Professional')
    project.set_setting('delivery.attributes.pitch', 'Low')
    project.set_setting("delivery.instructions", 'Speak slowly')
    project.set_setting("delivery.instructions", 'Speak briskly', project.slides[0])
    direction=project.directions(project.slides[0])
    assert 'Professional' in direction and 'pitch: Low' in direction
    assert 'slide directions override custom global directions' in direction
    assert 'Speak slowly' not in direction and 'Speak briskly' in direction


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
def test_common_delivery_reaches_every_synthesis_passage(project, mode):
    from autotalk.services import synthesize
    project.mode = mode
    project.slides[0].narration = 'One sentence about reliable software. ' * 20
    project.set_setting("delivery.instructions", 'Use more energy for the conclusion', project.slides[1])
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
    assert ('Use more energy for the conclusion' in items[1]['passages'][0]['instructions']) == True


def test_new_common_delivery_invalidates_previous_audio(project, monkeypatch):
    # A previously generated talk used the old effective vocal instruction.
    with monkeypatch.context() as old:
        old.setattr(Project, 'directions', lambda self, slide: 'Professional')
        make_audio(project)
        paths = [project.audio(s) for s in project.slides]
    assert all(s.text_ready for s in project.included_slides)
    assert not project.prepared
    assert all(p.exists() for p in paths)
    project.save()
    assert not Project.load(project.manifest).prepared


def test_base_does_not_receive_unsupported_delivery_instructions(project):
    project.voice.source = 'Base'
    project.set_setting("delivery.instructions", 'Very energetic')
    project.set_setting("delivery.instructions", 'Whisper', project.slides[0])
    assert project.directions(project.slides[0]) == ''
    project.mode = 'Quick'
    assert project.voice.source == 'Base'
    assert project.directions(project.slides[0]) == ''
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
    assert any(w.recordings.item(i, 0).data(Qt.ItemDataRole.UserRole) == str(root/'session.json') for i in range(w.recordings.rowCount()))


def test_desktop_workspaces_and_remembered_policy(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    assert [a.text() for a in w.menuBar().actions()]==['File', 'Edit', 'View', 'Talk', 'Presentation', 'Settings', 'Help']
    assert w.workspace.currentWidget() is w.editor
    w.mode.setCurrentText('Quick')
    assert w.workspace.currentWidget() is w.quick_page
    w.mode.setCurrentText('Realtime')
    assert w.workspace.currentWidget() is w.editor
    w.settings[0].show_section("AI & speech engine")
    next(b for b in w.gpu_retention.buttons() if b.property('value') == 'idle').click()
    assert w.speech.retention == 'session'
    w.settings[0].accept()
    assert w.speech.retention=='idle'
    w2=MainWindow();qtbot.addWidget(w2)
    assert w2.gpu_retention.checkedButton().property('value')=='idle'
    w.settings[0].show_section("AI & speech engine")
    next(b for b in w.gpu_retention.buttons() if b.property('value') == 'session').click()
    w.settings[0].accept()


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
    assert any(w2.recordings.item(i, 0).data(Qt.ItemDataRole.UserRole) == str(capture.root/'session.json') for i in range(w2.recordings.rowCount()))


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
    project.set_setting("writing_style", 'Conversational')
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
    from autotalk import services
    from autotalk.services import preview_text
    monkeypatch.setattr(services, 'data_dir', lambda: tmp_path)
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
    assert w.settings[1].accept_designed_voice()
    assert project.voice.source == 'Base'
    assert file_hash(project.asset(project.reference().file)) == file_hash(preview)
    assert w.job is None


def test_manual_edits_in_realtime_start_without_review(qtbot, project, monkeypatch):
    project.mode = 'Realtime'
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    started = []
    monkeypatch.setattr(w, 'prepare_and_present', lambda: started.append(True))
    assert w.start_button.text() == 'Start'
    w.start_button.click()
    assert started == [True]

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
    from types import SimpleNamespace
    w.job = SimpleNamespace(title="Preparing talk…")  # Deliver a producer event through the GUI's public handler.
    try:
        w.job_event({'type': 'narration', 'version': project.active_version,
                     'title': project.title, 'slides': [updated]})
        assert w.transport.buffered_seconds == before > 0
    finally:
        w.job = None


def test_single_slide_generation_preserves_unset_timing_and_other_work(project):
    from autotalk.services import narrate
    make_audio(project)
    old_title, second = project.title, copy.deepcopy(project.slides[1])
    class Client:
        def __init__(self, task): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, prompt, schema, images, **kwargs):
            data = json.loads(prompt.split('INPUT:\n')[1])
            assert data['requested_pages'] == [1]
            assert data['slides'][0]['requested_seconds'] is None
            assert schema['properties']['slides']['items']['properties']['budget_seconds']['minimum'] > 0
            return {'title': 'Do not replace the talk title', 'slides': [
                {'page': 1, 'narration': 'A revised opening.', 'notes': '', 'budget_seconds': 5}]}
    with patch('autotalk.services.Codex', Client):
        narrate(project, Task(), pages=[1])
    assert project.title == old_title
    assert project.slides[1] == second and project.ready(project.slides[1])
    assert all(s.text_ready for s in project.included_slides) and not project.ready(project.slides[0])


def test_excluded_slides_are_preserved_but_not_synthesized_or_exported(project, tmp_path):
    from autotalk.services import synthesize
    make_audio(project)
    project.slides[0].included = False
    project.slides[0].narration = ''
    project.set_setting("after", 'demo', project.slides[1])
    project.save()
    loaded = Project.load(project.manifest)
    assert loaded.prepared and len(loaded.slides) == 2
    assert loaded.setting('after', loaded.slides[1]) == 'demo'
    assert loaded.total_seconds == pytest.approx(.3)
    requested = []
    class Session:
        def generate(self, request, on_event): requested.extend(request['items'])
    loaded.slides[1].audio_key = ''
    synthesize(loaded, Task(), session=Session())
    assert [item['page'] for item in requested] == [2]
    destination = export_prepared(project, Task(), tmp_path / 'included.mp4')
    with av.open(str(destination)) as movie:
        assert movie.duration / av.time_base == pytest.approx(.3, abs=.06)


def test_after_slide_pause_continues_to_next_included_slide(qtbot, project):
    from autotalk.playback import Playback
    make_audio(project)
    project.set_setting("after", 'pause', project.slides[0])
    player = Playback();player.timer.stop();player.load(project)
    player._offset = round(.3 * RATE)
    player.state = 'paused'
    player.play()
    assert player.index == 1 and player.state == 'buffering'
    player.stop()
    project.slides[0].included = False
    player.load(project);player.play()
    assert player.index == 1
    player.stop()


def test_completed_desktop_recording_keeps_authoring_locked(qtbot, project):
    make_audio(project)
    w = MainWindow();qtbot.addWidget(w);w.adopt(project)
    capture = Capture(project)
    capture.ready = True
    w.transport.capture = capture
    w.transport._finish();w.refresh()
    assert w.transport.active and w.narration.isReadOnly()
    assert not w.talk_action.isEnabled()
    capture.close();w.transport.capture = None
    w.transport.stop()


def test_voice_library_preview_selection_and_cancel(qtbot, project, monkeypatch, tmp_path):
    from autotalk import voices
    monkeypatch.setattr(voices, 'data_dir', lambda: tmp_path)
    original = project.voice.speaker
    project.voice.speaker = 'Aiden'
    voices.save_voice(project, 'My conference voice')
    project.voice.speaker = original
    w = MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    w.settings[1].show_section("Voice & language")
    w.settings[1].voice_source.setCurrentIndex(3)
    assert w.settings[1].voice_library.rowCount() == 1
    assert w.settings[1].voice_library.item(0, 0).text() == 'My conference voice'
    w.settings[1].library_use.click()
    assert w.project.voice.speaker == 'Aiden'
    assert w.settings[1].navigation.currentItem().text() == "Voice & language"
    assert w.settings[1].voice_library.item(w.settings[1].voice_library.currentRow(), 0).text() == 'My conference voice'
    w.settings[1].reject()
    assert w.project.voice.speaker == original


def test_recording_sources_update_capabilities_and_restore_on_cancel(qtbot, project):
    w = MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    w.settings[1].show_section("Presentation & recording")
    w.settings[1].options.fields['recording_source'].setCurrentIndex(1)
    assert project.recording_source == 'screen'
    assert w.settings[1].options.fields['capture_microphone'].isEnabled()
    assert not w.settings[1].options.fields['recording_policy'].isEnabled()
    w.settings[1].reject()
    assert w.project.recording_source == 'slides'


def test_desktop_export_preserves_aspect_timing_and_microphone(project, tmp_path):
    from fractions import Fraction
    capture = Capture(project)
    capture.append(np.full((RATE//5, 2), 1000, dtype='<i2'), 1)
    root = capture.close()
    info = json.loads((root/'session.json').read_text());info['source'] = 'screen'
    (root/'session.json').write_text(json.dumps(info))
    (root/'events.jsonl').write_text('')
    (root/'microphone.pcm').write_bytes(np.full((RATE//5, 2), 500, dtype='<i2').tobytes())
    with av.open(str(root/'screen.mkv'), 'w') as container:
        stream = container.add_stream('libx264', rate=10)
        stream.width, stream.height, stream.pix_fmt = 320, 240, 'yuv420p'
        for i, color in enumerate(((230, 20, 20), (20, 230, 20))):
            pixels = np.zeros((240, 320, 3), dtype=np.uint8);pixels[:] = color
            frame = av.VideoFrame.from_ndarray(pixels, format='rgb24')
            frame.pts, frame.time_base = i, Fraction(1, 10)
            for packet in stream.encode(frame): container.mux(packet)
        for packet in stream.encode(): container.mux(packet)
    output = export_recording(root, Task())
    with av.open(str(output)) as movie:
        frames = [f.to_ndarray(format='rgb24') for f in movie.decode(video=0)]
        assert len(frames) == 6
        assert frames[0][540, 960, 0] > 200 and frames[-1][540, 960, 1] > 200
        assert frames[0][:, :200].max() < 10  # 4:3 is letterboxed, never stretched.
    wav = export_recording(root, Task(), tmp_path/'mixed.wav')
    with wave.open(str(wav)) as audio:
        assert audio.getnchannels() == 2
        assert audio.getnframes() / audio.getframerate() == pytest.approx(.2)
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2')
        assert np.allclose(samples[64:-64], 1500, atol=1)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux desktop capture")
def test_stopping_before_desktop_permission_never_starts_capture(qtbot, project):
    from autotalk.screen_capture import ScreenCapture
    capture = ScreenCapture(project)
    root = capture.close()
    qtbot.wait(20)
    assert not capture.screen.isActive() and not capture.workers
    assert json.loads((root/'session.json').read_text())['duration'] == 0


def test_saved_recordings_are_discoverable_and_selection_survives_refresh(qtbot, project, tmp_path):
    w = MainWindow();qtbot.addWidget(w);w.adopt(project)
    paths = []
    for i in range(2):
        capture = Capture(project);capture.append(np.zeros((RATE//10, 2), dtype='<i2'), 1)
        paths.append(export_recording(capture.close(), Task(), tmp_path/f'recorded-{i}.wav'))
    w.export_saved(paths[0])
    assert w.recordings.rowCount() == 2
    assert Path(w.output_path) == paths[0] and w.output_button.isEnabled()
    w.refresh_recordings()
    assert Path(w.output_path) == paths[0]


def test_excluding_final_slide_updates_pause_audio_key_and_language_copy(project):
    from autotalk.services import synthesize
    make_audio(project)
    previous_key = project.speech_key(project.slides[0])
    project.slides[1].included = False
    project.set_setting("after", 'demo', project.slides[0])
    assert project.speech_key(project.slides[0]) != previous_key
    assert not project.ready(project.slides[0])
    requests = []
    class Session:
        def generate(self, request, on_event): requests.extend(request['items'])
    synthesize(project, Task(), session=Session())
    assert [item['pause'] for item in requests] == [0]
    project.add_version('German', translate=True)
    assert not project.slides[1].included and project.setting('after', project.slides[0]) == 'demo'
