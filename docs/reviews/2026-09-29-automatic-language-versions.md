# Automatic language-version selection

Historical stage: the owner subsequently rejected translation/copying between
languages. See [the current correction](2026-09-29-fresh-language-narration.md).

29 September 2026. Follow-up to the
[language-validity correction](2026-09-29-language-voice-fix.md).
The owner requested automatic selection/creation of language versions and rejected
a narration-recreation checkbox. This supersedes the earlier explicit Add-version
UX; that earlier report remains a record of its implementation stage.

## Invariant and implementation

Selecting a talk language must restore that language's existing narration/audio,
or create its translation draft without replacing the departing version. The
same rule applies through the main selector, Talk settings and the existing
project language setter. Slide overrides remain local to the slide.

The old unconditional `add_version` operation was reshaped into
`Project.select_language`. It selects a matching version or copies the current
slides only when no match exists. Before leaving an inherited-language version,
its resolved language is retained, so it remains identifiable when returning or
reopening. An unchanged target does not create another version. Existing named
versions remain accessible and their names are preserved; the main selector
shows their language alongside a custom name. Existing duplicates are retained,
not silently deleted; Talk settings keeps the current matching version or chooses
the first matching stored version when switching from another language.

Talk-level `set_setting` uses this operation. Its existing inheritance reset
selects the application language's version and restores inheritance there,
preserving the version being left. Application defaults remain defaults: directly
changing an inherited default still follows the authored-language validity rules
from the preceding fix. It is not a separate whole-talk version-selection control.

The main **Language** selector offers saved versions and all remaining supported
languages. The Add-version dialog/menu command and its handler were removed.
**Language options…** still opens the existing settings page. No new dialog,
checkbox, cache or persisted field was added. The existing project-adoption path
reloads the editor and playback timeline when settings select another version,
while retaining the selected slide. This prevents old-version text or audio from
remaining bound to the new selection. Main-selector changes save; settings retain
Save/Cancel semantics, including restoration of versions and unsaved source edits.

Prepared, Quick and Realtime share the selected version. Start reuses valid
completed audio. **Talk → Rewrite all talk text…** remains an explicit confirmed
operation, including in idle Realtime, and affects only the active version.

## Verification

- Before the change, eight new regression cases failed through both selection
  surfaces, settings cancellation and inheritance reset.
- Focused suite: 218 passed, 5 audio-device tests deselected; one failure was an
  old assertion requiring German to be absent until explicit Add-version creation.
  That test now checks the approved automatic workflow and source preservation.
  Existing tests calling the removed Add-version operation now exercise selection.
- Final Linux/native Qt/Xvfb suite: **412 passed, 8 audio-device tests deselected
  in 103.52 seconds**. All three modes and both main/settings selection routes
  restore Chinese/German text and prepared audio after reopening; the Start check
  verifies presentation begins without launching preparation. Other coverage
  includes inheritance, Cancel, mixed passages, named versions, persistence,
  migration, and an actual Realtime rewrite menu action with controlled generation.
- Separate native Breeze mouse/keyboard journey: **1 passed in 1.66 seconds**.
  Actual dropdown input creates German from Chinese; returning to Chinese restores
  its text/audio; Talk settings then restores prepared German. Screenshots were
  inspected directly. Generation fixtures use silent WAVs; no speakers were
  unmuted and no physical playback was needed.
- Linux PyInstaller bundle built using the existing native Qt/Breeze overlay.
  Packaged startup/exit checked under Xvfb with isolated config/data and no Codex
  on PATH. The Qt multimedia library is byte-identical to the previously verified
  Wayland lifetime-patched library, SHA-256
  `5537cedf957b657d492adf7371147c05446acc78021a116ba9b43fd33b05659f`.
- Final diff review found no old production Add-version path or new readiness
  authority. `git diff --check` passed.

[New German translation draft](evidence/2026-09-29-automatic-languages/02-german-created-automatically.png),
[Chinese restored](evidence/2026-09-29-automatic-languages/03-chinese-restored.png),
[German restored through settings](evidence/2026-09-29-automatic-languages/04-german-restored-through-settings.png).

Local detailed logs, pre-change source/test snapshot, screenshots and the
interaction harness are in ignored `artifacts/automatic-languages/`.

## Accounting and limits

Relative to the start of this follow-up: production **31 added / 28 removed,
net +3 lines**; tests **157 added / 26 removed, net +131 lines**. Combined with the
preceding uncommitted language correction, production growth is **net +6**, within
the previously approved 100-line ceiling. Growth connects existing selection and
settings behavior; the obsolete creation dialog/handler was removed in the same
change. Documentation and images are separate.

No real AI translation/speech-quality assessment, Windows/macOS tests, physical
sound-device tests or new live Wayland recording test was performed. User talks,
host audio settings and GPU configuration were not changed. Startup optimization
and optional historical voice-cache recovery remain deferred. The earlier
historically mislabelled-talk recovery limitation still applies; automatic version
selection cannot recover provenance missing from old content.
