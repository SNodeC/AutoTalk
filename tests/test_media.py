import json
import wave

import av
import numpy as np
import pytest

from autotalk.media import AudioFile, Capture, RATE, export_recording, import_clip
from autotalk.runtime import Task


@pytest.mark.parametrize("policy, expected", [("fullscreen", 3600), ("all", 6000), ("content", 1200)])
def test_recording_policy_and_slide_journal(project, policy, expected):
    project.recording_policy = policy
    capture = Capture(project)
    capture.append(np.ones(1200, dtype=np.int16), 1)
    capture.waiting(0.1, 1, True)
    capture.waiting(0.1, 2, False)
    root = capture.close()
    assert (root / "audio.pcm").stat().st_size == expected * 2
    journal = [json.loads(l) for l in (root / "events.jsonl").read_text().splitlines()]
    assert journal[0] == {"frame": 0, "slide": 1}
    if policy == "all":
        assert journal[-1] == {"frame": 3600, "slide": 2}


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
