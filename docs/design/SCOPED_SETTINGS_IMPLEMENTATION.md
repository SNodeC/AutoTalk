# Flat settings pages and three-level inheritance

Requested 27 September 2026. This supersedes the nested navigation introduced by
the canonical Settings consolidation. The user approved up to 500 net additional production lines for this change.
Implementation and Linux verification are recorded in [VERIFICATION.md](../VERIFICATION.md).

## Invariant

For an inheritable setting, the effective value is the explicit slide override,
otherwise the explicit talk override, otherwise the application default. The same
resolved values must drive presentation, voice summaries, preview, narration,
speech synthesis and audio validity. Missing overrides are different from zero,
empty text, false and an explicitly selected model default.

One Settings dialog remains. Its left navigation is flat and has five pages:

1. Voice & language: voice identity/source, language, writing style and delivery.
2. Talk & preparation: audience/conference, duration, mode and timing policies.
3. Presentation & recording: playback behaviour, recording, output and added audio.
4. AI & speech engine: Codex selection, Qwen options and GPU lifecycle.
5. Application: account, device preferences and general application settings.

Pages combine meaningful related settings rather than retaining the thirteen
old pages behind another navigation control. A scope selector exposes Application
defaults, This talk or This slide where applicable. Device and engine lifecycle
controls retain application scope; changing this selector cannot turn them into
talk or slide settings. Existing shortcuts select the concrete page, scope and
relevant control group. Current palette and native widget style are retained.

## Settings ownership

| Scope chain | Settings |
| --- | --- |
| Application → talk → slide | Voice identity; narration language; writing style; supported delivery attributes and directions; pause after slide; after-slide action |
| Application → talk | Language arrangement; Codex model/reasoning; advanced synthesis sampling; presentation mode; Quick timing; Realtime script strategy/priority/buffer; timing tolerance; recording intent/source/microphone/pause policy; export encoding; background gain/loop defaults |
| Application only | Account connection; model installation/update and GPU lifetime; device preferences; appearance/layout; reusable libraries |
| Talk only | Title, conference and sources, audience, objective, duration, language versions, background track, recording destination and gradual delivery across the talk |
| Slide only | Narration, notes, inclusion, explicit duration budget and additional audio clips |

The selected language version belongs to talk scope; it is not a fourth tier.
Slide overrides belong to that version's slide. Explicit passage language markers
remain content instructions and must satisfy the talk's language-arrangement rule.
Changing language does not translate existing text automatically.

Voice identity is an atomic selection, including its reference recordings. Vocal
attributes inherit individually. Supported controls depend on the effective voice;
the Qwen variant follows that voice rather than an independently conflicting choice.

## Concrete implementation boundaries

1. **Project/settings state — `project.py`, application preferences.** Introduce
   one allowlisted settings resolver and explicit override storage. Application
   defaults are stored in application config; talk/slide overrides in the talk
   JSON. Workers receive a resolved snapshot instead of reading live preferences.
   Replace direct effective-setting calculations at consumers rather than keeping
   a parallel policy. Migrate existing talk values to explicit overrides, preserving
   saved behaviour and existing audio when effective synthesis inputs are unchanged.

2. **Bindings and dialog — `ui.py`, `options.py`, `app.py`.** Replace the tree and
   thirteen pages with five combined pages. Reuse the field editors with explicit
   scope-aware bindings, inherited-value captions and removal of overrides. Keep
   ordinary controls direct; technical parameters remain under Advanced. Preserve
   pending edits while changing scope/page. One Save/Cancel transaction covers
   application defaults, talk overrides and slide overrides. Immediate account,
   engine, system-audio and explicit library operations stay clearly identified.
   Do not temporarily adopt a fake talk to edit application defaults.

3. **Voice identity — `project.py`, `voices.py`, voice actions in `app.py`.** Preserve
   recorded/imported/designed/predefined origin independently of the synthesis
   backend and user-assigned name. Accepting a design keeps its origin after its
   audio becomes a Base reference. Saved-library selection is not another voice
   type. Older ambiguous references are labelled Reference voice without guessing.
   Use the resolved identity in both talk and selected-slide summaries. Reuse the
   existing reference-copy/hash mechanism for portable talk assets.

4. **Generation and engine ownership — `services.py`, `runtime.py`.** Resolve
   language, writing and speech settings per slide. Preserve whole-talk context
   during narration generation. Replace the one-configuration-per-batch assumption
   with compatible batches through the existing single speech owner, including
   Realtime and explicit preload. Avoid holding the existing session guard across
   a transition that needs to acquire it again. Speaker changes within a compatible
   model should not trigger needless model reloads. Model-type changes may require
   loading and must report that work. Do not change the existing text splitting.

5. **Modes, cache and saved projects.** Prepared, Quick and Realtime share effective
   settings; remove Quick's hidden Ryan/Professional substitutions. Quick keeps
   its simplified start workflow. Audio fingerprints use effective synthesis inputs,
   not override provenance, so switching from inherited to explicit identical values
   preserves valid audio. Only affected slides become outdated. Keep existing words
   and saved files until explicit replacement succeeds. Playback and exports use the
   accepted artifacts, not newly resolved settings midway through an operation.

## Defaults and persistence semantics

Inheritance is live: changing an application default affects talks/slides that still
inherit that field. Show the affected scope when saving application defaults; do
not silently regenerate text or audio. An active job retains its starting snapshot.

Provide an explicit Keep these settings for this talk action to turn inherited
values into talk overrides and include required voice assets. This makes a talk
independent of another computer's defaults without another inheritance tier.
Account credentials and machine-specific choices are never copied into a talk.

## Verification

- Resolver precedence, removal of overrides, explicit empty/zero/false values and
  supported/unsupported vocal controls; effective-value equality preserves cache.
- Application config versus talk JSON persistence; migration and reopen with changed
  application defaults; pinning settings and copying the talk to another directory.
- Predefined, own and designed voices retain their displayed origin through preview,
  acceptance, library save/load and project reopen; library audition does not select.
- One flat dialog, five pages, shortcut page/scope routing, cross-scope Save/Cancel,
  application defaults without a talk and correct selected-slide/version binding.
- Whole-talk and per-slide text/audio generation, mixed-language validation and
  Prepared/Quick/Realtime use the same resolved settings; no text approval is added.
- Engine reuse and compatible/incompatible voice transitions, cancellation and
  progress; pre-existing valid audio avoids loading a model unnecessarily.
- Linux native Qt/Breeze Xvfb, minimum/default window sizes and 150% scaling; full
  regression suite, packaged launcher and library audit. Only Linux is tested.

## Accounting and approval

The prior approved limit was 160 net additional production lines from baseline
117fb8b. Before this pass, the tree used 101, leaving 59. Flattening navigation can reduce UI
code, but the existing model has no persisted application speech/language defaults
or general slide overrides, and generation is bound to talk-level speech config.
Moving widgets cannot supply those missing semantics.

Estimated additional production growth, after removing superseded paths:

| Area | Net lines |
| --- | ---: |
| Settings resolution, serialization and migration | 110–150 |
| Scope-aware editors and transaction changes, offset by navigation consolidation | 130–180 |
| Voice origin, summaries and library/reference persistence | 30–50 |
| Generation, mode and single-engine transition changes | 80–120 |
| **Total** | **350–500** |

Approved allowance: at most **500 net additional production lines from the current
tree** (601 total from 117fb8b). Tests and documentation are counted separately.
This is an estimate and ceiling, not a target. Final measured accounting is recorded with the verification results.
