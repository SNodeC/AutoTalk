# Plasma sharing crash: core-dump analysis

Follow-up to the [Wayland acceptance attempt](2026-09-28-wayland-verification.md).
This investigation examined the saved crash without launching another sharing
request, changing installed packages, restarting services, or changing audio.

## Conclusion

The KDE portal aborted because it deleted a display-selection delegate while
that delegate's QML click handler was still executing. The handler synchronously
entered stream creation, which ran a nested event loop. That loop dispatched a
deferred deletion of the delegate. Qt detected the invalid lifetime and called
its fatal-error path, resulting in SIGABRT.

The selected path was **creation of a virtual display**, not capture of an
existing physical display. This is established by the resolved core, not inferred
from the generic portal error. It is unrelated to the disposable virtual *audio*
output used by the test.

## Evidence and method

The core is for PID 2631926, the system `xdg-desktop-portal-kde` process, at
12:54:25 CEST on 28 September 2026. Debian debug information was downloaded to
the local cache and used with offline GDB; no package was installed. Executable
build ID: `3a9e8593638b3b05bdb79c0086a5e7ca14310f19`.

Resolved frames establish the following chain (source line numbers are from the
installed Debian binaries' debug information):

| Stage | Evidence |
| --- | --- |
| A display card handles a mouse release | QQuickAbstractButtonPrivate::handleRelease; QML location PipeWireLayout.qml:79 |
| The single-selection card accepts the dialog | PipeWireLayout's selectAndAccept calls the dialog button box's accepted signal |
| Acceptance runs stream startup synchronously | QuickDialog::finished → delayReply callback, dbushelpers.h:91 → continueStartAfterDialog, screencast.cpp:234 |
| The selected source is a virtual output | startStreamingVirtual → startStreamingVirtualOutput, waylandintegration.cpp:91/240 |
| Startup enters an inner event loop | startStreaming, waylandintegration.cpp:267 → QEventLoop::exec |
| The inner loop delivers queued deletion | QCoreApplicationPrivate::sendPostedEvents → QObject::event; actual event is QDeferredDeleteEvent, type 52 |
| The deleted object is a selection delegate | QQuickItemDelegate destructor, object 0x55da093d8ba0 |
| Its click handler is still active | QQmlData::destroyed reports PipeWireLayout.qml:79, then QMessageLogger::fatal → qAbort |

The selectedOutputs list contains one entry: `Output::Virtual`, with display
label `Share virtual screen`, unique ID `Virtual`, and no physical QScreen.
The core's virtual-output arguments include a 1920×1080 size and
`Virtual Output (shared with Konsole)`. These are the portal's recorded arguments;
the terminal label alone is not evidence that another application caused the
crash. AutoTalk's failed request coincides with the portal failure and loss of
the D-Bus response.

Qt's fatal check explicitly protects against resuming a QML handler after its
object has been destroyed. This was an intentional abort on a detected lifetime
violation, not an unexplained segmentation fault. See the
[Qt implementation](https://github.com/qt/qtdeclarative/blob/v6.10.2/src/qml/qml/qqmlengine.cpp).

## Likely trigger for deletion: changing the output list

At 12:54:25.485–.503, many unrelated desktop applications and the portal reported
that no Wayland outputs were available and that they were creating a placeholder
screen. This establishes a desktop-wide output transition, not merely an
AutoTalk window change.

The matching portal source provides two relevant mechanisms:

- OutputsModel removes rows when a screen disappears.
- On output-order changes it resets the entire model. The selection cards are
  delegates of that model, through GeometryFilterModel and PipeWireLayout.

Sources: [OutputsModel](https://github.com/KDE/xdg-desktop-portal-kde/blob/v6.7.4/src/outputsmodel.cpp),
[PipeWireLayout](https://github.com/KDE/xdg-desktop-portal-kde/blob/v6.7.4/src/PipeWireLayout.qml),
[stream startup](https://github.com/KDE/xdg-desktop-portal-kde/blob/v6.7.4/src/waylandintegration.cpp).

The strongest explanation is that creating the virtual display caused an output
update, invalidating a selection delegate while its click handler was suspended
inside the inner event loop. **The exact function that originally scheduled the
deletion is not preserved in the core.** Deferred deletion separates scheduling
from destruction. The core proves the destruction, event type and still-active
handler, but does not prove whether a model reset, row/filter change or another
UI invalidation scheduled that particular deletion. Likewise, the journal alone
does not establish why the compositor temporarily exposed no outputs.

## Why AutoTalk continued waiting

This is a separate failure at the Qt Multimedia boundary. The KDE portal crash
breaks the D-Bus request; the frontend reports that its backend disconnected.
Qt's nonzero portal-response handler logs a warning and resets its operation,
but does not notify QScreenCapture.errorOccurred. AutoTalk already listens to
that signal, so its error handler receives nothing and capture never becomes
ready. The acceptance probe eventually reports its own 240-second timeout.

A successful error notification would restore a usable failure path; it would
not fix the KDE crash or create a valid recording.

## Correct repair boundary and remaining verification

The governing invariant is that a selection delegate must outlive execution of
its own handler. Starting a nested UI event loop from that handler breaks this
invariant when the underlying display model can change.

The narrowest repair to evaluate is to let the selection handler return before
starting the stream, with the selection/session lifetime explicitly preserved.
That belongs in the portal's acceptance-to-startup boundary. An asynchronous
stream-start implementation would remove the nested loop more broadly, but is a
larger change. Merely adding deleteLater is insufficient: the recorded crash
already happened through a deferred-delete event. Nor is changing a connection
to queued sufficient without checking when QuickDialog and captured pointers
are deleted.

Independently, Qt Multimedia should propagate unsuccessful portal responses
through its existing capture-error interface. Parsing warning text, adding a
second portal client, or hiding the problem with an arbitrary AutoTalk timeout
would leave the faulty boundaries intact.

No repaired build has been tested and no particular fixed upstream release has
been established. A later acceptance run should separately test an existing
physical display and the virtual-display path. Using an existing display tests
AutoTalk's intended presentation workflow; it does not count as fixing the
virtual-display crash.

Local evidence remains in ignored `artifacts/wayland-acceptance/`: portal.core,
gdb-resolved.txt, gdb-details.txt, gdb-selection.txt, display-events.log and the
matching source extracts. The full core is not committed because it contains
process memory. Production and regression-test changes: **0 lines**.
