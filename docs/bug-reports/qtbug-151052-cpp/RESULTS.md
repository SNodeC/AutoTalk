# QTBUG-151052 — C++ follow-up, 1 October 2026

The same `main.cpp` and private portal fixture are used for each version.
Only the selected Qt installation changes. No AutoTalk code or Python wrapper
is loaded. No source fix is applied to the tested Qt libraries.

## Completed checks

| Qt runtime | GUI platform | Result | Evidence |
| --- | --- | --- | --- |
| System Qt 6.10.2, unpatched | XCB/Xvfb and offscreen | SIGSEGV, exit 139, first cycle in both | `logs/stock610-cpp.log`, `logs/stock610-offscreen-cpp.log`, `logs/stock610-cpp-backtrace.log` |
| Official Qt 6.12.0 Linux GCC SDK | XCB/Xvfb and offscreen | 20/20 cycles completed per run, exit 0 | `logs/stock612-cpp.log`, `logs/stock612-offscreen-cpp.log` |
| Development Qt 6.13.0 alpha1, commits below | offscreen | 20/20 cycles completed, exit 0 | `logs/dev-offscreen-cpp.log` |

The 6.10.2 backtrace reaches `pw_thread_loop_stop()` through
`QtPipeWire::QPipeWireCapture::setActiveInternal(bool)`,
`QPlatformSurfaceCapture::setActive(bool)` and `QScreenCapture::stop()`.
The C++ reproduction confirms that Python wrappers are unnecessary to trigger
the reported failure.

Qt 6.12.0 and the development build no longer crash on this specific
failure/cleanup path. Both still
prints `QObject::killTimer: Timers cannot be stopped from another thread` and
`QObject::startTimer: Timers cannot be started from another thread` during the
cycles. These warnings are included in the logs; the result is **not** a claim
that all capture or threading issues are resolved.

This is a deterministic partial-initialization test, not an end-to-end desktop
recording test. It never opens a real PipeWire stream. Speaker/microphone mute
state, the real desktop portal and the installed application remain unchanged.

## Build and run commands

Commands below were run from the AutoTalk repository root; the attachment can
also be built independently using the shorter commands in `README.md`.

### Unmodified system Qt 6.10.2

This machine lacks the system Qt Multimedia CMake development package. The
existing matching 6.10.2 build tree supplies development metadata/headers only;
the explicit runtime path selects the **unpatched system libraries**. `ldd`
and the GDB trace confirm that selection. The patched application library is
not the runtime under test.

```sh
cmake -S docs/bug-reports/qtbug-151052-cpp \
  -B artifacts/qtbug-151052/probe610 -G Ninja \
  -DQt6Multimedia_DIR="$PWD/build/qtmultimedia-fixed/lib/x86_64-linux-gnu/cmake/Qt6Multimedia"
cmake --build artifacts/qtbug-151052/probe610
LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu \
  ldd artifacts/qtbug-151052/probe610/qtbug151052
LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu \
  xvfb-run -a dbus-run-session -- \
  docs/bug-reports/qtbug-151052-cpp/run.sh \
  "$PWD/artifacts/qtbug-151052/probe610/qtbug151052"
# Repeat with --gdb appended to obtain the attached backtrace.
```

### Qt 6.12.0

An isolated `aqtinstall` environment downloaded official Qt binary archives
(qtbase, ICU, qtmultimedia, qtshadertools and qtdeclarative). No application or
system dependency was upgraded. The matching Declarative libraries are needed
because this SDK's FFmpeg backend links to Qt Quick/QML.

```sh
cmake -S docs/bug-reports/qtbug-151052-cpp \
  -B artifacts/qtbug-151052/probe612 -G Ninja \
  -DCMAKE_PREFIX_PATH="$PWD/artifacts/qtbug-151052/qt612/6.12.0/gcc_64"
cmake --build artifacts/qtbug-151052/probe612
LD_LIBRARY_PATH="$PWD/artifacts/qtbug-151052/qt612/6.12.0/gcc_64/lib" \
  xvfb-run -a dbus-run-session -- \
  docs/bug-reports/qtbug-151052-cpp/run.sh \
  "$PWD/artifacts/qtbug-151052/probe612/qtbug151052"
```

### Development source build

The isolated development build uses these unmodified source checkouts:

| Repository | `dev` commit |
| --- | --- |
| qtbase | `e26d5a8eee0078c24e6a2a741b7a0df18824281a` |
| qtshadertools | `0e2e83bc3de2530b998b9d2547beae68f7178ea1` |
| qtmultimedia | `2169149ee8e37ad58f088f013f141acee14d9918` |

These sources identify themselves as Qt 6.13.0 alpha1. Each repository was
cloned from `https://github.com/qt/<repository>.git` with `--depth 1 --branch dev`.
Compiler: GCC 16.2.0; CMake 4.3.4. Build/install commands:

```sh
cmake -S artifacts/qtbug-151052/dev-src/qtbase \
  -B artifacts/qtbug-151052/dev-build/qtbase -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PWD/artifacts/qtbug-151052/dev-qt" \
  -DQT_BUILD_TESTS=OFF -DQT_BUILD_EXAMPLES=OFF \
  -DFEATURE_widgets=OFF -DFEATURE_sql=OFF \
  -DFEATURE_printsupport=OFF -DFEATURE_testlib=OFF \
  -DFEATURE_concurrent=ON
cmake --build artifacts/qtbug-151052/dev-build/qtbase --parallel 4
cmake --install artifacts/qtbug-151052/dev-build/qtbase

cmake -S artifacts/qtbug-151052/dev-src/qtshadertools \
  -B artifacts/qtbug-151052/dev-build/qtshadertools -G Ninja \
  -DCMAKE_PREFIX_PATH="$PWD/artifacts/qtbug-151052/dev-qt" \
  -DCMAKE_INSTALL_PREFIX="$PWD/artifacts/qtbug-151052/dev-qt" \
  -DCMAKE_BUILD_TYPE=Release -DQT_BUILD_TESTS=OFF -DQT_BUILD_EXAMPLES=OFF
cmake --build artifacts/qtbug-151052/dev-build/qtshadertools --parallel 4
cmake --install artifacts/qtbug-151052/dev-build/qtshadertools

PKG_CONFIG_PATH="$PWD/artifacts/open-tasks/build-deps/root/usr/lib/x86_64-linux-gnu/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}" \
cmake -S artifacts/qtbug-151052/dev-src/qtmultimedia \
  -B artifacts/qtbug-151052/dev-build/qtmultimedia -G Ninja \
  -DCMAKE_PREFIX_PATH="$PWD/artifacts/qtbug-151052/dev-qt" \
  -DCMAKE_INSTALL_PREFIX="$PWD/artifacts/qtbug-151052/dev-qt" \
  -DCMAKE_BUILD_TYPE=Release -DQT_BUILD_TESTS=OFF -DQT_BUILD_EXAMPLES=OFF \
  -DFEATURE_spatialaudio=OFF -DFEATURE_pipewire=ON \
  -DCMAKE_DISABLE_FIND_PACKAGE_Qt6Quick=ON \
  -DCMAKE_DISABLE_FIND_PACKAGE_Qt6Qml=ON \
  -DCMAKE_DISABLE_FIND_PACKAGE_Qt6QuickTest=ON \
  -DCMAKE_DISABLE_FIND_PACKAGE_Qt6QuickControls2=ON
cmake --build artifacts/qtbug-151052/dev-build/qtmultimedia --parallel 4
cmake --install artifacts/qtbug-151052/dev-build/qtmultimedia

cmake -S docs/bug-reports/qtbug-151052-cpp \
  -B artifacts/qtbug-151052/probe-dev -G Ninja \
  -DCMAKE_PREFIX_PATH="$PWD/artifacts/qtbug-151052/dev-qt"
cmake --build artifacts/qtbug-151052/probe-dev
QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH="$PWD/artifacts/qtbug-151052/dev-qt/lib" \
  xvfb-run -a dbus-run-session -- \
  docs/bug-reports/qtbug-151052-cpp/run.sh \
  "$PWD/artifacts/qtbug-151052/probe-dev/qtbug151052"
```

The additional pkg-config directory supplies previously extracted PipeWire 1.6.9
development headers. Runtime PipeWire remains the installed 1.6.8. Qt Concurrent
was initially disabled to minimize the source build, then enabled and Base
rebuilt because Multimedia requires it. No Qt source changes were made.

The initial development run aborted before the test because this source build
has no XCB platform plugin. The final run uses `QT_QPA_PLATFORM=offscreen`.
Both 6.10.2 and 6.12.0 were then rerun with that same environment prefix:
6.10.2 still crashes and 6.12.0 still completes 20 cycles. The fixture and client
code are identical in all three runs. Xvfb was retained in these comparison
commands but is unnecessary for offscreen execution.

## Environment and interpretation

- Linux x86_64, Debian development system; kernel `7.1.8+deb14-amd64`.
- PipeWire runtime 1.6.8.
- Qt 6.10.2 uses system FFmpeg 8.1.2; the Qt 6.12.0 SDK reports FFmpeg 9.0.1.
- The development build also uses system FFmpeg 8.1.2. Its configuration has
  PipeWire screen capture and the FFmpeg plugin enabled; Quick/QML is disabled.
- Xvfb provides the GUI connection (`xcb`); `XDG_SESSION_TYPE=wayland` selects
  the PipeWire capture path. Each run uses its own `dbus-run-session`.
- The fixture advertises a stream and rejects `OpenPipeWireRemote` with
  `Synthetic remote failure`. The client must observe that exact error before
  stopping and destroying its capture objects. Missing it returns exit 2.
- Earlier fixture attempts were inconclusive: a session handle needed string
  encoding, and newer Qt subscribes using `handle_token` before receiving the
  method reply. The final fixture handles both old and new request protocols.
  Qt 6.10.2 was rerun after these corrections and still crashed.
- An initial incomplete 6.12 SDK could not load its multimedia backend because
  matching Quick/QML libraries were missing. Installing qtdeclarative resolved
  that setup issue. Only the final, complete-SDK run is counted above.
- A separate copy containing only `main.cpp`, `CMakeLists.txt` and `run.sh`
  was built against Qt 6.12.0 and completed all 20 cycles (`logs/standalone-run.log`).
- An attachment check without Xvfb completed the client cycles but exposed an
  inherited blocked SIGTERM in the mock portal process. The runner now kills
  only its own disposable portal child with SIGKILL before waiting, so cleanup
  does not depend on the launcher's signal mask. This changes no Qt client code.
- Final attachment verification: extracted ZIP source built against 6.12.0,
  then ran with offscreen/private D-Bus without Xvfb: 20 cycles, exit 0
  (`logs/attachment-run.log`). The finalized runner was also checked on 6.10.2
  (exit 139, `logs/final-610.log`) and development Qt (20 cycles, exit 0,
  `logs/final-dev.log`). No probe or mock portal processes remained afterwards.

Application production changes: **0 lines**. The new C++ program and runner are
standalone diagnostic fixtures, not application functionality. The application
test suite was not rerun because no application code was changed.
Fixture accounting: 146 C++ lines, 6 CMake lines and 22 shell lines (174 total).
