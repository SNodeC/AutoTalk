# Prototype verification

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
