# Settings edit latency and slide navigation — PR A

Base: `ad5edc5` (main). Branch: `codex/edit-latency-and-navigation`.
Linux only. PR B remains a separate, dependent settings transaction refactor.

## Invariant and implementation

An inspector gesture mutates only the field it owns. `configuration_changed`
is the shared boundary for main-row and inspector edits: mutate, reload visible
dialogs, stop/rebuild the audio mix, and refresh the window once. Hidden dialogs
load when opened; hidden voice panels no longer create synthesis snapshots on
every refresh. Language selection retains automatic version selection and saving.

Freshness is compared before and after the mutation in one pass-cache lifetime.
The user explicitly approved **up to two readiness passes (120 evaluations at
60 slides)** because mutators invalidate the first set of answers. Metadata and
budget edits do not affect speech readiness and reuse answers within this pass.
Defaults, active-version changes and inclusion changes now have cache-invalidating
Project mutators, just like settings and narration. `speech_key` reads sampling
and progression directly through `setting`, avoiding construction of an entire
Delivery object for these scalar/dictionary inputs. Its inputs are unchanged.

Only other slides becoming stale produce an additional status/log line. It lists
at most three pages and an additional count. The pause explanation is used only
for inclusion changes with a measured `pause_after` difference. Status messages
survive redraws; loading a talk and completing a job restore the normal static hint.

Editor Previous/Next uses the slide-list selection path and includes excluded
slides. Presenter stopped/finished navigation selects included neighbours without
requiring all audio to be ready; active playback retains its previous gating.
Both use `Playback.neighbour`. View owns the shared menu commands and
Ctrl+PgUp/Ctrl+PgDn; Quick and modal dialogs disable them. Fullscreen navigation
and the Start/Continue gating are unchanged.

## Verification

Commands use the existing driver and a private null audio sink. They do not
unmute, reroute or change the physical speaker or microphone controls.

```sh
AUTOTALK_TEST_WM=1 .venv/bin/python \
  docs/reviews/evidence/2026-09-30-ui-structure-perf/full-tests.py pr-a-final
```

The driver runs the complete suite with a private Xvfb/xfwm4/D-Bus session, first
on stock Qt 6.11.2, then native Qt 6.10.2/Breeze with the existing Multimedia
cleanup patch. Final results and benchmark evidence are recorded below.

New tests cover field independence, action costs, inherited pause/last-slide
invalidations, stopped and active Presenter navigation, Editor/list equivalence,
shortcuts with narration/list focus, modal guards, and exception-safe inspector
loading. The surface equivalence journey now includes the additional edits and
both navigation pairs. Existing Codex tests open the relevant dialog before
checking its selectors; their discovery, saved-value and logout assertions remain.

Native screenshots cover Prepared/Quick/Realtime at 940×680 and 1100×850, plus a
stopped Presenter after excluding the last slide. Every image was visually
inspected. The fixture uses blank slide images and synthetic narration. The only
intended layout additions are the Editor navigation pair, single-line elided slide
information with a full tooltip, and the minimum 110-pixel narration area needed
to keep the existing small-window space requirement on Breeze.

## Failed attempts and corrections

- First focused run: 47 failed, 10 passed, 3 errors. Navigation queried the
  transport before its project was installed during adoption. The neighbour
  helper now returns no neighbour in that state.
- Second focused run: 3 failed, 54 passed. A normal footer redraw erased the new
  stale-audio notice. Resetting the static hint moved to lifecycle boundaries.
- New interaction run: 1 failed, 33 passed, 2 teardown/setup errors. A synthetic
  job fixture compared its first progress reparenting with a later setup, then
  left the fake job installed on assertion failure. The disabled-navigation
  case now compares immediately before/after the attempted click.
- First full runs: wheel 502 passed/14 failed; native 500 passed/16 failed.
  Hidden-selector assertions were moved to the user-visible opening boundary;
  clip gain reloads now avoid resetting unchanged spin values during typing;
  existing duration feedback was restored; the Breeze narration minimum is
  explicitly preserved. No behavior assertion or test marker was removed.
- Corrective focused run: 120 passed. Earlier navigation/placement focused run:
  62 passed.
- Private test-desktop services report portal registration warnings and a portal
  shutdown crash when their private D-Bus/Xvfb session ends. These are separate
  processes, after pytest exits, and are preserved in the logs.

## Same-machine benchmark

Stock Qt 6.11.2, offscreen, synthetic prepared talks at 20 and 60 slides,
15 repeats per action. Full raw results and query-body counts are in
[evidence](evidence/2026-10-01-edit-latency-and-navigation). The baseline worktree
used `ad5edc5` plus the benchmark tool from this PR. Editor baseline entries use
a slide-list click because the buttons did not exist.

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python \
  artifacts/edit-latency-and-navigation/base/tools/bench_ui.py --repeats 15
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/bench_ui.py --repeats 15
```

| 60-slide action | Before ms | After ms | Speedup | After readiness evaluations |
| --- | ---: | ---: | ---: | ---: |
| refresh | 10.193 | 7.492 | 1.36× | 60 |
| keystroke | 0.411 | 0.405 | 1.01× | 1 |
| selection | 11.924 | 9.317 | 1.28× | 60 |
| after | 90.595 | 17.464 | 5.19× | 120 |
| pause | 90.501 | 17.723 | 5.11× | 120 |
| budget | 90.123 | 11.224 | 8.03× | 60 |
| include | 91.274 | 18.966 | 4.81× | 120 |
| duration | 23.587 | 11.228 | 2.10× | 60 |
| record | 45.292 | 17.422 | 2.60× | 120 |
| mode | 35.385 | 17.410 | 2.03× | 120 |
| editor_next | 11.921 | 9.203 | 1.30× | 60 |
| editor_previous | 12.040 | 9.242 | 1.30× | 60 |
| aggregates | 10.502 | 7.724 | 1.36× | 60 |

Every measured inspector/main-row edit performs one full refresh, zero hidden
dialog loads and one `configuration_changed`. The extra comparisons stay at or
below the approved 120-evaluation limit. Metadata and budget changes need 60.
Editor button and slide-list navigation execute the same query counts; measured
button medians are no slower than the list-click median.

Radon command:

```sh
PYTHONPATH=artifacts/ui-structure-perf/analysis-tools .venv/bin/python -m radon cc \
  src/autotalk/app.py src/autotalk/inspector.py -s
```

`configuration_changed`: CC 19; `navigate_slide`: CC 9;
`refresh_presenter`: CC 23. No new application dependency.

## Final results and accounting

- Stock Qt 6.11.2: **518 passed**, 111.20 s.
- Native Qt 6.10.2/Breeze: **518 passed**, 137.48 s.
- A preceding complete run was 516 passed on stock Qt and 515 passed/1 failed
  on native Qt: the long-title layout exposed one-pixel clipping. The splitter
  minimum now derives from its child minimum heights and native handle width;
  the seven native layout cases passed before the final complete runs.
- Final review additionally tested switching to Quick without a nested refresh
  and no-talk defaults editing without marking a nonexistent document modified.
- Physical ALSA sinks/sources have identical mute, volume and active-port state
  before and after the final full-suite driver.
- Production from `ad5edc5`: **+190 / −100 = +90 lines**, including the benchmark
  tool (+18 net); application code alone is +72 net. Within the approved +100.
- Tests: **+239 / −2 = +237 lines**; no test deleted.

The additions provide the requested navigation controls and shared neighbour
lookup, truthful stale-slide feedback, pass-invalidating state mutators and the
expanded measurement tool. They replace the shared inspector handler and repeated
per-edit refresh chain. No dependencies or global caches were added.

Archived test logs have trailing whitespace removed for `git diff --check`;
their diagnostic text and results are otherwise unchanged.
