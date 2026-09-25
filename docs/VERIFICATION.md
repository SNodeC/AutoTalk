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
