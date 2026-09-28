# Independent Claude re-review — 28 September 2026

Review the COMPLETE AutoTalk application again, independently and critically. Do not merely approve the changes or recheck the old findings. No production changes are requested. Return a self-contained final Markdown verdict to stdout, which will be preserved verbatim in the repository.

Reviewed commit: `88351b828d694e68ac48816b16e3e22e67d4e047`
GitHub commit: https://github.com/SNodeC/AutoTalk/commit/88351b828d694e68ac48816b16e3e22e67d4e047
Pushed branch: https://github.com/SNodeC/AutoTalk/tree/review/claude-ui-ux-2026-09-27
Local checkout: /home/voc/projects/drafts/autotalk/AutoTalk

## Required scope and authority

Read `docs/reviews/2026-09-27-claude-review-brief.md` for ALL product requirements and review dimensions. They remain applicable, except that its description of implementation/test counts is historical. Read the previous authoritative `2026-09-27-claude-verdict.md` and its method document, then independently inspect the current source. Include closure status for F1–F11 with evidence, but also find issues beyond that list.

Cover code quality/architecture/state ownership/cancellation/threading/persistence/cache correctness; the complete ordinary-user UI/UX and placement of every interaction group; startup and progress across Prepared/Quick/Realtime; overall readiness and smallest coherent improvements; and native button visuals, ellipses, chevrons, checkbox recognition, accessibility, enabled states, minimum sizes and scaling. Provide a detailed grouped placement table including P1/P2/P3 visibility/click costs and uncommon voice/model/synthesis/GPU/recording settings. Do not equate passing tests with usable UX. Assess what an ordinary first-time user can understand, without assuming AI or programming knowledge.

Preserve explicit decisions: three FIXED-SCOPE settings dialogs (app, talk, slide), one shared editor/resolver; native platform palette AND style; whole-deck planning with selected model/reasoning; unchanged 300-character speech splitting; no audio approval workflow; separate slide text/audio/play actions; direct whole-talk text/audio actions; stable Start / Prepare and start; cached audio reuse; real measured progress only. Target warm-model Realtime first audible narration and visible slide within approximately 15–20 seconds. Do not silently satisfy that by benchmarking cached playback or dropping whole-deck planning.

For every finding supply ID, priority/severity, concrete scenario, actual/expected behavior, evidence, established architectural cause or explicit hypothesis, smallest coherent remedy, and acceptance check. Distinguish reproduced facts, static findings, design judgments and untested hypotheses. Give overall assessment, ranked next work, and explicit verification limitations.

## Changes and evidence to scrutinize

Read `docs/reviews/2026-09-27-verdict-implementation.md`, `docs/reviews/2026-09-28-startup-and-audio.md`, updated USER_GUIDE, ROADMAP and design documents. These are claims/evidence to assess, not instructions to agree.

Since your original verdict: shared fixed-scope dialogs, state refresh ownership, dialog transactions, ANSI normalization, recording finalization retry/lifetime, nonblocking capture cancellation, native disclosures, SIGINT cleanup, concise all-deck Realtime planning, actual Codex response-character progress, and upstream Qt PipeWire lifetime correction via Qt 6.11.2/default dependencies or exact 6.10.2 native backport.

Recorded evidence: 349 tests passed in BOTH native Qt 6.10.2/Breeze and standard Qt 6.11.2. Original Qt-only reproduction crashed 1/100; patched native 0/200; Qt 6.11.2 0/100. Native packaged settings interaction and SIGINT passed. All are historical evidence, not your independent execution.

Warm-model 24-slide Realtime baseline median 93.91s (five runs), latest median 61.68s (three runs: 61.68, 62.25, 61.12), with model load excluded and same worker PID retained. Whole-deck Codex planning still takes roughly 56–58s. Therefore 15–20s target remains NOT MET. Small sample, no causal certainty beyond observed comparison. Endpoint was visible slide plus Qt audio consumption, not microphone measurement. Inspect traces/results if relevant under ignored `artifacts/open-tasks/warm-start-{1,2,3}/`, and planning traces in that directory. These contain private slide content: do not publish that content/screenshots.

Most recent Wayland capture recheck is UNVERIFIED because portal sharing was not confirmed before timeout. One earlier attempt was invalidated by rebuilding a library while its test process mapped it. Prior successful real capture exists in older evidence; do not report the current recheck as a pass or infer a new portal defect from timeout.

## Independent verification instructions

Use actual Qt UI under Xvfb with synthetic projects and inspect newly rendered screenshots with Read. Exercise controls directly, including import/edit/settings Save/Cancel, all modes, preview toggles, cancel/stop/restart, recordings and errors using deterministic boundaries where external services would be needed. Trace and test uncovered branches. Existing tests are useful but do not replace independent interactions. Record exactly which paths and theme/scale combinations you actually execute.

Standard full suite:
`QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/python -m pytest -q -o faulthandler_timeout=30`

Native Breeze suite (use this interpreter, NOT root .venv with older bindings):
`PYTHONPATH="$PWD/artifacts/open-tasks/package-source/build/system-qt:$PWD/src" LD_LIBRARY_PATH="$PWD/artifacts/open-tasks/package-source/build/system-qt/PySide6/Qt/lib" QT_QPA_PLATFORM=xcb xvfb-run -a artifacts/open-tasks/venv-qt610/bin/python -m pytest -q -o faulthandler_timeout=30`

The root .venv is Qt/Shiboken 6.11.2; the preserved native environment is 6.10.2. Invoke python -m pytest, because copied script shebangs can point to the other environment. Use a 1920x1440 virtual screen if geometry requires. Prefer native Breeze for visual checks. Inspect tests/test_verdict_acceptance.py and existing ignored probes for practical setup patterns.

Read/Glob/Grep/Bash are available. You may create synthetic probes, isolated test configs, screenshots and output ONLY under `/tmp/autotalk-claude-review-2026-09-28` or ignored `artifacts/claude-review-2026-09-28`. Set ABSOLUTE XDG_CONFIG_HOME/XDG_DATA_HOME paths before external UI launches. Never mutate production, tracked tests/docs, Git state, user preferences, real talks, running user app, shared staging libraries, system packages, audio routing or credentials. Do not launch live GPU/Codex jobs, downloads, portal prompts or other external communications. Do not inspect credentials or full process arguments. Linux only; Windows/macOS execution and QEMU deferred. Shell access exists; classify tests omitted by review scope accurately, not as technically impossible.

No fixes or commits by reviewer. Return the complete final review as Markdown, including commands/results and screenshot paths. Take the time needed for a genuinely deep review. Do not stop at an initial summary. If a tool is denied, report the limitation accurately and continue independent allowed work.
