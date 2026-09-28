"""Native Qt registry/lifetime regression; no real display or audio access.

Run with the native Qt PYTHONPATH/LD_LIBRARY_PATH under:
    xvfb-run -a dbus-run-session -- python tests/probes/pipewire_lifecycle.py OUT
A private PipeWire daemon advertises synthetic source metadata only. This verifies
initialization, cancellation and teardown, not negotiated video-frame delivery.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def client():
    import shiboken6
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    print(json.dumps({'native_library': sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if '/libQt6Multimedia.so' in line})}), flush=True)
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    results = []
    for attempt in range(50):
        session, capture, sink = QMediaCaptureSession(), QScreenCapture(), QVideoSink()
        session.setScreenCapture(capture)
        session.setVideoSink(sink)
        errors = []
        capture.errorOccurred.connect(lambda code, message: errors.append(message))
        messages.clear()
        started = time.monotonic()
        capture.start()
        while not errors and not any(') result= true' in m for m in messages):
            QTest.qWait(10)
            assert time.monotonic()-started < 5, messages
        if attempt % 5 == 0:
            assert errors == ['Screen sharing was cancelled.'], errors
        elif attempt % 5 == 2:
            assert errors == ['Failed to open pipewire remote file descriptor'], errors
        elif attempt % 5 == 3:
            assert len(errors) == 1 and 'Synthetic remote failure' in errors[0], errors
        else:
            assert not errors, errors
        capture.stop()
        session.setScreenCapture(None)
        session.setVideoSink(None)
        shiboken6.delete(capture)
        shiboken6.delete(session)
        shiboken6.delete(sink)
        QTest.qWait(10)
        result = dict(attempt=attempt, cancelled=attempt % 5 == 0,
                      missing_source=attempt % 5 == 2, remote_failure=attempt % 5 == 3,
                      seconds=round(time.monotonic()-started, 3))
        results.append(result)
        print(json.dumps(result), flush=True)
    print(json.dumps({'cycles': len(results), 'completed': True}), flush=True)


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='autotalk-pw-') as temporary:
        runtime = Path(temporary)
        env = dict(os.environ)
        for key in ('PIPEWIRE_PROPS', 'PIPEWIRE_REMOTE', 'PIPEWIRE_CONFIG_DIR'):
            env.pop(key, None)
        env.update(XDG_RUNTIME_DIR=temporary, PIPEWIRE_RUNTIME_DIR=temporary)
        config = '''context.properties = { core.daemon = true core.name = pipewire-0 }
context.spa-libs = { support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-access }
 { name = libpipewire-module-spa-node-factory }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-link-factory }
]
context.objects = [
'''
        for i in range(12):
            config += (' { factory = spa-node-factory args = { '
                       'factory.name = support.null-audio-sink '
                       f'node.name = synthetic-video-{i} '
                       'media.class = Video/Source audio.position = [ FL FR ] } }\n')
        (runtime/'daemon.conf').write_text(config+']\n')
        portal = None
        with (output/'pipewire.log').open('w') as daemon_log, (output/'portal.log').open('w') as portal_log:
            daemon = subprocess.Popen(['pipewire', '-c', str(runtime/'daemon.conf')],
                                      env=env, stdout=daemon_log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic()+5
                while True:
                    snapshot = subprocess.run(['pw-dump'], env=env, capture_output=True, text=True, timeout=5)
                    if snapshot.returncode == 0:
                        break
                    assert daemon.poll() is None and time.monotonic() < deadline, snapshot.stderr
                    time.sleep(.02)
                nodes = json.loads(snapshot.stdout)
                env['AUTOTALK_PIPEWIRE_NODE'] = str(next(i['id'] for i in nodes
                    if i.get('info', {}).get('props', {}).get('node.name') == 'synthetic-video-0'))
                portal = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('portal_failure_server.py')), 'cycle'],
                                          env=env, stdout=subprocess.PIPE, stderr=portal_log, text=True)
                assert portal.stdout.readline().strip() == 'ready'
                env.update(QT_QPA_PLATFORM='xcb', XDG_SESSION_TYPE='wayland',
                           QT_LOGGING_RULES='qt.multimedia.pipewire.capture=true')
                with (output/'client.log').open('w') as log:
                    result = subprocess.run([sys.executable, __file__, '--client'], env=env,
                                            stdout=log, stderr=subprocess.STDOUT, timeout=45)
                (output/'exit.json').write_text(json.dumps({'returncode': result.returncode}))
                assert result.returncode == 0, (result.returncode, (output/'client.log').read_text())
            finally:
                if portal:
                    portal.terminate()
                    portal.wait(timeout=5)
                daemon.terminate()
                daemon.wait(timeout=5)
    print('50 native capture/cancellation/failure/teardown cycles passed', flush=True)


if __name__ == '__main__':
    if sys.argv[1] == '--client':
        client()
    else:
        run(Path(sys.argv[1]).resolve())
