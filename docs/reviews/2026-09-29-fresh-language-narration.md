# Fresh narration for each language

29 September 2026. This implements the owner's corrected requirement and supersedes
the translation behavior in the earlier language-fix and automatic-version reports.

## Required behavior and invariant

A selected language owns its narration. If that language already exists, restore
its narration and matching audio. Otherwise, create an empty version: no copied
narration, generated notes, speech identity, audio path, duration or synthesis
provenance. The original version remains unchanged. Codex generates missing words
from the PDF, language, timing and applicable talk context, never by translating
another version's narration. Quick retains its existing context policy.

## Implementation

- `Project.select_language` retains existing version selection and builds new
  `Slide` records from the common PDF extraction and slide configuration. Inclusion,
  explicit settings, timing budgets and attached clips are retained; generated
  narration/audio are not. No new persistent fields or additional cache were added.
- `narration_result` no longer emits a translation instruction. Its current-text
  context contains only narration valid for that slide's effective language; a
  missing/stale narration contributes an empty string. Other language versions
  are not passed to Codex. Realtime planning follows the same boundary.
- Editor and presenter display only valid current-language narration. Missing
  content shows an empty editor and **Needs [language] narration**, with **Create
  slide text**. Settings changes and Cancel refresh that same selected-slide view.
  The previous translation-specific button/status wording was removed.
- Unfinished copied drafts from the previous build remain recoverable on disk,
  but mismatched authored-language text is neither displayed as current narration
  nor submitted to Codex. Fresh generation replaces the active draft's missing
  narration. Existing source versions remain untouched.
- Explicit mixed-language passages intentionally authored in an existing slide
  remain deliberate overrides. They are not copied into a newly created version.
  Existing synthesis validation and atomic replacement checks remain intact.
- **Rewrite all talk text…** remains available in idle Realtime and changes only
  the active version after confirmation. No recreation checkbox was introduced.

## Executed verification

Before production changes, all seven new regression cases failed. After the
change they pass through both main and Talk-settings selection in Prepared,
Quick and Realtime, plus reopening an old copied draft. Checks assert an empty
editor/presenter, no copied speech metadata, no source-language narration in Codex
input, fresh target-language output, and unchanged original text/audio after save
and reopen.

The first focused run then exposed 21 assertions requiring the superseded
translation behavior (161 passed, 2 deselected). Those expectations were updated
to the owner's corrected contract. Protection of deliberate mixed passages,
atomic rejection, inheritance, source preservation and audio validation remains
covered; tests were not removed to bypass failures.

Final Linux/native Qt/Xvfb suite: **419 passed, 8 audio-device tests deselected in
109.13 seconds**. This includes the existing version reuse, cancellation, migration,
settings and Realtime rewrite checks.

Separate native Breeze mouse/keyboard check: **1 passed in 1.52 seconds**. Actual
language dropdown input selects German and exposes an empty editor. Clicking
**Create slide text** runs a controlled Codex response from PDF context. Returning
to Chinese restores its original narration and prepared audio. All three captured
screenshots were directly inspected:

- [German narration is empty](evidence/2026-09-29-fresh-language/01-german-empty.png).
- [Fresh German narration created](evidence/2026-09-29-fresh-language/02-german-freshly-created.png).
- [Original Chinese restored](evidence/2026-09-29-fresh-language/03-chinese-preserved.png).

PyInstaller Linux build and isolated packaged `--smoke-test` succeeded, exit 0.
Runtime file comparison found only ZIP-container metadata/order differences in
`base_library.zip`; every member's content matched. All other bundled runtime
files were byte-identical, including the verified Wayland Qt multimedia library.
This permits atomic replacement of the executable while the old process continues
using its original executable inode and unchanged runtime files. The previous
executable is retained in the ignored evidence directory. Restart AutoTalk to load
the corrected code. Source and packaged documentation have been updated.

Detailed logs, pre-change snapshot and interaction harness are under ignored
`artifacts/fresh-language/`. `git diff --check` passed.

## Accounting and limits

Relative to this correction's starting tree: production **18 added / 17 removed,
net +1 line**; tests **118 added / 33 removed, net +85 lines**. The small production
increase comes from creating empty slide records and sharing current-language text
between both views; the translation instruction was deleted. Combined uncommitted
production growth across these language corrections is net +7, within the approved
100-line ceiling. Documentation and screenshots are separate.

Only Linux was tested. External generation used deterministic test responses and
silent WAVs; no real AI language-quality assessment or physical playback was
performed. User talks, speaker/microphone settings and GPU configuration were not
modified. Startup performance work remains deferred.

Old content already mislabelled as the target language cannot be detected from
incorrect metadata alone. Such historically corrupted content still requires an
explicit rewrite; this correction does not guess its language or silently alter
private user projects.
