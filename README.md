# AutoTalk

**Turn PDF slides into a timed, spoken presentation.**

AutoTalk is a Python/PySide6 desktop application. Codex app-server writes narration
using your ChatGPT sign-in; Qwen3-TTS **1.7B** generates speech on your local GPU.
The executable is `autotalk` (`autotalk.exe` on Windows).

Read the [UI user guide](docs/USER_GUIDE.md) for step-by-step Prepared, Quick and
Realtime workflows, editing and previewing individual slides, voice selection,
presentation controls, recording, export and GPU-model management.

The [UI interaction inventory](docs/design/UI_INVENTORY.md) lists current controls
by functional group and UI location, with user-importance ratings and availability.
The [revised UX placement proposal](docs/design/UX_PLACEMENT_PROPOSAL.md) records
the proposed interaction structure and access criteria; it is not yet implemented.

The 0.3 refinement prototype follows the [agreed feature and refinement plan](docs/ROADMAP.md), which distinguishes implemented work from remaining qualification.
Read [verification results and platform limitations](docs/VERIFICATION.md) before
relying on it for a conference.

## Start

Extract the native package and open `autotalk`, `autotalk.exe`, or `AutoTalk.app`.
Keep the accompanying files together. In this checkout, `./autotalk` launches the
local Linux bundle at `dist/autotalk/autotalk`.

AutoTalk follows the system light/dark appearance through Qt, including theme
changes while it is open. Controls, dialogs, and checkboxes use the system palette.
The current Linux bundle also includes this build machine's Qt 6.10.2 (with the
upstream Multimedia callback-lifetime fix), Plasma
integration, and Breeze widget style. Plasma selects the appearance; AutoTalk
does not force Breeze. Other styles require a compatible included style plugin.

| Platform | Speech backend | Qualification |
| --- | --- | --- |
| Linux x86_64, NVIDIA GPU | vLLM-Omni streaming | Tested locally on an RTX 2000 Ada laptop, 8 GB VRAM |
| Windows 11 x64, NVIDIA GPU | Qwen/PyTorch CUDA, grouped passages | Implemented; native build and GPU testing pending |
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
2. **Quick:** choose the PDF, language, and duration, then Start. AutoTalk uses the resolved voice,
   delivery and Codex settings, with no conference setup.
   The default generates once and starts, with the measured duration shown.
   Alternatives attempt duration fitting or require a timing match before playback.
3. **Realtime:** prepare the opening audio buffer and start presenting while later
   audio is generated. By default one request plans the deck and writes the first
   slide while the speech model loads; subsequent slides are written ahead of
   synthesis. A complete-script-first alternative remains available. Consistency
   first groups sentences and adapts the buffer to observed production speed;
   Earliest playback prioritizes a short first speech unit. Buffer underruns wait
   visibly. Final duration remains approximate until preparation finishes.

First-time downloads and model loading precede newly generated speech. Saved current
audio is reused in every mode. Realtime starts from a sufficient saved opening buffer
without waiting for preparation needed only on later slides. Streaming does not
guarantee uninterrupted playback on every GPU.

The main window retains the prototype's **slide navigator**, **PDF/narration editor**
and **slide inspector**, with system styling. Duration, language/version, voice,
recording and preparation are directly accessible. Three separate settings windows
identify their scope: **Application defaults**, **Talk settings — [title]**, and
**Slide settings — [number]**. They share flat, consistently ordered pages for
voice/language, talk/preparation, presentation/recording, AI/speech engine and
application resources; only applicable pages appear. Existing shortcuts open the
appropriate window and section. There is no in-dialog scope selector.
Slide overrides take precedence over talk settings, then application defaults.
Voice summaries identify **Predefined**, **Own**, **Designed**, or a legacy
**Reference** voice and the source of the effective setting. **From app / From talk**
indicates inheritance; **Use app / Use talk** removes an override.

Application defaults live in application config; talk and slide overrides live in
`talk.autotalk.json`. Changed defaults affect settings still inheriting them.
**Keep these settings for this talk** pins inherited settings and language versions
for portable use. Existing words are retained; only audio whose effective inputs
change needs updating. Prepared, Quick and Realtime use the same resolution rule.

One Save/Cancel covers pending changes across pages and scopes. Account, manual
engine, external audio-routing and explicitly saved library actions are immediate.
Saved-voice audition does not select that candidate. See the
[scoped settings contract](docs/design/SCOPED_SETTINGS_IMPLEMENTATION.md).

**Create talk text** fills missing/translated text without replacing existing words.
**Create talk audio** prepares missing/outdated audio without presenting, once all
included text is ready. **Talk → Rewrite all talk text…** confirms replacement.
These operations apply to the active language version and included slides.
The inspector groups inclusion, after-slide behaviour, Timing, Delivery and
Additional audio. Notes and language passage insertion sit beside the text editor.
Use **Enlarge slide…** for a larger, resizable preview. **File → Recordings & export…**
finds previous results; direct result links appear when a new output is saved.
The preview waveform is calculated from the generated audio.

**Quick** shows duration and language directly. **View → Presenter** shows the
current and next slides, narration, playback timing, and Continue controls. The primary
action is always **Prepare and start** in Prepared mode and **Start** in Quick
and Realtime. It remains available for a loaded talk; there is no text-approval
barrier. Prepared creates all missing content before fullscreen; Realtime can
start with opening audio while later slides prepare. Existing words are preserved,
and current saved audio is reused. Changes to conference scope, target duration,
or Codex choices do not invalidate existing speech by themselves.

In Prepared and Realtime, separate buttons offer **Create slide text / Rewrite
slide text…**, **Create slide audio**, and **Play audio / Stop audio**. Rewriting
calls Codex; audio creation calls Qwen using the displayed words and saves and
previews the new recording. Playback can audition an existing recording even
when edited words require fresh audio for presentation. Failed/cancelled audio
creation retains the previous completed file. Save / Ctrl+S persists narration
edits; starting preparation/presentation and normal closing also save the talk.
Ellipses mark actions that open dialogs, including rewrite confirmation.

Use **End presentation** to return from playback. **Start** resumes interrupted
Realtime preparation using completed work. Escape and
Continue presentation preserve the current playback position. Fullscreen has
visible Previous/Next, Pause/Continue and End controls. Once finished,
**Return to editing** is primary; use **Presentation → Restart from beginning**
to replay. Space cannot restart a finished talk. Ready recordings offer
**Save a copy / another format**; unfinished recordings offer **Save unfinished recording**.

Use **Settings → Speech engine…** (also available from the status bar) to see the
current model and control GPU memory. **Load model now** and **Unload model now**
act immediately without changing the saved automatic settings or stopping prepared
audio. A compatible model is reused; changing model variant or deployment sampling
settings requires loading the selected model.

Automatic settings take effect only when you click **Save**:

- **Load:** when speech is first needed (default), or when starting a presentation.
  Presentation preload runs in the background; prepared audio starts immediately.
  Preparation and voice previews always load a needed model.
- **Unload:** keep until AutoTalk closes (default), at presentation end, after five
  idle minutes, or after each preparation/preview. These rules also apply to a
  manually loaded model. Per-operation unloading waits for the next actual
  preparation/preview, so it does not undo a manual preload.

Pause, leaving fullscreen, and continuing do not end a presentation. Screen
recording keeps the session open until **End presentation and save video**.
Choosing an automatic rule never causes an immediate load or unload; selecting
five idle minutes starts that countdown for an already idle model. **Cancel**
discards unsaved rules but does not undo immediate Load/Unload actions. Loading is
cancellable; unloading waits for safe ownership of the model and retains downloaded
files. GPU policies, Quick timing, and Realtime priority are remembered.
A retained Linux worker uses roughly 6 GiB of GPU memory on the tested machine.

Model loading shows the current stage in the progress bar: runtime setup,
finding/downloading model files, file verification, GPU/engine startup, then ready.
Available measurements are shown as completed files or transferred MiB, without
percentages. On Linux, backend startup also shows checkpoint files per loading pass,
reported weight counts, model memory and load times, inference-cache capacity, and
each engine stage as it initializes. These are individual observations, not a
percentage of overall GPU loading. Stages without a measurement say **Progress not
reported**; elapsed time remains visible. Only the service readiness check marks
the model ready. Cached models are checked and reused, not downloaded
again on every load; missing or damaged files may require a download.

**Check for model updates…** in Speech engine explicitly checks the selected
model's upstream revision while AutoTalk is idle. It reports whether it matches
AutoTalk's pinned revision, without downloading weights or replacing a loaded
model. A different upstream revision requires an AutoTalk release with the
verified model manifest before it becomes the model used for speech.

## Configure the talk

- Choose **Open PDF…** for an unencrypted PDF of 1–80 slides. AutoTalk saves it in
  **an `autotalk` subfolder beside the PDF**, choosing a unique project folder
  without replacing an earlier talk. For example, `/slides/demo.pdf` creates
  `/slides/autotalk/demo-AutoTalk/`.
  **Open saved talk…** opens an AutoTalk project; **File → Save a copy…** changes location.
- Import opens Audience & conference in Prepared/Realtime. Duration and language
  stay in the main window in all modes. **Talk → Fit duration…** also appears in
  **Talk settings → Preparation & timing**, beside timing tolerance. Inter-slide
  pauses belong to **Presentation settings → Display & sound**.
- Optionally enter conference scope directly, read it from a URL, or combine both. Review
  the editable extraction and its source links. JavaScript-only and authenticated
  websites may need a manually supplied explanation.
- Creating speech checks ChatGPT sign-in and opens browser sign-in when needed,
  before expensive speech setup. **Settings → Account…** offers **Sign in**
  when disconnected and **Sign out** when connected. Signing out clears the shared
  local Codex login. At startup, an existing Codex installation
  is checked for a ChatGPT sign-in; available models and configured defaults appear
  automatically, without opening a browser or downloading tools. Saved talk choices
  are preserved. The model
  selector lists account-available models accepting slide images; reasoning choices
  come from the selected model. Subscription limits apply. No paid API fallback is
  used. Slide images, extracted text, and supplied context are sent to Codex;
  reference recordings remain local.
- Select English, German, French, Spanish, Italian, Portuguese, Russian, Chinese,
  Japanese, or Korean before writing narration. Afterwards the main language
  control switches existing versions. **Add language version…** explicitly creates
  a translation draft while preserving the original. **Create talk text** translates
  remaining drafts, preserving slides you already replaced manually. Drafts must be translated or replaced before audio creation; synthesis
  alone cannot translate.
  `[German]` and similar paragraph markers allow mixed passages. Choose mixed
  passages, one language per slide, or a single language per version in **Language options…**.

## Voices and delivery

**Predefined** voices use CustomVoice: Ryan, Aiden, Vivian, Serena, Uncle_Fu, Dylan,
Eric, Ono_Anna, and Sohee. The picker and library describe voice character and
native language. Preview in the selected talk language. During preparation, the
voice dialog shows progress, elapsed time and Cancel. Engine loading can take
about a minute even after downloads are installed.

**My voice** uses Base with a clean 3–60 second WAV recording. Record directly
(up to 30 seconds), or import a recording. Its exact transcript is recommended;
without one, conditioning uses speaker identity alone. No fine-tuning is needed.
Save named voices for reuse; project copies retain their own references, organized
by language, with a shared reference available for cross-language use.

**Design a voice** uses VoiceDesign for a preview/reference. Preview, then accept
the exact sample you heard to reuse it through Base. Saving or starting never
redesigns an accepted sample. This avoids
independently redesigning the speaker on every slide. Base inherits the reference's
identity/delivery and does not accept CustomVoice/VoiceDesign vocal instructions.

Choose Professional, Conversational, Energetic, Calm and understated, Lightly
humorous, Academic, Storytelling, or Inspirational. Customize acoustic attributes,
voice-design age, persona, gradual progression, and per-slide directions. Save
named delivery presets. Style and attributes are combined; explicit slide directions
take precedence over custom global directions, then structured attributes/style.
These are natural-language instructions, so adherence still needs preview.
Common vocal guidance requests a steady pace, restrained expression and consistent
voice character; selected style and explicit directions take precedence. Base
does not receive unsupported instructions. Updated effective directions require
audio regeneration, while the accepted script and previous files are preserved.
Unsupported controls are disabled. Dialect and expressive
cues are model requests requiring preview, not guaranteed effects or sound tags.
Use imported clips for precisely controlled singing, music, or nonverbal effects.

**AI & speech engine → Speech model — Qwen → Advanced synthesis** exposes sampling
temperature, top-k, top-p, repetition penalty,
and an output token limit for the main speech generator. The Linux acoustic-code
generator retains its separate defaults. These are not reasoning efforts or guaranteed quality
levels. Synthesis stays at native 24 kHz; export resampling and AAC bitrate are
separate compatibility/encoding choices.

## Present, route audio, and record

Choose the fullscreen display. Use **System audio settings** and **Test audio**
to select AutoTalk's output through Plasma, Windows Sound settings, or macOS Sound.
The operating system owns routing; projects do not store audio-device bindings.

Space pauses/resumes; arrows navigate. **Esc pauses and leaves fullscreen**, keeping
the slide and position. Use **Continue presentation**, **Restart from beginning**,
or **End presentation**. Previews, narration, imported clips, and background tracks share one
PCM transport. Slide advancement follows consumed audio rather than word estimates.

Attach clips before/after slides and adjust their gain. Add a background track,
gain, and looping. Fixed clips and pauses count toward duration fitting.

Use **File → Export prepared talk…** for MP4 with sound, WAV, or
M4A without playing the talk in real time or opening an audio device. The same
mixer supplies direct export and live playback: mono narration is centered,
while imported clips/backgrounds retain stereo in a 48 kHz internal mix.
Qwen speech assets remain native 24 kHz; choose 48 kHz export to retain imported
music bandwidth. Video renders the source PDF at 1080p rather than enlarging
editor previews.

Enable **Record presentation as a video** beside **Presentation settings…** in
the main window. Its tooltip identifies the source; configure source and destination
in **Presentation settings → Recording**. During
capture the checkbox label displays **Recording video** and the recorded duration.
Choose a recording source:

- **Slide video + narration:** captures AutoTalk's slides, navigation and audio mix.
  Pause policies keep fullscreen waits, all waits, or content only.
- **Screen + system audio (Linux):** records the desktop, including live demos.
  On Wayland, grant access in the system screen-sharing chooser. Choose the system
  audio output before starting; recording uses its monitor. Optionally include the
  default microphone for live commentary. System audio already includes AutoTalk;
  narration is not mixed in a second time. X11 captures the primary display.

Screen recording continues when narration pauses, fullscreen is left, or the last
slide finishes. The status explicitly says **Slides finished — recording continues**.
Use **End presentation and save video** to stop it. The status then changes to
**Saving video** and a dated **Saved** link to open the video or folder. That link
remains separate from the next recording's on/off status.
Slide-video recordings instead finish automatically after the last slide.
MP4 output is 1080p/30 fps, retaining aspect ratio, with AAC at 24, 44.1, or 48 kHz.
Configured filenames receive a session suffix to preserve earlier recordings.
**File → Recordings & export…** lists the talk title, date, duration, and **Ready / Needs saving**
status. Select a recording to open its output/folder or save it again. Opening the
selected recording is the primary action; creating a separate slides-and-speech
video is below it and does not include recorded live demos. An empty list
explains how to make a recording; it never asks you to find an internal metadata file. Interrupted exports keep their inputs and
can be retried. On close, choose finish saving, save later, or cancel closing.
Prepared export remains available after a talk that was not recorded, but cannot
reconstruct a live demonstration.

## Projects and persistence

Save with Ctrl+S and copy the entire project folder to move a talk:

- `talk.autotalk.json`: versioned configuration, language versions, and artifact metadata.
- `slides.pdf`, `slides/`: source PDF and rendered previews.
- `voice/<language>/`: reference snapshots.
- `audio/<version>/<language>/`: generated speech, keyed by effective synthesis inputs.
- `media/`: normalized imported clips/background tracks.
- `recordings/<session>/`: recoverable stereo PCM, source PDF snapshot, timeline, and export.
- `runs/`: operation outcome, elapsed time, and stage measurements.

Version-1/2 projects migrate on save with an untouched version-specific backup.
Review and accept imported scripts once because old version-wide acceptance cannot
establish each slide's context. Verified legacy audio is preserved with its original
model provenance; default grouped synthesis does not erase existing audio. Regeneration
uses 1.7B. Changed inputs invalidate affected audio; damaged files are detected on
reopening. Old artifacts are retained; automatic disk cleanup is not implemented.

## Development and native builds

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python tools/build.py
```

Standard builds use Qt/PySide6 6.11.2, which includes the upstream PipeWire
callback-lifetime fix. To bundle a Linux build machine's Qt libraries and desktop
style plugins, use `tools/build.py --system-qt` with matching PySide6 bindings.
For this machine's Qt 6.10.2, an isolated build invocation is:

```sh
uv run --extra dev --with PySide6==6.10.2 python tools/build.py --system-qt
```

The Qt 6.10.2 build automatically downloads the checksum-pinned Qt Multimedia
source, applies the included upstream lifetime fix, and rebuilds that library.
The build host needs CMake, Ninja, patch, matching Qt base/private and shader-tools
development packages, and PipeWire, PulseAudio and FFmpeg development headers.
Other matching system Qt versions use the installed modules directly.
This build option requires `qtpaths6`. It stages the bindings with installed Qt
modules and the corrected Multimedia library, and discovers the system
plugins through the existing PyInstaller hooks. The packaging recipe also includes
KDE's local filesystem plugin when present, so native file dialogs can browse
directories. Missing optional modules, such as
Qt PDF on this machine, come from the same-version binding package. The original
Python environment and system installation are not modified by staging. The
corrected library's source archive, patch and build recipe accompany the bundle
in `qt-multimedia-source/`.

This is a build-host requirement, not an end-user setup step. The resulting bundle
contains the collected libraries/plugins. Its Linux/glibc baseline follows the
build host; it is not qualified for arbitrary older distributions. The default
build command continues to use the binding package's Qt distribution, including
in the existing CI workflow. Windows/macOS dependency selection is unchanged.

On Windows use `.venv\Scripts\python.exe`; build on each target OS. The native CI
matrix builds Linux archives, Windows ZIP packages, and Apple Silicon DMGs.
Tests marked `audio_device` need a working physical/virtual audio output and run
locally; remaining tests run in the native CI matrix. Signing hooks accept
`AUTOTALK_SIGN_IDENTITY` / `AUTOTALK_NOTARY_PROFILE` on macOS and
`AUTOTALK_SIGN_CERT` / `AUTOTALK_TIMESTAMP_URL` on Windows.

`project.py` owns configuration and artifact validity. `services.py` operates on
job snapshots and publishes validated results to Qt. `runtime.py` owns managed
processes; `speech_worker.py` adapts the three native synthesis backends.
`playback.py` owns presentation position and consumed PCM; `media.py` owns the
shared mix, recording, and direct/captured exports. Script acceptance is per slide,
and the application leases the existing single speech process across operations.
No second playback engine or speech service is introduced.

See [third-party notices](THIRD_PARTY.md). This is a development build; public
release licensing, native signing, and broader hardware qualification remain open.
