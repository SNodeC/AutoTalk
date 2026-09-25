from conftest import make_audio
import pytest
from PySide6.QtCore import Qt

from autotalk.app import MainWindow
from autotalk.playback import Playback


def test_user_can_change_language_and_edit_narration(qtbot, project):
    make_audio(project)
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.show()
    assert window.present_button.isEnabled()
    window.language.setCurrentText("German")
    assert project.language == "German"
    assert not window.present_button.isEnabled()
    window.tabs.setCurrentIndex(1)
    window.narration.setPlainText("Dies ist ein Vortrag.")
    assert project.slides[0].narration == "Dies ist ein Vortrag."
    window.save()
    from autotalk.project import Project
    reopened = Project.load(project.manifest)
    assert reopened.language == "German"
    assert reopened.slides[0].narration == "Dies ist ein Vortrag."


@pytest.mark.audio_device
def test_navigation_and_end_of_audio_share_one_slide_index(qtbot, project):
    make_audio(project)
    player = Playback()
    player.load(project)
    seen = []
    player.slide_changed.connect(seen.append)
    player.select(1)
    assert player.index == 1
    player.step(-1)
    assert player.index == 0
    player.play()
    qtbot.waitUntil(lambda: player.index == 1, timeout=5000)
    assert player.index == 1
    player.stop()
    assert seen == [1, 0, 1]


@pytest.mark.audio_device
def test_fullscreen_escape_pauses_and_continue_preserves_position(qtbot, project):
    make_audio(project, seconds=10)
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.present()
    qtbot.waitUntil(lambda: window.presentation.isVisible())
    qtbot.waitUntil(lambda: window.transport.position > 0.05, timeout=5000)
    qtbot.keyClick(window.presentation, Qt.Key.Key_Escape)
    assert window.presentation is None
    assert window.transport.state == "paused"
    position = window.transport.position
    qtbot.wait(100)
    assert window.transport.position == position
    assert window.continue_button.isEnabled()
    window.continue_presentation()
    qtbot.waitUntil(lambda: window.transport.position > position, timeout=5000)
    window.stop_presentation()
    assert window.tabs.isEnabled()


@pytest.mark.audio_device
def test_real_media_advances_and_pause_preserves_position(qtbot, project):
    make_audio(project, seconds=1)
    player = Playback()
    player.load(project)
    player.play()
    qtbot.waitUntil(lambda: player.position > 0.05, timeout=5000)
    player.toggle()
    position = player.position
    qtbot.wait(150)
    assert player.position == position
    assert player.index == 0
    player.toggle()
    qtbot.waitUntil(lambda: player.index == 1, timeout=5000)
    player.stop()


@pytest.mark.parametrize("policy,starts", [("fit", True), ("once", True), ("require", False)])
def test_quick_autostart_respects_timing_policy(qtbot, project, monkeypatch, policy, starts):
    from autotalk import app
    window = MainWindow()
    qtbot.addWidget(window)
    project.mode, project.quick_timing = "Quick", policy
    window.adopt(project)
    presented = []
    monkeypatch.setattr(window, "present", lambda: presented.append(True))
    def prepared(p,task):
        make_audio(p)
        return p
    monkeypatch.setattr(app, "workflow", prepared)
    window.start_mode()
    qtbot.waitUntil(lambda: window.job is None, timeout=5000)
    assert bool(presented) is starts
    assert window.project.prepared and not window.project.within_target


def test_incomplete_realtime_talk_cannot_wait_for_a_missing_producer(qtbot, project):
    make_audio(project)
    project.mode = "Realtime"
    project.audio(project.slides[-1]).unlink()
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.transport.pause()
    window.refresh()
    assert not window.continue_button.isEnabled()
    assert not window.play_button.isEnabled()
    window.present()
    assert window.presentation is None
