# Independent Claude review: language, voices and intuitive settings changes

The owner explicitly requests: "Let claude deeply review the language settings -
because not only language change must be correct but also other speakers/languate
settings change must be handled intuitively!"

Review only. Return a COMPLETE standalone Markdown verdict to stdout. Do not
implement fixes, edit tracked files, commit, push, or modify the running app.
The coordinator will preserve your actual verdict verbatim in the repository.

Checkout: /home/voc/projects/drafts/autotalk/AutoTalk
Current source HEAD: c5f45d6136675eb66edbb7cf5e52ce1fb64eb225
Current checked-out branch: main
GitHub source: https://github.com/SNodeC/AutoTalk/commit/c5f45d6136675eb66edbb7cf5e52ce1fb64eb225
Read current files; do not assume another historical main tip is checked out.
Unrelated untracked GPU/Windows investigation documents must remain untouched.

## Trigger and coordinator evidence

User reported that changing a Chinese talk to German and restarting still speaks
Chinese, probably through Talk settings. They asked to check ALL routes and
permitted the coordinator to inspect their running application. Do not inspect
private talks yourself: here is the sufficient anonymized finding from read-only
inspection of the most recently opened saved talk:

- Active main version named German, language German, mode Realtime, mixed policy.
- Only one version; 24 slides, nine text-ready and six audio-ready at inspection.
- Opening slides contain Chinese characters with untagged passages, origin generated.
- Their WAV files are under audio/main/German and satisfy Project.ready().
- No user talk or running application was altered. Live in-memory settings could
  not be inspected through AT-SPI, so this is saved-state evidence, not UI-memory proof.

Coordinator reproduced the cause using actual Qt settings controls, Save and
Start under Xvfb, synthetic Chinese text/PCM and stubbed external AI. Probe:
artifacts/language-restart/reproduce.py
Log: artifacts/language-restart/reproduction.log
Six cases: Prepared/Quick/Realtime x untagged/explicit [Chinese] text.
All six fail the desired invariant that old-language text must not be counted
ready after a target-language change. Untagged: text 2/2, audio 0/2, then Start
makes ZERO Codex calls and regenerates speech from Chinese words using German
metadata. Tagged: both counters 2/2; Start reuses Chinese audio without Codex.
Do not conflate this historical coordinator execution with your own tests.

## What to review deeply

Trace authoritative state, mutation, inheritance, persistence, cancellation,
versioning, cache identity, requests to Codex/Qwen, UI counters and actual playback:

1. Language changes from the main selector, talk settings, slide settings and
   application defaults; reverting to inherited values; selecting an existing
   language version; Add language version; empty/manual/generated/translation
   states; explicit mixed-language passages and slide overrides. What does each
   action really do, and what would an ordinary user expect?
2. Speaker/voice changes: predefined speakers, Base own/reference voices,
   VoiceDesign and accepted designed references, saved voice library, imports,
   recorded voices, language-specific reference fallback, preview versus actual
   talk synthesis, all app/talk/slide scopes. Which text/audio remains valid?
3. Writing style versus spoken delivery, vocal attributes, custom instructions,
   progression, sampling, voice source/model, pitch/pace/accent and language
   compatibility. Separate deliberate overrides from inherited defaults.
4. Prepared, Quick, Realtime and independent slide text/audio/preview actions;
   stopped, paused, finished, restarted and reopened talks; streamed partial audio,
   worker snapshots, cancellation and changing settings around queued work.
5. Save/Cancel across fixed-scope dialogs, simultaneous dialogs and scope
   inheritance; old artifacts/version retention and returning to earlier choices.
6. Usability: values visibly identify active voice/source/language/scope; counters
   reflect current content; explain regeneration without technical jargon or new
   approval steps; no hidden requirement to manually rewrite text after choosing
   another language. Check labels/tooltips and click paths against actual behavior.

Please independently inspect Project.set_setting/language/add_version,
MainWindow.edit_setting/apply_defaults/language_selected/adopt/configuration_changed,
SettingsDialog.done/voice_context, options bindings, services generation/workflow,
Mix/Playback and tests. Do not restrict review to these named functions if tracing
reveals other responsibilities. Study existing architecture before proposing fixes.

## Fixed requirements and design constraints

- Correct scope precedence: slide > talk > application defaults. Do not silently
  erase deliberate slide-language or mixed-passage choices.
- A new target language with no prepared content must not reuse source-language
  narration/audio as if translated. Existing saved language versions should survive;
  selecting an already prepared version should reuse matching valid audio.
- Changing only speaker or delivery should not rewrite factual narration.
- Keep three FIXED-scope settings dialogs sharing one implementation; no scope
  selector atop a single dialog. Native system theme/style and current visual design.
- Independent Create/Rewrite slide text, Create slide audio, Play audio, plus whole-
  talk controls. Stable Start in Quick/Realtime, Prepare and start in Prepared.
- No audio approval workflow. Do not redesign synthesis chunking (owner rejected
  replacing the existing 300-character split). Startup optimization stays deferred.
- Preserve Windows/macOS product support; this review executes tests on Linux only.
- Smallest architectural solution: reduce first, reshape existing authority second,
  add only when needed. No new parallel validity state/flags/cache authorities
  merely to patch counters or playback. If growth is necessary, estimate net
  production lines and explain what cannot be solved by deleting/reshaping.
- The owner requires explicit approval before net production growth. This review
  is not implementation approval. Propose a coherent bounded plan and acceptance
  tests, not broad new architecture.

## Required output

A complete standalone Markdown verdict with:
- Executive assessment and concrete user journeys.
- Change-semantics matrix: setting/action, scope, current effect, expected intuitive
  effect, text invalidation/translation, audio invalidation/reuse, version preservation,
  UI feedback and exceptions for deliberate overrides.
- Numbered findings LV1, LV2, etc.: severity/priority, reproduction, exact source
  references, evidence type (executed/static/design judgment), governing invariant,
  narrowest cause-level remedy, regression risks and acceptance checks.
- Rank actual defects separately from UX recommendations and unverified hypotheses.
- A concise implementation plan preserving a single authority and clear Save/Cancel
  semantics, with line-growth estimate if unavoidable. Include how to handle an
  already mislabelled saved talk safely, without silently guessing its language.
- Exact independent tests/commands/results, failed attempts and verification limits;
  screenshots actually opened versus merely generated. Cite source lines accurately.

## Execution boundaries

Use Read/Glob/Grep/Bash. Write independent probes/logs/images ONLY under
/tmp/autotalk-claude-language-review or ignored
artifacts/claude-language-review-2026-09-29. No changes under tests/ or src/.
Use synthetic decks/text and deterministic external-service substitutes.
No live Codex/Qwen requests, downloads, GPU work, real desktop/share prompts,
private talk inspection, credential reading, running-user-process interruption,
host configuration changes, git mutations, or physical audio volume/mute/routing
changes. The user's existing AutoTalk and speech engine must remain untouched.

Focused suite example (add relevant files after inspecting):
PYTHONPATH="$PWD/src" QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/python -m pytest -q -o faulthandler_timeout=30 tests/test_versions.py tests/test_scoped_settings.py tests/test_settings_dialog.py tests/test_start_interaction.py -m 'not audio_device'

For your own pytest probes, add absolute tests/ to sys.path and import needed
fixtures from conftest. Isolate QSettings. Never run competing GUI suites in parallel.
Native Breeze is available via:
PYTHONPATH="$PWD/artifacts/wayland-fix/native:$PWD/src"
LD_LIBRARY_PATH="$PWD/artifacts/wayland-fix/native/PySide6/Qt/lib"
QT_QPA_PLATFORM=xcb
Interpreter: artifacts/open-tasks/venv-qt610/bin/python
Use xvfb-run -a; keep any XDG paths absolute. Do not replace shared Qt libraries.

Take the time needed to review the entire language/voice interaction, including
failure boundaries. Passing old tests is not proof of correct UX. Return your
full verdict, not only a summary or a path to a report.
