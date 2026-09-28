# Wayland capture: routing isolation and lifecycle diagnostics

Scope: diagnose capture initialization separately from teardown, without changing
production code or physical audio settings. Native Qt 6.10.2 with the existing
AutoTalk patches, real Plasma/Wayland, existing laptop display eDP-1. The user
approved sharing through Plasma for each attempt. No virtual display was requested.

## Findings

The original assumption that failure necessarily belonged to Plasma or Qt was
premature. Both the earlier acceptance harness and AutoTalk's production playback
constructor set process-wide PipeWire routing properties. These reach video
streams as well as audio streams.

The governing invariant is that audio destination policy must affect audio only;
a video stream must retain the source selected through the portal. An unrelated
playback constructor must not rewrite routing policy for all capture clients.

`src/autotalk/playback.py:37` sets `node.target = null` in `PIPEWIRE_PROPS`.
The earlier harness additionally set `target.object` to its disposable audio sink.
The isolated comparison captured a video node with that audio sink as its target.
With AutoTalk's normal properties, the video node had no target and remained
suspended. This is a production configuration problem as well as a test problem.

PipeWire's stream implementation first writes the supplied target ID to
`node.target`, then applies `PIPEWIRE_PROPS` to the stream properties. The order
explains why the global override can erase the portal-selected destination.
See [upstream stream.c](https://github.com/PipeWire/pipewire/blob/master/src/pipewire/stream.c),
`pw_stream_connect`: target-ID assignment and the later environment-property update.
The locally inspected Qt helper passes the portal's selected node ID to this call.

Removing routing overrides did not make all subsequent tests pass. The actual
AutoTalk recorder also reproduced an initialization failure without them. Routing
is therefore not a sufficient explanation of every observed failure.

## Experiments and evidence boundaries

Raw logs, diagnostic scripts, private screen image and PipeWire node snapshots are
retained locally under `artifacts/wayland-isolation/`; desktop images are not
committed. The native library was unchanged throughout.

| Run | Configuration | Initialization / frames | Cleanup |
| --- | --- | --- | --- |
| `.` | Minimal QScreenCapture; routing overrides unset; no audio objects | Portal accepted; 44 frames at 1920 x 1200 over approximately five seconds | Explicit stop, detach, native capture/session/sink deletion; exit 0 |
| `routed` | Same minimal probe, old harness PIPEWIRE_PROPS, disposable audio sink | Remote opened successfully; zero frames; video target.object named the audio sink; stream suspended | Closed only the diagnostic window through KWin; normal interpreter shutdown, exit 0 |
| `recording` | Actual ScreenCapture class; AutoTalk's normal PIPEWIRE_PROPS; silent monitor selected explicitly in test-only PulseInput wrapper | Remote opened; zero frames; video target missing; stream suspended | Interrupt/terminate signals did not stop the process (signal mask blocked them); terminated with SIGKILL; no claim of graceful cleanup |
| `recording-clean` | Actual class, routing overrides unset | Initialization failed after nine stream creations/destructions | Capture close returned, process exit 1; no segmentation fault. Inconclusive comparison because the preceding stalled process was still alive |
| `recording-clean-solo` | Actual class, overrides unset; preceding stalled process removed before sharing | Initialization failed after 17 stream creations/destructions; no recording became ready | Capture close returned, process exit 1; no segmentation fault |

The first successful run's 17.448-second first-frame timestamp includes the human
sharing decision; it is not a measured application startup latency. Its frame was
visually inspected and showed the shared laptop desktop. This proves native
screen-frame acquisition and normal teardown, not completed AutoTalk video export.

All actual-recorder tests disabled microphone capture and created no playback
sink. Only a disposable null sink's monitor was selected for the recorder's audio
worker. The failed runs never reached audio-worker startup. No physical volume,
default device or mute setting was changed. Speaker and microphone both reported
`Mute: yes` before and after testing. All diagnostic processes and disposable
sink nodes were removed afterward.

## Initialization and destruction are distinct

The routing comparison opened the PipeWire remote successfully but delivered no
frames: connection success alone is not recording readiness.

The clean recorder failures instead returned false from the Qt helper's open
operation. Logs show repeated stream destruction/recreation at approximately
one-second intervals before the generic descriptor error. This is not evidence
of a denied sharing request or an invalid OS descriptor.

Source inspection identifies an additional concern in Qt 6.10.2:
`onRegistryEventGlobal` discards the registry node ID, accepts every Video/Source
or Stream/Output/Video announcement, resets its core synchronization sequence,
and recreates the capture stream. It does not restrict recreation to the
portal-selected node. `destroyStream(true)` can wait for a second within this
callback, whereas `open()` waits for initialization using a two-second timed
wait. This provides a concrete candidate for the observed churn and incomplete
initialization. The exact announcement IDs were not instrumented in these runs;
the causal sequence remains to be proven before changing the native code.

The earlier SIGSEGV remains a separate unresolved failed-initialization teardown
case. The minimal successful run proves normal stop/destruction can work, and
these two clean recorder failures exited without that crash. Neither result
invalidates the saved earlier core or proves all failure teardown is safe.

## Narrow repair direction and remaining verification

1. Remove process-global audio routing policy from video's path. Preserve Plasma
   audio destination selection through the existing audio owner; simply deleting
   the override without checking audio routing could regress that requirement.
2. Trace the selected node and registry callbacks during failed initialization;
   correct stream ownership/selection at the native capture source if confirmed.
3. Recheck failure teardown against the earlier core's surviving stream state.
4. Run complete AutoTalk presentation, pause/live-demo, End and video export with
   correctly isolated audio. That acceptance test remains outstanding.

No production changes and no tracked automated-test changes were made by this
investigation. Temporary diagnostic probes are not application code. The existing
production-growth allowance is unchanged. No system libraries or services were
replaced or restarted.

## Continuation: narrow correction and successful full recording

Further experiments established that the complete global override need not be
removed. With no override at all, moving a native Qt audio stream between two
explicitly selected disposable outputs failed with `Invalid argument`.
Retaining `node.dont-reconnect = false`, while preserving `node.target`, allowed
the same system routing operation to succeed. Both virtual monitors contained
the tone (RMS approximately 323 and 353). Thus the narrow repair removes only
`node.target = null` from Playback's existing configuration. Stream targets are
no longer erased; no new backend, routing owner, state, flag or compatibility path
was added. This supersedes the broader proposed repair direction above.

A diagnostic Qt build logged registry node IDs and initialization completion.
The successful run saw only the selected video source, completed both core sync
callbacks, recorded screen frames and explicitly deleted capture objects cleanly.
The later image-export step of that diagnostic failed because Pillow was absent;
it is not counted as a passing test. The already saved screen track was decoded
separately (15 frames, 5.533 seconds). A debugger-only attempt before it could not
read optimized arguments and also is not counted as a passing run.

Two complete real Wayland acceptance journeys then passed:

| Run | Capture wall time | Screen track | Final MP4 | Audio RMS |
| --- | ---: | ---: | ---: | ---: |
| Diagnostic library, logging only | 9.563 s | 9.600 s | 9.400 s | 534.95 |
| Original release library, logging removed | 9.770 s | 9.666 s | 9.600 s | 524.01 |

Both used the real MainWindow/Playback/ScreenCapture/export path, synthetic
prepared narration, two slides, pointer/keyboard interaction, a two-second live
demo pause, resume, continued capture after slides finished, and End/export.
The MP4s have one video and one audio stream; exported-session metadata and the
Open video/Open folder controls were verified. Saved frames were visually
inspected: the blue live-demo window and green post-slide window are present.
The initial frame can contain the sharing chooser while it is closing; that
brief desktop transition is faithfully captured. The narration source was a test
tone, not Qwen synthesis, and this does not measure Realtime preparation speed.

The corrected acceptance harness selects a virtual QAudioDevice explicitly and
records only that virtual sink's monitor. It does not set a global video target.
The native library's original SHA256 was restored and checked against a clean
rebuild: `ba828bd659ea20f75f53567934d0e63600fa6294dd68f797f44eee76e9ea0360`.
No diagnostic logging or native-code change is part of this correction.
Artifacts: `artifacts/wayland-verify/` and `artifacts/wayland-verified-release/`.

These successes verify the existing-display recording journey. They do not prove
that the earlier intermittent native initialization/cleanup crash is repaired.
The failed runs' repeated registry-driven recreation remains an investigation
item, and the KDE virtual-screen crash is separate. No unproven native patch was
introduced to suppress either symptom.

Production diff: **3 lines added, 3 removed, net zero**, including two comment
lines; one configuration line changes. Tracked automated-test code: **no change**.
The approved production-growth allowance remains 247/250.

Final regression verification: standard Qt 6.11.2 **372 passed in 77.54 s**;
native Qt 6.10.2/Breeze **372 passed in 94.30 s**, no skips. Both ran on Xvfb
with explicit virtual playback-device selection. The native package was rebuilt;
its audit verified 27 Qt/plugin hashes, 18 mapped Qt libraries within the bundle,
Breeze loaded and smoke exit 0. Direct packaged-executable interaction opened
application/talk/slide settings, reloaded the saved manifest and exited on SIGINT.

A later physical-device readback showed the speaker unmuted and microphone
muted. The diagnostic/suite commands changed mute/volume only for explicitly
named disposable virtual sinks; the physical state was left as observed. No
claim is made that the speaker remained muted throughout this later continuation.
