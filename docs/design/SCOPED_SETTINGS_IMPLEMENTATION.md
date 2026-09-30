# Scoped settings: schema, drafts and Preferences

The October 1 refinement supersedes the September 27 combined application dialog.
See [verification and accounting](../reviews/2026-10-01-settings-refactor.md).

## Invariant

Project resolves slide override → talk setting → application default → built-in.
Resolution, schema v5, SETTING_DEFAULTS, language versions and audio fingerprints
are unchanged. MainWindow owns the live project. A scoped dialog owns a draft,
never the live project. Preferences owns computer controls, not talk defaults.

## Ownership

| Scope | Settings | Editor location |
| --- | --- | --- |
| Application → talk → slide | Voice identity and references | Voice & language in each fixed-scope dialog |
| Application → talk → slide | Language | Talk defaults; main Language combo; Slide sound → Voice & language |
| Application → talk → slide | Writing style, delivery instructions/attributes | Writing & delivery in each fixed-scope dialog |
| Application → talk → slide | After-slide action and pause | Defaults/talk Timing & playback; slide inspector only |
| Application → talk | Mode | Talk defaults Timing & playback; main Mode combo |
| Application → talk | Recording intent | Talk defaults Audio & recording; main checkbox |
| Application → talk | Language arrangement | Defaults/talk Voice & language |
| Application → talk | Quick/Realtime/timing policies | Defaults/talk Timing & playback |
| Application → talk | Codex model/effort; synthesis sampling | Defaults/talk AI model |
| Application → talk | Recording/output settings; background gain/loop | Defaults/talk Audio & recording |
| Talk | Duration | Main Duration spin only |
| Talk | Title/audience/objective/conference/sources; pin inherited settings | Talk settings → Talk |
| Talk | Background file and recording destination | Talk settings → Audio & recording |
| Slide | Inclusion/budget | Slide flow inspector |
| Slide | Audio clips, gain and placement | Slide sound → Audio & recording |
| Computer | Display, system sound, account, engine and lifecycle policy | Preferences, immediate; Close only |
| Shared library | Reusable voices and delivery presets | Relevant component's explicit library actions, immediate |

Talk mode, language and recording rows are read-only with Reset. Every inheritable
row has a constant source caption (set here/from talk/from app/built-in) and Reset;
explicit zero, false, empty, and equal-to-parent values remain overrides.

## Implementation

`settings_schema.py` is the presentation metadata authority for keys, kinds,
choices, scope, page, section and order. Values/scopes originate in Project's
SETTING_DEFAULTS and SETTING_CHOICES. The explicitly listed custom owners handle
voice, sampling, delivery presets and assets. `SettingField` builds and loads the
same editor/source/Reset row in dialogs and the inspector. Widgets are placed once.

`ScopedSettingsDialog` has thin TalkDefaults/Talk/Slide configurations. It composes
VoiceEditor, AudioAssets, CodexModelPicker, ConferencePanel and DeliveryPresets.
The narrow controller API is documented in module docstrings and checked by AST.
PreferencesDialog owns device, account and engine widgets. MainWindow owns actions,
the speech session and persistence; no compatibility widget aliases remain.

Opening copies the project (or defaults) and records its generation. Edits use
`apply_edit`, shared by draft editing and Save replay, and append immutable operations.
Save checks the generation, replays once through Project mutators inside the
existing configuration change boundary, updates audio/UI once, compares stale
slides, and writes once. Defaults write QSettings; talk/slide write the manifest.
Cancel writes nothing, preserves pre-existing main-window modifications, cancels
owned operations and deletes only session-created unreferenced media.

Conference/import workers receive the draft and never save. Late cancelled results
cannot edit a reopened draft. Save is unavailable during project-returning jobs;
Cancel remains available. Shared-library actions do not save the project.
Preferences account/model jobs do not save pending document settings.

Draft edits never call MainWindow.edit_setting, configuration_changed or refresh.
MainWindow no longer reloads drafts after live edits. Local timing is measured on
the draft when its page is shown/edited. Engine status and account availability are
read-only external state; they do not replace draft model selections.
