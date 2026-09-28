# Wayland capture failure recovery

This implements the AutoTalk-side repair identified by the
[portal crash analysis](2026-09-28-wayland-crash-analysis.md). The installed KDE
portal is unchanged; its virtual-display crash is a separate outstanding defect.

## Behavior and ownership

The existing native Qt 6.10.2 build patch now reports unsuccessful ScreenCast
responses through QScreenCapture's error interface after resetting request state.
Cancellation says “Screen sharing was cancelled.” Other rejected requests say
“The screen-sharing service could not start capture.” Previously Qt only logged
a warning, leaving AutoTalk waiting for a stream that would never arrive.

An integration probe then exposed duplicate reporting in AutoTalk: the capture
callback reported the error, and playback polling reported it again. Playback
now queues capture failures to its own UI-thread handler, closes the owned
capture through its existing stop/finalization path, and reports once. The
duplicate polling branch is removed. This handles failures from the Qt callback
and from recording workers, including during a paused live demonstration.

Visual verification exposed a remaining UI lifetime issue: stopped capture alone
left the fullscreen presentation window alive and editing disabled. The existing
application error handler now ends a presentation whose transport has already
stopped before displaying the error. The editor is enabled and Start retries
without requiring a manual End action. Other paused playback errors retain
their existing recovery behavior.

The invariant is one recording owner and one failure-reporting path, with
cleanup outside active backend callbacks and worker threads. No new backend,
portal client, timeout, polling flag or recording-state cache was introduced.
If finalizing a partial recording itself fails, the existing ownership/retry
behavior remains in force rather than discarding the capture.

## Verification

- Final full suites: standard Qt 6.11.2 **372 passed in 75.73 seconds**;
  native Qt 6.10.2/Breeze **372 passed in 94.01 seconds**, neither with skips.
- A private D-Bus ScreenCast responder exercised the real native Qt request
  sequence and returned cancellation (1) or failure (2) at Start. For each result,
  two consecutive Start attempts produced one notification each, released capture,
  stopped playback, returned to the enabled editor and allowed another request.
- The same failure probe against the unpatched native library failed: no error
  was delivered and the transport remained buffering. This establishes that the
  test exercises the library correction, rather than merely simulating its signal.
- Regression tests also inject a recording-worker failure while buffering and
  while paused. Cleanup and notification run on the UI thread, occur once, and
  a new capture can be started.
- Under Xvfb/native Breeze, an actual modal error was displayed and dismissed by
  pointer interaction; Start was clicked again. The recovered editor and dialog
  were inspected visually: [error dialog](evidence/2026-09-28-wayland-fix/error-dialog.png),
  [enabled editor](evidence/2026-09-28-wayland-fix/recovered.png).
- The rebuilt native bundle audit verified 27 Qt/plugin files, all 18 mapped Qt
  libraries inside the bundle, Breeze loaded, and a clean smoke-test exit.
- Pointer/keyboard interaction with the packaged executable opened application,
  talk and slide settings, reloaded the saved test manifest and exited cleanly
  on SIGINT. The local launcher bundle was rebuilt; restart AutoTalk to use it.

The separate real Wayland attempt waited 240 seconds without receiving a ready
shared stream and closed. It produced no application error and no recording.
No successful sharing selection was observed. Its silent virtual audio output
was removed; physical speaker settings were untouched. Successful real Wayland
recording remains an acceptance gap, distinct from the verified failure handling.

An intermediate focused test command did not explicitly select X11 for Xvfb;
two popup-interaction cases failed under the inherited Wayland environment. It
is not accepted as Xvfb verification. Final full-suite runs explicitly select
X11 and use disposable virtual PipeWire outputs, with no test expectations relaxed.

## Build scope and accounting

The dependency fix is applied by the existing Linux `--system-qt` build path for
Qt 6.10.2, used by this machine's native bundle. It does not modify system Qt or
KDE. Stock PySide wheels and other Qt versions do not acquire this native patch
automatically; the successful native integration result must not be attributed
to those builds. Windows/macOS packaging and deferred QEMU scope are unchanged.

Python production changes: **9 additions, 3 deletions, net +6 lines**. The new
native Qt source hunk replaces one warning line with two error-reporting lines:
**net +1 C++ line**. Total runtime-source growth is **+7**, bringing the existing
approved allowance to **247/250**. The tracked patch file additionally includes
patch context and explanatory metadata; its file diff is +17/-1.
Tests/probes: **90 additions, no deletions**. Raw logs, the private-bus runner,
native build and isolated acceptance artifacts are in `artifacts/wayland-fix/`.
