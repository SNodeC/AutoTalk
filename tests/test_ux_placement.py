# SPDX-License-Identifier: MIT
"""Acceptance journeys for docs/design/UX_PLACEMENT_PROPOSAL.md under real Qt."""
import copy
import json

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QPushButton, QStyle, QStyleOptionComboBox

from autotalk import app, options, voices
from autotalk import settings_components as settings
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
    for control in (w.minutes, w.language, w.voice_button, w.start_button, w.record):
        visible_inside(control, w)
    if mode != 'Quick':
        for control in (w.talk_text_button, w.talk_audio_button, w.narration, w.regenerate_button,
                        w.slide_audio_button, w.preview_button, w.slide_list, w.editor_previous, w.editor_next):
            visible_inside(control, w)
        assert w.image.height() >= 100 and w.narration.height() >= 110
        for inherited in ('advance', 'pause', 'demo'):
            w.project.set_setting('after', inherited)
            w.show_slide(0)
            option = QStyleOptionComboBox(); w.inspector.slide_after.initStyleOption(option)
            field = w.inspector.slide_after.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, w.inspector.slide_after)
            for item in range(w.inspector.slide_after.count()):
                assert w.inspector.slide_after.fontMetrics().horizontalAdvance(w.inspector.slide_after.itemText(item)) <= field.width()
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
    assert w.settings[1].isVisible() and w.settings[1].voice.speaker.isVisible()
    for index, control in ((1, w.settings[1].voice.record_button), (2, w.settings[1].voice.voice_description), (3, w.settings[1].voice.voice_library)):
        qtbot.mouseClick(w.settings[1].voice.voice_source, Qt.LeftButton, pos=w.settings[1].voice.voice_source.tabRect(index).center())  # depth 2
        visible_inside(control, w.settings[1])
        visible_inside(w.settings[1].voice.voice_preview_button, w.settings[1])
    w.settings[1].reject()
    qtbot.mouseClick(w.presentation_button, Qt.LeftButton)
    w.preferences.show_section("Display & sound")
    visible_inside(w.preferences.screen, w.preferences)
    visible_inside(w.preferences.audio_test_button, w.preferences)
    w.preferences.reject()
    w.settings[1].show_section("Audio & recording")
    visible_inside(w.settings[1].fields['recording_source'].editor, w.settings[1])
    assert w.record.parentWidget() is w.record_footer
    w.settings[1].reject()
    w.talk_action.trigger()
    assert w.settings[1].fields['audience'].editor.isVisible() and w.settings[1].fields['objective'].editor.isVisible() and w.settings[1].fields['scope'].editor.isVisible()
    w.settings[1].show_section("AI model")
    assert w.settings[1].models.codex_model.isVisible() and w.settings[1].models.codex_effort.isVisible()
    assert not w.preferences.codex_signin.isVisible() and w.settings[1].voice.override.isVisible()
    w.settings[1].reject()


@pytest.mark.parametrize('scope', [0, 1])
@pytest.mark.parametrize('size', [(760, 580), (920, 760)])
def test_language_arrangement_choices_fit_native_field(qtbot, project, scope, size):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[scope]
    dialog.show_section('Voice & language')
    dialog.resize(*size)
    combo = dialog.fields['language_policy'].editor
    scroll = dialog.pages.currentWidget()
    for index in range(combo.count()):
        scroll.ensureWidgetVisible(combo)
        combo.setFocus()
        qtbot.keyClick(combo, Qt.Key_Home)
        for _ in range(index):
            qtbot.keyClick(combo, Qt.Key_Down)
        qtbot.wait(20)
        assert combo.currentIndex() == index
        assert dialog.setting_value('language_policy') == combo.itemData(index)
        option = QStyleOptionComboBox(); combo.initStyleOption(option)
        field = combo.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, combo)
        assert combo.fontMetrics().horizontalAdvance(combo.currentText()) <= field.width()
        assert (dialog.width(), dialog.height()) == size
        assert scroll.horizontalScrollBar().maximum() == 0
        visible_inside(combo, dialog)
    dialog.reject()


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
    monkeypatch.setattr(settings, 'synthesize', lambda p, task, preview: heard.append(p.voice.speaker) or p.audio(p.slides[0]))
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    monkeypatch.setattr(w.transport, 'preview', lambda path: None)
    w.voice_button.click(); w.settings[1].voice.voice_source.setCurrentIndex(3)
    w.settings[1].voice.voice_preview_button.click(); qtbot.waitUntil(lambda: w.job is None)
    assert heard == ['Aiden']
    assert w.project.voice == original and w.project.prepared
    assert Project.load(project.manifest).voice == original
    w.settings[1].voice.library_use.click()
    assert w.settings[1].project.voice.speaker == 'Aiden' and not w.settings[1].project.prepared
    assert w.project.voice.speaker != 'Aiden' and w.project.prepared
    w.settings[1].reject()
    assert w.project.voice == original and w.project.prepared
    assert Project.load(project.manifest).voice == original


def test_language_selection_automatically_creates_and_preserves_original(qtbot, project, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    original = copy.deepcopy(project.version)
    assert w.language.findText('German') >= 0
    w.language.setCurrentText('German')
    assert len(project.versions) == 2 and project.language == 'German'
    w.language.setCurrentIndex(w.language.findData('main'))
    assert project.version.slides == original.slides
    assert project.version.language == project.language == 'English'
    w.language.setCurrentIndex(w.language.findData('options'))
    assert w.settings[1].isVisible()
    assert w.settings[1].fields['language_policy'].editor.isVisible()
    w.settings[1].fields['language_policy'].editor.setCurrentIndex(2)
    w.settings[1].reject()
    assert w.project.language_policy == 'mixed'


def test_delivery_preset_and_style_never_overwrite_sampling(qtbot, project, monkeypatch, tmp_path):
    monkeypatch.setattr(options, 'data_dir', lambda: tmp_path)
    directory = tmp_path/'delivery'; directory.mkdir()
    # A legacy preset containing sampling must not cross the new delivery boundary.
    (directory/'preset.json').write_text(json.dumps({'name': 'Warm', 'delivery': {
        'style': 'Storytelling', 'attributes': {'texture': 'Warm'}, 'sampling': {'temperature': 1.8}}}))
    project.set_setting("delivery.sampling", {'temperature': .3})
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    w.settings[1].show_section("Voice & language")
    w.settings[1].presets.use_preset_button.click()
    assert w.settings[1].project.delivery.style == 'Storytelling' and w.settings[1].project.delivery.sampling == {'temperature': .3}
    assert project.delivery.style == 'Professional'
    w.settings[1].fields['delivery.style'].editor.setCurrentText('Professional')
    assert w.settings[1].project.delivery.attributes == {'texture': 'Warm'}
    w.settings[1].reject()
    assert w.project.delivery.sampling == {'temperature': .3}


def test_cancel_restores_clips_display_and_project_settings(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    w.preferences.screen.addItem('Second test display',1)
    w.preferences.show_section();w.preferences.screen.setCurrentIndex(1);w.preferences.reject()
    w.presentation_button.click();w.settings[1].fields['pause_seconds'].editor.setValue(2)
    w.settings[1].reject()
    assert w.preferences.screen.currentIndex()==1 and w.project.pause_seconds==.6
    w.project.slides[0].notes='Pending edit';w.setWindowModified(True)
    before=project.manifest.read_bytes()
    w.settings[2].show_section('Audio & recording');w.settings[2].reject()
    assert w.project.slides[0].notes=='Pending edit' and w.isWindowModified()
    assert project.manifest.read_bytes()==before


def test_engine_account_and_f5_use_their_single_authoritative_commands(qtbot, project, monkeypatch):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.engine_status.click()
    assert w.preferences.engine_state.isVisible() and w.preferences.load_gpu_button.isVisible()
    w.preferences.reject()
    w.preferences.show_section("Account")
    assert w.preferences.codex_signin.isVisible() and w.preferences.codex_signout.isVisible()
    assert not w.settings[0].models.codex_model.isVisible()
    w.preferences.reject()
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
    assert w.settings[1].voice.voice_source.isEnabled()
    w.settings[1].show_section("Voice & language")
    assert w.settings[1].presets.use_preset_button.isEnabled()
    assert w.settings[1].fields['delivery.style'].editor.isEnabled()
    assert w.settings[1].voice.voice_preview_button.isEnabled()
    w.settings[1].reject()


def test_voice_workflows_and_audition_remain_visible_in_minimum_dialog(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.settings[1].resize(760, 580)
    w.voice_button.click()
    for index, control in ((0, w.settings[1].voice.speaker), (1, w.settings[1].voice.record_button), (2, w.settings[1].voice.voice_description), (3, w.settings[1].voice.library_use)):
        w.settings[1].voice.voice_source.setCurrentIndex(index)
        qtbot.wait(10)
        visible_inside(control, w.settings[1])
        visible_inside(w.settings[1].voice.voice_preview_button, w.settings[1])
        assert w.settings[1].size().toTuple() == (760, 580)
    w.settings[1].reject()


def test_long_talk_and_voice_names_preserve_p1_workspace(qtbot, project):
    project.title = 'An unusually long title about preparing and delivering reliable multilingual presentations ' * 3
    project.voice.name = 'My carefully designed calm conference narration voice'
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.resize(940, 680); w.show()
    qtbot.wait(20)
    assert w.size().toTuple() == (940, 680)
    for control in (w.start_button, w.voice_button, w.narration, w.slide_audio_button):
        visible_inside(control, w)


def test_language_version_selector_has_one_meaning_before_and_after_writing(qtbot, project):
    for slide in project.slides:
        slide.narration = ''
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert w.language.currentData() == 'main'
    choices = [w.language.itemData(i) for i in range(w.language.count())]
    w.narration.setPlainText('Words I wrote myself in English.')
    assert w.language.currentData() == 'main'
    assert w.language.findData('language:German') == -1
    assert w.language.findData('German') >= 0
    assert [w.language.itemData(i) for i in range(w.language.count())] == choices
    assert len(project.versions) == 1 and project.language == 'English'


def test_multiple_empty_versions_are_selected_without_relabelling(qtbot, project, monkeypatch):
    for slide in project.slides:
        slide.narration = ''
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.language.setCurrentText('German')
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
