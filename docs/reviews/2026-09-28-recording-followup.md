# Recording acceptance and startup follow-up

Continuation of the [second-review refinement](2026-09-28-refinement.md), starting
at `cf00820`. Linux only; platform scope and deferred QEMU work are unchanged.
The source change belongs to the existing recording owner, not a UI redesign.

## Recording defect reproduced during acceptance

The initial Xvfb screen-recording journey produced a decodable MP4 with both
streams, but a stronger check exposed truncation: **8.966 seconds** of captured
screen became **3.800 seconds** of exported video. A separate probe using Qt's
normal event loop also reproduced audio falling behind: **9.233 seconds** of
screen versus **5.802 seconds** of committed audio. The bare audio reader, without
screen capture alongside it, read **8.760 seconds** during a nine-second run.
The original stream-existence check alone was insufficient acceptance evidence.

**Invariant:** the recording source must drain ready audio without inserting an
idle delay; ending capture must retain audio already available in the connection.
Packet placement must use the timestamp of its first sample. Export cannot
recover samples discarded upstream.

The source loop slept before every PulseAudio event-loop iteration. While screen
capture ran, it consumed 20 ms packets more slowly than they arrived; measured
backlog grew beyond three seconds. The existing event API reports how many
sources it dispatched, so the fix waits only when there was no work. Shutdown
now consumes already-available audio without waiting for new audio, then closes
the same connection. Cancellation before stream creation still returns safely.
No new timer, queue, worker, ownership flag or replacement backend was added.

A second timing error subtracted the packet length from a latency that already
locates the first unread sample. The subtraction is removed. This interpretation
is grounded in the installed PulseAudio headers and its [latency/read-index
implementation](https://github.com/pulseaudio/pulseaudio/blob/master/src/pulse/stream.c).
Both positive and negative monitor latency are covered. The export implementation
is unchanged: no silence padding or duration override hides lost recording data.

Three initial regressions failed before the source corrections. A fourth case
then reproduced loss of queued packets at shutdown. All four now pass, alongside
the existing stalled-device, cancellation, recording-recovery and export tests.

## Direct recording acceptance

The final journey used native Qt 6.10.2/Breeze under Xvfb and real PipeWire audio,
with a disposable virtual sink and its monitor. Test-only device selection routed
both playback and recording to that sink. It did not change the physical speaker's
mute, volume or default output. The application's source, timing, capture and
export implementations ran normally. This proves the X11 capture path; it is not
Wayland permission evidence.

Actual mouse/keyboard interaction exercised Start, leaving fullscreen, live-demo
pause, Continue, slides finishing while recording remained active, and End
presentation and save video. Two distinct test tones exercised audio capture.
The exported MP4 was decoded and its visible demo/final segments inspected.

| Measurement | Result |
| --- | ---: |
| Capture wall time | 9.688 s |
| Captured screen track | 9.666 s |
| Exported MP4 | 9.567 s |
| Screen/export difference | 0.099 s |
| Captured stereo audio RMS, PCM16 | 516.48 |
| Streams | One video, one audio |
| Saved video/folder links | Enabled |
| Application errors | None |

This is measured agreement within 0.2 seconds in this short journey, not a claim
of sample-perfect synchronization or long-duration drift verification.

Synthetic evidence from the actual exported video and application:

- [Live demonstration included](evidence/2026-09-28-recording/demo.png).
- [Post-slide segment included](evidence/2026-09-28-recording/final.png).
- [Saved recording links and recovered editor](evidence/2026-09-28-recording/saved-recording.png).

## Startup experiment: rejected

A four-request ABBA experiment compared current input serialization with removing
only JSON whitespace from the input. All values, images, schema, selected model
and reasoning were preserved. Every result passed full-deck validation.

| Order | Input | Request time | First response text |
| --- | --- | ---: | ---: |
| 1 | Current | 46.253 s | 17.814 s |
| 2 | Compact input | 40.634 s | 11.964 s |
| 3 | Compact input | 50.132 s | 20.950 s |
| 4 | Current | 45.396 s | 16.762 s |

Medians were **45.824 versus 45.383 seconds**. The last current request reported
4224 cached input tokens; the others reported none. This small, variable result
does not establish a worthwhile latency improvement, so the candidate was not
promoted. The earlier production output-format improvement remains; its measured
49.13-second warm end-to-end median is not replaced by these request-only numbers.
**The 15–20-second startup target remains open.**

## Verification boundaries and discarded attempts

- The fresh Wayland attempt again timed out without Share confirmation. Qt also
  reported that capture failed, possibly because sharing was cancelled, and a
  temporary absence of outputs. The user action/cause was not observed. No
  successful Wayland capture or new portal diagnosis is claimed.
- An initial Xvfb attempt inherited the host's Wayland session type, making Qt
  choose the portal. It was stopped; the corrected X11 run explicitly selected
  the isolated X11 session.
- Larger audio packets, changing ctypes call behavior, draining buffered reads
  alone and removing per-packet file flushes were investigated outside production.
  None was adopted. Two diagnostic-script errors (ctypes type and indentation)
  were corrected before using their results. These are probe errors, not product
  failures.
- A pre-drain run failed the duration check by 0.333 seconds. The later drained
  run passed duration and audio checks but its screenshot helper lacked Pillow;
  the final run uses Qt to save evidence and passes the entire journey.
- A private vanilla PulseAudio server was also tried for silent testing. One native
  regression missed its prepared-playback-before-model-readiness timing assertion,
  and the recording probe did not observe its audio counter advance in the final
  second. The standard suite passed with one PipeWire-only skip. These runs are
  not accepted as native PipeWire verification; no tests were weakened. Final
  verification uses the actual PipeWire backend with a virtual output only.

Raw logs, traces and test recordings remain in ignored `artifacts/refinement-3/`.

## Final regression and package verification

- Standard Qt 6.11.2: **369 passed in 76.83 seconds**, no skips.
- Native Qt 6.10.2/Breeze: **369 passed in 96.52 seconds**, no skips.
- Both final suites used the actual PipeWire backend and a disposable virtual
  output. Test-only selection redirected monitor capture to that output. The
  virtual output was removed after the tests; physical output settings were not
  changed. The temporary private PulseAudio server was also stopped.
- Native packaged executable: actual pointer/keyboard interaction opened all
  three settings windows, returned to the editor, reloaded the saved manifest
  and exited cleanly on SIGINT. The library audit verified 27 copied Qt/plugin
  files, all 18 mapped Qt libraries inside the bundle, Breeze loaded, exit zero.
- Python application packaging was rebuilt against the previously verified,
  unchanged native Qt/Multimedia binaries. No native dependency or patch changed.
  Production sources in the build staging tree match the committed sources.
  The local launcher bundle is replaced by directory rename, preserving the
  previous bundle's files for any already-running process. Restart AutoTalk to
  use the new version.

Compared with `cf00820`: **17 production additions, 7 deletions, net +10 lines**;
**65 test additions, no deletions**. Cumulative verdict-refinement growth is now
**+240 of the approved +250 production-line allowance**. Growth handles readiness
and shutdown at the existing source boundary. No second implementation or owner
was introduced. The original Claude verdict remains unchanged.
