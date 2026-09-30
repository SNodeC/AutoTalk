"""Language selection restores completed versions instead of relabelling words."""
import copy

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox

from autotalk.app import MainWindow
from autotalk.project import Project
from autotalk import services
from conftest import make_audio


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
@pytest.mark.parametrize('control', ['main', 'settings'])
def test_select_language_restores_version_and_start_reuses_audio(qtbot, project, monkeypatch, mode, control):
    project.mode = mode
    project.quick_timing = 'once'
    project.language = 'Chinese'
    for slide in project.slides:
        project.set_narration(slide, '这是中文。')
    make_audio(project)
    chinese = project.active_version
    original = copy.deepcopy(project.version)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.transport.select(1)

    def choose(language):
        if control == 'main':
            w.language.setCurrentIndex(w.language.findText(language))
        else:
            dialog = w.settings[1]
            dialog.show_section('Voice & language')
            dialog.settings_language.setCurrentText(language)
            qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.Save), Qt.LeftButton)
        assert w.project.language == language
        assert w.transport.index == 1
        assert w.narration.toPlainText() == w.project.slides[1].narration

    choose('German')
    german = project.active_version
    assert german != chinese
    assert project.versions[chinese] == original
    assert w.narration_progress.value() == w.slide_progress.value() == 0
    for slide in project.slides:
        project.set_narration(slide, 'Guten Tag.')
    make_audio(project)
    prepared_german = copy.deepcopy(project.version)
    w.adopt(project)
    for language, key in [('Chinese', chinese), ('German', german), ('Chinese', chinese)]:
        choose(language)
        assert project.active_version == key and project.prepared
        assert w.narration_progress.value() == w.slide_progress.value() == 2
    assert project.versions[chinese] == original
    assert project.versions[german] == prepared_german
    assert len(project.versions) == 3  # Original English, Chinese and German.
    w.save()
    loaded = Project.load(project.manifest)
    w.adopt(loaded)
    choose('German')
    assert loaded.active_version == german and loaded.prepared
    calls = []
    monkeypatch.setattr(w, 'present', lambda **kwargs: calls.append('present'))
    monkeypatch.setattr(services, 'workflow', lambda *_: pytest.fail('Prepared language must not regenerate'))
    qtbot.mouseClick(w.start_button, Qt.LeftButton)
    assert calls == ['present'] and w.job is None


def test_settings_cancel_restores_versions_and_source_edits(qtbot, project):
    make_audio(project)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    w.narration.setPlainText('My unsaved English edit.')
    before = copy.deepcopy(project)
    dialog = w.settings[1]; dialog.show_section('Voice & language')
    dialog.settings_language.setCurrentText('German')
    assert len(project.versions) == 2
    assert project.versions['main'].slides[0].narration == 'My unsaved English edit.'
    dialog.reject()
    assert w.project.versions == before.versions and w.project.active_version == before.active_version
    assert w.narration.toPlainText() == 'My unsaved English edit.'
    assert Project.load(project.manifest).versions == before.versions


def test_talk_inheritance_selects_default_version_preserving_other_language(project):
    make_audio(project)
    english = copy.deepcopy(project.slides)
    project.language = 'German'
    for slide in project.slides:
        project.set_narration(slide, 'Hallo.')
    german = project.active_version
    make_audio(project)
    project.set_setting('language', None, inherit=True)
    assert project.active_version == 'main' and project.version.language == ''
    assert project.slides == english and project.prepared
    project.language = 'German'
    assert project.active_version == german and project.prepared


def test_realtime_rewrite_changes_only_selected_language(qtbot, project, monkeypatch):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMessageBox
    project.mode = 'Realtime'
    make_audio(project)
    project.language = 'German'
    for slide in project.slides:
        project.set_narration(slide, 'Hallo.')
    make_audio(project)
    original = copy.deepcopy(project.versions['main'])
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    def rewrite(p, task, pages):
        return services.apply_narration(p, {'title': p.title, 'slides': [
            {'page': i, 'narration': 'Überarbeiteter Text.', 'notes': '', 'budget_seconds': 1}
            for i in pages]}, task)
    monkeypatch.setattr('autotalk.app.narrate', rewrite)
    action = next(a for a in w.findChildren(QAction) if a.text() == 'Rewrite all talk text…')
    assert action.isEnabled()
    action.trigger()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert all(s.narration == 'Überarbeiteter Text.' for s in w.project.slides)
    assert w.project.versions['main'] == original
    assert w.narration_progress.value() == 2 and w.slide_progress.value() == 0
    assert w.start_button.text() == 'Start' and w.start_button.isEnabled()


def test_custom_named_versions_remain_accessible_without_duplication(qtbot, project):
    project.language = 'German'
    project.version.name = 'Conference edition'
    german = project.active_version
    project.language = 'English'
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    assert w.language.itemText(w.language.findData(german)) == 'German — Conference edition'
    dialog = w.settings[1]; dialog.show_section('Voice & language')
    dialog.settings_language.setCurrentText('German')
    dialog.accept()
    assert project.active_version == german and len(project.versions) == 2
    assert project.version.name == 'Conference edition'
