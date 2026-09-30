# Chinese-to-German restart: coordinator reproduction

29 September 2026; source `c5f45d6136675eb66edbb7cf5e52ce1fb64eb225`.
No production files or user talks were modified.

## User report and saved-state observation

The owner reported that a talk started in Chinese still speaks Chinese after
changing to German and restarting. They believe the setting was changed in Talk
settings and requested investigation of every language-change route. They also
authorized read-only inspection of the running application.

The running executable was the local packaged AutoTalk build. The most recently
opened project, identified from application preferences, had one version named
German with language German, Realtime mode and mixed-language policy. At the
inspection instant it had 24 included slides, nine text-ready and six audio-ready.
The opening slides contained Chinese narration without explicit language markers.
Their audio paths were under `audio/main/German`, and `Project.ready()` accepted
these artifacts. Private narration and talk paths are deliberately omitted here.

This is saved-state evidence. AT-SPI did not expose the running application;
unsaved in-memory widget values were not observed. No playback was initiated,
stopped, or listened to, and physical speaker/microphone settings were untouched.

## Controlled reproduction

An independent coordinator probe under ignored
`artifacts/language-restart/reproduce.py` used synthetic two-slide projects,
Chinese narration, silent synthetic WAVs, isolated QSettings, real Qt controls
and the existing deterministic speech fixture. It selected German through Talk
settings, accepted Save, and clicked the real Start button. Fullscreen/audio
playback was substituted at the final presentation boundary to avoid physical
output. Codex was replaced with a deterministic German response and call counter.

Command:

```sh
PYTHONPATH=src QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/python -m pytest -q -s artifacts/language-restart/reproduce.py
```

| Initial passages | Modes tested | Text ready after language change | Audio ready after change | Codex calls on Start | Result |
| --- | --- | --- | --- | --- | --- |
| Untagged Chinese words | Prepared, Quick, Realtime | 2/2 | 0/2 | 0 | Chinese text retained; speech regenerated with German language metadata; project becomes prepared |
| Explicit `[Chinese]` marker | Prepared, Quick, Realtime | 2/2 | 2/2 | 0 | Existing Chinese audio reused; project remains prepared |

All six cases reached the simulated presentation boundary and failed the probe
assertion that text readiness becomes zero. Result: **6 failed in 2.53 seconds**.
This is not a passing regression test. The untagged cases reproduce the reported
defect. The tagged cases require a narrower interpretation: an explicit Chinese
passage may be a deliberate mixed-language override and must not automatically
be erased or translated merely because the talk default changes. The probe
blanket assertion is too broad for that intentional-override case; those results
are observations for the review, not six independently established defects. Full log:
`artifacts/language-restart/reproduction.log`.

## Established cause and boundary

`Project.set_setting('language', ...)` changes the active version's language/name
without creating/selecting a version or marking existing words for translation.
`Slide.text_ready` still accepts those passages, so `services.workflow` finds no
missing text and skips Codex. For untagged passages the effective speech language
changes and invalidates the WAV identity, but synthesis still receives Chinese
words. Explicit passage languages can keep even the WAV identity unchanged.

The existing Talk settings tooltip and user guide expressly say that language
changes keep existing words. That documented behavior is inconsistent with the
owner's stated expectation for changing a talk's target language. An audio-only
cache reset would not correct the cause. The existing language-version and
translation mechanisms must be considered before introducing more validity state.

The owner subsequently requested an independent deep Claude review of all
language, voice, speaker and related setting-change semantics. Implementation
is held pending that broader review and the smallest coherent remedy. This
probe does not establish behavior of application-default changes, slide-level
changes, every mixed-language policy, or every voice source; those are explicit
review requirements, not silently claimed as tested here.
