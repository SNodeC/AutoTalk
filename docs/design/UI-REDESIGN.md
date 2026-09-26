# AutoTalk desktop redesign — approved visual reference

The interactive prototype (`interactive-prototype.html`) is the visual authority.
The subsequent Qt/Breeze mockups are structural studies, not the visual target.
The prototype contains simulated states and data; it is not application code.

## Visual analysis

The accepted interface has compact application chrome, a conventional menu bar,
small labeled toolbar buttons, a project summary strip, and a three-column editor.
The slide navigator is narrow; the central PDF preview and narration editor are
on a white/base surface; the right inspector and surrounding chrome use the
window surface. Thin borders divide the areas. It avoids large marketing headings,
centered group-box captions, and entire-page stacks of configuration controls.

Reference geometry at 1024 px content width:

- Menu buttons: 3 px vertical / 9 px horizontal padding; no permanent button boxes.
- Toolbar: 9 px vertical / 12 px horizontal margins, 6 px gaps, 32 px controls.
- Editor: 154 px slide navigator, flexible center, 226 px inspector.
- Center: 15 px padding; original slide aspect ratio retained, narration below.
- Surfaces: 1 px borders, mostly square geometry, 3 px control corner radii.
- Text: approximately 13 px body, 12 px secondary, 17 px dialog section heading.
- Dialogs: approximately 760 px wide, 158 px section list, 21 / 23 px content
  margins; a separate bottom action row. Fields fill the available width.
- Main action: solid blue with contrasting text. Selection is a pale blue surface
  with a thin blue outline. Checkboxes are explicit and labels are clickable.

Native Breeze alone differs: control insets, primary-button emphasis, group-box
captions, navigation selection, default form spacing, text wrapping and widget
sizing do not match this design. The implementation needs deliberate Qt layout
metrics and narrowly scoped palette-aware widget styling. System theme changes,
fonts and native OS dialogs remain supported. The light prototype is the primary
comparison target; dark mode uses the system palette, not hard-coded light colors.

## Existing ownership and behavior

`Project` owns talk configuration, language versions, per-slide narration,
voice/reference selection, delivery, recording preferences and artifact validity.
`SettingsPanel` binds its controls to that project. `MainWindow` applies authoring
edits, accepts worker results and saves the project. Existing service jobs work on
snapshots and publish validated results. `Playback` owns the selected slide,
position, timing and internal recording; `Presentation` is its fullscreen view.
`SpeechSession` owns the managed speech process. `QSettings` owns remembered defaults.

The governing invariant is one authoritative project and one playback position.
Rearranging the interface must preserve all existing invalidation, review,
language-version, cancellation, recording recovery and resume behavior. Widgets
and menu actions must derive availability from the same active job/playback state.
Settings dialogs must have honest save/cancel semantics; opening a dialog cannot
silently reset the project or change the active language version.

## Narrow implementation

Replace the current Setup / Script / Present & Export layout. Do not retain a
second legacy workspace or embed a browser with a second application state model.
Keep PySide6, existing controller methods, workers, persistence and audio services.

1. Replace the construction methods in `app.py` with the prototype's menu bar,
   toolbar, project summary, editor/inspector, progress footer and presenter view.
   Remove the old layout and its tab-index-based enablement/navigation policy.
2. Reorganize the existing settings bindings into General, Conference, Voice,
   Delivery and Presentation/Recording dialog sections. Reuse existing controls;
   separate global defaults from current-talk values explicitly.
3. Expose application speech retention under Preferences; current-talk Codex
   model/reasoning and sampling live under Talk settings → Advanced.
   Keep actual backend capabilities: the current generator sampling control must
   not pretend to configure the acoustic generator. New synthesis behavior is a
   separate functional change, not part of appearance matching.
4. Reuse voice import/record/preview/library handlers and the existing exporter.
   Preserve the recorded-file destination and recovery actions. The continuation
   integrates the separately scoped Linux screen/audio capture through the same
   recording sessions and exporter.
5. Keep Quick deliberately small and use the same project-bound input controls.
   Display actual Realtime preparation and buffer state. Returning from fullscreen
   exposes Continue without creating a second transport or resetting its position.
6. Use compact reusable layout primitives and a scoped Qt appearance definition.
   Avoid a theme manager, UI-specific project copy kept permanently in sync, a
   browser bridge, or a second settings/command service.

Replacing the old UI is necessary but is not sufficient to cover the additional
menu commands, section dialogs, genuine dialog acceptance/cancellation, dedicated
Quick/presenter states and visual metrics. Estimated net production growth is
**350–500 lines**, including the scoped appearance rules, after deleting the old
construction and navigation code. This is UI code only. It does not include
screen capture, new sampling policies, runtime changes or new persistence formats.
The user approved implementation after reviewing this estimate. The preceding checkpoint is commit `7bb41a3`. The continued implementation also
covers the previously scoped Linux screen/audio recording work. Production and
test accounting for the final combined diff is in `../VERIFICATION.md`.

## Verification and acceptance

Record the Linux test baseline and cold/warm window startup before replacement.
Use the same fixture PDF and application size for before/after screenshots.
Compare the implementation directly with the clickable prototype, not with the
structural Qt sketches: main editor, all opened menus, all talk settings sections,
Preferences, Quick, Realtime progress, presenter and Continue states.

Tests must preserve the behavior of the removed layout, not its obsolete tab
names or indices. Exercise shared action availability while editing, preparing,
playing and paused; persisted settings and cancellation; language preservation;
manual narration review; saved recording discovery; and native PDF navigation.
Check minimum-size layout, normal/enlarged scaling and live light/dark changes.
Rebuild the actual Linux package and inspect it because the checkout launcher
prefers the bundle. Report production/test changes separately and identify any
prototype features that remain functionally unavailable. Linux-only local testing;
Windows/macOS support is retained.

Baseline recorded on 2026-09-26: **101 Linux tests passed in 25.52 s**. The
regression suite used Qt's offscreen platform; the visual baseline separately used
Plasma/Wayland and confirmed the actual `breeze` style at 1024 × 850. Five
consecutive native source launches measured a median **0.595 s** and mean
**0.598 s**, from import to the first visible-window event. These are cached
application launches, not cold speech-runtime/model startup. Screenshots and logs
are under ignored `artifacts/ui-redesign/`; the startup samples are also retained
in `artifacts/platform-style/startup-redesign-before.json`.

## Implemented desktop UI

The editor now has the menu bar, compact toolbar and summary strip, actual PDF
thumbnails, PDF/narration center, and a scrollable slide inspector. Talk settings
contains General, Conference, Voice/library, Delivery, Recording and Advanced. Preferences
contains system appearance information and application speech retention. Quick exposes the same
duration/language fields directly; opening General moves those controls into the
dialog. Recording likewise uses one checkbox in the footer or Recording section.
Presenter view displays current/next slides, narration, timing and continuation.
Export / recordings uses the existing encoder and recoverable sessions.

Dialog edits use existing bindings plus a temporary rollback snapshot. Cancel
restores the manifest, controls and selected slide even after a handler saved
changes; explicitly saved reusable library assets are retained. Dialog closure is
blocked during a worker operation or reference recording, with a visible Stop /
Cancel operation control. Main-window buttons and menu actions share availability
computed by the controller. Additive fields persist per-slide policy and recording source; the existing project
format remains readable and there is still one transport and recording owner.

The continuation adds the dedicated voice-library table, real waveform, per-slide
regeneration, inclusion, timing and after-slide actions. Export lists saved and
unfinished sessions. Screen/demo capture now has an implemented Linux backend;
its qualification boundaries are recorded in VERIFICATION.md. Existing main-
generator sampling is honestly labelled; the separate acoustic-sampling evaluation
has not been silently promoted to a completed feature.

The application matches the prototype's desktop hierarchy, layout and spacing;
actual PDF aspect ratio, real data, system palette/fonts and native controls
remain authoritative. Prototype sample content, speculative engine options and
simulated setup/audio/portal windows are not substituted for operating-system
behavior. Existing language, audio-clip and advanced runtime controls remain
accessible through the relevant dialogs.

The final Linux evidence is in `../VERIFICATION.md`, with screenshots and logs in
ignored `artifacts/ui-redesign/`. These include all menus and dialogs, Quick,
presenter, minimum-size light/dark and enlarged-scale views. The final package is
rebuilt so the checkout launcher runs the refinement.
