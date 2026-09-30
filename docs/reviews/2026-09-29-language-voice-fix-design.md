# Language and voice corrections: implementation design

Historical stage: the owner subsequently rejected translation/copying between
languages. See [the current correction](2026-09-29-fresh-language-narration.md).

Source inspected: `c5f45d6136675eb66edbb7cf5e52ce1fb64eb225`.
The owner approved implementation with a ceiling of 100 net additional production
lines by replying “Continue”. Implementation and Linux verification are complete;
see [the implementation report](2026-09-29-language-voice-fix.md). The design and
approval estimate below are retained as the decision record.

## Governing invariant

Narration is ready only when its inherited words belong to the effective target
language. A deliberate passage language or slide-language override remains
authoritative. Readiness must survive defaults changes, inheritance resets,
Save/Cancel, version switching and reopening without guessing the language of
the text. Changing voice or spoken delivery must not rewrite narration.

The current `Slide.text_ready` is context-free and tests only that passages exist
and `narration_origin != 'translation'`. `Project.set_setting`, the independent
language property setter and direct application-default replacement can all
change the effective language without changing that state. `workflow`, counters,
audio preparation and streaming consume the resulting false positive. Saved
projects omit application defaults, so a transient before/after callback would
still miss reopening a talk under different defaults.

## Narrowest coherent change

1. Replace the persisted manual/generated/translation readiness convention with
   the language in which inherited narration was authored. The manual/generated
   distinction has no separate production behavior outside this convention.
   Derive readiness in `Project`, where slide > talk > application resolution
   already lives. Remove the old context-free readiness calculation and migrate
   every consumer; do not keep two readiness authorities or add invalidation
   callbacks to settings controls.
2. Route manual editor changes and accepted Codex output through one
   project-owned narration assignment operation. It records the effective
   language together with the words. Keep configuration inheritance unchanged:
   do not silently turn inherited settings into talk overrides on first typing.
3. Reuse the existing translation generation path for text whose authored
   language differs from the target. In a mixed slide, send the inherited portion
   for translation and retain the original explicit-language portions verbatim
   when applying the result. The parser allows an inherited prefix followed by
   explicit-language passages; no second per-passage readiness state is needed.
   Reject malformed output before committing a replacement.
4. Reuse the same derived readiness for Add language version. Preserve the source
   version and deliberate slide overrides; do not ask Codex to translate a
   French-pinned slide whose effective language remains French. Preserve valid
   completed audio references where synthesis identity is unchanged.
5. Consolidate the language property setter into the existing settings authority.
   Make the main selector explicitly a language-version selector, eliminating
   its silent change from editing a language to selecting a version. Keep target
   language editing in the existing settings and Add version interaction.
6. Correct readiness/status text to show the selected slide's effective target
   language, and update language-setting guidance. Preserve independent text,
   audio and playback buttons and stable Start behavior in all three modes.
   Existing audio may still be auditioned after an edit, as the owner previously
   requested; label it as previous audio when it is stale so a speaker/language
   change cannot make that audition appear current.

## Persistence and already-affected talks

Introduce a backed-up schema migration for the replacement narration metadata.
Preserve existing declared language/version information and intentional tags;
do not infer language from characters, filenames, or a stale audio hash. Previously
pending translations remain pending. For legacy inherited narration with no
stored language evidence, retain its words as source requiring language
preparation rather than silently certifying the new application default.

A historically mislabelled talk with an explicit German label but Chinese words
cannot be distinguished automatically from a genuinely German talk by the old
metadata. Existing user-directed rewriting/translation remains the recovery
route, preserving the original project/version. This limitation must remain
explicit; no generic cache warning can detect it after bad synthesis completed.
The running user application and its project are not to be silently modified.

## Deferred or non-defect findings

- Arbitrary speaker A → B → A cache recovery remains deferred, as in Claude's
  corrected recommendation. File presence, a readable WAV or a newly computed
  hash does not prove completed synthesis or restore discarded provenance. Do
  not add a second cache manifest or partial-file shortcut in this correction.
- Stale-stream rejection is existing correct protection; settings edits are
  disabled while generation is active. Preserve it.
- Voice-source tabs' transactional live preview and existing Save/Cancel remain;
  no new audio approval step, settings scope selector, layout redesign or model
  lifecycle change is needed.
- Startup optimization remains deferred. Existing audio artifacts are not
  deleted as an incidental cleanup.

## Regression and interaction checks

Use real Qt controls and isolated synthetic talks under Linux Xvfb, with external
AI replaced by deterministic responses and no audible playback:

- Talk/slide/application language changes and inheritance resets, including
  identical effective values, Cancel and save/reopen after defaults change.
- Untagged, fully explicit and mixed narration; overrides whose effective
  language changes versus overrides shielded from a talk/default change.
- Prepared, Quick and Realtime Start: translate only affected words before
  synthesis; counters and button states agree; no source-language audio is
  accepted as the changed target.
- Existing prepared language-version reuse and source-version preservation.
- Manual text editing, single-slide/whole-talk text and audio preparation, and
  explicit old-audio audition versus current audio readiness.
- Predefined/own/designed/saved voices, delivery changes, reference-language
  fallback and their scope resets: text stays unchanged, audio validity follows
  actual synthesis inputs, Save/Cancel and reopen retain the right values.
- Legacy schema migration, backups, pending translations and unknown inherited
  source language. Verify malformed generation cannot destroy authored content.
- Capture and inspect native-style screenshots of the changed visible states.

The unchanged-head baseline is already recorded: 69 native Qt/Xvfb tests passed,
2 deselected, plus Claude's separate probes. Do not count those as post-fix proof.

## Reduction, growth and approval boundary

Reduction removes the independent language setter policy and obsolete
context-free readiness/translation state. Reshaping existing callers and UI text
is largely line-neutral. Neither recovers authored-language information omitted
from saved talks nor provides structural preservation of explicit passages during
translation. Those responsibilities need additional persistence/transformation
logic in the existing model and services.

Expected net production growth: **about 60–90 lines; requested ceiling 100**,
including migration, shared narration assignment, protected translation and small
UI feedback changes, after related obsolete code is removed. No unrelated code
will be deleted to offset growth. Tests and review documentation are separate
and do not count toward that ceiling. If the complete coherent implementation
cannot fit this boundary, stop and explain before exceeding it.

At the original approval boundary no production changes had been made. The final
implementation adds 3 net production lines, within the approved ceiling.
