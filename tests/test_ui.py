from conftest import make_audio
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer

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


def test_navigation_and_end_of_audio_share_one_slide_index(qtbot, project):
    make_audio(project)
    player = Playback()
    player.load(project)
    seen = []
    player.slide_changed.connect(seen.append)
    player.select(1)
    assert player.index == 1
    assert player.player.source().toLocalFile() == str(project.audio(project.slides[1]))
    player.step(-1)
    assert player.index == 0
    # Exercise the event delivered by the multimedia backend.
    player._status(QMediaPlayer.MediaStatus.EndOfMedia)
    assert player.index == 1
    player.stop()
    assert seen == [1, 0, 1]


def test_fullscreen_escape_stops_playback(qtbot, project):
    make_audio(project, seconds=10)
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.present()
    qtbot.waitUntil(lambda: window.presentation.isVisible())
    qtbot.keyClick(window.presentation, Qt.Key.Key_Escape)
    assert window.presentation is None
    assert window.transport.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
    assert window.tabs.isEnabled()


def test_real_media_advances_and_pause_preserves_position(qtbot, project):
    make_audio(project, seconds=1)
    player = Playback()
    player.load(project)
    player.play()
    qtbot.waitUntil(lambda: player.player.position() > 50, timeout=5000)
    player.toggle()
    position = player.player.position()
    qtbot.wait(150)
    assert player.player.position() == position
    assert player.index == 0
    player.toggle()
    qtbot.waitUntil(lambda: player.index == 1, timeout=5000)
    player.stop()
