# SPDX-License-Identifier: MIT
"""User journeys through the existing project, job and playback boundaries."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from conftest import make_audio
from autotalk import app, services
from autotalk import settings
from autotalk.app import MainWindow
from autotalk.media import Capture, RATE
from autotalk.runtime import Cancelled, Task


def test_open_pdf_has_one_dialog_and_non_destructive_default_location(qtbot, sample_pdf, monkeypatch):
    projects = sample_pdf.parent / 'autotalk'
    monkeypatch.setattr(app.QFileDialog, 'getOpenFileName', lambda *a: (str(sample_pdf), 'PDF'))
    monkeypatch.setattr(app.QFileDialog, 'getExistingDirectory', lambda *a: pytest.fail('Unexpected folder dialog'))
    w = MainWindow(); qtbot.addWidget(w); w.show()
    for suffix in ('', '-2'):
        w.new_project()
        qtbot.waitUntil(lambda: w.job is None, timeout=5000)
        assert w.project.root == projects / ('slides-AutoTalk' + suffix)
        assert w.project.manifest.is_file()
        assert w.start_button.text() == 'Prepare and start'
        assert 'Start reuses current audio' in w.status.text()
        assert w.settings[1].isVisible() and w.minutes.isVisible() and w.audience.isVisible()
        w.settings[1].accept()
    assert (projects / 'slides-AutoTalk/talk.autotalk.json').is_file()


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
def test_mode_start_label_is_stable_after_manual_edits(qtbot, project, monkeypatch, mode):
    project.mode = mode
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    caption = 'Prepare and start' if mode == 'Prepared' else 'Start'
    calls = []
    monkeypatch.setattr(w, 'prepare_and_present', lambda: calls.append(True))
    for text in ('My edited narration.', '', 'Restored words.'):
        w.narration.setPlainText(text)
        assert w.start_button.text() == w.start_action.text() == caption
        assert w.start_button.isVisible() and w.start_button.isEnabled()
        w.start_button.click()
    assert calls == [True] * 3
    w.minutes.setValue(5)
    assert 'Talk length changed' in w.status.text()
    assert w.start_button.text() == caption
    assert not any('Approve' in b.text() for b in w.findChildren(QPushButton))

def test_voice_source_shows_only_its_own_workflow(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings[1].show_section("Voice & language")
    designed = next(b for b in w.settings[1].findChildren(QPushButton) if b.text() == 'Use this designed voice')
    for source in ('CustomVoice', 'Base', 'VoiceDesign', 'CustomVoice'):
        w.settings[1].voice_source.setCurrentIndex(["CustomVoice", "Base", "VoiceDesign"].index(source))
        assert w.settings[1].speaker.isVisible() == (source == 'CustomVoice')
        assert w.settings[1].record_button.isVisible() == (source == 'Base')
        assert w.settings[1].transcript.isVisible() == (source == 'Base')
        assert w.settings[1].voice_description.isVisible() == (source == 'VoiceDesign')
        assert designed.isVisible() == (source == 'VoiceDesign')
        assert w.settings[1].voice_preview_button.isVisible()
    w.settings[1].reject()


def test_presenter_offers_one_action_and_explicit_recording_end(qtbot, project):
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.workspace.setCurrentWidget(w.presenter)
    actions = (w.play_button, w.continue_button)
    for state, expected in [('stopped', None), ('playing', w.play_button), ('paused', w.continue_button)]:
        w.transport.state = state
        w.refresh()
        assert [b for b in actions if b.isVisible()] == ([expected] if expected else [])
        assert expected is None or expected.isEnabled()
        assert w.start_button.isVisible() and w.start_button.isEnabled()
    capture = Capture(project)
    try:
        capture.append(np.zeros((RATE, 2), dtype='<i2'), 1)
        w.transport.capture = capture
        w.transport.state = 'finished'
        w.refresh()
        assert 'Slides finished — recording continues' in w.record_status.text()
        assert w.end_button.text() == w.end_action.text() == 'End presentation and save video'
        assert w.end_button.isEnabled()
        assert not any(b.isVisible() for b in actions)
    finally:
        capture.close(); w.transport.capture = None; w.transport.stop()


def test_interrupted_realtime_has_a_visible_resume_preparation(qtbot, project):
    project.mode = 'Realtime'
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.workspace.setCurrentWidget(w.presenter)
    w.transport.state = 'paused'; w.refresh()
    assert w.start_button.isVisible() and w.start_button.isEnabled()
    assert w.start_button.text() == 'Start'
    assert not hasattr(w, "present_button") and not w.continue_button.isVisible()
    w.transport.stop()


def test_recording_browser_empty_then_saved_and_legacy_recovery(qtbot, project, tmp_path, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.export_dialog.show_section()
    assert w.recordings_empty.isVisible() and not w.recover_button.isEnabled()
    monkeypatch.setattr(app.QFileDialog, 'getOpenFileName', lambda *a: pytest.fail('No metadata chooser'))
    w.recover_recording()
    capture = Capture(project); capture.append(np.zeros((RATE, 2), dtype='<i2'), 1)
    root = capture.close()
    info = json.loads((root / 'session.json').read_text())
    assert info['title'] == project.title and info['started_at'] > 0
    w.refresh_recordings()
    assert not w.recordings_empty.isVisible() and w.recover_button.isEnabled()
    assert w.recordings.item(0, 0).text() == project.title
    assert w.recordings.item(0, 2).text() == '0:01'
    assert w.recordings.item(0, 3).text() == 'Needs saving'
    assert w.recover_button.text() == 'Save unfinished recording…'
    output = tmp_path / 'video.mp4'; output.write_bytes(b'exported')
    info['output'] = str(output); (root / 'session.json').write_text(json.dumps(info))
    w.export_saved(output); w.update_timing()
    assert w.recordings.item(0, 3).text() == 'Ready'
    assert w.recover_button.text() == 'Save another format…'
    assert 'Saved ' in w.saved_output.text() and w.output_button.isEnabled()
    # Older recoverable recordings have no title/date fields or project manifest.
    del info['title']; del info['started_at']
    (root / 'session.json').write_text(json.dumps(info)); project.manifest.unlink()
    w.refresh_recordings()
    assert w.recordings.rowCount() == 1 and w.recordings.item(0, 0).text() == project.title
    w.export_dialog.reject()


def test_prepared_export_without_session_still_has_open_links(qtbot, project, tmp_path):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    output = tmp_path / 'prepared.mp4'; output.write_bytes(b'exported')
    w.start_job("Exporting prepared talk…", lambda task: output, w.export_saved)
    qtbot.waitUntil(lambda: w.job is None)
    assert w.output_path == str(output)
    assert w.output_button.isEnabled() and w.folder_button.isEnabled()
    assert 'Open video' in w.saved_output.text()


def test_recording_intent_and_saving_are_not_reported_as_finished(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    w.record.setChecked(True); w.update_timing()
    assert w.record_status.text() == 'Will record when presentation starts'
    w.pending_exports.append(project.root); w.update_timing()
    assert w.record_status.text() == 'Saving video…'
    w.pending_exports.clear()
    w.job = SimpleNamespace(title='Saving presentation video…')
    try:
        w.update_timing()
        assert w.record_status.text() == 'Saving video…'
    finally:
        w.job = None


@pytest.mark.parametrize('mode', ['Quick', 'Realtime', 'fit'])
def test_sign_in_failure_prevents_expensive_speech_loading(project, monkeypatch, mode):
    from contextlib import contextmanager
    @contextmanager
    def signin(task):
        raise Cancelled('Sign-in cancelled')
        yield  # context manager must acquire before any speech setup.
    monkeypatch.setattr(services, 'Codex', signin)
    @contextmanager
    def speech(*args):
        pytest.fail('Speech loaded before sign-in')
        yield
    monkeypatch.setattr(services, 'speech_session', speech)
    if mode == 'fit':
        operation = lambda: services.prepare(project, Task(), fit=True)
    else:
        project.mode = mode
        for slide in project.slides:
            slide.narration = ''
        operation = lambda: services.workflow(project, Task())
    with pytest.raises(Cancelled, match='Sign-in cancelled'):
        operation()


@pytest.mark.parametrize('mode', ['Quick', 'Realtime'])
def test_audio_only_resume_does_not_require_chatgpt(project, monkeypatch, mode):
    from contextlib import nullcontext
    project.mode = mode; project.quick_timing = 'once'
    monkeypatch.setattr(services, 'Codex', lambda *a: pytest.fail('No text generation needed'))
    monkeypatch.setattr(services, 'speech_session', lambda *a: nullcontext())
    monkeypatch.setattr(services, 'synthesize', lambda p, t, **kw: make_audio(p))
    services.workflow(project, Task())
    assert project.prepared


def test_language_draft_accepts_manual_text_without_approval(qtbot, project, monkeypatch):
    from autotalk.project import Project
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    original = project.active_version
    text = [s.narration for s in project.slides]
    monkeypatch.setattr('autotalk.app.QInputDialog.getItem', lambda *a, **kw: ('German', True))
    w.add_version()
    assert w.start_button.text() == 'Prepare and start'
    assert 'Source text — waiting for German translation' in w.slide_info.text()
    assert 'German — German' not in w.language.currentText()
    assert not any(s.text_ready for s in project.slides)
    for index, slide in enumerate(project.slides):
        w.slide_list.setCurrentRow(index)
        w.narration.setPlainText(f'Dies ist die Erklärung für Folie {slide.page}.')
        assert slide.text_ready
        assert w.start_button.isEnabled()
    assert w.save()
    reopened = Project.load(project.manifest)
    assert reopened.language == 'German' and all(s.text_ready for s in reopened.slides)
    assert [s.narration for s in reopened.versions[original].slides] == text

def test_previous_video_does_not_override_new_recording_intent(qtbot, project, tmp_path, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    video = tmp_path / 'previous.mp4'; video.write_bytes(b'video')
    w.export_saved(video)
    w.record.click()
    assert 'Will record when presentation starts' in w.record_status.text()
    assert 'Saved ' in w.saved_output.text() and 'Open video' in w.saved_output.text()
    w.settings[1].options.fields['recording_source'].setCurrentIndex(w.settings[1].options.fields['recording_source'].findData('screen'))
    assert 'Screen + system audio' in w.record.toolTip()
    monkeypatch.setattr('autotalk.app.QInputDialog.getItem', lambda *a, **kw: ('German', True))
    w.add_version()
    assert 'Will record when presentation starts' in w.record_status.text()
    video.unlink()
    w.update_timing()  # An externally removed video must not crash the UI timer.
    assert 'Saved ' not in w.saved_output.text()


def test_voice_actions_follow_reference_and_current_design(qtbot, project, tmp_path, monkeypatch):
    import wave
    monkeypatch.setattr(services, 'data_dir', lambda: tmp_path)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings[1].show_section("Voice & language")
    assert 'Energetic male' in w.settings[1].speaker.currentText()
    w.settings[1].speaker.setCurrentIndex(w.settings[1].speaker.findData('Aiden'))
    assert project.voice.speaker == 'Aiden'
    w.settings[1].voice_source.setCurrentIndex(1)
    assert not w.settings[1].voice_preview_button.isEnabled() and not w.settings[1].save_voice_button.isEnabled()
    w.settings[1].voice_source.setCurrentIndex(2)
    assert not w.settings[1].voice_preview_button.isEnabled() and not w.settings[1].accept_voice_button.isEnabled()
    w.settings[1].voice_description.setText('Warm, calm and clear')
    assert w.settings[1].voice_preview_button.isEnabled() and not w.settings[1].accept_voice_button.isEnabled()
    path = services.preview_path(project); path.parent.mkdir(parents=True)
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0\0' * 4 * 24000)
    w.refresh()
    assert w.settings[1].accept_voice_button.isEnabled()
    w.settings[1].voice_description.setText('An entirely different voice')
    assert not w.settings[1].accept_voice_button.isEnabled()
    w.settings[1].voice_description.setText('Warm, calm and clear')
    w.settings[1].accept_voice_button.click()
    assert project.voice.source == 'Base' and project.asset(project.voice_file).is_file()
    assert w.settings[1].voice_preview_button.isEnabled()
    w.settings[1].accept()


def test_operation_feedback_is_in_the_active_dialog(qtbot, project):
    import threading
    release = threading.Event()
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings[1].show_section("Voice & language")
    try:
        w.start_job('Generating voice preview…', lambda task: release.wait(3))
        qtbot.wait(300)
        assert w.progress.isVisible() and w.progress.parentWidget() is w.settings[1]
        assert 'Waiting ' in w.settings[1].status.text()
        assert w.settings[1].cancel_job.isVisible() and w.settings[1].cancel_job.isEnabled()
    finally:
        release.set()
        qtbot.waitUntil(lambda: w.job is None)
    assert not w.progress.isVisible()
    w.settings[1].accept()
    assert w.progress.parentWidget() is w.footer
    assert "Start reuses current audio" in w.status.text()


def test_inapplicable_options_and_recording_browser_priorities(qtbot, project, monkeypatch, tmp_path):
    from autotalk import options
    monkeypatch.setattr(options, 'data_dir', lambda: tmp_path)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert not w.settings[1].options.use_preset_button.isEnabled()
    w.settings[1].show_section("Presentation & recording")
    assert not w.remove_background_button.isEnabled() and w.settings[1].background_gain.isEnabled()
    assert w.settings[1].background_gain.value() == 15 and w.settings[1].background_gain.suffix() == ' %'
    w.settings[1].accept()
    w.export_dialog.show_section()
    assert w.output_button.property('primary') and not w.export_button.property('primary')
    assert w.export_button.y() > w.recordings.y()
    w.export_dialog.accept()
    w.settings[1].show_section("Talk & preparation")
    assert w.fit_button.isVisible()
    w.settings[1].reject()
    assert project.slides[0].source_text.splitlines()[0] in w.slide_list.item(0).text()


def test_fullscreen_mouse_controls_and_finished_return(qtbot, project):
    from PySide6.QtCore import QPoint
    make_audio(project, seconds=10)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.start_button.click()
    fullscreen = w.presentation
    assert fullscreen is not None
    qtbot.mouseMove(fullscreen, QPoint(20, fullscreen.height()-25))
    qtbot.waitUntil(lambda: fullscreen.controls.isVisible())
    qtbot.mouseClick(fullscreen.controls.widgetForAction(fullscreen.toggle_action), Qt.MouseButton.LeftButton)
    assert w.transport.state == 'paused'
    assert fullscreen.toggle_action.text() == 'Continue'
    qtbot.mouseClick(fullscreen.controls.widgetForAction(fullscreen.toggle_action), Qt.MouseButton.LeftButton)
    assert w.transport.playing
    assert not w.previous_action.isEnabled() and w.next_action.isEnabled()
    qtbot.mouseClick(fullscreen.controls.widgetForAction(w.next_action), Qt.MouseButton.LeftButton)
    assert w.transport.index == 1 and w.previous_action.isEnabled()
    qtbot.mouseClick(fullscreen.controls.widgetForAction(w.previous_action), Qt.MouseButton.LeftButton)
    assert w.transport.index == 0
    w.transport.select(len(project.slides)-1)
    w.transport.step(1)
    assert w.transport.state == 'finished' and not fullscreen.toggle_action.isEnabled()
    assert fullscreen.controls.isVisible() and w.end_action.text() == 'Return to editing'
    qtbot.mouseClick(fullscreen.controls.widgetForAction(w.end_action), Qt.MouseButton.LeftButton)
    assert w.presentation is None and w.workspace.currentWidget() is w.editor
    assert w.transport.state == 'stopped'


def test_enlargement_keeps_the_current_slide_inside_autotalk(qtbot, project, monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QDialog
    from autotalk.app import SlideImage
    monkeypatch.setattr(app.QDesktopServices, 'openUrl', lambda url: pytest.fail('Unexpected external viewer'))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.slide_list.setCurrentRow(1)
    viewed = []
    def inspect():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QDialog):
            image = dialog.findChild(SlideImage)
            viewed.append((dialog.windowTitle(), image.original.toImage(), image.size()))
            dialog.accept()
    timer = QTimer(); timer.timeout.connect(inspect); timer.start(50)
    try:
        button = next(b for b in w.findChildren(QPushButton) if b.text() == 'Enlarge slide…')
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    finally:
        timer.stop()
    assert len(viewed) == 1 and viewed[0][0] == 'Slide 2'
    assert viewed[0][1] == w.image.original.toImage()
    assert viewed[0][2].width() > w.image.width() and viewed[0][2].height() > w.image.height()
    assert w.transport.index == 1 and w.workspace.currentWidget() is w.editor


def test_automatic_recording_save_cannot_resume_finished_fullscreen(qtbot, project):
    make_audio(project, seconds=.2)
    project.record_presentation = True
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.start_button.click()
    view = w.presentation
    qtbot.waitUntil(lambda: w.transport.state == 'finished' and w.job is None and not w.pending_exports, timeout=10000)
    assert Path(w.output_path).is_file()
    assert not view.toggle_action.isEnabled()
    qtbot.keyClick(view, Qt.Key.Key_Space)
    assert w.transport.state == 'finished' and w.transport.capture is None
    assert w.end_action.text() == 'Return to editing'
    qtbot.mouseClick(view.controls.widgetForAction(w.end_action), Qt.MouseButton.LeftButton)
    assert w.presentation is None and w.workspace.currentWidget() is w.editor


def test_translation_keeps_manually_replaced_slides(project, monkeypatch):
    project.add_version('German', translate=True)
    project.slides[0].narration = 'Meine eigene Erklärung.'
    def translated(p, task, client, fit, pages):
        assert pages == [2]
        return {'title': 'Übersetzter Titel', 'slides': [{'page': 2, 'narration': 'Die zweite Folie.',
                 'notes': '', 'budget_seconds': 12}]}
    from contextlib import nullcontext
    monkeypatch.setattr(services, 'Codex', lambda task: nullcontext())
    monkeypatch.setattr(services, 'narration_result', translated)
    result = services.narrate(project, Task(), pages=[2])
    assert result.slides[0].narration == 'Meine eigene Erklärung.'
    assert result.slides[1].narration == 'Die zweite Folie.'
    assert all(s.text_ready for s in result.included_slides)


def test_empty_window_has_one_top_aligned_start_and_no_talk_controls(qtbot, project):
    from PySide6.QtCore import QPoint
    w = MainWindow(); qtbot.addWidget(w); w.show()
    buttons = [b for b in w.findChildren(QPushButton) if b.isVisible()]
    assert [b.text() for b in buttons] == ['Open PDF…', 'Open saved talk…']
    assert buttons[0].mapTo(w, QPoint()).y() < w.height() // 4
    assert not w.toolbar.isVisible() and not w.overview.isVisible() and not w.footer.isVisible()
    assert not w.narration_progress.isVisible() and not w.record.isVisible()
    w.adopt(project)
    assert w.toolbar.isVisible() and w.overview.isVisible() and w.footer.isVisible()
    assert w.narration_progress.isVisible() and w.record.isVisible()
    assert [b.text() for b in w.findChildren(QPushButton) if b.isVisible()].count('Open PDF…') == 1


def test_generated_text_reports_readiness_without_claiming_human_approval(qtbot, project):
    services.apply_narration(project, {'title': project.title, 'slides': [
        {'page': s.page, 'narration': 'A newly generated explanation.', 'notes': '', 'budget_seconds': 15}
        for s in project.slides]}, Task(lambda _: None))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert w.narration_progress.text() == 'Text ready: 2 / 2'
    assert 'Start reuses current audio' in w.status.text() and w.start_button.text() == 'Prepare and start'
    assert w.language.currentText() == 'English'


def test_saved_voice_preview_feedback_and_settings_have_one_owner(qtbot, project, monkeypatch, tmp_path):
    import threading
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
    from autotalk import voices
    monkeypatch.setattr(voices, 'data_dir', lambda: tmp_path)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings[1].show_section("Voice & language")
    w.settings[1].voice_source.setCurrentIndex(3)
    assert w.settings[1].voice_library.rowCount() == 0
    assert not w.settings[1].voice_preview_button.isEnabled() and not w.settings[1].library_use.isEnabled()
    voices.save_voice(project, 'Conference voice'); w.settings[1].refresh_library()
    assert w.settings[1].voice_preview_button.isEnabled() and w.settings[1].library_use.isEnabled()
    release = threading.Event()
    monkeypatch.setattr(settings, 'synthesize', lambda *a, **kw: (release.wait(3), None)[1])
    # Exercise the real button and worker path; no speech model needed to check ownership.
    monkeypatch.setattr(w.transport, 'preview', lambda path: None)
    try:
        w.settings[1].voice_preview_button.click(); qtbot.wait(300)
        assert QApplication.activeModalWidget() is w.settings[1]
        assert w.progress.isVisible() and w.progress.parentWidget() is w.settings[1]
        assert 'Generating voice preview' in w.settings[1].status.text()
        assert w.settings[1].cancel_job.isVisible()
    finally:
        release.set(); qtbot.waitUntil(lambda: w.job is None)
    assert w.settings[1].buttons.button(QDialogButtonBox.Save).text().replace('&', '') == 'Save'
    w.settings[1].reject()
    w.settings[0].show_section("Application")
    assert w.screen.isVisible() and w.audio_test_button.isVisible()
    w.settings[0].reject()
    w.settings[1].show_section("Presentation & recording")
    assert w.record.isVisible() and not w.screen.isVisible() and not w.audio_test_button.isVisible()
    w.settings[1].reject()


def test_skipping_to_the_end_promotes_completion_not_replay(qtbot, project):
    make_audio(project, seconds=10)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.workspace.setCurrentWidget(w.presenter)
    w.transport.select(len(project.slides)-1); w.transport.step(1)
    assert w.transport.state == 'finished'
    assert w.duration_label.text() == 'Presentation finished'
    assert 'Remaining' not in w.play_time.text() and 'Buffered' not in w.play_time.text()
    assert not hasattr(w, "present_button") and w.start_button.isVisible()
    assert w.end_button.text() == 'Return to editing' and w.end_button.property('primary')
    assert w.start_button.isEnabled()
    w.end_button.click()
    assert w.workspace.currentWidget() is w.editor and w.transport.state == 'stopped'
