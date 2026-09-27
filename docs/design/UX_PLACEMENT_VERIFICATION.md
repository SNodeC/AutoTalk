# UX placement implementation and verification

Implemented 27 September 2026 against the accepted
[placement contract](UX_PLACEMENT_PROPOSAL.md). The original
[inventory](UI_INVENTORY.md) remains the pre-refactor coverage baseline; the
[user guide](../USER_GUIDE.md) describes the current interaction routes.

## Subsequent settings refinement

The settings-specific locations below describe the preceding canonical-dialog
pass. They are superseded by the [five flat pages and scope contract](SCOPED_SETTINGS_IMPLEMENTATION.md).
Main authoring/presentation controls retain their placement. Current tests cover
shortcuts selecting page and scope, inherited values, storage ownership, voice
origin, and per-slide generation; see [VERIFICATION.md](../VERIFICATION.md).

## Governing invariant

Every operation has one authoritative implementation, a predictable task/scope,
and the same prerequisites through buttons, menus and shortcuts. P1 authoring
controls stay visible without navigation or scrolling in the applicable workspace.
Dialog Save/Cancel governs pending configuration, not immediate account, engine,
external-system or library operations.

The existing `SectionDialog`, project bindings, preparation services, playback
controller and engine owner are retained. One canonical Settings dialog now groups all configuration, following the
later consolidation instruction. Existing shortcuts select their named section. It removes moving duration and
recording controls between surfaces, the duplicate language selector, the separate
Presenter Start command and style-driven replacement of hidden vocal attributes.
No parallel preparation pipeline, approval state or engine controller was added.

## Placement assessment

Depth counts navigation to expose a control, not executing it, filling it in or
confirming it. A dropdown entry opening a dialog counts both navigation steps.
Ratings below mean **Correct against the agreed placement metric**. They are an
engineering assessment, not evidence from recruited first-time users.

| Contract group / controls | Implemented primary location | Priority / depth | Rating and evidence |
| --- | --- | --- | --- |
| Open PDF, open saved talk, Save | Welcome opening actions, then document toolbar | P1 / 0 | Correct: welcome and loaded toolbar are mutually exclusive. |
| Mode, fixed Start | Upper-right toolbar; F5 shares the same command | P1 / 0 | Correct: Prepared says Prepare and start; Quick/Realtime say Start. Button/shortcut tested. |
| Duration, language/version, voice entrance | Main talk-basics row | P1 / 0 | Correct: visible in all modes at minimum window size. |
| Create talk text/audio | Main preparation row in Editor | P1 / 0 | Correct: missing text only; current audio reused; preparation never starts presentation. Tested in Prepared and Realtime. |
| Selected-slide text/audio/play, readiness | Immediately below PDF/narration | P1 / 0 | Correct: distinct commands and prerequisites; current and stale audio behaviour retained. |
| Enlarge, insert passage, notes | Beside preview/text editor | P3 / 0–1 | Correct: supporting content stays with the text, not the settings sidebar. |
| Slides, titles, selection and status | Left sidebar; status in thumbnail tooltip | P1–P2 / 0 | Correct: one slide navigator, no second language selector. |
| Include, after-slide action | This slide sidebar | P3 / 0 | Correct: explicitly selected-slide scope. |
| Timing, delivery override | Separate sidebar disclosures | P3 / 1 | Correct: small contextual groups; no combined miscellaneous panel. |
| Imported audio clips | Settings → This slide → Slide audio clips, from sidebar | P3 / 1 | Correct: list, add/remove, volume, before/after; language insertion is separate. |
| Title, audience, objective, conference URL/scope/sources | Talk settings → Audience & conference | P2 / 1 | Correct: ordinary entrance resets to this section. |
| Codex model/reasoning | Talk settings → Narration AI — Codex | P2–P4 / 2 | Correct: talk scope, status and link to the single account page. |
| Fit duration, tolerance, mode policies | Talk settings → Preparation & timing | P2–P3 / 2 | Correct: Fit also exposed at depth 1 through Talk menu; buffer at depth 3. |
| Predefined speaker and sample | Voice & speech → Voice | P1 / 1 | Correct: default section; sample remains visible across sections. |
| Personal voice, design, saved candidates | Direct My voice / Design / Saved tabs | P2 / 2 | Correct: no hidden dropdown navigation. Minimum-dialog controls tested. |
| Saved voice audition/use | Shared audition and Saved-tab Use action | P2 / 2 | Correct: audition leaves talk identity/audio intact; Use is pending until Save; Cancel restores. Tested with a persisted project. |
| Delivery style/presets | Voice & speech → Delivery | P2 / 2 | Correct: sampling remains unchanged, including when loading a legacy preset. |
| Vocal attributes, persona, directions, progression | Delivery → More vocal attributes | P3 / 3 | Correct: supported controls grouped together; age belongs to Design. |
| Qwen identity/capabilities and sampling | Voice & speech → Speech model — Qwen → Advanced synthesis | P4 / 2–3 | Correct: model variant follows voice source; no invalid independent model combination. |
| Display, audio routing/test, pauses | Presentation settings → Display & sound | P2 / 1 | Correct: single setup entrance; external routing and local display scope explained. |
| Recording enable | Stationary main checkbox | P1 / 0 | Correct: it never moves into a modal dialog. |
| Recording source, microphone, destination | Presentation settings → Recording | P2 / 2 | Correct: current intent shown; capture scope and screen-sharing distinction explained. |
| Pause policy and encoding | Recording → Advanced recording / Output quality | P3 / 3 | Correct: details stay with recording. |
| Background track, gain, loop, remove | Presentation settings → Background audio | P2 / 2 | Correct: whole-talk audio is separate from slide clips. |
| Existing/initial language | Single main language control | P1 / 0 | Correct: switching never silently creates a version. |
| Add version and arrangement | Named language entries or Talk menu | P2–P3 / 2 | Correct: explicit creation dialog, original content preserved; options Cancel tested. |
| New output links | Main completion area | P1 / 0 when available | Correct: saved output is separate from current capture status. |
| Historical recordings, recovery, alternate format | File → Recordings & export | P2 / 2 | Correct: dated titled rows, disabled empty-state actions and Recording setup link. |
| Direct prepared export | File → Export prepared talk; same command in browser | P2 / 2 | Correct: MP4/WAV/M4A export without presenting. |
| Account sign-in/out | Settings → Account | P2 / 2 | Correct: account actions are immediate and labelled as such; common Save/Cancel preserves pending edits from other sections; first-use direct sign-in at depth 0. |
| Engine current state/load/unload/update | Status-bar Speech engine control | P2 / 1 | Correct: one engine page; immediate actions separate from saved automatic policy. |
| Engine loading/release policy | Same engine page | P3 / 1, lower-priority text may scroll in small dialog | Correct: no artificial extra clicks; Save/Cancel scope stated. |
| Editor/Presenter choice | Main tabs and View menu | P2 / 0 | Correct: selecting a workspace does not present; Quick authoring remains unavailable. |
| Previous, Pause/Continue, Next, End, demo | Presenter controls | P1–P2 / 0 | Correct: state-dependent controls, no second Start workflow. |
| Start selected/restart | Presenter More actions menu | P2 / 1 | Correct: secondary operations grouped; same QActions as Presentation menu. |
| Fullscreen navigation/pause/return/end | Persistent control strip outside slide content | P1 / 0 | Correct: existing mouse/keyboard and retained-position tests preserved. |
| File/Edit/View/Talk/Presentation/Settings/Help | Seven menus; Selected slide submenu under Talk | Secondary route | Correct: menus mirror commands; editor-only commands unavailable in Quick. |
| Save, unsaved indication, Cancel, progress, operation details | Document toolbar/title, task-dialog footer, main status area | Contextual | Correct: Qt modified marker, transactional rollback, single progress bar follows active task. |

## Canonical Settings verification

`tests/test_settings_dialog.py` adds 13 cases for menu and button destinations,
internal links, one transaction across sections, Save/Cancel persistence, automatic
engine policy, no-project availability, and completed background results. The
existing playback/engine tests ensure hidden talk pages do not disable application
engine actions. All six former configuration-dialog instances were removed.
Screenshots of all 13 pages at 780×700 and 660×550 are under
`artifacts/canonical-settings/`.

## Verification scope

`tests/test_ux_placement.py` checks 23 placement/journey cases: all three modes at
940×680 and 1100×850; direct voice destinations; minimum 660×550 voice dialog;
Quick restrictions; long user-supplied names; whole-talk authoring; saved-candidate
audition; explicit language versions, including manually written text and empty versions; preset boundaries; dialog rollback; engine,
account and F5 routing; minimum-size Presenter previews and controls in four playback
states. Existing tests cover presentation transport, recording,
export, startup, model discovery and engine lifetime.

Screenshots in `artifacts/ux-placement/` cover the three main workspaces and every
task-dialog section. Detailed command results, code accounting and packaged-build
checks are recorded in [VERIFICATION.md](../VERIFICATION.md).

Only Linux is exercised. These checks use controlled narration/speech substitutes
for deterministic UX journeys; they do not reassess model voice quality, GPU speed,
real conference extraction or first-use multi-GB downloads. A Plasma screen-sharing
approval is an external permission, not something an Xvfb run can grant. No fresh
Wayland capture acceptance or Windows/macOS validation is claimed by this refactor.
