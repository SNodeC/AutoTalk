"""Reproduce failed-portal cleanup using public Qt APIs only, without AutoTalk.

Run with the desired PySide6 interpreter under xvfb-run -a dbus-run-session:
    python tests/probes/qt_remote_failure.py
The private portal returns a D-Bus error; no real display/audio access occurs.
A nonzero exit is a failed cleanup, not an expected success. Stock 6.10.2 and
6.11.2 currently crash here. Keep this probe separate from the in-process suite.
"""
import os
from pathlib import Path
import subprocess
import sys


def application_client():
    import json
    import tempfile
    import shiboken6
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from autotalk.project import Project
    from autotalk.screen_capture import ScreenCapture

    app = QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        project = Project(Path(directory))
        # Capture snapshots the PDF but does not parse it during initialization.
        project.asset('slides.pdf').write_bytes(b'%PDF-1.4\n%%EOF\n')
        for attempt in range(20):
            errors = []
            capture = ScreenCapture(project, errors.append)
            for _ in range(200):
                QTest.qWait(10)
                if errors:
                    break
            assert len(errors) == 1 and 'Synthetic remote failure' in errors[0], errors
            root = capture.close()
            QTest.qWait(30)
            assert not capture.workers and not capture.ready
            assert not shiboken6.isValid(capture.session)
            journal = json.loads((root/'session.json').read_text())
            assert journal['duration'] == 0 and journal['error'] == errors[0]
        print('20 AutoTalk failed-initialization/cleanup cycles passed', flush=True)


def client():
    from PySide6.QtCore import qVersion
    from PySide6.QtWidgets import QApplication
    from PySide6.QtMultimedia import QScreenCapture, QMediaCaptureSession, QVideoSink
    from PySide6.QtTest import QTest

    app = QApplication([])
    for attempt in range(20):
        session = QMediaCaptureSession()
        capture, sink = QScreenCapture(session), QVideoSink(session)
        session.setScreenCapture(capture)
        session.setVideoSink(sink)
        errors = []
        capture.errorOccurred.connect(lambda code, message: errors.append(message))
        capture.start()
        for _ in range(200):
            QTest.qWait(10)
            if errors:
                break
        print(f"Qt {qVersion()}: {errors}", flush=True)
        assert len(errors) == 1 and 'Synthetic remote failure' in errors[0], errors
        print('Stopping capture through its public API', flush=True)
        capture.stop()
        session.setScreenCapture(None)
        session.setVideoSink(None)
        session.deleteLater()
        QTest.qWait(100)
        print('Clean exit', flush=True)
    print("20 failed-initialization/cleanup cycles passed", flush=True)


if __name__ == '__main__':
    if '--client' in sys.argv:
        application_client() if '--autotalk' in sys.argv else client()
    else:
        env = {**os.environ, 'AUTOTALK_PIPEWIRE_NODE': '123',
               'XDG_SESSION_TYPE': 'wayland', 'QT_QPA_PLATFORM': 'xcb'}
        server = subprocess.Popen(['/usr/bin/python3',
            str(Path(__file__).with_name('portal_failure_server.py')), 'remote-failure'],
            env=env, stdout=subprocess.PIPE, text=True)
        try:
            assert server.stdout.readline().strip() == 'ready'
            result = subprocess.run([sys.executable, __file__, '--client', *sys.argv[1:]], env=env, timeout=30)
            print(f'Client exit: {result.returncode}', flush=True)
            sys.exit(0 if result.returncode == 0 else 1)
        finally:
            server.terminate()
            server.wait(timeout=5)
