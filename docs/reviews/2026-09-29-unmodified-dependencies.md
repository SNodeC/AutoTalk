# Unmodified dependencies and screen-capture ownership

Historical checkpoint: after this audit the user explicitly approved reapplying
a Qt fix. See `2026-09-29-approved-qt-cleanup.md` for the narrowly scoped correction.
The GStreamer replacement proposed below was not approved or implemented.

Status: dependency restoration and the narrow AutoTalk ownership correction are
implemented. The failed-portal cleanup crash is still reproducible with stock Qt.
The proposed replacement of Linux screen capture awaits architectural approval.

## Requirement and invariant

AutoTalk must work with unmodified dependencies. Its build must not patch or
rebuild Qt, or depend on private Qt source details.

Each recording owns one capture session and its native video objects. Closing the
recording must stop producers, finish workers and release native resources on the
GUI thread, including when Python references remain alive. Cancellation, startup
failure and retry must obey the same ownership contract.

## What changed

- Removed `packaging/qt-6.10.2-pipewire-lifetime.patch` in its entirety, including
  the upstream backport and the three local changes. Removed the source download,
  patching, CMake build and patched-library packaging from `tools/build.py`.
- `--system-qt` now stages installed, unmodified Qt modules and compatible desktop
  plugins. Matching PySide6 remains necessary for ABI compatibility; there is no
  Qt-version-specific correction to maintain.
- Restored 23 identified modified Multimedia shared-library copies in local
  builds and historical artifact bundles to the stock system library. Removed
  identified patch-bearing release archives, obsolete patch/source bundles and
  generated `qtmultimedia-fixed` and `qt-build` directories. Updated six historical build
  script copies that could otherwise recreate the removed patching procedure.
- Restored the modified copies of Qt source files to their release-archive
  contents. Historical investigation reports remain evidence, not current build
  instructions. Their claims about patched builds do not qualify stock builds.
- Gave `QScreenCapture` and `QVideoSink` a common session parent. Close now marks
  recording stopped before stopping frame delivery, joins workers, detaches the
  native objects and schedules their destruction on the GUI thread. Previously,
  they were unparented and Python/signal cycles could defer native destruction.
- Updated the build tests to require stock library bytes and reject patch/CMake
  subprocesses. Updated the early-stop test to assert native destruction instead
  of accessing an object that should no longer exist.

The ownership correction does not establish that Python lifetime was the cause of
every historical native crash. The remaining reproduction below is independent.

## Dependency audit

The system Qt package was not modified: `dpkg -V libqt6multimedia6` is clean.
All 25 bundled Qt library files match their installed-system or same-version
wheel sources. The rebuilt bundle and installed `libQt6Multimedia.so.6.10.2` both
have SHA-256:

```
2d2f64ac228ed64cce614c371eff35059c59d7e94595946f98e4a34acffddeaf
```

Checked 78,085 recorded Python/native-library file entries across 680 package
records in the application environments and private speech data directory.
Apparent mismatches were investigated:

- OpenCV GUI/headless distributions overlap; the installed files match one of
  their upstream package records.
- `flashinfer-python` and `torch-c-dlpack-ext` both distribute `build_backend.py`;
  the installed file matches FlashInfer's record.
- Four PyNvVideoCodec library copies differ from their distributed RECORD entries
  but match the actual binaries in the freshly downloaded, checksum-verified
  upstream 2.0.4 wheel exactly. They were not locally patched and were preserved.

No further locally modified dependency code was identified in this audit. This
is not an audit of every unrelated system package. Detailed inventories, hashes
and logs are under `artifacts/stock-qt/` (local generated evidence).

## Verification

- New ownership regression failed before the application fix: native Qt objects
  remained alive after close. It passes after the fix without garbage collection.
- Full application suite, stock native Qt 6.10.2 under Xvfb:
  **419 passed, 8 deselected**, 105.08 seconds. The deselected cases require audio
  devices; physical meeting audio was not changed for testing.
- Native build with `tools/build.py --system-qt`: completed without rebuilding Qt.
  The rebuilt executable also passed `--smoke-test` under Xvfb.
- Live Plasma/Wayland recording using stock Qt: permission granted, presentation
  started, paused for a demo, continued and ended/saved. Recording continued after
  slides finished. Export decoded with one video and one audio stream, duration
  9.766667 seconds; nonzero test-tone audio RMS 510.15. No capture errors reported.
- Inspected the acceptance screenshots showing the sharing chooser, live demo
  with recording active and the saved recording links. This demonstrates the
  exercised successful path, not exhaustive failure coverage.
- Live test used a disposable silent virtual output; physical speaker and
  microphone mute/volume/routing were not changed.

## Remaining failure: public Qt capture API

`tests/probes/qt_remote_failure.py` imports no AutoTalk application code. Under a
private D-Bus session it creates a standard capture session, screen and sink. A
test portal returns an explicit failure from `OpenPipeWireRemote`. Qt emits the
error; calling its public `stop()` API then crashes with SIGSEGV (child exit -11).
This reproduces with unmodified **6.10.2 and 6.11.2**. GDB on stock 6.10.2
locates the failure in `pw_thread_loop_stop`, called by
`QtPipeWire::QPipeWireCapture::setActiveInternal(bool)`. The probe accesses neither
the real desktop nor real audio devices.

Example command, using the chosen PySide6 interpreter:

```sh
xvfb-run -a dbus-run-session -- .venv/bin/python tests/probes/qt_remote_failure.py
```

The stock 6.10.2 source explains this path: after `openPipeWireRemote()` reports a
failure before creating its loop, the StartStream response handler still sets its
internal state to Streaming. Stop proceeds to destruction of the absent loop.
Application-side QObject parenting cannot repair that internal state transition.
Stock cancellation also lacks the error notification expected by the historical
patched-library probe; that old probe is not evidence of stock compatibility.

This evidence rules out claiming that all recording crashes have been fixed by
the AutoTalk ownership change. Leaking failed capture objects, parsing Qt log
messages, patching private state or merely isolating crashes in another process
would not meet the requested architectural standard.

## Proposed narrow replacement, not yet implemented

Replace only the Linux screen-video acquisition boundary:

1. AutoTalk owns public XDG ScreenCast portal requests, session, selected stream
   and remote file descriptor. Cancellation or error closes exactly the resources
   acquired so far and reports through the existing recording error interface.
2. An unmodified GStreamer PipeWire pipeline consumes the selected stream. Its
   public bus reports readiness, error and completion. No Qt private API or
   Qt-version test is involved.
3. Keep the existing session journal, presentation controls, PulseAudio recording
   and export interface. Preserve a measured common timeline for video and audio.
4. Delete the replaced Qt capture/frame-delivery path; do not retain two Linux
   implementations. Bundle the required stock runtime components so end users do
   not install them manually.
5. Verify permission cancellation at each stage, failed remote connection,
   interrupted stream, immediate stop, repeated retry and successful live recording.

Reduction and ownership changes solve the application lifetime defect but cannot
alter the proven Qt-internal failure. This replacement needs additional portal
and pipeline integration. Requested ceiling: **350 net additional production
lines**, including packaging adjustments; tests accounted separately. Stop and
reassess if a correct implementation cannot fit that boundary. The user's global
engineering instructions require explicit approval before this addition.

Public interfaces:
[Qt capture session](https://doc.qt.io/qt-6/qmediacapturesession.html),
[XDG ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html),
[GStreamer bus](https://gstreamer.freedesktop.org/documentation/gstreamer/gstbus.html).

## Change accounting

Relative to the pre-task working-tree snapshot, excluding prior language work:
production Python **+6 / -29, net -23**. The third-party patch is deleted separately.
The narrow ownership/build regression changes are **+19 / -31, net -12** test
lines. The standalone Qt failure probe and its fixture changes are additional
diagnostic test code (**+63 / -3**), not production code. Total test delta:
+82 / -34, net +48. Documentation and generated artifacts
are counted separately.
