# AutoTalk refinement plan and implementation status

This plan replaces the previous implementation sequence while retaining the
complete agreed product scope below. Implementation targets 0.3. Testing for
this refinement pass is **Linux only**; Windows/macOS support is retained.
See [behavior](../README.md) and [measured verification](VERIFICATION.md).

## Refinement following the second Claude review — 28 September 2026

The [second verdict](reviews/2026-09-28-claude-verdict.md) is recorded with its
[method and evidence](reviews/2026-09-28-claude-review-method.md). The owner
approved refinement of labels/clipping, model retention, measured startup and
audio-resource ownership, followed by Linux interaction/recording acceptance.
See the [current refinement ledger](reviews/2026-09-28-refinement.md) for changes,
measurements and outstanding checks. This sequence preserves all product and
platform requirements below; it does not restart the UI architecture.

Current dispositions: F12/F13 label/readability fixes are implemented; F6 has a
reproduced and corrected narration-interruption unload path, without claiming
that every historical unloading report has the same cause; F14 adds deterministic
resource cleanup. F7's 15–20-second warm Realtime target remains open. F15 was
retracted by Claude and requires no change. The original reports below retain
historical observations; their old status text is explicitly labeled as such.

The [recording follow-up](reviews/2026-09-28-recording-followup.md) reproduces and
corrects audio-reader throttling and shutdown loss found during acceptance.
A real X11/PipeWire journey with a silent virtual output verifies live-demo and
post-slide footage in the saved video. The later Wayland acceptance is recorded below;
further input compaction did not demonstrate a startup gain and was rejected.

**Current priority (owner decision, 28 September):** defer further startup
optimization and focus on supervised native Wayland recording acceptance.
The 15–20-second target remains open, not waived. Verify permission, live-demo
capture, continued recording after the slides finish, and the complete saved
video. Use a silent virtual audio output; leave physical audio settings untouched.
The [native Wayland attempt](reviews/2026-09-28-wayland-verification.md) now
identifies a KDE sharing-service crash and missing failure propagation in Qt's
portal-response handler. Those initial failures replaced the earlier assumption
that the check was only awaiting permission.
The [failure-recovery fix](reviews/2026-09-28-wayland-failure-fix.md) now reports
failed/cancelled portal requests in the native Qt 6.10.2 bundle, closes failed
capture once and restores editing/retry. The subsequent
[routing isolation and correction](reviews/2026-09-28-wayland-routing-isolation.md)
removed a global override that erased the portal-selected video target while
preserving system audio-output switching. Two full existing-display Wayland
recordings now pass, including live-demo and post-slide footage, audio and MP4
export; one uses the unchanged release Qt library. KDE's virtual-display crash
remains open. The subsequent
[native lifecycle correction](reviews/2026-09-28-wayland-lifecycle.md) reproduces
and fixes initialization with multiple advertised sources and an early-failure
cleanup crash. It also stops callback dispatch before stream destruction; the
historical destructor crash itself has not been reproduced deterministically.

## Independent Claude review — 27 September 2026

At the owner's request, Claude CLI reviewed source snapshot `8d06f96` on
`review/claude-ui-ux-2026-09-27`. The [verbatim verdict](reviews/2026-09-27-claude-verdict.md)
contains code-quality, UI/UX placement, startup timing, overall assessment and
button-convention findings. See the [review brief](reviews/2026-09-27-claude-review-brief.md)
and [provenance/evidence](reviews/2026-09-27-claude-review-method.md) for scope,
verification, factual follow-ups and limitations. The owner subsequently made
the verdict authoritative and approved the implementation plan. See the
[implementation and evidence ledger](reviews/2026-09-27-verdict-implementation.md)
for actual progress and remaining checks; the overall refactor is not complete.
The recorded reports below preserve their original context. **28 September update:**
the fixed-scope settings refactor, state recovery, save semantics, ANSI cleanup,
recording shutdown/retry, button disclosures and Ctrl+C handling are implemented.
Linux verification: 346 tests, native theme/scaling interaction, real GPU policies,
real generation interrupted by SIGINT, and a repeated real Wayland capture/export.
The [startup/audio follow-up](reviews/2026-09-28-startup-and-audio.md) subsequently
reproduced the native PipeWire crash in a Qt-only process and applied Qt's upstream
lifetime fix. Both Linux Qt variants pass 349 tests. Concise whole-deck outlines
reduced three warm starts to 61.12–62.25 s; the 15–20-second target remains open.
See the ledger for the 39-group placement matrix and precise evidence boundaries.

## Recorded issue — Ctrl+C does not stop AutoTalk

- **Status when recorded:** open; recorded only, not investigated or fixed.
- **Reported:** 27 September 2026, Linux.
- **Observed:** pressing Ctrl+C does not stop the application.
- **Expected:** when launched from a terminal, Ctrl+C should request a clean
  shutdown, including cleanup of active speech, playback and recording resources.
- **Follow-up:** confirm the launch context and reproduce before diagnosing
  interrupt handling. No cause has been established.

## Recorded issue — settings unavailable after conference preparation

- **Status when recorded:** open; recorded only, no application changes made.
- **Reported:** 27 September 2026, Linux, with a screenshot.
- **Observed:** after opening a PDF and reading/preparing the conference website
  with Codex, some settings remain unavailable. In **Talk & preparation → This
  talk**, the screenshot shows **Allowed timing difference** and **Preparation
  mode** disabled while other talk fields remain editable.
- **Expected:** applicable configuration controls should be editable when the
  operation has finished and no presentation or recording is active.
- **Follow-up:** reproduce the completed-operation state and check availability
  across settings pages. Distinguish configuration controls from actions with
  prerequisites; the screenshot also shows **Fit duration…** disabled, whose
  narration prerequisite needs checking separately. Root cause is unconfirmed.

## Recorded issue — delivery-preset UX is not meaningful

- **Status when recorded:** open; recorded only, no application changes made.
- **Reported:** 27 September 2026, with a screenshot of **Voice & language →
  This talk → Writing & delivery**.
- **User finding:** saving delivery presets is meaningless in the current UX.
  The screenshot shows an empty **Saved delivery presets** selector, **Save
  preset…**, disabled **Use preset**, and a separate **Save reusable voice…**
  action on the same page.
- **Follow-up:** reconsider the purpose, grouping and save/use flow of delivery
  presets, including their distinction from reusable voices and the dialog's
  **Save** action. Clarify what is saved, where it applies and how it is reused.
  No redesign or removal decision has been made.

## Recorded issue — raw ANSI color codes in Operation details

- **Status when recorded:** open; recorded only, no application changes made.
- **Reported:** 27 September 2026, Linux, with a screenshot during Realtime
  speech-model loading.
- **Observed:** **Operation details** displays terminal escape/color sequences
  such as `[0;36m` and `[0;0m` alongside speech-engine log messages, making the
  output harder to read.
- **Expected:** readable log text without exposed terminal formatting codes.
- **Follow-up:** trace subprocess output into the details widget and handle
  terminal formatting at the appropriate boundary. No fix has been selected.

## Recorded issue — stopping leaves the interface disabled

- **Status when recorded:** open; blocks returning to editing and starting over. No application
  changes made.
- **Reported:** 27 September 2026. The user stopped the whole presentation process
  intending to start again, but reports that the whole UI remained disabled.
- **Expected:** stopping must visibly complete and restore applicable editing and
  start controls. Any necessary cancellation or recording finalization must be
  clearly identified while it runs; the interface must recover when it finishes.
- **Initial code inspection:** main-window editability depends on the worker,
  playback, fullscreen and voice-recorder states. Settings loading also assigns
  individual disabled states based on worker presence. These are investigation
  leads, not a reproduced diagnosis of this reported stop sequence.
- **Follow-up:** reproduce stop during preparation and playback in all three modes,
  including recording and worker cancellation; verify return to editing and a
  successful subsequent start through actual user controls.
- **UX feedback:** the user considers the current UI/UX unacceptable and suggests
  starting its design afresh. Reassess complete task flows and lifecycle behavior
  before further layout changes; no full rewrite has been agreed or started.

## Recorded issue — speech model repeatedly unloads

- **Status when recorded:** open; user-reported, not reproduced or fixed.
- **Reported:** 27 September 2026. The user reports that the speech model
  "always gets unloaded", disrupting the workflow.
- **Expected:** model retention must follow the selected policy. With **Never
  unload**, the application must not automatically unload an otherwise usable
  model between operations while AutoTalk remains open. Manual unloading,
  application exit, failures or required model changes must be distinguishable
  from automatic retention-policy actions.
- **Follow-up:** establish the selected policy and exact triggering operations;
  trace model ownership through preparation, preview, presentation stop and
  cancellation. Check policy persistence and show why an unload or reload occurs.
  Do not assume a cause or change the selected policy as a workaround.

## Recorded requirement — Realtime startup in approximately 15–20 seconds

- **Status when recorded:** open; performance requirement recorded, not measured or implemented
  in this pass.
- **Reported:** 27 September 2026. The first Realtime presentation start is
  extremely slow even when the speech model is already loaded.
- **Target:** approximately **15–20 seconds from clicking Start to the first
  audible narration with its slide displayed**, with the required speech model
  already loaded and ready. This includes opening narration generation when no
  prepared narration/audio exists; cached playback alone cannot validate it.
- **Progress UX:** show the actual current stage, elapsed time and measurable
  completed/total work wherever available. Report narration generation, opening
  audio synthesis and playback buffering separately. Never invent a percentage
  or use a timer-driven estimate as measured progress. If a stage supplies no
  measurable total, say so and show its activity and elapsed time explicitly.
- **Verification:** record end-to-end and per-stage timings on the target Linux
  machine across repeated starts, documenting deck, voice, generation settings,
  cache state and engine readiness. Distinguish already-loaded startup from cold
  loading/downloads and cached-audio playback. Confirm that stopping/restarting
  does not cause unnecessary model unloading or regeneration.
- **Constraint:** preserve coherent opening narration and the chosen voice/delivery;
  the startup target is an acceptance goal, not an achieved or guaranteed result.

## Recorded UX requirement — justify every interaction's placement

- **Status:** open; requirements recorded, no application changes made.
- **Reported:** 27 September 2026. Some controls still appear arbitrarily placed;
  the user rejects the overall interaction structure, not merely isolated defects.
  Earlier placement assessments do not establish ordinary-user usability.
- **Required design basis:** map each interaction to a concrete user task, its
  scope, the point in the workflow where it is needed, and its importance. Group
  related controls together. Keep P1 actions directly visible and reachable with
  the fewest clicks; place P2/P3 controls progressively deeper where appropriate.
  Any repeated entry points must have a clear task-based reason and invoke the
  same behavior. Existing widget placement is not a reason to retain it.
- **Explicit settings requirement from this discussion:** provide separate
  **Application defaults**, **Talk settings — [title]**, and **Slide settings —
  [number]** dialogs. Remove the in-dialog scope selector. Keep shared inheritable
  settings consistently ordered and labelled across the three; clearly identify
  scope-specific controls and inheritance. Reuse underlying editors/resolution
  rather than duplicating their implementation.
- **Acceptance:** review complete ordinary-user journeys and a clickable proposal,
  including preparation, presentation, stop, return to editing and restart. Each
  placement must be explainable through those tasks and assessed by visibility,
  clicks, grouping and scope clarity. Do not declare placements correct merely
  because they match the previous proposal or pass widget-level tests.
- **Scope:** redesign interaction structure first. Preserve required capabilities
  and platform-native appearance; no new implementation or full code rewrite is
  authorized by this issue entry.

## Flat settings and three scopes — historical implementation, superseded UX

The description below records the existing implementation, not the accepted
direction for the next UX design. The explicit settings dialogs required above
replace its scope-selector approach in the proposed redesign.

The nested settings tree is replaced by five meaningful flat pages with an
application/talk/slide scope selector. The [scoped settings contract](design/SCOPED_SETTINGS_IMPLEMENTATION.md)
records ownership, inheritance, persistence and verification requirements. Voice
origin is preserved independently of the synthesis backend. Quick, Prepared and
Realtime resolve the same settings and audio validity. Product/platform scope
below is retained; this pass is tested on Linux only.

## Task-based UX placement — implemented, 27 September 2026

The accepted [placement contract](design/UX_PLACEMENT_PROPOSAL.md) now governs the
main window, task dialogs, sidebars, seven menus and presentation controls.
[Placement verification](design/UX_PLACEMENT_VERIFICATION.md) maps every contract
group to its implemented route and Linux checks. This replaces the earlier
earlier interaction structure while preserving the product/platform scope below.
The subsequent settings consolidation is implemented: all configuration shares
one Settings dialog; existing shortcuts select a named section, with one common
Save/Cancel transaction across sections. Recordings & export remains a task window.
The [user guide](USER_GUIDE.md) documents the current Prepared, Quick and Realtime
journeys, whole-talk and per-slide preparation, voices, engine policies and recording.

## Restored start/editor interaction — current refinement

The fixed upper-right actions are Prepared: **Prepare and start**; Quick and
Realtime: **Start**. No changing next-step dispatcher or text-review barrier remains.
Each editor action has one purpose: Codex text creation/rewriting, Qwen audio
creation, or playback of existing audio. Dialog-opening commands retain ellipses;
direct commands omit them. Preview stop/completion clears preview state before
notifying the UI. Account defaults and explicit models share the same display names.
Verification and packaged Linux delivery are recorded in VERIFICATION.md.

## Default project location — implemented

New PDF imports collect their projects in the source PDF folder's `autotalk`
subdirectory. Existing projects remain openable where they are; repeated imports
create numbered project folders without overwriting prior talks.

## Per-slide speech and Realtime reuse — implemented

Prepared and Realtime share the selected-slide text → audio → playback flow,
with separate, persistent text and audio buttons. Rewriting stays available after
audio preparation; the audio button requires usable narration.
Creating audio uses the displayed text and persists the result without a separate
audio approval step. Rewriting words and regenerating audio remain distinct menu
actions. Failed/cancelled regeneration retains the previous completed recording.
Existing wording stays usable after context changes without approval;
remaining-text creation fills only missing/translation slides. Saved current audio
survives mode changes between Prepared and Realtime and is reused after reopening.
Realtime checks the saved opening buffer immediately, before later preparation
finishes. Quick retains its simple page and explains its defaults before switching
away from prepared audio. See USER_GUIDE.md and VERIFICATION.md for tested behavior.

## Ordinary-user usability pass — implemented

The nine original review groups, 15 second-pass findings, and all **12 latest
walkthrough findings** are implemented in [the individual acceptance list](design/USABILITY.md).
The latest pass removes duplicate welcome controls and the nested voice dialog,
clarifies readiness/translation/completion, separates presentation from capture,
and adds shared fullscreen slide navigation. Enlarged slides stay inside AutoTalk.

Cumulative usability accounting is **117 net production lines**, within the
approved 120-line limit, and **506 net test lines**. The latest pass removes one
net production line and adds 97 test lines. Linux verification includes 148 passing
tests, with 89 relevant tests repeated after the final simplification, native
Breeze walkthroughs and real prepared-audio playback/MP4 saving. The earlier real
Realtime generation and Qwen preview runs remain separate evidence. Model loading
is still the main cold-start wait; this UI pass does not claim to accelerate it.
Earlier product/platform requirements and deferred qualifications below remain.

## Current follow-up — implementation started

The current scope is checkbox visibility, recording discovery, Linux screen/audio
recording for live demonstrations, the three CI failures, and the explicitly
approved speech-continuity work below. Preserve startup and sustained Realtime
measurements and all existing product/platform requirements.

Implemented in the working tree:

- The local Linux bundle includes system Qt 6.10.2, Plasma integration and Breeze.
  The platform selects the style; isolated tests cover other styles and live
  palette/style changes. Build-time staging replaces the wheel's Qt module sources
  with installed counterparts, retaining matching optional modules when absent.
  The desktop UI refinement now follows the approved clickable prototype; see
  [design and acceptance](design/UI-REDESIGN.md).

- Linux CI includes `libpulse0` so QtMultimedia can import.
- Subprocess output uses UTF-8 text mode with universal newline handling.
- PDF import and export destroy their operation-owned Qt documents on every exit,
  before staging moves/cleanup; exception tracebacks cannot retain native handles.
- Native Qt controls follow the system light/dark appearance, including live changes;
  the forced dark stylesheet and custom checkbox asset are removed.
- Shared checkboxes have visible native states. Recording selection stays below
  the editor, Quick and presenter views; active capture shows recorded time.
  Destination is under Talk settings → Recording; outputs are in Export / recordings. Settings lock during presentation.
- The existing delivery resolver supplies steady-pace, restrained-expression and
  consistent-character guidance. Style/custom/slide overrides remain explicit;
  Base receives no unsupported vocal instruction. All modes, including Quick,
  use the resolved slide → talk → application voice settings.
  Effective instructions remain part of audio freshness. Splitting is unchanged.
- The sampling override label identifies its main-generator scope. Sampling
  defaults are unchanged; both-stage comparison and listening acceptance remain open.

The user approved the narrow PDF/UI additions. They add 20 net production lines
relative to the prior follow-up changes, within the estimated 15–25 lines. Linux
verification passes 99 tests after the platform-style refinement, with minimum-size
UI checks in light/dark appearance at normal/150% scaling.

The clickable-prototype refinement now includes a dedicated voice library, real
preview waveform, per-slide regeneration/timing/inclusion/after-slide controls,
menu commands and saved/unfinished recording discovery. Old tabs are removed.
Linux screen capture uses Qt's desktop chooser, a bounded encoder queue and the
PulseAudio system monitor, with optional default microphone. Recording survives
narration pauses and the final slide, and uses the existing session/export path.
Slides/narration capture remains available on all platforms. The latest Linux
regressions and live checks are recorded in VERIFICATION.md.

A new real Codex/Qwen Realtime run completed both slides and produced its MP4.
Desktop capture passed on both an isolated Linux X11 display and native Wayland
with user-granted Plasma sharing. Stereo monitor capture and microphone mixing
have separate checks. Physical microphone, permission revocation and simultaneous
desktop capture under sustained Qwen load remain qualification work. Do not treat these as already accepted.

The running user's speech session was not interrupted for synthesis comparisons;
the normal exclusive GPU lease rejected the comparison attempt. The reproducible
fixed-text/seed comparison harness is in ignored
`artifacts/improvements/continuity/compare.py`. Neither sampling defaults nor the
chosen voice were changed. Base reference evaluation and listening remain open.

**Deferred: Windows QEMU/KVM setup and local Windows VM testing.** These are
optional future work and do not block current fixes or delivery. When explicitly
resumed, prepare a reusable Windows 11 x64 VM (8 vCPUs, 16 GiB RAM, 128 GiB dynamic
disk, UEFI/Secure Boot, virtual TPM), official installation media and a clean
checkpoint. Match CI's Python 3.12 environment; test imports, persistence, playback,
exports, native packaging and launch without developer Python. GPU passthrough is
excluded. Windows/macOS CI remains required after authorized publication; local
testing remains Linux-only.

## 1. Product and platform support — preserved

Keep AutoTalk, executable `autotalk`, Python/PySide6, PDF import and timed spoken
presentations, selectable language/conference scope (URL or editable text),
Codex app-server subscription sign-in/model/reasoning, and automatic local
Qwen3-TTS 1.7B installation. Preserve Prepared, Quick and Realtime, language
versions, voice library/design/cloning, delivery controls, fullscreen display
choice, system-owned audio routing, clips/backgrounds, recording, and persistence.

Retain Linux NVIDIA/vLLM-Omni, Windows NVIDIA/PyTorch, and Apple Silicon macOS/MLX
adapters and native packaging. CPU/NPU and Intel Mac inference remain outside
scope. Only Linux is qualified in this pass; native Windows/macOS qualification,
signing and distribution remain future work. Automatic provisioning cannot
supply missing GPU hardware or replace the operating system's driver setup.

## 2. Architectural rules and implementation sequence

Trace authority, transformations, ownership, lifetime, presentation, persistence,
and tests before changes. Reduce first, reshape existing code second, add narrowly
only where necessary. Derive speech validity from its actual inputs; keep one speech-process
owner, one playback position, and one shared audio mix. Preserve unrelated work.

The following architectural corrections are implemented. Finding 5 remains open
for acoustic acceptance: matched samples still show pace variation. Qualification
limits and measured results are tracked below.

| Review finding | Narrow correction and acceptance boundary |
| --- | --- |
| 1. Partial regeneration approves stale slides | Removed script approval/context stamps. Partial rewriting preserves other words and audio; legacy stamps are ignored when loading. Start prepares only missing/translation text and invalid audio. |
| 2. Language silently relabels old text | Select existing language versions or create translation drafts; preserve originals and send translation instructions to Codex. |
| 3. Realtime serial startup | Load speech concurrently with Codex. A single first request plans the deck and writes its opening slide; later slide requests overlap synthesis and use the same thread/context. |
| 4. Repeated cold model loads | Lease the existing speech process across preview/preparation; reload incompatible configurations, release on error/exit or selected idle policy. No separate model service. |
| 5. Inconsistent sentence delivery | Group compatible sentences within paragraphs and the existing 300-character bound. Retain Earliest playback as a selectable tradeoff. Preserve voice and effective delivery settings, and record segmentation provenance. Listening acceptance remains separate. |
| 6. Confusing/clipped UI | Menu bar, compact toolbar, slide editor/inspector, Quick and presenter views; sectioned Talk settings and Preferences; one contextual primary action; visible recording control. See design/UI-REDESIGN.md. |
| 7. Lost style/redesigned preview | Combine style and attributes with explicit instruction precedence. Accept the exact VoiceDesign preview and explain the transition to Base controls. |
| 8. Expensive timing updates | Audio descriptors change at project/audio transitions. Timing labels read descriptors at 4 Hz; audio feeding performs no full-deck file/hash traversal. |
| 9. Buffering/misleading timing | Show incomplete remaining time as estimating, expose buffered audio and fullscreen state, adapt consistency-first buffering to observed production, persist stage/run measurements. |
| 10. Hidden recovery/manual overwrite | Separate Continue, Resume preparation, Stop and edit, and explicit regeneration. Ignore events from finished jobs; reuse completed scripts/audio. An interrupted slide restarts from its beginning. |
| 11. Fragile recording/export | Direct MP4/WAV/M4A export through the same mixer, discover pending sessions, retain export inputs/destination on failure, and offer finish/save-later/cancel on close. |
| 12. Enlarged previews/mono imported music | Render captured original PDF at export resolution. Use a stereo 48 kHz mix and keep speech assets at 24 kHz; retain stereo clips/backgrounds. |

### Remembered defaults

- Speech engine: immediate Load/Unload with current state; saved loading policy
  (on demand / presentation start) and unloading policy (exit / presentation end /
  five idle minutes / each preparation or preview). Manual preload follows the
  same policy without counting as generation. Save/Cancel changes only policies;
  playback continues during model management. The existing speech owner remains
  authoritative; pauses, leaving fullscreen and live demos are not end events.
- Model-loading progress: explicit stages, measured file/data counts where
  available, no invented percentages for engine startup. Explicit **Check for
  model updates…** compares the selected pinned model with upstream metadata;
  it does not replace the verified manifest or download weights.
- Quick: generate once and start; alternatives fit / require duration match.
- Realtime: consistency first with grouped speech and adaptive buffering;
  Earliest playback uses a shorter first unit and lower minimum buffer.
- Existing project settings are preserved when reopening. New project defaults
  use the remembered preferences.

## 3. Verification and remaining acceptance

Measure application launch separately from runtime installation, cached cold
model load, warm generation, first audio, first playback, sustained production,
fitting and export. Record a baseline before performance changes. Test public
workflow boundaries, legacy migration, cancellation/resume, manual acceptance,
voice-preview identity, output timing/stereo, recovery/close, minimum-size UI,
and an 80-slide timeline. Production and test line changes are reported separately.

Linux regression tests, real GPU/end-to-end Realtime, startup/UI timing, and
export evidence are recorded in VERIFICATION.md. These establish the exercised
cases, not a latency guarantee. Subjective voice continuity, own-voice similarity,
all-language/dialect adherence, and sustained generation of a full conference
remain acceptance work. Long synthetic media export is distinct from long speech
inference. Native Windows/macOS testing is deliberately excluded from this pass.

## 4. Improvement backlog from hands-on review

Collected 2026-09-25. Items below remain requirements or investigations; the current
follow-up above records partial implementation, not overall completion. They supplement the preserved scope and the
remaining acceptance work above. This list does not authorize publishing changes
or expand the current Linux-only local testing scope.

### Recording and live demonstrations

1. **Make checkboxes recognizable.** Fix the shared dark-theme checkbox appearance,
   including Record presentation and Loop: clear border, adequately sized indicator,
   and distinct unchecked, checked, focused and disabled states. Verify visibility
   at normal and enlarged display scaling; the complete label remains clickable.
2. **Make recording discoverable before Start.** Expose recording selection and its
   enabled/disabled state near the primary presentation action, without requiring
   users to discover controls below the scroll viewport. Make the destination easy
   to find and explain when a recording is active versus when a file is being saved.
3. **Offer two recording sources.** Preserve Slides and narration for clean internal
   capture, and add Screen and audio for the actual performance, including manually
   operated applications, pointer movement and intermediate live demonstrations.
   Keep direct prepared-talk export available independently of live recording.
4. **Continue screen recording through a demo.** Leaving fullscreen pauses narration
   and preserves its position while screen recording continues. Returning to the
   slides and choosing Continue resumes narration in the same recording. Apply this
   behavior to screen recording explicitly; preserve the existing internal-capture
   pause policies.
5. **Give screen recording explicit Start/Stop controls.** Its lifetime must be
   independent of fullscreen and narration playback. Reaching the final slide must
   not silently end a recording that may include a closing demo or discussion.
   Show a persistent recording indicator and elapsed recording time, distinguishable
   from the narration playback state. Define close/failure behavior and retain a
   recoverable result when interrupted.
6. **Use native Linux screen selection.** Investigate the desktop screen-capture
   portal with PipeWire for Plasma/Wayland. Let the user select the capture source
   through the system dialog; keep it distinct from AutoTalk's fullscreen-display
   selection. Handle cancellation and capture-source loss visibly. Preserve future
   Windows/macOS support without assuming the Linux capture path works there.
7. **Select recording audio sources.** Offer AutoTalk narration, microphone for live
   explanations, and desktop/demo audio, individually or together where supported.
   Playback destination routing remains owned by the OS. Prevent capturing narration
   twice through both the internal mix and desktop output; verify synchronization,
   levels and behavior when sources disappear.
8. **Investigate encoding during the presentation.** Aim for a short finalization
   step after Stop instead of a full post-presentation encoding pass. Measure CPU/GPU
   load alongside Qwen before choosing the implementation. Preserve recovery and
   synchronization; avoid a second recording-state authority or duplicated encoding
   policy. Reduce/reshape the existing recorder first and propose only the narrow
   additional capture boundary that is actually needed.
9. **Make saved results obvious.** Show the final filename/location, saving progress
   and Open file/Open folder actions prominently. Keep unfinished recordings easy
   to recover. Explain that prepared export can create a video after an unrecorded
   talk, but cannot reconstruct live demonstrations, navigation or spoken comments.

Acceptance scenario: start recording, present slides with generated narration,
leave fullscreen, demonstrate another application while explaining through the
microphone, return and continue, then explicitly stop recording. Check the resulting
video/audio, timing, source selection, recording indicator and interrupted-session
recovery. A slides-only export does not satisfy this scenario.

### CI reliability

10. **Repair the three confirmed CI causes.** The inspected
    [native-build run for `6199c01`](https://github.com/SNodeC/AutoTalk/actions/runs/36144942117)
    failed before packaging on Linux and Windows:
    - Linux: install the missing `libpulse0` runtime dependency; QtMultimedia fails
      to import without `libpulse.so.0`, even when physical-audio tests are excluded.
    - Windows: end PDF ownership before moving/deleting staged import files.
      `QPdfDocument.close()` retained a file handle in a local Linux probe; document
      destruction released it. Windows reported `WinError 32` in 37 test setups.
      Fix resource lifetime at the import boundary, including failure cleanup.
    - Windows: define consistent newline handling for subprocess text output;
      the output test received CRLF while expecting LF. Fix the boundary contract
      rather than weakening the test to hide an unspecified behavior.
    Retain independent matrix jobs and verify each affected stage after fixes are
    published. The inspected macOS run passed tests, packaging and launch; it did
    not establish GPU speech functionality. The local 0.3 changes were not in that run.

### Existing open quality items — retained

11. **Speech continuity:** continue matched listening and pace/expression evaluation.
    Grouped synthesis removes request boundaries but has not demonstrated reduced
    pace variation. Keep this item open until the audible result is assessed.
12. **Startup and duration:** retain separate cold/warm startup measurements, sustained
    Realtime buffering checks and duration accuracy work. Realtime remains approximate;
    the latest 30-second target produced 46.36 seconds. Do not imply that streaming
    alone solves startup latency, delivery consistency or duration matching.

### Confirmed continuity decisions

The user explicitly supplied the following eight-item list. Its numbering is
separate from the improvement backlog above; retain the heading and explanatory
items separately to preserve the exact decisions.

| Item | Proposal | User decision |
| --- | --- | --- |
| 1 | Replace the fixed 300-character splitting. | **Rejected** |
| 2 | Aim for one synthesis request per slide within model limits; split longer slides at natural paragraph boundaries while streaming audio. | **Rejected** |
| 3 | Use one explicit delivery instruction throughout the talk. | **Approved** |
| 4 | Specify steady pace, restrained expression and consistent delivery rather than only “Professional”; preserve deliberate slide overrides. This is guidance, not an exact acoustic lock. | **Approved** |
| 5 | Evaluate less-random synthesis correctly. | **Approved** |
| 6 | Compare controlled sampling settings for both the main speech generator and acoustic-code generator. The current Linux temperature selector changes only the first. A fixed seed supports repeatable experiments, not continuity between different texts. | **Approved** |
| 7 | If voice character still drifts, evaluate a fixed reference recording. | **Not applicable** |
| 8 | Evaluate reuse of the same accepted audio sample and exact transcript for every passage through Qwen Base. Account for the different delivery controls when switching from CustomVoice; demonstrate improvement. | **Approved** |

Retain the current 300-character splitting. Proceed within the approved delivery,
sampling-evaluation and reference-reuse scope without interpreting item 7 as a
rejection of item 8 or making drift a prerequisite for that approved evaluation.
Preserve selected style and deliberate slide overrides when resolving the common
delivery instruction. Record measured and audible outcomes before claiming a
continuity improvement. No implementation or synthesis experiments were performed
when recording these decisions.

## Preserved detailed feature requirements

1. **Presentation modes:** Prepared retains narration review, voice and conference
   configuration, complete audio preparation, duration fitting, and explicit
   presentation start. Quick accepts PDF, language, and duration, uses the default
   voice without conference input, then prepares and presents automatically.
   Realtime plans the whole deck, buffers initial streamed audio, starts presenting,
   and generates subsequent audio in the background. Playback can begin within
   the first slide when the backend supports incremental audio. It supports optional
   conference context and the selected voice. Wait visibly if the buffer empties;
   show that final duration is approximate until generation finishes. Initial
   runtime/model downloads must finish before synthesis can begin.
2. **Slide progress:** Keep the activity indicator and add completed/total slides
   for stages with measurable slide completion. Identify the active stage; do not
   invent slide percentages while waiting for a whole-deck Codex response.
3. **Multiple languages:** Preserve language versions of narration and audio and
   support per-slide languages for mixed-language talks. Organize generated speech
   by language. Keep voice identity reusable across languages, with language-specific
   reference recordings where supplied. Language and all effective synthesis
   settings must participate in determining whether an audio artifact is current.
4. **Presentation recording:** Add a Record presentation checkbox and a video
   destination. Capture the actual presentation's slide/audio timeline, including
   navigation, pauses, and buffering, with synchronized sound.
5. **Voice selection:** Offer a reusable library of predefined, cloned, and designed
   voices with previews. See the Qwen selections below for controls and capabilities.
6. **Speech quality:** Expose only validated quality/performance choices and explain
   their resource tradeoffs. Qwen has no general quality-level switch. Keep native
   synthesis quality separate from export sample rate/encoding; upsampling does not
   improve the generated voice. Do not present sampling randomness as a guaranteed
   quality or speed control.
7. **Speech style:** Offer Professional, Conversational, Energetic, Calm and
   understated, Lightly humorous, Academic, Storytelling, and Inspirational.
   Apply style to narration wording and to vocal delivery only where the selected
   model supports it. Keep the two capabilities clear in the UI.
8. **Continue fullscreen:** Leaving fullscreen pauses playback and preserves the
   current slide and audio position. Offer Continue presentation and Restart from
   beginning. The existing playback controller remains the authority for position.
9. **Codex model and reasoning:** Add separate selectors populated from app-server
   model/list, including each model's supported reasoning efforts and default.
   Respect account availability and slide-image input requirements. Apply the
   selected settings to scope extraction, narration, and duration revisions; save
   them with the project. Quick mode uses defaults without requiring configuration.
10. **Qwen model and synthesis settings:** Use the 1.7B family for the planned
    feature set. Select the appropriate variant for the voice source, as detailed
    below, and download it automatically when needed. Both model sizes need not be
    installed; 0.6B is outside the initial selector and must not be substituted
    silently. Validate 1.7B memory use and speed on the target GPU before promising
    uninterrupted Realtime playback. Qwen has no Codex-style reasoning effort.
11. **Preparation timing:** Measure Codex work, speech-runtime/model loading,
    synthesis, and duration-fitting passes separately. Show elapsed time and an
    estimate based on observed synthesis speed; in Realtime also show buffered
    audio duration. Separate first-use installation/download time from generation.
12. **Optional presentation audio:** Support user-supplied audio excerpts and
    background tracks, as detailed below. Their playback and video recording must
    follow the same presentation timeline as slides and narration.
13. **System audio destination:** Make AutoTalk's output selectable through Linux/
    Plasma's native Audio Volume controls, independently of the fullscreen display.
    The system audio service owns device routing; avoid a competing application
    device selector or project-specific hardware binding. Provide a System audio
    settings action that opens Plasma's native sound settings and a short preview
    to make the playback stream available for selection. Identify streams clearly
    as AutoTalk and respect system defaults and explicit per-application routing.
    Cover voice previews, prepared playback, Realtime audio, and optional clips.
    Keep routing stable across slide changes, stream recreation, and fullscreen
    exit/continue. Device changes must preserve presentation position; recover
    through system routing or pause with a clear message if no output is available.
    Record video from AutoTalk's own presentation audio mix, independently of the
    physical output device, without capturing unrelated desktop sounds. Verify
    routing and switching with the host's PipeWire/PulseAudio-compatible service;
    documentation of the requirement does not establish that all backends work.

## Qwen voice and delivery selections

These are planned user controls, not additional independent implementations of
voice or style. Organize them into Voice, Delivery, Per-slide directions, and
Optional audio clips, with technical generation parameters under Advanced.

| Selection | Required behavior and limits |
| --- | --- |
| Voice source | Predefined voice uses 1.7B CustomVoice; My voice uses 1.7B Base; Design a voice uses 1.7B VoiceDesign. Show the effective model and its supported controls. |
| Predefined voice / timbre | Offer Ryan, Aiden, Vivian, Serena, Uncle_Fu, Dylan, Eric, Ono_Anna, and Sohee, subject to the loaded model's speaker list. Show native-language profiles and a preview in the chosen talk language. |
| Personal voice | Record/import reference audio, optionally provide its exact transcript, name the voice, and save it for reuse. Explain the difference between audio-plus-transcript conditioning and speaker-identity-only conditioning. |
| Designed voice | Describe a new voice, preview it, and save the accepted identity. Reuse an accepted reference rather than independently redesigning the voice for each slide. |
| Perceived age | An optional VoiceDesign attribute, with descriptive age groups or free text. Do not promise exact age transformation of a cloned or predefined voice. |
| Acoustic attributes | Offer descriptive pitch/register, pace, energy, warmth/texture, articulation, and vocal projection where supported. These are instruction-based guidance, not calibrated pitch, decibel, or words-per-minute controls. Keep output volume separate. |
| Speaker background | An optional persona/role description guiding voice design and delivery. Keep it separate from conference scope and factual narration; it must not become an invented speaker biography in the talk. |
| Single or multiple attributes | Use one delivery editor for individual adjustments and combined settings. Save named presets and provide a custom instruction box. Resolve conflicting preset, field, and free-text directions into one effective instruction. |
| Style and human-likeness | Use the style choices in item 7, with natural rhythm, emphasis, and pauses as the default quality goal. Do not imply a measurable human-likeness percentage or add fillers automatically. |
| Gradual control | Allow section/slide directions such as a calm opening, rising enthusiasm around results, and a measured conclusion. Support within-passage progression as best-effort instructions, without promising exact timed transitions or changing voice identity. |
| Cross-language voice reuse | Keep the chosen identity across language versions and mixed-language passages. Language selection controls synthesis; Codex creates/translates narration. Preview each language, and avoid guarantees of identical accent or pronunciation quality. |
| Accent / dialect | An optional descriptive preference where the model/voice combination has been validated. Do not infer arbitrary dialect-generation support from tokenizer reconstruction demos. |
| Nonverbal expression | Optional, previewed delivery cues such as a chuckle or sigh when the selected model can produce them. Do not assume a universal sound-tag syntax; use imported audio for precisely controlled effects. |
| Advanced synthesis | Expose supported temperature, top-k, top-p, sampling, and repetition-penalty controls with model defaults and Reset. Keep backend-specific/internal sampling controls advanced. Treat maximum generated tokens as an output guard, not a talk-duration or quality selector; detect truncation. |
| Audio export | Preserve native 24 kHz synthesis. Offer output format/encoding and resampling only for export compatibility; do not label a higher export sample rate as higher generated quality. |
| Streaming | Use an incremental-audio backend for Realtime and show buffered duration. Evaluate vLLM-Omni locally; the standard Qwen wrapper's non_streaming_mode flag alone does not enable incremental output. Keep backend setup automatic. |
| Singing / music excerpts | Allow imported clips for musical examples or introductions. Generating new singing from arbitrary lyrics and melody is outside the established Qwen TTS capability and needs separate evaluation. |
| Background sound / ambience | Allow optional imported tracks with volume and placement controls. Keep them separate from narration and voice references so they can be changed independently. Do not expose tokenizer reconstruction as a text-to-sound generator. |

### Model boundaries and acceptance criteria

- CustomVoice and VoiceDesign support natural-language delivery instructions.
  Base voice cloning does not expose the same direct instruction interface.
  Disable unsupported controls with an explanation rather than silently ignoring
  them. A designed reference reused through Base inherits this limitation.
- Download only the selected variants and manage their lifetime automatically;
  do not require the user to run servers or keep all three models in GPU memory.
- Keep one saved voice profile and one effective delivery configuration, with
  explicit section/slide overrides. Save model, language, reference, style, and
  synthesis settings with generated artifacts so changes invalidate affected audio.
- Provide previews using the selected voice, language, and effective delivery.
  Review consistency, pronunciation, and prompt adherence on the target machine;
  model demonstrations are not acceptance tests for AutoTalk.
- Include delivered audio, optional clips, and track timing in duration accounting,
  synchronized slide changes, pause/resume, and recorded video. Style changes can
  change duration. Changed settings must invalidate affected prepared or queued
  audio before it can be played.
- Prepared exposes full authoring. Quick uses the resolved voice and automatic
  delivery settings without conference input. Realtime uses supported selected settings with
  visible buffering and no promised first-audio latency until measured locally.
- The article's Dialect, Singing, Paralanguage, and Background Sound Reconstruction
  examples demonstrate encoding/decoding of existing audio. Do not implement them
  as four unrestricted generation switches or add a redundant reconstruction pass
  to ordinary imported-clip playback.

## Performance evidence and capability sources

The [current measurements](VERIFICATION.md) separate application launch, model
loading, Codex planning, first audio/playback and synthesis. Cached cold model
loading dominates the tested cold Realtime start; warm starts avoid that load.
Sustained synthesis still determines whether buffering can keep up. Duration
fitting adds narration and synthesis passes. Historical 0.6B figures in the
verification record are not measurements of the current 1.7B runtime.

- [Codex model discovery and supported reasoning efforts](https://learn.chatgpt.com/docs/app-server#models)
  provide the selectable capabilities; do not hard-code account/model availability.
- [Official Qwen3-TTS model capabilities](https://github.com/QwenLM/Qwen3-TTS#released-models-description-and-download)
  distinguish model sizes, predefined voices, cloning, and instruction control.
- [Qwen's capability article](https://qwen.ai/blog?id=qwen3tts-0115) demonstrates
  voice design, expressive delivery, cross-language voices, and tokenizer audio
  reconstruction; the selections above distinguish these capabilities.
- [Voice design and reuse](https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone)
  documents the designed-reference-to-Base workflow.
- [Qwen inference interface](https://github.com/QwenLM/Qwen3-TTS/blob/main/qwen_tts/inference/qwen3_tts_model.py)
  documents generation controls and the standard wrapper's streaming limitation.
- [vLLM-Omni speech interface](https://docs.vllm.ai/projects/vllm-omni/en/stable/serving/speech_api/)
  documents a candidate local streaming backend and its output controls.
- [Plasma Audio Volume](https://docs.kde.org/trunk_kf6/en/plasma-pa/kcontrol/plasma-pa/index.html)
  documents system and application audio controls.
- [Qt audio output](https://doc.qt.io/qt-6/qaudiooutput.html)
  documents device selection and the system-default output.
