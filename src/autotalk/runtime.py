"""Provision pinned tools privately; never change the system Python or drivers."""

import hashlib
import json
import os
import platform
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
from contextlib import contextmanager
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

UV_VERSION = "0.12.19"
CODEX_VERSION = "0.157.0"
# Pinned upstream release asset hashes; selection never depends on a latest URL.
BINARIES = {
    "Linux": ("x86_64", "x86_64-unknown-linux-gnu", "x86_64-unknown-linux-musl", "tar.gz",
              "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8",
              "db3fe3adaa35c50edfb68a988a117782fe3492960fb63d7003eb6748ccc0657b"),
    "Windows": ("AMD64", "x86_64-pc-windows-msvc", "x86_64-pc-windows-msvc.exe", "zip",
                "6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0",
                "6c74e2019583cc16e55f79161ef795c8ff712709ad9ed832b3a5b87a7eacdef6"),
    "Darwin": ("arm64", "aarch64-apple-darwin", "aarch64-apple-darwin", "tar.gz",
               "a9a8df1eedeb192f2e47e40e2faabfb387db4b850209118786d42f89dde3e0ba",
               "0f1522362bf8c8bbb58bf2fa8a3c600a0b723f1d4e3405ab831afeda32438909"),
}
MODELS = json.loads(Path(__file__).with_name("models.json").read_text())
_spawn_lock = threading.Lock()
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def data_dir() -> Path:
    if "AUTOTALK_DATA_DIR" in os.environ:
        return Path(os.environ["AUTOTALK_DATA_DIR"])
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "AutoTalk"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/AutoTalk"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "autotalk"


class Cancelled(Exception):
    pass


class Task:
    def __init__(self, report=print, open_url=lambda url: None, log=None, event=lambda value: None):
        self.report = report
        self.log = lambda value: (log or report)(ANSI_ESCAPE.sub("", value))
        self.open_url = open_url
        self.cancelled = threading.Event()
        self.event = event
        self.speech = None

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled("Operation cancelled. Completed work has been saved.")


def child_env():
    env = os.environ.copy()
    # Frozen launchers must not inject their bundled libraries into external tools.
    if getattr(sys, "frozen", False):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        env.pop("LD_LIBRARY_PATH", None)
        if original:
            env["LD_LIBRARY_PATH"] = original
        for name in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
            env.pop(name, None)
        bundle = Path(sys._MEIPASS).resolve()
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                     if p and not Path(p).resolve().is_relative_to(bundle))
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONUNBUFFERED"] = "1"
    env["HF_HOME"] = str(data_dir() / "models")
    env["UV_PYTHON_INSTALL_DIR"] = str(data_dir() / "python")
    return env


def process_options():
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def start_process(command, **kwargs):
    """External runtimes must not inherit the launcher's native library search path."""
    kwargs.setdefault("env", child_env())
    with _spawn_lock:
        frozen_windows = sys.platform == "win32" and getattr(sys, "frozen", False)
        if frozen_windows:
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:
            return subprocess.Popen(command, **process_options(), **kwargs)
        finally:
            if frozen_windows:
                ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)


def stop_process(process):
    if process.poll() is None:
        if sys.platform == "win32":
            # taskkill is an OS component, located independently of the user's PATH.
            executable = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"
            subprocess.run([str(executable), "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
    if sys.platform != "win32":
        # A worker may exit before its GPU children. Its isolated process group
        # must also be gone before another model is allowed to acquire the GPU.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run(command, task: Task, *, env=None, cwd=None):
    task.check()
    process = start_process([str(c) for c in command], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                               env=env or child_env(), cwd=cwd)
    tail = ""
    messages = queue.Queue(maxsize=256)
    finished = threading.Event()

    def read():
        try:
            for block in iter(process.stdout.readline, ""):
                while not finished.is_set():
                    try:
                        messages.put(block, timeout=0.1)
                        break
                    except queue.Full:
                        pass
        finally:
            finished.set()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        while not finished.is_set() or not messages.empty():
            task.check()
            try:
                value = messages.get(timeout=0.2)
            except queue.Empty:
                continue
            value = ANSI_ESCAPE.sub("", value)
            tail = (tail + value)[-12000:]
            task.log(value.strip())
        task.check()
        if process.wait() != 0:
            raise RuntimeError(f"Command failed: {Path(str(command[0])).name}\n{tail[-4000:]}")
        return tail
    finally:
        finished.set()
        stop_process(process)
        reader.join(timeout=2)
        process.stdout.close()


def download(url: str, destination: Path, sha256: str, task: Task):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == sha256:
        return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={"User-Agent": "AutoTalk/0.1",
                                                  "Range": f"bytes={offset}-"})
    try:
        response = urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as error:
        if error.code != 416:
            raise
        partial.unlink(missing_ok=True)
        return download(url, destination, sha256, task)
    with response:
        append = response.status == 206 and offset > 0
        if not append:
            offset = 0
        length = response.headers.get("Content-Length")
        total = int(length) + offset if length else None
        last = 0
        with partial.open("ab" if append else "wb") as stream:
            while block := response.read(1024 * 1024):
                task.check()
                stream.write(block)
                offset += len(block)
                if time.monotonic() - last > 0.5:
                    task.event({"type": "model_progress", "stage": "Downloading runtime: " + destination.name,
                                "completed": offset, "total": total, "unit": "bytes"})
                    last = time.monotonic()
        task.event({"type": "model_progress", "stage": "Checking runtime download"})
    with partial.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != sha256:
        partial.unlink()
        raise RuntimeError(f"Download verification failed for {destination.name}. Please retry.")
    partial.replace(destination)
    return destination


def install_binary(name, url, checksum, member, task):
    target = data_dir() / "tools" / name
    if target.is_file():
        return target
    archive = download(url, data_dir() / "downloads" / f"{name}.tar.gz", checksum, task)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as container:
            item = next((m for m in container.infolist() if not m.is_dir() and Path(m.filename).name == member), None)
            if item is None:
                raise RuntimeError(f"Expected executable {member} is missing from the verified archive.")
            with container.open(item) as source, temporary.open("wb") as out:
                shutil.copyfileobj(source, out)
    else:
        with tarfile.open(archive) as container:
            item = next((m for m in container.getmembers() if m.isfile() and Path(m.name).name == member), None)
            if item is None:
                raise RuntimeError(f"Expected executable {member} is missing from the verified archive.")
            with container.extractfile(item) as source, temporary.open("wb") as out:
                shutil.copyfileobj(source, out)
    temporary.chmod(0o755)
    temporary.replace(target)
    return target


def ensure_uv(task):
    _, uv, _, archive, checksum, _ = binary_platform()
    suffix = ".exe" if platform.system() == "Windows" else ""
    return install_binary(f"uv-{UV_VERSION}{suffix}",
                          f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/uv-{uv}.{archive}",
                          checksum, "uv" + suffix, task)


def binary_platform():
    target = BINARIES.get(platform.system())
    machine = platform.machine().lower()
    if target is None or machine != target[0].lower():
        raise RuntimeError("AutoTalk supports Linux x86_64, Windows x64, and Apple Silicon macOS.")
    return target


def ensure_codex(task, *, install=True):
    # Existing installations preserve the user's normal ChatGPT login.
    existing = shutil.which("codex")
    if existing:
        return Path(existing)
    _, _, codex, archive, _, checksum = binary_platform()
    suffix = ".exe" if platform.system() == "Windows" else ""
    name = f"codex-{CODEX_VERSION}{suffix}"
    if not install:
        cached = data_dir() / "tools" / name
        return cached if cached.is_file() else None
    return install_binary(name,
                          f"https://github.com/openai/codex/releases/download/rust-v{CODEX_VERSION}/codex-{codex}.{archive}",
                          checksum, "codex-" + codex, task)


def speech_python() -> Path:
    root = data_dir() / ("speech-v2-" + speech_backend())
    return root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def check_model_update(spec, task):
    """Check upstream metadata without changing the verified model manifest/cache."""
    task.check()
    task.event({"type": "model_progress", "stage": "Checking model updates online"})
    request = urllib.request.Request("https://huggingface.co/api/models/" + spec["repo"] + "?expand=sha",
                                     headers={"User-Agent": "AutoTalk/0.3"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            latest = json.loads(response.read(65536)).get("sha", "")
        if len(latest) != 40 or any(c not in "0123456789abcdef" for c in latest):
            raise ValueError("The server did not provide a valid model revision.")
    except (OSError, ValueError, AttributeError, TypeError) as error:
        task.check()
        raise RuntimeError(f"Could not check model updates: {error}") from error
    task.check()
    return latest


def speech_backend():
    binary_platform()
    return {"Linux": "vllm", "Windows": "torch", "Darwin": "mlx"}[platform.system()]


def ensure_speech(task):
    from PySide6.QtCore import QLockFile
    data_dir().mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data_dir() / "runtime-setup.lock"))
    if not lock.tryLock(0):
        raise RuntimeError("Another AutoTalk instance is preparing the speech runtime.")
    try:
        uv = ensure_uv(task)
        python = speech_python()
        marker = python.parent.parent / "autotalk-ready.json"
        if not python.exists():
            task.report("Preparing private Python 3.12 runtime…")
            task.event({"type": "model_progress", "stage": "Creating private speech runtime"})
            run([uv, "venv", "--managed-python", "--python", "3.12.14", python.parent.parent], task)
        requirements = Path(__file__).with_name("speech-" + {
            "Linux": "linux", "Windows": "windows", "Darwin": "macos"}[platform.system()] + ".txt")
        fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
        if not marker.exists() or json.loads(marker.read_text()) != fingerprint:
            task.report("Installing GPU speech dependencies. The first download is several GB…")
            task.event({"type": "model_progress", "stage": "Installing speech dependencies"})
            run([uv, "pip", "sync", "--python", python, requirements], task)
            marker.write_text(json.dumps(fingerprint))
        if speech_backend() == "vllm":
            for name, mode in (("cc", "cc"), ("cxx", "c++")):
                compiler = python.parent / ("autotalk-" + name)
                command = [str(python), str(Path(__file__).with_name("compiler.py")), mode]
                compiler.write_text("#!/bin/sh\nexec " + shlex.join(command) + ' "$@"\n')
                compiler.chmod(0o755)
        return python
    finally:
        lock.unlock()


def worker_path():
    return Path(__file__).with_name("speech_worker.py")


def speech_command(task, request: dict):
    with speech_session(task, request) as session:
        session.generate(request)


@contextmanager
def speech_session(task, config, preload=False):
    config = {key: config[key] for key in ("backend", "model", "source", "speaker", "sampling")}
    session = task.speech or SpeechSession(task, config)
    with session.guard:
        if session.idle_timer:
            session.idle_timer.cancel()
            session.idle_timer = None
        session.release_requested = False
        try:
            session.task = task
            session.configure(config)
            yield session
        except BaseException:
            if session.state != "in_use":
                task.report("Stopping speech worker: " + ("operation cancelled" if task.cancelled.is_set() else "speech operation failed") + ".")
                session.close()
                if not task.cancelled.is_set():
                    session.phase = "failed"
            raise
        finally:
            if session.phase != "failed" and (task.speech is None or session.release_requested or session.retention == "operation" and not preload):
                session.close()
            else:
                session.schedule_release()
            session.task = Task(report=lambda _: None, log=lambda _: None)


def backend_loading_progress(line):
    """Decode only the pinned vLLM 0.28 loading diagnostics; never infer readiness."""
    line = ANSI_ESCAPE.sub("", line)
    engine = re.search(r"(?:StageEngineCoreProc_stage|\[StageRuntime\] Stage )(\d+)", line)
    prefix = f"Speech engine {int(engine[1])+1}: " if engine else ""
    event = {"type": "model_progress", "stage": ""}
    files = re.search(r"Loading safetensors checkpoint shards(?: \(eager\))?:\s*\d+% Completed \|\s*(\d+)/(\d+)\s", line)
    if files:
        completed, total = map(int, files.groups())
        if total > 0 and 0 <= completed <= total:
            return {**event, "stage": prefix + "Reading checkpoint files (current pass)",
                    "completed": completed, "total": total, "unit": "files"}
        return None
    for pattern, stage, detail in (
        (r"Initializing a V1 LLM engine", "Starting GPU runtime", ""),
        (r"Starting to load model ", "Loading model weights", ""),
        (r"Loaded (\d+) weights for Qwen3TTSTalkerForConditionalGeneration", "Speech weights loaded", "{0} weights reported"),
        (r"Loading weights took ([\d.]+) seconds", "Weight loading completed", "{0} s"),
        (r"Model loading took ([\d.]+) GiB memory and ([\d.]+) seconds", "Weights loaded; initializing engine", "Model memory: {0} GiB; load: {1} s"),
        (r"Available KV cache memory: ([\d.]+) GiB", "Preparing inference cache", "{0} GiB available for cache"),
        (r"GPU KV cache size: ([\d,]+) tokens", "Preparing inference cache", "Capacity: {0} tokens"),
        (r"init engine \(profile, create kv cache, warmup model\) took ([\d.]+) s", "GPU initialization completed", "{0} s for profiling, cache and warmup"),
        (r"\[StageRuntime\] Stage (\d+) initialized", "Initialization completed", "Service startup continues"),
        (r"Orchestrator ready with (\d+) stages", "Checking speech service", "{0} engine stages initialized"),
        (r"AsyncOmniEngine initialized in ([\d.]+) seconds", "Checking speech service", "Engine startup: {0} s"),
    ):
        match = re.search(pattern, line)
        if match:
            return {**event, "stage": prefix + stage, "detail": detail.format(*match.groups())}
    return None


class SpeechSession:
    """One model owner, optionally retained by the application between jobs."""
    def __init__(self, task, config):
        self.task, self.config = task, config
        self.guard = threading.Lock()
        self.retention = "session"
        self.phase = "unloaded"
        self.release_requested = False
        self.idle_timer = None
        self.process = None
        self.readers = []
        self.messages = queue.Queue()
        self.lock = None

    @property
    def state(self):
        process = self.process
        if process and process.poll() is not None and self.phase != "unloading":
            return "failed"
        return "in_use" if self.phase == "ready" and self.guard.locked() else self.phase

    def matches(self, config):
        process = self.process
        return bool(process and process.poll() is None and all(
            self.config.get(k) == config[k] for k in ("backend", "model", "source", "sampling")))

    def __enter__(self):
        if self.process:
            self.task.report("Reusing the loaded speech model.")
            return self
        from PySide6.QtCore import QLockFile
        self.phase = "loading"
        try:
            data_dir().mkdir(parents=True, exist_ok=True)
            self.lock = QLockFile(str(data_dir() / "speech-session.lock"))
            if not self.lock.tryLock(0):
                raise RuntimeError("Another AutoTalk instance is using the speech GPU.")
            started = time.monotonic()
            self.task.event({"type": "model_progress", "stage": "Preparing speech runtime"})
            python = ensure_speech(self.task)
            self.task.event({"type": "measurement", "stage": "Runtime setup", "seconds": time.monotonic()-started})
            env = child_env()
            if speech_backend() == "vllm":
                env.update(CC=str(python.parent / "autotalk-cc"), CXX=str(python.parent / "autotalk-cxx"),
                           ZIG_GLOBAL_CACHE_DIR=str(data_dir() / "cache/zig"),
                           ZIG_LOCAL_CACHE_DIR=str(data_dir() / "cache/zig-local"),
                           TRITON_CACHE_DIR=str(data_dir() / "cache/triton"),
                           TORCHINDUCTOR_CACHE_DIR=str(data_dir() / "cache/inductor"))
            self.process = start_process([str(python), str(worker_path())], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                errors="replace", bufsize=1, env=env)
            for pipe, protocol in ((self.process.stdout, True), (self.process.stderr, False)):
                reader = threading.Thread(target=self._read, args=(pipe, protocol), daemon=True)
                reader.start()
                self.readers.append(reader)
            self._send(self.config)
            self._wait("ready")
            self.phase = "ready"
            self.task.event({"type": "model_progress", "stage": "Speech model ready", "completed": 1, "total": 1, "unit": ""})
            return self
        except BaseException:
            self.close()
            raise

    def _read(self, pipe, protocol):
        for line in pipe:
            if protocol:
                try:
                    self.messages.put(json.loads(line))
                    continue
                except json.JSONDecodeError:
                    pass
            self.task.log(line.rstrip()[:4000])
            if not protocol and self.phase == "loading" and self.config.get("backend") == "vllm":
                self.messages.put({"type": "backend_log", "line": line})
        if protocol:
            self.messages.put(None)

    def _send(self, request):
        self.task.check()
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _wait(self, expected, on_event=None):
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            self.task.check()
            try:
                event = self.messages.get(timeout=0.2)
            except queue.Empty:
                continue
            if event is None:
                raise RuntimeError("The local speech process stopped. See preparation details.")
            if event.get("type") == "backend_log":
                event = backend_loading_progress(event["line"]) if expected == "ready" else None
                if event is None:
                    continue
            kind = event.get("type")
            if kind == "error":
                raise RuntimeError(event.get("message", "Speech generation failed."))
            if kind == expected:
                return
            if kind == "status":
                self.task.report(event["message"])
            else:
                (on_event or self.task.event)(event)
            deadline = time.monotonic() + 1200
        raise TimeoutError("Speech generation stopped responding. Completed slides have been retained.")

    def configure(self, config):
        requested = self.release_requested
        if not self.matches(config):
            if self.process:
                changed = ", ".join(k for k in ("backend", "model", "source", "sampling") if self.config.get(k) != config[k])
                self.task.report("Reloading speech model: " + ("changed " + changed if changed else "previous worker exited") + ".")
            self.close()
        self.config = {k: config[k] for k in ("backend", "model", "source", "speaker", "sampling")}
        self.__enter__()
        self.release_requested = requested

    def generate(self, request, on_event=None):
        self.configure(self.config | request)
        self.phase = "generating"
        self._send({**self.config, "items": request["items"]})
        self._wait("batch_complete", on_event)
        self.phase = "ready"

    def schedule_release(self):
        def expire():
            with self.guard:
                if self.idle_timer is threading.current_thread():
                    self.close()
        if self.idle_timer:
            self.idle_timer.cancel()
            self.idle_timer = None
        if self.process and (self.release_requested or self.retention == "idle"):
            self.idle_timer = threading.Timer(0 if self.release_requested else 300, expire)
            self.idle_timer.daemon = True
            self.idle_timer.start()

    def set_retention(self, policy):
        self.retention = policy
        if self.guard.acquire(blocking=False):
            try:
                self.schedule_release()
            finally:
                self.guard.release()

    def request_release(self):
        if not self.process and not self.guard.locked():
            return
        self.release_requested = True
        self.set_retention(self.retention)

    def release(self):
        with self.guard:
            self.close()

    def close(self):
        if self.idle_timer:
            self.idle_timer.cancel()
        if self.process:
            self.phase = "unloading"
            stop_process(self.process)
            for reader in self.readers:
                reader.join(timeout=2)
            for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                try:
                    pipe.close()
                except OSError:
                    pass
            self.process = None
        if self.lock and self.lock.isLocked():
            self.lock.unlock()
        self.readers.clear()
        self.messages = queue.Queue()
        self.phase = "unloaded"
        self.release_requested = False

    def __exit__(self, *args):
        self.close()
