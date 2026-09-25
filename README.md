# AutoTalk

**Turn existing PDF slides into a timed presentation in your own voice.**

AutoTalk is a Python/PySide6 desktop prototype for Linux. It uses **Codex
app-server with ChatGPT sign-in** to write the talk and **Qwen3-TTS on your
NVIDIA GPU** to generate speech locally. The executable is **`autotalk`**.

## Start the application

Extract the packaged `AutoTalk-0.1.0-linux-x86_64.tar.gz` archive and open the
`autotalk` executable inside its `autotalk` directory. Keep the accompanying
`_internal` directory beside it. The package contains Python and Qt: users do
not install Python, PySide6, PyTorch, a CUDA toolkit, or command-line tools.

For this development checkout, the built application is available through
`./autotalk` and directly at `dist/autotalk/autotalk`. Release archives are
build outputs and are not committed to Git.

The first speech operation automatically downloads a private Python speech
runtime, pinned dependencies, and the selected model. Downloads show progress,
can be cancelled, and reuse completed/cached files when retried. Tools and model
files are verified against pinned upstream hashes. A built-in voice and voice
cloning use different Qwen models; each is downloaded only when needed.

**Current target:** Linux x86_64 with a working NVIDIA driver. The prototype was
verified on an RTX 2000 Ada laptop GPU with 8 GB VRAM. NPU and CPU inference are
not supported by this first build. AutoTalk does not replace system drivers.
Allow roughly 15–20 GB of free disk space for runtime, models, and download
caches; the application archive itself is much smaller. The locally built Qt
bundle still relies on ordinary Linux desktop/system libraries. Compatibility
with other distributions needs separate testing.

## Create a talk

1. **New from PDF:** select a PDF and a parent directory for a portable project.
   AutoTalk creates a new project folder without overwriting an existing one.
   The prototype supports unencrypted decks of 1–80 pages.
2. **Talk details:** set the duration in minutes, timing tolerance, pause between
   slides, spoken language, audience, and objective.
3. **Conference scope:** enter a description directly, or give a conference URL
   and select **Read conference website**. Review the extracted scope and source
   links. The reader handles static HTML and a small number of relevant pages
   on the same site; login-protected or JavaScript-only sites may need manual
   scope entry.
4. **Connect ChatGPT:** use an existing Codex ChatGPT login or complete the
   supported browser sign-in flow. No API key is needed. Your subscription's
   limits apply; AutoTalk does not switch to paid API access automatically.
5. **Create narration:** Codex receives the deck's rendered pages and extracted
   text, plus your conference context. Review and edit each slide's narration.
   Notes identify uncertainties rather than inventing supporting facts.
6. **Voice:** use the built-in Ryan voice, or import/record your own reference
   voice. Recordings are PCM WAV, 3–60 seconds; in-app recording stops after
   30 seconds. Entering the recording's exact transcript improves conditioning.
   Preview the voice before generating the whole talk. Reference-based cloning
   requires no fine-tuning; AutoTalk prepares the conditioning automatically.
7. **Generate speech:** synthesize the reviewed script as written. AutoTalk
   measures the audio files, including the configured inter-slide pauses.
   **Fit narration to duration** can revise the script and regenerate audio for
   up to three passes. It reports if the result is still outside your tolerance;
   it never silently claims that an unmet target has been reached.
8. **Present:** select the display and start fullscreen playback. Audio completion
   advances the slides. Use the presenter controls or Space to pause/resume,
   arrow keys to navigate, and Esc to leave fullscreen. Prepared playback is
   offline. The measured content duration excludes user pauses and small device
   loading delays between audio files.

The spoken language is selectable: **English, German, French, Spanish, Italian,
Portuguese, Russian, Chinese, Japanese, and Korean**. The selection is sent to
both Codex and Qwen. Changing it invalidates generated audio and flags existing
narration for review/regeneration. The UI itself is currently English.

## Save and reopen

Use **Save** or Ctrl+S. AutoTalk also saves before operations, after completed
preparation steps, and on normal exit. Editing alone is not crash-safe autosave.
A project directory contains:

- `talk.autotalk.json`: settings, narration, notes, budgets, and audio metadata.
- `slides.pdf` and `slides/`: the original deck and rendered page previews.
- `voice/`: an imported/recorded reference voice, when used.
- `audio/`: generated PCM WAV files keyed by their generation inputs.

Move or copy the complete folder to keep the talk portable. **Open talk** loads
its `talk.autotalk.json`. Original PDF/reference hashes are checked on load;
missing or damaged audio is marked for regeneration. Completed slide audio is
saved even when a later generation is cancelled. Superseded audio files remain
in the folder; automatic disk cleanup is not implemented.

## Architecture and invariants

- `project.py` owns project state and derives whether audio matches its narration,
  language, voice, and pause settings. There is no independent mutable ready flag.
- `codex.py` speaks JSON-RPC over app-server stdio, supports ChatGPT login,
  structured output, errors, and cancellation. Generation disables shell tools,
  web search, app connectors, and configured MCP servers. It supplies document
  content explicitly and does not send voice recordings.
- `services.py` imports PDFs, extracts conference context, generates narration,
  synthesizes audio, and performs bounded duration adjustment.
- `runtime.py` provisions verified tools and an isolated speech environment.
  `speech_worker.py` loads the official Qwen runtime in a separate process,
  retaining the model and voice prompt across slides in that job. Process exit
  releases its GPU resources.
- `playback.py` is the single authority for slide index and audio position.
- `app.py` provides the Qt interface and cancellable background jobs.

Conference URL extraction and manual entry populate the same editable scope.
Narration/audio/timing belong to one consistent project version. Editing a
narration or changing voice/language/pause settings makes affected audio stale;
playback requires current audio for every slide. A scope change flags narration
for review but does not rewrite it without a generation request.

## Data and costs

Voice reference recordings and generated speech stay local. Slide images, text,
narration, and conference context are sent to Codex for preparation, under the
user's configured ChatGPT account. Source websites are accessed when requested.
Preparation is therefore not fully offline; playing an already prepared talk is.

Speech has no OpenAI API charge. Codex uses an eligible ChatGPT subscription and
its usage allowance. First-run downloads, disk storage, and local computation
are still required. Synthesized narration should be identified as AI-generated.

Application data normally lives in `~/.local/share/autotalk`, respecting
`XDG_DATA_HOME`. Developers can override it with `AUTOTALK_DATA_DIR`. Existing
Codex authentication is reused through app-server; otherwise the application
provisions Codex and opens its login flow.

## Development

These commands are for contributors, not end-user preparation:

```sh
uv venv --python 3.12
uv pip install -e '.[dev]'
.venv/bin/autotalk
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python tools/build.py
```

The build produces a standalone application directory and a compressed archive
under `dist/`. Unit/UI tests use a generated two-page PDF and short WAV fixtures;
normal test runs do not invoke paid APIs, Codex generation, or model downloads.
GitHub Actions runs these checks on Ubuntu 24.04. Its remote run is separate
from local verification.

See [verification results](docs/VERIFICATION.md) for what was actually exercised
and remaining limitations. AutoTalk is a prototype, not yet a broadly qualified
Linux distribution. Its own license remains to be selected; see
[third-party components](THIRD_PARTY.md).

## Upstream references

- [Codex app-server](https://learn.chatgpt.com/docs/app-server)
- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- [Qt for Python](https://doc.qt.io/qtforpython-6/)
