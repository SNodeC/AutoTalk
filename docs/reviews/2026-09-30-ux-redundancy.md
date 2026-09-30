# UX redundancy removal — 30 September 2026

Base: `dc77943` on `main`. Branch: `codex/ux-redundancy`. Linux verification only.
This implements owner decisions D1–D6 and work items R1–R13 from steering brief rev. 2.

## Invariant and implementation boundary

Each setting has one value editor per scope. Other surfaces may show its effective
value/source and remove an override. Menu mirrors remain where requested. Main
controls save immediately; the three existing fixed-scope dialogs retain Save/Cancel.

The existing `Project.setting`/`set_setting` authority, `MainWindow.edit_setting`,
language version selection and dialog snapshots remain authoritative. Read-only
rows reuse `SettingsPanel.add_inheritance`; a language reset goes through the
window's existing language/version/adopt path. No second settings store or resolver
was introduced. The shared read-only widget helper and existing loader handle mode,
language and recording alike.

Production changes are confined to `app.py`, `ui.py`, `settings.py` and `options.py`.
No changes to project/schema/defaults, language-generation rules, audio fingerprints,
generation, engine, playback, PDF reload, styles, shortcuts or dependency patches.
The existing footer hint and Presenter heading/Return to editing remain.

## Before/after inventory against dc77943

| Item | Before | After | Verification |
| --- | --- | --- | --- |
| R1 Duration | Main spin plus talk-dialog spin | Main Duration is the sole editor; duplicate widget and synchronization removed | Ownership, main duration persistence and modal Save/Cancel tests |
| R2 Mode/language/record | Talk-dialog editors duplicated main controls | Three read-only value/source rows with the existing Use app reset; app defaults editable; slide language editable under its existing arrangement rule | Each reset × Save/Cancel; persisted settings, language versions and active version restored correctly |
| R3 Language options | Combo/menu focused the duplicate language editor | Both focus Language arrangement | Both entrances tested for actual keyboard focus |
| R4 Slide playback | After-slide duplicated; pause hidden in slide dialog | Inspector owns after-slide and pause; source/value caption names app/talk correctly; Timing exposes inheritance checkbox and override spin | Both inheritance chains, explicit zero, save/reopen, inheritance restoration, unchanged delivery directions |
| R5 Slide delivery | Inspector directions duplicated dialog delivery | Inspector disclosure/editor/callback removed; Slide voice & delivery… opens the slide dialog, with voice/source/style below | Ownership and preservation of delivery overrides when editing playback |
| R6 Header/timing | Target/language repeated; timing prefixed the header | Header only shows audio readiness/duration; timing shows target versus prepared once | Readout assertions and main screenshots; long-title workspace check |
| R7 Recording | Checkbox and footer repeated states/timer; saved links forwarded through recording label | Constant checkbox label; one transient recording status; direct saved-output link handler | Waiting/timer/saving/idle assertions and existing recording tests |
| R8 Status bar | Permanent filler text | Transient saved/elapsed messages plus engine button | Empty initial status assertion |
| R9 Engine page | Engine state and policy explanation repeated | App model line omits state; engine section owns state; existing policy note owns Save/Cancel explanation; talk line retains state | State assertion, lifecycle suite and all engine-page scroll positions |
| R10 Menus | Account opened page without focus; Operation details also in Help | Account focuses sign-in control; footer and View retain Operation details | Action/focus/menu assertions |
| R11 Background | Separate track section away from volume/loop | Talk Background audio starts with Add/Remove, followed by volume/loop; app scope has defaults only | Shared-parent assertion and both dialog sizes/palettes |
| R12 Quick | Title and voice repeated in page body | Slide count plus existing explanation | Quick screenshots and mode tests |
| R13 Wording | Account copy contradicted defaults; Codex copy suggested signing in there | Defaults plus talk overrides explained; Codex shows connection state only | Source inspection and Account/AI-page screenshots |

The header now allocates surplus width to its title instead of the shortened audio
readout. This is a change to the existing size policy, without an extra control or
layout mechanism, and keeps the long-title P1 test working on native Breeze.
`SectionDialog.show_section` now applies keyboard focus as well as scrolling to the
requested existing focus target.

## Automated verification

The full suite includes audio-device tests. A disposable PipeWire/Pulse null sink
receives test output; physical speaker/microphone mute and volume are not changed.
The runner removes its sink in `finally`. Physical audio mute/volume snapshots
matched before and after the final suite. The existing stereo-channel test creates
and removes its own disposable sink as before.

| Run | Result |
| --- | --- |
| Standard PySide6/Qt 6.11.2 wheel, Xvfb | 453 passed, 95.25 seconds |
| Native PySide6/Qt 6.10.2, Breeze, approved cleanup patch, Xvfb | 453 passed, 118.26 seconds |

The new `tests/test_ux_redundancy.py` covers A1–A7 in 14 cases. Existing
`test_ux_placement.py` retains all 27 cases, including A8's P1 controls at 940×680
and 1100×850 in all modes and the inspector width check. Tests of removed talk
editors now exercise their surviving main controls; application and slide editors
retain their behavioral tests. Language reset/Cancel explicitly compares complete
versions and `active_version`; unchanged controls preserve `speech_key`, `text_ready`
and `ready` for every slide.

Exact full-suite commands, from the repository root (the checked-in evidence runner
sets up the disposable sink and these environment variables):

```bash
PULSE_SINK=autotalk_ux_verification \
PULSE_SOURCE=autotalk_ux_verification.monitor \
PIPEWIRE_PROPS='{"target.object":"autotalk_ux_verification","node.dont-reconnect":false}' \
QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/python -m pytest -q

PULSE_SINK=autotalk_ux_verification \
PULSE_SOURCE=autotalk_ux_verification.monitor \
PIPEWIRE_PROPS='{"target.object":"autotalk_ux_verification","node.dont-reconnect":false}' \
PYTHONPATH="$PWD/build/system-qt:$PWD/src" \
LD_LIBRARY_PATH="$PWD/build/system-qt/PySide6/Qt/lib:$PWD/artifacts/open-tasks/venv-qt610/lib/python3.12/site-packages/shiboken6" \
QT_QPA_PLATFORM=xcb xvfb-run -a artifacts/open-tasks/venv-qt610/bin/python -m pytest -q
```

Native `libQt6Multimedia.so.6` SHA-256:
`a7243f9b75189d79d97171bee23e388a135e1e1572571e392e424b9a9603782f`.
This is the existing bundle-only `packaging/qt-6.10.2-pipewire-cleanup.patch`;
no system library was modified during this work.

## Visual verification

[Evidence gallery and original PNGs](evidence/2026-09-30-ux-redundancy/README.md).
The 55 screenshots were inspected, including individual full-size images where
needed. They are actual Qt/Breeze widgets under Xvfb using the DACHS PDF, not mockups.

- Main window: Prepared, Quick and Realtime, each at 940×680 and 1100×850.
- All visible pages: application (five), talk (four), slide (two), each at 760×580
  and 920×760, including successive scroll positions to inspect the full page.
- Inspector with Timing expanded and talk Presentation & recording top/bottom:
  light and dark, at 100% and 150% scale.

Controls/readouts follow the assigned ownership. The sidebar remains narrow; long
source wording wraps in its caption. Small dialogs retain scrolling and visible
Save/Cancel; lower inspector controls remain reachable through its existing scroll
area. Dark checks set a palette only in the test process; the desktop theme is
unchanged. No new styling was introduced. The capture harness waits for layout
settlement and asserts exact logical dimensions and dialog button containment.

Exact capture command (repeat with `QT_SCALE_FACTOR=1.5`):

```bash
QT_QPA_PLATFORM=xcb \
PYTHONPATH="$PWD/build/system-qt:$PWD/src" \
LD_LIBRARY_PATH="$PWD/build/system-qt/PySide6/Qt/lib:$PWD/artifacts/open-tasks/venv-qt610/lib/python3.12/site-packages/shiboken6" \
xvfb-run -a -s '-screen 0 2400x1800x24' \
artifacts/open-tasks/venv-qt610/bin/python artifacts/ux-redundancy/screens.py
```

The capture and suite-runner scripts are retained with the evidence. They create
only temporary talks and virtual outputs; live Codex/Qwen synthesis, startup timing,
Wayland permission and non-Linux platforms are outside this placement verification.

## Failed attempts and corrections

- Initial existing placement run: 27 passed. First non-audio wheel run: 430 passed,
  one failed, eight deselected. The old timer assertion targeted the changing
  checkbox label; it now checks the required single recording status instead.
- First new acceptance run: 10 passed, four failed. Three failures exposed missing
  actual keyboard focus in the existing dialog entrance; focus now accompanies
  scrolling. The fourth test incorrectly set project defaults before `adopt`
  reloaded application defaults; its fixture now sets application defaults.
- Focused acceptance/UI run after correction: 33 passed, three audio cases
  deselected. The first complete wheel run then passed all 453 cases.
- First complete native run: 450 passed, three failed. Two menu tests lost temporary
  action wrappers while retrieving menus; retaining the actions during traversal
  fixes the tests without changing production menu ownership. The third was real
  long-title clipping; shifting the existing expanding size policy from audio
  summary to title fixes it. Intermediate focused native run: 40 passed, one failed;
  the final long-title check passed after the size-policy correction.
- The next complete native run terminated in the existing Linux stereo-channel
  test during creation of its virtual sink. The core identifies the `QAudioContext`
  thread inside `libpipewire-module-protocol-native.so`; the Python main thread
  was waiting for `pactl load-module`. The crash log and stack excerpt are retained.
  No causal link to the UX changes is established, and no audio/runtime code was
  changed or test removed to obtain a pass. Its orphaned disposable sink was
  removed after diagnosis. A complete unchanged-suite rerun is
  reported above. This intermittent native audio-device event needs separate
  investigation; it is not claimed fixed by R1–R13.
- Early captures were taken before all resize/layout events had settled. The final
  matrix waits for settlement and checks footer containment. Contact-sheet creation
  initially used the application venv, which lacks Pillow; system Python already
  supplies Pillow and was used instead. No dependency was added.

## Accounting and final review

Against `dc77943`, production (`src/autotalk`): **+65 / −65, net 0**.
Tests: **+225 / −45, net +180**, including the new 172-line acceptance file.
Documentation and screenshot evidence are separate from production/test accounting.

The final diff removes obsolete editor state and callbacks, reuses existing
inheritance and transaction paths, and introduces no parallel settings authority.
Unrelated pre-existing `.gitignore`, review evidence and Qt bug-report files are
excluded from this branch's commit. One PR targets `main`; no merge is performed.
