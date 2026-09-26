from conftest import make_audio
import pytest
from PySide6.QtCore import Qt

from autotalk.app import MainWindow
from autotalk.playback import Playback


def test_recording_selection_visible_in_workspaces_and_persisted(qtbot, project):
    from PySide6.QtCore import QPoint
    from autotalk.project import Project
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.resize(940, 680)
    window.show()
    checkbox = window.options.record
    for page in (window.editor, window.presenter, window.quick_page):
        window.workspace.setCurrentWidget(page)
        qtbot.wait(10)
        assert checkbox.isVisible() and checkbox.isEnabled()
        top = checkbox.mapTo(window, QPoint(0, 0))
        assert window.rect().contains(top)
        assert top.y() + checkbox.height() <= window.height()
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
    assert window.options.record.text() == 'Record presentation as a video · Slide video + narration'


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
            # The prototype's primary action follows the system accent and its
            # contrasting text role; other controls use normal system surfaces.
            assert window.start_button.palette().color(QPalette.ColorRole.Button) == palette.color(QPalette.ColorRole.Highlight)
            assert window.start_button.palette().color(QPalette.ColorRole.ButtonText) == palette.color(QPalette.ColorRole.HighlightedText)
            for widget in (window, window.options.record, window.play_image,
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
    window.workspace.setCurrentWidget(window.editor)
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
    assert window.start_button.isEnabled()


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
    def prepared(p,task):
        make_audio(p)
        return p
    monkeypatch.setattr(app, "workflow", prepared)
    window.start_mode()
    qtbot.waitUntil(lambda: window.job is None, timeout=5000)
    assert (window.presentation is not None) is starts
    assert window.start_button.text() == "Start" and window.start_button.isEnabled()
    window.start_button.click()
    assert (window.presentation is not None) is starts
    window.stop_presentation()
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


def test_settings_open_and_save_preserve_selected_slide(qtbot, project):
    from PySide6.QtWidgets import QDialogButtonBox
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.show()
    window.transport.select(1)
    original = window.project
    window.talk_action.trigger()
    assert window.talk_dialog.isVisible()
    assert window.project is original and window.transport.index == 1
    window.minutes.setValue(14)
    qtbot.mouseClick(window.talk_dialog.buttons.button(QDialogButtonBox.StandardButton.Save), Qt.MouseButton.LeftButton)
    assert not window.talk_dialog.isVisible()
    assert window.project is original and window.transport.index == 1
    from autotalk.project import Project
    assert Project.load(project.manifest).target_minutes == 14


def test_cancel_settings_restores_project_and_manifest_after_eager_save(qtbot, project):
    from autotalk.project import Project
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.show()
    window.transport.select(1)
    window.talk_dialog.show_section()
    window.minutes.setValue(19)
    window.scope.setPlainText('A different conference')
    window.language.setCurrentText('German')
    window.save()  # Existing language/reference/worker handlers can save eagerly.
    window.talk_dialog.reject()
    restored = Project.load(project.manifest)
    assert restored.target_minutes == 10 and restored.language == 'English'
    assert restored.scope != 'A different conference'
    assert len(restored.versions) == 1
    assert window.project.language == 'English' and window.transport.index == 1
    assert window.options.project is window.project
    assert window.transport.project is window.project


def test_preferences_cancel_restores_retention_and_sampling(qtbot, project):
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.show()
    original = window.gpu_retention.checkedButton().property("value")
    window.preferences_dialog.show_section(1)
    next(b for b in window.gpu_retention.buttons() if b.property('value') == 'operation').click()
    assert window.speech.retention == original  # Draft policies do not act before Save.
    window.preferences_dialog.reject()
    assert window.gpu_retention.checkedButton().property("value") == original
    assert window.speech.retention == original
    window.talk_dialog.show_section(6)
    window.options.override.setChecked(True)
    window.options.sampling['temperature'].setValue(.4)
    window.talk_dialog.reject()
    assert window.project.delivery.sampling == {}


def test_quick_reuses_settings_fields_without_losing_edits(qtbot, project):
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.resize(940, 680)
    window.show()
    window.mode.setCurrentText('Quick')
    qtbot.wait(30)
    assert window.minutes.isVisible() and window.language.isVisible()
    window.minutes.setValue(7)
    assert project.target_minutes == 7
    window.talk_dialog.show_section()
    assert window.basics.parentWidget() is window.general_form
    window.minutes.setValue(9)
    window.talk_dialog.reject()
    qtbot.wait(30)
    assert window.basics.parentWidget() is window.quick_form
    assert window.minutes.value() == window.project.target_minutes == 7
    assert window.language.isVisible()
    from PySide6.QtCore import QPoint
    bottom = window.language.mapTo(window, QPoint(0, window.language.height()))
    assert window.workspace.geometry().contains(bottom)


def test_commands_and_dialogs_cannot_bypass_job_or_playback_lock(qtbot, project):
    from threading import Event
    window = MainWindow()
    qtbot.addWidget(window)
    make_audio(project)
    window.adopt(project)
    window.show()
    window.talk_dialog.show_section(1)
    release = Event()
    window.start_job('Checking command availability', lambda task: release.wait(5))
    try:
        assert not window.talk_action.isEnabled()
        assert window.narration.isReadOnly()
        assert not window.talk_dialog.pages.isEnabled()
        assert not window.present_button.isEnabled()
        assert not window.welcome.isEnabled()
        assert all(not a.isEnabled() for a in window.actions)
        for action, control in window.control_actions:
            assert action.isEnabled() == control.isEnabled()
        window.talk_dialog.reject()
        assert window.talk_dialog.isVisible()
    finally:
        release.set()
        qtbot.waitUntil(lambda: window.job is None)
    window.talk_dialog.reject()
    window.transport.state = 'paused'
    window.refresh()
    assert window.narration.isReadOnly() and not window.talk_action.isEnabled()
    assert window.continue_button.isEnabled()
    assert not window.options.record.isEnabled()
    window.stop_presentation()
    assert not window.narration.isReadOnly() and window.talk_action.isEnabled()


def test_minimum_editor_layout_keeps_inspector_controls_separate(qtbot, project):
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.resize(940, 680)
    window.show()
    qtbot.wait(30)
    from PySide6.QtCore import QPoint
    window.clip_gain.window().show()
    qtbot.wait(30)
    gain_bottom = window.clip_gain.mapToGlobal(QPoint(0, window.clip_gain.height()))
    placement_top = window.clip_placement.mapToGlobal(QPoint(0, 0))
    assert placement_top.y() >= gain_bottom.y()
    assert window.image.height() >= 100
    assert window.narration.height() >= 100


def test_recording_dialog_uses_same_checkbox_and_cancel_restores_choice(qtbot, project):
    window = MainWindow()
    qtbot.addWidget(window)
    window.adopt(project)
    window.show()
    checkbox = window.options.record
    window.talk_dialog.show_section(5)
    qtbot.waitUntil(checkbox.isVisible)
    assert checkbox.parentWidget() is window.recording_form
    from PySide6.QtCore import QPoint
    qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(40, checkbox.height()//2))
    assert window.project.record_presentation
    window.talk_dialog.reject()
    assert not window.project.record_presentation
    qtbot.waitUntil(checkbox.isVisible)
    assert checkbox.parentWidget() is window.record_footer


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
def test_numeric_editors_fit_native_style_geometry(qtbot, project, mode):
    from PySide6.QtWidgets import QAbstractSpinBox, QSpinBox, QStyle, QStyleOptionSpinBox
    project.mode = mode
    window = MainWindow(); qtbot.addWidget(window); window.adopt(project)
    window.resize(940, 680); window.show()
    seen = set()
    for section in range(window.talk_dialog.navigation.count()):
        window.talk_dialog.show_section(section)
        qtbot.wait(1)
        for spin in window.findChildren(QAbstractSpinBox):
            if not spin.isVisible():
                continue
            option = QStyleOptionSpinBox(); spin.initStyleOption(option)
            expected = spin.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option,
                                                  QStyle.SubControl.SC_SpinBoxEditField, spin)
            assert spin.lineEdit().geometry() == expected, (spin.text(), spin.lineEdit().geometry(), expected)
            assert spin.rect().contains(spin.lineEdit().geometry())
            seen.add(type(spin))
    assert QSpinBox in seen and len(seen) >= 2
    window.talk_dialog.reject()
