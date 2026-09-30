# Approved Qt capture cleanup correction

The user explicitly authorized reapplying a Qt patch after the independent
reproduction and upstream bug investigation. This supersedes the no-patches
checkpoint in `2026-09-29-unmodified-dependencies.md` for this correction only.

## Scope and invariant

Cleanup must tolerate partially initialized resources. Stock Qt 6.10.2 transitions
the capture helper to Streaming after OpenPipeWireRemote fails, even though no
PipeWire event loop was created. Calling stop then invokes pw_thread_loop_stop
with a null pointer. The Qt-only probe, without AutoTalk imports, reproduces SIGSEGV;
the same failure was reproduced on stock 6.11.2.

The approved patch guards that one stop call with `if (m_threadLoop)`. This makes
resource cleanup safe for the absent-loop case and leaves normal teardown intact.
It does not redesign Qt's activation state machine or correct its separate
permission-cancellation notification behavior.

Only `packaging/qt-6.10.2-pipewire-cleanup.patch` is applied. The former combined
patch remains deleted: its callback-lifetime backport, portal-cancellation
notification, registry filtering and teardown reordering are not restored.
AutoTalk's application-side QObject ownership correction remains in place.
No alternative screen-capture backend was introduced.

## Build and distribution

Restored the existing version-gated build procedure for `--system-qt` with
PySide6/system Qt 6.10.2, using the new narrow patch. It downloads the pinned
source archive, applies the patch with zero fuzz, rebuilds Multimedia and includes
only that corrected library in AutoTalk. Failure to apply/build stops packaging.

The system Qt installation, other libraries and speech environments are untouched.
Source archive, license texts, patch and build recipe accompany the bundle.
Other Qt versions and standard wheel builds are not patched automatically.

On this host the existing private PipeWire development package staging is used:

```sh
PKG_CONFIG_PATH="$PWD/artifacts/open-tasks/build-deps/root/usr/lib/x86_64-linux-gnu/pkgconfig" \
  artifacts/open-tasks/venv-qt610/bin/python tools/build.py --system-qt
```

Stock system Multimedia SHA-256:
`2d2f64ac228ed64cce614c371eff35059c59d7e94595946f98e4a34acffddeaf`

Corrected bundled Multimedia SHA-256:
`a7243f9b75189d79d97171bee23e388a135e1e1572571e392e424b9a9603782f`

## Verification

- Qt-only probe: 20 consecutive failed-remote-initialization/stop/destruction
  cycles, clean exit. Original stock-library evidence remains in
  `evidence/2026-09-29-stock-qt/`.
- AutoTalk probe: 20 failed-initialization/cleanup/retry cycles, no recording
  workers started, native session objects released and correct journal errors.
- Focused build and capture tests: 14 passed, including version compatibility,
  patch application failure and AutoTalk's native-object lifetime invariant.
- Full suite on the corrected native library under Xvfb: **420 passed,
  8 audio-device tests deselected**, 110.44 seconds. Rebuilt executable smoke test
  passed. Re-running the same probe with stock Qt still exits -11; the corrected
  library exits 0.
- System package verification remains clean (`dpkg -V libqt6multimedia6`).
- Tests use private D-Bus/Xvfb sessions without desktop-sharing permission or
  physical audio changes. The successful real Wayland recording in the previous
  report used stock Qt; it is not claimed as a fresh live test of this rebuild.

Repeat the independent checks with:

```sh
PYTHONPATH="$PWD/build/system-qt:$PWD/src" \
LD_LIBRARY_PATH="$PWD/build/system-qt/PySide6/Qt/lib" \
  xvfb-run -a dbus-run-session -- artifacts/open-tasks/venv-qt610/bin/python \
  tests/probes/qt_remote_failure.py
```

Add `--autotalk` to run the application capture ownership test instead.

## Upstream status and removal criterion

No exact public bug report was found for this failed-remote cleanup crash.
[QTBUG-136981](https://qt-project.atlassian.net/browse/QTBUG-136981) is a related
Linux/Wayland permission-cancellation defect, not an exact crash match.
The [Qt 6.12 event-loop ownership change](https://github.com/qt/qtmultimedia/commit/a02154e751b957386f374146b57b84bbe622b033)
removes the helper's direct loop-stop call. It may eliminate this failure but has
not been qualified here. Test an unmodified official version containing that
change before removing this local correction; do not carry the patch forward
blindly or label it an upstream backport.

## Accounting

Relative to the immediately preceding rollback: 27 Python build lines restored;
no additional AutoTalk runtime code. The dependency patch changes one Qt source
line into two (net +1). Build tests restore net 24 lines; the standalone failure
probe adds net 33 lines for repeated cycles and an AutoTalk integration case
(total test growth net 57 lines). Prior language work
is preserved and excluded from this accounting.
