# Third-party software

AutoTalk's own license has not yet been selected. Upstream software and model
weights retain their licenses. Redistribution must retain the applicable notices.

| Component | License / source |
| --- | --- |
| Qt / PySide6 / Shiboken | LGPL/GPL/commercial, depending on module; [Qt licensing](https://doc.qt.io/qt-6/licensing.html) |
| Qt PDF / PDFium | Includes third-party PDFium code; [Qt PDF licenses](https://doc.qt.io/qt-6/qtpdf-index.html#licenses-and-attributions) |
| Qt Multimedia / FFmpeg | Bundled Qt multimedia reports FFmpeg under LGPL 2.1 or later; [Qt Multimedia](https://doc.qt.io/qt-6/qtmultimedia-index.html#licenses-and-attributions) |
| CPython | Python Software Foundation License; [Python](https://docs.python.org/3/license.html) |
| PyInstaller | GPL with a bundling exception; [PyInstaller](https://pyinstaller.org/en/stable/license.html) |
| uv | MIT or Apache-2.0; [uv](https://github.com/astral-sh/uv) |
| Codex | Apache-2.0; [Codex](https://github.com/openai/codex) |
| Qwen3-TTS code and model weights | Apache-2.0; [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) |
| PyTorch | BSD-style; [PyTorch](https://github.com/pytorch/pytorch/blob/main/LICENSE) |
| NVIDIA runtime dependencies | NVIDIA's applicable redistribution terms; [CUDA](https://docs.nvidia.com/cuda/eula/index.html) |

The packaged prototype uses dynamically loaded Qt libraries. Speech dependencies
and model weights are downloaded into the user's private application data
directory; they are not included in the application archive. Their distribution
metadata and license files remain in that environment. The exact speech package
versions are recorded in the platform-specific `src/autotalk/speech-*.txt` lock files.

The prototype is a development build. Before publishing a distributable release,
select AutoTalk's license and complete the applicable Qt/PDF and third-party
notice/source distribution requirements.

Additional 0.2 dependencies: vLLM / vLLM-Omni (Apache-2.0), MLX / MLX Audio
(MIT), Zig (MIT), NumPy (BSD), and PyAV (BSD). PyAV bundles its own FFmpeg
libraries, including the H.264 encoder used for recording. Those libraries have
their own licensing terms; the Qt Multimedia LGPL notice does not describe the
entire video-export stack. Preserve the wheel distribution notices and review
the exact bundled libraries before public redistribution.
