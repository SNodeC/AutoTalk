# AutoTalk

**Turn PDF slides into a timed, spoken presentation.**

AutoTalk is a Python/PySide6 desktop application. Codex app-server writes narration
using your ChatGPT sign-in; Qwen3-TTS **1.7B** generates speech on your local GPU.
The executable is `autotalk` (`autotalk.exe` on Windows).

The expanded 0.2 prototype implements the [agreed feature list](docs/ROADMAP.md).
Read [verification results and platform limitations](docs/VERIFICATION.md) before
relying on it for a conference.

## Start

Extract the native package and open `autotalk`, `autotalk.exe`, or `AutoTalk.app`.
Keep the accompanying files together. In this checkout, `./autotalk` launches the
local Linux bundle at `dist/autotalk/autotalk`.

| Platform | Speech backend | Qualification |
| --- | --- | --- |
| Linux x86_64, NVIDIA GPU | vLLM-Omni streaming | Tested locally on an RTX 2000 Ada laptop, 8 GB VRAM |
| Windows 11 x64, NVIDIA GPU | Qwen/PyTorch CUDA, sentence chunks | Implemented; native build and GPU testing pending |
| macOS 14+, Apple Silicon | MLX Audio, Metal streaming | Implemented; native build and GPU testing pending |

The application packages Python, Qt, and audio/video libraries. Speech setup
privately downloads its Python runtime, pinned dependencies, models, and any
required compiler. Users do not install Python, a CUDA toolkit, or speech servers.
A supported GPU with a working compatible OS driver is required for synthesis.
CPU/NPU inference and Intel Macs are outside this prototype. Prepared playback
does not require the speech runtime or a GPU capable of synthesis.

First setup requires internet access and several GB of downloads. Allow roughly
40 GB of free space for the Linux runtime, model, and installation caches; more
for additional models and projects. Downloads are cached and verified. Cancelling
retains completed slide audio; an interrupted slide is regenerated on retry.
Runtime/model data stays in the user's application-data directory.

## Three modes

1. **Prepared:** import a PDF, choose language, duration, conference context and
   voice, create and review narration, then generate audio. Optionally fit its
   measured duration with up to three revision passes. Start fullscreen explicitly.
2. **Quick:** choose the PDF, language, and duration, then Start. AutoTalk uses Ryan,
   professional delivery, default Codex settings, and no conference context.
   The default policy attempts duration fitting, then presents even if a visible
   mismatch remains. Alternatives generate once or require a timing match.
3. **Realtime:** prepare the opening audio buffer and start presenting while later
   audio is generated. Choose a complete script first, or a whole-deck outline
   followed by two-slide writing batches overlapping synthesis. Buffer underruns
   wait visibly. Final duration remains approximate until preparation finishes.

First-time downloads and model loading precede speech in every mode. Streaming
reduces waiting for audio; it does not guarantee uninterrupted playback on every GPU.

## Configure the talk

- Import an unencrypted PDF of 1–80 slides into a new project directory.
- Select duration in minutes, tolerance, inter-slide pause, audience, and objective.
- Enter conference scope directly, read it from a URL, or combine both. Review
  the editable extraction and its source links. JavaScript-only and authenticated
  websites may need a manually supplied explanation.
- Use **Connect ChatGPT** for subscription sign-in and model discovery. The model
  selector lists account-available models accepting slide images; reasoning choices
  come from the selected model. Subscription limits apply. No paid API fallback is
  used. Slide images, extracted text, and supplied context are sent to Codex;
  reference recordings remain local.
- Select English, German, French, Spanish, Italian, Portuguese, Russian, Chinese,
  Japanese, or Korean. Add language versions to retain independent scripts/audio.
  `[German]` and similar paragraph markers allow mixed passages. Choose mixed
  passages, one language per slide, or a single language per version in settings.

## Voices and delivery

**Predefined** voices use CustomVoice: Ryan, Aiden, Vivian, Serena, Uncle_Fu, Dylan,
Eric, Ono_Anna, and Sohee. Preview in the selected talk language.

**My voice** uses Base with a clean 3–60 second WAV recording. Record directly
(up to 30 seconds), or import a recording. Its exact transcript is recommended;
without one, conditioning uses speaker identity alone. No fine-tuning is needed.
Save named voices for reuse; project copies retain their own references, organized
by language, with a shared reference available for cross-language use.

**Design a voice** uses VoiceDesign for a preview/reference. Save an accepted voice
or prepare the talk to freeze one reference and reuse it through Base. This avoids
independently redesigning the speaker on every slide. Base inherits the reference's
identity/delivery and does not accept CustomVoice/VoiceDesign vocal instructions.

Choose Professional, Conversational, Energetic, Calm and understated, Lightly
humorous, Academic, Storytelling, or Inspirational. Customize acoustic attributes,
voice-design age, persona, gradual progression, and per-slide directions. Save
named delivery presets. Unsupported controls are disabled. Dialect and expressive
cues are model requests requiring preview, not guaranteed effects or sound tags.
Use imported clips for precisely controlled singing, music, or nonverbal effects.

Advanced settings expose sampling temperature, top-k, top-p, repetition penalty,
and an output token limit. They are not reasoning efforts or guaranteed quality
levels. Synthesis stays at native 24 kHz; export resampling and AAC bitrate are
separate compatibility/encoding choices.

## Present, route audio, and record

Choose the fullscreen display. Use **System audio settings** and **Test audio**
to select AutoTalk's output through Plasma, Windows Sound settings, or macOS Sound.
The operating system owns routing; projects do not store audio-device bindings.

Space pauses/resumes; arrows navigate. **Esc pauses and leaves fullscreen**, keeping
the slide and position. Use **Continue presentation**, **Restart from beginning**,
or **Stop**. Previews, narration, imported clips, and background tracks share one
PCM transport. Slide advancement follows consumed audio rather than word estimates.

Attach clips before/after slides and adjust their gain. Add a background track,
gain, and looping. Fixed clips and pauses count toward duration fitting.

Enable **Record presentation as a video** under Delivery & recording. Export uses
AutoTalk's own audio mix and slide timeline, without recording other desktop sound.
MP4 output is 1080p/30 fps with AAC at 24, 44.1, or 48 kHz. Recording policies retain
fullscreen pauses only (default), all elapsed waiting, or content only. Configured
filenames receive a session suffix to preserve earlier recordings. Export runs
after playback; **Export recorded session** can recover a saved session after a
cancelled export or interrupted application session.

## Projects and persistence

Save with Ctrl+S and copy the entire project folder to move a talk:

- `talk.autotalk.json`: versioned configuration, language versions, and artifact metadata.
- `slides.pdf`, `slides/`: source PDF and rendered previews.
- `voice/<language>/`: reference snapshots.
- `audio/<version>/<language>/`: generated speech, keyed by effective synthesis inputs.
- `media/`: normalized imported clips/background tracks.
- `recordings/<session>/`: recoverable PCM, slide images, timeline, and exported video.

Version-1 projects migrate on save with an untouched `.v1-backup.json`. Verified
legacy audio remains playable with its original model provenance. Regeneration
uses 1.7B. Changed inputs invalidate affected audio; damaged files are detected on
reopening. Old artifacts are retained; automatic disk cleanup is not implemented.

## Development and native builds

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python tools/build.py
```

On Windows use `.venv\Scripts\python.exe`; build on each target OS. The native CI
matrix builds Linux archives, Windows ZIP packages, and Apple Silicon DMGs.
Tests marked `audio_device` need a working physical/virtual audio output and run
locally; remaining tests run in the native CI matrix. Signing hooks accept
`AUTOTALK_SIGN_IDENTITY` / `AUTOTALK_NOTARY_PROFILE` on macOS and
`AUTOTALK_SIGN_CERT` / `AUTOTALK_TIMESTAMP_URL` on Windows.

`project.py` owns configuration and artifact validity. `services.py` operates on
job snapshots and publishes validated results to Qt. `runtime.py` owns managed
processes; `speech_worker.py` adapts the three native synthesis backends.
`playback.py` owns presentation position and consumed PCM; `media.py` records and
exports that same stream. The old separate media-player path has been removed.

See [third-party notices](THIRD_PARTY.md). This is a development build; public
release licensing, native signing, and broader hardware qualification remain open.
