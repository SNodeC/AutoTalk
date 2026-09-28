# F17: readable language-arrangement selections

The owner accepted the third Claude verdict as authoritative while keeping startup
optimization deferred. F17 is its new actionable application defect; F16 was
retracted, and the original F6 sequence remains uncharacterized rather than a
new reproduced failure requiring speculative changes.

## Invariant and implementation

Every language-arrangement choice must fit the closed native selector at the
supported settings-dialog size, including beside its inheritance control.
The dialog must not grow beyond the requested size or require horizontal scrolling.

The setting is owned by `Project.setting()` / application defaults, bound once by
`SettingsPanel`, then moved into the shared Voice & language form for each scope.
Talk overrides wrap the selector with an inheritance button. A fixed ten-character
minimum in `SettingsPanel.combo()` suppressed Qt's content-based size hint, while
the form's default side-by-side layout compressed the remaining field. Persistence,
inheritance and selection values were correct; layout was the faulty boundary.

The correction removes the two fixed-minimum sizing statements from the existing
settings combo factory. Existing form builders use Qt's `WrapLongRows` policy,
including forms receiving the moved language selector. Native Qt now determines
the content width and moves a field below its label when a row cannot fit. At
normal width the row stays side by side. The minimum window/dialog sizes remain
unchanged. A narrow dialog uses more vertical space within its existing scroll
area; the control can be reached by ordinary scrolling or keyboard focus.

This is the content-aware sizing remedy from Claude's verdict, with the existing
form respecting that size. There is no custom painting, fixed pixel width,
theme-specific branch, eliding renderer or additional state. Both application
defaults and talk settings share it. Slide settings retain their existing scope
rules; language arrangement is not a slide override.

## Verification

The new regression exercises all three choices through actual Qt keyboard input
in app/talk scopes at 760×580 and 920×760. It measures the native edit field,
checks the effective selected value, verifies the entire control is reachable,
and rejects horizontal scrolling or implicit dialog enlargement.

Before the production fix, the native regression failed in the minimum-size talk
dialog: **236 px text versus 234 px field**. The other three scope/size cases
passed. After the fix all four cases pass. A dedicated visual journey selects
the longest choice: **255 px text**, with **388 px talk field** / **321 px app
field**, zero horizontal scroll at 760×580 in the measured light/Breeze run.

- Full native Qt 6.10.2/Breeze suite: **376 passed in 97.67 seconds**.
- Full standard Qt 6.11.2 suite: **376 passed in 78.41 seconds**.
- Breeze light/dark at 100%/150%: **12 interaction checks per combination passed**,
  covering minimum/normal layout, the new selector regression and all-scope/menu
  pointer navigation. Dedicated selector/popup journeys also pass in each.
- Native screenshots were visually inspected: the longest language choice is
  fully readable, inheritance controls remain adjacent, and the normal-width
  form keeps its side-by-side layout.
- Rebuilt bundle audit: **27 matching Qt/plugin hashes**, **18 Qt libraries
  mapped from within the bundle**, Breeze loaded, smoke exit 0. The native
  Multimedia library remains byte-identical to the verified Wayland fix:
  `5537cedf957b657d492adf7371147c05446acc78021a116ba9b43fd33b05659f`.
- Direct packaged XTest input: opened Talk settings, chose Voice & language,
  selected the longest arrangement via the native dropdown, clicked Save, loaded
  the saved manifest and confirmed `language_policy == "slide"`; SIGINT exit 0.
  The selected-label screenshot was visually inspected.

Selected synthetic evidence:

- [Minimum-size talk setting, light](evidence/2026-09-28-f17-fix/light.png).
- [Minimum-size talk setting, dark](evidence/2026-09-28-f17-fix/dark.png).
- [Minimum-size talk setting, 150%](evidence/2026-09-28-f17-fix/light-150.png).
- [Minimum-size application defaults, dark 150%](evidence/2026-09-28-f17-fix/app-dark-150.png).
- [Normal-size form stays inline](evidence/2026-09-28-f17-fix/normal.png).
- [Actual packaged application selection](evidence/2026-09-28-f17-fix/packaged.png).

Diagnostic artifacts are under ignored `artifacts/f17-fix/`. Early layout probes
confirmed changing content size after the widget had already been laid out was
insufficient; the accepted change works at widget/form construction. An initial
packaged XTest harness used an OR-style window search and operated on the wrong
window; that attempt is not a pass. The corrected harness requires both process
ID and dialog title (`xdotool search --all`). It also waits for the loaded talk's
title before input. A later attempt scrolled over the language combo instead of
the page, then clicked the wrong coordinates; it did not verify the target action.
The final pass uses the observed selector position without that wheel step. All
diagnostic failures and screenshots remain local; only the final pass is counted.

## Scope and accounting

Production: **2 added, 2 removed, net zero** across existing sizing/form helpers.
Tests: **27 added, zero removed**; four parametrized regression cases.
No startup, synthesis, model-retention, recording or audio-routing logic changed.
No physical speaker/microphone settings changed. Linux only was tested; platform
support and deferred QEMU work remain as previously agreed.

The 15–20-second startup target remains open and explicitly deferred. Existing
Wayland acceptance is preserved; no new real-portal prompt was needed for this
settings-only change. The KDE virtual-screen crash remains separate and open.
