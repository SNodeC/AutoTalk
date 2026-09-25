# 0.3 refinement verification — Linux only

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
