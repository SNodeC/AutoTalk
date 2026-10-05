# QTBUG-151052 — standalone C++ reproducer

Issue: <https://qt-project.atlassian.net/browse/QTBUG-151052>

This replaces the earlier PySide6 probe. Both the Qt client and the synthetic
ScreenCast portal are C++. No Python, AutoTalk, Qt private APIs, display-sharing
permission or actual screen/audio capture is needed.

The portal accepts CreateSession, SelectSources and Start, advertises a synthetic
stream, then returns `org.freedesktop.portal.Error.Failed` / `Synthetic remote failure`
from OpenPipeWireRemote. The client requires that exact error before calling
QScreenCapture::stop() and destroying the capture objects. It repeats 20 times.
Failure to reach the injected error is an **inconclusive test**, never a pass.

## Build and run

Requirements: Linux, a C++17 compiler, CMake, Ninja (or another CMake generator),
Qt Core/Gui/DBus/Multimedia development files and the FFmpeg multimedia plugin,
PipeWire runtime, Xvfb/xauth, and dbus-run-session. Qt binary SDKs also need their
matching Qt Declarative libraries if their FFmpeg plugin links to Quick/QML.

```sh
cmake -S . -B build -G Ninja -DCMAKE_PREFIX_PATH=/path/to/qt
cmake --build build
xvfb-run -a dbus-run-session -- ./run.sh "$PWD/build/qtbug151052"
```

Choose a complete, matching Qt installation. When needed, prefix the run with
`LD_LIBRARY_PATH=/path/to/qt/lib`; do not include AutoTalk's patched bundle.
The runner defaults to `QT_QPA_PLATFORM=xcb` and sets `XDG_SESSION_TYPE=wayland`
and `QT_MEDIA_BACKEND=ffmpeg`. Xvfb provides the GUI connection while the Wayland
session setting selects PipeWire capture. D-Bus is private to this run. The
runner owns the mock portal and removes it afterwards; the real desktop portal
and PipeWire configuration are untouched.

For Qt builds without the XCB plugin, the same failure path can be tested with
the offscreen plugin (no Xvfb needed):

```sh
QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH=/path/to/qt/lib \
  dbus-run-session -- ./run.sh "$PWD/build/qtbug151052"
```

For a C++ backtrace:

```sh
LD_LIBRARY_PATH=/path/to/qt/lib xvfb-run -a dbus-run-session -- \
  ./run.sh "$PWD/build/qtbug151052" --gdb
```

Without `--gdb`, exit 0 means all 20 expected errors were followed by successful
cleanup. Exit 139 indicates SIGSEGV; exit 2 means the required error was not
observed. In GDB mode, inspect the signal/backtrace rather than GDB's exit code.

The fixture supplies introspection and honors optional `handle_token` values:
newer Qt subscribes to the derived request path before making its method call;
older Qt can omit the token and subscribe to the returned path. The injected
failure and the client cleanup sequence are identical across versions.

## Verification

See `RESULTS.md` and the attached logs for tested versions, build provenance,
known warnings and exact results. The test covers this particular partial-
initialization cleanup path; it is not a full screen-recording qualification.
