# AutoTalk interaction inventory

Recorded: **26 September 2026**. Scope: the implementation before the 27 September UX refactor after restoring
fixed Start commands, removing text approval, and correcting audio-preview state.
This is a preserved historical inventory of behavior, not a redesign or a list of approved
future features. Linux is the inspected platform; native dialogs vary by desktop.

The [accepted UX placement contract](UX_PLACEMENT_PROPOSAL.md) replaces these
locations. See its [implementation verification](UX_PLACEMENT_VERIFICATION.md)
and the [current user guide](../USER_GUIDE.md) for today's routes. Priority and
feature coverage in this baseline remain traceable; obsolete routes below are
retained as review evidence, not current instructions.

Each functional group is subdivided by **where the user currently encounters the
control**: main window, menu, dialog, presentation window, or external system.
An operation with multiple access points can appear in multiple location tables;
those entries describe the same operation, not separate capabilities. Keyboard
shortcuts are listed beside their commands. An empty location subgroup is omitted.

## Importance and availability

| Importance | Meaning |
| --- | --- |
| 1 | Essential to the ordinary open → configure → prepare → present journey, or essential when its prerequisite is needed. |
| 2 | Commonly useful supporting operation. |
| 3 | Occasional or specialized operation. |
| 4 | Technical tuning, diagnosis or maintenance. |

These rankings are an assessment of user-task importance, not implementation
priority or measured usage. A specialized operation can be essential to a user
who needs that feature. The inventory does not establish usability acceptance.

Most authoring controls require a loaded project, no background operation, no
active presentation/fullscreen window and no voice recording. Additional
restrictions depend on mode, voice source, language, audio readiness and engine
state. Disabled controls remain part of this inventory. The upper-right Start
command stays visible and enabled for a loaded talk; it does not bypass missing
permissions, errors or explicitly configured timing requirements.

## Contents

- [Application, projects and files](#application-projects-and-files)
- [Workspace navigation and layout](#workspace-navigation-and-layout)
- [Talk configuration and conference context](#talk-configuration-and-conference-context)
- [Narration and text editing](#narration-and-text-editing)
- [Slide audio and imported sound](#slide-audio-and-imported-sound)
- [Voice selection, personal voices and library](#voice-selection-personal-voices-and-library)
- [Delivery and vocal attributes](#delivery-and-vocal-attributes)
- [Presentation and playback](#presentation-and-playback)
- [Recording, export and recorded files](#recording-export-and-recorded-files)
- [Timing and mode-specific preparation](#timing-and-mode-specific-preparation)
- [ChatGPT, Codex and synthesis](#chatgpt-codex-and-synthesis)
- [Speech model and GPU lifecycle](#speech-model-and-gpu-lifecycle)
- [Help, progress and diagnostics](#help-progress-and-diagnostics)
- [Shared dialogs and standard interactions](#shared-dialogs-and-standard-interactions)
- [Read-only feedback and absent controls](#read-only-feedback-and-absent-controls)
- [Source coverage](#source-coverage)

## Application, projects and files

### Main window — welcome page and toolbar

| Importance | Control / interaction | Current behavior |
| --- | --- | --- |
| 1 | Open PDF… — welcome and toolbar buttons | Opens the native PDF chooser and creates a project. New projects go in the source PDF folder's `autotalk` subdirectory. Repeated imports use distinct project folders. |
| 1 | Open saved talk… — welcome and toolbar buttons | Opens the native AutoTalk project-file chooser. |
| 1 | Save — toolbar button | Saves project settings and narration. Preparation/start and normal closing also save; narration edits are not written to disk on every keystroke. |

The welcome page appears without a project; the toolbar appears with a project.
They are alternative locations, not two simultaneous Open PDF controls.

### Menus and shortcuts

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 1 | File → Open PDF…; Ctrl+N | Same PDF import as the main-window button. |
| 1 | File → Open saved talk…; Ctrl+O | Same project open operation. |
| 2 | File → Open recent → project entry | Opens a previously used project. |
| 1 | File → Save; Ctrl+S | Same project save operation. |
| 2 | File → Save a copy…; Ctrl+Shift+S | Chooses a destination directory and creates a separate project copy. |
| 3 | File → Open talk folder | Opens the project directory in the system file manager. |
| 1 | File → Quit; Ctrl+Q | Closes AutoTalk; saves the project and handles unfinished work. |

### Native dialogs, desktop and command line

| Importance | Interaction | Current access / choices |
| --- | --- | --- |
| 1 | Start the application | Executable or available desktop launcher. Existing ChatGPT sign-in is checked automatically. |
| 2 | Start with a saved project | `autotalk path/to/talk.autotalk.json`. The positional argument is a saved project, not a PDF-import argument. |
| 1 | Select an input file | Native open dialog: directory navigation, filename/path, file selection, Open or Cancel. |
| 2 | Select a copy destination | Native directory chooser: navigate, select directory, accept or cancel. |
| 3 | Minimize, maximize, restore, move or resize | Desktop window controls and borders. |
| 1 | Close using the window decoration | Same application close handling as Quit. |

Closing with unfinished recording/export presents the choices documented under
[shared dialogs](#shared-dialogs-and-standard-interactions).

## Workspace navigation and layout

### Main window

| Importance | Control / interaction | Current behavior |
| --- | --- | --- |
| 1 | Mode dropdown | Prepared, Quick or Realtime. Changes the working mode/page. |
| 1 | Talk settings… button | Opens talk configuration. |
| 1 | Slide thumbnail list | Selects the current slide. |
| 2 | Language-version dropdown above thumbnails | Selects an existing version's narration/audio. |
| 3 | Enlarge slide… button | Opens a larger preview dialog. |
| 3 | Editor splitter handles | Drag to resize navigator, central editor and inspector. |
| 3 | Advanced slide options toggle | Expands/collapses slide-specific settings in the inspector. |

### Menus and shortcuts

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 1 | Talk → Mode: Prepared / Quick / Realtime | Same mode choices as the toolbar. |
| 1 | Talk → Talk settings…; Ctrl+T | Same settings dialog. |
| 2 | View → Slide editor | Selects the editing workspace. |
| 2 | View → Presenter view | Selects the presenter-controls workspace in the main window. |
| 3 | View → Slide navigator | Checkable visibility toggle. |
| 3 | View → Slide inspector | Checkable visibility toggle. |
| 3 | View → Restore default layout | Restores pane visibility and default proportions. |
| 3 | View → Enlarge slide… | Same enlarged-preview dialog. |
| 2 | Settings → Preferences…; Ctrl+, | Opens application preferences. |

### Dialogs

| Importance | Control / interaction | Current behavior |
| --- | --- | --- |
| 2 | Talk-settings navigation list | General, Conference, Voice, Delivery, Presentation, Recording, Advanced, Saved voices. |
| 3 | Preferences navigation list | General and Speech engine. General currently provides information, not appearance selectors. |
| 3 | Enlarged-preview dialog | View/resize the enlarged slide; close using the dialog/window controls. |
| 3 | Settings scrollbars / mouse wheel / keyboard | Navigate content that exceeds the dialog height. |

The presenter workspace is part of the main window. The fullscreen presentation
is a separate window; the two are not interchangeable locations.

## Talk configuration and conference context

### Main window — Quick page

| Importance | Control | Current behavior |
| --- | --- | --- |
| 1 | Talk duration number field | Sets the target, 0.1–240 minutes. |
| 1 | Spoken language dropdown | Chooses the talk language/version. |

These two widgets move into Talk settings → General while that dialog is open.
Prepared and Realtime expose them through General rather than directly on the
editor page.

### Talk settings dialog — General

| Importance | Control | Current behavior |
| --- | --- | --- |
| 2 | Talk title text field | Changes the displayed project title. |
| 1 | Talk duration number field | Target duration, 0.1–240 minutes. |
| 1 | Spoken language dropdown | Opens an existing version or creates one when needed. |
| 2 | Audience text field | Describes audience knowledge/background; Quick does not use this customization. |
| 2 | Save and return to talk | Saves configuration and closes the dialog. |
| 2 | Cancel / dialog close | Restores the starting talk configuration. |

Language choices: **English, German, French, Spanish, Italian, Portuguese,
Russian, Chinese, Japanese, Korean**.

### Talk settings dialog — Conference

| Importance | Control | Current behavior |
| --- | --- | --- |
| 2 | Talk objective text field | Specifies what the talk should communicate. |
| 2 | Conference website URL field | Stores the URL; typing alone does not fetch it. |
| 2 | Read conference website button | Reads the site and replaces the scope box with an editable extracted summary. |
| 2 | Conference scope text box | Manual topics, tracks, context and edits to the extracted summary. |
| 3 | Source links | Open source pages in the external browser. |

Conference customization is unavailable in Quick. Existing narration is retained
when these fields change; changing context is not an instruction to rewrite it.

## Narration and text editing

### Main window — slide editor

| Importance | Control / interaction | Current behavior |
| --- | --- | --- |
| 1 | Narration text editor | Enter, replace, select or edit the selected slide's wording in memory. |
| 1 | Create slide text button | Calls Codex for a slide with no narration. |
| 1 | Rewrite slide text… button | Opens replacement confirmation, then calls Codex for that slide. |
| 2 | Translate slide text button | Appears for a translation draft; calls Codex to translate it. |
| 3 | Include in presentation checkbox | Includes/excludes the selected slide; cannot exclude the final included slide. |

The three text-generation labels are states of one selected-slide button.

### Main window — expanded slide inspector

| Importance | Control | Current behavior |
| --- | --- | --- |
| 3 | Target duration for this slide | Automatic at zero, otherwise up to 14,400 seconds. |
| 3 | After this slide dropdown | Advance automatically; Pause for live demo; Wait for presenter. |
| 3 | Language / audio clips… button | Opens the slide extras dialog. |

Delivery inheritance and overrides are listed in [delivery](#delivery-and-vocal-attributes).

### Menus and shortcuts

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 1 | Talk → Write or translate talk text… | Generates missing/untranslated text for included slides without starting audio or presentation. |
| 2 | Same whole-talk command when all included text exists | Offers confirmation to rewrite the existing whole talk. |
| 1 | Talk → Create slide text / Rewrite slide text… / Translate slide text | Mirrors the selected-slide button and its current label. |
| 2 | Edit → Undo; Ctrl+Z | Reverses an available edit in the focused supported editor. |
| 2 | Edit → Redo; Ctrl+Shift+Z | Reapplies an undone edit. |
| 2 | Edit → Cut; Ctrl+X | Cuts the selection in the focused editable control. |
| 2 | Edit → Copy; Ctrl+C | Copies selected text where supported. |
| 2 | Edit → Paste; Ctrl+V | Pastes into the focused editable control. |
| 2 | Edit → Select all; Ctrl+A | Selects the focused supported control's content. |
| 3 | Edit → Find in talk text…; Ctrl+F | Opens a search dialog; searches the active narration editor, not every slide. |
| 2 | Edit → Add language version… | Opens the new-version language selection dialog. |

### Dialogs and native text controls

| Importance | Control / interaction | Current behavior |
| --- | --- | --- |
| 2 | Rewrite slide / Rewrite all talk text confirmation | Yes performs replacement; No retains the wording. |
| 3 | Find in talk text | Enter search term; accept/cancel. |
| 2 | New language version | Select a supported language; accept/cancel. |
| 3 | Slide extras → Language passage dropdown | Select the language marker to insert. |
| 3 | Slide extras → Insert language passage | Inserts a marker such as `[German]` into the narration editor. |
| 2 | Native editor context menu | Standard supported cut/copy/paste/undo/redo/select-all interactions; availability follows editor state. |

The multilingual arrangement selector is listed under mode/settings below.

## Slide audio and imported sound

### Main window — slide editor

| Importance | Control | Current behavior |
| --- | --- | --- |
| 1 | Create slide audio | Calls Qwen for the current usable narration, saves and previews the new recording. |
| 1 | Play audio | Plays the existing selected-slide recording, including a retained older recording after text edits. |
| 1 | Stop audio | Stops the preview; the Play audio button changes to this label during playback. |

Create slide audio can request another performance of unchanged wording.
Presentation reuse separately checks whether saved audio matches current speech
inputs. Failed/cancelled replacement preserves the prior completed file.

### Talk menu

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 2 | Regenerate slide audio | Same operation as the editor's Create slide audio button. |
| 1 | Play audio / Stop audio | Same preview operation and current label as the editor button. |

### Slide language and audio clips dialog

Access: inspector → Advanced slide options → Language / audio clips….

| Importance | Control | Current behavior |
| --- | --- | --- |
| 3 | Slide audio clips dropdown | Selects the clip to configure. |
| 3 | Add… | Chooses/imports WAV, MP3, FLAC, OGG, M4A, MP4 or another file. |
| 3 | Remove | Removes the selected clip from the slide. |
| 3 | Volume number field | Clip gain from 0 to 2. |
| 3 | Play dropdown | Places the clip before or after narration. |
| 3 | Dialog close/Escape | Closes this extras dialog; it does not have the talk-settings Save/Cancel transaction. |

### Talk settings dialog — Presentation

| Importance | Control | Current behavior |
| --- | --- | --- |
| 3 | Add background track… / current-track button | Opens a chooser to add or replace talk-wide background audio. |
| 3 | Background volume | 0–100%. |
| 3 | Loop checkbox | Repeats the background track. |
| 3 | Remove background | Removes the background track. |

## Voice selection, personal voices and library

### Talk settings dialog — Voice

| Importance | Control | Current behavior / choices |
| --- | --- | --- |
| 1 | Voice-source dropdown | Choose a voice; Use my own voice; Design a new voice. Selects the relevant control panel. |
| 1 | Predefined-speaker dropdown | Ryan, Aiden, Vivian, Serena, Uncle_Fu, Dylan, Eric, Ono_Anna, Sohee. |
| 2 | Listen to a sample | Generates/plays sample words rather than the selected slide's text. Also auditions a designed voice. |
| 2 | Stop sample | Same button's label while a preview is active; stops it. |
| 2 | Record my voice | Records a personal reference from the system-default microphone; automatic stop after 30 seconds. |
| 2 | Stop recording | Ends the reference recording and imports it. |
| 2 | Import voice recording… | Opens a PCM WAV chooser; accepted reference duration is 3–60 seconds. |
| 2 | Recording transcript text box | Enter/correct the exact words in the reference. Enabled when a reference exists. |
| 3 | Describe the voice text field | Free-text instructions for voice design. |
| 3 | Use this designed voice | Keeps the auditioned sample as the reference for subsequent speech. |
| 2 | Save reusable voice… | Opens a name-entry dialog and saves a reusable library entry. |
| 2 | Saved voices… | Opens the Saved voices section. |

Quick uses its default voice and disables custom voice selection. Recording,
reference-transcript and design controls are shown for their respective sources.

### Talk settings dialog — Saved voices

| Importance | Control | Current behavior |
| --- | --- | --- |
| 3 | Language filter | All languages or a selected supported language. |
| 2 | Voice table row | Selects the voice entry. |
| 2 | Listen to selected voice | Applies the selected voice to the dialog's current talk state and generates/plays its preview. |
| 2 | Use selected voice | Applies the voice and opens the Voice section. |

### Menu, naming and permission dialogs

| Importance | Access / decision | Current behavior |
| --- | --- | --- |
| 2 | Talk → Saved voices… | Opens the same Saved voices section. |
| 2 | Save reusable voice naming dialog | Enter a voice name; accept or cancel. |
| 1 when needed | Operating-system microphone permission | Allow or deny where the platform requires permission. |
| 2 | Dialog operation area → Stop voice recording | Alternate stop control while recording a reference. |

The microphone follows the system default; there is no dedicated input-device
dropdown on the Voice page.

## Delivery and vocal attributes

### Talk settings dialog — Delivery

| Importance | Control | Current behavior / choices |
| --- | --- | --- |
| 2 | Writing / delivery style dropdown | Professional; Conversational; Energetic; Calm and understated; Lightly humorous; Academic; Storytelling; Inspirational. Selecting a style also applies its corresponding vocal-attribute preset. |
| 3 | Saved delivery presets dropdown | Selects a saved preset. |
| 3 | Use preset | Applies the selected delivery settings. |
| 3 | Save preset… | Opens a naming dialog and saves the current delivery settings. |
| 3 | More vocal attributes toggle | Expands/collapses the detailed controls below. |

### Talk settings dialog — Delivery → More vocal attributes

| Importance | Control | Current choices / restrictions |
| --- | --- | --- |
| 3 | Pitch dropdown | Model default, Low, Medium, High. |
| 3 | Texture dropdown | Model default, Clear, Warm, Breathy, Raspy. |
| 3 | Energy dropdown | Model default, Low, Moderate, High. |
| 3 | Pace dropdown | Model default, Slow, Moderate, Brisk. |
| 3 | Age dropdown | Model default, Young adult, Middle-aged adult, Older adult; enabled for voice design. |
| 3 | Articulation dropdown | Model default, Natural, Precise, Relaxed. |
| 3 | Projection dropdown | Model default, Soft, Conversational, Confident. |
| 3 | Accent dropdown | Model default, Beijing Mandarin, Sichuan Mandarin; enabled for Chinese. |
| 3 | Expression dropdown | Model default, Restrained laughter, Audible sigh, Thoughtful hesitation, Enthusiastic interjection. |
| 3 | Speaker background / persona | Free-text guidance. |
| 3 | Custom vocal directions | Additional free-text delivery guidance. |
| 3 | Gradual delivery across slides | Free-text description of progression through the talk. |

Direct vocal controls are disabled for Base voice cloning and Quick. Style is
also disabled in Quick. These are requested delivery attributes, not guarantees
of an exact acoustic result.

### Main window — expanded slide inspector

| Importance | Control | Current behavior |
| --- | --- | --- |
| 3 | Use talk delivery checkbox | Chooses inherited delivery for the selected slide. |
| 3 | Delivery override text field | Slide-specific instructions; enabled for supported voice/mode combinations when inheritance is off. |

### Naming dialog

| Importance | Decision | Current behavior |
| --- | --- | --- |
| 3 | Save delivery | Enter preset name; accept or cancel. |

## Presentation and playback

### Main window — upper-right command

| Importance | Interaction | Current behavior |
| --- | --- | --- |
| 1 | Prepare and start — Prepared | Preserves existing words/current audio, prepares missing content, then presents after all included slides are ready. |
| 1 | Start — Quick | Automatic preparation/start using Quick defaults, subject to the selected timing policy. |
| 1 | Start — Realtime | Begins when sufficient opening audio exists; remaining preparation continues. |
| 2 | Start while another operation runs | Requests startup after successful completion. Repeated clicks do not create duplicate workers. Failure/cancellation does not trigger queued startup. |
| 2 | Start after interrupted Realtime preparation | Reuses completed work and prepares unfinished content. |
| 2 | Start while a presentation already exists | Raises the presentation window and invokes playback/resume. |
| 2 | Start after presentation completion | Ends the completed session before starting again; pending work may defer startup. |

### Main window — presenter workspace

| Importance | Control | Current behavior |
| --- | --- | --- |
| 1 | Start presentation | Opens already playable content fullscreen; does not prepare missing content. |
| 1 | Pause | Pauses playback. |
| 1 | Continue | Reopens fullscreen at the retained position. |
| 1 | Previous / Next | Moves between included slides. |
| 2 | Pause for a live demo | Pauses narration and leaves fullscreen. Screen recording can continue. |
| 1 | End presentation | Ends the session and returns to editing/Quick. |
| 1 | End presentation and save video | Ending label when a recording remains active. |
| 2 | Return to editing | Ending label after presentation completion without active capture. |

Start/Pause/Continue visibility follows playback state. The ending labels are
states of one end control.

### Menus and shortcuts

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 1 | Talk → Start / Prepare and start | Same command as the upper-right button. |
| 1 | Presentation → Present fullscreen; F5 | Starts already playable content from the beginning. |
| 2 | Presentation → Start from selected slide; Shift+F5 | Starts at the selected slide. |
| 1 | Presentation → Continue presentation; F6 | Resumes at the retained position. |
| 1 | Presentation → Pause | Pauses playback. |
| 1 | Presentation → Previous slide / Next slide | Same slide navigation as the presenter buttons. |
| 2 | Presentation → Restart from beginning | Restarts playback. |
| 2 | Presentation → Live demo / leave fullscreen | Same live-demo operation. |
| 1 | Presentation → End presentation / ending variant | Same end operation and state-dependent caption. |
| 2 | Presentation → System audio settings… | Opens operating-system sound controls. |

### Fullscreen presentation window

| Importance | Control / shortcut | Current behavior |
| --- | --- | --- |
| 1 | Previous slide; Left / Page Up | Moves backward. |
| 1 | Next slide; Right / Page Down | Moves forward. |
| 1 | Pause / Continue toolbar control; Space | Toggles active playback/pause; does not restart a completed talk. |
| 2 | Pause and return to controls (Esc); Escape | Closes fullscreen and pauses if playing. |
| 1 | End presentation / ending variant | Ends the presentation session. |
| 2 | Close fullscreen window | Leaves fullscreen and pauses if playing; differs from ending the session. |

### Talk settings dialog and operating-system controls

| Importance | Control | Current behavior |
| --- | --- | --- |
| 2 | Presentation → Fullscreen display dropdown | Selects an available screen. |
| 2 | Presentation → System audio settings… button | Opens Plasma/GNOME/PulseAudio sound controls on Linux, or the platform sound settings elsewhere. |
| 2 | System audio routing / volume controls | Choose output device, routing and volume externally; exact controls depend on the desktop. |
| 2 | Presentation → Test audio button | Plays a test tone through the current output. |

## Recording, export and recorded files

### Main window — footer and overview

| Importance | Control | Current behavior |
| --- | --- | --- |
| 1 | Record presentation as a video checkbox | Enables/disables recording at presentation start. |
| 2 | Videos / recordings… button | Opens the recording browser. |
| 1 | Saved-output Open video / audio link | Opens the currently selected available output in its associated application. |
| 2 | Saved-output Open folder link | Opens the containing folder. |

The recording checkbox moves from the footer into the Recording settings section
while the talk-settings dialog is open; it is the same widget and setting.

### File menu

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 2 | Export / recordings… | Opens the same recording browser. |

### Talk settings dialog — Recording

| Importance | Control | Current behavior / choices |
| --- | --- | --- |
| 1 | Record presentation as a video checkbox | Same recording intent as the footer. |
| 2 | Recording source dropdown | Slide video + narration; Screen + system audio (Linux). |
| 2 | Include microphone in screen recording checkbox | Adds live commentary; enabled for screen recording. |
| 2 | Video destination text field | Explicit destination or the project's default recordings location. |
| 2 | Choose video destination… button | Opens a native MP4 save dialog. |

### Talk settings dialog — Advanced

| Importance | Control | Current behavior / choices |
| --- | --- | --- |
| 3 | Recording pauses dropdown | Keep fullscreen pauses but omit time outside fullscreen; keep all elapsed time; omit manual pauses, buffering and outside-fullscreen time. Enabled for slides recording. |
| 3 | Export audio sample rate dropdown | 24 kHz (native), 44.1 kHz, 48 kHz. |
| 3 | MP4 / M4A audio encoding dropdown | AAC 96, 128 or 192 kbit/s. |

Export format choices are not a selector for synthesis-model quality or size.

### Export / recordings dialog

| Importance | Control | Current behavior |
| --- | --- | --- |
| 2 | Recordings table row | Selects a recording; columns show talk, date, duration and Ready / Needs saving. |
| 1 | Open video / audio | Opens an existing selected output. |
| 2 | Open folder | Opens its containing directory. |
| 2 | Save unfinished recording… | Chooses destination/format and exports retained session data. |
| 3 | Save a copy / another format… | Alternate caption for a recording with an existing output. |
| 2 | Create slides-and-speech video or audio… | Exports a prepared talk without presenting; live demos are not included. |
| 2 | Cancel operation | Cancels ongoing export/save while the operation control is present. |
| 2 | Close / dialog close | Closes the browser when active-work rules permit. |

### Native save and screen-sharing dialogs

| Importance | Interaction | Current choices |
| --- | --- | --- |
| 2 | Select output path and filename | Native save dialog; accept or cancel, with overwrite confirmation where applicable. |
| 3 | Select exported format | MP4 video, WAV audio or M4A audio in export/recovery dialogs. |
| 1 when needed | Select screen-sharing source | Linux desktop portal when screen recording starts. Independent of the fullscreen-display dropdown. |
| 1 when needed | Authorize or cancel screen sharing | Share or cancel through the portal; AutoTalk cannot grant permission itself. |

## Timing and mode-specific preparation

### Main window — overview

| Importance | Control | Current behavior |
| --- | --- | --- |
| 2 | Fit duration… | Opens confirmation, then can revise narration and regenerate audio up to three times. Enabled while editable when every included slide has narration; prepared audio is not required. |

### Talk settings dialog — Advanced

| Importance | Control | Current choices / range |
| --- | --- | --- |
| 3 | Allowed timing difference | 0–600 seconds. |
| 3 | Pause between slides | 0–10 seconds. |
| 3 | Language arrangement | Separate versions and mixed passages; separate versions with one language per slide; separate single-language versions. |
| 3 | Quick timing policy | Generate once, then start; Fit, then start (up to three revisions); Require timing match before start. Visible in Quick. |
| 3 | Realtime narration | Write the complete script first; Plan the deck and write ahead by slide. Visible in Realtime. |
| 3 | Realtime speech priority | Consistency first; Earliest playback. Visible in Realtime. |
| 4 | Realtime startup/refill buffer | 2–30 seconds. Selecting consistency/earliest sets 5/2 seconds respectively before further manual adjustment. |

### Confirmation dialogs

| Importance | Decision | Current choices |
| --- | --- | --- |
| 2 | Fit duration | Yes permits text/audio revisions; No cancels. |
| 2 | Switch to Quick? | Conditional warning when switching with current audio: Yes adopts Quick defaults; No retains the prior mode. |

## ChatGPT, Codex and synthesis

### Talk settings dialog — Advanced

| Importance | Control | Current behavior / choices |
| --- | --- | --- |
| 1 when needed | Sign in | Enabled when not signed in and the application is editable; starts browser authentication. |
| 3 | Sign out | Enabled when signed in and editable; signs out of the shared Codex account on this machine. |
| 3 | Model dropdown | Account default or discovered image-capable Codex models. Default and explicit entries use the same model display names. |
| 3 | Reasoning effort dropdown | Default or the levels returned for the selected model. |
| 4 | Override main speech generator sampling defaults checkbox | Enables/disables explicit synthesis sampling fields. |
| 4 | Temperature | 0–2. |
| 4 | Top k | 1–200. |
| 4 | Top p | 0.01–1. |
| 4 | Repetition penalty | 1–2. |
| 4 | Max new tokens | 128–2,048. |

Quick uses account-default Codex choices and default synthesis settings. The
sampling controls target the main speech generator, not a separately exposed
acoustic-code generator.

### Settings menu

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 3 | Codex model & reasoning… | Opens the same Advanced section. |

### External browser and operation controls

| Importance | Interaction | Current behavior |
| --- | --- | --- |
| 1 when needed | Complete ChatGPT authentication | Browser-based sign-in/authorization opened by Codex. Generation can guide the user into this flow when required. |
| 2 | Cancel waiting for sign-in | AutoTalk's Cancel operation control cancels the waiting authentication operation. |

## Speech model and GPU lifecycle

### Main window — status bar

| Importance | Control | Current behavior |
| --- | --- | --- |
| 2 | Speech engine: state… button | Opens Preferences → Speech engine. Its text also reports the current engine state. |

### Settings menu

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 2 | Speech engine… | Opens the engine page. |
| 2 | Load speech model now | Same explicit load operation as the engine-page button. |
| 2 | Unload speech model now | Same explicit unload operation. |

### Preferences dialog — Speech engine

| Importance | Control | Current behavior / choices |
| --- | --- | --- |
| 2 | Load model now / Load selected model | Loads the configured model; label changes if a different model is already loaded. Enabled according to project/configuration and engine state. |
| 2 | Unload model now | Requests release when the loaded model is available for release. |
| 3 | When to load an unloaded model — radio buttons | When speech is first needed; When I start a presentation. |
| 3 | When to release a loaded model — radio buttons | Never until AutoTalk closes; When presentation ends; After five idle minutes; After each preparation or voice preview. |
| 3 | Check for model updates… | Checks upstream revision availability; does not download or replace model files. |
| 3 | Save | Commits the selected automatic policies. |
| 3 | Cancel | Restores saved policy choices. Explicit load/unload operations already performed remain effective. |
| 2 | Cancel operation | Cancels loading/update checking while an operation is active. |

### Result dialog

| Importance | Interaction | Current behavior |
| --- | --- | --- |
| 3 | Read model-update result and dismiss | Displays pinned/upstream revisions and whether a different revision exists. |

## Help, progress and diagnostics

### Main window and active section dialogs

| Importance | Control / interaction | Current behavior |
| --- | --- | --- |
| 2 | Cancel operation | Shown in the footer or active section dialog during work. Cancels preparation/other work, not merely playback. |
| 2 | Stop voice recording | Conditional operation-button label in dialogs while recording a reference. |
| 3 | Preparation details | Main-window button toggles the embedded log. |
| 3 | Select/copy log or presenter text | Standard supported read-only text interactions. |

### Menus and information dialogs

| Importance | Entry | Current behavior |
| --- | --- | --- |
| 3 | View → Preparation details | Toggles the same embedded log. |
| 3 | Help → Diagnostics | Shows/focuses the log; does not open a separate dialog. |
| 2 | Help → Getting started… | Opens introductory information. |
| 3 | Help → Keyboard shortcuts… | Opens the shortcut reference. |
| 4 | Help → About AutoTalk… | Opens application/version/component information. |
| 3 | Information-dialog close/OK | Dismisses these information dialogs. |

### Command line

| Importance | Invocation | Current behavior |
| --- | --- | --- |
| 4 | `autotalk --help` | Displays command-line usage. |
| 4 | `autotalk --smoke-test` | Hidden diagnostic switch: launches and closes after a short interval. Can accompany a saved-project argument. |

## Shared dialogs and standard interactions

### Conditional close and error dialogs

| Importance | Control / decision | Current behavior |
| --- | --- | --- |
| 2 | Finish saving and close | Offered when closing with unfinished recording/export; finishes saving before exiting. |
| 2 | Close and save later | Closes while retaining recoverable recording data. |
| 2 | Cancel — unfinished-recording close dialog | Keeps AutoTalk open. |
| 2 | Dismiss error/warning | Acknowledges the message; retry, if applicable, uses the original action. There is no universal Retry button. |
| 2 | Close/cancel settings during active work | Can be refused with an instruction to stop the operation/reference recording first. Preferences has its own policy-editing availability. |

### Standard controls throughout the application

| Importance | Interaction | Current access / scope |
| --- | --- | --- |
| 3 | Move keyboard focus | Tab / Shift+Tab, using Qt focus order. |
| 3 | Activate a focused control | Standard Qt button, checkbox, radio-button and menu keyboard behavior. |
| 3 | Edit numeric values | Typing, spinner arrows and supported keyboard/wheel behavior. |
| 3 | Select a dropdown/list/table item | Mouse or standard Qt keyboard navigation. |
| 3 | Scroll overflowing content | Scrollbars, wheel and supported navigation keys. |
| 3 | Select/copy text in supported read-only controls | Native selection/context menus; global Edit-menu availability can differ from local context-menu availability. |
| 3 | Close a dialog | Its buttons, window decoration or Escape where standard Qt behavior permits. |

### Native file, permission and external application controls

| Importance | Interaction | Current access / scope |
| --- | --- | --- |
| 3 | Browse folders, enter paths and choose filenames | Native file/directory dialogs used by PDF/project import, voice/clip/background import, project copy and export. |
| 3 | Select a file-type filter | Native file dialogs, where multiple filters are provided. |
| 3 | Accept/cancel file selection | Native Open/Save/directory buttons. |
| 3 | Confirm output replacement | Native overwrite confirmation when applicable. |
| 1 when needed | Grant/deny microphone access | Platform-owned permission flow. |
| 1 when needed | Choose/authorize/cancel shared screen | Linux portal. |
| 2 | Route sound and adjust device/system volume | External desktop audio settings. |
| 2 | Operate opened video/audio or folder | Associated system player/file manager; their internal controls are not AutoTalk-defined. |

## Read-only feedback and absent controls

### Main-window and dialog feedback

| Surface | Read-only feedback |
| --- | --- |
| Main overview | Talk title, target/measured duration, language, mode explanation. |
| Slide navigator/editor | Slide titles, readiness tooltips, selected-slide status, planned duration, PDF preview. |
| Inspector | Delivery summary and generated notes. Notes are displayed, not exposed as an editable notes field. |
| Audio preview | Waveform, current position and duration. |
| Presenter | Current/next slide, narration display, elapsed/remaining time, buffering/completion state. |
| Main footer | Text/audio progress, operation stages, recording state and saved-output information. Output links are interactive. |
| Preparation details | Log and measured preparation timings. |
| Advanced settings | Account/connection status and synthesis explanations. |
| Speech engine | Selected/loaded model, lifecycle state, policy consequences and unsaved-policy notice. The status-bar version is also a button. |
| Library/recording tables | Voice descriptions/languages and recording title/date/duration/status. Rows can be selected, but cells are not editable. |

### Not currently exposed as dedicated interactions

- Whole-talk audio preparation without presenting or invoking duration fitting.
- Waveform seeking, audio trimming or timeline editing.
- Slide reordering, insertion/deletion, or PDF-page editing inside AutoTalk.
- Voice-library entry deletion/renaming or delivery-preset deletion/renaming.
- A standalone Qwen size/variant dropdown: the model variant follows voice source.
- A separate acoustic-code-generator sampling editor or seed selector.
- An in-app theme/style selector: appearance follows the system.
- A microphone-device dropdown on the reference-recording page.
- A model-update installation button: the exposed operation only checks revisions.
- Text approval or audio approval.
- Per-keystroke narration autosave or an autosave preference.

These absences document current scope. They are not approvals or proposals to add
all of these features. The inventory also does not promise that model capability
names such as singing reconstruction are dedicated UI controls.

## Source coverage

Reviewed application-defined widget/menu construction, settings bindings,
conditional dialogs and controller handlers, fullscreen keyboard handling, and
the native permission/audio boundaries:

- [ui.py](../../src/autotalk/ui.py): main window, menus, section dialogs and shared controls.
- [options.py](../../src/autotalk/options.py): individual settings, ranges and applicability.
- [app.py](../../src/autotalk/app.py): handlers, labels, visibility/enabling, dialogs and command-line launch.
- [playback.py](../../src/autotalk/playback.py): fullscreen controls and keyboard handling.
- [project.py](../../src/autotalk/project.py): language, speaker and style catalogs.
- [recording.py](../../src/autotalk/recording.py): system-default reference microphone.
- [screen_capture.py](../../src/autotalk/screen_capture.py): Linux capture and portal boundary.
- [codex.py](../../src/autotalk/codex.py): external sign-in flow and model discovery.

This document records current interaction placement. The [user guide](../USER_GUIDE.md)
describes task sequences; the [usability record](USABILITY.md) records historical
reviews and the current interaction contract.
