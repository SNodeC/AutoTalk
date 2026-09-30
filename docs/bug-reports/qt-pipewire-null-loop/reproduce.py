"""Reproduce failed-portal cleanup using public Qt APIs only, without AutoTalk.

Run with the desired PySide6 interpreter under xvfb-run -a dbus-run-session:
    python reproduce.py
The private portal returns a D-Bus error; no real display/audio access occurs.
A nonzero exit is a failed cleanup, not an expected success. Stock 6.10.2 and
6.11.2 currently crash here. Keep this probe separate from the in-process suite.
"""
import os
from pathlib import Path
import subprocess
import sys


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
        client()
    else:
        env = {**os.environ, 'QT_TEST_PIPEWIRE_NODE': '123',
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
