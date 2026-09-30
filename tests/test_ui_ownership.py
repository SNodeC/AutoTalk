# SPDX-License-Identifier: MIT
import ast
import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QComboBox

from autotalk.app import MainWindow
from autotalk.project import Clip, Project
from conftest import make_audio


ALLOWED = {'project', 'edit_setting', 'codex_settings', 'error', 'log_message',
           'start_job', 'voice_context', 'configuration_changed', 'transport',
           'recorder', 'refresh', 'request_refresh'}


def test_component_controller_allowlist():
    for name in ('settings', 'options', 'inspector'):
        tree = ast.parse(Path(f'src/autotalk/{name}.py').read_text())
        for function in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            aliases = {'window'} if name != 'options' else set()
            def controller(node):
                return (isinstance(node, ast.Name) and node.id in aliases or
                        isinstance(node, ast.Attribute) and node.attr == 'window')
            for node in ast.walk(function):
                if isinstance(node, ast.Assign) and controller(node.value):
                    aliases.update(t.id for t in node.targets if isinstance(t, ast.Name))
            for node in ast.walk(function):
                if isinstance(node, ast.Attribute) and controller(node.value):
                    assert node.attr in ALLOWED, (name, node.lineno, ast.unparse(node))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'getattr' and controller(node.args[0]):
                    assert isinstance(node.args[1], ast.Constant) and node.args[1].value in ALLOWED
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) and controller(node.value.value):
                    if node.value.attr == 'recorder':
                        assert node.attr == 'source', (name, node.lineno, 'recorder must be read-only')


def test_each_component_owns_widgets_and_builders(qtbot, project):
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    for dialog in w.settings.values():
        popups = {combo.view().window() for combo in dialog.findChildren(QComboBox)}
        for child in dialog.findChildren(QWidget):
            assert child.window() is dialog or child.window() in popups
            if child.window() in popups:
                assert child.window().windowType() == Qt.WindowType.Popup
                assert child.window().parentWidget().window() is dialog
    for name in ('slide_include', 'slide_after', 'slide_pause', 'clip_select', 'clip_gain',
                 'clip_placement', 'codex_signin', 'engine_state', 'background_button'):
        assert not hasattr(w, name), name
    assert w.inspector.slide_after.window() is w
    assert all('takeRow(' not in p.read_text() for p in Path('src').rglob('*.py'))
    tree = ast.parse(Path('src/autotalk/ui.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add':
            assert 'settings' not in ast.unparse(node.func.value)


def test_cancel_restores_clip_gain_and_placement(qtbot, project):
    make_audio(project)
    for slide in project.slides:
        slide.clips = [Clip(slide.audio_file, slide.audio_sha256, slide.duration)]
    project.save()
    original = copy.deepcopy(project.slides)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.show()
    dialog = w.settings[2]
    dialog.show_section('Presentation & recording')
    dialog.clip_gain.setValue(.5)
    dialog.clip_placement.setCurrentIndex(dialog.clip_placement.findData('after'))
    assert w.project.slides[0].clips[0].gain == .5
    assert w.project.slides[0].clips[0].placement == 'after'
    dialog.reject()
    assert w.project.slides == original
    assert Project.load(project.manifest).slides == original


def test_tab_order_matches_base(qtbot):
    import json
    expected = json.loads(Path('docs/reviews/evidence/2026-09-30-ui-structure-perf/base-tab-order.json').read_text())
    w = MainWindow(); qtbot.addWidget(w)
    for scope, dialog in w.settings.items():
        names = {v: k.replace('conference_scope', 'scope') for k, v in dialog.__dict__.items()
                 if isinstance(v, QWidget) and QWidget.window(v) is dialog}
        names.update({v: 'field:' + k for k, v in dialog.options.fields.items()})
        names.update({v[1]: 'reset:' + k for k, v in dialog.options.inheritance.items()})
        actual = []
        child = dialog.nextInFocusChain()
        while child is not dialog:
            if child in names and child.focusPolicy() & Qt.FocusPolicy.TabFocus:
                actual.append(names[child])
            child = child.nextInFocusChain()
        assert actual == expected[str(scope)]
