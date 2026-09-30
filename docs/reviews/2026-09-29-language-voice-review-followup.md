# Complete the language and voice review

Continue the same review with all original execution boundaries unchanged. Your
first verdict proves the core bug, but the owner's request covers intuitive voice
and language settings as a whole. Complete that broader review, then return a
COMPLETE revised standalone verdict, not just an addendum.

Please independently test these concerns rather than accepting my hypotheses:

1. Your application-default row says “seeds new talks only”, but `setting()` falls
   back to defaults for existing versions with an empty language. Follow
   `apply_defaults` and actual dialog edits: can existing populated talks inherit
   a changed application language without translation? Does “Use application” or
   “Use talk” create the same problem? Compare effective values before and after,
   rather than presence of an explicit version value. Do not add guards merely
   to preserve existing tests that omit validity assertions.
2. Your proposed talk-wide marking visits all slides: does it incorrectly flag
   deliberate slide-language overrides whose effective language did not change?
   Mixed explicitly tagged and untagged passages, language policies, and
   `add_version(translate=True)` copying slide overrides all need scrutiny. Is
   Add version really correct in ALL these cases? Preserve intentional overrides.
3. Voice/speaker correctness needs independent evidence beyond the digest. Read
   options bindings, saved voice selection/use, previews (`voice_context`),
   per-language references, Base versus CustomVoice/VoiceDesign instructions,
   sampling and delivery progression. Check actual UI edits, Save/Cancel and
   scope reset paths. Distinguish writing style (new words) from spoken delivery.
   Check changing speaker back: do old valid WAVs actually get reused, or does
   the single audio pointer prevent reuse? Avoid a blanket claim either way.
4. Trace playback, streaming mix and worker snapshots. Check changing settings
   before restart, paused/stopped/finished, plus independent slide audio actions.
   Inspect the relevant files, and run the focused relevant existing tests. No
   real speech engine/Codex calls or physical audio are needed or allowed.
5. Exercise real Qt settings controls under Xvfb with isolated QSettings and
   synthetic data. Include all three scopes, predefined speaker, Base reference,
   designed/saved voice selection, inheritance, Save/Cancel and language versions.
   Use deterministic service substitutes as needed. Capture fresh native-style
   settings screenshots and OPEN them with Read; assess labels, visibility of
   effective/inherited values and whether consequences are understandable to an
   ordinary user. Source inspection alone is not a complete usability review.
6. The proposed generic warning for an already mislabelled saved talk misses the
   actual inspected case: old Chinese words were already synthesized under German
   and `ready()` is TRUE. Do not invent a warning that cannot detect that case.
   State the honest limitation and propose explicit user-directed recovery using
   existing operations, without guessing language or automatic data rewriting.

Use the native Qt environment from the original brief. Do not run audio-device
tests or two GUI suites concurrently. Write probes and screenshots only to the
allowed scratch/artifact directories. Report exact test results and limitations.

Correct overbroad first-pass statements. Use stable LV identifiers where possible;
append new findings. Distinguish reproduced defects, static evidence, and design
recommendations. Include the complete setting-effects matrix and a coherent
minimal remedy estimate, with alternatives/tradeoffs if needed. Do not implement
production changes. Return the full verdict to stdout.
