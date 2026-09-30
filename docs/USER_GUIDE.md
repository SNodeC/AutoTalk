# AutoTalk UI user guide

This guide describes the current AutoTalk 0.3 interface, including the speech-engine
task-based placement implemented on 27 September 2026. Instructions use the Linux UI. Windows and
macOS builds have not yet received equivalent native testing; screen recording
with system audio is currently a Linux feature.

AutoTalk turns an existing PDF into a spoken presentation. It creates two separate
things: **talk text** (the words to say) and **audio** (a recording of those words).
You can review both before presenting, or let AutoTalk prepare and present automatically.

## Contents

- [Choose a mode](#choose-a-mode)
- [Find your way around](#find-your-way-around)
- [Open, save and reopen a talk](#open-save-and-reopen-a-talk)
- [Prepared: review before presenting](#prepared-review-before-presenting)
- [Prepare and preview an individual slide](#prepare-and-preview-an-individual-slide)
- [Quick: prepare and start automatically](#quick-prepare-and-start-automatically)
- [Realtime: start while preparation continues](#realtime-start-while-preparation-continues)
- [Conference, audience and objective](#conference-audience-and-objective)
- [Voices and voice samples](#voices-and-voice-samples)
- [Delivery and speaking style](#delivery-and-speaking-style)
- [Languages and versions](#languages-and-versions)
- [Slide settings and additional audio](#slide-settings-and-additional-audio)
- [Present, pause, continue and give a live demo](#present-pause-continue-and-give-a-live-demo)
- [Record a presentation or export a video](#record-a-presentation-or-export-a-video)
- [Manage the speech model and GPU](#manage-the-speech-model-and-gpu)
- [Advanced settings](#advanced-settings)
- [Progress, cancellation and recovery](#progress-cancellation-and-recovery)
- [Menu and keyboard reference](#menu-and-keyboard-reference)
- [Common questions](#common-questions)

## Choose a mode

Choose **Mode** in the toolbar after opening a talk. The highlighted action is
**Prepare and start** for Prepared and **Start** for Quick/Realtime. Its name does
not change with narration or audio readiness.

| Mode | What you do | What AutoTalk does | When presentation starts |
| --- | --- | --- | --- |
| **Prepared** | Set up the talk and optionally edit/preview individual slides. Choose **Prepare and start**. | Preserves existing words/audio and prepares missing content. | Automatically after all included slides are prepared. |
| **Quick** | Choose a PDF, duration and language. | Uses resolved voice, delivery and model settings without conference setup. | Automatically after preparation, subject to the selected timing policy. |
| **Realtime** | Set up duration, language, conference and voice, then choose **Start**. | Prepares opening audio, then continues writing and generating later slides while presenting. | Automatically when enough opening audio is available. |

Use **Prepared** when you need to check wording, names, timing and pronunciation.
Use **Quick** for a minimal setup. Use **Realtime** when you want to begin before
the whole deck's audio is ready and can accept possible buffering.

Realtime is generated narration for your slides. It is not a live conversation
with the audience. It can still take time to start, especially on first use.

Switching modes does not create a separate copy of the talk. For an experiment
you want to keep separate, use **File → Save a copy…** first. Quick preserves the
selected or inherited voice, delivery and model settings. Changing mode alone
does not invalidate matching audio. Quick skips conference and audience customisation.

## Find your way around

The welcome page offers **Open PDF…** and **Open saved talk…**. After opening a talk:

| Area | Purpose |
| --- | --- |
| Document toolbar | Open/save, mode and the fixed **Start / Prepare and start** action. |
| Talk basics | Duration, language/version, **Voice: …** (opens Voice & language), **Talk settings…**. |
| Whole-talk preparation | **Create talk text** and **Create talk audio**, without starting playback. |
| Presentation setup | **Record presentation as a video** and **Presentation settings…**. |
| Left: Slides | Select a slide; hover its thumbnail for inclusion and audio readiness. |
| Centre: Editor | PDF preview, editable narration, separate text/audio/play controls, notes and language insertion. |
| Right: This slide | Inclusion, after-slide action, Timing (budget and pause), Slide voice & delivery, and Additional audio. |
| Bottom | Current recording, last saved result, text/audio counts, operation progress and cancellation. |
| Status bar: Speech engine | Current model state; click for immediate and automatic engine controls. |

Use the **Editor / Presenter** tabs, or their **View** menu entries, to switch
workspaces. This does not start presentation. Quick has a simplified workspace;
choose Prepared or Realtime to edit slides. Drag pane dividers or use **View →
Slide navigator / Slide inspector / Restore default layout**. In both Editor and
Presenter, drag the horizontal divider up or down to resize the slide previews
and narration. Click a slide preview to enlarge that slide; the Presenter’s
**Up next** preview opens the next slide without advancing the presentation.
**View → Enlarge slide…** also opens the current slide.

The project keeps its own PDF copy. If the external source PDF changes, AutoTalk
asks whether to reload when you open the talk, return to its window, or begin
preparation/presentation. **Not now** keeps the saved slides and suppresses that
same change notification for the current session. Missing or inaccessible
originals never prevent opening or presenting the saved talk.

**File → Reload PDF…** also works when the PDF has not changed: it re-reads the
PDF and recreates all slide PNGs. For older projects or missing originals, choose
the source PDF when prompted. Reloading preserves talk settings and language
versions; confidently matched unchanged slides keep their narration and audio.
Changed, new or ambiguously matched slides start without narration or audio.
Existing audio still has to match the current delivery settings before reuse.
The previous project is retained beside the talk in a folder named
`<talk>-before-pdf-<date>-<time>-<identifier>`. Failed or cancelled preparation
leaves the current talk intact. Reloading is unavailable during presentation or
another operation. You can remove the backup manually once satisfied.

Settings open in three distinct windows: **Application defaults**,
**Talk settings — [title]**, and **Slide settings — [number]**. Each window has
flat navigation and only the sections relevant to its scope:

| Page | Settings grouped here |
| --- | --- |
| **Voice & language** | Voice identity, language arrangement, writing style and spoken delivery. |
| **Talk & preparation** | Audience/conference, timing and Prepared/Quick/Realtime policies. |
| **Presentation & recording** | Pauses/after-slide action, recording/output, background track and slide clips. |
| **AI & speech engine** | Codex model/reasoning, Qwen sampling and application GPU controls. |
| **Application** | Account, display selection and system audio access. |

The window title identifies what you are editing; there is no scope selector.
Use **Settings → Application settings…**, the main **Talk settings…** button, or
**Slide voice & delivery… / Additional audio…** in the inspector.
**Duration** in the main row is the only talk-duration editor. The toolbar's
**Mode**, main **Language** selector and main **Record presentation as a video**
checkbox are likewise the only talk-level value editors. Talk settings shows
read-only mode, language and recording values with their source and **Use app**
reset buttons. Reset participates in that dialog's Save/Cancel transaction;
Cancel also restores language versions and their selected version. Application
defaults retain their editable default mode, language and recording controls.

Main voice and presentation shortcuts select talk scope. **Slide voice & delivery…**
and **Additional audio…** in the inspector select slide scope. Account and Speech
engine shortcuts select application scope. Manual model loading prepares the
selected slide's effective voice, or the application default when no talk is open.

The precedence is **slide override → talk setting → application default**. Voice,
language, writing style, spoken delivery, pauses and after-slide action support all
three levels. Workflow, recording, output and technical model defaults support
application and talk levels. Account/device/GPU lifecycle settings remain local to
the application; conference content and files belong to the talk.

**From app / From talk** identifies an inherited value. Edit a field to override it;
**Use app / Use talk** removes that override. Empty directions, zero pause and an
explicit model default are valid choices, distinct from inheritance. Voice summaries
show **Predefined**, **Own**, **Designed**, or **Reference** for ambiguous older
references, together with their scope. Saved is a library location, not a voice type.

Changing application defaults affects existing talks that still inherit them.
Settings saved into the talk override those defaults. To keep a talk independent of
another computer's defaults, choose **Talk settings → Talk & preparation → Keep these
settings for this talk**. Required personal-voice assets are included in the talk.

**Save** keeps changes across the pages of that window, in that scope only.
**Cancel** restores that scope’s starting configuration, including manifest changes
saved during a settings operation. Saving application defaults from a nested window
is not undone by cancelling talk settings. Slide settings stay bound to the slide
identified in the window title.
Account, manual model, external system-audio and explicitly saved library operations
are immediate. Stop a preparation or voice-recording operation started in Settings
before closing it. Closing engine settings during playback does not stop presentation.

Selecting a talk language restores that language's saved version or creates an
empty version while preserving the current version. Changing an individual slide's
language affects only that slide. **Start**, **Create talk text** or **Create slide
text** generates missing narration from the slides and talk context before audio
preparation. Other languages' narration is never used as translation input.
Deliberate slide-language overrides remain in effect. Readiness follows the current target, including after **Use app**,
**Use talk**, Cancel and reopening. Writing style affects later text generation;
spoken delivery changes audio only. Unchanged synthesis inputs reuse current audio.
Previously recorded audio remains available as **Play previous audio** when stale.

**File → Recordings & export…** remains a separate task window; its settings link
opens **Presentation & recording** for the talk.

Appearance follows the system palette and available native widget style; there
is no independent theme picker. File dialogs retain normal directory navigation.

## Open, save and reopen a talk

1. Choose **Open PDF…** and select the slide deck. The current importer accepts
   unencrypted PDFs containing 1–80 slides.
2. AutoTalk creates a project inside an **`autotalk` folder beside the PDF**, using
   the PDF name. For example, `/slides/demo.pdf` creates
   `/slides/autotalk/demo-AutoTalk/`. Further imports use `demo-AutoTalk-2`, and so on.
   Existing projects stay in their current locations and can still be reopened.
3. In Prepared and Realtime, Talk settings opens for audience and conference context.
   Save or Cancel to return; duration and language remain in the main window.
4. Use **Save** or **Ctrl+S** to save your work.

To return later, choose **Open saved talk…** and open its `talk.autotalk.json` file,
or use **File → Open recent**. Opening the original PDF again creates another talk;
it does not reopen your previous narration and audio.

**File → Open talk folder** locates the project. **File → Save a copy…** copies the
project into a chosen parent folder and opens that copy. To move or back up a talk,
copy the **whole folder**, not only its small project file: the PDF, narration
audio, voice references and recordings belong together.

On first preparation, AutoTalk guides ChatGPT sign-in if necessary. Speech generation
also downloads its local runtime and model automatically. Those downloads are several
GB and require internet access; allow roughly 40 GB free for the Linux setup and
caches, plus your projects. A supported GPU with a working system driver is needed
to generate speech. Already prepared audio can play without loading a speech model.

## Prepared: review before presenting

Example: prepare a five-minute conference talk in German and listen to it before presenting.

1. Open the PDF and choose **Prepared**.
2. Set **Duration** to 5 minutes and **Language** to German in the main window.
3. Optionally configure **Talk settings → Talk & conference** and
   **Voice & language → Voice / Writing & delivery**. Save the Talk settings window.
4. Use **Create talk text** to fill missing narration for all included slides in
   the active language version. Existing wording is preserved. Edit it, then use
   **Create talk audio** to prepare missing/outdated audio without presenting.
   This button becomes available once all included slides have usable text.
5. Optionally create or rewrite individual slide text, edit it, create slide audio
   and listen using the three separate editor controls described below.
6. Save edits with **Save / Ctrl+S**. Edits update memory immediately; there is no
   per-keystroke disk autosave. Preparation, presentation startup and normal closing
   also save the talk.
7. Choose the display and test the audio output. Enable recording if wanted.
8. Choose **Prepare and start**. AutoTalk preserves existing narration, creates
   missing narration, creates missing/current speech and starts fullscreen
   after every included slide is ready. Current saved audio is reused.

There is no text-approval step. **Text ready** counts slides with usable narration;
it does not claim a person reviewed the words. You can edit before presenting,
but editing is optional. To revise a completed talk's duration explicitly, use
**Talk → Fit duration…** (also in Talk settings → Preparation & timing); this opens a confirmation because it can rewrite text.

Fitting aims for your requested duration and allowed tolerance. It does not
guarantee an exact finish time. Live pauses and demonstrations add time beyond the
prepared content. Fit duration changes the script; it is not just a playback-speed adjustment.

## Prepare and preview an individual slide

The same slide editor works in **Prepared** and **Realtime**. Preparing a single
slide does not require text or audio on the other slides.

**Show AI notes / Hide AI notes** reveals Codex’s supporting interpretation notes
for the selected slide. They are read-only and are not spoken. If none were returned,
the disabled button says **No AI notes**; it does not open an empty area.

1. Select a slide. If it has no narration, choose **Create slide text** below the
   editor. Only this slide is written. You can also type the words yourself.
2. Read and edit the text, then choose **Create slide audio**. This uses exactly
   the displayed words, saves the audio and plays it. It does not rewrite text.
3. Use **Play audio / Stop audio** to listen again. There is no audio approval step.
4. If you want another performance, use **Create slide audio** again. To change
   words, edit them or use **Rewrite slide text…**. These commands also appear in
   **Talk → Selected slide**.
   A cancelled or failed regeneration leaves the previous completed recording intact.

Both text and audio buttons remain visible. The text button offers **Rewrite slide
text…** once narration exists, so you can replace the wording at any time. The audio
button is disabled until this slide has usable narration. Its status says
**Audio ready** and explains that the recording is reused when presenting. The
waveform and time display show playback progress, not audio editing or seeking.
**Listen to a sample** in Voice settings remains a separate voice audition; it
uses sample text, not the selected slide's narration.

Editing words, language or effective speech settings makes affected audio need an
update. Other slides remain usable. Switching between Prepared and Realtime does
not invalidate audio. Saved audio and its text survive reopening the talk.

Changing audience, duration or Codex model/reasoning keeps existing narration and
valid audio. Use **Rewrite slide text…** if you want Codex to apply new context to
existing words. **Create slide audio** requests a new performance; **Play audio**
plays the existing file. Start reuses audio only when its words and speech settings
still match. Explicit duration-fitting policies can revise text to meet its length.

In all modes, Start fills missing narration without replacing other slides.
Realtime checks cached opening audio immediately while later preparation continues.

The slide preview plays narration and its prepared pause. It does not mix imported
clips or background music; use a presentation to hear the complete mix. Selecting
another slide ends the preview and leaves the editor ready for that slide.

## Quick: prepare and start automatically

1. Open the PDF and choose **Quick**.
2. Set duration and spoken language in the Quick view.
3. If wanted, enable recording and choose its source/destination before starting.
4. Choose **Start**.
5. AutoTalk writes narration, prepares audio and opens fullscreen automatically.

Quick uses the same resolved voice, language, delivery and model settings as
Prepared and Realtime, including saved slide overrides. Its simplified workspace
still omits the editor and conference setup. Switch to Prepared or Realtime to
edit individual narration; switching mode does not discard voice choices or audio.

**Talk settings → Preparation & timing → Quick timing policy** controls what happens before playback:

| Policy | Behaviour |
| --- | --- |
| **Generate once, then start** | Default. Prepares once and starts even if the measured duration differs from the target. |
| **Fit, then start (up to three revisions)** | Attempts to fit the duration, then starts. It can still finish outside the tolerance. |
| **Require timing match before start** | Attempts fitting, but does not automatically present if the result still misses the tolerance. Review or fit the talk before starting. |

Quick keeps the **Start** caption throughout. Existing narration is preserved;
current saved audio plays without generation. No text approval is required.

## Realtime: start while preparation continues

1. Open the PDF and choose **Realtime**.
2. Set duration and language, then optionally conference, voice and delivery.
3. For a designed voice, listen to a sample and choose **Use this designed voice**
   before starting. For your own voice, supply its reference recording first.
4. Select the presentation display, test sound and configure recording if wanted.
5. Choose **Save**, then **Start**.
6. AutoTalk reuses saved current audio and prepares missing narration/audio.
   Cached opening audio can start while preparation continues in the background.
7. Fullscreen opens automatically once enough audio is buffered. Later slides
   continue preparing while the current slide plays.

The progress bars continue updating during preparation. If playback reaches audio
that is not ready, it displays **Buffering** and waits. It continues once sufficient
audio is available. Remaining time is an estimate while the talk is incomplete.

Realtime options live under **Talk settings → Preparation & timing**. The startup/refill
buffer is under its **Advanced Realtime buffering** disclosure:

| Setting | Choices and effect |
| --- | --- |
| **Realtime narration** | **Plan the deck; write ahead by slide** is the default: plan once, write the opening slide, then write later slides ahead of speech. **Write the complete script first** waits for all text before synthesis. |
| **Realtime speech priority** | **Consistency first** is the default and favours grouped delivery and more buffering. **Earliest playback** favours earlier sound and a shorter opening unit. Neither guarantees identical expression between passages. |
| **Realtime startup/refill buffer** | Minimum prepared audio before starting/refilling, selectable from 2–30 seconds. Selecting Consistency first sets 5 seconds; Earliest playback sets 2 seconds. You can adjust it afterwards. Consistency first may wait for more based on observed generation speed. |

**Pause** and **Esc** pause narration, not background preparation. This can give
later slides time to finish. **Continue** resumes playback at the retained position.
**End presentation** cancels ongoing Realtime preparation as well as ending playback.
**Cancel operation** stops preparation; completed slides remain reusable.

If preparation was interrupted, choose **Start**. It reuses completed text/audio;
an unfinished slide restarts generation from its beginning. **Continue** resumes
paused playback at its retained position.

Once every slide's audio is prepared, later starts can play it directly even if the
mode still says Realtime. Selecting Realtime does not force regeneration each time.

## Conference, audience and objective

Set **Audience** under **Talk settings → Talk & conference**: for example, “Researchers and
software engineers; familiar with Linux, new to speech generation.”

In the same section, set **Talk objective** and supply context in either way:

- **Write it yourself:** enter topics, tracks, technical level and relevant emphasis
  in **Conference scope**. A website URL is not required.
- **Use a website:** enter **Conference website**, then choose **Read conference website**.
  Review the resulting scope and source links. Edit or add your own guidance afterwards.

Reading a website replaces the scope box with its extracted summary. To combine
website context and personal instructions, read the website first, then edit the
result. Supplying a URL alone does not perform the extraction.

Save the settings before returning to narration. Existing text stays usable after
a scope change; use Rewrite slide text to apply new context to those words. Quick ignores conference and audience customisation.

## Voices and voice samples

Open **Voice: …** in the main window (or **Talk → Voice & speech…**).
The **Voice** section has directly selectable **Predefined / My voice / Design / Saved** tabs.
The shared sample controls stay visible while changing delivery or model settings.

### Choose a voice

Select a predefined voice, then **Listen to a sample**. The sample uses the talk's
selected language. **Stop sample** ends playback. No personal recording is required.

Available names are Ryan, Aiden, Vivian, Serena, Uncle_Fu, Dylan, Eric, Ono_Anna and
Sohee. The selector describes their character and native-language strengths. The
voice can speak the other supported languages; listen to assess pronunciation.

### Use my own voice

1. Select **My voice**.
2. Choose **Record my voice**, speak clearly, then stop recording; the recorder
   stops automatically at 30 seconds. Alternatively choose **Import voice recording…**.
3. Use a clean WAV recording between 3 and 60 seconds long.
4. Enter the exact words from that recording in the transcript box.
5. Choose **Listen to a sample** to hear newly generated speech using the reference.
6. Save the talk settings. Optionally choose **Save reusable voice…** and give it a name.

This uses a reference sample, not a separate training session. A transcript is
recommended; without one, the model uses speaker identity without the same
audio-and-transcript conditioning. The current recorder uses the default microphone;
choose that device through the system's audio settings.

### Design a new voice

1. Select **Design**.
2. Describe the voice, such as “a warm, calm adult voice with clear pronunciation”.
3. Optionally select age here and adjust supported attributes under Delivery.
4. Choose **Listen to a sample**.
5. If satisfied, choose **Use this designed voice**. If you change the description
   or effective settings, listen to the new sample before accepting it.
6. Save the talk settings or save the voice for reuse.

Accepting keeps the exact sample you heard as the reference for the talk. It changes
to reference-voice playback, so some direct vocal controls become unavailable.
AutoTalk does not independently design a new speaker for each slide.

### Saved voices

Use **Voice & language → Voice → Saved**. Filter by language and select a row:

- **Listen to selected voice** auditions the candidate without selecting it for the talk.
- **Use selected voice** applies the candidate to the dialog's pending voice choice.

Choose **Save** to keep the choice. Cancel restores the previous
talk voice. Saving a reusable voice is a separate, explicit library action and
is not undone by cancelling the dialog.

Voice samples can require a model download or cold load. Follow progress and use
**Cancel operation** if needed. A sample is not an instantaneous stored sound clip.

## Delivery and speaking style

**Voice & language → Writing & delivery** provides separate **Writing style**
and **Spoken delivery** choices: Professional, Conversational, Energetic, Calm and
understated, Lightly humorous, Academic, Storytelling and Inspirational. Writing
style guides new narration wording; spoken delivery guides audio where supported
by the voice. Changing writing style does not rewrite existing words.

Expand **More vocal attributes** for:

| Control | Available choices/input |
| --- | --- |
| Pitch | Low, Medium, High |
| Texture | Clear, Warm, Breathy, Raspy |
| Energy | Low, Moderate, High |
| Pace | Slow, Moderate, Brisk |
| Articulation | Natural, Precise, Relaxed |
| Projection | Soft, Conversational, Confident |
| Accent | Beijing Mandarin, Sichuan Mandarin; Chinese only |
| Expression | Restrained laughter, Audible sigh, Thoughtful hesitation, Enthusiastic interjection |
| Speaker background / persona | Free text describing the speaker |
| Custom vocal directions | Free text for the talk's delivery |
| Gradual delivery across slides | Free text, such as a calm opening and more energetic conclusion |

Attribute selectors also offer **Model default**. Changing style preserves explicit
attribute choices. **Save preset…** stores a named delivery configuration; select it
under **Saved delivery presets** and choose **Use preset**. Presets do not change
advanced speech sampling. Age (young, middle-aged or older adult) is on the Design tab.

These are instructions to the model, not exact sound controls. Preview important
passages. Age is restricted to voice design; accent presets to Chinese. Reference
voices inherit character and delivery from their reference, so direct vocal
instructions are disabled. Writing style still affects narration. Quick uses the same inherited or overridden settings.

For one deliberate exception, use the selected slide's **Delivery → Use talk delivery** setting (uncheck to override).
Explicit slide directions take precedence over global custom directions, which
take precedence over structured attributes/style. Speech continuity guidance is
provided by default, but it cannot lock expression or speed exactly across passages.
Changed vocal settings require preparing affected audio again.

## Languages and versions

Supported spoken languages are English, German, French, Spanish, Italian,
Portuguese, Russian, Chinese, Japanese and Korean.

Choose the target language in the main **Language** selector. It restores an existing
version of that language, including its text and matching audio. If none exists,
AutoTalk creates an empty version with the same slides and slide settings,
preserving the original narration and audio. Switching back restores the previous version. No separate Add step or
recreation checkbox is needed. All three preparation modes use these versions.

1. Select the desired language.
2. Use **Create talk text** to generate missing narration without presenting, or
   **Create slide text** for one slide. Codex uses the PDF and talk context, not
   narration from another language. Start also generates missing narration.
3. Review the new text, then create audio and listen.

**Talk → Rewrite all talk text…** explicitly replaces the included slides' narration
in the selected version after confirmation, including with Realtime selected.
Stop any active preparation/presentation first. Other versions remain preserved;
Start reuses valid text/audio and prepares only what is missing or outdated.

Until narration exists in the selected language, the editor is empty and the slide
shows **Needs [language] narration**. You can type your own text instead. Existing
narration and matching audio return immediately when you select their language.
An unfinished copied draft saved by an earlier build is also shown as missing when
its authored language differs; those old words are not sent to Codex. Creating audio
requires narration and does not generate or translate its words.

For multiple languages within a slide, choose **Insert language passage…** beside
the narration editor and select a language.
It inserts a marker such as `[German]` into the narration. Type that passage's
words in the intended language. The marker selects pronunciation; it does not translate.

Both **Language → Language options…** and **Talk → Language options…** open
the talk dialog focused on **Language arrangement**. Choose:

- **Separate versions and mixed passages:** allow different languages within a slide.
- **Separate versions; one language per slide:** allow one language on each slide.
- **Separate single-language versions:** all passages must use the version's language.

Text and generated audio are kept by language version. Voice references are stored
by language, with a shared fallback reference for cross-language speech. Voice and
delivery settings are talk-wide, so check their effects when revisiting another version.

Projects now save the language in which narration was authored. Older projects are
backed up before their first save in the new format. If an old project did not store
its inherited narration language, its words remain stored but are not certified as
current narration or sent as translation input. The editor shows missing narration;
create fresh text from the slides.
An older project already mislabelled with the wrong language cannot be detected
reliably from its metadata: select the intended target and use **Talk → Rewrite all
talk text…**. To retain the original, create another version first and run that
rewrite in the new version. Review regenerated text before presenting.

## Slide settings and additional audio

Select the slide before using the right-hand inspector. **Include in presentation**
controls whether it is spoken/presented; at least one slide must remain included.
The PDF itself is not edited or reordered. The inherited after-slide choice names
its app/talk source above the combo. Slide playback controls live only in the
inspector; the slide dialog does not show Playback.

The inspector groups these controls by their purpose:

| Control | Use |
| --- | --- |
| **Timing** | Leave the slide budget at **Automatic**, or set a target in seconds. **Pause after slide** inherits while **Use talk pause (X s)** is checked. Uncheck it to override; 0 means no pause and is distinct from inheritance. |
| **Slide voice & delivery…** | Opens the slide dialog for voice, language, delivery directions and vocal attributes. The caption beneath the button shows voice, source and style. |
| **After this slide: Advance automatically** | Continue to the next included slide after the audio ends. |
| **After this slide: Pause for live demo** | Pause and leave fullscreen for a demonstration. |
| **After this slide: Wait for presenter** | Pause until you continue. |
| **Additional audio…** | Attach recorded audio before/after this slide. Language markers belong beside the text editor. |

At an end-of-slide pause, **Continue** moves on when that slide's audio has finished.
An ordinary mid-slide pause resumes from the paused position.

In **Additional audio…**, choose **Add…** to import an audio clip. Select it
in **Slide audio clips**, set **Play** to before/after and adjust **Volume**
(1 is unchanged; 0 is silent; 2 doubles the gain). **Remove** removes it from the slide.
Use clips for music, singing or effects you want reproduced from an existing recording.

For audio across the presentation, use **Presentation settings → Background audio → Add
background track…**. Adjust **Background volume**, enable **Loop** if wanted, or
choose **Remove background**. Listen to a presentation/export to check the balance.
Imported clips and between-slide pauses count toward duration fitting.

If an edit makes other slides’ audio stale, the status line names up to three slides
and reports any additional count. The last included slide has no trailing pause;
excluding the last slide can therefore make the new last slide’s audio need updating.

## Present, pause, continue and give a live demo

Before starting, open **Application → Display & sound**:

1. Choose **Fullscreen display**.
2. Choose **System audio settings…** to select/reroute AutoTalk's output using the
   operating system. On Plasma, this is the system audio configuration.
3. Choose **Test audio** and confirm the sound comes from the intended speakers.

AutoTalk does not store a separate audio-device choice in each project; routing
belongs to the system. Select the output before beginning screen recording.

| Action | Result |
| --- | --- |
| **Start / Prepare and start** / **F5** | The same preparation-and-start command as the upper-right button. |
| **Presenter → More actions → Start from selected slide** / **Shift+F5** | Begin from the selected slide when presentation is available. |
| **Pause** / fullscreen **Space** | Pause narration; press Space or use Continue to resume. |
| **Previous / Next** / **Ctrl+PgUp / Ctrl+PgDn** | In the Editor, select any slide, including excluded slides. In the Presenter, navigate included slides only. While stopped, navigation only selects a slide and does not prepare or play audio. During playback, navigation retains the existing playback behavior. View-menu actions follow the visible view; they are unavailable on the Quick page or in modal dialogs. |
| Fullscreen **Esc** | Pause and leave fullscreen, preserving the playback position. |
| **Continue presentation** / **F6** | Reopen fullscreen and continue from the retained position. |
| **Pause for a live demo** | Pause narration and leave fullscreen. |
| **Presenter → More actions → Restart from beginning** | Start the presentation again from its beginning. |
| **End presentation** | End the session and return to editing; cancel unfinished Realtime preparation. |

For a live demo, pause/leave fullscreen, show another application, then use Continue.
**Screen + system audio** recording continues throughout; a slides-only video cannot
show the other application.

After the last slide, a finished presentation offers **Return to editing**. Space
does not restart it; use Restart. If screen capture is still running, the action is
**End presentation and save video** instead.

## Record a presentation or export a video

There are three distinct uses:

| Desired result | Choose |
| --- | --- |
| A video of slides and AutoTalk's audio as you present/navigate | Record with **Slide video + narration**. |
| A video including your desktop, live demos and optionally your microphone | Record with **Screen + system audio (Linux)**. |
| A ready-made video/audio file without playing the talk in real time | **File → Export prepared talk…** after preparation. |

### Record while presenting

1. Open **Presentation settings → Recording**.
2. Choose **Recording source**.
3. For screen capture with commentary, enable **Include microphone in screen recording**.
4. Optionally use **Choose video destination…**. Otherwise AutoTalk saves a new
   video in the project's recordings folder. Session suffixes protect previous recordings.
5. Enable **Record presentation as a video** beside Presentation settings in the
   main window before starting. The Recording page reports whether it is enabled.
6. Save the settings and start the presentation.

On Wayland, screen capture opens Plasma's screen-sharing chooser. Choose the display
to capture and approve **Share**. The fullscreen-display choice and the system's
screen-sharing permission are separate. AutoTalk cannot approve sharing for you.
On X11, screen capture uses the primary display.

Screen capture records the system's **default output** audio, including other sounds
played there. Route AutoTalk to that same output so its narration is included.
Choose the default output before starting and keep it consistent during capture. Microphone commentary uses
the default microphone and can pick up speaker sound, so check your setup first.

### Know when recording stops

- **Before Start:** the bottom bar says recording will start with the presentation.
- **During capture:** it shows recording status and elapsed recording time.
- **Slides finished — recording continues:** screen capture is still active.
- **End presentation and save video:** explicitly ends screen capture.
- **Saving video:** allow the save/export operation to finish.
- **Saved:** use the dated output link or open File → Recordings & export.

Slide-video capture finishes automatically after the last slide. Screen capture
continues through pauses, leaving fullscreen, live demos and completion of the last
slide, until you explicitly End. A link to an older saved video is not evidence
that the current recording has finished.

For slide-video capture, **Presentation settings → Recording → Advanced recording → Recording pauses** chooses
whether to retain fullscreen pauses, all elapsed waits, or content only. It does
not apply to screen recording, which records the ongoing session.

### Find or recover the result

Open **File → Recordings & export…**, or use the direct result links after saving.
The table lists talk, date, duration and status. With a talk open it shows that
project's recordings; reopen the relevant saved talk to locate its videos.

- Select a **Ready** row, then **Open video / audio** or **Open folder**.
- Use **Save another format…** for another MP4, WAV or M4A output.
- Select **Needs saving**, then **Save unfinished recording…** to retry saving
  retained recording material.

If you close while recording or saving, AutoTalk offers finishing the save, saving
later, or cancelling the close. Saving later retains the available recording
material; it does not mean the final video is already ready.

### Export without presenting

Use **Create talk text** and **Create talk audio** to prepare all included slides.
Choose **File → Export prepared talk…**, then save as MP4, WAV or M4A. The same
export command is also available in Recordings & export.
This exports prepared slides/narration with clips and background audio. It does not
require live playback, and it does not include a demonstration from another application.

If you presented without recording, you can still export this prepared version.
You cannot recover an unrecorded live demo from the PDF and narration afterwards.

## Manage the speech model and GPU

Open **Settings → Speech engine…**, or click **Speech engine** in the status bar.
The page separates **Current model**, immediate actions, and saved automatic rules.
It also identifies the model selected by the current talk's voice. Choosing a
different voice model does not mean it has already replaced the resident model.

| Immediate action | Effect |
| --- | --- |
| **Load model now** | Load the current talk's selected model in the background. A matching loaded model is reused and the redundant action becomes unavailable. |
| **Load selected model** | Shown when a different model is resident; replace it with the talk's selection. |
| **Unload model now** | Release an idle model's GPU memory without stopping prepared audio or deleting downloaded files. |
| **Cancel operation** during loading | Cancel the load. The selected automatic rules are unchanged. |
| **Check for model updates…** | While idle, check the selected model's upstream revision online. No model load or weight download is needed. |

Unload is unavailable while the model is in use. State distinguishes loading,
ready, generating/in use, unloading and failure. Loading can include first-use
downloads. Having downloaded model files is not the same as having loaded them into GPU memory.

The loading bar names the current stage. Model downloads and verification show
completed files, such as **Checking model files · 7 / 13 files**. Runtime downloads
show transferred MiB and a total when known. During Linux GPU/engine startup,
the bar also displays measurements reported by the backend:

- Checkpoint files read in the **current pass**. Qwen can load several components,
  so a new pass can start again at **0 / 1 files**; this is not another download.
- Loaded speech-weight counts, when reported.
- Memory used by model loading and the time it took.
- Available inference-cache memory and its token capacity.
- GPU initialization/warmup time and completion of each engine stage.

The final stage is **Checking speech service**. The model becomes **Ready** only
when the actual readiness check succeeds. File counters and memory measurements do
not indicate overall startup completion or bytes copied to the GPU. Stages without
a measurement say **Progress not reported**; elapsed time continues separately.
The backend's original output remains available in **Operation details**. This
adapter recognizes the pinned Linux backend; unknown messages remain in the log
without inventing progress.

Model files normally download only once per version. Later loads verify the cache
and load it into GPU memory. Missing or damaged files may be downloaded again;
another voice-model variant can require its own initial download.

**Check for model updates…** is a separate, explicit online check for the model
selected by this talk. It reports whether the latest upstream revision matches
the revision verified by AutoTalk. It does not change the selected model, cached
weights, GPU residency or automatic loading/unloading policies. If a different
revision exists, using it requires an AutoTalk release that includes its verified
model manifest. This button checks availability; it does not install unverified revisions.

**When to load an unloaded model:**

- **When speech is first needed (recommended):** load for preparation or a voice
  sample; prepared playback does not need it.
- **When I start a presentation:** preload at Start in the background. Prepared
  audio starts immediately. Realtime must still wait for its opening audio.

**When to release a loaded model:**

- **Never — keep loaded until I close AutoTalk:** retain it between operations.
- **When the presentation ends:** release at the next actual presentation end;
  pause, fullscreen exit and live demo do not count. Screen recording keeps the
  session open until End.
- **After 5 minutes without speech generation:** release after idle time. Loading
  or using the model restarts the idle period; saving this rule for an already idle
  model starts its countdown.
- **After each preparation or voice preview:** release after speech work finishes.
  A manual preload is not speech generation: it stays ready for the next operation.

Choose **Save** to apply automatic rules. **Cancel** discards draft rule changes;
it does not undo a manual Load/Unload you performed. Current-state text describes
the saved rule, even while you are editing different draft choices.

Manual and automatic loads follow the same unloading rule. Changing a rule does
not itself start loading, or treat an already stopped presentation as a new End.
Manually unloading does not immediately reload the model; it loads at the next
applicable event. Closing AutoTalk releases its model regardless of the selected rule.

Practical examples:

- **Avoid a cold load just before generating speech:** Load now earlier, keep until
  close, then prepare or start Realtime. Text generation and synthesis still take time.
- **Free the GPU after presenting:** choose presentation-end unloading and Save.
  A manually preloaded model follows that same rule.
- **Only play an already prepared talk:** use loading when speech is needed. No
  model load is required for playback or direct export.

## Advanced settings

Technical settings stay with the task they configure. Open the indicated section:

| Control / location | Meaning |
| --- | --- |
| **Talk settings → Preparation & timing → Allowed timing difference** | Tolerance in seconds around the target duration when assessing/fitting a talk. |
| **Application/Talk settings → Presentation & recording → Playback → Pause after slide** | Default prepared gap between slides; contributes to duration. Override for one slide in inspector → Timing. |
| **Language → Language options… → Language arrangement** | Mixed passages, one language per slide, or single-language versions. |
| **Quick timing policy** | Generation/fitting/start behaviour; visible in Quick. |
| **Realtime narration / speech priority / startup-refill buffer** | Text preparation and buffering choices; visible in Realtime. |
| **Recording pauses** | How slide-video capture handles waits; unavailable for screen capture. |
| **Presentation settings → Recording → Output quality → Export audio sample rate** | 24 kHz, 44.1 kHz or 48 kHz. This controls output encoding, not the original voice model's quality. |
| **Presentation settings → Recording → Output quality → MP4 / M4A audio encoding** | AAC 96, 128 or 192 kbit/s. Higher bitrate generally increases file size. |
| **Settings → Account… → Sign in / Sign out** | Sign in is enabled when disconnected; Sign out is enabled when connected. Both are disabled during an operation. Sign-out clears the shared local Codex login and the discovered model list, while preserving saved talk selections. |
| **AI & speech engine → Narration AI — Codex → Model / Reasoning effort** | Choose from the connected account's available text models and that model's effort options. All modes respect the selected scope. |
| **AI & speech engine → Speech model — Qwen → Advanced synthesis** | Exposes Temperature, Top k, Top p, Repetition penalty and Max new tokens for speech generation. |

AutoTalk checks an existing Codex installation for a ChatGPT sign-in at startup,
even before you open a PDF or saved talk. If already signed in, model and reasoning
choices are populated automatically. **Account default** shows the configured model;
**Codex default** shows the configured reasoning effort, or the selected model's
suggested effort when Codex has no explicit effort setting. Saved talk selections
remain unchanged. Quick respects these selections too.

Startup does not install Codex or open a sign-in browser. If Codex is unavailable,
or you are signed out, use **Sign in** to connect. If model discovery fails while
you are signed in, restart AutoTalk to retry; **Sign out** remains available.
An unavailable model saved in a talk remains visible with **refresh availability**
until you refresh or choose another model. Successful connections for narration
also refresh the choices.

The **Model / Reasoning effort** choices control writing, not the local voice.
Voice selection determines which Qwen 1.7B voice model is used. Speech sampling
controls are not a “reasoning effort” or a guaranteed quality setting. The current
Linux acoustic-code generator has separate defaults not exposed by these controls.

Speech is generated at native 24 kHz. Exporting it at 48 kHz does not add missing
voice detail; that rate can preserve higher-frequency content in imported music.

Slide images, extracted text and supplied conference context are sent through the
connected text-generation service. Voice references and local speech generation
remain on the machine. Prepared playback uses saved content.

## Progress, cancellation and recovery

**Text ready** counts included slides with usable narration in the active language version.
**Prepared slides** counts included slides with current audio. During a job the
bars can show the active narration/audio stage. The separate operation bar shows
the current stage and measured counts where available. Codex first shows
**Awaiting response**, then the actual number of response characters received.
Its total is unknown; this is not a percentage or a count of completed slides.
The complete response is validated before AutoTalk uses it. **Operation details**
shows messages and measurements. When a settings dialog is open, operation
progress appears there.

**Cancel operation** stops the current task. Completed slide audio is retained;
the unfinished slide needs generation again. In Realtime, cancellation pauses active
playback. Pause/Continue controls affect playback instead and do not cancel preparation.
Canceling narration retains a healthy loaded speech model according to your retention
policy. Canceling active synthesis terminates its unfinished worker request, so a
later synthesis may need to reload the model.

The upper-right command is **Prepare and start** in Prepared mode and **Start** in
Quick/Realtime. It stays visible and enabled for a loaded talk. If another operation
is running, it requests startup after that operation succeeds. Repeated clicks do
not create duplicate workers. Cancelled or failed operations do not trigger queued
startup. An active voice recording must be stopped before presenting.

Other controls are enabled according to their prerequisites. **Create slide audio**
requires narration; **Play audio** requires an existing file. **Buffering** means
speech generation is catching up; **Needs saving** means an unfinished recording
can be saved from the recordings dialog. Dialog-opening buttons/menu entries have
an ellipsis; direct commands such as Start and Create slide audio do not.

If setup or generation fails, read **Operation details** or **View → Operation details**.
For a missing voice reference, import/record the reference again. For an audio-output
error, check system routing and Test audio. If another AutoTalk instance owns the
speech GPU, unload/close that instance before attempting another model load.

## Menu and keyboard reference

| Menu | Contents |
| --- | --- |
| **File** | Open PDF, Open saved talk, Reload PDF, Open recent, Save, Save a copy, Open talk folder, Recordings & export, Export prepared talk, Quit. |
| **Edit** | Undo/Redo, Cut/Copy/Paste/Select all, Find in slide text. Find searches the current narration, not the whole deck. |
| **View** | Editor/Presenter, navigator/inspector visibility, restore layout, enlarge slide, Operation details. |
| **Talk** | Talk settings, Voice & speech, Create talk text/audio, Rewrite all talk text, Fit duration, Language options, Selected slide and Mode submenus. |
| **Presentation** | Start / Prepare and start, Continue, Pause, start selected, Restart, live demo, Previous/Next, End, Presentation settings, System audio settings. |
| **Settings** | Application settings, Account, Speech engine, immediate model Load/Unload. |
| **Help** | Getting started, Keyboard shortcuts, About AutoTalk. |

| Shortcut | Action |
| --- | --- |
| **Ctrl+N / Ctrl+O** | Open PDF / open saved talk |
| **Ctrl+S / Ctrl+Shift+S** | Save / save a copy |
| **Ctrl+T / Ctrl+,** | Talk settings / Application settings |
| **Ctrl+F** | Find in current talk-text editor |
| **Ctrl+Z / Ctrl+Shift+Z** | Undo / redo in the focused text editor |
| **Ctrl+X / Ctrl+C / Ctrl+V / Ctrl+A** | Cut / copy / paste / select all in the focused editor |
| **F5 / Shift+F5** | Start or prepare and start / start selected slide when ready |
| **F6** | Continue presentation |
| **Ctrl+PgUp / Ctrl+PgDn** | Previous / next slide in the visible Editor or Presenter |
| **Space** in fullscreen | Pause / continue |
| **Right or Page Down / Left or Page Up** in fullscreen | Next / previous slide |
| **Esc** in fullscreen | Pause and return to controls |
| **Ctrl+Q** | Quit |

Menu actions follow the same availability as their corresponding buttons. F5 invokes
the highlighted start command, including missing preparation; it is not a separate workflow.

## Common questions

**I changed a sentence. What happens to the recording?**
The existing file remains playable with **Play audio**. It is marked as needing an
update and will not be reused for the edited narration during presentation.
**Create slide audio** generates new speech immediately; Start generates it as
part of preparation.

**Can I hear just this slide before starting the presentation?**
Yes. Select it, use **Create slide text** if needed, then **Create slide audio**.
The result is saved and previewed. **Play audio / Stop audio** auditions it again.

**Does Quick use my voice and conference settings?**
Quick uses the same selected or inherited voice, delivery and model settings as
the other modes. It skips conference and audience customisation; use Prepared or
Realtime when that context matters.

**Why does Realtime still take time to start?**
Initial downloads, model loading, opening text and enough audio must be ready first.
Preloading can move model loading earlier; it cannot remove narration/synthesis work.

**Why is the talk longer than my requested duration?**
Duration is a target. Check measured audio, use Fit duration if appropriate, and
account separately for time you spend paused or demonstrating something live.

**Can I resume after leaving fullscreen?**
Yes: Continue presentation or F6. Do not use Restart if you want to retain position.

**The last slide ended. Where is the screen recording?**
Screen recording continues until End presentation and save video. Wait for saving,
then open File → Recordings & export and select the completed output.

**Can I create a video if I forgot to record?**
Yes, from the prepared slides and audio through direct export. An unrecorded live
demo or microphone commentary cannot be reconstructed this way.

**Why did my newly loaded model stay loaded with “after each preparation” selected?**
Load now prepares the model for use; it is not a speech-generation operation. The
model unloads after the next preparation/voice preview finishes, or when you Unload now.

**Where are the current test results and remaining limitations?**
See [VERIFICATION.md](VERIFICATION.md). This guide describes implemented controls;
it does not imply every platform or voice has received the same testing.

### Recording and status readouts

The main recording checkbox keeps the label **Record presentation as a video**.
A separate indicator appears only while waiting for screen sharing, recording
(with elapsed time), or saving video. Saved-output links remain available beside
it. The header shows audio readiness/duration; target duration and language stay
in their own controls. Quick's explanation shows the included slide count without
repeating the title or voice. The status bar contains transient saved/operation
messages and the Speech engine button, without permanent filler text.

Background track Add/Remove, volume and loop share the talk's **Background audio**
section. Application defaults show volume and loop only. **Settings → Account…**
focuses the account controls; Codex model/reasoning support application defaults
and talk overrides. The Codex page displays connection state without suggesting
that its readout is a sign-in control.
