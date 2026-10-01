# SPDX-License-Identifier: MIT
"""One field builder and loader for schema rows and inspector inheritance."""

from PySide6.QtWidgets import QWidget, QLineEdit, QPlainTextEdit, QCheckBox, QDoubleSpinBox, QHBoxLayout, QVBoxLayout
from .ui import combo, button, label


class SettingField(QWidget):
    def __init__(self, spec, scope, edit, editor=None, compact=False):
        super().__init__()
        self.spec, self.scope = spec, scope
        self.read_only = scope in spec.read_only_scopes
        self.read, self.write = None, None
        if self.read_only:
            editor = label('')
        elif editor is None:
            editor = self.make_editor(edit)
        self.editor = editor
        editor.setToolTip(spec.help)
        editor.setProperty('setting_key', spec.key)
        editor.setProperty('setting_scope', scope)
        editor.setProperty('value_editor', not self.read_only)
        self.source = label('')
        self.source.setWordWrap(False)
        self.reset = button('Reset', lambda: edit(spec.key, None, True))
        self.reset.setToolTip('Remove this override and inherit the parent value')
        box = QVBoxLayout(self) if compact else QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(editor, 1)
        if compact:
            tail = QHBoxLayout()
            box.addLayout(tail)
        else:
            tail = box
        tail.addWidget(self.source)
        tail.addWidget(self.reset)
        self.source.setVisible(not spec.metadata)
        self.reset.setVisible(not spec.metadata)

    def make_editor(self, edit):
        spec = self.spec

        def changed(*_):
            edit(spec.key, self.read())

        if spec.kind == 'choice':
            widget = combo(spec.choices)
            widget.setMinimumContentsLength(0)
            widget.setSizeAdjustPolicy(widget.SizeAdjustPolicy.AdjustToContents)
            self.read = widget.currentData
            self.write = lambda value: widget.setCurrentIndex(widget.findData(value))
            widget.currentIndexChanged.connect(changed)
        elif spec.kind == 'bool':
            widget = QCheckBox()
            self.read, self.write = widget.isChecked, widget.setChecked
            widget.toggled.connect(changed)
        elif spec.kind == 'number':
            widget = QDoubleSpinBox()
            widget.setRange(*spec.limits)
            widget.setSuffix(spec.unit)
            widget.setSingleStep(0.1 if spec.key == 'pause_seconds' else 5 if spec.key == 'background_gain' else 1)
            self.read = lambda: widget.value() / spec.scale
            self.write = lambda value: widget.setValue(value * spec.scale)
            widget.valueChanged.connect(changed)
        elif spec.kind == 'multiline':
            widget = QPlainTextEdit()
            self.read, self.write = widget.toPlainText, widget.setPlainText
            widget.textChanged.connect(changed)
        else:
            widget = QLineEdit()
            self.read, self.write = widget.text, widget.setText
            widget.textChanged.connect(changed)
        return widget

    def load(self, value, source, overridden):
        self.source.setText(source)
        self.reset.setEnabled(overridden)
        blocked = self.editor.blockSignals(True)
        try:
            if self.read_only:
                self.editor.setText(('On' if value else 'Off') if isinstance(value, bool) else str(value))
            elif self.write and self.read() != value:
                self.write(value)
        finally:
            self.editor.blockSignals(blocked)
