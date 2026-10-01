# SPDX-License-Identifier: MIT
"""Save is atomic, literal ampersands stay literal, and compact controls fit."""
import copy
import re
from dataclasses import asdict
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractButton, QDialogButtonBox, QLabel, QTabBar, QToolButton

from autotalk import settings
from autotalk.app import MainWindow
from autotalk.project import Project


@pytest.mark.parametrize('scope', [0, 1, 2])
@pytest.mark.parametrize('fail_at', [1, 2])
@pytest.mark.parametrize('modified', [False, True])
def test_failed_replay_is_atomic_and_retryable(qtbot, project, monkeypatch, scope, fail_at, modified):
    project.save()
    w = MainWindow()
    qtbot.addWidget(w)
    w.adopt(project)
    w.show()
    if modified:
        w.minutes.setValue(17)
    w.setWindowModified(modified)
    dialog = w.settings[scope]
    dialog.show_section('Writing & delivery')
    for key, value in [('writing_style', 'Conversational'), ('delivery.style', 'Storytelling'),
                       ('delivery.instructions', 'Keep a steady pace.')]:
        dialog.edit_setting(key, value)
    live_before = copy.deepcopy(asdict(w.project))
    defaults_before = copy.deepcopy(w.defaults)
    draft_before = copy.deepcopy(asdict(dialog.project))
    operations_before = copy.deepcopy(dialog.operations)
    expected = copy.deepcopy(w.project)
    target = Project(expected.root, defaults=copy.deepcopy(w.defaults)) if scope == 0 else expected
    for operation in dialog.operations:
        settings.apply_edit(target, scope, dialog.slide_index, operation)
    if scope == 0:
        expected.set_defaults(target.defaults)
    before_bytes = project.manifest.read_bytes()
    before_mtime = project.manifest.stat().st_mtime_ns
    before_config = w.config.value('setting_defaults')
    real_apply = settings.apply_edit
    count = 0

    def faulty_apply(*args):
        nonlocal count
        count += 1
        real_apply(*args)
        if count == fail_at:
            raise ValueError('injected replay failure')

    with monkeypatch.context() as fault:
        fault.setattr(settings, 'apply_edit', faulty_apply)
        save = Mock(wraps=w.save)
        fault.setattr(w, 'save', save)
        dialog.accept()
        assert save.call_count == 0
    assert count == fail_at
    assert dialog.isVisible() and 'injected replay failure' in dialog.status.text()
    assert asdict(w.project) == live_before
    assert w.defaults == defaults_before and w.config.value('setting_defaults') == before_config
    assert asdict(dialog.project) == draft_before and dialog.operations == operations_before
    assert project.manifest.read_bytes() == before_bytes
    assert project.manifest.stat().st_mtime_ns == before_mtime
    assert w.isWindowModified() == modified
    assert dialog.generation == w.project_generation
    dialog.accept()
    assert not dialog.isVisible()
    assert asdict(w.project) == asdict(expected)
    if scope:
        assert asdict(Project.load(w.project.manifest)) == asdict(w.project)
    else:
        assert w.defaults == target.defaults
        assert w.config.value('setting_defaults') != before_config


def test_buttons_actions_and_tabs_have_no_accidental_mnemonics(qtbot, project):
    w = MainWindow()
    qtbot.addWidget(w)
    w.adopt(project)
    w.show()
    single_ampersand = re.compile(r'(?<!&)&(?!&)')
    for surface in [w, *w.settings.values(), w.preferences]:
        if surface is not w:
            surface.show_section()
        texts = [button.text() for button in surface.findChildren(QAbstractButton)]
        texts += [action.text() for action in surface.findChildren(QAction)]
        texts += [tab.tabText(i) for tab in surface.findChildren(QTabBar) for i in range(tab.count())]
        assert not [text for text in texts if single_ampersand.search(text)]
        if surface is not w:
            native = QDialogButtonBox(surface.buttons.standardButtons())
            for control in surface.buttons.buttons():
                standard = native.button(surface.buttons.standardButton(control))
                assert control.shortcut() == standard.shortcut()
            native.deleteLater()
            surface.reject()
    for scope in (0, 1):
        dialog = w.settings[scope]
        dialog.show_section('Timing & playback')
        link = next(b for b in dialog.findChildren(QAbstractButton)
                    if b.text() == 'Display && sound settings…')
        assert link.text().replace('&&', '&') == 'Display & sound settings…'
        assert link.shortcut().isEmpty()
        dialog.reject()


@pytest.mark.parametrize('size', [(940, 680), (1100, 850)])
def test_compact_inspector_caption_and_reset_fit(qtbot, project, size):
    w = MainWindow()
    qtbot.addWidget(w)
    w.adopt(project)
    w.resize(*size)
    w.show()
    next(b for b in w.inspector.findChildren(QToolButton) if b.text() == 'Timing').setChecked(True)
    w.editor.setSizes([154, size[0] - 354, 200])
    qtbot.wait(50)
    for field in (w.inspector.after_field, w.inspector.pause_field):
        field.source.setText('from an unusually long inherited source')
        qtbot.wait(20)
        assert field.source.toolTip() == 'from an unusually long inherited source'
        assert field.source.alignment() & Qt.AlignmentFlag.AlignRight
        assert field.source.text() != field.source.toolTip()
        for child in (field.source, field.reset, field.editor):
            rect = child.rect()
            assert field.rect().contains(child.mapTo(field, rect.topLeft()))
            assert field.rect().contains(child.mapTo(field, rect.bottomRight()))
        assert field.reset.mapTo(field, QPoint()).y() < field.editor.mapTo(field, QPoint()).y()
        assert field.reset.width() >= field.reset.minimumSizeHint().width()
        assert field.editor.width() == field.width()
        title = next(child for child in field.findChildren(QLabel) if child is not field.source)
        assert not title.wordWrap()
        assert title.width() >= title.fontMetrics().horizontalAdvance(title.text())
    assert w.inspector.parentWidget().parentWidget().horizontalScrollBar().maximum() == 0
