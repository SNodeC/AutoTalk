"""Exercise channel mapping at the Linux audio server, without physical output."""
import json
import shutil
import subprocess
import sys
import uuid
import wave

import numpy as np
import pytest

from autotalk.media import RATE
from autotalk.playback import Playback


@pytest.mark.audio_device
@pytest.mark.skipif(sys.platform != "linux", reason="Linux PipeWire channel routing")
def test_mono_narration_reaches_both_stereo_channels(qtbot, tmp_path, monkeypatch):
    if not all(shutil.which(tool) for tool in ("pactl", "parec")):
        pytest.skip("Requires pactl and parec with a running PipeWire server")
    info = subprocess.run(["pactl", "info"], capture_output=True, text=True)
    if info.returncode or "PipeWire" not in info.stdout:
        pytest.skip("Requires a running PipeWire server")
    name = "autotalk_channels_" + uuid.uuid4().hex
    module = subprocess.check_output([
        "pactl", "load-module", "module-null-sink", "sink_name=" + name,
        "channels=2", "channel_map=front-left,front-right"], text=True).strip()
    monkeypatch.setenv("PIPEWIRE_PROPS", json.dumps({
        "application.name": name, "node.target": None, "target.object": name,
        "node.dont-reconnect": False}))
    source = tmp_path / "mono.wav"
    samples = (6000 * np.sin(np.arange(RATE) * 2*np.pi*440/RATE)).astype("<i2")
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(samples.tobytes())
    player, recorder, errors = None, None, []
    try:
        with (tmp_path / "stereo.pcm").open("wb") as output:
            recorder = subprocess.Popen([
                "parec", "--device=" + name + ".monitor", "--format=s16le",
                "--rate=" + str(RATE), "--channels=2",
                "--channel-map=front-left,front-right", "--latency-msec=20", "--raw"],
                stdout=output, stderr=subprocess.PIPE)
            qtbot.wait(200)
            player = Playback()
            player.failed.connect(errors.append)
            player.preview(source)
            qtbot.waitUntil(lambda: player.state == "finished" or bool(errors), timeout=5000)
            assert not errors
            qtbot.wait(200)
            recorder.kill()
            recorder.communicate(timeout=5)
        captured = np.frombuffer((tmp_path / "stereo.pcm").read_bytes(), dtype="<i2").reshape(-1, 2)
        assert len(captured) > RATE // 2
        levels = np.sqrt(np.mean(captured.astype(np.float64)**2, axis=0))
        assert min(levels) > 100, f"Left/right RMS levels: {levels}"
        assert levels[0] == pytest.approx(levels[1], rel=0.01)
    finally:
        if player:
            player.stop()
            player.timer.stop()
        if recorder and recorder.poll() is None:
            recorder.kill()
            recorder.communicate(timeout=5)
        subprocess.run(["pactl", "unload-module", module], check=True)
