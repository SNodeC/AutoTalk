"""Give an isolated Xvfb test display normal window-manager focus semantics."""
import os
import subprocess
import sys
import tempfile
import time

with tempfile.TemporaryDirectory(prefix='autotalk-xfwm-') as config:
    manager = subprocess.Popen(['xfwm4', '--compositor=off'],
        env={**os.environ, 'XDG_CONFIG_HOME': config}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = subprocess.check_output(['xprop', '-root', '_NET_SUPPORTING_WM_CHECK'], text=True)
            if 'window id #' in state:
                break
            if manager.poll() is not None:
                raise RuntimeError('The isolated window manager exited')
            time.sleep(.02)
        else:
            raise RuntimeError('The isolated window manager did not become ready')
        result = subprocess.run(sys.argv[1:])
    finally:
        manager.terminate()
        manager.wait(timeout=5)
sys.exit(result.returncode)
