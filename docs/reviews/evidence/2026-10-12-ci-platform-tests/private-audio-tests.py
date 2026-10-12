"""Run every test against a private audio server without touching desktop audio."""
import os
from pathlib import Path
import subprocess
import time
import tempfile

root = Path.cwd()
with tempfile.TemporaryDirectory(prefix='autotalk-ci-') as directory:
    socket = Path(directory) / 'native.sock'
    env = dict(
        os.environ,
        XDG_RUNTIME_DIR=directory,
        DBUS_SESSION_BUS_ADDRESS='unix:path=' + directory + '/no-dbus',
        PULSE_SERVER='unix:' + str(socket),
        QT_QPA_PLATFORM='offscreen',
        QT_AUDIO_BACKEND='pulseaudio',
        PYTHONPATH=str(root / 'src'),
    )
    with open('/tmp/autotalk-private-pulse.log', 'w') as log:
        pulse = subprocess.Popen([
            'pulseaudio', '--daemonize=no', '--use-pid-file=no', '--exit-idle-time=-1', '-n',
            '--load=module-native-protocol-unix socket=' + str(socket) + ' auth-anonymous=1',
            '--load=module-null-sink sink_name=autotalk_ci channels=2',
        ], env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                if socket.exists():
                    break
                if pulse.poll() is not None:
                    raise RuntimeError('Private audio server failed')
                time.sleep(.05)
            else:
                raise RuntimeError('Private audio server did not become ready')
            with open('/tmp/autotalk-ci-audio-full.log', 'w') as output:
                result = subprocess.run(
                    [str(root / '.venv/bin/python'), '-m', 'pytest', '-vv'],
                    env=env, stdout=output, stderr=subprocess.STDOUT,
                )
            print('Full suite exit:', result.returncode)
        finally:
            pulse.terminate()
            try:
                pulse.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pulse.kill()
                pulse.wait()
raise SystemExit(result.returncode)
