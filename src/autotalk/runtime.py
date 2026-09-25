"""Provision pinned tools privately; never change the system Python or drivers."""

import hashlib
import json
import os
import platform
import selectors
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

UV_VERSION = "0.12.19"
UV_SHA = "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"
CODEX_VERSION = "0.157.0"
CODEX_SHA = "db3fe3adaa35c50edfb68a988a117782fe3492960fb63d7003eb6748ccc0657b"
MODELS = json.loads(Path(__file__).with_name("models.json").read_text())
SPEECH_REQUIREMENTS = Path(__file__).with_name("speech-requirements.txt")


def data_dir() -> Path:
    return Path(os.environ.get("AUTOTALK_DATA_DIR", Path(os.environ.get(
        "XDG_DATA_HOME", Path.home() / ".local/share")) / "autotalk"))


class Cancelled(Exception):
    pass


class Task:
    def __init__(self, report=print, open_url=lambda url: None, log=None):
        self.report = report
        self.log = log or report
        self.open_url = open_url
        self.cancelled = threading.Event()

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
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONUNBUFFERED"] = "1"
    env["HF_HOME"] = str(data_dir() / "models")
    return env


def stop_process(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def run(command, task: Task, *, env=None, cwd=None):
    task.check()
    process = subprocess.Popen([str(c) for c in command], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True,
                               env=env or child_env(), cwd=cwd)
    tail = ""
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            task.check()
            for key, _ in selector.select(0.2):
                block = os.read(key.fileobj.fileno(), 8192)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                value = block.decode(errors="replace")
                tail = (tail + value)[-12000:]
                task.log(value.strip())
        if process.wait() != 0:
            raise RuntimeError(f"Command failed: {Path(str(command[0])).name}\n{tail[-4000:]}")
        return tail
    finally:
        selector.close()
        stop_process(process)
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
    with tarfile.open(archive) as tar:
        item = next((m for m in tar.getmembers() if m.isfile() and Path(m.name).name == member), None)
        if item is None:
            raise RuntimeError(f"Expected executable {member} is missing from the verified archive.")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        with tar.extractfile(item) as source, temporary.open("wb") as out:
            shutil.copyfileobj(source, out)
        temporary.chmod(0o755)
        temporary.replace(target)
    return target


def ensure_uv(task):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("This prototype's automatic runtime supports Linux x86_64.")
    return install_binary(f"uv-{UV_VERSION}",
                          f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz",
                          UV_SHA, "uv", task)


def ensure_codex(task):
    # Existing installations preserve the user's normal ChatGPT login.
    existing = shutil.which("codex")
    if existing:
        return Path(existing)
    ensure_uv(task)  # Checks the supported platform before binary provisioning.
    return install_binary(f"codex-{CODEX_VERSION}",
                          f"https://github.com/openai/codex/releases/download/rust-v{CODEX_VERSION}/codex-x86_64-unknown-linux-musl.tar.gz",
                          CODEX_SHA, "codex-x86_64-unknown-linux-musl", task)


def speech_python() -> Path:
    return data_dir() / "speech-v1" / "bin" / "python"


def ensure_speech(task):
    import fcntl
    data_dir().mkdir(parents=True, exist_ok=True)
    with (data_dir() / "setup.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another AutoTalk instance is preparing the speech runtime.") from None
        uv = ensure_uv(task)
        python = speech_python()
        marker = python.parent.parent / "autotalk-ready.json"
        if not python.exists():
            task.report("Preparing private Python 3.12 runtime…")
            run([uv, "venv", "--python", "3.12", python.parent.parent], task)
        fingerprint = hashlib.sha256(SPEECH_REQUIREMENTS.read_bytes()).hexdigest()
        if not marker.exists() or json.loads(marker.read_text()) != fingerprint:
            task.report("Installing GPU speech dependencies. The first download is several GB…")
            run([uv, "pip", "install", "--python", python, "-r", SPEECH_REQUIREMENTS], task)
            marker.write_text(json.dumps(fingerprint))
        return python


def worker_path():
    return Path(__file__).with_name("speech_worker.py")


def speech_command(task, request: dict):
    python = ensure_speech(task)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="autotalk-speech-") as tmp:
        path = Path(tmp) / "request.json"
        path.write_text(json.dumps(request))
        run([python, worker_path(), path], task)
