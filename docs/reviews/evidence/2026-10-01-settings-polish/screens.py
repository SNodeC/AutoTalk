"""Capture the requested settings surfaces with real Qt widgets and isolated preferences."""
import json
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from autotalk.app import MainWindow
from autotalk.runtime import Task
from autotalk.services import import_pdf

app = QApplication([])
output = Path(os.environ['AUTOTALK_SCREEN_OUTPUT'])
output.mkdir(parents=True, exist_ok=True)
scale = os.environ.get('QT_SCALE_FACTOR', '1')
records = []
base = QPalette(app.palette())


def capture(widget, name, size):
    widget.resize(*size)
    app.processEvents()
    QTest.qWait(250)
    assert widget.size().toTuple() == size
    name = f'{name}-scale{scale}.png'
    assert widget.grab().save(str(output / name))
    records.append({'file': name, 'size': size, 'style': app.style().objectName()})


with tempfile.TemporaryDirectory() as tmp:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(Path(tmp) / 'config'))
    pdf = next(Path('/home/voc/projects/Hagenberg/DACHS/2026/DACHS').glob('*.pdf'))
    project = import_pdf(pdf, Path(tmp) / 'talk', Task(lambda _: None))
    project.title = 'Settings polish — inspection'
    project.set_narration(project.slides[0], 'Welcome. This slide introduces the presentation.')
    w = MainWindow()
    w.adopt(project)
    w.show()
    for dark in (False, True):
        palette = QPalette(base)
        if dark:
            for role, color in (
                (QPalette.Window, '#31363b'), (QPalette.Base, '#232629'),
                (QPalette.AlternateBase, '#31363b'), (QPalette.Button, '#31363b'),
                (QPalette.WindowText, '#eff0f1'), (QPalette.Text, '#eff0f1'),
                (QPalette.ButtonText, '#eff0f1'), (QPalette.Mid, '#62686e'),
            ):
                palette.setColor(role, QColor(color))
        app.setPalette(palette)
        theme = 'dark' if dark else 'light'
        next(b for b in w.inspector.findChildren(QToolButton) if b.text() == 'Timing').setChecked(True)
        for size in ((940, 680), (1100, 850)):
            w.resize(*size)
            w.editor.setSizes([154, size[0] - 354, 200])
            capture(w, f'inspector-{theme}-{size[0]}', size)
            records[-1]['inspector_width'] = w.inspector.width()
        dialog = w.settings[1]
        dialog.show_section('Timing & playback')
        for size in ((760, 580), (920, 760)):
            dialog.resize(*size)
            app.processEvents()
            bar = dialog.pages.currentWidget().verticalScrollBar()
            bar.setValue(bar.maximum())
            capture(dialog, f'timing-{theme}-{size[0]}', size)
            assert dialog.pages.currentWidget().horizontalScrollBar().maximum() == 0
        dialog.reject()
    w.close()
(output / f'manifest-{scale}.json').write_text(json.dumps(records, indent=2))
print(f'Captured {len(records)} screenshots; style={app.style().objectName()}, scale={scale}')
