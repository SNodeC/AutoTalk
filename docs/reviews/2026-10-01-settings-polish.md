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
