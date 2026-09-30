# UI performance and surface ownership

Base: `4f21166`, unmerged `codex/ux-redundancy`. Implementation branch:
`codex/ui-structure-perf`. Linux verification only. This report is incremental;
C1–C4 are separate verification checkpoints, not a claim of completion.

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
