import json
import wave

import av
import numpy as np
import pytest

from autotalk.media import AudioFile, Capture, RATE, export_recording, import_clip
from autotalk.runtime import Task


@pytest.mark.parametrize('outcome', ['success', 'cancel', 'invalid'])
def test_export_releases_pdf_even_when_an_exception_retains_its_frame(project, monkeypatch, outcome):
    from autotalk import media
    from autotalk.runtime import Cancelled
    from shiboken6 import isValid
    documents = []
    original = media.QPdfDocument
    class Document(original):
        def __init__(self):
            super().__init__()
            documents.append(self)
    monkeypatch.setattr(media, 'QPdfDocument', Document)
    capture = Capture(project)
    capture.append(np.ones((RATE//10, 2), dtype=np.int16), 1)
    root = capture.close()
    task = Task(report=lambda _: None)
    if outcome == 'cancel':
        task.cancelled.set()
    if outcome == 'invalid':
        (root/'slides.pdf').write_bytes(b'invalid pdf')
    if outcome == 'success':
        assert export_recording(root, task).is_file()
    else:
        with pytest.raises(Cancelled if outcome == 'cancel' else ValueError):
            export_recording(root, task)
    assert documents and all(not isValid(d) for d in documents)


@pytest.mark.parametrize("policy, expected", [("fullscreen", 6000), ("all", 10800), ("content", 1200)])
def test_recording_policy_and_slide_journal(project, policy, expected):
    project.recording_policy = policy
    capture = Capture(project)
    capture.append(np.ones(1200, dtype=np.int16), 1)
    capture.waiting(0.1, 1, True)
    capture.waiting(0.1, 2, False)
    root = capture.close()
    assert (root / "audio.pcm").stat().st_size == expected * 4
    journal = [json.loads(l) for l in (root / "events.jsonl").read_text().splitlines()]
    assert journal[0] == {"frame": 0, "slide": 1}
    if policy == "all":
        assert journal[-1] == {"frame": 6000, "slide": 2}


@pytest.mark.parametrize("rate", [24000, 44100, 48000])
def test_export_contains_timed_slides_and_selected_audio_rate(project, rate):
    project.export_rate = rate
    project.recording_policy = "content"
    capture = Capture(project)
    for slide in (1, 2):
        samples = (3000 * np.sin(np.arange(RATE//5) * 2*np.pi*440/RATE)).astype("<i2")
        capture.append(samples, slide)
    root = capture.close()
    destination = export_recording(root, Task(lambda _: None))
    with av.open(str(destination)) as container:
        assert container.streams.audio[0].rate == rate
        assert container.streams.video[0].width == 1920
        images = list(container.decode(video=0))
        assert len(images) == 12
        assert not np.array_equal(images[0].to_ndarray(), images[-1].to_ndarray())
        assert abs(container.duration/av.time_base - 0.4) < 0.1


def test_import_normalizes_audio_and_loop_gain(project, tmp_path):
    source = tmp_path / "stereo.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        wav.writeframes(np.full((4800, 2), 1000, dtype="<i2").tobytes())
    clip = import_clip(project, source, Task(lambda _: None))
    audio = AudioFile(project.asset(clip.file), gain=0.5, loop=True)
    assert clip.seconds == 0.1
    assert len(audio.read(audio.frames-10, 30)) == 30
    assert 400 < np.mean(audio.read(20, 30)) < 800


def test_separate_recordings_have_distinct_destinations(project, tmp_path):
    project.recording_destination = str(tmp_path / "talk.mp4")
    first, second = Capture(project), Capture(project)
    assert first.destination != second.destination
    first.close()
    second.close()


@pytest.fixture
def retained_readers(monkeypatch):
    """Retain diagnostic references so cleanup cannot depend on CPython refcounts."""
    from autotalk import media, playback
    readers = []
    class Retained(AudioFile):
        def __init__(self, *args, **kwargs):
            readers.append(self)
            super().__init__(*args, **kwargs)
    monkeypatch.setattr(media, 'AudioFile', Retained)
    monkeypatch.setattr(playback, 'AudioFile', Retained)
    return readers


def test_mix_replacement_releases_superseded_assets(project, retained_readers):
    from autotalk.media import Mix
    from conftest import make_audio
    make_audio(project)
    mix = Mix(project)
    old = list(retained_readers)
    mix.update(0)
    assert old[0].stream.closed and not old[1].stream.closed
    assert len(mix.read(0, 0, 120)) == 120
    project.slides[1].included = False
    mix.update(1)
    assert old[1].stream.closed
    mix.close()
    assert all(r.stream.closed for r in retained_readers)


@pytest.mark.parametrize('failure', ['capture', 'read', 'cancel', 'success', 'invalid_audio'])
def test_export_closes_audio_even_with_retained_traceback(project, retained_readers, monkeypatch, tmp_path, failure):
    from autotalk import media
    from autotalk.runtime import Cancelled
    from conftest import make_audio
    make_audio(project)
    task = Task(lambda _: None)
    if failure == 'cancel': task.cancelled.set()
    if failure == 'capture':
        def fail(*args, **kwargs): raise OSError('Capture failed')
        monkeypatch.setattr(media, 'Capture', fail)
    elif failure == 'read':
        def fail(*args, **kwargs): raise OSError('Read failed')
        monkeypatch.setattr(media.Mix, 'read', fail)
    elif failure == 'invalid_audio':
        project.audio(project.slides[1]).write_bytes(b'invalid wave')
    if failure == 'success':
        assert media.export_prepared(project, task, tmp_path/'out.wav').exists()
    else:
        with pytest.raises((OSError, EOFError, wave.Error, Cancelled)) as captured:
            media.export_prepared(project, task, tmp_path/'out.wav')
        assert captured.traceback  # Deliberately still alive when checking handles.
    assert retained_readers and all(r.stream.closed for r in retained_readers)


def test_preview_project_change_and_shutdown_release_audio(qtbot, project, retained_readers):
    from autotalk.app import MainWindow
    from conftest import make_audio
    make_audio(project, seconds=3)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    project_readers = list(retained_readers)
    w.preview_button.click()
    preview = retained_readers[-1]
    w.transport.pause()
    assert not preview.stream.closed
    w.preview_button.click()
    assert preview.stream.closed
    assert all(not reader.stream.closed for reader in project_readers)
    w.adopt(project)
    assert all(reader.stream.closed for reader in project_readers)
    w.close()
    assert all(reader.stream.closed for reader in retained_readers)


def test_failed_mix_update_keeps_old_audio_and_closes_partial_replacement(project, retained_readers, tmp_path):
    from autotalk.media import Mix
    from autotalk.project import Clip
    from conftest import make_audio
    make_audio(project)
    mix = Mix(project)
    previous = retained_readers[0]
    expected = mix.read(0, 0, 120)
    invalid = project.asset('bad.wav'); invalid.write_bytes(b'bad wave')
    project.slides[0].clips = [
        Clip(project.slides[0].audio_file, '', .3, 'before'),
        Clip('bad.wav', '', .3, 'after')]
    with pytest.raises((EOFError, wave.Error)) as captured:
        mix.update(0)
    assert captured.traceback and not previous.stream.closed
    assert all(r.stream.closed for r in retained_readers[2:])
    assert np.array_equal(mix.read(0, 0, 120), expected)
    mix.close()


def test_repeated_background_and_stream_updates_bound_owned_handles(project, retained_readers):
    from autotalk.media import Mix
    from autotalk.project import Clip
    from conftest import make_audio
    make_audio(project)
    project.background = Clip(project.slides[0].audio_file, '', .3)
    mix = Mix(project)
    for _ in range(20):
        mix.update()
        assert sum(not r.stream.closed for r in retained_readers) == 3
    project.background = None
    mix.update()
    assert sum(not r.stream.closed for r in retained_readers) == 2
    slide = project.slides[0]; slide.audio_key = ''
    with wave.open(str(project.audio(slide)), 'rb') as wav:
        frames = wav.getnframes()
    with project.audio(slide).open('rb') as stream:
        with wave.open(stream, 'rb') as wav:
            offset = stream.tell()
    for _ in range(20):
        mix.update(0, {'key':project.speech_key(slide),'path':str(project.audio(slide)), 'frames':frames,'offset':offset})
        assert sum(not r.stream.closed for r in retained_readers) == 2
        assert len(mix.read(0, 0, 120)) == 120
    mix.close()
    assert all(r.stream.closed for r in retained_readers)


@pytest.mark.parametrize('paused', [False, True])
def test_selecting_a_slide_ends_preview_without_starting_a_presentation(qtbot, project, retained_readers, paused):
    from PySide6.QtCore import Qt
    from autotalk.app import MainWindow
    from conftest import make_audio
    make_audio(project, seconds=3)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.preview_button.click()
    preview = retained_readers[-1]
    if paused: w.transport.pause()
    next_slide = w.slide_list.visualItemRect(w.slide_list.item(1)).center()
    qtbot.mouseClick(w.slide_list.viewport(), Qt.LeftButton, pos=next_slide)
    assert w.transport.index == 1 and w.transport.state == 'stopped'
    assert not w.transport.active and not w.transport.preview_path
    assert preview.stream.closed and w.transport.preview_audio is None
    assert w.slide_audio_button.isEnabled() and w.narration.isEnabled() and w.mode.isEnabled()
