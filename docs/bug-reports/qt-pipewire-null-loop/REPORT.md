# QScreenCapture::stop() crashes in pw_thread_loop_stop after OpenPipeWireRemote fails

Suggested project/component: Qt / Multimedia

Affected versions verified: Qt 6.10.2 and 6.11.2

Platform: Linux, PipeWire screen capture / XDG ScreenCast portal

## Summary

If the ScreenCast portal returns a D-Bus error from `OpenPipeWireRemote`, Qt emits
`QScreenCapture::errorOccurred`. Calling `QScreenCapture::stop()` afterwards
crashes with SIGSEGV in `pw_thread_loop_stop()`.

This issue was discovered while developing [AutoTalk](https://github.com/SNodeC/AutoTalk),
a Qt-based presentation application. The attached standalone reproducer does not
require AutoTalk or import its code; building AutoTalk is unnecessary to reproduce
the crash.

The attached reproducer uses only public Qt APIs through PySide6. It contains no
application imports or dependency modifications. A private D-Bus test portal
deterministically injects the remote-opening failure. No real screen-sharing
permission, screen capture, microphone access or speaker playback is needed.

## Environment

- Debian GNU/Linux forky/sid, x86_64.
- Kernel: `7.1.8+deb14-amd64`.
- PipeWire library package: `libpipewire-0.3-0t64 1.6.8-1`.
- Reproduced with unmodified Debian Qt Multimedia `6.10.2-4`, matching PySide6
  6.10.2, and separately with the unmodified PySide6/Qt 6.11.2 wheel distribution.
- The reproducer uses Xvfb for the Qt GUI connection and sets
  `XDG_SESSION_TYPE=wayland` to exercise Qt's PipeWire screen-capture path.
  This is deliberate: the portal runs on a private D-Bus session, independent of
  the real desktop compositor.

## Reproduction

Extract the attached ZIP. Keep `reproduce.py` and `portal_failure_server.py` in
the same directory.

Dependencies:

- Python with PySide6 6.11.2 (or the tested matching 6.10.2 setup).
- `xvfb-run`, `xauth` and `dbus-run-session`.
- PipeWire runtime library.
- `/usr/bin/python3` with `dbus-python` and PyGObject/GLib. On Debian these are
  provided by `python3-dbus` and `python3-gi`.

For example, from the extracted directory with an unmodified PySide6 environment:

```sh
python3 -m venv qt-repro-env
qt-repro-env/bin/python -m pip install PySide6==6.11.2
xvfb-run -a dbus-run-session -- qt-repro-env/bin/python reproduce.py
```

The runner starts the private test portal using `/usr/bin/python3`, then launches
the Qt client using the same interpreter as the runner. Do not add paths to a
locally patched Qt installation when testing the stock behavior.

The test portal successfully answers `CreateSession`, `SelectSources` and
`Start`. It advertises one synthetic stream, then deliberately returns
`org.freedesktop.portal.Error.Failed` with message `Synthetic remote failure`
from `OpenPipeWireRemote`. The synthetic node is never opened because that
D-Bus call fails first. The fixture's `remote-failure` mode is selected by the
runner; the other fixture modes are not involved in this reproduction.

The Qt client creates a `QMediaCaptureSession`, a parented `QScreenCapture` and
`QVideoSink`, starts capture, waits for the error signal, then calls `stop()`.
It attempts 20 consecutive initialization/cleanup cycles; stock Qt crashes on
the first cycle.

## Expected result

The failed portal request should produce an error. Stopping and destroying the
capture objects afterwards should safely release any resources that were
actually initialized, without terminating the application.

## Actual result

Qt emits the expected error, then the client crashes when it calls `stop()`:

```text
Qt 6.11.2: ['Failed to open pipewire remote for org.freedesktop.portal.ScreenCast. Error: name=org.freedesktop.portal.Error.Failed, message=Synthetic remote failure']
Stopping capture through its public API
Client exit: -11
```

`-11` is the child process's SIGSEGV termination reported by Python. The runner
itself returns exit status 1 when its child fails.

Relevant GDB frames from stock Qt 6.10.2:

```text
#0 pw_thread_loop_stop () in libpipewire-0.3.so.0
#1 unknown internal function in libQt6Multimedia.so.6
#2 QtPipeWire::QPipeWireCapture::setActiveInternal(bool)
#3 QPlatformSurfaceCapture::setActive(bool)
```

The attached `backtrace-qt610.txt` includes the fuller trace. Local installation
paths have been replaced with `<stock-PySide6>`; stack frames are otherwise retained.

## Source analysis

In Qt 6.10.2, `QPipeWireCaptureHelper::gotRequestResponse()` handles `StartStream`
by calling `openPipeWireRemote()`, then unconditionally setting `m_state` to
`Streaming`.

If the D-Bus reply is invalid, `openPipeWireRemote()` emits the error and returns
before `open()` allocates `m_threadLoop`. The helper nevertheless reaches the
Streaming state. On stop, `destroy()` calls
`pw_thread_loop_stop(m_threadLoop.get())` without checking whether the loop exists.
This explains the observed crash after partial initialization.

## Minimal proposed correction and verification

The attached local patch guards cleanup of the absent loop:

```diff
-    pw_thread_loop_stop(m_threadLoop.get());
+    if (m_threadLoop)
+        pw_thread_loop_stop(m_threadLoop.get());
```

With this correction in Qt 6.10.2, the same standalone reproducer completes all
20 failure/stop/destruction cycles and exits normally. Re-running it with stock
Qt still crashes. No changes to the application client are required.

This is a minimal cleanup correction, not a claim that the helper's broader
activation/error state transitions are correct. An upstream fix may also choose
to address the unconditional transition to Streaming.

| Library tested | Result |
| --- | --- |
| Stock Qt 6.10.2 | SIGSEGV, first cycle |
| Stock Qt 6.11.2 | SIGSEGV, first cycle |
| Qt 6.10.2 with attached guard | 20 cycles completed, clean exit |

Qt 6.12 has not been tested. The upstream
[event-loop ownership change](https://github.com/qt/qtmultimedia/commit/a02154e751b957386f374146b57b84bbe622b033)
changes this teardown path and may be relevant; I cannot confirm whether it
resolves this reproducer in a released build.

## Related issue

[QTBUG-136981](https://qt-project.atlassian.net/browse/QTBUG-136981) concerns
incorrect capture behavior after permission cancellation on Linux/Wayland.
This report instead concerns a D-Bus failure opening the PipeWire remote followed
by a crash in cleanup. I have not established that the reports are duplicates.

## Attachments

- `reproduce.py`: standalone Qt client and private test runner.
- `portal_failure_server.py`: test portal fixture.
- `stock-qt610.log`, `stock-qt611.log`: stock-library failures.
- `patched-qt610.log`: 20 successful cleanup cycles with the proposed correction.
- `backtrace-qt610.txt`: GDB trace, with local paths redacted.
- `qt-6.10.2-pipewire-cleanup.patch`: the proposed local correction.
