#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic local UI benchmark; no network, model load or audio playback.

QT_QPA_PLATFORM=offscreen .venv/bin/python tools/bench_ui.py
Counts are query-body executions (cache hits do not execute a query body).
Timing excludes tracing, fixture setup, queued painting and aggregate flushing.
"""
import argparse
import copy
import inspect
import json
import statistics
import sys
import tempfile
import time
import wave
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from autotalk.app import MainWindow
from autotalk.project import Project, Slide, file_hash
from autotalk.settings import SettingsDialog


def prepared_project(root, count):
    project = Project(root, title=f'Benchmark: {count} prepared slides')
    project.slides.extend(Slide(i + 1, f'Topic {i + 1}\nSupporting explanation') for i in range(count))
    image = QImage(800, 450, QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    for slide in project.slides:
        path = project.image(slide); path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(path))
        project.set_narration(slide, f'This is the narration for topic {slide.page}. ' * 5)
        slide.audio_key = project.speech_key(slide)
        slide.audio_file = project.audio_name(slide)
        path = project.audio(slide); path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), 'wb') as stream:
            stream.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            stream.writeframes(b'\0\0' * 7200)
        slide.duration = .3
        slide.audio_sha256 = file_hash(path)
    project.save()
    return project


def benchmark(count, repeats):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(root / 'config'))
        project = prepared_project(root / 'talk', count)
        window = MainWindow(); window.adopt(project); window.show()
        QApplication.processEvents()
        window.elapsed_timer.stop(); window.transport.timer.stop()
        original = copy.deepcopy(project)
        def restore():
            nonlocal project
            project = copy.deepcopy(original)
            window.adopt(project)
            window.select_slide(count // 2)
            window.elapsed_timer.stop(); window.transport.timer.stop()
        codes = {inspect.unwrap(getattr(Project, name)).__code__: name
                 for name in ('ready', 'speech_key', 'text_ready', 'asset')}
        codes.update({inspect.unwrap(method).__code__: name for name, method in
                      [('refresh', MainWindow.refresh), ('dialog_loads', SettingsDialog.load_settings),
                       ('configuration_changed', MainWindow.configuration_changed)]})
        result = {'slides': count}
        actions = {'refresh': window.refresh,
                   'keystroke': lambda: window.narration.insertPlainText('x'),
                   'selection': lambda: window.slide_list.setCurrentRow((window.transport.index + 1) % count)}
        actions.update({
            'after': lambda: window.inspector.slide_after.setCurrentIndex(window.inspector.slide_after.findData('pause')),
            'pause': lambda: window.inspector.inherit_pause.setChecked(False),
            'budget': lambda: window.inspector.slide_budget.setValue(75),
            'include': lambda: window.inspector.slide_include.setChecked(False),
            'duration': lambda: window.minutes.setValue(12),
            'record': lambda: window.record.setChecked(True),
            'mode': lambda: window.mode.setCurrentText('Realtime'),
            'editor_next': lambda: window.editor_next.click() if hasattr(window, 'editor_next') else window.slide_list.setCurrentRow(window.transport.index + 1),
            'editor_previous': lambda: window.editor_previous.click() if hasattr(window, 'editor_previous') else window.slide_list.setCurrentRow(window.transport.index - 1),
        })
        if hasattr(window, 'flush_refresh'):
            actions['aggregates'] = window.flush_refresh
        for name, action in actions.items():
            samples = []
            for _ in range(repeats):
                restore()
                if name == 'aggregates':
                    window.narration.insertPlainText('x')
                start = time.perf_counter(); action()
                samples.append((time.perf_counter() - start) * 1000)
            restore()
            if name == 'aggregates':
                window.narration.insertPlainText('x')
            counts = Counter()
            def trace(frame, event, arg):
                if event == 'call' and frame.f_code in codes:
                    counts[codes[frame.f_code]] += 1
            sys.setprofile(trace)
            try:
                action()
            finally:
                sys.setprofile(None)
            result[name] = {'ms': round(statistics.median(samples), 3),
                            'calls': {name: counts[name] for name in codes.values()}}
        window.close(); window.deleteLater(); QApplication.processEvents()
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=9)
    args = parser.parse_args()
    app = QApplication([])
    print(json.dumps([benchmark(n, args.repeats) for n in (20, 60)], indent=2))
