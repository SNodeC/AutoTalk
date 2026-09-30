# UI performance and surface ownership

Base: `4f21166`, unmerged `codex/ux-redundancy`. Implementation branch:
`codex/ui-structure-perf`. Linux verification only. C1–C4 are completed as separate verification checkpoints; the documented
measurement and Qt-popup qualifications below are part of the result.

## Invariants and measurement

A project query may be reused only within a synchronous UI pass. Outside that
pass, mutable project state remains authoritative. Memo state is neither a
manifest field nor part of worker copies. Project mutators invalidate the pass.

The committed `tools/bench_ui.py` builds audio-ready 20/60-slide fixtures without
network access or audio playback. Measurements are median nine repetitions,
offscreen on this machine with stock Qt 6.11.2. Profiling is a separate execution
and counts underlying query evaluations, not wrapper/cache lookups. Timings
exclude fixture restoration and queued painting. The synthetic fixture differs
from the steering brief, so the measured local baseline is used for ratios.

Command: `QT_QPA_PLATFORM=offscreen .venv/bin/python tools/bench_ui.py`.

| Checkpoint | Slides | Full refresh ms | Keystroke ms | Selection ms |
|---|---:|---:|---:|---:|
| Base | 20 | 26.455 | 11.274 | 30.527 |
| Base | 60 | 79.641 | 29.688 | 82.981 |
| C1 | 20 | 3.858 | 4.864 | 7.794 |
| C1 | 60 | 9.620 | 10.304 | 13.233 |

| Checkpoint, 60 slides | ready | speech_key | text_ready | asset |
|---|---:|---:|---:|---:|
| Base refresh | 722 | 722 | 1025 | 725 |
| Base keystroke | 247 | 247 | 550 | 239 |
| C1 refresh | 60 | 60 | 60 | 60 |
| C1 keystroke | 60 | 60 | 60 | 60 |

## C1 — pass-scoped queries

Query decorators retain values and ValueError arguments only during the context;
nested contexts share the outer memo. Exceptions are reconstructed without
retaining traceback frames. Mutator entry and exit invalidate the memo.
`__getstate__` excludes it from both shallow and deep worker copies. `asdict`
never sees it because it is not a dataclass field. The UI pass wrapper is used
for full refresh and timed readouts.

Randomized mutation sequences cover language versions, direct passage/override
writes between passes, inclusion and audio-key changes. Tests also exercise
nested passes, in-pass mutation, invalid language policy, copies, serialization,
and the 60-slide full-refresh query bound.

Failed attempt: the first decorator forwarded Qt signal arguments to parameterless
refresh, causing one focused test failure. Retaining a parameterless wrapper
restored Qt's signal argument-discarding behavior. Focused rerun: 15 passed.

Full-suite commands use `xvfb-run -a <python> -m pytest -q` with a private null
sink, leaving physical speaker/microphone mute and volume untouched. Python is
`.venv/bin/python` for the wheel and
`artifacts/open-tasks/venv-qt610/bin/python` for native Qt. Native additionally uses
`PYTHONPATH=$PWD/build/system-qt:$PWD/src` and
`LD_LIBRARY_PATH=$PWD/build/system-qt/PySide6/Qt/lib:$PWD/artifacts/open-tasks/venv-qt610/lib/python3.12/site-packages/shiboken6`.
The approved bundled Multimedia cleanup patch is unchanged.

Full-suite results and subsequent checkpoints are recorded below when verified.

The first wheel full run had one Account focus assertion fail (467 passed); the
unchanged test passed in isolation. The first native run inadvertently collected
nine draft C2 tests before that implementation existed (475 passed, two failed).
Those drafts were removed from collection and both complete suites repeated on
C1 alone. No tests were skipped, weakened or re-marked.

Diagnostic radon 6.0.1 was installed only into ignored
`artifacts/ui-structure-perf/analysis-tools` with
`python3 -m pip install --target artifacts/ui-structure-perf/analysis-tools radon`.
No application or development dependency declarations changed. The first attempt
with `.venv/bin/python -m pip` failed because that interpreter has no pip module.
C1 refresh complexity remains 115; splitting it is C3 work.

C1 checkpoint: wheel **468 passed in 95.80 s**, native/Breeze **468 passed in
119.83 s**. Exact driver:
`.venv/bin/python docs/reviews/evidence/2026-09-30-ui-structure-perf/full-tests.py c1-repeat`.
Production: +69/−2, net **+67** from base; tests: **+123**. Benchmark/evidence
scripts and documentation are counted separately. This already exceeds the
combined C1+C2 estimate of +60; the small explicit decorators and copy boundary
are retained for correctness and readability rather than compressed to meet an
estimate. Final combined accounting follows C2.

## C2 — source PDF checks

The in-memory signature contains source path, nanosecond mtime and size. It is
recorded only after a successful hash, reset for another project and after reload
installation, and never serialized. Activation/job-completion checks skip hashing
an unchanged signature. The six generation entrances pass `force=True` and retain
all existing guards and content-based prompt de-duplication. Missing/unreadable
sources retain the previous non-blocking behavior.

Focused command:
`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_pdf_check_cost.py tests/test_pdf_reload.py`
— **22 passed**. No implementation failure in this checkpoint.

C2 production: +18/−8, net **+10**; tests **+75**. Cumulative production from base:
+87/−10, net **+77**, 17 over the combined +60 estimate. The added lines make the
pass lifetime, exception and snapshot behavior explicit; C2 itself only adds ten
net production lines. This retains readable boundaries rather than shortening
error handling or introducing a broader cache architecture.

C2 checkpoint: wheel **477 passed in 96.01 s**, native/Breeze **477 passed in
120.17 s**. Driver: the same full-tests.py command with argument `c2`.

## C3 — refresh surfaces and narration coalescing

Frame, header, dialogs, slide list/row, editor, inspector, presenter, footer and
actions have explicit update methods. A full refresh shares one project pass.
Slide selection updates the dependent surfaces; document-wide configuration
changes explicitly request a full refresh. Narration edits update the editor and
current row immediately, then restart a single 150 ms aggregate timer. Focus-out,
other refreshes, Save, job start, presentation start, slide changes and Close flush
pending aggregates. No background thread or revision cache was introduced.

The widget-snapshot journey runs in Prepared, Quick and Realtime, including slide
selection, typing, include/after/pause, language selection, fake job completion,
preview start/stop and all settings dialogs followed by Cancel. It compares all
requested widget properties and item texts/tooltips before/after a full refresh.
Focused checks: 86 passed, including the existing language, settings and UX tests.

| Checkpoint | Slides | Full refresh ms | Keystroke ms | Selection ms | Aggregate flush ms |
|---|---:|---:|---:|---:|---:|
| C3 | 20 | 4.349 | 0.357 | 7.974 | 3.686 |
| C3 | 60 | 10.517 | 0.396 | 13.690 | 9.982 |

The committed JSON contains the exact measurements. At 60 slides full refresh is
**7.57× faster**, synchronous keystroke **74.97× faster** than the same-machine
baseline. Keystroke queries: ready=1, speech_key=1, text_ready=1, asset=1.
Coalesced aggregate queries: 60, 60, 60, 59 respectively.

Radon command:
`PYTHONPATH=artifacts/ui-structure-perf/analysis-tools .venv/bin/python -m radon cc src/autotalk/app.py -s`.
Refresh-family maximum CC is **20** (frame/presenter), full refresh **1**;
header/timing **19**, dialogs **17**, recordings **16**, editor **14**, slide row
**11**, actions **8**, footer **6**, inspector **4**, slide list **3**, flush **2**,
aggregate/request **1**. No refresh-family method exceeds 25.

C3 full suites: wheel **487 passed in 101.76 s**, native/Breeze **487 passed in
129.76 s**. Driver argument: `c3`. No full-suite failure at this checkpoint.

C3 production: +188/−58, net **+130**; tests **+113**. Cumulative production
from base is **+207**. The per-commit +80 estimate is exceeded by 50 lines:
explicit surface entry points, their no-project guards, derived enablement
properties and flush boundaries are retained instead of packing statements or
adding a generic dispatch abstraction. C4 will move these responsibilities to
the actual component owners.

## C4 — component ownership

`InspectorPanel` owns inclusion, after-slide, timing/pause and delivery/audio
entrances. The window retains only `inspector`, with no widget aliases. Fixed-scope
dialogs construct and render their own sections, including clips, background,
account and engine controls. SettingsPanel now creates editor/reset containers
before their single final placement; deferred construction rows are consumed and
deleted after building. There are no `takeRow` or `replaceWidget` calls in src.

The controller retains application operations, recording/session lifetime and
Save/Cancel coordination. Dialog-owned `before` snapshots are preserved. Explicit
begin/finish callbacks and operation/navigation signals replace reach-through to
window internals. The allowed window interface is documented in settings.py and
inspector.py and enforced by an AST test over settings.py/options.py/inspector.py.
Existing test assertions were retained; widget paths and moved mock targets were
updated mechanically. A new clip test verifies gain and placement rollback in
memory and after reopening. The conference/duration mutation handler remains in
the controller to preserve its original update behavior.

Keyboard traversal was measured on `4f21166` before changing ownership. Direct
field placement initially interleaved reset buttons; explicit tab ordering now
preserves the base order. A regression test compares all 93/92/90 named focusable
controls in application/talk/slide dialogs against the recorded base list.

One literal acceptance assertion needs a Qt-specific qualification: native
QComboBox popups are child QObjects but independent Qt.Popup windows. They cannot
have `window() == dialog` without changing native combo behavior. Tests require
that equality for all embedded content; popup children must belong to a native
combo popup whose owning combo's window is the dialog. This is not an application
exception, reparenting shim or alternate dialog implementation.

### Visual verification

Captured 55 native Qt/Breeze screenshots: all three modes at 940×680/1100×850;
all visible pages per scope at 760×580/920×760, including scroll positions;
inspector and recording pages in light/dark at 100%/150%. Each image was inspected
in contact sheets, with full-size checks of the changed regions. Window sizes
and dialog button containment are asserted by the capture script.

Capture commands (run with the native PYTHONPATH/LD_LIBRARY_PATH above):

```
QT_QPA_PLATFORM=xcb xvfb-run -a artifacts/open-tasks/venv-qt610/bin/python docs/reviews/evidence/2026-09-30-ui-structure-perf/screens.py
QT_SCALE_FACTOR=1.5 QT_QPA_PLATFORM=xcb xvfb-run -a artifacts/open-tasks/venv-qt610/bin/python docs/reviews/evidence/2026-09-30-ui-structure-perf/screens.py
```

The archived base set is actually under
`docs/reviews/evidence/2026-09-30-ux-redundancy/screens` (the brief omitted
`evidence`). Comparison tool:
` .venv/bin/python docs/reviews/evidence/2026-09-30-ui-structure-perf/compare-screens.py <base-directory> <current-directory>`.
The decoded RGBA pixels are compared without rescaling, tolerance or masking.

Against the archived set: **43/55 pixel-identical**. Every remaining delta:

| Images | Delta |
|---|---|
| main Prepared/Realtime, both sizes | Narration focus border |
| dialog-0-2, 760 part1 and 920 part0 | Loop checkbox focus indicator (76 pixels each) |
| recording-dark, 150%, top/bottom | Recording-source combo focus border |
| inspector-light, 100% | Narration focus border and temporary project path |
| inspector-light, 150% | Narration focus border |
| inspector-dark, 100%/150% | Temporary project path in status bar |

A fresh unmodified `4f21166` checkout was captured with the same script, native
libraries and machine to distinguish capture state from application changes.
**52/55 are exactly identical**. Only inspector-dark 100%/150% and inspector-light
100% differ, solely in the generated `/tmp/.../talk/talk.autotalk.json` status-bar
path. The fresh base reproduces the focus highlights above. Both complete sets
and pixel-count/bounding-box manifests are committed. Thus raw archived captures
are not claimed to be 55/55 identical; no layout, wording, styling or control
placement delta remains.

The first visual pass caught missing styled-background painting on the new
QWidget subclass; enabling Qt's WA_StyledBackground restored the existing Breeze
background without adding a stylesheet or changing the theme.

### Failed attempts and final verification

- First C4 focused run: 33 passed, two failures from an overly broad mechanical
  replacement that also changed Job.url. Restored the worker signal.
- Next focused runs: 66 passed twice. Ownership test initially treated native
  combo popups as embedded widgets, then used isAncestorOf across a window
  boundary; corrected it to verify the owning combo's window instead.
- First C4 full runs: wheel 466 passed/24 failed; native 468 passed/22 failed.
  Remaining old dynamic/reopened widget paths and conference mock targets caused
  the failures, alongside the popup test and one wheel focus assertion.
- A focused offscreen acceptance run had an accidental test import rename and a
  signal-cleanup timeout; the import was corrected and playback/signal acceptance
  retained in the normal Xvfb/full-audio-server runs.
- Next full runs: wheel 490 passed/one failed; native likewise, from the last
  `reopened.gpu_loading` test path. Its focused rerun passed after the path update.
- Another wheel run: 490 passed/one Account-focus failure, the same 30 ms focus
  assertion that was intermittent at C1. No assertions, timeouts or markers were
  relaxed. Final full-suite results follow below.
- An isolated development helper was first invoked with a wrong relative path;
  it made no edits and was rerun from the scratch checkout. Radon installation
  and the initial tab-order diagnostic's QWidget.window lookup errors were also
  corrected in diagnostic tooling only.

The last bare-Xvfb native run also hit the 30 ms language-menu focus assertion
(490 passed/one failed). The installed `xfwm4` was therefore started on the
private Xvfb display, with a private D-Bus session and temporary xfwm configuration.
No production desktop, window manager or test assertions were changed. The
focused UX suite passed 14 tests in that environment. The full-suite command is:

```
AUTOTALK_TEST_WM=1 .venv/bin/python docs/reviews/evidence/2026-09-30-ui-structure-perf/full-tests.py c4-managed
```

The driver expands this to `xvfb-run -a dbus-run-session -- <python>
.../xvfb-session.py <python> -m pytest -q`, retaining the same null-audio-sink and
native Qt environment. Private-session desktop portal daemons emitted shutdown
warnings (including a portal-kde KCrash message after the focused session); those
were session cleanup messages, not AutoTalk test-process crashes. No application
libraries were modified.

C4 additionally splits dialog synchronization into section/voice/engine/talk
methods. Maximum refresh/sync CC is **23** (SettingsDialog.sync); main-window
surface maximum remains **20**, InspectorPanel.refresh **4**. The AST ownership,
embedded-widget ownership, exact tab-order and clip-rollback tests pass.

| Final checkpoint | Slides | Full refresh ms | Keystroke ms | Selection ms | Aggregate flush ms |
|---|---:|---:|---:|---:|---:|
| C4 | 20 | 4.015 | 0.344 | 7.561 | 3.646 |
| C4 | 60 | 10.235 | 0.378 | 13.326 | 9.389 |

At 60 slides this is **7.78×** faster full refresh and **78.54×** faster synchronous
keystrokes than the recorded baseline. Counts remain 60/60/60/60 for full refresh
and 1/1/1/1 for keystrokes (ready/speech_key/text_ready/asset). Aggregates remain
within the per-pass limits. These are synthetic UI measurements, not speech-model
startup or synthesis measurements.

| Commit | Production added/deleted | Net production | Net from base | Tests added/deleted |
|---|---:|---:|---:|---:|
| C1 | 69 / 2 | +67 | +67 | 123 / 0 |
| C2 | 18 / 8 | +10 | +77 | 75 / 0 |
| C3 | 188 / 58 | +130 | +207 | 113 / 0 |
| C4 | 551 / 407 | +144 | +351 | 183 / 90 |

C4 is within its +150 ceiling. C1+C2 and C3 exceed their estimates for the explicit
lifetime/refresh boundaries described above. Tests total **+404 net lines**;
benchmark tools, verification scripts, screenshots and this report are separate.


Final C4 checkpoint on unchanged production sources: stock Qt **491 passed in
100.05 s**, native Qt/Breeze **491 passed in 123.38 s**. Both subprocesses exited
zero. The complete logs are committed as `c4-wheel.log` and `c4-native.log`.
Source hashes were checked against the frozen verification snapshot. Physical
ALSA sink/source mute and volume values match the initial C1 snapshot; private
null sinks were released by the driver. The approved bundled Qt Multimedia SHA256
remains `a7243f9b75189d79d97171bee23e388a135e1e1572571e392e424b9a9603782f`.

All four code checkpoints passed complete suites on both requested Qt builds.
No application runtime dependencies, schema, settings resolution, Codex/engine
protocol, audio fingerprints or platform support were changed. Windows/macOS and
live speech-model startup/synthesis were outside this Linux UI task.
