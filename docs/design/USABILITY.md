# Ordinary-user usability refinement

## Current interaction contract (supersedes earlier next-step/approval rules)

Prepared always offers **Prepare and start**; Quick/Realtime offer **Start**.
The command stays visible and enabled for a loaded talk and prepares missing
content automatically. There is no text approval or context-freshness gate.
Existing words remain unless the user requests rewriting or explicit duration fitting.
The editor separates Codex text generation, Qwen audio creation and existing-file
playback. Saved audio is reused in presentation only when its speech inputs match.
Dialog-opening actions retain ellipses, including rewrite confirmation. Direct
commands omit them. Both stopping and finishing a preview restore Play audio;
account-default models use the same names as their explicit dropdown entries.

The historical acceptance entries below describe earlier passes; their next-step
and approval behavior has been replaced by this contract.


The first two passes addressed the nine original review groups and 15 follow-up
findings. The latest pass addresses the additional 12 findings listed first below. It retains the
clickable prototype's desktop layout, native platform appearance, and all three
preparation modes. Linux is the verification target.

## Invariant and implementation boundary

One project owns content and settings; one playback controller owns presentation
and capture state. The next action must follow those authorities everywhere.
Application preferences and current-talk settings must not appear interchangeable.
Worker completion must preserve the result shown by its success handler.

The implementation removes the competing Quick start button, the duplicate next-step
label policy, the extra restart button, irrelevant simultaneous voice controls,
and the ordinary-user metadata-file chooser. It reshapes existing dialogs and
handlers. A computed next-step decision replaces the competing branches; stacked
voice panels reuse the existing bindings. Existing capture/session metadata gains
a title and creation timestamp; no new service or workflow state is introduced.
The user approved up to **120 net additional production lines** for this pass.

## Latest walkthrough: all 12 findings

The welcome screen uses the existing project boundary, and completed playback
retains its finished state during export. Removing the nested voice-library dialog
leaves one settings transaction and one progress owner. No new persisted state,
workflow flags, services or timers were introduced.

| Finding | Implemented behavior |
| --- | --- |
| 1. Duplicate, centered opening controls | One opening area near the top. The document toolbar appears only after a talk is opened. Sign-in stays in the guided preparation flow. |
| 2. Empty application shows talk controls | Hide summary, recording status and document progress until a talk exists. Import still shows operation progress. Previous recordings remain available from File. |
| 3. Vague setup completion | Save and return to talk explains the transition; General explains writing/reviewing text next. |
| 4. Generated text called Approved | Text ready reports freshness; Prepared explicitly asks the user to review before Prepare audio. Manual edits retain their approval guard. |
| 5. Repeated guidance and crowded editor | Remove whole-talk instructions from the slide inspector and idle dialogs. Simplify thumbnail/version captions and Quick layout. Enlarge reuses the existing image widget inside AutoTalk. |
| 6. Duplicate voice pickers | Predefined voices have one picker. Saved voices contains only reusable profiles, in Talk settings with one final Save/Cancel. |
| 7. Hidden library progress | Removing the nested dialog lets saved-voice previews use the settings dialog's existing spinner, elapsed status and Cancel. |
| 8. Display/audio under Recording | Presentation owns display, system audio and background music; Recording owns optional capture. |
| 9. Missing fullscreen mouse navigation | Fullscreen shares Previous/Next actions with presenter controls and explicitly says that returning pauses playback. |
| 10. Finished view promotes restart | Return to editing/end-and-save becomes primary. No remaining/buffered countdown at completion. Replay is explicitly in the Presentation menu. Automatic video export preserves finished state. |
| 11. Ambiguous recording Save | Ready outputs offer Save a copy / another format; unfinished recordings offer Save unfinished recording. |
| 12. Translation source looks translated | The label directly above the text says Source text — waiting for the selected language's translation until replaced or translated. |

## Second walkthrough: all 15 findings

The follow-up keeps the same owners and persistence format. It removes stale
message copying, a redundant voice label/timer restart, a one-use callback, and
hover-dependent controls. The fullscreen toolbar shares the existing End action;
preview creation and design acceptance share the same artifact path. No new
workflow flags, timers, services, or model-selection policies were introduced.
Slide enlargement now reuses the existing slide image widget in a resizable
AutoTalk dialog; it no longer opens another application.

| Finding | Implemented behavior |
| --- | --- |
| 1. Basic setup skipped | Import opens General for Prepared/Realtime with duration, language and audience together. Quick retains its direct duration/language inputs. |
| 2. Ambiguous approval | Write talk text, Prepare audio and Approve all slide text distinguish text from sound. Approval does not copy the selected slide's words. |
| 3. Invalid voice actions | Personal voice preview needs an existing recording; design preview needs a description. Acceptance appears after Listen and needs the matching completed sample. Changing the design invalidates acceptance. |
| 4. Preview wait | The existing spinner moves into the open dialog; elapsed time and Cancel remain visible. Help explains both first downloads and recurring engine startup. |
| 5. Voice names | Picker and library describe character and native language. Persistent speaker identifiers remain unchanged; all supported talk languages remain available. |
| 6. Fullscreen mouse controls | A native bottom toolbar always offers Pause/Continue, Return to controls, and the existing End/save action. The pointer remains visible. |
| 7. Finished presentation | Finished/stopped playback cannot resume with Space or Continue. Return to editing remains available, including after automatic video saving. |
| 8. Old recording versus new intent | Current recording intent/capture/saving is shown first. A separate dated saved-file link remains available without replacing that state. |
| 9. Recording source | The main recording checkbox names slides/narration or screen/system audio. Talk settings → Recording changes the source. |
| 10. Find versus create video | Opening the selected saved recording is primary; creating a separate slides-and-speech export is below it and explicitly excludes live demos. Table space follows content, with wrapping titles. |
| 11. Language changes | Untranslated drafts cannot be approved at the Project boundary. Translate processes remaining draft slides, preserving manually replaced slides and the original language version. A user may instead replace each draft's text before approval. |
| 12. Slide detail | Navigator captions wrap and include a text-derived heading, skipping text repeated throughout a multi-slide deck; full captions have tooltips. Enlarge slide reuses the slide image widget in a larger resizable AutoTalk window. |
| 13. Duration | Fit duration sits beside target and measured audio duration in the main window. |
| 14. Stale guidance | Idle guidance is recomputed from the current next step; old operations remain in Preparation details. Hidden dialogs no longer inherit the last error as their current instruction. |
| 15. Inapplicable settings | Background volume is a labelled percentage; volume/loop/remove require a track. Use preset requires a saved preset. Conference context is explicitly optional. |

Voice descriptions paraphrase the [official Qwen speaker table](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base/blob/dc3a91051aad39bf1f66d58cd89988b3b1084f0b/README.md).
Descriptions guide selection; listening remains the check for the chosen language.

## Original review coverage

| Review group | Implemented behavior |
| --- | --- |
| 1. Opening slides | Open PDF and Open saved talk appear once in the welcome content, then in the toolbar after opening a talk. Menu equivalents remain. PDF import creates a unique project under the source PDF folder’s `autotalk` subdirectory without a second chooser. Save a copy selects another location. |
| 2. First-time readiness | Codex acquisition checks ChatGPT sign-in and guides browser login. Automatic preparation and timing fitting complete that step before loading speech. Cancellation closes the client. Audio-only resume and prepared playback do not require a new ChatGPT connection. First-use download size and wait are explained. |
| 3. Mode consistency | The toolbar, menu and Quick guidance use one computed next step. There is one start action. All three modes have visible descriptions. Existing manual edits retain their review guard. Interrupted Realtime has a visible Resume preparation action. |
| 4. Honest guidance | A fresh PDF says the slides are ready and to create speech. Actual duration/audience/context changes identify the changed field and show the resulting next step. |
| 5. Voice workflows | Predefined voice shows choice and sample; personal voice shows recording/import and transcript; design shows description, audition, and acceptance. Listen switches to Stop sample during preview. No irrelevant recording/design controls appear with predefined voices. |
| 6. Recording lifecycle | The footer distinguishes recording intent, permission wait, recording, slides-finished-but-still-recording, saving, and saved video with open links. End explicitly includes saving while capture is active. Slide-only recording still finishes automatically; desktop recording continues for demos. |
| 7. Presentation actions | Presenter view emphasizes Start, Pause or Continue according to state. End remains separate and reachable. Previous/next and live-demo controls are secondary; restart remains a menu command. |
| 8. Recording discovery | The table shows talk title, date, duration and Ready / Needs saving. Empty-state guidance and disabled selection actions replace the metadata picker. Legacy recordings remain recoverable. Direct prepared exports retain open-file/folder links after job completion. |
| 9. Basic/advanced separation | Duration/language, conference, voice and recording have clear sections. Talk Advanced contains timing tolerance, multilingual arrangement, model/reasoning, sampling and encoding. Preferences contains application settings. Slide advanced controls state their scope and collapse by default; slide and speech regain space at minimum window size. |

## Verification boundaries

Automated user journeys, real widget interactions, native Breeze screenshots,
startup measurements, and an actual Codex/Qwen Realtime run are recorded in
[VERIFICATION.md](../VERIFICATION.md). These checks are not a recruited usability
study. Earlier Windows/macOS, physical-microphone and sustained desktop-capture
qualification limits remain unchanged. Speech chunking and sampling defaults are
outside this pass and remain unchanged.
