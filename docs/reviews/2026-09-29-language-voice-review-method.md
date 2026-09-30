# Language and voice review: method and evidence

29 September 2026. Review-only work against
`c5f45d6136675eb66edbb7cf5e52ce1fb64eb225`, checked out on `main`.

The owner requested a deep Claude review of language, speaker and related setting
changes, including whether their effects are intuitive. This followed a reported
Chinese-to-German restart that still spoke Chinese.

## Independent reviewer

Claude CLI 2.1.276, configured model `claude-sonnet-5`, session
`1b96e7d4-bb55-4095-9a68-6b47d7914415`.

- [Original review brief](2026-09-29-language-voice-review-brief.md).
- [Follow-up requesting broader checks and corrections](2026-09-29-language-voice-review-followup.md).
- [Final factual and architectural audit request](2026-09-29-language-voice-review-audit.md).
- [Coordinator's original restart reproduction](2026-09-29-language-restart-reproduction.md).

The first review independently reproduced the main defect but relied on source
inspection for much of the voice/UI assessment. Its first proposed remedy also
missed inherited language changes and deliberate slide overrides. The coordinator
requested an additional pass with independent probes, real Qt controls, visual
inspection and corrected claims. The initial verdict is superseded, not an
approved implementation specification.

The CLI ran with `--safe-mode -p --permission-mode dontAsk`, restricted to
`Read,Glob,Grep,Bash`, and `--output-format stream-json --verbose`. The second pass
used `--resume` with the same session. Input was redirected from the two briefs;
responses and stderr were saved under ignored
`artifacts/claude-language-review-2026-09-29/`.

Revision 2 is preserved verbatim in
[Claude's full verdict](2026-09-29-claude-language-voice-verdict.md). Its source
response SHA-256 is
`933f52104aab0f79a7d211fc28c6c2e93287a6a05b17eb82bc6b2a1f919261ba`.
The coordinator requested a short final addendum after finding overclaims in
that revision's verification record and gaps in several proposed remedies.
Read [Claude's final corrections](2026-09-29-claude-language-voice-corrections.md)
with the original verdict; superseded recommendations
must not be treated as an implementation specification.

## Execution and limitations

Claude independently created pure project-state probes and a real Qt dialog
probe. The latter exercised the talk-language change, Save, voice-source tabs,
all three settings scopes, inheritance reset and Cancel. It generated twelve
synthetic screenshots and opened six with its Read tool: 03, 04, 06, 08, 09, 11.
The raw verdict's claim that all twelve were opened is contradicted by the trace.
Opening tabs is not an end-to-end acoustic test of every voice source.

Claude's executed baseline suites:

- `tests/test_versions.py tests/test_scoped_settings.py`: **21 passed in 3.06 s**,
  offscreen.
- `tests/test_slide_speech.py tests/test_workflow.py`: **24 passed in 10.60 s**,
  offscreen.
- Final audit only:
  `tests/test_refinement.py::test_writing_next_slide_preserves_current_stream_buffer`:
  **1 passed in 0.83 s**, offscreen. Revision 2 initially described this as passing
  after only reading it; the actual execution happened later, during the audit.

The coordinator separately ran:

```sh
PYTHONPATH="$PWD/artifacts/wayland-fix/native:$PWD/src" \
LD_LIBRARY_PATH="$PWD/artifacts/wayland-fix/native/PySide6/Qt/lib" \
QT_QPA_PLATFORM=xcb xvfb-run -a \
artifacts/open-tasks/venv-qt610/bin/python -m pytest -q \
  -o faulthandler_timeout=30 tests/test_versions.py \
  tests/test_scoped_settings.py tests/test_settings_dialog.py \
  tests/test_start_interaction.py -m 'not audio_device'
```

Result: **69 passed, 2 deselected in 33.90 s**. Log:
`artifacts/claude-language-review-2026-09-29/coordinator-native-tests.log`.
These overlap Claude's tests; the numbers must not be added as unique coverage.
Passing existing tests does not disprove the independently reproduced defects.

The GUI probe used synthetic slides and silent WAVs under Xvfb. No real Codex or
Qwen generation, physical playback, microphone recording, model download or GPU
work was requested. The user's running AutoTalk and speech engine were not
interrupted. Speaker/microphone mute, volume and routing were not changed.
This is a technical usability review, not a study with recruited ordinary users
or a multilingual listening-quality evaluation. Windows/macOS were not executed.

Probe scripts, logs and screenshots were copied from Claude's temporary scratch
directory to ignored
`artifacts/claude-language-review-2026-09-29/evidence/`. They remain local evidence,
not checked-in regression tests. Raw CLI traces are also local artifacts; the
Markdown verdict is the repository record.

## Additional coordinator finding: reopening an inherited-language talk

A separate persistence probe saved a populated talk inheriting Chinese, then
loaded it and applied German application defaults. The source narration remained
Chinese, `text_ready` stayed true, audio readiness became false, and the list of
pages needing Codex remained empty. The result is recorded in
`artifacts/claude-language-review-2026-09-29/coordinator-closed-talk.json`.

This extends the inherited-default problem to talks that were closed when the
default changed. A fix based only on comparing values during an open dialog edit
would miss this route. The persisted model excludes application defaults and an
inherited version has an empty `version.language`: implementation must explicitly
resolve how the language of existing authored content survives reopening. Do not
claim that a callback around `set_setting` alone solves that lifetime boundary.

The persistence probe used a minimal synthetic PDF placeholder and PNG; it tested
manifest validation and state round-trip, not PDF rendering. Two initial harness
attempts omitted the required PDF/image assets and failed validation before the
behavior under test. After supplying those assets the observation assertions
passed. Those setup failures were not application defects.

## Accounting

No production or tracked test files were changed: **production +0/-0, tests +0/-0**.
Only review documents and ignored diagnostic artifacts were created. Existing
untracked GPU/Windows investigation documents were preserved. No commit, push,
branch change, automatic project repair or implementation approval is implied.
