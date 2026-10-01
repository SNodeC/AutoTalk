# Settings polish after PR #3/#4

Base: `ad4178d` (main). Branch: `codex/settings-polish`. Linux only. The unrelated
Qt bug-report work remains in its original worktree, outside these commits.

## Invariants and scope

Formatting must preserve every touched module's AST. Settings Save must apply
all replayed operations or restore the pre-Save project without saving or losing
the draft. Compact inheritance fields own their label, editor, source and Reset;
existing dialog rows and application settings semantics remain unchanged.

The existing adopt rollback path and ElidedLabel are reused. No new dependency,
transaction layer, settings authority or application architecture is introduced.

## Commit 1 — formatting only

Only `settings.py`, `settings_schema.py`, `settings_fields.py`,
`settings_components.py`, `preferences.py` and `inspector.py` were formatted.
`app.py` and `ui.py` were untouched. Long text literals were split using implicit
concatenation; no wording changed. The schema was also wrapped for readability.

Analysis tools were installed only into `artifacts/settings-polish/analysis`:

```sh
python3 -m venv artifacts/settings-polish/analysis
artifacts/settings-polish/analysis/bin/pip install black autopep8 pycodestyle ruff
artifacts/settings-polish/analysis/bin/black -S -l 120 \
  src/autotalk/settings{,_schema,_fields,_components}.py \
  src/autotalk/{preferences,inspector}.py
python3 docs/reviews/evidence/2026-10-01-settings-polish/check-formatting.py
artifacts/settings-polish/analysis/bin/pycodestyle --select=E225,E231,E702 \
  src/autotalk/settings{,_schema,_fields,_components}.py \
  src/autotalk/{preferences,inspector}.py
PYTHONPATH="$PWD/src" AUTOTALK_TEST_WM=1 .venv/bin/python \
  docs/reviews/evidence/2026-10-01-settings-refactor/full-tests.py settings-polish-c1
```

The initial schema-only spacing pass used `autopep8 --select E225,E231,E702`;
Black then formatted all six files. Black leaves long strings intact, so seven
strings were split manually and Black/AST checks repeated. The recorded
[script and output](evidence/2026-10-01-settings-polish/ast-identity.txt) prove
all six ASTs identical against `ad4178d`. All physical source lines are at most
120 characters. pycodestyle reports **0 findings** for E225/E231/E702.

Accounting: **+582 / −206 = +376 production lines**, all formatting; **0 test
lines changed**. Evidence scripts are reported separately from production/tests.
The corrected PR B production delta is **+482**, exceeding its +150 ceiling by
332; the addendum to the PR B report explicitly corrects the compressed-code count.

Formatting verification initially found one E231 inside an f-string that Black
left intact. The comma spacing was corrected and AST/pycodestyle checks repeated
successfully. No AST mismatch occurred.

Baseline captures use `capture.py before ../AutoTalk/src`, importing the unchanged
`ad4178d` production tree from the original worktree. All 32 captures succeeded:
Fusion for the wheel, Breeze for native; both palettes, both scales, both main
window sizes and 760×580/920×760 talk Timing & playback pages. The minimum-width
inspector has horizontal clipping and stacked source/Reset rows before F4.

Commit 1 full-suite results: **561 passed** on the stock wheel (185.01 s), and
**561 passed** on native Qt/Breeze (234.45 s). The existing driver ran both
stacks against this worktree with a private null audio sink; logs and audio
snapshots are in `evidence/2026-10-01-settings-polish/commit1`.

Audio audit limitation: all physical volumes/ports and source mute states stayed
unchanged, but four physical sink mute flags changed from true to false during
this run. The driver/capture commands only create/remove named null sinks; the
Linux audio test only changes its own named test sink. No command in this work
sets a physical sink's mute state. The cause of the observed change is unproven;
we did not reset the user's current audio state. Thus this report does not claim
physical mute-state identity for the first run. Private portal/desktop teardown
warnings appear after pytest and are retained in the logs.

## Commit 2 — fixes

- **F1:** the Preferences link uses `&&` in Qt source text, rendering the literal
  “Display & sound settings…”. The guard inspects every QAbstractButton, QAction
  and tab label under the main window, all three scoped dialogs and Preferences.
  Breeze also supplies intentional native `&Save`, `&Cancel` and `&Close` labels.
  To satisfy the requested universal raw-text guard without changing their
  keyboard shortcuts, SectionDialog now initializes standard buttons in one
  shared method: retain each Qt-provided shortcut, remove mnemonic markup from
  its caption, restore the shortcut. Tests compare those shortcuts with a fresh
  native QDialogButtonBox. No native label is hardcoded or dependency patched.
- **F2:** Save snapshots the live project before replay. An exception restores it
  through `adopt`, keeps the draft/operation log/dialog open, restores the dirty
  flag and reports the error in dialog status. Because adopt increments the
  generation, the restored dialog's generation is aligned for retry. Defaults
  still replay into a fresh Project; defaults/QSettings are assigned only after
  every operation succeeds. Tests inject exceptions **after** operation 1 or 2
  actually mutates its target, across all three scopes and both dirty states.
  They check whole-project equality, unchanged manifest bytes/mtime, unchanged
  draft/log/defaults, no Save call, and successful second Save after fault removal.
- **F3:** removed the unused presenter `slide` assignment.
- **F4:** compact fields own a single title/source/Reset line above the editor.
  The existing ElidedLabel supplies the full source tooltip. Titles stay on one
  line; the caption is right-aligned and can shrink. Vertical spacing is 10 px,
  matching inspector rows. The inspector scroll area reserves its native
  scrollbar width in addition to the 200 px content minimum, fixing the Breeze
  overflow rather than hiding a scrollbar or clipping controls. Non-compact
  dialog field layout is unchanged.

Functional production delta against `de09443`: **+48 / −14 = +34 lines**, within
+40. This includes the shared standard-button initializer and native scrollbar
allowance. The snapshot/exception boundary cannot be replaced by removing code:
partial live replay must be undone. The existing adopt path is reused rather
than introducing a second transaction implementation. No new runtime dependency
or settings schema/resolution change was made.

## Functional verification commands

```sh
PYTHONPATH="$PWD/src" AUTOTALK_TEST_WM=1 \
AUTOTALK_PYTEST_ARGS='tests/test_settings_polish.py tests/test_settings_drafts.py tests/test_ux_placement.py tests/test_ui_ownership.py' \
.venv/bin/python docs/reviews/evidence/2026-10-01-settings-refactor/full-tests.py settings-polish-focused-final
PYTHONPATH="$PWD/src" AUTOTALK_TEST_WM=1 .venv/bin/python \
  docs/reviews/evidence/2026-10-01-settings-refactor/full-tests.py settings-polish-c2
artifacts/settings-polish/analysis/bin/ruff check --select F src
artifacts/settings-polish/analysis/bin/pycodestyle --select=E225,E231,E702 \
  src/autotalk/settings{,_schema,_fields,_components}.py \
  src/autotalk/{preferences,inspector}.py
.venv/bin/python docs/reviews/evidence/2026-10-01-settings-polish/capture.py after
python3 docs/reviews/evidence/2026-10-01-settings-polish/compare-screens.py
```

The existing full-suite driver records exact subprocesses/environments and runs
both stacks despite failure on either. PYTHONPATH selects the worktree source;
the native environment retains the existing Qt Multimedia cleanup patch. Focused
final checks passed **88 tests on each stack** (32.69 s wheel, 44.58 s native).
The last caption-alignment adjustment followed that focused run and is covered
by the subsequent final full-suite verification and recaptured visual matrix.
The commit 1 AST script is intended to run at `de09443`; commit 2 deliberately
changes behavior and thus changes ASTs.

## Visual comparison

The evidence contains **32 baseline and 32 final captures**, plus four labelled
before/after review sheets and a JSON pixel-difference bounding-box inventory.
Both palettes and scales are included for main sizes 940×680 and 1100×850 and
talk Timing & playback sizes 760×580 and 920×760. Fusion is the wheel's native
available widget style; the system build uses Breeze. Palettes are changed only
inside the test process. The same presentation and capture script are used at
`ad4178d` and after the fixes.

All four comparison sheets were inspected, with full-size checks of the small
Breeze and Fusion inspectors and the Breeze Timing & playback page. Intended
changes: the literal ampersand appears; source/Reset moves beside the field title;
vertical stacking shrinks; the minimum inspector reserves scrollbar space and
no longer clips its right edge. Captions elide with full tooltips, Reset stays
visible, and wider windows expose more of the inspector below Timing. At the
minimum size the inspector content is exactly 200 logical pixels on both stacks
and scales. Existing vertical scrolling remains for content below the viewport.
Dialog sections, non-compact fields, Save/Cancel placement, themes and styling
are otherwise unchanged.

## Failed attempts and corrections

- The first focused run passed 88 tests on the wheel but had **2 failures / 86
  passed** on Breeze: native standard-button mnemonic markers failed the literal
  guard, and the 200 px outer scroll area left too little width for its content.
- Initial compact screenshots also showed “Pause after slide” wrapping. Titles
  now do not wrap, header gaps are 5 px, and the scroll container reserves native
  scrollbar width. A dedicated rerun passed both layout cases on both stacks.
- The strict mnemonic guard remains universal; it was not weakened to ignore
  native button boxes. Native shortcut comparisons were added instead.
- Final visual inspection prompted explicit right alignment of source captions.
  The visual matrix was recaptured after that final adjustment.
- The audio snapshot assertion for commit 1 did not pass because physical sink
  mute flags changed during the run, as recorded above. No physical audio control
  was changed to make that comparison pass.
- Private desktop/portal teardown warnings are retained separately from pytest
  outcomes. No Qt, driver, test marker or application dependency was modified.

The initial full wheel run passed 576 tests (191.91 s), but started before the
last source-caption alignment adjustment. Its log is retained as an intermediate
attempt, not the final wheel result. The final wheel suite is rerun with:

```sh
PYTHONPATH="$PWD/src" AUTOTALK_TEST_WM=1 .venv/bin/python \
  docs/reviews/evidence/2026-10-01-settings-refactor/full-tests.py settings-polish-c2-final-wheel wheel
```

That repeat and the final native run use frozen final source, independent private
Xvfb/WM sessions and separately named null sinks. Runtime version probes confirm
wheel Qt **6.11.2** and native Qt **6.10.2**. The final static checks also confirm
all six formatted modules still have no physical lines over 120 characters.

A full native run then found two pre-existing assertions in
`test_inspector_source_pause_and_delivery_independence` which required the entire
source caption in `.text()`. Its result was **2 failed / 574 passed** (247.33 s).
Those assertions are incompatible with the explicitly requested elision. The
source assertion now checks the full tooltip and additionally checks that the
visible text equals Qt's font-metric elision result. All pause persistence,
inheritance and delivery-independence assertions remain. The aligned wheel run
passed 576 tests before this test-contract update; it is retained as intermediate
coverage. Final full suites use the updated test on both stacks:

```sh
PYTHONPATH="$PWD/src" AUTOTALK_TEST_WM=1 .venv/bin/python \
  docs/reviews/evidence/2026-10-01-settings-refactor/full-tests.py settings-polish-release-wheel wheel
PYTHONPATH="$PWD/src" AUTOTALK_TEST_WM=1 .venv/bin/python \
  docs/reviews/evidence/2026-10-01-settings-refactor/full-tests.py settings-polish-release-native native
```

## Final results and accounting

| Commit | Stock Qt 6.11.2 | Native Qt 6.10.2/Breeze | Production delta | Test delta |
| --- | --- | --- | --- | --- |
| 1, formatting (`de09443`) | 561 passed, 185.01 s | 561 passed, 234.45 s | +582 / −206 = **+376** | **0** |
| 2, functional, against commit 1 | 576 passed, 191.24 s | 576 passed, 245.97 s | +48 / −14 = **+34** (ceiling +40) | +145 / −2 = **+143** |

Both final driver statuses are zero. All tests, including existing placement,
settings tab order, navigation, readiness and draft lifecycle checks, ran; no test
was removed or marked out. Fifteen parametrized cases were added. Two existing
raw-label assertions were adapted to the specified literal-ampersand/elision
contracts while preserving their behavioral assertions. Evidence/capture scripts
and reports are not included in production or test-file accounting.

Final `ruff check --select F src`: **0 findings**. Final pycodestyle selection:
**0 findings**. `git diff --check` is clean. The final diff was reviewed for new
state, duplicate policy and unnecessary mechanisms: rollback uses the existing
project owner/adopt path, compact display uses the existing eliding widget, and
standard-button setup has one owner. No parallel settings implementation remains.

The final wheel/native audio snapshots each show all four physical ALSA sinks
and six ALSA sources/monitors unchanged in mute, volume and active port. Test
null sinks were removed by the driver. This final audit does not erase the
separately documented commit 1 mute-state discrepancy.

Final full logs and audio snapshots are in
[`evidence/2026-10-01-settings-polish/commit2`](evidence/2026-10-01-settings-polish/commit2).
The [comparison sheets](evidence/2026-10-01-settings-polish/comparisons) cover all
32 before/after pairs and were reinspected after the final alignment change.
This verification is Linux-only; it makes no Windows/macOS or new GPU/Wayland
recording qualification claim.
