# Language, speaker and delivery settings: reviewed findings

29 September 2026. Source: `c5f45d6136675eb66edbb7cf5e52ce1fb64eb225`.
Review only; production code is unchanged.

## Review record

The owner requested an independent deep Claude review extending beyond the
Chinese-to-German restart bug to intuitive handling of all related settings.

- [Claude's complete second-pass verdict](2026-09-29-claude-language-voice-verdict.md),
  preserved verbatim. Several recommendations and verification claims required
  correction; it must not be used alone as an implementation specification.
- [Claude's final corrective addendum](2026-09-29-claude-language-voice-corrections.md),
  which supersedes the affected parts of that verdict. Read these together.
- [Review method, executed checks and limits](2026-09-29-language-voice-review-method.md).
- [Original restart reproduction and anonymized saved-state evidence](2026-09-29-language-restart-reproduction.md).

This document is the coordinator's synthesis, not text attributed to Claude.
Claude's stable LV identifiers distinguish related manifestations from separate
defects. Sixteen numbered entries do **not** mean sixteen independently proven bugs.

## Findings that require attention

| Priority | Finding | Evidence and consequence |
| --- | --- | --- |
| High | Changing talk language retains old-language narration as ready (LV1) | Independently reproduced in project state and actual Qt settings. Start can regenerate audio from Chinese words labelled German without translating them. |
| High | Changing one slide's language has the same problem (LV2) | Independent project-state reproduction; the slide's resolved language changes while its words remain ready. |
| High | Application defaults and inheritance resets reach the same defect (LV9/LV10) | Independent probes plus actual Talk settings reset/Cancel interaction. A fix only in the talk dropdown misses these routes. |
| High | Persistence also matters | Coordinator probe: save a talk inheriting Chinese, reopen with German defaults; text remains Chinese and ready. The previous effective language is not retained in the manifest. |
| High | Readiness feedback conceals the error (LV3) | Actual Xvfb screenshot shows German selected with Chinese text, “Text ready: 2 / 2”, “Prepared slides: 0 / 2”, and disabled whole-talk text generation. This is a consequence of faulty text validity, not a separate progress-bar calculation bug. |
| Medium | Add language version unnecessarily flags deliberate slide-language overrides for translation (LV11) | Independent probe: a French-pinned slide stays effectively French in a new German version but is marked as needing translation anyway. |
| Medium | Language mutation has two authorities (LV4) | Source inspection: the property setter and `set_setting` differ, including version-name handling. Their callers must share one policy. |
| Medium / UX | The main language selector changes meaning after narration exists (LV5) | Source and rendered-state assessment: initially chooses a target language, later selects saved versions. The distinction needs to be apparent to ordinary users. |
| Optional efficiency | Speaker A → B → A may regenerate an existing A recording (LV13) | Independent silent-WAV probe: old A file survives, but the slide points to B's latest completion. File existence alone is insufficient evidence for safe reuse. |

## Important behavior to preserve

| User action | Required result |
| --- | --- |
| Change the effective target language | Affected inherited narration must need translation before synthesis. Counters reflect the resulting valid slides; they are not blindly set to zero. |
| Keep a deliberate slide-language override or explicit language passage | Preserve its language and authored content. Changes to unrelated defaults must not invalidate it. Mixed slides still need their affected inherited portions translated. |
| Select an already-prepared language version | Restore that version and reuse its matching completed audio. Preserve other versions. |
| Change predefined speaker, own/designed/saved voice, or spoken delivery | Preserve narration text; invalidate only audio whose actual synthesis inputs changed. Respect slide > talk > application precedence. |
| Change writing style | Guide subsequently created/revised words; do not silently overwrite authored narration or invalidate audio whose inputs are unchanged. |
| Use an inherited setting | Apply the same validity rules as explicitly selecting that effective value. “Use app” is not a bypass. |
| Save / Cancel / reopen | Commit or restore the appropriate scope consistently, and retain enough authored-language information for reopening to remain correct. |

Existing behavior already provides useful protections: voice/delivery changes
generally preserve words, saved versions isolate their slide/audio state, deliberate
language overrides can keep valid audio, dialog cancellation restores tested
scope changes, and streaming rejects mismatched speech identities. These should
be preserved rather than replaced by another workflow or approval mechanism.

## Implementation boundaries identified by the audit

The first suggested remedies were not ready to implement unchanged:

- Skipping mixed-language slides leaves a known subset of the original bug.
  Translation must preserve explicit portions structurally while handling the
  affected portions; one whole-slide readiness state can remain authoritative.
- An “untagged passage exists” predicate does not distinguish a slide explicitly
  pinned to French from one inheriting the talk language. Compare resolved source
  and destination language at the correct scope.
- Automatically pinning language on first text creation changes inheritance
  behavior and does not repair already populated inherited talks. Authored content
  language and current target language need coherent persistence semantics.
- An existing WAV path alone does not establish completed, intact audio, and does
  not restore duration/hash/provenance. Do not add a file-existence cache shortcut.
- A historical talk already re-synthesized under incorrect language metadata may
  pass all current readiness checks. Do not claim a generic stale-audio warning
  can detect it, or silently guess and rewrite its language.

The final implementation scope and production-line estimate require a coherent
design across these boundaries. The review does not authorize production growth
or establish that proposed fixes have passed tests. Startup optimization remains
deferred.

Two cautions remain even after Claude's addendum: computing a duration and a new
hash cannot prove that an interrupted WAV is complete or recover its original
provenance; the optional cache optimization remains deferred. Also, first-write
pinning alone is not sufficient while a populated version can subsequently be
reset to inheritance, saved and reopened. The addendum's sufficiency claim must
not be adopted without resolving that reset path and the intended inheritance
semantics. These are implementation-design limits, not reasons to weaken the
confirmed findings or leave a mixed-language exception to the correctness fix.

## Verification

Claude used independent synthetic state probes, real Qt settings controls under
Xvfb, source tracing and visual inspection of six captured screenshots. Its two
baseline runs passed 21 and 24 tests. The coordinator additionally ran the native
Qt/Xvfb scope/settings/version/Start suite: **69 passed, 2 deselected**. These suites
overlap. Newly reproduced defects show missing coverage despite the green baseline.

No real AI synthesis or listening-quality assessment was performed. The user's
running application and physical audio settings were left unchanged. Exact
commands, scope limitations, harness corrections and local evidence locations are
in the method document.
