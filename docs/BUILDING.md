# Building and testing AutoTalk

AutoTalk is a Python/PySide6 application packaged with PyInstaller. Build native
packages on the target operating system. Source execution uses the same application
code as the packaged executable.

## Source environment

Use Python 3.12–3.14; the CI matrix uses Python 3.12. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/autotalk
```

On Windows use `py -3.12 -m venv .venv`, then replace `.venv/bin/python` with
`.venv\Scripts\python.exe` and launch `.venv\Scripts\autotalk.exe`.
The development extra installs pytest, pytest-qt and PyInstaller.

On Ubuntu 24.04, CI installs these Qt runtime dependencies:

```sh
sudo apt-get update
sudo apt-get install -y libegl1 libopengl0 libxcb-cursor0 libxkbcommon-x11-0 libpulse0
```

Other distributions may use different package names. Speech inference separately
requires a supported GPU and a working compatible driver. AutoTalk manages its
speech environment and model downloads in the user's application-data directory.
The Python environment above is for running or building the application itself.

## Tests

Tests that do not require an audio device run in the native CI matrix:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -m 'not audio_device'
```

For Linux interaction checks using Xvfb, install `xvfb` and `xauth` and run:

```sh
QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/python -m pytest -q -m 'not audio_device'
```

In PowerShell, set `$env:QT_QPA_PLATFORM = 'offscreen'` before running pytest.
Tests marked `audio_device` require a working physical or virtual output and
must be run in an appropriate local environment. Xvfb does not qualify native
Wayland screen sharing: that requires the desktop portal and user permission.
See the [verification record](VERIFICATION.md) for dated checks, rather than
assuming a passing CI run validates every device or desktop configuration.

## Native packages

```sh
.venv/bin/python tools/build.py
```

The build produces an application directory and an archive with a SHA-256 file
under `dist/`, including AutoTalk's MIT `LICENSE` and third-party notices.
Python wheels and source distributions also include the license.
Supported build targets are Linux x86_64, Windows x64 and macOS
Apple Silicon. The executable is `autotalk`, `autotalk.exe`, or the executable
inside `AutoTalk.app`. Keep the bundled files together.

The repository-root `./autotalk` launcher prefers `dist/autotalk/autotalk` when
present, otherwise `.venv/bin/autotalk`. Use the explicit virtual-environment
executable while developing to avoid launching an older bundle accidentally.

The [native-build workflow](../.github/workflows/native-builds.yml) runs tests,
packages the application and performs a packaged startup check on each target OS.
Its downloadable artifacts are development builds, not signed, qualified releases.

Optional signing hooks:

- macOS: `AUTOTALK_SIGN_IDENTITY` and `AUTOTALK_NOTARY_PROFILE`.
- Windows: `AUTOTALK_SIGN_CERT` and `AUTOTALK_TIMESTAMP_URL`.

## Qt libraries and platform styling

The standard build uses the Qt distribution supplied by the pinned PySide6
package. On Linux, `--system-qt` stages the build machine's Qt libraries and
platform/style plugins, including Breeze and Plasma integration when installed.
It requires `qtpaths6` and a PySide6 version matching system Qt exactly.

For a machine with Qt 6.10.2, an isolated environment can be used:

```sh
uv run --extra dev --with PySide6==6.10.2 python tools/build.py --system-qt
```

The Qt 6.10.2 system build applies the version-specific Multimedia patch supplied
in `packaging/` and rebuilds that library for the application bundle. Consult the
patch header and [third-party notices](../THIRD_PARTY.md) for its exact scope;
standard wheel builds do not acquire these corrections automatically. The source
archive, patch and build recipe accompany the native bundle in
`qt-multimedia-source/`.

This path requires CMake, Ninja, `patch`, matching Qt development/private and
shader-tools packages, plus PipeWire, PulseAudio and FFmpeg development headers.
`PKG_CONFIG_PATH` may point to privately staged development packages. The build
stages its output without replacing installed system libraries or the original
Python environment. Missing optional Qt modules, such as Qt PDF, come from the
same-version binding package.

Desktop plugins must be ABI-compatible with the bundled Qt. The resulting Linux
package inherits the build host's glibc baseline; it is not qualified for arbitrary
older distributions. Recheck dependency corrections and platform integration when
changing Qt versions rather than blindly applying an old patch.

## Code organization

| Module | Responsibility |
| --- | --- |
| `project.py` | Project configuration, settings resolution and artifact validity |
| `services.py` | Preparation jobs and validated results |
| `runtime.py`, `speech_worker.py` | Managed processes and platform speech backends |
| `app.py`, `ui.py`, `settings.py` | Application interactions, views and settings |
| `playback.py` | Presentation position and consumed audio |
| `media.py`, `screen_capture.py` | Mixing, export and recording |

Narration generation and speech synthesis are separate operations. Saved audio
is reused when its effective inputs match. Playback and export share the audio
mixing implementation. The application manages one speech service across its
operations rather than starting an independent service for each UI action.

## Distribution status

The project remains a development prototype. Windows/macOS native behavior,
release signing and wider hardware testing require further work. AutoTalk's own
code uses the [MIT License](../LICENSE); review
[third-party notices](../THIRD_PARTY.md) before redistribution.
