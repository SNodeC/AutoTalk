# Claude verdict implementation and evidence

Authority: [the final independent verdict](2026-09-27-claude-verdict.md).
The owner subsequently made that verdict authoritative and approved implementing
the plan, with direct interaction and visual verification under Xvfb. This record
does not modify the independent review or claim the entire refactor is complete.

## Decisions and completion gate

- Keep whole-deck planning in Realtime, even if the latency target is missed.
- Retain presence-only checks for generated slide images (F11); image hashes
  are an optional feature, deliberately not part of this refactor.
- Preserve native style/palette, all three modes, existing speech splitting,
  separate text/audio/play actions, and valid audio reuse.
- Replace the scope selector with Application defaults, Talk settings — title,
  and Slide settings — number. Share editors and resolution logic, keep the
  scope fixed for each dialog transaction, and retain inline slide shortcuts.
- Test Linux only. Do not claim Windows/macOS or Wayland capture verification
  from an Xvfb run.
- Require an evidence-backed disposition for every finding and all 39 placement
  groups before declaring completion. Outstanding performance and device checks
  remain outstanding, even when the regression suite passes.

## Architectural changes

The owner approved up to **250 net additional production lines** on 27 September.
The scope-selector implementation has been replaced by three fixed-scope editor
instances sharing one editor factory and the existing Project resolution authority.
Application defaults, talk settings and slide settings have separate Save/Cancel
transactions. Slide clips stay bound to the opened slide. Nested application Save
survives talk/slide Cancel; no global active-scope proxy remains.

Activity restrictions belong to the main refresh policy and dialog containers.
Settings value loading now applies only field-specific capability restrictions.
The old job-presence checks in the field loader were removed, preserving Base
voice, language-arrangement and recording-source restrictions. Redundant field
assignments in project adoption were removed in favor of the existing settings
loader. There is no completion-time settings-reload workaround.

The existing terminal-escape expression is shared by task logging and stage
parsing. Generic subprocess failures also preserve clean diagnostic tails.
Disclosure controls share a native QToolButton/arrow implementation, including
vocal attributes and AI notes. Start remains the editor's primary action.

Ctrl+C schedules the ordinary window-close path on the Qt event loop. It does
not bypass worker cancellation, project saving, recording choices or speech
cleanup. Configuration mismatches and cancellation/failure now explain speech
worker replacement or termination in the operation log.

## Findings ledger

| Finding | Current disposition | Evidence / remaining work |
| --- | --- | --- |
| F1 Disabled settings | Activity-gating fix implemented | Pointer-driven conference completion and keyboard editing, both predefined and Base voices; operation/recovery paths are covered in the completed acceptance matrix below. |
| F2 ANSI logs | Shared normalization implemented | Real failing subprocess test verifies log and error text; real vLLM loading and voice preview also produced ANSI-free visible logs. |
| F3 Saving/restart clarity | Explicit queued-recording message and prominent recording status implemented | Full pointer/keyboard sequence records, exports, queues restart, records again and exports the second session. Stalled-audio cancellation and failed-journal retry now have direct UI tests. A real Wayland recording/export also passed on repeat; the first portal attempt failed and is recorded below. |
| F4 Three settings windows | Implemented | Fixed scope, flat applicable pages, independent Save/Cancel, pinned slide, menu/inline routes and keyboard edits exercised under Xvfb. |
| F5 Save meanings | Implemented | Delivery presets and reusable voices explicitly persist immediately in the shared library. Settings Save/Cancel is scope-local; nested transaction and persistence tests pass. |
| F6 Repeated unloading | Diagnostics implemented; reported policy violation not reproduced | Real preload/preview reuse, explicit unload, operation/end/idle retention and active-generation cancellation verified. Intentional cancellation still releases the worker; logs distinguish that from a model/configuration mismatch. |
| F7 Startup | Baseline and five repeats measured; **target not met** | Warm first playback 91.36–98.81 s; planning 86.43–93.94 s. The agreed whole-deck planning remains. No speedup is claimed. |
| F8 Quick voice documentation | Corrected | Roadmap now states that Quick uses the resolved voice like the other modes. |
| F9 Ctrl+C | Implemented and verified | Real SIGINT during actual GPU synthesis: exit 0 in 0.57 s, five descendants reaped, project reloads. All three recording-close choices exercised through actual Qt buttons. |
| F10 Visual hierarchy | Implemented | Editor screenshot inspected; Start is the sole visible primary action, with Create slide audio enabled normally. Native disclosures use arrows. |
| F11 Slide-image hashes | Accepted existing policy | Explicit owner decision: no persisted hashes or migration added. Existing missing-image handling retained. |

The 39 placement groups are checked below. “Depth” counts pointer actions needed
to **expose** the relevant control from the appropriate main view; activating or
choosing a value adds an action. Scrolling is stated separately. Native submenus
show chevrons; ellipses indicate a dialog or confirmation. These are source/UI
acceptance results, not research with recruited users.

| # | Interaction / placement now | Priority / depth | Verification |
|---|---|---|---|
| 1 | PDF: welcome / toolbar, File menu | P1 / 0 | Single default destination; native dialog test |
| 2 | Saved talk: welcome / toolbar; recent submenu | P1 / 0; recent 2 | File menu pointer inspection; load/persistence suite |
| 3 | Save: toolbar; Save a copy: File | P1 / 0; P3 / 1 | Save/Cancel reload checks; native menu inspection |
| 4 | Duration and language: summary | P1 / 0 | Minimum-size visibility; keyboard edit in all modes |
| 5 | Audience / conference: Talk settings | P2 / 1, scope text may scroll | Pointer-driven conference completion, field recovery |
| 6 | Codex model/reasoning: AI & speech engine | P2 / 2 via Talk settings then page | Fixed-scope navigation; discovery and override tests |
| 7 | Sign in/out: actionable footer; Application account | P1 / 0 when needed; P3 / 2 | Signed-in/out state tests; Application-page inspection |
| 8 | Predefined voice: main voice button → Predefined | P2 / 1 | Direct pointer route and visible speaker selector |
| 9 | My voice: voice window → My voice tab | P2 / 2 | Source tab interaction; reference capability tests |
| 10 | Designed voice: voice window → Design tab | P2 / 2 | Source tab interaction; design/accept tests |
| 11 | Saved voice: voice window → Saved tab | P2/P3 / 2 | Audition without selection; explicit Use and Cancel |
| 12 | Delivery/presets: voice page; attributes disclosure | P2 / 1 + scroll; P3 / 2 + scroll | Native arrows; preset/sampling isolation tests |
| 13 | Language versions: main combo; arrangement: voice page | P1 / 0; P2 / 1 + scroll | Version creation, translation, preservation tests |
| 14 | Create talk text/audio: editor top row | P1 / 0 | Direct generation without presentation, cache reuse |
| 15 | Slide text/audio/play: below narration | P1 / 0 | Separate commands, readiness and playback state tests |
| 16 | Include / after-slide / timing: right inspector | P1/P2 / 0; timing 1 | Inline policy, selected-slide and native disclosure tests |
| 17 | Slide delivery: inspector disclosure | P2 / 1 | Native arrow interaction, scope/cache tests |
| 18 | Clips: inspector → Additional audio; background: talk recording page | P3 / 1 + scroll | Pinned-clip test; import/export and Cancel tests |
| 19 | Mode: toolbar | P1 / 0 | Keyboard selection; editor/Quick visibility tests |
| 20 | Start: toolbar primary action | P1 / 0 | Fixed captions in all modes, one editor primary action |
| 21 | Pause/Continue/Previous/Next: presenter row | P1 / 0 | Actual audio transport/fullscreen tests |
| 22 | Restart / start selected: More actions | P2/P3 / 1 | Presenter/menu inspection and transport tests |
| 23 | Live demo: presenter row | P1 / 0 | Live-demo timeline and recording continuity tests |
| 24 | Leave/continue fullscreen: Escape / presenter Continue | P1 / 0 | Real window and audio-position tests |
| 25 | Display: Application page; talk playback link | P2 / 2 | Fixed machine scope, selection Save/Cancel, route tests |
| 26 | System audio: Presentation menu / Application page | P3 / 1 to command | Native OS command placement; no competing selector |
| 27 | Recording checkbox: footer; source/mic: talk recording page | P1 / 0; P2 / 1 + scroll | Checkbox, capability and recording tests |
| 28 | Recording/saving state: prominent footer | P1 / 0 | Two recorded sessions with queued restart and real export |
| 29 | Recordings/export: File → dedicated task window | P2 / 2 to browser | Empty/recovery/saved-video and export tests |
| 30 | Automatic GPU policy: engine status → application engine | P2/P3 / 1 + scroll | Policy lifecycle and Save/Cancel tests |
| 31 | Manual GPU actions: Settings menu / engine window | P2 / 1 | Single owner, load/reuse/unload real-device probe |
| 32 | Update check: engine window | P3 / 1 + scroll | No implicit download/reload; explicit-check tests |
| 33 | Progress/stage/elapsed: footer and open dialog | P1 / 0 | Measured backend progress and visible feedback tests |
| 34 | Cancel operation: footer/open dialog | P1 / 0 | Cancellation/recovery and worker ownership tests |
| 35 | Application defaults: Settings menu | P2 / 2 to window | Separate title, applicable pages, independent persistence |
| 36 | Talk settings: main button | P1/P2 / 1 | Separate title; duration/context/voice persistence |
| 37 | Slide settings: inspector shortcuts; frequent controls inline | P1 / 0; P3 / 1 | Separate title, pinned slide, inheritance tests |
| 38 | Help/shortcuts/about: Help menu | P3 / 1 to commands | Actual native menu inspection; current shortcuts |
| 39 | View/panels/enlarge: tabs, View menu, inline enlarge | P2/P3 / 0–1 | Panel geometry, enlarge, Editor/Presenter tests |

Source correction tests retain deliberate capability restrictions and exercise
actual Qt pointer/keyboard controls. Network answers and generated speech are
controlled in deterministic workflow tests; real inference has separate evidence.
The complete suite and final theme/package verification results are recorded below.

## Final verification — 28 September 2026

- Full native Qt/Breeze Linux suite under Xvfb: **346 passed in 92.69 s**.
  Baseline before refactoring: 325 passed. No regression assertions were weakened.
- Additional native KDE **BreezeDark at 100% and 150%**, and **BreezeLight at
  150%**: **14 placement/geometry/interaction checks passed per combination**.
  Native default light at 100% is covered by the full suite. Each combination
  covers 940×680 and 1100×850 main windows, minimum/normal settings sizes,
  all three modes, all three scopes, all applicable pages and opened menus.
- Theme checks load the installed KDE scheme through an isolated `kdeglobals`
  and the native KDE platform plugin. An earlier palette-only harness did not
  refresh the native menubar's class palette; it was corrected, not used as
  final dark-theme evidence. User desktop settings were not changed.
- Rebuilt `dist/autotalk/autotalk` using the installed matching Qt/Breeze.
  All staged Python source files match the workspace. Audit confirmed **27**
  native Qt libraries/plugins, **18** runtime-mapped Qt libraries from the bundle,
  and Breeze loaded. The PDF library uses the matching PySide wheel, as before.
- Actual packaged executable, Xvfb/XTest input: opened **Application defaults**,
  **Talk settings — AutoTalk acceptance**, and **Slide settings — 1**, returned
  through Escape, exited successfully on SIGINT, and reloaded its saved talk.
  The former bundle is retained locally in `artifacts/verdict-refactor/previous-bundle`.
- Logs, failed harness attempts, real-deck content and videos remain local in
  ignored `artifacts/verdict-refactor/`. Only synthetic screenshots are published.

Two external executable/SIGINT probe launchers supplied a relative configuration
path, which Qt ignored, temporarily adding disposable talks to the user's recent
list. All ten original entries were restored from the pre-test record; every
other preference byte was verified unchanged. Those launchers now use absolute
paths. Original talk files were not changed. The startup-measurement and theme
harnesses used isolated preferences throughout.

The real stereo regression initially found silence. Inspection established that
the newly created disposable sink was **muted by session policy** even though
the application stream targeted that sink at 100% volume. The fixture now
initializes only its own virtual sink. The audible-signal and equal-left/right
assertions are unchanged; the user's physical output was not unmuted or changed.

The fixed-scope implementation also caught and corrected navigation feedback:
selecting Voice & language in the left list now reveals the audition controls
through the same main refresh authority. Mode changes in settings update the
main window from the resolved project setting. Clip editing remains bound to
the dialog's slide even if the transport selection changes.

### Published visual evidence

- [Editor and its one primary action](evidence/2026-09-27-refactor-editor.png)
- [Settings after conference completion](evidence/2026-09-28-settings-recovered.png)
- [Native disclosure](evidence/2026-09-27-refactor-disclosure.png)
- [Application defaults](evidence/2026-09-28-application-defaults.png)
- [Talk settings](evidence/2026-09-28-talk-settings.png)
- [Slide settings](evidence/2026-09-28-slide-settings.png)
- [Native BreezeDark, 150%, minimum window](evidence/2026-09-28-dark-editor-150.png)

Full UI tests save screenshots when `AUTOTALK_EVIDENCE_DIR` is set. Example:

```sh
PYTHONPATH="$PWD/artifacts/ux-placement/package-source/build/system-qt:$PWD/src" \
LD_LIBRARY_PATH="$PWD/artifacts/ux-placement/package-source/build/system-qt/PySide6/Qt/lib" \
QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/pytest -q
```

## Real Realtime measurements

An isolated copy of the user's **24-slide, 30-minute** talk was used. Its narration
was cleared, recording disabled, Realtime set to whole-deck planning with
write-ahead, account-default Codex model and **low** reasoning retained. Voice:
Qwen3-TTS 1.7B CustomVoice/Ryan on the RTX 2000 Ada laptop GPU. Preferences and the
original talk were not modified. The model was loaded before Start; download and
loading are excluded from the warm-start measurement.

Timing ends with a presentation window and over 0.1 s consumed by Qt's audio sink.
This verifies delivery to the audio output, **not a microphone measurement of
physical audible sound**. The initial baseline was **99.44 s**, of which
**94.48 s** was Codex planning. The five successful repeats are:

| Attempt | Model loading, excluded | Codex planning | First audio | Slide + consumed audio |
|---|---:|---:|---:|---:|
| 1 | 38.57 s | 86.43 s | 89.58 s | 91.36 s |
| 2 | 38.27 s | 87.11 s | 90.14 s | 91.99 s |
| 4 | 38.54 s | 88.98 s | 92.08 s | 93.91 s |
| 5 | 38.42 s | 89.47 s | 92.55 s | 94.41 s |
| 6 | 38.46 s | 93.94 s | 96.93 s | 98.81 s |

Median warm start: **93.91 s**. Each successful run kept the same worker PID from
preload to playback. No speedup is inferred from this small sample. The **15–20 s
requirement remains unmet**. Complete-deck planning is retained by explicit owner
decision; no opening-only prompt, model downgrade, cache shortcut, altered speech
splitting or invented progress was introduced.

Attempt 3 crashed before measurement, during audio-device initialization. The
saved core trace places the fault in the system PipeWire native-protocol library,
with Qt Multimedia initializing its audio context. It contains no Python frame at
the fault. This establishes the location, **not the root cause**. Later starts and
the full suite passed; the intermittent crash remains an open reliability finding.

## Real GPU and recording checks

One matching worker survived real preload and preview generation under session
retention. A real preview under presentation retention also kept it loaded;
presentation-end release then removed it. Operation retention kept explicit
preload, then unloaded after generation. The **actual** five-minute idle timer
released the worker after **305.34 s including teardown**; no accelerated timer
was used for this real check. Explicit unload was verified separately. GPU use
returned to the 40 MiB desktop baseline. The owner's original unconditional-unload
sequence was not reproduced; no unsupported retention-policy change was made.

A real SIGINT during Qwen generation exited AutoTalk with code 0 in **0.57 s**.
All **five** captured worker descendants were gone and the project reloaded.
The deterministic suite additionally covers cancellation, deferred release,
policy changes during work, fullscreen/pause and export boundaries.

Screen recording's audio connection now uses worker-owned, nonblocking libpulse
polling. Cancellation reaches connection setup and reading; cleanup runs on the
owning worker. The real monitor-read probe stopped in under 1 ms. A controlled
stalled source plus real video encoder verifies End joins both workers and restores
editing. A real journal-write failure verifies recording ownership is retained,
End stays available, closing is refused safely, and retry exports the video.
Finalization's pending journal update can be retried after the PCM files close.
No forced control unlock or abandoned capture worker was introduced.

The first real Wayland check failed with Qt's “Failed to open pipewire remote
file descriptor”. A subsequent Qt-only check received ten frames, and AutoTalk's
repeated capture/export succeeded: **6.24 s**, **188 decoded video frames**, one
stereo audio stream and no reported errors. Maximum sampled UI tick interval was
**0.205 s**. This check used the real portal, ScreenCapture and exporter; it does
not establish that the transient initialization error cannot recur. Local video
is retained outside git. Recording-close tests cover Cancel, save later and finish
saving; two consecutive recordings with a queued restart both export successfully.

## Accounting and remaining limitations

Against the pre-refactor commit `430c579`:

| Area | Added | Removed | Net |
|---|---:|---:|---:|
| Production Python | 790 | 656 | **+134** |
| Tests | 776 | 319 | **+457** |

Production growth remains within the approved +250-line limit. Fixed-scope
transactions replace the shared scope selector and move the existing voice
operations out of MainWindow; there is one shared editor implementation.
Cancellable recording-device setup/read requires the asynchronous libpulse API
in place of the uninterruptible simple API. This accounts for additional lifecycle
code without introducing a second capture or settings authority.

The required source refactor and its Linux interaction checks are implemented.
The broader acceptance gate remains open for the **15–20 s startup target** and
the **intermittent native PipeWire initialization crash**. A repeat successful
capture does not explain its earlier transient error. These are recorded limits,
not completed fixes. Windows/macOS execution and QEMU remain untested/deferred.
