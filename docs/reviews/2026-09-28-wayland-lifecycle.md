# Native Wayland initialization and teardown correction

Continuation of the [routing investigation](2026-09-28-wayland-routing-isolation.md).
The Python routing correction remains in place. This change extends the existing
native Qt 6.10.2 patch; it does not replace the capture backend or system Qt.

## Reproduced failures

A private D-Bus portal and private PipeWire daemon advertise synthetic video-source
metadata. They have no access to the real desktop, microphone or speakers. One
source initializes successfully. Twelve visible sources reproduce the generic
“Failed to open pipewire remote file descriptor” error in the previous native
library. An initial probe took 11.447 seconds before reporting failure.

Qt's registry callback ignored the node ID, treated every video-source announcement
as a reason to recreate the capture stream, and reset the initialization sync
sequence each time. Each recreation could wait for a second while draining the
old stream. The callback now accepts only the node selected by the portal.
The selected source is the authority; unrelated registry entries cannot replace
its stream or delay its initialization.

A separate early-failure probe makes OpenPipeWireRemote return a D-Bus error.
The previous teardown then calls pw_thread_loop_stop with a null loop pointer.
This produced SIGSEGV (probe PID 2795997); the saved native stack identifies
pw_thread_loop_stop from QPipeWireCaptureHelper::destroy. Teardown now stops a
loop only when that resource exists.

## Ownership and teardown

The existing teardown destroyed the stream, released its loop lock, and only
then stopped callback dispatch. While initialization was incomplete and registry
hooks remained installed, a callback could recreate the stream in that gap.
This violates the requirement that dispatch stop before its owned stream and
context are destroyed, and is consistent with the earlier core's surviving
stream after state had become NoState.

Teardown now stops the loop before destroying the stream, then releases registry,
core, context and loop in the existing order. The stop call is outside the loop
lock, as required by PipeWire's thread-loop API. The existing destroyStream helper
still locks access to the stream. No extra flag, timeout, cache, callback or second
owner was introduced.

The earlier destructor SIGSEGV itself was not reproduced deterministically in
this investigation. A baseline error-triggered immediate-cleanup test exited
cleanly. The unsafe callback window is removed by ordering; that architectural
correction and repeated successful cleanup are evidence, not proof that every
historical crash necessarily had the same cause.

## Regression proof

`tests/probes/pipewire_lifecycle.py` starts its own PipeWire daemon and reuses the
private portal responder. Fifty cycles cover:

- 10 cancelled sharing requests;
- 20 successful initializations with 12 advertised sources;
- 10 missing selected-source failures;
- 10 failures before a PipeWire loop exists.

Each cycle stops capture, detaches the session, deletes the native objects and
then starts a fresh capture, matching AutoTalk's ownership per presentation.
The test observes the native initialization result/error and process survival;
it does not claim real video-frame delivery from synthetic metadata.

The final library passes all 50 cycles, with successful initializations around
0.1 seconds. That timing includes a synthetic portal response, not human sharing
permission or Realtime speech preparation. The same selected-source regression
fails against the previous library; an explicit LD_PRELOAD and /proc/self/maps
record verify the negative control actually loaded that library. An earlier
LD_LIBRARY_PATH-only comparison inadvertently loaded the corrected library due
to loader search order and is not counted as a valid negative control.

The early-failure extension crashed before the null-resource guard and passes
afterward. The existing application-level cancellation/rejection probes also pass:
one error per attempt, capture released, editor restored, Start usable again.
The full patch applies to pristine Qt 6.10.2 sources; its resulting helper source
is compared with the compiled source.

Run the native regression with the matching Qt environment under:

```sh
xvfb-run -a dbus-run-session -- python tests/probes/pipewire_lifecycle.py /tmp/autotalk-lifecycle-results
```

Dependencies: Linux PipeWire tools, system Python dbus/GLib, matching PySide6 and
the patched native Qt library. Raw logs, private core and reproducer artifacts
remain under `artifacts/wayland-lifecycle/`; cores and desktop images are not committed.

## Scope and accounting

Effective native production source: **5 lines added, 3 removed, net +2**.
This includes replacing the ignored ID with a selected-source guard, moving the
existing stop call, and guarding a missing loop. Patch-file context/metadata are
not runtime-source growth. The existing allowance moves from 247/250 to 249/250.
Python production changes for this continuation: zero. The separately pending
routing correction has zero net Python growth.

The native `--system-qt` packaging path carries this patch. Stock Qt wheels do not
automatically receive it. Windows/macOS execution and QEMU remain deferred.
KDE's virtual-screen creation crash is unchanged. The 15–20-second Realtime
startup target remains deferred and is not satisfied by these capture timings.

Final native suite: **372 passed in 94.33 seconds**, no skips. The standard
Qt 6.11.2 suite had already passed 372 tests for the Python routing correction;
these additional native changes do not modify that wheel. The final 50-cycle
native regression and both application cancellation/rejection probes pass.
Test/probe source changes: **146 additions, 4 removals, net +142**.

The rebuilt package audit verifies 27 Qt/plugin hashes, 18 Qt libraries loaded
from within the bundle, Breeze loaded and smoke exit 0. Its native library is
built from the checked, reproducibly patched source, with no diagnostic logging.

## Final live Wayland acceptance — passed

The pending final-library run completed after the user granted Plasma sharing
permission for the existing display. No further permission is needed for this
verification. This follows the two successful runs in the routing report, which
predated the additional native correction. An earlier pending run was closed
when the final guard became available and is not counted as a pass.

The test exercised the real MainWindow and presentation controls on Wayland:
Start, leave fullscreen, pause for a live demo, Continue, finish both slides,
continue recording afterward, and End presentation and save video. The editor
returned with Open video / audio and Open folder enabled. The process exited 0,
reported no application errors, and removed its disposable virtual audio output.
No physical speaker or microphone settings were changed by the test.

Evidence is local under `artifacts/wayland-lifecycle/final-live/`: the harness,
`wayland.log`, `session/result.json`, screenshots and saved recording. Desktop
images and recordings are deliberately not committed. The final native library
matches the installed bundle (SHA-256
`5537cedf957b657d492adf7371147c05446acc78021a116ba9b43fd33b05659f`).

| Measurement | Result |
| --- | --- |
| Capture wall time | 9.663 seconds |
| Raw screen track | 9.500 seconds |
| Exported MP4 | 9.467 seconds; one video and one audio stream |
| Fully decoded exported video | 284 frames |
| Fully decoded exported audio | 222 frames, 227,328 samples at 24 kHz |
| Recorded test-tone RMS | 529.57 in signed 16-bit sample units |
| Application errors | None |

Visual inspection of decoded MP4 frames confirms the blue live-demo window and
the green post-slide window, with the final slide still visible behind it.
The saved-recording screenshot confirms the editor and enabled result links.
The first video frame is black; the next frame at 0.033 seconds is nonblack,
and no other decoded frame is entirely black. This initial frame is recorded
as an observation, not omitted from the result.

This closes existing-display live recording acceptance for the corrected native
library. The test uses prepared slides and generated test tones; it does not
measure Qwen generation, microphone capture, or the deferred Realtime startup
target. The external KDE virtual-screen crash remains outside this passing path.
This verification follow-up changes documentation only: zero production or test
source lines changed.
