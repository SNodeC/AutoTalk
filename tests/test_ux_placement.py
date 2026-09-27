"""Acceptance journeys for docs/design/UX_PLACEMENT_PROPOSAL.md under real Qt."""
import copy
import json

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QPushButton

from autotalk import app, options, voices
from autotalk.app import MainWindow
from autotalk.project import Project
from conftest import make_audio
from test_modes import local_speech


def visible_inside(widget, window):
    assert widget.isVisible(), widget.objectName() or getattr(widget, 'text', lambda: '')()
    origin = widget.mapTo(window, QPoint())
    assert window.rect().contains(origin)
    assert window.rect().contains(origin + QPoint(widget.width()-1, widget.height()-1))
    ancestor = widget.parentWidget()
    while ancestor is not window:
        assert ancestor.rect().contains(widget.mapTo(ancestor, QPoint()))
        assert ancestor.rect().contains(widget.mapTo(ancestor, QPoint(widget.width()-1, widget.height()-1)))
        ancestor = ancestor.parentWidget()


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
@pytest.mark.parametrize('size', [(940, 680), (1100, 850)])
def test_p1_controls_are_visible_without_scroll_and_do_not_overlap(qtbot, project, mode, size):
    project.mode = mode
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.resize(*size); w.show()
    qtbot.wait(20)
    assert (w.width(), w.height()) == size
    for control in (w.minutes, w.language, w.voice_button, w.start_button, w.options.record):
        visible_inside(control, w)
    if mode != 'Quick':
        for control in (w.talk_text_button, w.talk_audio_button, w.narration, w.regenerate_button,
                        w.slide_audio_button, w.preview_button, w.slide_list):
            visible_inside(control, w)
        assert w.image.height() >= 100 and w.narration.height() >= 110
        for control in (w.regenerate_button, w.slide_audio_button, w.preview_button):
            assert not control.geometry().intersects(w.narration.geometry())
    else:
        assert not w.editor.isVisible() and not w.preparation.isVisible()
        assert not w.editor_action.isEnabled()
        w.editor_action.trigger()
        assert w.workspace.currentWidget() is w.quick_page


def test_dialog_destinations_and_direct_voice_sources(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    qtbot.mouseClick(w.voice_button, Qt.LeftButton)  # depth 1
    assert w.settings_dialog.isVisible() and w.speaker.isVisible()
    for index, control in ((1, w.record_button), (2, w.voice_description), (3, w.voice_library)):
        qtbot.mouseClick(w.voice_source, Qt.LeftButton, pos=w.voice_source.tabRect(index).center())  # depth 2
        visible_inside(control, w.settings_dialog)
        visible_inside(w.voice_preview_button, w.settings_dialog)
    w.settings_dialog.reject()
    qtbot.mouseClick(w.presentation_button, Qt.LeftButton)
    w.settings_dialog.show_section("Application", 0)
    visible_inside(w.screen, w.settings_dialog)
    visible_inside(w.audio_test_button, w.settings_dialog)
    item = w.settings_dialog.navigation.findItems("Presentation & recording", Qt.MatchFlag.MatchExactly)[0]
    w.settings_dialog.scope_selector.setCurrentIndex(1)
    qtbot.mouseClick(w.settings_dialog.navigation.viewport(), Qt.LeftButton,
                    pos=w.settings_dialog.navigation.visualItemRect(item).center())
    visible_inside(w.options.fields['recording_source'], w.settings_dialog)
    assert w.options.record.parentWidget() is w.record_footer
    w.settings_dialog.reject()
    w.talk_action.trigger()
    assert w.audience.isVisible() and w.objective.isVisible() and w.scope.isVisible()
    w.settings_dialog.show_section("AI & speech engine", 1)
    assert w.codex_model.isVisible() and w.codex_effort.isVisible()
    assert not w.codex_signin.isVisible() and not w.options.override.isVisible()
    w.settings_dialog.reject()


@pytest.mark.parametrize('mode', ['Prepared', 'Realtime'])
def test_whole_talk_text_then_audio_preserves_edits_and_does_not_present(qtbot, project, monkeypatch, local_speech, mode):
    project.mode = mode
    original = project.slides[0].narration
    project.slides[1].narration = ''
    requested = []
    def narrate(p, task, pages):
        requested.extend(pages)
        for slide in p.slides:
            if slide.page in pages: slide.narration = 'New narration.'
        return p
    monkeypatch.setattr(app, 'narrate', narrate)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    monkeypatch.setattr(w, 'present', lambda **kw: pytest.fail('Preparation must not present'))
    assert not w.talk_audio_button.isEnabled()
    qtbot.mouseClick(w.talk_text_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: w.job is None)
    assert requested == [2] and w.project.slides[0].narration == original
    assert not w.talk_text_button.isEnabled() and w.talk_audio_button.isEnabled()
    qtbot.mouseClick(w.talk_audio_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: w.job is None)
    assert w.project.prepared and Project.load(project.manifest).prepared
    saved = [(s.audio_file, s.audio_sha256) for s in w.project.slides]
    qtbot.mouseClick(w.talk_audio_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: w.job is None)
    assert [(s.audio_file, s.audio_sha256) for s in w.project.slides] == saved
    assert w.presentation is None and not w.transport.active


def test_saved_voice_audition_does_not_select_or_invalidate_talk(qtbot, project, monkeypatch, tmp_path):
    monkeypatch.setattr(voices, 'data_dir', lambda: tmp_path)
    candidate = copy.deepcopy(project); candidate.voice.speaker = 'Aiden'
    voices.save_voice(candidate, 'Candidate')
    make_audio(project)
    original = copy.deepcopy(project.voice)
    heard = []
    monkeypatch.setattr(app, 'synthesize', lambda p, task, preview: heard.append(p.voice.speaker) or p.audio(p.slides[0]))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    monkeypatch.setattr(w.transport, 'preview', lambda path: None)
    w.voice_button.click(); w.voice_source.setCurrentIndex(3)
    w.voice_preview_button.click(); qtbot.waitUntil(lambda: w.job is None)
    assert heard == ['Aiden']
    assert w.project.voice == original and w.project.prepared
    assert Project.load(project.manifest).voice == original
    w.library_use.click()
    assert w.project.voice.speaker == 'Aiden' and not w.project.prepared
    w.settings_dialog.reject()
    assert w.project.voice == original and w.project.prepared
    assert Project.load(project.manifest).voice == original


def test_language_creation_is_explicit_and_switching_preserves_original(qtbot, project, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    original = copy.deepcopy(project.version)
    assert w.language.findText('German') == -1
    monkeypatch.setattr(app.QInputDialog, 'getItem', lambda *a, **kw: ('German', True))
    w.language.setCurrentIndex(w.language.findData('add'))
    assert len(project.versions) == 2 and project.language == 'German'
    w.language.setCurrentIndex(w.language.findData('main'))
    assert project.version == original
    w.language.setCurrentIndex(w.language.findData('options'))
    assert w.settings_dialog.isVisible()
    assert w.options.fields['language_policy'].isVisible()
    w.options.fields['language_policy'].setCurrentIndex(2)
    w.settings_dialog.reject()
    assert w.project.language_policy == 'mixed'


def test_delivery_preset_and_style_never_overwrite_sampling(qtbot, project, monkeypatch, tmp_path):
    monkeypatch.setattr(options, 'data_dir', lambda: tmp_path)
    directory = tmp_path/'delivery'; directory.mkdir()
    # A legacy preset containing sampling must not cross the new delivery boundary.
    (directory/'preset.json').write_text(json.dumps({'name': 'Warm', 'delivery': {
        'style': 'Storytelling', 'attributes': {'texture': 'Warm'}, 'sampling': {'temperature': 1.8}}}))
    project.set_setting("delivery.sampling", {'temperature': .3})
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    w.settings_dialog.show_section("Voice & language", 1)
    w.options.use_preset_button.click()
    assert project.delivery.style == 'Storytelling' and project.delivery.sampling == {'temperature': .3}
    w.options.fields['delivery.style'].setCurrentText('Professional')
    assert project.delivery.attributes == {'texture': 'Warm'}
    w.settings_dialog.reject()
    assert w.project.delivery.sampling == {'temperature': .3}


def test_cancel_restores_clips_display_and_project_settings(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.screen.addItem('Second test display', 1)
    w.presentation_button.click(); w.screen.setCurrentIndex(1); w.pause.setValue(2)
    w.settings_dialog.reject()
    assert w.screen.currentIndex() == 0 and w.project.pause_seconds == .6
    w.settings_dialog.show_section("Presentation & recording", 2)
    w.project.slides[0].notes = 'Pending edit'
    w.save()  # Even handlers that persist eagerly are rolled back by Cancel.
    w.settings_dialog.reject()
    assert w.project.slides[0].notes != 'Pending edit'
    assert Project.load(project.manifest).slides[0].notes != 'Pending edit'


def test_engine_account_and_f5_use_their_single_authoritative_commands(qtbot, project, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.engine_status.click()
    assert w.engine_state.isVisible() and w.load_gpu_button.isVisible()
    w.settings_dialog.reject()
    w.settings_dialog.show_section("Application", 0)
    assert w.codex_signin.isVisible() and w.codex_signout.isVisible()
    assert not w.codex_model.isVisible()
    w.settings_dialog.reject()
    starts = []
    monkeypatch.setattr(w, 'prepare_and_present', lambda: starts.append(True))
    with qtbot.waitActive(w):
        w.activateWindow(); w.raise_()
    qtbot.keyClick(w, Qt.Key_F5)
    assert starts == [True]
    w.start_button.click()
    assert starts == [True, True]
    assert not any(b.text() == 'Start presentation' for b in w.findChildren(QPushButton))


def test_quick_can_configure_its_inherited_voice_and_delivery(qtbot, project, tmp_path, monkeypatch):
    monkeypatch.setattr(options, 'data_dir', lambda: tmp_path)
    directory = tmp_path/'delivery'; directory.mkdir()
    (directory/'preset.json').write_text(json.dumps({'name': 'Different', 'delivery': {'style': 'Storytelling'}}))
    project.mode = 'Quick'
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.voice_button.click()
    assert w.voice_source.isEnabled()
    w.settings_dialog.show_section("Voice & language", 1)
    assert w.options.use_preset_button.isEnabled()
    assert w.options.fields['delivery.style'].isEnabled()
    assert w.voice_preview_button.isEnabled()
    w.settings_dialog.reject()


def test_voice_workflows_and_audition_remain_visible_in_minimum_dialog(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings_dialog.resize(760, 580)
    w.voice_button.click()
    for index, control in ((0, w.speaker), (1, w.record_button), (2, w.voice_description), (3, w.library_use)):
        w.voice_source.setCurrentIndex(index)
        qtbot.wait(10)
        visible_inside(control, w.settings_dialog)
        visible_inside(w.voice_preview_button, w.settings_dialog)
        assert w.settings_dialog.size().toTuple() == (760, 580)
    w.settings_dialog.reject()


def test_long_talk_and_voice_names_preserve_p1_workspace(qtbot, project):
    project.title = 'An unusually long title about preparing and delivering reliable multilingual presentations ' * 3
    project.voice.name = 'My carefully designed calm conference narration voice'
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.resize(940, 680); w.show()
    qtbot.wait(20)
    assert w.size().toTuple() == (940, 680)
    for control in (w.start_button, w.voice_button, w.narration, w.slide_audio_button):
        visible_inside(control, w)


def test_first_manually_written_text_requires_explicit_language_creation(qtbot, project):
    for slide in project.slides:
        slide.narration = ''
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert w.language.findData('language:German') >= 0
    w.narration.setPlainText('Words I wrote myself in English.')
    assert w.language.currentData() == 'main'
    assert w.language.findData('language:German') == -1
    assert w.language.findData('add') >= 0
    assert len(project.versions) == 1 and project.language == 'English'


def test_multiple_empty_versions_are_selected_without_relabelling(qtbot, project, monkeypatch):
    for slide in project.slides:
        slide.narration = ''
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    monkeypatch.setattr(app.QInputDialog, 'getItem', lambda *a, **kw: ('German', True))
    w.language.setCurrentIndex(w.language.findData('add'))
    german = project.active_version
    assert w.language.currentData() == german
    w.language.setCurrentIndex(w.language.findData('main'))
    assert project.language == 'English' and project.versions[german].language == 'German'


@pytest.mark.parametrize('state', ['stopped', 'playing', 'paused', 'finished'])
def test_minimum_presenter_preserves_both_slide_previews_and_controls(qtbot, project, state):
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.resize(940, 680); w.show()
    w.view_switch.setCurrentIndex(1)
    if state in ('playing', 'paused'):
        w.transport.play()
        if state == 'paused':
            w.transport.pause()
    elif state == 'finished':
        w.transport.select(len(project.slides)-1)
        w.transport.step(1)
    w.refresh()
    qtbot.wait(20)
    for control in (w.play_image, w.next_image, w.presenter_narration, w.previous_button,
                    w.next_button, w.end_button, w.more_presentation, w.demo_button):
        visible_inside(control, w)
    assert w.play_image.height() >= 100 and w.next_image.height() >= 100
    if state == 'playing':
        visible_inside(w.play_button, w)
    if state == 'paused':
        visible_inside(w.continue_button, w)
    w.transport.stop()
