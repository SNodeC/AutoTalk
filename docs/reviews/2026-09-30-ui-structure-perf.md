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
Production: +69/−2, net **+67** from base; tests: **+127**. Benchmark/evidence
scripts and documentation are counted separately. This already exceeds the
combined C1+C2 estimate of +60; the small explicit decorators and copy boundary
are retained for correctness and readability rather than compressed to meet an
estimate. Final combined accounting follows C2.
