"""Run the visual matrix using the existing Xvfb/WM driver and a null sink."""
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
phase = sys.argv[1]
source = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else root / 'src'
out = root / 'docs/reviews/evidence/2026-10-01-settings-polish/screens' / phase
sink = 'autotalk_polish_capture_' + str(os.getpid())
module = subprocess.check_output(['pactl', 'load-module', 'module-null-sink', 'sink_name=' + sink], text=True).strip()
try:
    for tag, python in [('wheel', '.venv/bin/python'), ('native', 'artifacts/open-tasks/venv-qt610/bin/python')]:
        for scale in ('1', '1.5'):
            folder = out / tag
            folder.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ, PYTHONPATH=str(source), QT_QPA_PLATFORM='xcb', QT_SCALE_FACTOR=scale,
                       PULSE_SINK=sink, PULSE_SOURCE=sink + '.monitor',
                       PIPEWIRE_PROPS=json.dumps({'target.object': sink, 'node.dont-reconnect': False}),
                       AUTOTALK_SCREEN_OUTPUT=str(folder))
            if tag == 'native':
                env['PYTHONPATH'] = str(root / 'build/system-qt') + ':' + str(source)
                env['LD_LIBRARY_PATH'] = str(root / 'build/system-qt/PySide6/Qt/lib') + ':' + str(root / 'artifacts/open-tasks/venv-qt610/lib/python3.12/site-packages/shiboken6')
            with (folder / f'capture-{scale}.log').open('w') as log:
                result = subprocess.run(['xvfb-run', '-a', '-s', '-screen 0 1920x1440x24',
                    'dbus-run-session', '--', python,
                    'docs/reviews/evidence/2026-09-30-ui-structure-perf/xvfb-session.py',
                    python, 'docs/reviews/evidence/2026-10-01-settings-polish/screens.py'],
                    env=env, stdout=log, stderr=subprocess.STDOUT)
            print(phase, tag, scale, result.returncode, flush=True)
            if result.returncode:
                raise RuntimeError(f'Capture failed: {folder}, scale={scale}')
finally:
    subprocess.run(['pactl', 'unload-module', module], check=True)
