# 0.3 refinement verification — Linux only

## Project folders beside the source PDF — 2026-09-26

New imports use `<PDF folder>/autotalk/<PDF name>-AutoTalk/`. The import entry point
owns this location choice; the existing importer, relative project assets, recent
projects and saved-talk loader remain unchanged. Existing folders receive numbered
siblings instead of being overwritten. No migration or second location policy is
introduced. Preferences, Getting started and the user guide describe the same rule.

**50 relevant Linux tests passed in 11.56 s**, covering actual PDF import twice,
unique sibling project folders, persisted manifests and existing project/workflow
behavior. Production Python **+4 / −5 = −1**; tests **+4 / −5 = −1** relative to this
task. Evidence: `artifacts/project-location/`. Audio-server qualification below
is unchanged; this correction does not modify playback.

## Separate slide-text and slide-audio controls — 2026-09-26

Correction: text creation/rewriting and audio creation are independent actions.
Both buttons stay visible in Prepared and Realtime. Audio creation requires
usable narration and cannot fall back to writing text. The existing text rewrite
confirmation and saved-audio reuse behavior remain in place; no approval state
or workflow was added. Controls share the existing row; Qt font/layout metrics
keep the duration label readable at 940×680 with the native Breeze style.

- **63 relevant Linux UI/workflow tests passed in 11.01 s**. Additional geometry
  assertions passed for both Prepared and Realtime, including readable duration,
  no overlap, retained rewriting after synthesis and disabled audio for empty or
  untranslated narration. Existing audio-server qualification below is unchanged.
- Native Wayland/Breeze screenshots cover empty text, available narration,
  prepared audio and minimum-size Realtime. Cached fullscreen playback still starts
  while later preparation is blocked, using synthetic speech for this UI check.
- Production Python **+9 / −10 = −1**; tests **+43 / −9 = +34**, relative to the
  start of this correction. Existing assertions were updated for the explicitly
  requested two-button behavior, with added rewriting and layout checks.

Evidence: `artifacts/separate-slide-buttons/`.

## Selected-slide speech and saved-audio startup — 2026-09-26

Invariant: speech belongs to the slide's text and effective synthesis settings,
not to Prepared versus Realtime. The editor and background workflow reuse the
same artifact-validity check and synthesis implementation. There is no audio
approval field or gate. Existing text review now protects generated wording too;
context changes cannot silently replace it during Start.

- **235 tests passed in 31.89 s**, excluding the four audio-device cases; the
  three audio-device UI tests separately **passed in 4.38 s**. New tests cover
  selected text/audio creation in both editor modes, saved-talk reuse in all
  modes, cancellation-safe regeneration, preserved neighboring slides, cached
  startup before worker completion, language isolation and waveform restoration.
- **One existing PipeWire stereo-routing test remains failing**: its virtual
  monitor captured silence. A separate baseline run crashed in Qt audio-device
  initialization. Playback/media source is unchanged in this work. These results
  do not establish the host/test failure's root cause; the full suite is not
  claimed green. The crashed test's recorder and virtual sink were cleaned up.
- Native Wayland/Breeze verification exercises creation, automatic audition,
  Prepared/Realtime controls, minimum window size and actual fullscreen playback
  from cached audio while later preparation is blocked. Synthetic speech avoids
  changing the user's active GPU model; Qwen voice quality is not reassessed here.
- A controlled **600 ms** background operation delayed cached startup to
  **659 ms** with the baseline and **6 ms** with the change. This measures removal
  of a startup dependency, not model loading or inference throughput.
- The rebuilt native Linux bundle passed its empty-PATH saved-project smoke test
  and Qt audit: 27 libraries/plugins verified; all 17 mapped Qt libraries are bundled.
- Waveform file identity now drives reloads on audio replacement, invalidation
  and restoration. The playback timer performs no file/configuration scans.

Production Python **+82 / −41 = +41**; tests **+254 / −0 = +254** relative to the
start of this task. Growth extends the existing selected-page preparation path,
safe replacement artifacts and shared startup-buffer handling; there is no new
speech owner, approval mechanism or presentation mode. Evidence is under
`artifacts/slide-speech/`. Windows/macOS remain untested in this pass.

## Backend GPU-loading observations — 2026-09-26

Invariant: backend diagnostics describe measured work; only the speech worker's
successful service-readiness check makes the model ready. A narrow decoder for the
pinned vLLM 0.28 output feeds the existing model-progress events through the
SpeechSession queue. No loader replacement, dependency patch, GPU-memory polling,
extra thread or estimated percentage is added. Unknown output remains in the log.

The display now exposes checkpoint-file counts for each loading pass, loaded
speech-weight counts, model-loading memory/time, inference-cache memory/capacity,
GPU initialization duration and per-engine initialization. The final diagnostic
stage says Checking speech service. Late loading diagnostics are ignored outside
the startup wait, including when queued just before readiness.

- **224 Linux tests passed in 34.13 s**; **54 focused progress/lifecycle tests passed
  in 8.47 s**. Coverage includes the recorded real-backend trace, carriage returns,
  ANSI formatting, invalid counters, unknown messages, backend/lifecycle isolation,
  late messages, cancellation and full file counters before actual readiness.
- Native Qt replay of the recorded trace exercised the real stderr reader, event
  queue and progress widget: 27 displayed events, all text fitting the dialog.
  Screenshots cover file counts, model memory/time and service checking.
- Decoder benchmark: 1,000 passes over 27 recorded messages took **0.080 s**,
  approximately **0.080 ms per complete trace**. No extra GPU synchronization is
  performed. This is a decoder overhead measurement, not a cold-load speed claim.
- **Fresh real-GPU acceptance remains pending**: the running user instance owns
  the speech lock and GPU model. It was left untouched. The prior real-GPU cached
  load baseline was 39.03 s; no new end-to-end GPU timing is claimed.
- The rebuilt Linux bundle passed its empty-PATH project smoke test and Qt audit:
  27 libraries/plugins verified, all 17 mapped Qt libraries from the bundle.

Production Python **+41 / −0 = +41**, within the approved 100-line allowance.
Tests **+145 / −0 = +145** (118 Python lines and 27 recorded-output fixture lines).
The decoder is the single backend-specific interpretation boundary; existing job,
logging, progress rendering, cancellation and readiness ownership remain in use.
Evidence: `artifacts/backend-progress/`. Windows/macOS checks remain deferred.


## Native numeric-field alignment — 2026-09-26

The shared minimum-height rule was applied to both spin boxes and their internal
QLineEdit. Breeze allocated a 20-pixel text area inside a 32-pixel control, but the
internal editor was forced to 32 pixels, shifting its text centre down 6 pixels.
The rule now sizes only outer controls, covers integer and decimal spin boxes via
QAbstractSpinBox, and leaves editors inside spin boxes/combos to their Qt style.

- Native Wayland/Breeze before/after measurements cover all ten numeric controls
  in the talk settings: vertical editor offset **6 px → 0 px**. Screenshots confirm
  alignment with neighbouring labels and dropdowns.
- **50 Linux UI/usability tests passed in 11.56 s**. New checks compare actual
  editor geometry with the active style's edit-field rectangle in Prepared,
  Quick and Realtime, including integer and decimal controls. All three new cases
  fail against the preserved pre-fix source.
- The rebuilt Linux bundle passed the empty-PATH project smoke test and Qt audit:
  27 libraries/plugins verified, all 17 mapped Qt libraries from the bundle.

Production Python **+3 / −4 = −1**; tests **+23 / −0 = +23**. No padding override,
custom spin-box implementation or font-dependent offset was introduced. Evidence:
`artifacts/spin-alignment/`. Native Windows/macOS checks remain deferred.


## Codex sign-in/sign-out controls — 2026-09-26

The account status reported by Codex controls two buttons in Talk settings →
Advanced: Sign in is enabled while disconnected, Sign out while connected, and
both are disabled during an operation. Authentication status is published before
model discovery so a catalog failure cannot falsely show a signed-out account.
Logout goes directly to `account/logout`, without a login or model-list dependency;
only an acknowledged logout clears account/catalog state. Saved talk overrides
remain unchanged, and a failed logout leaves Sign out available for retry.

- **205 Linux tests passed in 33.13 s**, including both button transitions, busy
  state, successful/failed logout, catalog failure with a known account, and saved
  model/effort persistence. Logout tests use an isolated fake app-server.
- Native Qt verification used the real account read-only: Sign in disabled, Sign
  out enabled, and defaults retained. The user's account was not signed out.
- The rebuilt Linux bundle passed the empty-PATH project smoke test and Qt audit:
  27 libraries/plugins verified, all 17 mapped Qt libraries from the bundle.

Production Python **+30 / −16 = +14**; tests **+62 / −1 = +61**. Combined with
startup discovery, net production growth is **38**, within the approved 60 lines.
The connection method replaces the old context-entry-only settings flow and shares
one account/settings event with the UI; no separate auth cache or polling is added.
Evidence: `artifacts/codex-auth/`. Windows/macOS checks remain deferred.


## Codex startup discovery — 2026-09-26

Invariant: the Codex connection owns account status, its model catalog and effective
configuration. The UI displays that result while each talk retains its saved
model/effort overrides. Startup uses the existing background job and a passive
client; it never installs tools or starts browser sign-in. Successful interactive
connections and narration jobs publish through the same settings event.

- **202 Linux tests passed in 34.75 s**. Contract/UI coverage includes signed-in,
  signed-out and API-key accounts; missing installations; offline discovery and
  explicit retry; cancellation; catalog pagination; configured versus recommended
  defaults; effort-only generation; startup with/without a command-line talk;
  Prepared/Quick/Realtime persistence; and unavailable saved choices.
- Read-only native startup discovered five models and displayed the configured
  **gpt-6-astra / high**, before importing a private test talk. The complete check
  took **1.72 s** (catalog visible at **1.65 s**); no inference was requested.
  The maximum observed 50-ms UI-timer interval was **110 ms** during the check.
- The baseline discovery/cleanup probe took **5.18 s**. Initial UI verification
  exposed a five-second server shutdown timeout after discovery. Closing the
  client's stdin before process teardown removes that delay at its owner. A real
  subprocess test ignores SIGTERM and verifies prompt EOF-driven termination.
- A native Qt screenshot confirms readable populated defaults in Talk settings →
  Advanced. The rebuilt Linux bundle passed its empty-PATH project smoke test and
  Qt-library audit (27 libraries/plugins checked, all 17 mapped Qt libraries from
  the bundle). Windows/macOS testing remains deferred.
- The passive client bounds each protocol request to ten seconds. Failures leave
  the application usable and display a retry instruction; this does not promise
  that an offline server can provide a fresh catalog.

This pass changes production Python **+51 / −27 = +24** and tests
**+161 / −1 = +160**, within the separately approved 60-line allowance. Growth
adds passive connection policy, bounded startup discovery and settings delivery;
the old button-specific result callback and separate model-list state are removed.
Evidence: `artifacts/codex-startup/`. Protocol reference:
[Codex App Server](https://learn.chatgpt.com/docs/app-server).


## Measured model progress and explicit update check — 2026-09-26

The existing task event channel now carries model-stage progress to the existing
operation bar. Narration and slide counters retain their separate meanings. File
verification and snapshot downloads expose completed-file counts; runtime downloads
expose bytes and a known total when provided. Unknown-total stages use a static bar
with a named stage and **Progress not reported**, rather than a made-up percentage.
Parallel Hugging Face byte totals can grow while files are discovered, so snapshot
progress uses its stable completed-file total. No stderr progress parsing is used.

- **186 Linux tests passed in 51.34 s**, including download resume, missing totals,
  cached-file reuse, integrity repair, independent narration/model progress, large
  byte counters, progress relocation into Preferences, update-check errors and
  cancellation, and preservation of the loaded model and policies during checks.
- Byte-bar scaling is tested against large downloads and fractional-MiB totals:
  the bar cannot show full completion before the measured transfer completes.
- Real Wayland/Breeze GPU load verified **13 cached files** and reached ready in
  **39.03 s**. No model download occurred. The earlier load baseline was **38.85 s**;
  this change improves feedback, not inference/startup speed. Maximum observed
  100-ms UI-timer interval was **138 ms** during the check. The test released its
  model afterwards and left the user's project unchanged.
- The explicit online check succeeded for CustomVoice and found the same upstream
  revision as the pinned manifest. Tests cover the different-revision response.
  Checks query metadata only; they do not install a new revision or alter the cache.
- A real pinned Hugging Face 1.33.0 callback check downloaded only `config.json`
  into a private temporary cache, reported **0 / 1 → 1 / 1 files**, then reused that
  cache on the second access. Full multi-GB downloads were not repeated.
- Native screenshots verify readable stage/count text and the update result.
  The Linux bundle audit verified 27 Qt libraries/plugins; all 17 mapped Qt
  libraries came from the bundle, and the prepared-project smoke test passed
  with an empty PATH. Evidence is in `artifacts/model-progress/`; Windows/macOS
  native tests remain deferred.

This pass adds production Python **+79 / −14 = +65** and tests **+210 / −0 = +210**.
Combined with the prior GPU-control pass, production growth is **202 lines**, within
the approved 240-line allowance. The additions report measurements at their source
and provide the requested explicit metadata check; they reuse the existing job,
model owner, progress bar, cancellation and event channel, with no new timer or
model manager. The previously reported Realtime cached-start delay is a separate
pending fix and is not changed by this pass.

## Speech-model lifecycle controls — 2026-09-26

Invariant: `SpeechSession` alone owns the model, its lease and idle timer. Saved
load/unload preferences describe future events; immediate actions do not edit
preferences. Manual preload is not a synthesis operation. Playback owns the actual
presentation-end signal, excluding previews, pauses and fullscreen exit.

- Full Linux suite: **167 passed in 49.25 s**. After adding a slow-teardown
  responsiveness case, the focused lifecycle suite passed **20 tests in 6.78 s**
  (168 unique tests verified across these runs).
- Subprocess-protocol/UI tests cover all four retention policies, model reuse,
  five-minute timer reset/stale callbacks, deferred release during a lease,
  Save/Cancel and persistence, cancelling load, retry after failure, prepared audio
  during preload/unload, pause/fullscreen/Continue, natural completion, automatic
  video export, and screen capture remaining open until End. A deliberately slow
  child teardown confirms audio advances and Preferences remains usable during
  unloading. These lifecycle tests use a small protocol worker, not Qwen inference.
- Native Wayland/Breeze screenshots cover unloaded/loading/ready, saved versus
  draft policies, Settings menu and light/dark palettes. All choices and Save/Cancel
  fit the existing dialog. Visual ready/loading states use the protocol worker.
- Pre-change real Qwen baseline: **38.85 s cold load**, **0.000065 s compatible
  lease reuse**, **5.15 s teardown**. The post-change hardware run was stopped by
  the normal exclusive GPU lease because another running AutoTalk instance owns
  the model. It was left untouched. Real-Qwen post-change timing and playback
  acceptance remain pending; no cold-load speed improvement is claimed.
- Linux package built successfully. Audit verified **27 Qt libraries/plugins**
  against the approved system Qt/Breeze sources; all **17 mapped Qt libraries**
  came from the bundle. A prepared-project smoke test passed with an empty PATH.
  Windows/macOS native testing and QEMU remain deferred.

Against the snapshot immediately before this GPU-control feature, production
Python **+179 / −42 = +137**; tests **+328 / −6 = +322**. The production increase
is within the separately approved 240-line allowance: explicit model state,
background release and preload using the existing owner/job, independent saved
policies and their UI replace the old immediate retention selector. No second
model manager, job queue or polling timer was introduced. Earlier uncommitted
usability changes are excluded from these counts. Evidence: ignored
`artifacts/gpu-lifecycle/`.

## Second ordinary-user walkthrough fixes — 2026-09-26

All 15 findings have an individual implementation entry in
[USABILITY.md](design/USABILITY.md#second-walkthrough-all-15-findings).
The project still owns language/content, playback owns capture and completion,
and the existing worker owns progress/cancellation. The fullscreen toolbar shares
the controller's End action. Preview synthesis and design acceptance share one
hash-derived output path. The system image viewer handles enlargement/zoom.

- **144 Linux tests passed in 42.89 s**. New journeys exercise untranslated-draft
  rejection at both Project and UI boundaries, preservation of manually translated
  slides, original-language preservation after save/reopen, voice prerequisite
  actions and changing designs, progress inside the active dialog, recording intent
  alongside older output, and fullscreen mouse/finish/automatic-save behavior.
- After the final table-layout adjustments, **43 UI/usability tests passed in
  10.26 s**. No regression assertions were dropped.
- Native Wayland/Breeze screenshots cover the three modes, all sections and menus,
  and minimum-size light/dark layouts. Visual inspection corrected toolbar contrast,
  caption/table clipping and excessive footer wrapping. These are solo walkthroughs,
  not a recruited-user study.
- A real Qwen CustomVoice preview played after **43.72 s**; the prior review measured
  **43.10 s**. A visible dialog spinner, elapsed time and Cancel now explain that wait.
  This is not a synthesis speed improvement or a first-download benchmark.
- A native mouse walkthrough paused/continued a prepared presentation, ended it,
  saved a new slides/audio MP4, and found it beside an older recording. A separate
  final-slide walk verified Return to editing and that Space does not restart it.
  The system viewer received the selected slide, and Gwenview's Zoom In action was
  exercised. The created test viewer was closed afterward.
- Five isolated first-window runs averaged **0.641 s** (median **0.626 s**), versus
  **0.686 s** (median **0.693 s**) before this follow-up. Run-to-run variation means
  this establishes no material startup regression, not a durable speedup.
- The rebuilt native package passed its empty-PATH project-opening smoke test:
  **27 matching Qt libraries/style plugins**, **17 loaded Qt libraries**, all from
  the bundle. Existing platform integration and native file browsing remain packaged.
- This pass did not repeat the complete Codex/Realtime generation run, first-ever
  downloads, browser login, microphone capture, or Plasma sharing permission. Earlier
  evidence below remains applicable to those unchanged paths. The native audio
  backend logged an unsupported Bluetooth-format probe; the tested presentation and
  recording completed, but this is not qualification of that Bluetooth device.

Accounting against the immediately preceding review snapshot: production Python
**+160 / −112 = +48**; tests **+196 / −8 = +188**. Cumulative against the original
usability baseline: production **+411 / −293 = +118**, tests **+416 / −7 = +409**.
This remains inside the original approved 120-line allowance; the proposed increase
was unnecessary. No new workflow flags, timers, services or synthesis policies were
introduced. Evidence is in ignored `artifacts/usability-followup/`.

## Ordinary-user usability pass — 2026-09-26

Coverage and architectural invariants are in [USABILITY.md](design/USABILITY.md).
This pass preserves the existing project, playback, worker and recording owners.
It removes competing next-action decisions and reorganizes existing controls.
Guided sign-in, recording metadata and computed status handling require the net
addition; the user explicitly approved up to 120 production lines.

- **135 Linux tests passed in 40.95 s** with native Qt. After the final export
  completion correction, **76 focused UI, playback, recording and usability tests
  passed in 11.24 s**. These include actual asynchronous job completion, default
  PDF import with no second chooser, manual-review guards in all modes, voice
  control visibility, state-appropriate presentation actions, recording guidance
  and discovery, legacy recovery, direct-export links, and settings cancellation.
- Scripted app-server subprocess tests cover browser sign-in and cancellation;
  pipeline tests prevent model loading before sign-in succeeds, and preserve
  audio-only resume without Codex. Authentication follows the existing
  [official app-server browser flow](https://learn.chatgpt.com/docs/app-server#3-log-in-with-chatgpt-browser-flow).
  No user account was logged out or credentials replaced for testing.
- Native Breeze screens, menus and dialogs were inspected in light and dark at
  normal and 150% scaling, including 940×680 editor/presenter layouts. Advanced
  slide controls are collapsed initially; the simpler inspector and combined
  preview/rewrite row leave more height for the PDF. These are widget/visual
  checks, not a recruited study of inexperienced users.
- Five first-window startup runs averaged **0.699 s**, versus **0.656 s** before
  this pass. Medians were **0.692 / 0.646 s**. This measures application startup,
  not model loading; it does not establish a speech-startup improvement.
- A real Codex/Qwen 1.7B Realtime run completed both slides and saved an MP4 with
  no reported errors. First playback was **41.97 s**, model load **35.76 s**,
  opening planning **15.06 s**, speech generation **11.86 s** for **27.72 s** of
  audio. Playback began before all preparation completed. The previous recorded
  run's first playback was 40.32 s; model loading remains the main cold-start cost.
- Decoding that MP4 verified H.264 video **27.767 s** and AAC audio **27.751 s**.
  Both audio channels were present with RMS **0.07427** and correlation **0.9999996**.
  This run used slides/narration recording. Desktop-sharing permission was not
  requested again; the earlier native Wayland acceptance remains separate evidence.
- The rebuilt package verified **27 matching Qt libraries/style plugins** and
  **17 loaded Qt libraries**, all from the bundle. Its project-opening smoke test
  passed with an empty PATH. Platform appearance and the existing KIO filesystem
  backend are retained. No Windows/macOS testing was performed.

Accounting relative to the working tree immediately before this usability pass:
production Python **+279 / −209 = +70**; tests **+226 / −5 = +221**.
The changes stay below the approved 120-line limit. Test updates preserve the
review guard and move cancellation assertions to the correct settings scopes;
one producer-event fixture now supplies the real job's title contract. No test
was dropped. Evidence is in ignored `artifacts/usability/`.


## Packaged native file navigation — 2026-09-26

The previous native chooser inspection ran from source and missed a packaging
dependency. A frozen reproduction showed an empty directory view and KIO's
`Unknown protocol 'file'` error. PyInstaller collected the Plasma dialog but not
its dynamically discovered local filesystem plugin. The package specification now
collects `kf6/kio/kio_file.so` from the selected Qt distribution as a binary, so
its dependencies are also analysed. Application filters and native dialog
selection are unchanged; ordinary Qt distributions without this plugin are
unaffected.

- **4 build tests passed**, covering matching/mismatched Qt bindings and package
  collection with/without the filesystem backend.
- A frozen probe built with the same specification verified visible folders,
  PDF filtering, keyboard entry into a subdirectory, Alt-Up parent navigation,
  and acceptance of the exact PDF path. Directory-only and save dialogs also
  displayed subdirectories.
- The same checks passed with isolated preferences and an empty PATH. Runtime
  mappings confirmed the filesystem plugin came from the bundle. A child-exec
  trace showed no external `kioworker` execution with this machine's KIO version.
- Evidence, the frozen probe and its logs are in ignored `artifacts/file-dialog/`.
  This verification is Linux-only. No application behavior or speech defaults
  changed, and the application test suite was not repeated for this packaging fix.

This fix adds **3 packaging lines and 22 test lines**, with no application-code
growth. It completes the already approved native Qt bundling by declaring its
missing runtime backend; it adds no application state or fallback implementation.

## Bundled platform style — 2026-09-25

The Linux package now includes the build machine's Qt 6.10.2 libraries, Plasma
integration and Breeze. Qt chooses the style from desktop settings. There is no
new application style resolver, forced style, stylesheet or theme callback.

The initial Qt 6.11.2 probe loaded Breeze but rejected the machine's Qt 6.10
platform integration plugin. An alternate Plasma style selection exposed that
incomplete integration. Matching the Qt version and collecting the native plugins
restores the actual platform selection boundary. Build staging ensures the
bindings' embedded library search paths cannot select wheel modules ahead of
installed counterparts. Qt PDF is absent on the host and uses the matching 6.10.2
binding-package module; all other collected Qt libraries match installed files.

- **99 tests passed in 25.74 s** using the staged system libraries with Plasma's
  platform theme, including the four audio-device tests. Build tests reject Qt /
  binding mismatches before collection and verify native-module precedence and
  the matching optional-module source. The checkbox visual test now waits for
  native check-mark animation; the visible-state assertion remains intact.
- Hash verification covered **27 Qt libraries and style/integration plugins**.
  Runtime inspection after Breeze loaded found **17 Qt libraries**, all within
  the bundle. Opening an isolated saved PDF project passed with an empty PATH.
  The installed checkout launcher also loaded the bundled Plasma/Breeze plugins.
- The packaged application loaded its own Plasma integration and Breeze plugins.
  An alternate isolated Plasma configuration selected the Windows widget style;
  Breeze was not forced. A separate isolated D-Bus session verified existing
  AutoTalk controls following Windows → Breeze and light → dark → light changes.
  The user's desktop preferences and notifications were not changed.
- Source-run native Breeze controls and the native KDE PDF chooser were visually inspected
  in light mode at 100% and dark mode at 150%. The 940×680 workspaces had no
  horizontal overflow. Evidence is in ignored `artifacts/platform-style/`.
- Five source launches before/after had medians **0.500 / 0.688 s** and means
  **0.868 / 1.058 s**; the first run in each batch took **2.334 / 2.558 s**.
  These measure import through the first visible-window event, not speech startup.
  The roughly 0.19-second median increase is a measured native-integration cost.
- The uncompressed native bundle is approximately **538 MiB**, versus **374 MiB**
  previously. It includes KDE dependencies. This host build is not a qualification
  of older Linux distributions; Windows/macOS were not tested. The ordinary CI
  build retains the wheel-based Qt distribution unless `--system-qt` is requested.

Production build code changes are **+21 / −1 (net +20)**. Tests are **+68 / −1
(net +67)**; the dependency manifest adds one net line. Growth implements the
approved bundling of this machine's Qt, including isolated binding/library staging
and a version guard, rather than only the initially estimated plugin discovery.
The application itself adds no production lines. Source and bundled notices
identify the native FFmpeg/KDE components; public-release licensing remains open.

## System appearance — 2026-09-25

The global dark stylesheet and forced Fusion selection are removed. Qt owns the
application palette and native control rendering; heading fonts and primary-action
emphasis remain. The custom checkbox SVG and packaging entry are removed. There
is no theme preference, palette copy, or theme-change callback in production.

- **97 tests passed in 24.54 s** on Linux, including four audio-device tests. The
  added regression changes the application palette light → dark → light while
  the main window and PDF chooser remain open; it verifies inherited colors and
  visibly distinct checkbox states. The previous stylesheet failed this check.
- On Plasma/Wayland, app-local Qt color-scheme notifications were exercised on
  existing controls. Their palettes followed light → dark → light. Desktop theme
  preferences were not changed. The system's initial light palette was detected.
- All three tabs, PDF chooser, and enabled/disabled checked/unchecked states were
  visually inspected at 100% and 150% scaling. At 940×680 there was no horizontal
  workspace overflow. Screenshots and probe logs are in ignored `artifacts/theme/`.
- The rebuilt Linux bundle passed an empty-PATH launch opening an isolated copy
  of a saved project. It replaces the bundle used by the checkout launcher.
- Windows/macOS were not tested. Appearance uses their existing Qt platform
  integration; this Linux verification does not qualify those integrations.

Relative to the immediately preceding follow-up snapshot, production changes are
**+9 / −56 (net −47)**, including the removed SVG and packaging edit; tests are
**+44 / −0**. Native styling replaces both the fixed colors and custom checkbox
rendering, without adding a theme manager. Earlier evidence below is historical.

## Follow-up fixes and capture feasibility — 2026-09-25

Compared with the existing uncommitted refinement at the start of this follow-up,
not with repository HEAD:

- Host-access baseline: **75 passed, 4 audio-device tests deselected, 20.15 s**.
  The sandboxed baseline stalled during Qt/audio initialization and was interrupted.
- After changes: **96 passed, 24.32 s**, including all four real audio-device tests.
  Focused delivery/runtime/version/workflow verification passed (51 tests); a
  subsequent PDF/UI/media run passed 32 tests before final indicator coverage.
- Subprocess output now normalizes LF, CRLF and CR to LF at the text boundary,
  decodes UTF-8 and replaces malformed bytes. Tests cover those inputs as well as
  output draining, failure reporting and cancellation.
- Common delivery guidance reaches every synthesis passage in Prepared, Quick and
  Realtime. Tests preserve slide overrides, the existing 300-character bound,
  unsupported Base controls, Quick defaults and stale-audio detection after the
  instruction change. These tests do not establish an audible improvement.
- PDF import now destroys its Qt document before staging moves or cleanup; export
  also guarantees destruction on every exit. Regression tests retain Python
  references deliberately and verify native objects are released on success,
  cancellation, invalid PDFs, unsupported page counts and rendering failure.
- Recording selection remains visible above the tabs at 940×680 and normal/150%
  scaling, with no horizontal overflow. Checked/unchecked and enabled/disabled
  states were visually inspected. Tests cover label/keyboard toggling, persistence,
  locking during presentation and elapsed recording time independent of narration.
  Destination and saved-file actions are visible near the top of Present & Export.
- Linux CI now installs `libpulse0`. No changes were published and no native CI run
  verified this follow-up. Windows/macOS were not tested locally. QEMU is deferred.
- Five before/after source launches averaged **0.508 / 0.500 s**; an 80-slide timing
  update averaged **0.04814 / 0.04795 ms** over 500 updates (p95 0.04926 / 0.04953 ms).
  These establish no material UI regression, not a synthesis-speed improvement.

On the host's Plasma/Wayland session, Qt `QScreenCapture` obtained frames after
system source selection. A first `QMediaRecorder` probe failed to initialize the
selected H.264 NVENC encoder for 10-bit capture input. A second standalone probe
used Qt frames with AutoTalk's existing PyAV/libx264 software encoder and produced
an 8.1-second, 1920×1080 H.264 video. Independent decoding verified 140 frames with
strictly increasing timestamps from 0 to 8.1 s. Finalization took 28.83 ms;
conversion/encoding callbacks averaged 19.17 ms and peaked at 152.60 ms. This
demonstrates a video path, not production readiness; encoding must leave the GUI
thread. Probe sources were 1920×1080 and 1920×1200 respectively, so these are not a
controlled encoder comparison or an aspect-ratio acceptance test.

The screen probe contains **no audio**. A separate PulseAudio-library probe used
an isolated temporary stereo sink and a generated tone: 144,000 frames captured
at 48 kHz in 3.032 s, with matching left/right RMS of 2040.98. Reported capture
latency ranged from 0 to 8,994 microseconds. The sink was removed afterward; no
default routing changed and no microphone speech was recorded. This verifies a
desktop-monitor input without requiring an external audio executable in production.
Desktop/microphone mixing, synchronization,
interruption recovery and performance during active Qwen generation remain open.
Qt exposed two microphones but no desktop monitor input. PyAV's installed input
formats include ALSA/X11, not PulseAudio/PipeWire. The user's existing speech
session held approximately 6.3 GiB of the 8 GiB GPU and was left undisturbed. The
comparison attempt stopped at the normal exclusive GPU lease; no
new sampling or reference-voice synthesis experiments ran. No claims are made
about steady delivery or improved startup latency from this follow-up.

Probe media/measurements are in ignored `artifacts/improvements/capture/`. This
follow-up changes production **+58 / −39 (net +19)** and tests **+186 / −0**.
Production includes the checkbox SVG and packaging specification. CI configuration
adds/removes one line, excluded from production totals. The approved PDF/UI changes
add 20 net lines beyond the previous −1-line follow-up; these implement guaranteed
native resource cleanup, shared checkbox styling, visibility and status. No
production screen-capture implementation has been added. The Linux package was
rebuilt and passed both empty-PATH launch and isolated-project-opening smoke tests;
the new checkbox SVG is included. The earlier measurements below remain historical
evidence. The normal checkout launcher receives this verified bundle; an already
running AutoTalk window needs a restart to use the new code.

---

Recorded 2026-09-25, against baseline `6199c01`. All tests and measurements below
were run on this Linux host. Windows/macOS adapters and packaging are preserved
but were not tested, built or qualified in this pass.

## Architectural result

Script acceptance now belongs to each slide. Language changes create/select
versions instead of relabeling text. The existing speech worker has one
application owner with bounded leases across operations. Model loading overlaps
Codex planning; the first plan contains the opening narration. Playback and
both direct/captured export consume one shared mix. Human-readable timing no
longer hashes or opens the whole deck on every audio tick. No additional service,
parallel player, or second persisted readiness authority was introduced.

Growth implements the approved UI workspaces, ownership policy, direct export,
recovery, and provenance/regression boundaries. Existing per-operation speech
ownership, duplicated playback mixing, version-wide script stamping, hidden
Generate audio control, and obsolete setup action were removed/replaced. The
legacy recording reader remains inside the same encoder to recover existing
sessions; it is not a second export implementation.

## Linux automated and end-to-end checks

- **79 tests passed in 26.99 seconds** in the final Linux suite, including real
  system-output tests. Baseline: 52 tests. Test preferences are isolated from the
  user's settings. A sandboxed attempt could not access host audio and was stopped;
  the complete suite was rerun with host audio access, with no skips.
- Tests cover partial context revisions, manual acceptance, legacy v1/v2 migration,
  translation drafts preserving originals, exact accepted design-reference reuse,
  grouped text boundaries, stale priority artifacts, adaptive buffering, model
  lease reuse/idle expiry, initiating-error preservation during parallel startup,
  descriptor-only timing updates, preservation of the current stream while the
  next slide is written, accepted-slide progress, stereo mix/resampling, direct
  MP4/WAV/M4A, cancelled export recovery, discovery, and finish/save-later on close.
  Existing system output, fullscreen/continue, modes, languages and rate tests
  remain enabled; no native-platform tests were added for Windows/macOS.
- A real GUI Realtime run used signed-in Codex, the managed Linux 1.7B CustomVoice
  model, a two-slide German deck, fullscreen playback routed to an isolated
  PipeWire stereo output, and actual-performance MP4 recording. It completed
  without workflow errors. First playback: **43.03 s**, generated audio **35.4 s**
  for a 30 s target, final MP4 saved by **84.15 s**. Realtime duration is approximate.
  Stage timings: model files **2.99 s**, model load **35.55 s**, overlapping Codex
  planning **14.33 s**, first audio **41.14 s**. The temporary output was removed.
- A separate cold-preview → warm-preview → Realtime sequence reused worker PID
  1571777 throughout. Cold preview took **41.47 s** including setup/load; warm
  preview first audio **0.117 s**, total **2.18 s**. Warm Realtime first audio
  **15.48 s**, planning **14.95 s**, complete operation **34.78 s**, generated talk
  **34.12 s**. These are individual samples, not guaranteed latency bounds or
  controlled comparisons to the different 0.2 narration.
- Source application launch (import through first Qt event after show, offscreen,
  five runs each) averaged **0.495 s** at baseline and **0.447 s** after refinement.
  These are source/Qt startup measurements, separate from model loading and
  packaged launch. No speech runtime starts in the window constructor.
- An 80-slide timing-display probe with approximately 1,300 characters per slide
  averaged **0.049 ms** per update (500 samples, p95 **0.051 ms**), versus the
  baseline **14.4–14.7 ms**. Regression tests prohibit project readiness/key/file
  access in that label update. This measures GUI work, not physical output latency.
- Minimum-size 940×680 workspaces were rendered at normal and 150% scaling.
  Scrollable content exposes configuration, script controls and export/recovery;
  the 150% probe found no horizontal overflow. Screenshots were inspected.
- An **80-slide / 20-minute synthetic prepared talk** exported to 1080p MP4 with
  stereo audio in **240.53 s**, without an audio device or real-time playback.
  The result contains **36,000 video frames**, exactly **1,200.0 s**, and all 80
  journal slide boundaries match their expected PCM offsets. Peak RSS reached
  about **340 MiB**; sampled high-water memory after encoder warmup ranged from
  324–340 MiB. This exercises long mixing/encoding, not long Qwen generation.

Local reproducible probes, logs, screenshots, generated audio and video are in
ignored `artifacts/refinement/`. No physical-speaker listening or microphone
recording was performed. The original PDF, not the editor preview, supplies new
video frames. Imported audio is normalized to stereo 48 kHz PCM; this does not
claim lossless retention of arbitrary source formats or sample rates.

## Matched speech samples and final workflow

Three repeats used identical German text, Ryan, delivery instructions, sampling,
and the same loaded model. The old segmentation required four sentence requests;
grouped synthesis required one. Sentence-by-sentence durations were **13.12,
12.88, 14.48 s** (99.4–111.8 words/minute); grouped durations were **16.00,
12.08, 13.28 s** (90.0–119.2 words/minute). These short samples **do not demonstrate
reduced pace variation**; grouping removes application-created request boundaries,
but the model still varies. Listen to `artifacts/refinement/continuity/*.wav` before
accepting the audible result. Do not call finding 5 fully acoustically validated.

A further warm real Realtime workflow with the consolidated planning/translation
prompt produced first audio at **16.42 s**, completed in **41.07 s**, and reused
the existing model. Its **46.36 s** result overshot the 30 s target; this reinforces
that Realtime duration is approximate. Prepared fitting and Quick's optional fit/
require policies remain available when matching duration matters.

The Linux 0.3.0 standalone package was rebuilt and smoke-tested with an empty
executable search path, both empty and opening the newly generated project.
The checkout launcher selects that bundle. The package includes the updated
README, roadmap, verification record, and checksum. No Windows/macOS build ran.

## Remaining qualification

Grouping reduces independently synthesized boundaries; it does not establish
stable expression across every slide/language. Matched speech samples and their
measurements are retained for listening review. Natural-language precedence is
explicit in the instruction, not a guarantee that a model resolves every conflict.
Own-voice similarity, all-language/dialect/style adherence, and sustained Qwen
inference through a full conference talk remain unverified. No latency guarantee
is made. Clean-system installation and signed/public native releases remain
separate acceptance work. Windows/macOS were deliberately not tested.

## Refinement change accounting

Relative to `6199c01`: production **+725 / −282 (net +443)**;
tests **+432 / −18 (net +414)**. Production includes application and native
build specification; documentation and project metadata are excluded. Growth
implements the approved refinement requirements described above, principally
recoverable/direct export and the revised UI. Existing responsibilities were
extended/consolidated rather than introducing a parallel service or player.

---

# AutoTalk 0.2 verification

Recorded on 2026-09-25 on the same Debian/NVIDIA laptop as the original prototype.
These are functional observations, not guarantees for every GPU, voice, or language.

## Current results

- Linux left-only playback regression: a real PipeWire stereo monitor measured
  left/right RMS levels of 3299.36/0 before the correction and 3299.36/3299.36
  afterward. The shared playback transport now declares an explicit mono channel
  layout instead of only a channel count. Preview and presentation share this
  output boundary; system balance and stored audio are unchanged. The isolated
  output was removed after testing; physical speaker listening was not performed.
  The updated suite passed all 52 tests in 22.13 seconds. This correction replaces
  one production line (+1/-1, zero net growth) and adds 65 regression-test lines.
- **51 tests passed locally**, including real audio-output tests. The original
  baseline was 21 tests in 14.67 seconds; the expanded suite took 20.78 seconds.
- A complete Realtime run used the signed-in Codex app-server, a two-slide German
  deck, managed Qwen3-TTS 1.7B CustomVoice, fullscreen playback, and MP4 export.
  Playback started about 67.4 seconds after Start while preparation was still
  active. The generated talk measured 24.52 seconds; its exported H.264/AAC video
  measured 24.533 seconds and contained 736 frames. Export finished by 96 seconds
  after Start. No workflow errors were reported. This run used cached downloads.
- Managed Linux synthesis succeeded for **CustomVoice, Base, and VoiceDesign**.
  Base used a synthetic reference; this does not establish similarity to a human.
  The automatic VoiceDesign-to-Base reuse path also completed a two-slide talk
  using one saved identity, with 7.0 seconds of audio in a 100.3-second operation
  including two model startups.
- A fresh compiler-cache test with an empty executable search path generated
  streamed speech using private Zig wrappers. It required no system C compiler,
  CUDA toolkit command, FFmpeg command, or SoX command.
- Real output playback advanced slides from consumed audio. Escape paused and
  Continue preserved position. Tests cover mixed-language validity, independent
  language versions, legacy project migration, cancellation, clips and background
  normalization, recording policies, and exports at all three selectable rates.
- Realtime writing-ahead tests verify that the next batch is being written while
  the current batch synthesizes. Quick-mode tests cover all three timing policies,
  including refusing automatic presentation when a required match is unmet.
- PipeWire/PulseAudio routing was exercised through a temporary virtual output.
  A system move succeeded, audio continued, and the selected destination survived
  stream recreation. The test output was removed afterward. Qt's default PipeWire
  stream flags prevented this initially; AutoTalk now leaves node selection and
  reconnection to the system and identifies the stream as AutoTalk.
- The Linux standalone bundle launches, opens a migrated/current project, and
  shuts down cleanly. Qt screenshots were inspected for the new configuration,
  voice, delivery, and presentation controls.

Local qualification logs, example projects, screenshots, and MP4 output are under
`artifacts/qualification/`; these generated files are not committed.

## Speech measurements

The Linux runtime uses vLLM/vLLM-Omni 0.28.0 with pinned dependencies and private
Python 3.12.14. The comparison baseline used official Qwen/PyTorch 2.9.1. Tests
ran on an RTX 2000 Ada laptop GPU with 8 GB VRAM and driver 610.57.04.

| Short functional sample | First audio | Total generation | Audio duration |
| --- | ---: | ---: | ---: |
| 1.7B official PyTorch preview | Complete waveform only | 4.35 s | 4.88 s |
| 1.7B vLLM first request after startup | 7.94 s | 8.67 s | 3.76 s |
| 1.7B vLLM subsequent request | 0.14 s | 3.00 s | 7.04 s |
| 1.7B vLLM empty-PATH compiler test | 7.07 s | 7.77 s | 3.84 s |

These runs are nondeterministic and not a controlled throughput comparison.
They demonstrate incremental output and functioning private compilation.
Server processes occupied approximately 6–6.3 GiB on the test GPU. Model startup
is separate from the timings in this table: the managed short-preview operations
including startup took 75.1 s (CustomVoice), 50.5 s (Base), and 50.9 s (VoiceDesign).
The application separately reports runtime setup, model files, model loading,
Codex work, synthesis, and measured audio duration.

## Platforms and remaining qualification

Windows CUDA and Apple Silicon MLX adapters, private installation paths, native
binary manifests, microphone permission handling, and native packaging are
implemented. Windows explicitly selects CUDA 12.8 PyTorch wheels. macOS packaging
includes microphone usage metadata and signing/notarization hooks. The GitHub
Actions matrix replaces the original Linux-only workflow.

**No Windows/macOS native build, GPU inference, microphone capture, or system
routing test was run from this Linux workspace.** CI definitions alone are not
proof that those platforms work. Native qualification, signing/notarization,
clean-machine installation, and public release publication remain outstanding.
Microphone similarity and subjective quality across all languages, dialects,
expressive cues, and long talks also remain unverified. Interrupted slide audio
is regenerated; only completed slides are reused. Automatic cache cleanup is
not implemented.

## Change accounting

Relative to commit `91c9827`, application/build production code adds 2,720 lines
and removes 406 (net +2,314). Tests add 396 and remove 15 (net +381). Counts exclude
documentation, dependency/model manifests, and CI configuration; the native build
specification is counted as production code. Growth implements the approved new
workflows, model adapters, settings, recording, and platform support. The separate
QMediaPlayer playback path and obsolete speech dependency file were removed.
Project state, artifact validity, and the presentation audio clock each retain
one owner.

The original prototype's historical measurements follow; they used 0.6B models
and must not be read as measurements of the new 1.7B runtime.

---

# Original 0.1 prototype verification

Recorded on 2026-09-25. These results describe the tested machine and examples,
not guarantees for every laptop, language, document, or voice.

## Environment

- Debian forky/sid, x86_64.
- NVIDIA RTX 2000 Ada Generation Laptop GPU, 8 GB VRAM; driver 610.57.04.
- Managed Python 3.12.14; PySide6 6.11.2.
- Qwen-TTS 0.1.1, PyTorch 2.9.1, CUDA runtime libraries supplied by Python wheels.
- Both the existing Codex 0.154.0 and automatically downloaded Codex 0.157.0
  completed the app-server initialization/account handshake.

## Exercised behavior

- PDF rendering and text extraction with Qt PDF.
- Existing ChatGPT subscription sign-in through app-server, without an API key.
- Structured narration for a real two-page test deck, with German selected.
- Conference URL reading and editable scope generation using the FOSDEM 2026
  About page and related official pages. Sources and edition were retained.
- Automatic private speech runtime provisioning on the development machine,
  including Python and GPU dependencies; no system Python changes.
- Built-in speech with Qwen3-TTS CustomVoice and reference-conditioned speech
  with Qwen3-TTS Base, using a synthetic reference rather than a person's voice.
- Pinned model file integrity verification against upstream file hashes.
- Speech generation with an empty executable search path: no system SoX,
  FFmpeg command, Python executable, or CUDA toolkit command was required.
  Qwen's optional SoX/FlashAttention notices did not prevent synthesis.
- Real duration fitting: a 33.24-second German talk was revised to 23.88 seconds
  for a 24-second target with a 3-second tolerance, in one adjustment pass.
- Standalone bundle startup with an empty executable search path and a fresh
  application-data directory. This proves independence from development tools
  on this host; it is not a clean operating-system distribution test.
- The packaged Qt application opened the prepared project and generated/played
  a German voice preview through its actual UI, with its executable search path
  empty. It used the managed speech runtime and cached model files.
- Visual inspection of the Qt configuration, narration, voice, and presentation
  pages using rendered screenshots.

## Observed synthesis times

All times exclude model download and initial loading. These are short functional
measurements, not a controlled comparative benchmark; sampling is nondeterministic.

| Operation | Generated duration | Generation time | Peak reserved GPU memory |
| --- | ---: | ---: | ---: |
| Initial built-in English preview | 4.48 s | 4.20 s | Not recorded |
| German slide 1 after fitting, including 0.6 s pause | 9.96 s | 7.50 s | 2,418 MiB |
| German slide 2 after fitting | 13.92 s | 10.29 s | 2,748 MiB |
| Base voice-clone preview after integrity checks | 4.16 s | 3.25 s | 2,442 MiB |
| German preview through the packaged GUI | 10.16 s | 8.20 s | 2,490 MiB |

The initial built-in preview is the recorded baseline. Later runs cover different
texts and modes and must not be interpreted as measured speed improvements.

## Automated regression coverage

All 21 tests passed locally. Static checks and `git diff --check` also passed.
The configured GitHub Actions workflow has not been run remotely.

The suite covers portable project reopening, corruption detection, stale audio
after narration/language/voice/pause changes, source PDF integrity, project path
containment, complete narration output, language propagation, cancellation,
bounded timing adjustment, app-server event ordering, Qt editing/persistence,
media-end slide advancement, actual media pause/resume, and fullscreen exit.

Run the suite with `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`.

## Change accounting

The initial repository contained a README only. This implementation adds 1,859
production-code lines (application, launcher, and build tools) and 317 test lines,
with no production or test deletions. A further 269 lines contain dependency/model
manifests and project/CI configuration. Production growth implements the new
application; there was no existing implementation to reduce or replace.

## Not yet established

- Installation and speech generation on a separate clean Linux distribution.
- A fresh interactive ChatGPT browser login; an existing login was used here.
- Microphone capture and similarity to the user's own voice. The recording UI
  exists, but no microphone was recorded during automated verification.
- Subjective pronunciation/quality across every supported language or technical
  subject. The user should review their voice preview and narration.
- Long conference decks, multi-hour preparation, CPU/NPU inference, and other GPU
  vendors. The first prototype targets NVIDIA GPU inference only.
- General availability of a public binary release. The local build is provided
  for evaluation; licensing and distribution qualification remain separate work.


## Clickable-prototype desktop refinement (2026-09-26)

The old tabs were replaced by the approved desktop hierarchy: menu bar, compact
three-column editor/inspector, Quick and presenter views, sectioned settings,
voice library and saved/unfinished recordings. See [design](design/UI-REDESIGN.md).

- Linux native Qt regression suite: **118 passed in 28.79 s**. The final progress/recording-label adjustment also passed
  all **61 refinement/UI tests in 9.34 s**. Tests include dialog rollback,
  command locks, inclusion, per-slide regeneration without changing other work,
  pause/continue, voice selection, capture cancellation before permission,
  saved-output discovery, desktop aspect ratio/timing and microphone mixing.
- Visual checks use native Breeze with a landscape reference deck: editor, Quick,
  presenter, five Talk settings sections, Preferences, voice library, exports and
  seven opened menus. Minimum-size light/dark and 150% scaling are checked.
- Five native source startup samples: 0.711, 0.656, 0.618, 0.682, 0.683 seconds.
  Median **0.682 s**, mean **0.670 s**; pre-redesign median was **0.595 s**.
  This is cached window startup, not model loading; the added UI costs about 87 ms
  in this sample and is not a startup-speed improvement.
- Fresh real Codex → Qwen3-TTS 1.7B → Realtime fullscreen → MP4 completed without
  errors. First playback **40.32 s**, model load **34.70 s**, opening planning
  **16.38 s**, later narration **6.65 s**, total speech generation **11.67 s**,
  audio produced **27.32 s**. Planning/model loading overlap. The 24-second target
  is approximate in Realtime. The completed video exists and the project is prepared.
- That live check exposed an unset per-slide duration being sent as zero to Codex.
  Unset timing now remains null, and the output schema requires nonblank narration
  and a positive duration. Runtime validation remains in place.
- Real desktop capture on an isolated Linux X11 display: **6.271 seconds**, no
  errors, maximum UI timer gap **121 ms** with a nominal 100 ms timer. Export kept
  4:3 screen content letterboxed at 1080p. Real PulseAudio monitor capture recorded
  144,000 stereo frames in 3 seconds, identical left/right RMS **2040.98** from a
  private test sink. The system's normal output routing was not changed.
- Synthetic screen and separate microphone tracks verify frame timing, aspect ratio,
  duration and summed audio through the production exporter. This does not establish
  physical microphone behavior or subjective audio quality.
- Production diff from `7bb41a3`: **+1,244 / −511 = +733 lines**. Tests:
  **+344 / −12 = +332 lines**. Growth covers the UI replacement and Linux capture
  together, within their combined previously scoped estimates. Existing tab
  construction is deleted; capture reuses session metadata and the exporter.

- Final native Wayland acceptance with user-granted Plasma sharing succeeded:
  **6.102 seconds**, no reported errors, maximum UI timer gap **199 ms**.
  The exported 1080p H.264/AAC file contains changing screen content and the
  expected timed frame count. The application stopped capture and saved normally.

Qualification still open: Wayland permission revocation during capture,
physical microphone input, simultaneous long screen/demo recording under Qwen
load, cross-platform native testing and subjective voice continuity. Linux-only
local tests do not qualify Windows/macOS. The UI implementation does not claim
completion of the roadmap's separate acoustic-generator sampling/Base comparison.

Structured-output constraints were checked against the [official OpenAI schema
guide](https://developers.openai.com/api/docs/guides/structured-outputs). Linux
screen selection follows [Qt's QScreenCapture contract](https://doc.qt.io/qt-6/qscreencapture.html).

The final Linux package passed a prepared-project launch with empty PATH. All
27 audited Qt libraries/plugins matched their expected sources; 17 mapped Qt
libraries came from the bundle. `libpulse-simple.so.0` is included through normal
PyInstaller ctypes discovery. The native Plasma PDF chooser again navigated into
a child directory and displayed its PDF. System license notices are preserved.


## Latest ordinary-user review fixes (2026-09-26)

Baseline committed as `bee3abc` before this pass. All 12 latest findings have an
individual acceptance entry in [USABILITY.md](design/USABILITY.md).

- Full Linux suite: **148 passed in 45.44 s**. After simplifying saved-voice loading
  and disposing enlarged-slide dialogs, all **89 UI/usability/refinement tests
  passed in 14.17 s**. Coverage includes the one-button welcome state, current-text
  versus human approval, saved-voice transaction rollback/progress ownership,
  separate display/audio/capture pages, fullscreen mouse navigation, skipped-end
  timing, automatic export preserving completion, and pending-translation labels.
- Native Wayland/Breeze walkthrough: **40 captured states**, using isolated settings
  and copies of talks. Also inspected a landscape deck at 940×680 with light/dark
  palettes, all eight Talk settings pages, Preferences, and saved recordings.
  Programmatic menu popups emitted Wayland input-grab warnings in the landscape
  harness; their widget captures alone do not verify compositor input ownership.
- Real, previously generated narration was played through the native presentation
  controls, paused, resumed and ended. The saved **1.300-second H.264/AAC MP4**
  decoded successfully: **39 video frames**, **30,720 audio samples**, **stereo**.
  This was deliberately an early end, not a full-length recording or speech test.
- Latest production diff: **+106 / −107 = −1 line**. Test diff:
  **+123 / −26 = +97 lines**. Removing duplicate dialogs/layout and library passes
  absorbs the shared fullscreen actions and enlarged-slide window. No extra
  persisted state, workflow flags, services or timers were introduced.

These are automated checks and a visual review, not a study with recruited users.
New text/preview-wait states used controlled fixtures; no new Codex/Qwen generation,
fresh login, microphone recording or Wayland sharing permission was exercised in
this pass. Earlier platform/capture/voice-quality qualifications remain open.
The existing performance measurements remain the baseline; no speed improvement
is claimed by this UI change.

The rebuilt Linux package passed a prepared-project launch with empty PATH. All
27 audited Qt libraries/plugins match their intended sources; 17 mapped Qt
libraries came from the bundle. The checkout launcher uses the rebuilt package.
System license notices were carried forward; existing user processes were left running.


## Fixed start actions and preview state (2026-09-26)

The start/editing interaction now follows the fixed user contract: Prepared uses
Prepare and start, Quick/Realtime use Start, and existing narration requires no
approval. The context-stamp gate and changing next-step dispatcher are removed;
legacy stamp fields are discarded on import without discarding audio. Audio reuse
still checks its actual narration, voice and synthesis inputs. Explicitly configured
Quick "Require timing match" remains enforced at presentation entry, including
repeated starts; it does not change the start caption or disable the command.

Linux verification for this pass:

- 265 tests passed in 39.04 s, covering existing regressions and 25 additional
  start/control cases. The previously unqualified stereo-loopback test in
  test_linux_audio.py ran separately after aligning its preview-completion
  expectation with the corrected stopped state: **1 passed in 2.01 s**, with the
  original left/right amplitude and equality checks retained. Total: **266** tests
  passed across the suite and isolated stereo run.
- 90 focused interaction/playback tests passed in 14.66 s during iteration,
  including actual audio preview stop/natural completion and fullscreen playback.
- Generation tests use controlled Codex/Qwen substitutes through real worker,
  persistence and UI boundaries. No new real-model generation is claimed here.
- Native Wayland/Breeze walkthrough checked fixed Prepared/Realtime/Quick labels,
  preview Play → Stop → Play, rewrite confirmation and matching model display names.
  Screenshots and logs are under artifacts/start-interaction-fix.
- Tests preserve independent text/audio creation, old audio during unsuccessful
  replacement, manual and translated wording, saved-project reuse, cancellation,
  start-after-operation behavior, and Save/Ctrl+S persistence. No autosave was added.

Changes are reductions of existing state/dispatch policy, not a new workflow layer.
Text approval tests were replaced with preservation and startup tests for the
requested behavior. Windows/macOS and new model/GPU acceptance were not run.

After the final shared menu/button caption change, all **91** affected UI, editor,
start and usability tests passed in **17.16 s**. Production changes relative to
this pass’s starting tree are **+76 / −135 (net -59)**; tests are **+242 / −125 (net +117)**.

The rebuilt standalone Linux executable passed its installed Wayland launch with
an empty PATH and isolated preferences. All 27 audited Qt/Breeze libraries/plugins
matched their expected source files; all 17 mapped Qt libraries came from the
bundle. The previous executable was retained under artifacts/start-interaction-fix.
No user talk or running application was modified. Build evidence and checksums are
in artifacts/start-interaction-fix/package-result.json and bundle-audit.log.
