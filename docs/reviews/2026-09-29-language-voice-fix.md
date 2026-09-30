# Language and voice corrections: implementation and verification

Historical stage: the owner subsequently rejected translation/copying between
languages. See [the current correction](2026-09-29-fresh-language-narration.md).

29 September 2026. Based on `c5f45d6136675eb66edbb7cf5e52ce1fb64eb225`.
The owner approved the [implementation design](2026-09-29-language-voice-fix-design.md)
with a ceiling of 100 net additional production lines. Changes are in the working
tree; this report does not claim a commit or remote push.

The later [automatic language selection](2026-09-29-automatic-language-versions.md)
replaces the explicit Add-version interaction described below.

## Corrected responsibility

The governing invariant is now enforced by `Project.text_ready(slide)`: inherited
words are ready only when their persisted authored language matches the resolved
slide > talk > application target. Deliberate explicit-language passages remain
valid independently of that target. Voice and delivery changes affect synthesis
identity, not authored words.

The old context-free `Slide.text_ready` and manual/generated/translation origin
convention were replaced, not retained alongside the new authority. Manual editing
and accepted generation both use `Project.set_narration`. The language property
setter now delegates to the existing settings operation. Counters, buttons, Start,
synthesis and stream acceptance consume the same derived validity.

Language changes, inheritance resets and reopening under different application
defaults therefore prepare affected narration before creating its audio in
Prepared, Quick and Realtime. Explicit slide overrides remain authoritative.
When translating mixed content, only the inherited portion is submitted for
replacement; original tagged passages are retained verbatim. Invalid generated
language markers are rejected before replacement. A generated marker for the
current target is normalized so it cannot silently become a permanent override.

The main selector consistently selects **Language versions**. Target language is
edited in the existing settings. Pending translation names the selected slide's
resolved target. Stale audio can still be auditioned, labelled **Play previous
audio**. Creating a translated version preserves the source and reuses completed
matching audio for content whose effective synthesis inputs have not changed.
Independent text, audio and playback actions and mode-specific Start behavior
remain intact.

## Persistence and review disposition

Schema 5 stores authored language. Older schemas remain readable; first save
preserves an exact schema-numbered backup. Migration uses stored slide/version
language, leaves pending translations pending, and treats unrecorded inherited
language as unknown rather than assuming today's application default.

| Review entries | Disposition |
| --- | --- |
| LV1, LV2, LV3, LV9, LV10 | Fixed through authored-language validity across all scopes, counters, preparation modes and persistence. |
| LV4 | One language-setting policy. |
| LV5, LV7 | Stable version selector and corrected language guidance. |
| LV6 | Intentional tagged content preserved. |
| LV11 | New versions preserve deliberate overrides and matching completed audio. |
| LV12 | Mixed-slide translation preserves explicit passages structurally; no second per-passage readiness mechanism. |
| LV8 | Old artifact cleanup deferred; no incidental deletion of recordings. |
| LV13 | Optional arbitrary speaker A → B → A cache recovery deferred, as in the corrected review/design. File existence alone does not prove completed synthesis. |
| LV14 | Historical limitation documented, with explicit recovery below. |
| LV15 | Existing mismatched-stream rejection retained; settings are locked during generation. No observed defect requiring another notification mechanism. |
| LV16 | Existing transactional voice selection and Save/Cancel retained. |

An old talk already saved with Chinese words labelled as German cannot reliably
be detected from its old metadata. Select the intended target and use **Talk →
Rewrite all talk text…** once. To keep the original, create another version first
and rewrite in that version. Merely copying the same declared-language metadata
does not repair the historical mismatch. No private user project was modified.

## Executed verification

All checks used Linux. External generation in the interaction tests used
deterministic responses and silent WAV fixtures, not real Codex/Qwen requests.

- Before production changes, nine scope × mode reproductions failed, establishing
  the false-ready state (9 failed, 7 deselected).
- Final native Qt/Xvfb suite: **402 passed, 8 audio-device tests deselected in
  102.83 seconds**. Scope changes, resets, cancellation, save/reopen, versions,
  malformed generation, manual authoring, synthesis identity, preview and workflow
  regressions are covered. Legacy schema migration and exact backups are covered.
- Separate native Breeze pointer/keyboard journey: **1 passed in 1.89 seconds**.
  Selected German in Talk settings, saved, translated the selected slide, created
  audio, changed that slide's speaker to Aiden, and saved. Counters changed from
  0/2 text and audio to 1/2 each, then to 1/2 text and 0/2 audio. French-tagged
  words stayed unchanged. Playback was intercepted; no audible output occurred.
- Screenshots were inspected directly. This also revealed an orphan language-
  arrangement caption at Slide scope. Correcting the existing owning-form lookup
  fixes caption visibility without adding another visibility policy; a regression
  covers all three scopes. Final screenshots were captured after that correction.
- PyInstaller Linux executable rebuilt using the existing native Qt/Breeze
  overlay. Packaged executable launched and closed with `--smoke-test` under Xvfb,
  isolated config/data directories and a PATH excluding Codex; exit status 0.
  The headless log includes `kf.windowsystem: Could not find any platform plugin`;
  it did not prevent the smoke check. This is not a new live Wayland capture test.
- The bundled `libQt6Multimedia.so.6` matches the previous verified Wayland
  lifetime-patched library exactly: SHA-256
  `5537cedf957b657d492adf7371147c05446acc78021a116ba9b43fd33b05659f`.
  Breeze plugin, Qt source archive and patch provenance are retained.
- `git diff --check` passed. Final source search found the obsolete origin field
  only in legacy migration. No second readiness authority remains.

The first focused run exposed old tests assigning narration without its project
language context and a new assertion incorrectly expecting Quick's editor action
to be enabled. Tests now exercise project-owned authoring and preserve Quick's
intended controls. A later full run found an existing error-message expectation;
the production validation message now names the permitted language and preserves
that useful diagnostic. Tests were not removed or weakened to bypass validation.

Local detailed evidence is under ignored `artifacts/language-fix/`: `before.log`,
`focused-2.log`, `full-native-verified.log`, `visual-final.log`, `visual_journey.py`,
`build.log`, and `package-smoke.log`.

### Inspected visual evidence

- [Language changed; translation required](evidence/2026-09-29-language-fix/03-german-needs-translation.png).
- [First slide translated and audio prepared](evidence/2026-09-29-language-fix/04-first-slide-translated-and-prepared.png).
- [Slide speaker override; inherited language](evidence/2026-09-29-language-fix/05-slide-speaker-override.png).
- [Speaker change preserves words and invalidates audio](evidence/2026-09-29-language-fix/06-speaker-change-keeps-text.png).

## Accounting and limits

Production: **61 added, 58 removed, net +3 lines**. Tests: **289 added, 28 removed,
net +261 lines**, including two new regression files. Documentation and images
are separate. The small production growth records previously absent language
provenance and protects mixed content; obsolete origin/readiness and divergent
selector policy were removed rather than adding compensating callbacks.

Windows/macOS, physical audio-device tests, real AI translation/speech quality,
and another live Wayland permission/capture check were not performed. Speaker and
microphone settings, GPU configuration and user talks were left untouched.
Startup optimization remains deferred; this change makes no 15–20-second startup
claim. Optional historical voice-cache recovery and orphan artifact cleanup also
remain deferred as specified in the approved design.
