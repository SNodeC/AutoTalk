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
from autotalk.app import MainWindow
from autotalk.media import Capture, RATE
from autotalk.runtime import Cancelled, Task


def test_open_pdf_has_one_dialog_and_non_destructive_default_location(qtbot, sample_pdf, tmp_path, monkeypatch):
    documents = tmp_path / 'Documents'
    monkeypatch.setattr(app.QStandardPaths, 'writableLocation', lambda _: str(documents))
    monkeypatch.setattr(app.QFileDialog, 'getOpenFileName', lambda *a: (str(sample_pdf), 'PDF'))
    monkeypatch.setattr(app.QFileDialog, 'getExistingDirectory', lambda *a: pytest.fail('Unexpected folder dialog'))
    w = MainWindow(); qtbot.addWidget(w); w.show()
    for suffix in ('', '-2'):
        w.new_project()
        qtbot.waitUntil(lambda: w.job is None, timeout=5000)
        assert w.project.root == documents / 'AutoTalk' / ('slides-AutoTalk' + suffix)
        assert w.project.manifest.is_file()
        assert w.start_button.text() == 'Write talk text'
        assert w.context_warning.text() == 'Your slides are ready. Write the talk text next.'
        assert w.talk_dialog.isVisible() and w.minutes.isVisible() and w.audience.isVisible()
        w.talk_dialog.accept()
    assert (documents / 'AutoTalk/slides-AutoTalk/talk.autotalk.json').is_file()


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
def test_manual_review_and_next_action_agree_everywhere(qtbot, project, mode):
    project.mode = mode
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert w.start_button.text() == w.start_action.text() == 'Review talk text'
    assert mode in w.mode_description.text()
    w.start_button.click()
    assert w.workspace.currentWidget() is w.editor and w.job is None
    assert w.accept_button.isVisible()
    w.accept_button.click()
    assert project.script_current
    assert w.start_button.text() == w.start_action.text()
    assert w.start_button.text() == ('Prepare audio' if mode == 'Prepared' else 'Prepare and start')
    w.minutes.setValue(5)
    assert 'Talk length changed' in w.status.text()
    assert not project.script_current


def test_voice_source_shows_only_its_own_workflow(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.talk_dialog.show_section(2)
    designed = next(b for b in w.talk_dialog.findChildren(QPushButton) if b.text() == 'Use this designed voice')
    for source in ('CustomVoice', 'Base', 'VoiceDesign', 'CustomVoice'):
        w.voice_source.setCurrentIndex(w.voice_source.findData(source))
        assert w.speaker.isVisible() == (source == 'CustomVoice')
        assert w.record_button.isVisible() == (source == 'Base')
        assert w.transcript.isVisible() == (source == 'Base')
        assert w.voice_description.isVisible() == (source == 'VoiceDesign')
        assert designed.isVisible() == (source == 'VoiceDesign')
        assert w.voice_preview_button.isVisible()
    w.talk_dialog.reject()


def test_presenter_offers_one_action_and_explicit_recording_end(qtbot, project):
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.workspace.setCurrentWidget(w.presenter)
    actions = (w.present_button, w.play_button, w.continue_button)
    for state, expected in [('stopped', w.present_button), ('playing', w.play_button), ('paused', w.continue_button)]:
        w.transport.state = state
        w.refresh()
        assert [b for b in actions if b.isVisible()] == [expected]
        assert expected.isEnabled()
        assert not w.start_button.isVisible()
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
    project.mode = 'Realtime'; project.accept_script()
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.workspace.setCurrentWidget(w.presenter)
    w.transport.state = 'paused'; w.refresh()
    assert w.start_button.isVisible() and w.start_button.isEnabled()
    assert w.start_button.text() == 'Resume preparation'
    assert not w.present_button.isVisible() and not w.continue_button.isVisible()
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
    output = tmp_path / 'video.mp4'; output.write_bytes(b'exported')
    info['output'] = str(output); (root / 'session.json').write_text(json.dumps(info))
    w.export_saved(output); w.update_timing()
    assert w.recordings.item(0, 3).text() == 'Ready'
    assert 'Saved ' in w.record_status.text() and w.output_button.isEnabled()
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
    assert 'Open video' in w.record_status.text()


def test_recording_intent_and_saving_are_not_reported_as_finished(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    w.options.record.setChecked(True); w.update_timing()
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
    project.accept_script()
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
    project.mode = mode; project.quick_timing = 'once'; project.accept_script()
    monkeypatch.setattr(services, 'Codex', lambda *a: pytest.fail('No text generation needed'))
    monkeypatch.setattr(services, 'speech_session', lambda *a: nullcontext())
    monkeypatch.setattr(services, 'synthesize', lambda p, t, **kw: make_audio(p))
    services.workflow(project, Task())
    assert project.prepared


def test_language_draft_cannot_be_approved_until_translated_or_replaced(qtbot, project, monkeypatch):
    from autotalk.project import Project
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    original = project.active_version
    text = [s.narration for s in project.slides]
    w.language.setCurrentText('German')
    assert w.start_button.text() == 'Translate talk text'
    assert not w.accept_button.isEnabled()
    with pytest.raises(ValueError, match='Translate or replace'):
        project.accept_script()
    assert not project.script_current
    calls = []
    monkeypatch.setattr(app.QMessageBox, 'question', lambda *a: pytest.fail('Translation must not ask to rewrite the source'))
    monkeypatch.setattr(w, 'start_job', lambda *a, **kw: calls.append(a[1].keywords.get('pages')))
    w.start_button.click()
    assert calls == [[1, 2]]
    for index, slide in enumerate(project.slides):
        w.slide_list.setCurrentRow(index)
        w.narration.setPlainText(f'Dies ist die Erklärung für Folie {slide.page}.')
        if index == 0:
            assert not w.accept_button.isEnabled()
            assert w.start_button.text() == 'Translate talk text'
            w.start_button.click()
            assert calls[-1] == [2]
    assert w.accept_button.isEnabled()
    w.accept_button.click()
    assert project.script_current
    reopened = Project.load(project.manifest)
    assert reopened.language == 'German' and reopened.script_current
    assert [s.narration for s in reopened.versions[original].slides] == text


def test_previous_video_does_not_override_new_recording_intent(qtbot, project, tmp_path):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    video = tmp_path / 'previous.mp4'; video.write_bytes(b'video')
    w.export_saved(video)
    w.options.record.click()
    assert 'Will record when presentation starts' in w.record_status.text()
    assert 'Saved ' in w.record_status.text() and 'Open video' in w.record_status.text()
    w.options.fields['recording_source'].setCurrentIndex(w.options.fields['recording_source'].findData('screen'))
    assert 'Screen + system audio' in w.options.record.text()
    w.language.setCurrentText('German')
    assert 'Will record when presentation starts' in w.record_status.text()
    video.unlink()
    w.update_timing()  # An externally removed video must not crash the UI timer.
    assert 'Saved ' not in w.record_status.text()


def test_voice_actions_follow_reference_and_current_design(qtbot, project, tmp_path, monkeypatch):
    import wave
    monkeypatch.setattr(services, 'data_dir', lambda: tmp_path)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.talk_dialog.show_section(2)
    assert 'Energetic male' in w.speaker.currentText()
    w.speaker.setCurrentIndex(w.speaker.findData('Aiden'))
    assert project.voice.speaker == 'Aiden'
    w.voice_source.setCurrentIndex(w.voice_source.findData('Base'))
    assert not w.voice_preview_button.isEnabled() and not w.save_voice_button.isEnabled()
    w.voice_source.setCurrentIndex(w.voice_source.findData('VoiceDesign'))
    assert not w.voice_preview_button.isEnabled() and not w.accept_voice_button.isEnabled()
    w.voice_description.setText('Warm, calm and clear')
    assert w.voice_preview_button.isEnabled() and not w.accept_voice_button.isEnabled()
    path = services.preview_path(project); path.parent.mkdir(parents=True)
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0\0' * 4 * 24000)
    w.refresh()
    assert w.accept_voice_button.isEnabled()
    w.voice_description.setText('An entirely different voice')
    assert not w.accept_voice_button.isEnabled()
    w.voice_description.setText('Warm, calm and clear')
    w.accept_voice_button.click()
    assert project.voice.source == 'Base' and project.asset(project.voice_file).is_file()
    assert w.voice_preview_button.isEnabled()
    w.talk_dialog.accept()


def test_operation_feedback_is_in_the_active_dialog(qtbot, project):
    import threading
    release = threading.Event()
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.talk_dialog.show_section(2)
    try:
        w.start_job('Generating voice preview…', lambda task: release.wait(3))
        qtbot.wait(300)
        assert w.progress.isVisible() and w.progress.parentWidget() is w.talk_dialog
        assert 'Waiting ' in w.talk_dialog.status.text()
        assert w.talk_dialog.cancel_job.isVisible() and w.talk_dialog.cancel_job.isEnabled()
    finally:
        release.set()
        qtbot.waitUntil(lambda: w.job is None)
    assert not w.progress.isVisible()
    w.talk_dialog.accept()
    assert w.progress.parentWidget() is w.footer
    w.accept_button.click()
    assert w.status.text() == w.next_step()[1]
    assert 'Prepare its audio' in w.status.text()


def test_inapplicable_options_and_recording_browser_priorities(qtbot, project, monkeypatch, tmp_path):
    from autotalk import options
    monkeypatch.setattr(options, 'data_dir', lambda: tmp_path)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert not w.options.use_preset_button.isEnabled()
    w.talk_dialog.show_section(4)
    assert not w.remove_background_button.isEnabled() and not w.background_gain.isEnabled()
    assert w.background_gain.value() == 15 and w.background_gain.suffix() == ' %'
    w.talk_dialog.accept()
    w.export_dialog.show_section()
    assert w.output_button.property('primary') and not w.export_button.property('primary')
    assert w.export_button.y() > w.recordings.y()
    w.export_dialog.accept()
    assert w.fit_button.isVisible()
    assert project.slides[0].source_text.splitlines()[0] in w.slide_list.item(0).text()


def test_fullscreen_mouse_controls_and_finished_return(qtbot, project):
    from PySide6.QtCore import QPoint
    make_audio(project, seconds=10)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.present_button.click()
    fullscreen = w.presentation
    assert fullscreen is not None
    qtbot.mouseMove(fullscreen, QPoint(20, fullscreen.height()-25))
    qtbot.waitUntil(lambda: fullscreen.controls.isVisible())
    qtbot.mouseClick(fullscreen.controls.widgetForAction(fullscreen.toggle_action), Qt.MouseButton.LeftButton)
    assert w.transport.state == 'paused'
    assert fullscreen.toggle_action.text() == 'Continue'
    qtbot.mouseClick(fullscreen.controls.widgetForAction(fullscreen.toggle_action), Qt.MouseButton.LeftButton)
    assert w.transport.playing
    w.transport.select(len(project.slides)-1)
    w.transport.step(1)
    assert w.transport.state == 'finished' and not fullscreen.toggle_action.isEnabled()
    assert fullscreen.controls.isVisible() and w.end_action.text() == 'Return to editing'
    qtbot.mouseClick(fullscreen.controls.widgetForAction(w.end_action), Qt.MouseButton.LeftButton)
    assert w.presentation is None and w.workspace.currentWidget() is w.editor
    assert w.transport.state == 'stopped'


def test_enlargement_opens_current_slide_in_system_viewer(qtbot, project, monkeypatch):
    from autotalk import ui
    opened = []
    monkeypatch.setattr(ui.QDesktopServices, 'openUrl', lambda url: opened.append(Path(url.toLocalFile())))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.slide_list.setCurrentRow(1)
    button = next(b for b in w.findChildren(QPushButton) if b.text() == 'Enlarge in viewer…')
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert opened == [project.image(project.slides[1])]
    assert opened[0].is_file()


def test_automatic_recording_save_cannot_resume_finished_fullscreen(qtbot, project):
    make_audio(project, seconds=.2)
    project.record_presentation = True
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.present_button.click()
    view = w.presentation
    qtbot.waitUntil(lambda: w.transport.state == 'stopped' and w.job is None and not w.pending_exports, timeout=10000)
    assert Path(w.output_path).is_file()
    assert not view.toggle_action.isEnabled()
    qtbot.keyClick(view, Qt.Key.Key_Space)
    assert w.transport.state == 'stopped' and w.transport.capture is None
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
    assert not result.script_current
    result.accept_script()
    assert result.script_current
