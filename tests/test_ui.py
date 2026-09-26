from conftest import make_audio
import pytest
from PySide6.QtCore import Qt

from autotalk.app import MainWindow
from autotalk.playback import Playback


def test_recording_selection_visible_on_all_tabs_and_persisted(qtbot, project):
    from PySide6.QtCore import QPoint
    from autotalk.project import Project
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.resize(940, 680)
    window.show()
    checkbox = window.options.record
    for tab in range(window.tabs.count()):
        window.tabs.setCurrentIndex(tab)
        qtbot.wait(10)
        assert checkbox.isVisible() and checkbox.isEnabled()
        top = checkbox.mapTo(window, QPoint(0, 0))
        assert window.rect().contains(top)
        assert top.y() + checkbox.height() <= window.tabs.mapTo(window, QPoint(0, 0)).y()
    # The label and keyboard both operate the single project-backed checkbox.
    qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(55, checkbox.height()//2))
    assert project.record_presentation
    window.save()
    assert Project.load(project.manifest).record_presentation
    checkbox.setFocus()
    qtbot.keyClick(checkbox, Qt.Key.Key_Space)
    assert not project.record_presentation
    window.transport.state = 'paused'
    window.refresh()
    assert not checkbox.isEnabled()
    assert not window.options.recording_widget.isEnabled()
    window.transport.stop()
    window.refresh()
    assert checkbox.isEnabled()


def test_recording_selection_disabled_without_project(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert not window.options.record.isEnabled()


def test_recording_indicator_uses_recorded_time_and_clears_after_stop(qtbot, project):
    import numpy as np
    from autotalk.media import Capture, RATE
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    capture = Capture(project)
    try:
        window.transport.capture = capture
        capture.append(np.zeros((RATE, 2), dtype=np.int16), 1)
        window.update_timing()
        assert window.options.record.text() == 'Recording video • 0:01'
        assert window.transport.elapsed == 0  # Recording time is not narration time.
    finally:
        capture.close()
        window.transport.capture = None
    window.update_timing()
    assert window.options.record.text() == 'Record presentation as a video'


def test_controls_and_pdf_selector_follow_palette_changes(qtbot, qapp, project):
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QFileDialog, QLineEdit, QStyle, QStyleOptionButton
    previous_palette, previous_style = qapp.palette(), qapp.styleSheet()
    try:
        window = MainWindow()
        qtbot.addWidget(window)
        window.adopt(project)
        window.show()
        dialog = QFileDialog(window, 'Choose PDF', str(project.root))
        qtbot.addWidget(dialog)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.show()
        # Existing widgets must adopt palette updates, including a visible dialog.
        for background, foreground in [('#eff0f1', '#232627'), ('#31363b', '#eff0f1'), ('#eff0f1', '#232627')]:
            palette = QPalette(previous_palette)
            for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
                palette.setColor(role, QColor(background))
            for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
                palette.setColor(role, QColor(foreground))
            qapp.setPalette(palette)
            qtbot.waitUntil(lambda: window.palette().color(QPalette.ColorRole.Window) == QColor(background))
            qapp.processEvents()
            for widget in (window, window.options.record, window.start_button, window.play_image,
                           dialog, *dialog.findChildren(QLineEdit)):
                assert widget.palette().color(QPalette.ColorRole.Window) == QColor(background)
                assert widget.palette().color(QPalette.ColorRole.WindowText) == QColor(foreground)
                assert widget.palette().color(QPalette.ColorRole.Base) == QColor(background)
                assert widget.palette().color(QPalette.ColorRole.Text) == QColor(foreground)
            checkbox = window.options.record
            option = QStyleOptionButton()
            checkbox.initStyleOption(option)
            indicator = checkbox.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox)
            assert indicator.width() > 0 and indicator.height() > 0
            checkbox.setChecked(False)
            qtbot.wait(300)  # Native styles animate the check mark; let unchecking finish.
            unchecked = checkbox.grab().toImage()
            checkbox.setChecked(True)
            qtbot.waitUntil(lambda: checkbox.grab().toImage() != unchecked)
        dialog.close()
    finally:
        qapp.setPalette(previous_palette)
        qapp.setStyleSheet(previous_style)


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
    project.accept_script()  # This test starts from a reviewed existing script.
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
