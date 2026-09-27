# Independent Claude review brief — 27 September 2026

Requested by the AutoTalk owner. Review the complete current application, not just
recent diffs or known issues. This brief records the request; the independent
verdict will be recorded alongside it. No fixes are requested in this review.

Review branch: https://github.com/SNodeC/AutoTalk/tree/review/claude-ui-ux-2026-09-27
Repository: https://github.com/SNodeC/AutoTalk

## Product and user requirements

AutoTalk (`autotalk`) is a Python/Qt desktop application that turns PDF slides into
spoken presentations. Codex app-server supplies narration through the user's
ChatGPT subscription; local Qwen3-TTS 1.7B produces speech. Linux is the current
verification target, with Windows/macOS product support retained. GPU use and
installation/setup automation are required; NPU support and Windows QEMU testing
are deferred. Preserve native system appearance, palette and widget style (for
example KDE Breeze). The interactive prototype in docs/design is a previously
preferred visual reference; its interaction structure is not unquestionable.

An ordinary user should open a PDF, choose duration/language/voice, optionally
supply conference context through a URL or text, create/edit narration, prepare
or preview slide audio, present, pause/continue, stop, restart, and find recordings
without understanding AI internals or hunting through unexplained controls.

Three presentation modes must remain:
- Prepared: prepare everything before presentation, with optional editing/preview.
- Quick: simple prepare-and-start workflow with a reduced editing surface.
- Realtime: prepare opening audio and start while subsequent work continues.

The latest agreed implementation uses the same effective voice/model settings
across modes; older documents describe superseded Quick substitutions. Determine
actual behavior from code and identify documentation contradictions explicitly.

Required interactions and semantics:
- Separate Create/Rewrite slide text (Codex), Create slide audio (Qwen), and
  Play audio / Stop audio controls. Audio creation requires narration. Preserve
  usable existing audio in Realtime and after reopening when inputs are unchanged.
- Whole-talk text and audio preparation must be directly available without starting
  presentation. Do not replace Start with an implicit next-step/review dispatcher.
- Upper-right captions: Prepared = Prepare and start; Quick/Realtime = Start.
  No new audio approval workflow. Existing text edits must have clear persistence.
- Languages are selectable; multilingual versions and reference voices are supported.
  Distinguish predefined, own/reference and designed voices clearly. Voice character,
  pace and expression should remain consistent across slides.
- Do not replace the existing 300-character speech splitting in this review's
  recommendations without identifying that the user explicitly rejected that change.
  Shared delivery instructions and evaluation of both synthesis randomness stages
  were approved. Reference-voice reuse is supported, with its control tradeoffs.
- Conference/audience context, language, voice, model/reasoning, delivery and advanced
  synthesis settings must have clear scope and meaningful grouping.
- Three explicit settings dialogs are now required: Application defaults, Talk
  settings (named talk), Slide settings (numbered slide). The scope selector at the
  top of the current dialog is rejected. Shared inheritable settings should use
  consistent ordering/labels; distinguish inherently scope-specific settings.
  Slide overrides take precedence over talk defaults over application defaults.
  App values persist in application config; talk/slide values in talk JSON.
  Reuse editor/resolver code; three UI scopes must not mean three implementations.
- Explicit GPU load/unload and automatic load/unload policies, including Never
  unload, must be understandable and respected. Manual actions must interact
  logically with automatic policies. Avoid unnecessary model reloads.
- Realtime startup with the required speech model ALREADY LOADED must target
  approximately 15–20 seconds from Start to first audible narration and its slide.
  Include opening text/audio generation when not cached. Cached playback alone
  does not validate this requirement. Distinguish warm process, warm model,
  cold model, runtime initialization, Codex, synthesis and playback buffer timing.
- Progress must show actual stages and real measured completed/total work where
  possible, plus elapsed time. No invented percentages. Explain unmeasurable stages.
- Presentation display selection, Linux system audio routing, fullscreen resume,
  live demos, slide/audio export and live screen recording remain product requirements.
  Recording must clearly show active/continuing/saving/saved states and where files go.
- Common controls must be visible and reachable: P1 has the lowest interaction cost,
  P2/P3 may be progressively deeper. Related controls belong together. Explain why
  each action belongs in its menu/dialog/main window/sidebar/presentation window.
- Native conventions: ellipsis (…) for commands requiring a subsequent dialog/input;
  no ellipsis on immediate actions. Chevrons/arrows for actual menus/submenus or
  expandable sections, with visible state. Do not conflate ellipses and chevrons.
  Review button hierarchy, labels, checkbox recognition, numeric alignment,
  enabled/disabled states, keyboard access, minimum-size layout and scaling.

## Why the owner requested an independent review

After repeated refinements and overly strong completion claims, the owner considers
the overall UX unacceptable and wants its design reconsidered from ordinary user
tasks. Do not merely validate existing placement documents or passing tests.
Latest reported issues (docs/ROADMAP.md records them):
- Ctrl+C does not stop the terminal-launched application.
- Some settings remain disabled after conference scope extraction completes.
- After stopping the whole presentation process, the UI remains disabled and the
  user cannot return to editing/start again.
- Save delivery preset / Saved presets / Use preset have an unclear purpose and
  confusing relationship to Save reusable voice and the dialog's Save action.
- Raw ANSI terminal color escape sequences appear in Operation details.
- The speech model reportedly keeps unloading; selected policy/cause unconfirmed.
- Realtime startup is extremely slow even with the speech model loaded.
- Controls still appear arbitrarily placed; the scope dropdown is explicitly rejected.
- A missing talk-duration editor was just fixed at the top of Talk & preparation;
  do not mistake that fixed omission for an outstanding finding without checking.

## Required review output

Provide a candid independent verdict in Markdown covering ALL five areas:
1. Code quality and architecture: authoritative state, responsibility boundaries,
   lifecycle/cancellation, threading/signals, persistence/migration, cache correctness,
   duplication/coupling, error handling, platform boundaries, tests and maintainability.
2. Whole UI/UX: inspect all interaction groups, not only the issues above. Evaluate
   placements, grouping, scope clarity, discoverability, click cost by P1/P2/P3,
   ordinary-user usability and consistency across welcome/editor/Quick/presenter,
   menus, settings, voice/library, progress and recording/export surfaces.
3. Presentation startup timing: trace the actual critical path for each mode,
   especially warm-model Realtime; quantify only what you can measure or substantiate.
   Assess the 15–20-second target, progress observability, cache reuse, model retention,
   cancellation/restart. Separate measured results from hypotheses and estimates.
4. Overall application assessment: readiness, strengths, material defects, preserve
   versus refactor/rebuild decisions, ranked improvement sequence, concrete acceptance
   criteria. A greenfield UX proposal is welcome; a wholesale code rewrite needs evidence.
5. Button visuals and interaction conventions: explicit inventory of violations
   involving ellipses, chevrons, dropdowns/disclosures, action labels, state and hierarchy.

For each actionable finding include ID, severity/priority, concrete user scenario,
current behavior, expected behavior, evidence (file:line / screenshot / reproduced
steps), architectural cause if established, narrowest coherent remedy, and validation.
Provide a placement assessment table grouped by user task, with current/proposed
surface, visibility/click cost and verdict. Cover uncommon settings such as voice,
Codex model/reasoning, synthesis controls, GPU lifecycle and recording output.
Separate verified findings, reported-but-unreproduced issues, hypotheses and design
judgments. State scope/exclusions, tests run, timing limitations and review confidence.
Do not invent benchmarks or claim real user testing. Challenge this brief where
requirements conflict, while retaining the user's explicit product decisions.

## Engineering constraints and evidence

Inspect README.md, docs/USER_GUIDE.md, docs/ROADMAP.md, docs/VERIFICATION.md,
docs/design/* (including historical inventory, placement plan and interactive
prototype), then actual src/autotalk and tests. Historical documents are evidence,
not correctness authorities. The latest tested tree reports 319 full-suite tests
before the duration fix and 81 focused tests after it; independently assess coverage.
Use Linux native Qt/Breeze under Xvfb for UI verification. Inspect rendered screenshots
and exercise actual controls where possible; code review alone cannot establish
visual/interaction usability. No Windows/macOS execution claim without evidence.

Architectural rules: trace state/ownership/lifetime first, reduce before changing,
change before adding, avoid duplicate authorities and downstream workarounds.
Suggest the smallest coherent remedies; don't hide bad state with blanket enablement.
No production edits, git mutations, deployments or additional external communications
by the reviewer. Test scripts/evidence may be created under /tmp or ignored artifacts.
Do not read credentials or private account configuration. Do not publish screenshots
containing the user's slide content. Return the final report to stdout; the requesting
agent will store and commit it verbatim with provenance in this repository.
