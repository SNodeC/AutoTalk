<!-- Review by authenticated Claude Code CLI, requested by the repository owner.
Reviewed commit: 54b347367b13d81c4a53f0d8b2d24e330da6dff6.
Claude session: 8d498906-1cd1-46bf-a3a5-558787e61ea3.
Received 2026-11-02. The body below is Claude's independent assessment;
it is not a record of native DGX Spark execution or an owner approval.
-->

# AutoTalk Linux ARM64 / DGX Spark GPU review: commit `54b3473` against `e913399`

I had internet access. I made no changes to the repository, branches, packages, GPU or any external service. Scratch data went only to `/tmp/at_*`: PyPI and GitHub source fetches, plus the `vllm-omni` 0.28.0 wheel, which I unpacked and read but never imported or executed. I re-ran `tests/test_runtime.py` and `tests/test_build.py` on this x86_64 host: 25 passed. Nothing was run natively on ARM64 or on a GB10.

## Bottom line
- **No confirmed defect in the platform plumbing.** There is one OS+CPU table (`runtime.py:28-41`, `268-272`), which `tools/build.py:13,19` also uses. Windows (`"AMD64".lower()`) and macOS arm64 still select the same assets, and the Intel-Mac rejection still holds.
- **DGX Spark GPU operation is not established.** The upstream evidence makes GB10 support plausible but indirect, and the unchanged speech deployment means something different on unified memory.

## Findings by severity

### High: the unchanged memory budget behaves differently on unified memory (needs measurement on Spark, not yet a confirmed failure)
- **The settings.** `speech-linux.yaml:18,41` set `gpu_memory_utilization` to 0.65 for stage 0 and 0.2 for stage 1, both on `devices: '0'`.
- **How vLLM 0.28.0 reads them on an integrated GPU:**
  - It takes total memory from `psutil` and free memory from `psutil.virtual_memory().available` (`vllm/utils/mem_utils.py:48,148-155`, from PR [#35356](https://github.com/vllm-project/vllm/pull/35356), which fixed issue [#35313](https://github.com/vllm-project/vllm/issues/35313)).
  - It then requests `total × utilization` (`vllm/v1/worker/utils.py:449-453`).
  - Source: https://raw.githubusercontent.com/vllm-project/vllm/v0.28.0/vllm/utils/mem_utils.py
- **How vLLM-Omni 0.28.0 handles two stages on one GPU:**
  - It starts them one after the other (`engine/stage_runtime.py:445`).
  - If stage 1 finds less free memory than it asked for, it shrinks its budget to whatever is free instead of failing (`worker/memory_utils.py:18-55`).
  - It sets the KV-cache budget as the requested amount minus the process's NVML-reported memory (`worker/base.py:97-160`).
- **What that means on Spark:** about 85% of the whole shared pool is reserved. That is roughly 100 GiB on the 128 GB Spark and roughly 54 GiB on the 64 GB OEM GB10 systems listed on NVIDIA's product page. All of it backs a 1.7B TTS model with `max_num_seqs: 1`.
  - On the RTX 2000 Ada laptop, the same fractions only used VRAM.
  - On Spark, this memory is taken from the same pool that the desktop, the AutoTalk GUI, Codex, recording/export and every Python process's CPU-side memory all need.
- **How long it is held:** the default retention is `"session"` (`app.py:1246,1253`; `runtime.py:426`), so the reservation lasts for the life of the app.
- **Mitigating context:** vLLM's own Spark guide uses 0.85 for a *single* engine and says to leave headroom for the OS and page cache: https://vllm.ai/blog/2026-06-01-vllm-dgx-spark. NVIDIA warns that `cudaMemGetInfo` under-reports on Spark: https://docs.nvidia.com/dgx/dgx-spark/known-issues.html.
- **What to verify on hardware:**
  - The "Available KV cache memory … (process-scoped)" value for each stage. NVIDIA notes that iGPU memory reporting differs: `nvidia-smi` shows "Not Supported".
  - How much memory the system still has available while loaded, recording and exporting.
- An absolute budget would also work: vLLM-Omni honours `kv_cache_memory_bytes` (`worker/base.py:110`). That would be a deliberate deployment change, so decide it after measuring.

### High: GB10 (sm_121) kernel coverage is indirect (compatibility uncertainty)
- **torch 2.13.0 on aarch64 is a real CUDA 13 build, not CPU-only.** Its PEP 658 metadata requires `cuda-toolkit==13.0.3`, `nvidia-cudnn-cu13` and `triton==3.7.1`. Before 2.11, the PyPI aarch64 wheels were CPU-only: https://github.com/pytorch/pytorch/issues/160162
- **But the release wheel ships no sm_121 code of its own.** It contains SASS for 8.0, 9.0, 10.0, 11.0 and 12.0, and release builds add no PTX (`.ci/manywheel/build_env_setup.py:72-94`): https://raw.githubusercontent.com/pytorch/pytorch/v2.13.0/.ci/manywheel/build_env_setup.py
  - Running it on 12.1 depends on the rule that a cubin runs on any GPU with the same major revision: https://docs.nvidia.com/cuda/blackwell-compatibility-guide/index.html
  - That page states the rule in general terms. Applying it to 12.0 → 12.1 is my inference.
- **vLLM 0.28.0's aarch64 CUDA 13.0 wheel** is built for `"8.0 8.7 8.9 9.0 10.0 11.0 12.0"` using family targets. The upstream comment says "targets like 10.3 and 12.1 are automatically supported": https://raw.githubusercontent.com/vllm-project/vllm/v0.28.0/.buildkite/release-pipeline.yaml
  - The release notes mention GB10 MoE tuning: https://github.com/vllm-project/vllm/releases/tag/v0.28.0
  - The sm_121 bug [#36821](https://github.com/vllm-project/vllm/issues/36821) is still open, and the arch-list PR [#38484](https://github.com/vllm-project/vllm/pull/38484) is unmerged.
- **Triton 3.7.1** targets `sm_121a` using its bundled `ptxas-blackwell` 13.1.80: https://raw.githubusercontent.com/triton-lang/triton/v3.7.1/cmake/nvidia-toolchain-version.json
- **Attention backend:** on compute capability 12.x, vLLM tries FLASH_ATTN, then FLASHINFER, then TRITON_ATTN (`vllm/platforms/cuda.py:148-160`).
  - `flashinfer-python==0.6.16.post3` is JIT-only; the pins include no cubin or jit-cache package.
  - The laptop's sm_89 had native SASS throughout, so these fallback and JIT paths were probably never exercised in qualification.
- **Qwen3-TTS** has no ARM-specific code in AutoTalk's path. The models are the same bf16 checkpoints (`models.json`), and audio is explicit `<i2` little-endian, so they are only as good as the kernels underneath.

### Medium: driver/toolkit version skew on DGX OS (hardware-only check)
- **The mismatch:** DGX OS 7.6.0 ships driver 580.178.04 / CUDA 13.0.3 (https://docs.nvidia.com/dgx/dgx-spark/release-notes.html). The pins include nvcc, NVVM, nvJitLink and crt at 13.4.92, and Triton uses ptxas 13.1.
- **NVIDIA's rule:** code built with a newer 13.x toolkit runs on a driver ≥ 580 with a limited feature set, but "Applications that compile device code to PTX will not work on older drivers": https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html
- **Risk:** ptxas and nvcc produce cubins, so this is probably fine. Any path that hands 13.1/13.4 PTX to the driver would fail.
- **Open evidence gap:** the laptop's driver version isn't recorded, so this skew may never have been tested.

### Medium: the zig JIT compiler path has never run on aarch64 (hardware-only check)
- The vLLM worker sets `CC`/`CXX` to the zig shim (`runtime.py:341-346,463-468`), and `compiler.py` passes the original arguments straight to `ziglang`.
- Untested on ARM64:
  - Triton's launcher build linking `libcuda` from `/usr/lib/aarch64-linux-gnu`.
  - nvcc accepting zig `c++` as its host compiler, if FlashInfer JIT runs.
  - Zig's handling of the native glibc.

### Medium: teardown and reload on unified memory (existing design, larger exposure on Spark)
- `stop_process` (`runtime.py:116-146`) ends with a group `SIGKILL` but doesn't wait for group members to exit.
- On a discrete GPU this was fine in practice. On Spark, returning about 100 GiB of pinned pages may take longer.
- Because stage 1 shrinks its budget instead of failing (see the first finding), a reload that starts too soon may get a smaller KV budget without any error.
- Also untested:
  - The `VllmBackend` 300 s health deadline (`speech_worker.py:185`) on first start.
  - First-request JIT, which vLLM's Spark guide puts at about 25 s, inside the 180 s stream timeout.

### Low: packaging and Qt
- **glibc floor:** PySide6 6.11.2's aarch64 wheels are `manylinux_2_39`, versus `manylinux_2_34` on x86_64. So ARM64 needs glibc ≥ 2.39, and the docs don't say so.
- **Wheel contents match across architectures.** I checked by reading the zip central directories: both have QtPdf, QtMultimedia, the FFmpeg libraries and the FFmpeg plugin. aarch64 additionally ships a GStreamer plugin.
- **Not yet done:** a native PyInstaller build, a packaged launch, and the frozen `child_env` speech path on ARM64.

### Low: CI
- There is no ARM64 runner, and the ARM64 tests are simulated with `monkeypatch`. As documented at `BUILDING.md:84`.

### Low: accuracy of support statements
- **Error message:** `runtime.py:271` says "AutoTalk supports Linux x86_64/aarch64" with no qualifier. The docs call ARM64 experimental.
- **README table:** the row at `README.md:56` reads "Linux ARM64 with NVIDIA GPU". `binary_platform` accepts *any* aarch64 Linux (Jetson, GH200, Thor) and starts a multi-GB install. Only GB10 is the target, and the 64 GB vs 128 GB variants matter.
- **Install path:** `BUILDING.md:72-73` ("No alternate service or manual runtime installation is required") describes what the code does. It isn't yet validated, and vLLM's own Spark guidance uses the `cu130-nightly` container.
- **Accurate as written:** `README.md:15-17` and the rest of `BUILDING.md:63-78`.
- **Review report:** its header (`feat/linux-arm64`, "uncommitted") is a historical checkpoint and is accurate as such.

### Checked, no regression found
- **Cache/tool layout:** paths such as `tools/uv-0.12.19` and `speech-v2-vllm` aren't keyed by architecture. No supported workflow shares one data directory across architectures, so I'm not flagging it.
- **`tools/build.py`:** it now needs `autotalk` to be importable, which the documented `pip install -e '.[dev]'`, CI's `.[dev]` and `uv run` all provide.
  - Cosmetic: on an unsupported host it now fails with a `RuntimeError` traceback rather than a clean `SystemExit` message.
- **Source-only packages:** `antlr4-python3-runtime` and `openai-whisper` are pure-Python source archives on both architectures.
- **`SharedMemoryConnector` (`/dev/shm`):** arch-neutral, and its settings are unchanged.

## Assessment
- **Sufficient platform plumbing:** yes. The manifest, tool checksums, build eligibility, backend selection and archive naming are coherent, with no confirmed defect or regression.
- **DGX Spark GPU operation established:** no. Installation, imports, sm_121 kernels, the JIT and zig path, unified-memory budgeting, streaming, teardown and a packaged launch are all unverified.
- **Smallest remaining qualification**, on one 128 GB Spark with DGX OS 7.6 and driver 580.178.04:
  1. Fresh data dir, source launch, automatic setup. Then confirm `import torch, vllm, vllm_omni` works and record `torch.cuda.get_device_capability()`, `get_device_properties(0).is_integrated` and `get_arch_list()`.
  2. Run one preview per model type (CustomVoice, Base with a reference, VoiceDesign). Capture the chosen attention backend, the per-stage "Available KV cache memory", any Triton/FlashInfer/zig compiles, and any PTX or driver errors.
  3. Record `MemAvailable` with the GUI open, then loaded, during export/recording, and across about five unload/reload model switches.
  4. Run a full talk and record time-to-first-audio and real-time factor. Cancel mid-stream, quit, and confirm no `vllm` processes remain.
  5. Build natively with PyInstaller on Spark, run `--smoke-test`, and do one speech run from the package.
  6. Based on step 3, decide the UMA memory budget. Tighten the README row and the `runtime.py:271` wording to "DGX Spark (GB10), experimental".
  7. Separately: add an arm64 runner to the org workflow for tests and package smoke.

Sources:
- [NVIDIA DGX Spark product page](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)
- [DGX Spark release notes](https://docs.nvidia.com/dgx/dgx-spark/release-notes.html)
- [DGX Spark known issues](https://docs.nvidia.com/dgx/dgx-spark/known-issues.html)
- [CUDA minor version compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)
- [Blackwell compatibility guide](https://docs.nvidia.com/cuda/blackwell-compatibility-guide/index.html)
- [PyTorch v2.13.0 `build_env_setup.py`](https://raw.githubusercontent.com/pytorch/pytorch/v2.13.0/.ci/manywheel/build_env_setup.py)
- [PyTorch issue #160162](https://github.com/pytorch/pytorch/issues/160162)
- [vLLM v0.28.0 release](https://github.com/vllm-project/vllm/releases/tag/v0.28.0)
- [vLLM v0.28.0 release pipeline](https://raw.githubusercontent.com/vllm-project/vllm/v0.28.0/.buildkite/release-pipeline.yaml)
- [vLLM v0.28.0 `CMakeLists.txt`](https://raw.githubusercontent.com/vllm-project/vllm/v0.28.0/CMakeLists.txt)
- [vLLM v0.28.0 `mem_utils.py`](https://raw.githubusercontent.com/vllm-project/vllm/v0.28.0/vllm/utils/mem_utils.py)
- [vLLM v0.28.0 `platforms/cuda.py`](https://raw.githubusercontent.com/vllm-project/vllm/v0.28.0/vllm/platforms/cuda.py)
- [vLLM issue #35313](https://github.com/vllm-project/vllm/issues/35313)
- [vLLM PR #35356](https://github.com/vllm-project/vllm/pull/35356)
- [vLLM issue #36821](https://github.com/vllm-project/vllm/issues/36821)
- [vLLM PR #38484](https://github.com/vllm-project/vllm/pull/38484)
- [vLLM on the DGX Spark (blog)](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark)
- [vLLM GPU installation docs](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)
- [Triton v3.7.1 toolchain versions](https://raw.githubusercontent.com/triton-lang/triton/v3.7.1/cmake/nvidia-toolchain-version.json)
- [PyPI JSON API](https://pypi.org/pypi/vllm-omni/0.28.0/json) (also used for torch, vllm, triton, flashinfer-python and PySide6)
