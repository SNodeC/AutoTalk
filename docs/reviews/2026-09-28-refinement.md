# Refinement following Claude’s second review

This implements the owner-approved plan following the
[second verdict](2026-09-28-claude-verdict.md), reviewed source `88351b8` and review
record `3bf17fa`. Preserve the current architecture, native appearance, all three
modes, fixed-scope settings, whole-deck planning, selected model/reasoning and
300-character speech splitting. Linux is the test target; Windows/macOS support
remains and QEMU testing remains deferred. F15 was retracted and needs no fix.

## F12/F13: readable native labels and selections

Commit `8d55bd0` escapes literal ampersands at the five mnemonic-aware Qt
button/action call sites; it does not change labels that are plain text or window
titles. Inherited after-slide choices now read “Talk: advance”, “Talk: wait” and
“Talk: live demo”, with an explanation in the combo’s tooltip. Stored values and
inheritance are unchanged. No inspector widening, new renderer or stylesheet
workaround was introduced.

The existing minimum-size interaction test now checks every option’s measured
text width against the native combo edit-field rectangle for all three inherited
values. Native Breeze light/dark, 100%/150%, minimum/normal sizes passed. Fresh
synthetic screenshots were inspected for the previously missing ampersands and
clipped selection. This is visual/interaction verification, not a recruited user study.

## F6: a reproduced unnecessary unload

Commit `132f754` fixes a concrete case: a manually preloaded, healthy model under
Never unload was stopped when the surrounding narration operation was canceled
or failed before using speech. This reproduced through the actual UI in both
Prepared and Realtime (four failing regressions before the fix).

The old speech-session exception handler treated every workflow exception as a
speech-protocol failure. The existing process state already distinguishes a
healthy borrowed session (`in_use`) from a failed/loading/generating one. Cleanup
now preserves the healthy session on an unrelated narration exception, subject
to the existing release policies. Generation becomes ready only after the worker
acknowledges batch completion; an interrupted synthesis leaves an unfinished
protocol and is still terminated. No additional readiness flag, owner or process
cache was introduced. The runtime change is net **-1 production line**.

The regressions check the same subprocess PID after cancellation/failure, project
reopening and a subsequent speech request. A separate regression verifies an
interrupted synthesis is terminated even with Never unload. This establishes one
cause matching the complaint; it does not prove that every historical report had
this cause. Backend/model/source/sampling changes and worker failure can still
require a reload. Policy-triggered release and explicit unload remain supported.

## F14: deterministic audio ownership

Commit `72008c4` adds explicit cleanup to existing owners. `AudioFile` supports
closing/context management; `Mix` closes superseded clips, narration, streamed
audio and background assets. A temporary standard-library ExitStack owns partially
constructed replacements until they are adopted. Export closes its mix on success,
cancellation and failure. Playback closes preview assets, superseded project mixes
and final shutdown resources. Pause/resume retains needed assets; closed timeline
objects retain timing metadata still used by the closing UI.

Deletion/refcounting is retained only as a fallback, not the normal lifecycle.
Reduction alone cannot close handles while an exception traceback or diagnostic
reference still owns an object. Explicit cleanup is needed at the existing
ownership boundaries; no parallel resource manager or persistent registry was added.

New checks retain diagnostic references/exception tracebacks deliberately and
assert handles close on replacement, export failure, invalid audio, cancellation,
preview stop and shutdown. They also cover partial replacement failure (previous
readable audio survives), repeated background/stream updates and pause retention.
Seven initial ownership checks failed before implementation; all pass afterward.
One intermediate shutdown change discarded timing metadata too early; existing
UI tests caught it, and the owner was corrected before acceptance.

## Acceptance-discovered preview navigation defect

The real-GPU journey exposed another lifecycle fault: selecting a thumbnail while
slide preview was playing or paused carried preview state into a paused presentation,
which disabled editing and generation. Commit `279aac3` ends the preview at the
existing `Playback.select` boundary before selecting the next slide. Normal
presentation navigation is unchanged. Both actual-thumbnail-click regressions failed
before and pass after the fix. This is an acceptance finding, not a finding attributed
to Claude. The full real-GPU journey subsequently passed.

## F7: measured startup improvement; target remains open

Five baseline and five candidate warm-model runs used the same isolated 24-slide,
30-minute talk. Each run measured Start to first visible slide plus Qt consuming
more than 0.1 seconds of audio. Model loading was excluded; the worker PID was
unchanged between preload and playback. This is not microphone measurement of
physical speakers. Original user projects and preferences were preserved.

| Run | Baseline startup (s) | Compact output startup (s) |
| --- | ---: | ---: |
| 1 | 63.00 | 48.45 |
| 2 | 66.01 | 46.69 |
| 3 | 62.09 | 52.08 |
| 4 | 68.70 | 52.29 |
| 5 | 62.98 | 49.13 |
| **Median** | **63.00** | **49.13** |

Commit `ba4aadb` promotes the tested instruction to request compact JSON, without
indentation or whitespace outside strings. This reduced the observed median by
approximately **22%**. It changes serialization guidance at the existing request
boundary: the same schema, whole-deck images/text, selected model/reasoning, factual
requirements, validation and speech splitting remain. It does not parse incomplete
JSON or substitute a smaller model. All five candidate plans validated, covered
slides 1–24 in order, retained the 1786.2-second speech allocation and preserved
specific source uncertainty. Content inspection was bounded, not proof that every
possible generated plan has equivalent quality.

A separate request-only protocol trace confirmed account-default `gpt-6-astra`,
low reasoning, for both requests. Baseline output used 1588 tokens and 5875 response
characters; compact output used 1211 tokens and 4876 characters. Neither request
reported cached input tokens. Request elapsed time was 70.22 versus 46.72 seconds.
These two diagnostic requests are not included in the five-run startup medians.

The runs were sequential groups, not randomized; external model latency varies.
The five candidate startups ranged **46.69–52.29 seconds**, so the required
**15–20 seconds remains unmet**. Whole-deck Codex planning still dominates startup.
A further change must preserve the agreed planning/content requirements and have
new measured evidence; this pass does not claim the target is solved.

## Verification

- Standard Qt 6.11.2 full suite: **365 passed in 77.07 seconds**, no skips.
- Native Qt 6.10.2/Breeze full suite: **365 passed in 95.41 seconds**, no skips.
- Native Breeze light/dark at 100%/150%: ten interaction checks per combination,
  at minimum and normal window sizes. Screenshots were inspected for native labels,
  selection fit and disclosure controls. This is not a recruited-user study.
- Real local Qwen GPU journey: PID **2611187** survived voice preview, both slides'
  synthesis, project reopening, cached Realtime, pause outside fullscreen, continue,
  presentation end, canceled narration and another real synthesis. Explicit unload
  succeeded. The narration cancellation used a deliberately stalled test client;
  the GPU worker and subsequent speech generation were real. Other retention
  policies are covered by regressions and earlier evidence, not a newly repeated
  real idle-timeout test in this pass.
- Fresh native bundle: direct xdotool keyboard/mouse interaction opened Application
  defaults, Talk settings and Slide settings; clean SIGINT exit and reload passed.
  SHA-256 checks matched 27 Qt libraries/plugins to their expected sources;
  all 18 mapped Qt libraries came from the bundle, Breeze loaded, and smoke exit
  was zero. The existing matching Qt Multimedia lifetime patch was retained.
- Windows/macOS were not tested locally; QEMU remains deferred.

Synthetic visual evidence:

- [Native Breeze dark at 150%, minimum window](evidence/2026-09-28-refinement/dark-editor.png).
- [Literal ampersand in the File menu, light at 150%](evidence/2026-09-28-refinement/file-menu.png).
- [Final packaged editor](evidence/2026-09-28-refinement/packaged-editor.png).

## Pending Wayland acceptance

The real Plasma portal check was launched and sharing permission requested from
the user. No Share confirmation was received. The test timed out waiting for
capture readiness after 240 seconds, with no recorded application error, then
closed. This is **unverified**, not a passing recording test or proof of a portal
regression. The live-demo, slides-finished/recording-continues and saved-video
acceptance sequence must be rerun after permission is granted.

## Scope and accounting

Compared with review record `3bf17fa`, production changed by **92 additions and
51 deletions: net +41 lines**. Tests changed by **211 additions and 3 deletions:
net +208 lines**. Documentation and evidence are separate. Combined with the
previous +189 production lines, the verdict refinement is **+230 of the approved
+250 allowance**. Most growth implements deterministic cleanup in existing owners;
there is no second state authority or resource registry. Each coherent change was
committed separately. The original Claude verdict is unchanged.

Raw measurements, logs and private deck content stay under ignored
`artifacts/refinement-2/`. Only synthetic screenshots are published. The native
Linux bundle is rebuilt for the local launcher; a running older application must
be restarted to use it. F7 and supervised Wayland acceptance remain open.
