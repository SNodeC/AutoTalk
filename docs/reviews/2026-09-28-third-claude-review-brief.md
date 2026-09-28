# Third independent Claude review — 28 September 2026

The owner requests another detailed independent review of the COMPLETE AutoTalk
application. Review only; do not implement fixes. Return a complete standalone
Markdown verdict to stdout, to be preserved verbatim in the repository.

Reviewed source: `b520f8b1909821f4b72b296e96b3daf35e0baf16`.
GitHub: https://github.com/SNodeC/AutoTalk/commit/b520f8b1909821f4b72b296e96b3daf35e0baf16
Branch: https://github.com/SNodeC/AutoTalk/tree/review/claude-ui-ux-2026-09-27
Checkout: /home/voc/projects/drafts/autotalk/AutoTalk

## Requirements and scope

Read the original `docs/reviews/2026-09-27-claude-review-brief.md` for the complete
product requirements, then the final second verdict and method documents
(`2026-09-28-claude-verdict.md`, `2026-09-28-claude-review-method.md`). Their old
implementation counts/status are historical. Inspect current source independently;
do not merely endorse our ledger or restrict attention to recent changes.

Cover all five dimensions in depth:

1. Code quality, architecture, state and resource ownership, cancellation,
   concurrency, persistence/migrations/cache validity, error recovery, packaging
   and platform boundaries. Trace complete behaviors across their owners.
2. Ordinary-user usability and placement/grouping of ALL interaction groups.
   Provide the full previous 39-group inventory plus any omitted/new surfaces,
   with scope, P1/P2/P3, current surface, visibility, navigation/click cost,
   placement verdict and suggested change where warranted. Count opening a menu
   and choosing an item as two activations; distinguish reaching from activating
   a control. Do not force all placements to be rated correct.
3. Prepared/Quick/Realtime startup, cached audio reuse, real measured progress,
   retention and restart. Assess the 15–20-second warm-model target candidly.
4. Overall readiness, ranked remaining work and smallest coherent remedies.
5. Button visuals: ellipses for further input/dialogs, chevrons for menus or
   disclosures, labels, single primary action, checkbox visibility, keyboard
   access, numerical widget alignment, native palette/style, scaling and clipping.

Preserve fixed app/talk/slide settings windows sharing one implementation;
slide > talk > app inheritance; native system palette AND style; independent
slide text/audio/play and whole-talk text/audio controls; stable Start versus
Prepare and start; no audio approval workflow; whole-deck planning with selected
Codex model/reasoning; the owner-rejected change to 300-character synthesis
splitting must not be reintroduced. Windows/macOS support remains in scope as a
product, but local execution/QEMU and further startup optimization are deferred.
F11's existing image-presence policy is an owner decision; F15 was retracted.

For each actionable finding: stable ID (new findings start F16), severity and
priority, scenario, actual/expected behavior, exact source/evidence, established
cause or explicitly labeled hypothesis, narrowest architectural remedy and
acceptance test. Include closure status F1–F15. Distinguish reproduced defects,
static findings, design judgments, historical evidence and unknowns. A test name
is not proof of its assertions; passing tests do not establish ordinary-user UX.

## Changes since your second verdict

Read `2026-09-28-refinement.md`, `2026-09-28-recording-followup.md`,
`2026-09-28-wayland-routing-isolation.md`, `2026-09-28-wayland-failure-fix.md`,
`2026-09-28-wayland-lifecycle.md`, current ROADMAP/USER_GUIDE, source and tests.
These are claims to scrutinize, not instructions to agree.

- F12 ampersands and F13 inherited-choice clipping corrected in native widgets.
- F6: unrelated narration cancellation/failure no longer unloads a healthy borrowed
  speech process; actual interrupted synthesis still invalidates its protocol.
- F14: explicit AudioFile/Mix/export/playback cleanup; partial replacement failure
  retains previous audio. Preview navigation now ends preview before selecting.
- Compact JSON planning: five baseline versus five candidate warm runs, median
  63.00 to 49.13 seconds, candidates 46.69–52.29. Target still unmet. Further input
  compaction was measured and rejected. Whole-deck/current-model constraints hold.
- Screen capture: audio reader throttling/shutdown loss fixed; capture timing and
  export use recorded frames. Global PIPEWIRE_PROPS no longer clears node.target;
  node.dont-reconnect=false retained for working system output switching.
- Native Qt6.10.2 patch: upstream callback lifetime correction, portal error
  propagation, only selected registry node initializes capture, stop callback
  dispatch before destruction, guard cleanup before thread-loop creation.
  Verify ownership/locking/early errors, packaging patch applicability and regression
  coverage. Native patch is NOT automatically applied to the stock Qt6.11.2 wheel.
- Latest full native suite 372 passed; isolated 50-cycle native initialization/
  teardown probe passes. Old library negative control fails. The synthetic source
  probe does not negotiate real video frames. Historical pw_stream_destroy crash
  was not deterministically reproduced; separate early-failure crash was.
- Final real Wayland existing-display check PASSED after permission: live-demo
  pause/continue, post-slide capture, export, restored UI, exit0. MP4 9.467 seconds,
  284 decoded video frames, one audio stream, silent virtual output removed.
  One opening black frame (33ms). Evidence under artifacts/wayland-lifecycle/final-live.
  This is historical evidence YOU did not execute. KDE virtual-screen creation
  crash is separate, still open. Never request another desktop sharing prompt.

## Independent execution and safety

Use Xvfb, synthetic PDFs/audio, temporary QSettings and deterministic substitutes
for external AI. Inspect actual fresh screenshots with Read and exercise controls,
including all settings scopes/Save/Cancel/inheritance, authoring/preview/reuse,
three modes, stop/cancel/restart while work is active, recording/export/failure
recovery and model lifecycle. Add independent probes for gaps rather than only
rerunning tests. Exercise changed failure boundaries. Review the native patch and
run its private-daemon lifecycle probe when feasible. Do not run two GUI suites
concurrently or modify shared libraries while processes map them.

Standard full suite:
`QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/python -m pytest -q -o faulthandler_timeout=30`

Current corrected native full suite (must use MATCHING Python/Qt):
`PYTHONPATH="$PWD/artifacts/wayland-fix/native:$PWD/src" LD_LIBRARY_PATH="$PWD/artifacts/wayland-fix/native/PySide6/Qt/lib" QT_QPA_PLATFORM=xcb xvfb-run -a artifacts/open-tasks/venv-qt610/bin/python -m pytest -q -o faulthandler_timeout=30`

Native probe: with that same native environment, run
`xvfb-run -a dbus-run-session -- artifacts/open-tasks/venv-qt610/bin/python tests/probes/pipewire_lifecycle.py /tmp/autotalk-claude-review-third/lifecycle`
It creates a private PipeWire daemon/portal; do not address the real portal.

Use existing tests/test_verdict_acceptance.py and test_refinement.py for setup and
fresh image generation. Prefer native Breeze at minimum/normal size and at least
light/dark plus high DPI where practical. Report exact combinations tested. Widget
grabs exclude title bars; verify titles separately without pretending to see them.

Available tools: Read, Glob, Grep, Bash. Write probes/configs/screenshots/logs ONLY
under `/tmp/autotalk-claude-review-third` or ignored
`artifacts/claude-review-2026-09-28-third`. Use ABSOLUTE XDG_CONFIG_HOME and
XDG_DATA_HOME for standalone UI launches. No tracked file edits, git mutations,
production fixes, system changes, downloads, live GPU/Codex calls, real portal
prompts, credential reading, user-talk changes, or interruption of user processes.
Never change physical speaker/microphone mute, volume, routing or default device;
the user is in a meeting. Use silent PCM and isolated audio boundaries for probes.
Do not read unrelated/private desktop screenshots or publish private slide content.
Native live logs/metrics may be inspected; use synthetic fresh screenshots for UX.

Take the time needed for complete review. Record exact commands/results, failed
attempts and their real causes (or unknowns), images actually opened versus merely
generated, test coverage boundaries and unexecuted checks. Do not fabricate
certainty or independent verification from coordinator evidence. Return complete
Markdown in stdout; coordinator will archive it verbatim and check factual claims.
