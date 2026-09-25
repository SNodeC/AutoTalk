"""Provision pinned tools privately; never change the system Python or drivers."""

import hashlib
import json
import os
import platform
import queue
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
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
        self.log = log or report
        self.open_url = open_url
        self.cancelled = threading.Event()
        self.event = event

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
                               stderr=subprocess.STDOUT,
                               env=env or child_env(), cwd=cwd)
    tail = ""
    messages = queue.Queue(maxsize=256)
    finished = threading.Event()

    def read():
        try:
            for block in iter(process.stdout.readline, b""):
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
                block = messages.get(timeout=0.2)
            except queue.Empty:
                continue
            value = block.decode(errors="replace")
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
        total = int(response.headers.get("Content-Length", 0)) + offset
        last = 0
        with partial.open("ab" if append else "wb") as stream:
            while block := response.read(1024 * 1024):
                task.check()
                stream.write(block)
                offset += len(block)
                if time.monotonic() - last > 0.5:
                    task.report(f"Downloading {destination.name}: {offset / 2**20:.0f} / {total / 2**20:.0f} MiB")
                    last = time.monotonic()
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


def ensure_codex(task):
    # Existing installations preserve the user's normal ChatGPT login.
    existing = shutil.which("codex")
    if existing:
        return Path(existing)
    _, _, codex, archive, _, checksum = binary_platform()
    suffix = ".exe" if platform.system() == "Windows" else ""
    return install_binary(f"codex-{CODEX_VERSION}{suffix}",
                          f"https://github.com/openai/codex/releases/download/rust-v{CODEX_VERSION}/codex-{codex}.{archive}",
                          checksum, "codex-" + codex, task)


def speech_python() -> Path:
    root = data_dir() / ("speech-v2-" + speech_backend())
    return root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


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
            run([uv, "venv", "--managed-python", "--python", "3.12.14", python.parent.parent], task)
        requirements = Path(__file__).with_name("speech-" + {
            "Linux": "linux", "Windows": "windows", "Darwin": "macos"}[platform.system()] + ".txt")
        fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
        if not marker.exists() or json.loads(marker.read_text()) != fingerprint:
            task.report("Installing GPU speech dependencies. The first download is several GB…")
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
    with SpeechSession(task, request) as session:
        session.generate(request)


class SpeechSession:
    """One managed model process per preparation; it accepts successive batches."""
    def __init__(self, task, config):
        self.task, self.config = task, config
        self.process = None
        self.readers = []
        self.messages = queue.Queue()
        self.lock = None

    def __enter__(self):
        from PySide6.QtCore import QLockFile
        try:
            data_dir().mkdir(parents=True, exist_ok=True)
            self.lock = QLockFile(str(data_dir() / "speech-session.lock"))
            if not self.lock.tryLock(0):
                raise RuntimeError("Another AutoTalk instance is using the speech GPU.")
            started = time.monotonic()
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

    def generate(self, request, on_event=None):
        self._send({"items": request["items"]})
        self._wait("batch_complete", on_event)

    def close(self):
        if self.process:
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

    def __exit__(self, *args):
        self.close()
