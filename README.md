# AutoTalk

AutoTalk is a planned Qt desktop application that turns an existing PDF slide
deck into a timed, spoken presentation tailored to its conference and audience.
The application name is **AutoTalk**; its executable will be **`autotalk`**.

## Project status

This repository currently contains the project description. The application,
installer, and speech integration have not been implemented. Features below
describe the intended first draft, not capabilities already available.

## Intended workflow

1. Select a PDF slide deck and enter the desired talk duration in minutes.
2. Provide the conference scope through a website URL or a manual description.
   Review and edit the extracted scope, including conference themes, audience,
   and the talk's objective.
3. Generate a coherent narration grounded in the slides and aligned with that
   scope. Review and edit the narration alongside each slide.
4. Choose an available voice or record/import a reference sample of your own
   voice inside the application.
5. Generate speech locally, measure the actual audio duration, and adjust the
   narration to fit the requested duration within an explicit tolerance.
6. Present fullscreen with synchronized slides and audio, using pause, resume,
   previous, next, and stop controls.
7. Save the prepared talk for reuse and offline playback.

## Planned architecture

- **Qt desktop interface:** initially targeting Linux, with an integrated PDF
  viewer and audio playback. Python with PySide6 is the proposed implementation
  stack, subject to packaging validation.
- **Codex app-server:** analyzes slide text and rendered page images, interprets
  conference context, and writes or revises the narration. Users sign in with
  ChatGPT through the supported Codex authentication flow.
- **Local speech generation:** Qwen3-TTS Base 0.6B is the initial candidate for
  generating narration and cloning the user's voice from reference audio.
  Reference-based cloning normally does not require fine-tuning a model.
- **GPU acceleration:** NVIDIA GPU execution is the first supported acceleration
  target. Model inference, memory use, and voice quality require validation.
  NPU support is outside the first draft's scope. CPU execution and its practical
  minimum requirements remain to be evaluated; no universal hardware support or
  real-time generation speed is promised.
- **Playback controller:** one controller owns the current slide and audio
  position. Playback follows prepared audio segments and does not depend on live
  model responses or estimated slide timers.

The conference URL and manual-description paths produce one editable conference
scope. The model must preserve the slide deck's factual claims, flag unclear
material, and avoid inventing evidence to match conference themes.

Slides, narration, generated audio, and measured timing belong to one consistent
talk version. Editing narration invalidates its corresponding audio and timing.
The final duration includes narration, planned pauses, and transitions.

## No manual technical setup

The intended user experience is to install and launch AutoTalk without terminal
commands, Python installation, CUDA toolkit installation, or manual environment
configuration. The application must:

- Bundle or automatically provision an isolated runtime and required dependencies.
- Detect compatible hardware and existing drivers.
- Download and verify model files with progress and resumable downloads.
- Validate the selected speech runtime with a short generation check.
- Guide voice recording/import and automatically prepare reusable voice data.
- Keep the interface responsive during setup and speech generation.

ChatGPT sign-in and providing a voice sample are user interactions, not technical
setup. First use requires internet access for sign-in and downloads. Hardware and
driver requirements must be documented once validated; automatic runtime setup
does not imply automatic system-driver replacement. Prepared playback is offline.

## Data and usage costs

Codex preparation uses the user's eligible ChatGPT subscription allowance and is
subject to its usage limits. Subscription authentication does not include general
OpenAI API access. The proposed local speech engine requires no paid speech API.

Voice recordings and reusable voice data are intended to remain local. Slide
content, conference context, and narration sent to Codex are processed through
the configured Codex service; preparation is therefore not fully offline.
Conference URL analysis also requires network access.

## First-draft validation

- Clean-machine setup without manual dependency installation.
- GPU model loading and successful voice-cloned speech generation.
- Voice similarity, language support, and pronunciation of technical terms.
- Measured talk duration against the requested target and tolerance.
- Correct slide/audio synchronization after pause, resume, and navigation.
- Consistent regeneration after narration edits.
- Saved-talk reopening and offline playback.

## Upstream documentation

- [Codex app-server](https://learn.chatgpt.com/docs/app-server)
- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- [Qt for Python](https://doc.qt.io/qtforpython-6/)

The project license has not yet been selected. Third-party runtimes and model
weights retain their respective licenses.
