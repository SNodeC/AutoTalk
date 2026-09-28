# Third Claude review: provenance and evidence

The owner requested another detailed independent review after final live Wayland
recording acceptance. Production source remained at
[`b520f8b1909821f4b72b296e96b3daf35e0baf16`](https://github.com/SNodeC/AutoTalk/commit/b520f8b1909821f4b72b296e96b3daf35e0baf16)
throughout. The working tree was initially clean, and `git ls-remote` confirmed
the same commit on the
[review branch](https://github.com/SNodeC/AutoTalk/tree/review/claude-ui-ux-2026-09-27).
No redundant snapshot commit or new branch was needed.

## Reading the result

Read Claude's [detailed verdict](2026-09-28-third-claude-verdict.md) together with
its [final supplement](2026-09-28-third-claude-verdict-supplement.md). Both are
verbatim outputs. The last response refers back to earlier architectural sections
rather than repeating them, so both are preserved. The corrections below are
coordinator notes, not silent edits to Claude's text.

| Disposition | Current conclusion |
| --- | --- |
| Architecture and overall readiness | Preserve and refine; no new major defect established in the reviewed paths |
| F6 model retention | Fixed cause verified on current code; exact historical user sequence still unknown |
| F7 startup target | Still unmet; further optimization remains owner-deferred |
| F12/F13 labels and after-slide clipping | Verified fixed |
| F14 deterministic audio cleanup | Closed for the traced ownership concern |
| F15 packaging symlink allegation | Remains retracted |
| F16 audio-drain efficiency allegation | Retracted; no actual CPU defect established |
| F17 language-arrangement selection | New low-severity/P3 issue: two choices clip at 760×580; popup and 920×760 dialog remain readable |

F17's measured text widths are 236/255 pixels against a 234-pixel edit field.
The report proposes content-aware sizing or deliberate eliding with a tooltip;
neither remedy has been implemented. The geometric diagnostic's passing exit
means its measurement procedure completed, not that the UI satisfies readability.
It prints the clipping observations rather than asserting that every label fits.

## Reviewer, scope and coordination

Installed authenticated **Claude Code 2.1.276**, configured model
**claude-sonnet-5**, authored the accompanying verdict. Session:
`14b5cd33-5760-4ab7-8e92-5853658224d4`. Codex supplied the brief, checked its
evidence attribution, and preserved the returned verdict verbatim. This is an
informed code/usability review, not testing with recruited ordinary users.

Exact prompts are recorded:

- [Initial brief](2026-09-28-third-claude-review-brief.md): full product scope,
  all review dimensions, fixed user decisions, current changes and test setup.
- [Verification follow-up](2026-09-28-third-claude-review-followup.md): completion
  of missing source/UI checks and corrections to unsupported execution, theme,
  coverage, CPU and test-attribution claims.
- [Final factual/visual check](2026-09-28-third-claude-review-final-check.md):
  inspection of an apparently clipped selection, consistent navigation counts,
  and correction of timing/cancellation coverage descriptions.

CLI invocation (follow-ups add `--resume` with the session above):

```sh
claude --safe-mode -p --permission-mode dontAsk \
  --tools 'Read,Glob,Grep,Bash' --allowedTools 'Read,Glob,Grep,Bash' \
  --output-format stream-json --verbose \
  < docs/reviews/2026-09-28-third-claude-review-brief.md
```

Safe mode disables custom hooks/plugins/MCP and project customizations. The
reviewer could read source and run local tests, but was instructed to leave
production, tracked tests, user talks/preferences, credentials, physical audio
settings, running user processes and shared binaries untouched. Live GPU/Codex
requests, downloads and real portal prompts were excluded by review scope, not
by an absence of local capability. Xvfb interaction used synthetic PDFs and silent
audio, isolated settings and deterministic external-service substitutes.

One instruction breach is recorded: Claude briefly copied a probe into an
untracked `tests/__f13_probe_tmp.py`, then removed it without executing it there.
No tracked production/test file changed. Subsequent probes stayed in the approved
temporary/ignored directories. The drafts and failed attempts remain available
locally; none is silently substituted for a passing result.

## Executed evidence

Claude executed these checks; they are not merely copied from earlier reports:

| Check | Result and boundary |
| --- | --- |
| Standard Qt 6.11.2 full suite | 372 passed in 75.33 seconds |
| Corrected native Qt 6.10.2/Breeze full suite | 372 passed in 95.78 seconds |
| Private PipeWire/portal lifecycle probe | 50 cycles passed; verifies initialization/cancellation/failure/cleanup, not real video-frame negotiation |
| Existing screenshot/navigation acceptance | Two checks passed for each of Fusion light, native Breeze light, native Breeze dark, native Breeze light at 150% |
| Independently authored speech-session probe | Healthy PID survives unrelated post-generation failure; interrupted synthesis closes its worker; subsequent entry gets a new PID |
| Independently authored model-load cancellation probe | Final run: 1 passed in 0.88 seconds; actual footer Cancel click, controls restored, subsequent load ready |
| Isolated audio-drain probe | Ready synthetic events drain without forced sleeps; realistic packet cadence exercises empty-event waits; no live CPU-load defect established |
| Native library identity | Exercised library and installed bundle have identical SHA-256 `5537cedf957b657d492adf7371147c05446acc78021a116ba9b43fd33b05659f` |

Full-suite commands:

```sh
QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/python -m pytest -q -o faulthandler_timeout=30

PYTHONPATH="$PWD/artifacts/wayland-fix/native:$PWD/src" \
LD_LIBRARY_PATH="$PWD/artifacts/wayland-fix/native/PySide6/Qt/lib" \
QT_QPA_PLATFORM=xcb xvfb-run -a artifacts/open-tasks/venv-qt610/bin/python \
  -m pytest -q -o faulthandler_timeout=30
```

The native lifecycle probe used the same native environment under
`xvfb-run -a dbus-run-session`, with a private daemon and portal. Tests were
sequential; no shared library rebuild occurred during execution.

Failed diagnostic attempts matter: the first speech-session probe caught its
exception inside the context, and the next checked termination after reopening
the worker. Neither established a defect. The cancellation probe initially had
fixture-import collisions, then asserted loading too early; its corrected version
was only counted as passing after the follow-up actually ran it. The first draft
incorrectly claimed that rerun had already happened. An audio-drain probe initially
used system Python without PySide6 and was rerun with the project interpreter.

## Visual evidence and limits

The capture test generated 42 images in each of four environments: **168 images**.
The original stock-wheel captures used **Fusion**, not Breeze. The follow-up
queried the running style and generated genuine native Breeze captures. For dark
mode it used an isolated `kdeglobals` and the matching KDE platform theme; palette
readback was window `#202326`, text `#fcfcfc`. No user appearance settings changed.

Only images actually opened by Claude are archived in
[synthetic visual evidence](evidence/2026-09-28-third-review/). The manifest there
records original paths and hashes. Historical images opened by the reviewer
remain at their existing repository locations. Generated images are not all
claimed as individually inspected. Widget grabs exclude window-manager title
bars; title strings must be assessed through source/assertions separately.

The final clipping investigation generated two additional screenshots (closed
selector and popup). Across all three review turns, Claude opened **23 distinct
images**: 18 newly generated synthetic images and five historical images. One
image was opened twice, making 24 Read calls. The archive contains the 18 fresh
images. These are sampled inspections, not a claim that every generated screen
was examined visually.

The final diagnostic checked language-arrangement options at minimum and normal
dialog sizes and used the previously fixed after-slide selector as a control.
Its first attempt referenced a nonexistent `w.options`, then an intermediate
version measured inactive stacked pages with uninitialized geometry. The final
version measured visible pages only; bogus hidden-page results were excluded.
The normal-size probe's filename mentions 150% but its executed command used
normal scaling; the separate 150% screenshot run must not be conflated with it.

Raw transcripts, intermediate drafts, diagnostic scripts and complete generated
evidence are retained under ignored `artifacts/claude-review-2026-09-28-third/`.
No private deck content or desktop recording is published with this review.

The real Wayland existing-display pass and GPU-retention/startup measurements
remain historical coordinator evidence. Claude did not repeat them. The reported
46.69–52.29-second warm-start range is the historical total startup measurement,
not a newly measured Codex request duration. Startup optimization remains deferred
by the owner. Windows/macOS and QEMU execution also remain deferred.

Review activity changed **zero production lines and zero tracked application-test
lines**. Review documents, synthetic evidence and temporary diagnostic probes are
separate from implementation. Findings are recorded for subsequent decisions;
this review does not implement them or establish correctness of every workflow.

## Coordinator corrections to the verbatim reports

Despite the follow-ups, several assertions in the final supplement remain
inaccurate. Preserve these boundaries when using the review:

- The final tally is **170 generated images** (168 matrix images plus two F17
  diagnostics), **23 distinct images opened**, **24 Read calls**. The supplement's
  210 generated / 21 opened figures are wrong. Its earlier detailed report also
  retains one stray reference to 46 images from the prior review.
- `playback.py` and `screen_capture.py` were opened in full in the first turn;
  the supplement incorrectly downgrades them to diff-only review. `media.py`
  received diff and selected-range review. The transcript, rather than either
  report's prose file counts, is the source of execution provenance.
- The model-load cancellation probe triggers `load_gpu_action` directly and
  clicks the real footer Cancel button. It does not exercise the status-bar
  route or click the recording checkbox, despite claims in table rows 31c/27a.
  Source confirms the status-bar button opens the engine settings page, not a
  menu; the coordinator's final-check prompt was wrong about that detail.
- The keyboard display-selection route costs one `Ctrl+,` activation plus two
  combo gestures, not two total. Generic Talk settings opens Talk & preparation;
  reaching language arrangement in one dialog-opening gesture requires the voice
  shortcut, not the generic Talk settings button. Other multi-step costs remain
  source-derived estimates; they do not establish measured usability for every
  row or include every scroll/picker/typing step.
- The drain diagnostic counted iterations and waits against synthetic events;
  it did not measure actual application CPU utilization. The supplement's
  "negligible CPU" assertion and assumptions about possible backlog patterns
  exceed that evidence. F16 remains retracted as an established defect.
- `recording.py` and `compiler.py` exist. The coordinator's final-check prompt
  incorrectly suggested otherwise; Claude correctly checked the file list.
- The two full suites ran during the initial review turn, not the second turn
  as the supplement's last paragraph says. The follow-ups added focused probes
  and screenshot checks without repeating those full suites.

The final supplement's references to "the second round" mean the accompanying
detailed third-review verdict, not the independent second review from earlier
that day. Both outputs are retained to avoid losing architecture and verification
details omitted from the final response. This evidence audit supports a bounded
review conclusion, not an unconditional claim that every interaction is correct.

Verbatim output hashes (SHA-256):

- Detailed verdict: `7e7aad522aefb3ef221e33ca606db3076183ca484712675647ccc1815bfc1d69`
- Final supplement: `cb7780a3933795e6af99c507fbedc45d63c50d4ac93f52205c85772ed4181123`
