# AutoTalk UX placement proposal

Recorded: **26 September 2026**.

**Status: implemented on 27 September 2026; Linux verification recorded in
[UX placement verification](UX_PLACEMENT_VERIFICATION.md).** This is the accepted
interaction contract. The [original inventory](UI_INVENTORY.md) is the historical
baseline. Existing visual styling is retained. The implementation was authorized
with a ceiling of 160 net additional production lines.

## Current settings contract

The subsequent [flat scoped-settings contract](SCOPED_SETTINGS_IMPLEMENTATION.md)
supersedes settings grouping and Quick-mode substitutions described below. The
main authoring and presentation placement requirements remain in force. Settings
now have five flat pages and explicit application/talk/slide inheritance.

## Consolidated settings amendment — 27 September 2026

The later user instruction supersedes separate settings dialogs: one canonical
**Settings** dialog contains the task sections below. Existing menus, buttons and
internal links select the matching section without opening another dialog.

- **Talk:** Audience & conference, Narration AI — Codex, Preparation & timing,
  Language arrangement.
- **Voice & speech:** Voice, Delivery, Speech model — Qwen.
- **Presentation:** Display & sound, Recording, Background audio.
- **This slide:** Slide audio clips.
- **Application:** Account — Codex, Speech engine — Qwen.

One transaction owns pending edits across sections. Save/Cancel covers talk/display
configuration and automatic engine policies. Account, manual engine and explicit
library actions remain immediate, stated in the shared footer. Talk-dependent
sections are unavailable without a talk. Recordings & export remains a separate
task window. Existing shortcut access depths and system appearance are preserved;
references below to task dialogs now mean these groups inside Settings.

## Placement and access metric

Access depth means the number of navigation clicks needed to expose a control,
starting from the main workspace. Selecting a source or changing a section counts
as navigation when it reveals further controls. Executing the action, entering
data and confirming a dialog are counted separately.

A direct button has depth **0**; controls inside its dialog normally have depth
**1**. Selecting a dropdown value takes additional interaction. A dropdown choice
that opens another panel is navigation and must not be excluded from the count.

| Priority | Placement requirement |
| --- | --- |
| P1 — Essential | Visible directly, or exposed by one clearly named control. |
| P2 — Common | Direct access or normally no more than two navigation clicks. |
| P3 — Occasional | Contextual options or a clearly named advanced group, normally within three clicks. |
| P4 — Technical | Specialist settings grouped by the subsystem they configure. |

Lower-priority controls can remain easy to reach when they naturally belong beside
another control. Do not add clicks merely to enforce a hierarchy. Preserve
inventory priorities unless a change is explicitly justified.

Assess every placement for:

- Visibility, including any scrolling or control-reveal requirement.
- Navigation depth from the main workspace and within the active task.
- Execution steps, recorded separately from navigation.
- Discovery effort: whether an ordinary user can predict the destination.
- Context switching and repeated-use effort, such as edit → generate → listen.
- Scope clarity: application, talk, language version, slide or presentation session.
- Consistent wording, availability and consequences across applicable modes.

“Correct” is the acceptance requirement, not a label for unresolved problems.
Grouping and access depth can be assessed from this specification; visual
findability and minimum-window density require checking in the actual layout.

## 1. Main window: fewer permanent entrances

The authoring workspace has these persistent groups:

| Group | Visible elements | Priority / depth |
| --- | --- | --- |
| Document toolbar | Open PDF…, Open saved talk…, Save | P1 / 0 |
| Presentation launch | Prepared/Quick/Realtime selector; fixed Start command | P1 / 0 |
| Talk basics | Duration; language/version; Voice & speech… | P1 / 0 |
| Talk configuration | Talk settings… | P2 / 0 |
| Whole-talk preparation | Create talk text; Create talk audio | P1 / 0 |
| Recording and presentation setup | Record presentation as a video; Presentation settings… | P1–P2 / 0 |
| Workspace selection | Editor / Presenter | P2 / 0 |

This removes separate permanent buttons for Fit duration, mode options, recording
settings and the recordings browser. Those operations receive predictable homes
below. Important results still appear directly when relevant.

The welcome screen contains the two opening actions. Once a talk is loaded, the
document toolbar replaces that screen.

The launch command remains:

- Prepared: **Prepare and start**.
- Quick and Realtime: **Start**.

It does not turn into a review instruction.

Selected-slide authoring remains immediately accessible:

| Element | Placement | Priority / depth |
| --- | --- | --- |
| PDF preview | Central editor | P1 / 0 |
| Narration text | Directly beneath the preview | P1 / 0 |
| Create / Rewrite / Translate slide text | Beside narration | P1 / 0 |
| Create slide audio | Beside narration, separate from text creation | P1 / 0 |
| Play / Stop audio | Beside the waveform and duration | P1 / 0 |
| Narration/audio readiness | Beside the relevant text/audio controls | P1 / 0 |
| Enlarge slide… | Secondary control at the preview | P3 / 0 |
| Insert language passage… | Secondary text-editor command | P3 / 0; chooser at 1 |
| Generated notes | Expandable content below narration | P3 / 1 |

The waveform remains feedback, not a falsely implied seek control.

Whole-talk preparation and selected-slide preparation have separate, explicit
scope. Creating talk text preserves existing text and creates missing/translated
content. **Rewrite all talk text…** is a separate command. **Create talk audio**
is a direct entry point to preparation: it prepares missing or
outdated audio without presenting. Create slide audio remains separate from
rewriting slide text. Playing retained older audio identifies it as outdated;
presentation reuse still requires matching audio. No text or audio approval
mechanism is introduced.

## 2. Sidebars: clear and limited responsibilities

| Surface | Elements | Priority / depth |
| --- | --- | --- |
| Left sidebar: Slides | Thumbnails, titles, slide selection | P1 / 0 |
| Left sidebar | Included/excluded and text/audio readiness indications | P2 / 0 |
| Right sidebar: This slide | Include in presentation | P3 / 0 |
| Right sidebar | After this slide: advance, pause for demo, wait for presenter | P3 / 0 |
| Right sidebar → Timing | Automatic/explicit slide duration; Pause after slide with Use talk pause (X s) inheritance | P3 / 1 |
| Right sidebar → Slide voice & delivery… | Voice, language, delivery directions and attributes in the slide dialog; voice/source/style caption below entrance | P3 / 1 |
| Right sidebar → Additional audio… | Clip list, add/remove, volume, before/after narration | P3 / 1 |

These slide settings retain their inventory priority. Their direct visibility is
justified by being small, contextual controls—not by silently promoting them to P2.

There is no repeated language selector in the left sidebar. Generated notes leave
the settings sidebar because they are supporting content, not configuration.

## 3. Talk settings: three task-specific sections

**Talk settings… always opens its initial Audience & conference section.** Direct
menu shortcuts can open another named section, but ordinary entry does not depend
on whichever page was visited last.

| Section | Elements | Depth |
| --- | --- | --- |
| Audience & conference | Title, audience, objective | 1 |
| Audience & conference | Conference URL, Read conference website, editable scope, source links | 1 |
| Narration AI — Codex | Model and reasoning effort for this talk | 2 |
| Narration AI — Codex | Connection status and Account settings… link | 2 |
| Preparation & timing | Target/measured-duration information; Fit duration…; timing tolerance | 2 |
| Preparation & timing → Quick | Generate once / fit first / require timing match | 2 |
| Preparation & timing → Realtime | Complete script / write ahead; consistency / earliest playback | 2 |
| Realtime → Advanced | Startup/refill buffer | 3 |

The main duration field is the only duration editor. The timing page
provides context and refinement rather than an unexplained second duration-setting
workflow.

**Fit duration… also appears directly in the Talk menu:** one click exposes the
command, a second invokes its confirmation.

The distinction between model and account is explicit:

- Codex model/reasoning: this talk.
- Codex sign-in/sign-out: application/shared account.

The link opens the existing Account destination; it does not create another
account-management page.

## 4. Voice & speech: eliminate conditional dropdown navigation

The dialog has **Voice**, **Delivery**, and **Speech model** sections. It opens on
Voice.

Within Voice, the workflow choices are directly selectable: **Predefined**,
**My voice**, **Design**, **Saved**. They are not buried inside a dropdown. That
fixes the previously understated click count.

| Group | Elements | Depth from main window |
| --- | --- | --- |
| Voice → Predefined, initially shown | Speaker selection | 1 |
| Voice → My voice | Record / Stop; Import recording…; transcript | 2 |
| Voice → Design | Description, age, Use this designed voice | 2 |
| Voice → Saved | Voice list, language filter, Use selected voice | 2 |
| Shared audition area | Listen to a sample / Stop sample | 1; remains exposed in Voice and Delivery |
| Shared reuse action | Save reusable voice… when applicable | 1 |
| Delivery | Writing/delivery style; preset selection, Use preset, Save preset… | 2 |
| Delivery → More vocal attributes | Pitch, texture, energy, pace, articulation, projection, accent, expressive cues | 3 |
| Delivery → More vocal attributes | Vocal persona, custom directions, gradual progression | 3 |
| Speech model — Qwen | Selected model/variant and capabilities | 2 |
| Speech model → Advanced synthesis | Sampling override, temperature, top k, top p, repetition penalty, maximum new tokens | 3 |
| Speech model | Speech engine settings… | Shortcut to the single application-level engine page |

The engine shortcut is an alternative route, not the primary access for
loading/unloading. The main-window engine status provides the shorter route below.

Voice interaction rules:

- Selecting a library row selects a candidate.
- Listen auditions that candidate without choosing it for the talk.
- Use selected voice changes the dialog's pending voice selection.
- Save commits that selection; Cancel restores the previous talk configuration.
- Saving a reusable voice is an explicitly separate library operation.
- Audition remains available while adjusting delivery—no repeated Voice/Delivery
  page switching.
- Delivery presets cannot silently replace hidden synthesis settings.
- Unsupported vocal controls explain why they are unavailable.

Voice identity, vocal delivery and speech-model settings remain visibly distinct.
Model variant follows the chosen voice workflow where required; the proposal does
not add a misleading independent selector for unsupported combinations. The
combined writing/delivery style describes its effect on generated wording and
supported vocal delivery; changing it does not automatically rewrite existing text.

## 5. Presentation settings: one entrance for setup

There is one main-window **Presentation settings…** button. No competing Recording
settings button is added beside it.

The dialog has **Display & sound**, **Recording**, and **Background audio** sections.
It opens on Display & sound.

| Section | Elements | Depth |
| --- | --- | --- |
| Display & sound | Fullscreen display | 1 |
| Display & sound | System audio settings…; Test audio | 1 |
| Presentation & recording → Playback | Application/talk default pause between slides; slide overrides belong to inspector Timing | 1 |
| Recording | Slides/narration or screen/system audio source | 2 |
| Recording | Include microphone | 2 |
| Recording | Destination field and Choose destination… | 2 |
| Recording → Advanced | Treatment of pauses and outside-fullscreen time | 3 |
| Recording → Output quality | Sample rate and AAC bitrate | 3 |
| Background audio | Add/replace track, volume, loop, remove | 2 |

The main recording checkbox remains in place. The dialog shows whether recording
is enabled but does not move the checkbox between windows.

These groups state their scope:

- Display selection is presentation setup on this computer.
- System audio routing is changed immediately in the operating system.
- Background audio, pauses and recording choices belong to the talk.

Save/Cancel does not claim to undo an external system-audio change. Screen-sharing
permission remains in the system portal. The selected presentation display and
the screen authorized for capture are separate choices, explained at capture startup.

## 6. Language handling: complete, explicit destinations

| Interaction | Primary placement | Access |
| --- | --- | --- |
| Select an existing version | Main language/version control | Control visible at depth 0 |
| Choose initial spoken language | Same control before narration exists | Depth 0 |
| Restore/create language version | Select the language in the main combo | Depth 0 |
| Language options… | Named entry in the same control; also Talk menu | Dialog at 2 |
| Language arrangement policy | Both Language options entrances focus Language arrangement in talk settings | Depth 2 |
| Insert a language passage | Selected-slide text editor command | Chooser at 1 |

Language options contains the existing arrangement choices:

- Separate versions with mixed-language passages.
- Separate versions with one language per slide.
- Separate single-language versions.

It explains how these affect the current talk. It does not contain voice selection
or imported audio clips.

Selecting an existing version switches versions. Creating another version is
always an explicit action.

## 7. Recordings & export: no extra permanent toolbar button

The primary entrance is **File → Recordings & export…**. That exposes the browser
in two clicks from the main window, appropriate for P2. Immediately after
recording/export, direct result actions avoid that navigation.

| Surface | Elements | Access |
| --- | --- | --- |
| Main-window completion message | Open video/audio; Open folder | Depth 0 when a result is produced |
| Recordings browser | Talk, date, duration, status; select recording | Depth 2 from main window |
| Browser selection actions | Open result; Open folder; Save unfinished recording…; Save another format… | Visible within the browser |
| Browser empty state | Explanation and direct Presentation settings… link opening Recording | Visible within the browser |
| File → Export prepared talk… | Destination and MP4/WAV/M4A choice | Export dialog at depth 2 |
| Browser alternative | Export prepared talk… | Same command, not another implementation |
| Active export | Progress and Cancel operation | Visible beside the operation |

Open result is P1 when a result has just been produced. Browsing historical
recordings remains P2. This contextual distinction is explicit rather than hidden
in the rating.

The most recently completed output and the currently running recording are shown
as separate facts.

## 8. Application settings: one account page and one engine page

The dialog contains **Account — Codex** and **Speech engine — Qwen**. There is no
information-only General page.

| Page/group | Elements | Primary access |
| --- | --- | --- |
| Account — Codex | Status, Sign in, Sign out, shared-account explanation | Settings → Account…: 2 clicks |
| Sign-in required during a task | Direct Sign in action | Depth 0 in the active task |
| Speech engine — current state | Selected and loaded model; GPU state | Click main status-bar engine control: 1 |
| Current state | Load now / Load selected model; Unload now | Depth 1 |
| Current state | Check for model updates… | Depth 1 |
| Automatic policy | Load when needed / at presentation start | Depth 1 |
| Automatic policy | Keep until exit / unload at presentation end / after idle time / after operation | Depth 1 |
| Active engine operation | Stage, measurable progress, cancellation | Visible in the engine page or active main operation area |

The current-state actions and automatic-policy editor are visibly separate groups.

- Load, unload and update checking act immediately.
- Save/Cancel governs the automatic-policy edits only.
- The page states this beside those controls.
- Account operations have no misleading pending Save step.

All other engine/account links open these exact destinations. System appearance
remains automatic; its explanation belongs in Help/About rather than a
configuration page without controls.

## 9. Presenter and fullscreen controls: exact surfaces

The main-window **Presenter** workspace contains the current/next slide, narration
and timing.

| Location | Controls | Access |
| --- | --- | --- |
| Presenter control row | Previous, Pause/Continue, Next, End presentation | P1 / 0 |
| Presenter control row | Pause for live demo | P2 / 0 |
| Presenter “More actions” menu | Start from selected slide; Restart from beginning | P2 / 1 |
| Presenter status | Recording state, elapsed capture time, buffering and completion | Visible |
| Presenter completion | End presentation and save video, or Return to editor | P1 / 0 |

More actions is specifically a button opening a menu—not an unspecified secondary
area.

The fullscreen presentation retains a **visible control strip, separate from the
slide content**, with Previous, Pause/Continue, Next, Return to controls and End
presentation.

**Automatic hiding is removed from this proposal.** It added a discovery
requirement while claiming zero navigation effort. Keyboard equivalents remain
available.

- F5 invokes the same operation as the main Start button.
- F6 continues the retained presentation.
- Space pauses/continues in fullscreen.
- Arrows/Page Up/Page Down navigate.
- Escape pauses and returns to controls.
- Leaving fullscreen does not imply ending recording.

There is no second Start presentation command with a different preparation contract.

## 10. Menu structure: retain seven menus

The extra Slide menu is removed. Selected-slide commands receive a clearly named
submenu under Talk; their P1 primary access remains directly in the editor.

| Menu | Entries/groups |
| --- | --- |
| File | Open PDF…; Open saved talk…; Open recent →; Save; Save a copy…; Open talk folder; Recordings & export…; Export prepared talk…; Quit |
| Edit | Undo; Redo; Cut; Copy; Paste; Select all; Find in slide text… |
| View | Editor / Presenter; navigator/inspector visibility; Enlarge slide…; Restore default layout; Operation details |
| Talk | Talk settings…; Voice & speech…; Create talk text; Rewrite all talk text…; Create talk audio; Fit duration…; Add language version…; Language options…; Selected slide →; Mode → |
| Presentation | Start / Prepare and start; Pause / Continue; Previous / Next; Start from selected slide; Restart; Live demo; End presentation; Presentation settings…; System audio settings… |
| Settings | Application settings…; Account…; Speech engine…; Load speech model now; Unload speech model now |
| Help | Getting started…; Keyboard shortcuts…; Operation details; About AutoTalk… |

The Selected slide submenu mirrors text creation, audio creation, playback,
inclusion, language insertion and additional audio. It is an alternative access
route, not the route used to justify their P1 rating.

Mode and workspace choices show their current selection.

## 11. Common interaction rules

| Concern | Refactored requirement |
| --- | --- |
| Main-window density | Only the permanent groups listed above remain. No unrelated diagnostics, export or technical controls are added to the authoring toolbar. |
| P1 visibility | P1 controls cannot require scrolling or disappear into overflow at the supported minimum window size. |
| Prepared / Realtime | Identical selected-slide editing and preparation controls. |
| Quick | Simplified task surface; editor-only commands unavailable. Changing mode explicitly exposes editing. |
| Whole-talk scope | Preparation commands identify the active language version and included slides. |
| Saving text | Visible Save command and unsaved-changes indication; no implied per-keystroke autosave. |
| Dialog configuration | Save commits the declared configuration scope; Cancel restores pending edits. |
| Library creation | Save reusable voice/preset is an explicitly immediate operation. It is not silently reversed by cancelling talk settings. |
| Destructive replacement | Confirmation identifies the affected slide(s) and language version. |
| Progress | Operation stage, measurable progress and cancellation stay with the active task. |
| Readiness | Text/audio counts remain in the main status area; detailed logs are secondary. |
| Interrupted recording on close | Finish saving and close / Close and save later / Cancel. |
| Names and ellipses | Identical commands have identical names. Dialog-opening commands retain ellipses; direct actions and section changes do not gain them. |
| Standard interactions | Native file dialogs, permissions, keyboard focus, context menus and desktop controls remain standard. |

## Acceptance status

See [UX placement verification](UX_PLACEMENT_VERIFICATION.md) for the implementation
mapping, measured navigation depth, Linux Xvfb checks and remaining validation
limits. Ratings describe conformance to the agreed placement metric; they do not
substitute for testing with recruited first-time users.
