# Startup and native audio follow-up

This continues the [Claude-verdict implementation](2026-09-27-verdict-implementation.md)
from commit `26323f0`. Linux only was tested. Whole-deck planning, selected Codex
model/reasoning, native styling, speech splitting and validated audio reuse remain.

## Realtime startup: improved, target still open

A protocol trace of the existing 24-slide, 30-minute test talk located the delay:
app-server/account setup took under one second, the first response text arrived
at 15.0 seconds, and the complete result arrived at 86.4 seconds. The response
contained 937 words of later-slide outlines and 1,467 characters of notes.
It used 46,584 input tokens and 2,663 output tokens, including 276 reasoning tokens.
The requested model was `gpt-6-astra`, reasoning `low`; no reroute was observed.

The existing request now explicitly asks for one concise outline sentence for
each later slide, retaining its key point, narrative connection and time budget.
Only the opening slide receives final spoken narration in this planning call,
as before. Specific uncertainty notes remain; repeated caveats are discouraged.
The complete result still passes the existing schema/content validation before
any narration is adopted. There is no partial-JSON playback, reduced deck input,
model substitution, additional cache or new preparation pipeline.

Three request-only trials completed in 57.3, 58.1 and 57.8 seconds. An inspected
trial contained 318 outline words; all 24 slides and the same 1,786.2-second
spoken-time allocation remained (the rest of the target is transition pauses).
Source-topic review found the later-slide outline sequence intact. This is a
bounded review of one deck, not proof that every generated talk is equivalent.

The final application was then measured on isolated copies of the same talk,
with the GPU model loaded before Start:

| Run | Model load, excluded | Complete planning | First audio | Slide + consumed audio |
|---|---:|---:|---:|---:|
| 1 | 37.46 s | 56.79 s | 59.77 s | 61.68 s |
| 2 | 38.38 s | 57.49 s | 60.37 s | 62.25 s |
| 3 | 37.71 s | 56.28 s | 59.28 s | 61.12 s |

The median is **61.68 seconds**, versus **93.91 seconds** in the earlier five-run
baseline: about **34% lower in this sample**. Each run retained the same speech
worker PID from preload through playback. The endpoint is a visible presentation
plus audio consumed by Qt, not a microphone measurement of physical speakers.
Original talk files and preferences were not modified by these measurements.

**The 15–20-second target remains unmet.** Most remaining time is the complete
Codex response. The accepted whole-deck requirement has not been weakened to
claim the target. Larger speed claims need further evidence and any changes to
model selection or planning quality require an explicit product decision.

## Actual Codex progress

The existing progress display now starts each request with “Codex: awaiting
response”, then shows the actual number of response characters received.
The total is explicitly unknown; there is no estimated percentage or time-based
fill. Counts reset for each turn and ignore events from other threads/turns.
Only complete structured results are used by the application.

This uses the existing app-server response-delta events and the existing progress
renderer; no polling timer, second job state or parallel progress authority was
introduced. See [OpenAI's app-server event documentation](https://developers.openai.com/codex/app-server/)
and the [captured native UI](evidence/2026-09-28-codex-response-progress.png).

## PipeWire initialization crash: reproduced and corrected upstream

The standalone [Qt-only reproducer](../../tests/probes/qt_audio_startup.py) imports
no AutoTalk code. It creates an application, connects `audioOutputsChanged` and
queries the default device. The original native Qt 6.10.2 library crashed once
in 100 fresh processes. Its core trace matches the earlier AutoTalk crash at
`libpipewire-module-protocol-native.so + 0x17fb2`, followed by `+0x13166` and
`+0x138d8`. The additional Python faulthandler frames are signal reporting.

Qt's `CoreEventListener` destructor removed its hook without the PipeWire
event-loop lock. Callback dispatch and removal must share that lock to prevent
access after destruction. Upstream
[`1c6fb56a9686`](https://github.com/qt/qtmultimedia/commit/1c6fb56a9686ad012b35ecbee9a67cc6686b6099)
fixes that responsibility in Qt itself.

- Standard builds now use Qt/PySide6 **6.11.2**, whose tagged source contains the
  fix. Windows/macOS already used this version.
- The native build retains this machine's **Qt 6.10.2 and Breeze**. Its existing
  build path automatically builds Qt Multimedia with the exact upstream patch,
  using checksum-pinned source and matching system Qt headers. It replaces the
  affected library before collection; a failed patch/build aborts packaging.
- No audio-backend switch, preload delay, Python exception workaround, system
  package replacement or forced process restart was introduced.
- The source archive, patch and build recipe accompany the native bundle. Build
  prerequisites are documented in the README; end users just launch AutoTalk.

The corrected native library passed **200/200** fresh-process probes. Standard
Qt 6.11.2 passed **100/100**. This is strong evidence for the reproduced lifetime
fault; it is not a guarantee against every possible native audio/portal failure.

## Verification and accounting

- Final complete suite, native Qt/Breeze with patched Multimedia: **349 passed
  in 91.42 s** under Xvfb; no skips or weakened behavioral assertions.
- Final complete suite, standard Qt/PySide6 6.11.2: **349 passed in 73.70 s**
  under Xvfb; no skips.
- Packaging tests preserve version-match rejection and Qt/PDF/style collection
  checks; they additionally verify patched-library collection and fail-closed
  behavior when the dependency patch fails.
- A scripted app-server subprocess drives the actual Qt operation display,
  verifies measured character counts, ignores unrelated events and checks reset
  between turns. Synthetic screenshots were visually inspected.
- Both native and standard Linux packages rebuilt and passed launch smoke tests.
  The native bundle's **27** Qt libraries/plugins were audited, with **18** Qt
  libraries observed mapped from the bundle and Breeze loaded. The Multimedia
  hash matches the rebuilt, patched library; other native modules retain their
  original sources. Actual packaged keyboard/mouse checks opened all three
  settings windows and returned to the editor; SIGINT exited cleanly. The tested
  native bundle was installed via directory replacement, retaining old binary
  inodes for the user’s running application. A post-install library audit passed;
  restart AutoTalk to load the new bundle.
- The fresh Wayland capture/export recheck timed out after 300 seconds without
  capture becoming ready; no Share confirmation was received. No runtime capture
  error was reported before that timeout. It remains **unverified**, requiring
  another supervised run with Plasma sharing permission. This is not evidence
  of a successful recording or a diagnosis of a new portal defect.

One first Wayland probe was invalidated when a concurrent packaging build
rewrote libraries in its staging directory. Its crash timestamp matches that
rewrite; it is discarded as product evidence. The repeat uses a separate,
unchanged library set. Subsequent builds and runtime probes use separate paths.
The user's running application and system-installed libraries were not changed
by that test setup error.

Relative to `26323f0`, production Python adds 37 lines and removes 1 (**net +36**).
The upstream dependency patch is 19 repository lines, containing a two-line C++
addition. Conservatively counting the entire patch gives **+55 production/build
lines**, or **+189 cumulative** with the earlier refactor, within the approved
+250 limit. Tests/probes add 89 and remove 8 (**net +81**). The dependency manifest
changes its version pin without net line growth.

The added build code is necessary to correct the native dependency at its source
while retaining matching Qt/Breeze libraries. The response counter reuses the
existing event renderer. No second settings, playback or speech owner was added.
Detailed logs, protocol traces, core information, repeated timing JSON and private
videos remain in ignored `artifacts/open-tasks/`; only synthetic UI evidence is
published.

The remaining startup target stays open. The earlier transient Wayland portal
initialization failure must not be conflated with the reproduced audio-device
lifetime crash. Windows/macOS execution and QEMU remain deferred.
