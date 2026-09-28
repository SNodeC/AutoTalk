# Native Wayland verification — blocked by a portal crash

Subsequent [core-dump analysis](2026-09-28-wayland-crash-analysis.md) resolves the
crash to deferred deletion of a live QML selection delegate during nested
virtual-display startup. The initial observations below retain their context.

The owner deferred startup optimization and requested a supervised Wayland
recording test. Source snapshot: `994a858`. No production code was changed.

## Attempt and observed failure

On 28 September at 12:54 CEST, the real Plasma/Wayland desktop ran the existing
recording acceptance journey with native Qt 6.10.2/Breeze. A disposable PipeWire
virtual output isolated the test tones from physical audio. Test-only monitor
selection redirected capture to that output; physical mute, volume and default
output settings were not changed. Test settings and the synthetic talk were
isolated from the user's projects and preferences.

The Start button requested screen sharing. Before capture became ready,
`plasma-xdg-desktop-portal-kde.service` aborted. The service journal records:

```text
Object ... destroyed while one of its QML signal handlers is in progress.
qrc:/qt/qml/org/kde/xdgdesktopportal/PipeWireLayout.qml:79: function() { [native code] }
Main process exited, code=dumped, status=6/ABRT
A backend call failed: Message recipient disconnected from message bus without replying
```

The system automatically restarted the portal service. Neither the test nor
AutoTalk restarted it. Installed versions were xdg-desktop-portal-kde 6.7.4-1,
xdg-desktop-portal 1.22.1+ds-1, KWin 6.7.4-2, and Qt 6.10.2.

The matching KDE source identifies line 79 as the display-card click handler,
which accepts a single-selection request. The log establishes a crash in that
path, not the precise ownership defect or a validated repair. It must not be
described as the user failing to grant permission. See the
[matching KDE source](https://github.com/KDE/xdg-desktop-portal-kde/blob/v6.7.4/src/PipeWireLayout.qml).

## Error propagation is also incomplete

AutoTalk remained in its waiting-for-sharing state and its error callback
received no error. The bundled Qt source explains this: a nonzero portal response
sets the operation to idle and logs a warning, but does not call `updateError`.
AutoTalk already connects `QScreenCapture.errorOccurred` to its recording failure
handler. A message printed by Qt is therefore not equivalent to an application
error notification. The same branch is present in the inspected
[Qt development source](https://github.com/qt/qtmultimedia/blob/dev/src/multimedia/pipewire/qpipewire_screencapturehelper.cpp).

**Required invariant:** a denied or failed sharing request must terminate pending
capture through the capture backend's error interface. The user must be able to
end the attempt and retry. Logging alone does not satisfy that contract.

Any correction belongs at that existing backend boundary. A second portal client,
log parser or arbitrary UI timeout would duplicate responsibility or hide the
failure. No such workaround has been introduced. Fixing error propagation alone
would not repair Plasma's crash or prove successful recording.

## Acceptance status and next steps

Wayland recording remains **unverified**. This attempt did not establish a ready
stream, so live-demo footage, post-slide footage and saved-video completeness
could not be checked. Earlier X11 acceptance remains valid for X11 only.
The probe reached its 240-second readiness timeout, recorded the failed result
and closed. Its runner removed the disposable virtual output. The runner's zero
exit status indicates completed cleanup, not acceptance success; `result.json`
contains the timeout and an empty application-error list.

1. Diagnose and resolve the KDE portal crash; verify a repair before changing
   the user's installed desktop components.
2. Correct and test failed/cancelled portal response propagation in the bundled
   Qt backend, including state recovery and retry.
3. Repeat the native Wayland journey with the user's sharing permission and
   inspect the exported video and its duration/audio measurements.

Raw local evidence and the isolated test scripts are in ignored
`artifacts/wayland-acceptance/`, including `portal-journal.log`, `wayland.log`,
the matching KDE source files and the bundled Qt response-handler excerpt.
Production additions/deletions: **0/0**. Automated regression-test changes:
**0/0**; this was an acceptance attempt and investigation, not an implementation.
