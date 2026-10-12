# CI platform failures — 12 October 2026

Base: `46471c636d88c2d97b1bb07b0dfee4ca44c94331` (`main`).
Branch: `codex/ci-platform-tests`.

## Invariants and causes

1. **A backend-specific test must select its backend at the consumer boundary.**
   The progress fixture patched `runtime.speech_backend`, but `services` imports
   that callable directly. Windows selected Torch and macOS selected MLX while
   the fake worker emitted vLLM logs. Patch both lookup sites and assert the
   selected configuration. Production backend selection remains unchanged.
2. **Platform integration tests must state their platform requirement.**
   The Qt screen-capture disposal test constructed a Linux-only capture class
   on Windows and macOS. Give it the same Linux condition as its neighboring
   screen-capture tests.
3. **An unattended test cannot wait for a human to dismiss an error.**
   Unexpected `QMessageBox.warning` calls now fail through pytest-qt with their
   actual message. Expected-error tests retain their local handlers. Individual
   test names and 30-second stack dumps expose stalls without suppressing later
   tests or increasing timeouts.
4. **Tests that consume audio require an output; UI-state tests do not.**
   Seven additional parametrized cases genuinely consume audio and now use the
   existing `audio_device` marker (15 cases total). UI-only control, geometry and
   Quick autostart tests stop the transport timer instead of accidentally opening
   a device. All behavioral assertions remain. The complete local suite runs
   against a private PulseAudio process with only a stereo null sink.
5. **Worker-state assertions need causal synchronization.**
   The model/playback overlap test used a 400 ms fake-worker delay, which could
   expire before the audio server began consuming samples. A test-owned file gate
   releases the fake model only after the existing playback-progress assertion.
6. **The SIGINT test must actually deliver SIGINT.**
   The local test launcher inherited a blocked SIGINT. The Linux probe unblocks
   the signal before exercising AutoTalk's existing handler.
7. **The offscreen renderer must have real fonts.**
   Windows' offscreen plugin uses `QFreeTypeFontDatabase`, whose default font
   directory is Qt's library directory plus `/fonts`, not the Windows system
   directory. Empty font discovery produced blank extracted PDF text and
   meaningless fallback layout metrics. The test harness supplies
   `%WINDIR%/Fonts` through `QT_QPA_FONTDIR` only for Windows/offscreen, preserves
   explicit overrides, and asserts font availability. Generated PDFs use Qt's
   application font. No application font, widget style or layout is changed.
   Sources: [offscreen integration](https://github.com/qt/qtbase/blob/v6.11.2/src/plugins/platforms/offscreen/qoffscreenintegration.cpp#L58-L66),
   [FreeType discovery](https://github.com/qt/qtbase/blob/v6.11.2/src/gui/text/freetype/qfreetypefontdatabase.cpp#L28-L49),
   [font directory](https://github.com/qt/qtbase/blob/v6.11.2/src/gui/text/qplatformfontdatabase.cpp#L331-L337).
8. **Source-code inspection must use the source encoding.**
   Ownership tests now read Python/JSON evidence as UTF-8 rather than the Windows
   legacy locale encoding.
9. **Cancelling a draft must preserve live-project media on every OS.**
   Imports store relative asset names with `as_posix()`. Cleanup compared these
   with `str(relative_path)`, which uses backslashes on Windows and deleted a
   referenced file. Cleanup now uses the same portable representation as import.
   The existing cancellation test caught this data-loss defect on Windows.
10. **Project replacement must release owned file handles first.**
    Playback's `Mix` keeps audio files open while stopped. Windows correctly
    refuses to rename the project directory until they are closed. The new
    regression covers handle release before installation and usable audio after
    installation failure. The proposed fix reuses `transport.close()` and
    `refresh_audio()`; its two additional production lines were explicitly approved by the owner.

## Verification so far

- Initial full local run with private audio: 573 passed, 1 skipped, 2 failed.
  Failures were the fixed-delay overlap assertion and blocked SIGINT.
- After those corrections: **575 passed, 1 skipped**, 150.59 seconds. The skip
  requires PipeWire; this isolated server is PulseAudio. This ran all 15
  `audio_device` cases without accessing physical outputs.
- Local no-audio run at `d6cf039`: **561 passed, 15 deselected**, 108.06 seconds.
- Focused Windows-style local checks after the portability corrections:
  **15 passed, 95 deselected**, 5.69 seconds.
- The new reload ownership regression was run before the production fix:
  both cases failed the explicit assertion that retained streams were closed.
- A diagnostic large-font local probe found one compact-inspector overflow at
  940×680 with Arial 12. This is not proof of a native Windows layout defect;
  the stock Windows offscreen run first needs actual fonts. No layout assertion
  was removed or loosened.

The shared workflow and repository build manifest remain unchanged. GitHub runs
are dispatched manually on the branch using the existing workflow. Build/package
and smoke steps remain enabled even after test failures.

### Commands

Run from the repository root:

```sh
QT_QPA_PLATFORM=offscreen \
  XDG_RUNTIME_DIR=/tmp/autotalk-ci-runtime \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/autotalk-ci-no-dbus \
  PULSE_SERVER=unix:/tmp/autotalk-ci-no-audio \
  PYTHONPATH=src .venv/bin/python -m pytest -q -m 'not audio_device'
python3 docs/reviews/evidence/2026-10-12-ci-platform-tests/private-audio-tests.py
gh workflow run ci.yml --repo SNodeC/AutoTalk --ref codex/ci-platform-tests
gh run view RUN_ID --repo SNodeC/AutoTalk --json jobs
gh api repos/SNodeC/AutoTalk/actions/jobs/JOB_ID/logs
```

The private-audio script creates and terminates its own PulseAudio process. Its
only sink is a null sink. It never calls desktop `pactl` or changes physical
speaker/microphone mute, volume, default device or routing.

### Diagnostic CI runs

| Run | Revision | Result / useful evidence |
| --- | --- | --- |
| [38237355039](https://github.com/SNodeC/AutoTalk/actions/runs/38237355039) | `b7996ca` | Cancelled after collecting Linux and Windows modal-warning stacks; backend progress cases passed. |
| [38237728535](https://github.com/SNodeC/AutoTalk/actions/runs/38237728535) | `082bf4c` | Cancelled after exposing warning failures; unclassified audio tests still blocked teardown. |
| [38238052714](https://github.com/SNodeC/AutoTalk/actions/runs/38238052714) | `0838c00` | macOS green. Linux: 559 passed, 2 failed, 2 errors, 15 deselected. Windows: 505 passed, 23 failed, 8 errors, 33 skipped, 15 deselected. Full failure report exposed fonts, PDF handles, cleanup paths and encoding. |
| [38238353354](https://github.com/SNodeC/AutoTalk/actions/runs/38238353354) | `d6cf039` | macOS green. Linux: 559 passed, 2 failed, 15 deselected (Quick autostart timer, subsequently fixed). Windows: 507 passed, 21 failed, 6 errors, 33 skipped, 15 deselected. |
| [38239058549](https://github.com/SNodeC/AutoTalk/actions/runs/38239058549) | `12d4b75` | Linux/macOS green. Windows: 511 passed, 17 failed, 6 errors, 33 skipped, 15 deselected; before offscreen font-directory fix. |
| [38239179225](https://github.com/SNodeC/AutoTalk/actions/runs/38239179225) | `7d74921` | Linux: 561 passed, 15 deselected. macOS: 551 passed, 10 skipped, 15 deselected. Both jobs green. Windows: 525 passed, 3 failed, 3 errors, 33 skipped, 15 deselected. Only the three PDF-reload installation cases remain; all font/layout/language/cleanup/encoding checks pass. |

Earlier attempts also included an incorrectly chosen PulseAudio socket path that
collided with its runtime directory (corrected to `native.sock`), a sandboxed Qt
audio-initialization stall (rerun with full access), and an intermediate cleanup
edit referencing an unimported `Path` (caught locally and replaced with the
existing import-side `as_posix()` convention before commit).

## Approved reload fix and final verification

The test-only font setup resolved every Windows layout failure without changing
application geometry or weakening assertions. The three remaining Windows
failures were the existing GUI PDF-reload tests.

The owner approved the two-line production addition and requested push/merge.
The install callback now closes the existing transport before replacing the
project directory. If installation raises OSError, it refreshes the old project's
audio before displaying the error. Successful adoption already reconstructs the
transport. No additional state or abstraction was introduced.

All **15 PDF-reload tests pass** (4.62 seconds), including the two new cases that
failed before the fix: handles released before installation and playable audio
after installation failure. The final full local suite passes: **577 passed, 1 skipped**, 148.64 seconds,
including all 15 audio-device cases against the private stereo sink. The skip
requires PipeWire; this server is PulseAudio. All three hosted platform jobs now pass; exact results appear below.

## Accounting against main

- Production (`src`): **+3 / −1, net +2** (portable cleanup and approved reload lifetime fix).
- Tests (`tests`): **+71 / −12, net +59**, including the two pre-fix regressions.
- Test configuration (`pyproject.toml`): **+2**, named tests and stack diagnostics.
- Reproduction helper under review evidence: **+48** lines; no runtime dependency.
- Shared CI workflow/build manifest: unchanged.
- Production growth: **+2 lines**, explicitly approved before implementation.

## Final attempts and environment limits

- The first approved-fix run (`38240512151`) found the new report was not
  reachable from README. Added its link to `docs/reviews/README.md`; no CI rule
  was bypassed. Run `38240707142` checks the corrected index.
- A supplemental run with the old native Qt 6.10.2 environment aborted before
  the first test could initialize QApplication. A `QT_DEBUG_PLUGINS=1` probe
  confirmed the available system plugins now use Qt 6.11.0 and are incompatible
  with that old runtime. No native test pass is claimed and no libraries were
  changed. The pinned Qt 6.11.2 wheel is the locally verified and CI-tested stack.

## Approved-fix hosted results

All three platform jobs in [run 38240512151](https://github.com/SNodeC/AutoTalk/actions/runs/38240512151)
passed their tests, native packaging and packaged-application smoke checks at
`bf4f20e`:

| Stack | Passed | Skipped | Audio cases deselected | Test time |
| --- | ---: | ---: | ---: | ---: |
| Ubuntu 24.04 / Qt 6.11.2 | 563 | 0 | 15 | 168.06 s |
| Windows 2025 / Qt 6.11.2 | 530 | 33 | 15 | 226.03 s |
| macOS 15 / Qt 6.11.2 | 553 | 10 | 15 | 134.31 s |

The documentation index was corrected in `15fc35f`; its hygiene job passes in
[run 38240707142](https://github.com/SNodeC/AutoTalk/actions/runs/38240707142).
The application and test trees are identical between these two revisions.
The Windows PDF-reload regression and media-reference cleanup checks now pass.
The full local wheel suite (577 passed / 1 PipeWire-specific skip) additionally
covers the 15 audio integration cases omitted by the shared hosted workflow.
