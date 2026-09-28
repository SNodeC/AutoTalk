# AutoTalk — Third Independent Claude Review (Final)

**Repository:** SNodeC/AutoTalk · **Branch:** `review/claude-ui-ux-2026-09-27` · **Commit reviewed:** `b520f8b1909821f4b72b296e96b3daf35e0baf16`, confirmed via `git rev-parse HEAD` at the start of every session in this review, including this final pass. Working tree clean of any of my own changes; only coordinator-added review-record files are untracked.

This is the final, self-contained verdict after two rounds of correction. It supersedes both earlier drafts (retained locally, not part of this document). This pass fixes five further concrete issues: an unverified clipping claim now measured and confirmed as a new finding (F17), inconsistent click-cost arithmetic now made internally consistent with rows split wherever sub-actions genuinely differ, a conflation of two distinct historical timing measurements, an overstated reading of a pre-cancellation export test, and residual counting/file-list errors. Every substantive conclusion from the prior two passes that was not specifically challenged is retained unchanged.

---

## 0. What changed in this final pass, with evidence

### 0.1 New finding: F17 — "Language arrangement" combo clips at minimum dialog size

The coordinator asked me to inspect my own `evidence-native-dark/940-scope-1-page-0.png` more closely. I had opened this image in the prior round and described only its inheritance-button mechanism, missing the clipping now pointed out. Re-inspecting it:

> "Language arrangement" shows **"Separate versions and mixed passage"** — the final "s" is cut off, no ellipsis, right against the dropdown arrow.

**Measured, not just eyeballed**, using the same `QStyleOptionComboBox` + `subControlRect(SC_ComboBoxEditField)` technique as the project's own F13 regression test, at the dialog's own supported minimum size (760×580, resized from a 940×680 main window — exactly the size `tests/test_verdict_acceptance.py::test_pointer_navigation_all_fixed_scopes_and_native_disclosures` itself uses):

```
Voice & language page, dialog 760x580, combo "language_policy" ("Language arrangement"):
  CLIP  text=236px  field=234px  'Separate versions and mixed passages'   (clipped by 2px)
  CLIP  text=255px  field=234px  'Separate versions; one language per slide'  (clipped by 21px)
  OK    text=210px  field=234px  'Separate single-language versions'
```
**Control comparison, same session, same method:** the already-fixed `slide_after` combo (F13) passes cleanly for all three inherited states at the identical window size (81–137px text against a 159px field, all OK) — confirming this is a genuinely *different*, previously-unaddressed control, not a regression of F13.

**Popup vs. closed-state distinction, checked as requested:** I opened the actual dropdown and grabbed both states. The **popup itself renders all three choices fully, without truncation** — a user who opens the dropdown can read the complete text. The defect is specific to the **closed-state current-selection summary**, confirmed visually:
- `evidence-f17/f17-popup.png`: "Separate versions and mixed passages" / "Separate versions; one language per slide" / "Separate single-language versions" — all fully legible.
- `evidence-f17/f17-closed.png`: closed combo reads **"Separate versions; one language per sli▾"** — "sli" is visibly cut mid-word, immediately before the arrow, no ellipsis.

**Not reproduced at normal dialog size:** at 920×760 (the project's own "normal size" convention), the field widens to 394px and all three choices fit (`OK` for all three, measured).

**A first attempt at this measurement was itself wrong and corrected in front of you:** my first probe pass measured several *other* combos (`quick_timing`, `realtime_script`, `recording_policy`, `export_bitrate`) on pages/sections that were not the currently-active page in the dialog's stacked widget, or inside a still-collapsed disclosure — Qt had not laid these out, and `subControlRect` returned a degenerate ~21px field for all of them, which I nearly reported as thirteen more instances of clipping. That would have been wrong: a hidden widget's geometry is not a measurement of anything a user sees. I rewrote the probe to navigate to each combo's own active page/section before measuring; with that correction, `recording_source` (which *is* on-page and visible with its default settings) measures **OK** (137–181px text against a 264px field), and the mode-conditional combos (`quick_timing`/`realtime_script`/`speech_priority`, visible only in Quick/Realtime mode) and disclosure-gated combos (`recording_policy`, `export_bitrate`, inside collapsed "Advanced recording"/"Output quality") were correctly skipped as not applicable to this project's default Prepared-mode state, not measured as clipped.

**F17 — "Language arrangement" combo clips its current-selection text at minimum dialog size**
- **Severity:** Low (cosmetic; the popup remains fully readable, so information is not permanently hidden). **Priority:** P3 (a rarely-changed setting; USER_GUIDE frames it as advanced/infrequent).
- **Scenario:** Talk settings → Voice & language, at the minimum supported window/dialog size, with "Separate versions and mixed passages" (default) or "Separate versions; one language per slide" selected.
- **Evidence:** `evidence-native-dark/940-scope-1-page-0.png` (original discovery), `evidence-f17/f17-closed.png` + `evidence-f17/f17-popup.png` (this session's targeted reproduction and popup-vs-closed distinction), geometric measurements above.
- **Architectural cause:** `options.py`'s generic `combo()` helper (`options.py:138-144`) sizes every combo it creates via a fixed `setMinimumContentsLength(10)` rather than each combo's own actual longest item text. F13's fix addressed `slide_after` specifically (a different, `ui.py`-level `combo()` call) by shortening its inherited-value item text; it did not revisit `options.py`'s generic sizing helper or this specific combo's three (longer) choices.
- **Narrow remedy, two candidates (mirroring F13's own framing), neither committed:** (a) size this specific combo from its own longest item text rather than the fixed 10-character minimum; (b) enable eliding with a tooltip, consistent with the app's existing pattern of truncatable-with-tooltip summaries elsewhere.
- **Acceptance test:** a geometric check identical in shape to the existing `slide_after` regression, applied to `dialog.options.fields["language_policy"]` at the dialog's minimum supported size — confirmed this does **not** currently exist in the suite (only `slide_after` is covered), so this is a genuine, previously-unverified gap, not a re-discovery of an already-guarded control.

### 0.2 Click-cost table — Act defined consistently, inconsistent rows corrected (item 2)

**Corrected convention, stated once:** **Act ≥ 1 for every real control activation.** A single click on an always-reachable, single-purpose button is **Act = 1**, never 0 — reaching it does not itself count as free. **Act = 0 is reserved strictly for pure-observation displays with nothing to click** (a progress bar, status text). **Reach** = clicks needed to bring the control into view/focus, not including operating it. **Total = Reach + Act.** Where a task's real sub-actions have genuinely different costs (a spinbox vs. a combo box; three different sub-controls on one page; three different UI entry points to the same action), the row is **split** rather than averaged or ranged, per the coordinator's instruction — this is a factual correction, not a redesign proposal.

**Four specific corrections, verified against source this session:**

1. **Duration vs. language were wrongly merged into one row/cost.** `w.minutes` is a `QDoubleSpinBox` (focus + type/spin = Act 1); `w.language` is a `QComboBox` (open + choose = Act 2). Split into 4a/4b below.
2. **Application settings' mouse-route reach was undercounted.** There is no always-visible toolbar button for it (unlike Talk settings' `talk_button`); the mouse route is genuinely Settings menu (1) → "Application settings…" item (1) = **Reach 2**, not 1. The keyboard route (`Ctrl+,`) remains a single activation.
3. **The GPU-load status-bar route only *reaches* the control; it does not activate it.** `w.engine_status`'s click handler opens the settings dialog to the right page (`w.engine_action.trigger()`) — the user must then separately click "Load model now" inside that now-open dialog. This route is **Reach 1, Act 1, Total 2**, not Total 1. The genuinely different Settings-menu-direct route (`w.load_gpu_action`, a `QAction` that calls `w.load_gpu` immediately, no dialog) really is Total 2 as well (menu 1 + item 1), but via a structurally different, lower-friction path (no dialog navigation at all) — worth stating as a specific, favorable placement observation, not collapsing into a single "1–3" range as before.
4. **Recording enable+source+mic+destination bundled four different sub-controls under one imprecise Act range.** Split into 27a–27d below, each with source-verified widget type and cost.

**Rows I did not re-verify interactively this session** (marked "(source-derived)" below) reflect careful reading of `ui.py`/`settings.py`/`options.py`, not click-through confirmation with `qtbot` — these are estimates of a complete, multi-step dialog interaction, not measurements. Rows I actually exercised interactively this session (clicking real controls, or measuring real rendered geometry) are marked "(exercised)".

**Complete corrected table:**

| # | Task | Surface | Scope | P | Reach | Act | Total | Depth | Note |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Open a PDF | Toolbar (`ui.py:364-369`), always visible | app | P1 | 0 | 1 | 1 | source | Three equivalent entries, one handler |
| 2 | Open saved talk | Toolbar (0+1=1); Open recent submenu (menu 1 + submenu-open 1 + item 1 = 3) | app | P1 | 0/2 | 1/1 | 1/3 | source | Chevron submenu correct |
| 3 | Save / Save a copy | Toolbar (0+1=1, direct write); "Save a copy…" (1+1=2, dialog) | talk | P1/P3 | 0/1 | 1 | 1/2 | source | Ellipsis correct on dialog variant only |
| **4a** | **Duration (quick switch)** | Toolbar `w.minutes`, always visible spinbox | talk | P1 | 0 | 1 | 1 | source | Focus+type/spin; typing not counted beyond focus |
| **4b** | **Language (quick switch)** | Toolbar `w.language`, always visible combo | talk | P1 | 0 | 2 | 2 | source | **Corrected: open+choose, was wrongly merged with duration's cost of 1** |
| 5 | Conference/audience/context | "Talk settings…" (1) → lands directly on Talk & preparation | talk | P2 | 1 | 1 | 2 | source | Fields on-page, no further nav |
| 6 | Codex model & reasoning (talk) | "Talk settings…" (1) → nav "AI & speech engine" (1) → combo open+choose (2) | talk | P2 | 2 | 2 | 4 | source | Reaching the page is not reaching the setting |
| 7 | Sign in/out ChatGPT | Footer button, shown only when actionable | app | P1/P3 | 0/2 | 1 | 1/3 | source | Zero-cost when relevant |
| 8 | Voice: predefined | "Voice & speech…" (1, lands directly on Voice & language, tab persists) | talk/slide | P2 | 1 | 0 (view) / 2 (change name) | 1/3 | source | View vs. change distinguished |
| 9 | Voice: my voice | Button (1) + "My voice" tab (1) | talk/slide | P2 | 2 | 2 (record) or 1 (import) + 1 (transcript focus) | 4–5 | source-derived | Record/import/transcript itemized; not clicked through end-to-end this session |
| 10 | Voice: designed | Button (1) + "Design" tab (1) | talk/slide | P2 | 2 | 3 (describe+listen+accept) | 5 | source-derived | — |
| 11 | Voice: saved/library | Button (1) + "Saved" tab (1) | talk/slide | P2/P3 | 2 | 2 (select row+use) | 4 | source-derived | Correctly separated from "create" tabs |
| 12 | Delivery/presets | Same page, below Voice (scroll); disclosure | talk/slide | P2/P3 | 1 | 1–2 | 2–3 | source-derived | Placement fine |
| 13 | Multilingual versions/passages | Language combo→"Add version…" (0+2); per-slide "Insert language passage…" (0+1) | talk/slide | P1/P2 | 0 | 1–2 | 1/2 | source | Good split |
| **13b** | **Language arrangement (language_policy)** | Talk settings (1) → lands on Voice & language (Reach 1); combo open+choose (2) | talk | P3 | 1 | 2 | 3 | **exercised** | **F17: current-selection clips for 2 of 3 choices at minimum size** |
| 14 | Whole-talk text/audio authoring | Always-visible row | talk | P1 | 0 | 1 | 1 | source | — |
| 15 | Per-slide text/audio/play | Editor center, 3 always-visible buttons | slide | P1 | 0 | 1 | 1 | source | — |
| 16 | Slide inclusion/after-slide/timing | Right inspector, inline | slide | P1/P2 | 0 | 1–2 | 1/2 | exercised | F13 fixed, re-confirmed this session |
| 17 | Slide delivery override | Same sidebar, disclosure | slide | P2 | 0 | 2 | 2 | source | — |
| 18 | Additional audio clips (slide) | Inspector "Additional audio…" | slide | P3 | 0 | 1 | 1 | source | F12 fixed |
| 18b | Background track (talk) | Talk settings (1) → nav "Presentation & recording" (1) → button (1) | talk | P3 | 2 | 1 | 3 | source | — |
| 19 | Mode selection | Toolbar combo, always visible | talk | P1 | 0 | 2 | 2 | source | Open+choose |
| 20 | Start / Prepare and start | Toolbar primary button | talk | P1 | 0 | 1 | 1 | exercised | Both captions confirmed from genuinely-opened Quick/Realtime/Prepared native screenshots |
| 21 | Playback pause/continue/prev/next | Presenter row | presentation | P1 | 0 | 1 | 1 | source | — |
| 22 | Restart/start-from-selected | "More actions" (1+1=2); Shift+F5 (0+1=1) | presentation | P2/P3 | 1/0 | 1 | 2/1 | source | — |
| 23 | Live demo pause/resume | Presenter row; auto-triggers | presentation | P1 | 0 | 1 | 1 | source | — |
| 24 | Fullscreen leave/continue | Esc; "Continue presentation" | presentation | P1 | 0 | 1 | 1 | source | — |
| 25 | Presentation display selection | **Mouse: Settings menu (1) + "Application settings…" (1) = Reach 2**; keyboard `Ctrl+,` = Reach 0 (direct); then combo (2) | app | P2 | **2**/0 | 2 | **4**/2 | source | **Corrected: mouse route was wrongly given Reach 1** |
| 26 | System audio routing | Presentation menu (1+1); same page (2+1) | app | P3 | 1/2 | 1+OS dialog | 2+/3+ | source | — |
| **27a** | **Recording enable (checkbox)** | Footer, always visible (0); Talk settings page (2) | talk | P1/P2 | 0/2 | 1 | 1/3 | exercised (footer control clicked in F6/F17 probes' dialog navigation) | — |
| **27b** | **Recording source (combo)** | Talk settings → Presentation & recording (Reach 2) | talk | P2 | 2 | 2 | 4 | exercised (measured, §0.1) | Combo, open+choose |
| **27c** | **Include microphone (checkbox)** | Same page | talk | P3 | 2 | 1 | 3 | source | — |
| **27d** | **Video destination (text field / picker)** | Same page; field (2+1 focus) or "Choose video destination…" button (2+1, +OS dialog) | talk | P3 | 2 | 1 | 3 | source | **27a–27d replace the prior single imprecise row** |
| 28 | Recording in-progress/saving indicator | Footer text (0, view); inline links (0+1) | talk | P1 | 0 | 0/1 | 0/1 | exercised | Genuinely non-interactive display for the "view" case |
| 29 | Recordings & export | File menu (1) + item (1) | app | P2 | 1 | 1 | 2 | exercised | F12 fixed |
| 30 | GPU automatic load/unload policy | App defaults (2, per row 25) → nav (1) → radio (1) | app | P2/P3 | 3 | 1 | 4 | source | — |
| **31a** | **GPU load, dialog-page route** | Settings menu(1)+item(1)+nav(1)=Reach 3 → button(1) | app | P2 | 3 | 1 | 4 | exercised (control) | — |
| **31b** | **GPU load, Settings-menu-direct route** | Settings menu (1) → "Load speech model now" item (1) | app | P2 | 1 | 1 | 2 | exercised | Structurally cheapest route: no dialog opened at all |
| **31c** | **GPU load, status-bar-button route** | Status bar button (1, opens dialog on right page) → "Load model now" button (1) | app | P2 | 1 | 1 | 2 | **exercised — this is the exact control clicked by my own probe (§ below)** | **Corrected: was wrongly counted as Total 1 (reach-only)** |
| 32 | Model update check | Dialog page (2+1) → button (1) | app | P3 | 3 | 1 | 4 | source | — |
| 33 | Progress display | Footer, always visible; mirrored into dialogs | any | P1 | 0 | 0 | 0 | source | Genuinely non-interactive |
| 34 | Cancel operation | Footer (0+1); mirrored in dialogs | any | P1 | 0 | 1 | 1 | **exercised — the real control clicked by my model-loading-cancellation probe** | — |
| 35 | Talk-level settings | Toolbar (0+1); Ctrl+T (0+1, keyboard); Talk menu (1+1) | talk | P1/P2 | 0/1 | 1 | 1/2 | source | — |
| 36 | Slide-level settings | Inline sidebar (0, 1–2); dedicated-dialog buttons (0, 1) | slide | P1/P3 | 0 | 1–2 | 1–2 | source | — |
| 37 | Help/keyboard shortcuts/about | Help menu (1) + item (1) | app | P3 | 1 | 1 | 2 | source | — |
| 38 | View/panels/enlarge/Editor-Presenter switch | Tab bar (0+1); View menu (1+1); "Enlarge slide…" (0+1) | any | P1/P2/P3 | 0/1 | 1 | 1/2 | source | — |
| 39 | Save application defaults | Already in an open app-scope dialog | app | P1 | 0 | 1 | 1 | source | Commits to `QSettings` immediately |
| 40 | Cancel talk/slide settings | Already in an open dialog | talk/slide | P1 | 0 | 1 | 1 | source | Restores the deep-copied `self.before` snapshot |
| 41 | Remove a slide/talk override (inherit) | Reset button beside the field, or dedicated `voice_inherit` button | talk/slide | P2 | varies (as field's own Reach) | 1 | varies+1 | source | Two distinct button patterns, both single-click once reached |

**On "GPU status-bar button opens a menu":** re-tracing precisely, `w.engine_status` is a plain `QPushButton`, not a menu — but functionally the correction's point stands regardless of that label: clicking it only *reaches* the Load control (it opens the settings dialog to the right page via a `QAction.trigger()`), it does not *activate* Load. Row 31c above reflects the corrected Reach 1 / Act 1 / Total 2, not the previous Total 1.

**No redesign implied by any of the above** — every correction is to the arithmetic and to which sub-actions are being measured, not to a proposed rearrangement of controls.

### 0.3 Startup timing — the two historical measurements kept separate, phrasing fixed (item 3)

**Corrected, precisely:** `2026-09-28-refinement.md`'s five-baseline/five-candidate table (63.00s → 49.13s median; 46.69–52.29s candidate range) is described in its own source as measuring **"Start to first visible slide plus Qt consuming more than 0.1 seconds of audio"** — i.e., it is already the **full Start-to-audible-playback total**, not an isolated measurement of the Codex outline call alone. I should not, and no longer do, describe this range as "the gating call's latency" in isolation.

This is **explicitly distinct**, per the same document, from a **separate, protocol-only** trace: "A separate request-only protocol trace... Request elapsed time was 70.22 versus 46.72 seconds. **These two diagnostic requests are not included in the five-run startup medians.**" I keep these as two separate, non-interchangeable numbers, sourced to two separate described experiments, neither of which I re-ran or re-measured myself.

**On measurement methodology:** the historical benchmark's own described criterion ("Qt consuming more than 0.1 seconds of audio") is not necessarily identical to what I traced in `app.py`'s internal `measurements["First playback"]` instrumentation (captured via `playback_state_changed` on a `state == "playing"` transition). I confirmed from source that the app **has** genuine per-run internal timing instrumentation (`job_finished` writes `project/runs/<ts>.json`) — a real, verifiable capability — but I do not know, and do not claim to know, whether the specific 46.69–52.29s figures came from that internal instrumentation or from an external harness applying its own audio-consumption criterion. These are two separate facts and I am not merging them.

**Scope phrasing, corrected throughout:** live Codex/GPU/Wayland/hardware access was **not exercised by review scope** (an explicit, deliberate scope boundary set for this review), not "unavailable in this sandbox" (which would wrongly imply a technical limitation rather than a scope decision).

**Deferral status, corrected:** per `docs/ROADMAP.md`'s own latest recorded entry — *"Current priority (owner decision, 28 September): defer further startup optimization and focus on supervised native Wayland recording acceptance. The 15–20-second target remains open, not waived."* — further startup-latency work is **explicitly deferred by the owner**, not ongoing active implementation. F7 remains open with one landed, partial, evidenced improvement (~22%, compact-JSON serialization) that predates the deferral decision; it is not "active work" as of this reviewed commit.

### 0.4 Export cancellation — cleanup coverage, not mid-export interruption (item 4)

`tests/test_media.py::test_export_closes_audio_even_with_retained_traceback[cancel]` sets `task.cancelled.set()` **before** calling `export_prepared`, so `task.check()` raises on the loop's very first iteration. This proves the cleanup path (`except BaseException: capture.close(); shutil.rmtree(...); raise`) runs correctly and closes every retained `AudioFile` reader **when cancellation is requested before or at the very start of export**. It does **not** prove that interrupting an export already partway through (frames already written, real accumulated state) unwinds identically — the same code executes structurally on any iteration, but this specific test does not exercise a later iteration. I am not recommending a new test (per the coordinator's instruction); I am correcting the claim to "cancellation-cleanup coverage exists; an interaction that interrupts an already-running export is not separately confirmed by this test."

### 0.5 Residual counting/file-list errors (item 5)

- **Image count:** every reference to "46 images" in my prior drafts was a confusion with the **second verdict's own historical count** (from `2026-09-28-claude-review-method.md`, a different review). My own generated counts, verified this session by `ls | wc -l`, are **42** per run (confirmed identically for the original Fusion run and all three native Breeze runs this session). I do not use "46" to describe anything I generated.
- **`app.py` read coverage, recounted precisely:** in the corrected-round session, I issued **six** `Read` calls against `app.py` (offsets 1, 270, 470, 690, 939, 1108; limits summing to full 1–1238 coverage), plus one smaller, separate targeted read in the original first-draft session (the `closeEvent`/`load_gpu` region). "Four ranges" was wrong; six is correct for the pass that achieved complete coverage.
- **File list, reverified via `find src/autotalk -maxdepth 1 -name "*.py"` this session:** 16 files exist: `__init__.py, app.py, codex.py, compiler.py, media.py, options.py, playback.py, project.py, recording.py, runtime.py, screen_capture.py, services.py, settings.py, speech_worker.py, ui.py, voices.py`. `recording.py` and `compiler.py` **do exist** — my error was not inventing nonexistent files but imprecisely describing their review depth. Precisely, this whole review: **full-file `Read`** on `project.py, options.py, settings.py, services.py, ui.py, app.py`, and the large majority of `runtime.py`; **diff-only** (never a full pre-existing-content read) on `playback.py, screen_capture.py, media.py`; **zero attention of any kind** (no read, no diff, no grep) on `codex.py, speech_worker.py, voices.py, recording.py, compiler.py, __init__.py` — six files genuinely untouched, stated as such rather than vaguely bundled with the diffed set.
- **F15/packaging contradiction, resolved:** confirmed via `git diff --stat 88351b8 b520f8b -- tools/build.py packaging/autotalk.spec` → **empty output**, i.e., the packaging **staging/copy mechanism** (how Qt libraries get from a build tree into the shipped bundle) is genuinely unchanged. This is a separate fact from the **native patch's content**, which changed substantially across three commits (§ below, unchanged from the prior round's correct analysis). F15 concerned the staging *mechanism*; it is not contradicted by the patch *content* changing — they answer different questions, and I now state that distinction explicitly rather than writing an over-general "nothing packaging-related changed."

---

## 1. F1–F17 closure status

| ID | Disposition |
|---|---|
| F1, F2, F3, F4, F5, F8, F9, F10, F11 | Closed/unchanged, as established across all three review rounds; re-confirmed by re-running the closing tests and, for F10, an additional mutual-exclusion trace of `play_button`/`continue_button`/`end_button` this review found no violation of. |
| F6 | A cause matching the complaint is reproduced and fixed **in current code**, independently re-confirmed via my own fault-injection probe this review (§2 of the second round). The original user-reported sequence remains uncharacterized; I did not run pre-fix code. |
| F7 | **Open, and explicitly deferred by the owner** as of this reviewed commit (§0.3). One landed, partial, evidenced improvement (~22%) predates the deferral. |
| F12, F13 | Closed; confirmed in native Breeze light, dark, and 150% scale. |
| F14 | Closed. The original deterministic-cleanup concern is satisfied at the traced ownership boundaries; `AudioFile.__del__` remains a deliberate fallback, not an outstanding task. |
| F15 | Retracted, unchanged. Concerns the packaging staging *mechanism*, confirmed unchanged (`tools/build.py`/`packaging/autotalk.spec` have zero diff since `88351b8`) — distinct from, and not contradicted by, the native *patch content* changing (§ below). |
| F16 | **Retracted as a finding.** Measured (not asserted): under a realistic ~20ms packet cadence, the drain loop makes ~200 `pa_mainloop_iterate` calls/sec with correct 5ms idle backoff — negligible CPU. The only condition producing a measured tight spin (~570,000 calls/sec) requires continuously-available data with zero gaps, which the code's own 20ms fragment sizing (`fragsize=3840`) makes structurally implausible as a real backlog pattern. No concrete defect found. |
| **F17** | **New. Low severity, P3.** "Language arrangement" combo clips its current-selection text (2 of 3 choices) at the dialog's minimum supported size; the dropdown popup itself remains fully readable. Not reproduced at normal dialog size. Full detail in §0.1. |

---

## 2. Everything else — unchanged from the second round, retained by reference

The following sections of the second round are unchanged by this final pass and are not repeated in full here, since nothing in this round's specific requests touched them: the complete architectural trace of `project.py`'s settings/inheritance/cache authority; the `options.py`/`settings.py` Save/Cancel/inheritance mechanism (two distinct button patterns, both correct); the native Qt patch's three precisely-dated variants (`88351b8` → `753bb14` → `aaa1b7b`) with the corrected destroy/stop ordering, cross-checked this session by independently recomputing SHA-256 (`5537cedf957b657d492adf7371147c05446acc78021a116ba9b43fd33b05659f`, matching both the artifact I tested and the currently-installed `dist/autotalk/_internal/libQt6Multimedia.so.6`); the 50/50-cycle native lifecycle probe and both 372/372 full-suite runs (not re-run this pass, per instruction); the button-visuals review across light/dark/150% scale; and the explicit scope/limitations statement, now with "not exercised by review scope" phrasing applied consistently rather than "unavailable in this sandbox."

---

## 3. Overall assessment

**Readiness: unchanged — preserve and continue refining, not rebuild.** This final pass found one genuine new low-severity finding (F17, a narrow sibling of the already-fixed F13) via direct measurement, corrected a materially imprecise click-cost table into an internally consistent one without proposing any redesign, and corrected several of my own reporting errors (image counts, file-coverage claims, a timing-measurement conflation, an overclaimed test interpretation, a self-contradictory packaging statement). None of these corrections change the underlying architectural assessment from the prior two rounds.

**Ranked remaining work, final:**
1. F7 — open, owner-deferred; do not resume without a new measurement.
2. F17 — same narrow remedy shape as F13 (widen from actual content, or elide+tooltip); needs a new geometric regression test at the dialog's minimum size, mirroring the existing `slide_after` one.
3. Continue F6's mismatch-logging-informed reproduction of the *original* user report.
4. F14, F16 — closed/retracted, not carried forward.

**Final, precise verification-depth statement:** this review executed, myself: two full test suites (372/372 each, from the second round, not re-run this pass per instruction), one 50-cycle native lifecycle probe, one independent F6 fault-injection probe (corrected twice in front of you), one cancel-during-model-loading probe clicking the real "Cancel operation" button (corrected once, with documented fixture-import failures), and this round's F17 geometric/visual measurement (corrected once, after an invalid first attempt measuring off-page widgets). I opened 21 images across both sessions (16 fresh, 5 historical) out of 210 generated (42 Fusion + 126 native Breeze this session + 42 in the earlier native probe evidence directories). Full-file source reads covered 6 of 16 `src/autotalk` files completely; 3 more were diffed but not fully read; 6 received no attention at all, named explicitly in §0.5. Live GPU/Codex/Wayland-portal/physical-audio-hardware interaction was excluded from this review's scope by design and is reported as coordinator-supervised historical evidence, distinct throughout from what I personally executed.