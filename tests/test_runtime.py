# SPDX-License-Identifier: MIT
"""Runtime lifecycle and verified archive extraction at the subprocess/file boundary."""

import hashlib
import sys
import zipfile

import pytest

from autotalk import runtime


def test_run_drains_output_and_reports_failure():
    lines = []
    task = runtime.Task(log=lines.append)
    result = runtime.run([sys.executable, "-c", "print('hello'); print('last')"], task)
    assert result == "hello\nlast\n"
    assert lines == ["hello", "last"]
    with pytest.raises(RuntimeError, match="useful failure"):
        runtime.run([sys.executable, "-c", "import sys; print('useful failure'); sys.exit(3)"], task)


def test_run_normalizes_newlines_and_decodes_utf8():
    lines = []
    script = "import sys; sys.stdout.buffer.write(b'Gr\\xc3\\xbc\\xc3\\x9fe\\r\\nprogress\\rfinal\\ninvalid \\xff')"
    result = runtime.run([sys.executable, "-c", script], runtime.Task(log=lines.append))
    assert result == "Grüße\nprogress\nfinal\ninvalid \ufffd"
    assert lines == ["Grüße", "progress", "final", "invalid \ufffd"]


def test_verified_zip_extracts_only_named_executable(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOTALK_DATA_DIR", str(tmp_path / "data"))
    archive = tmp_path / "tool.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("../escape", "not extracted")
        package.writestr("tools/uv.exe", b"executable")
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    # Use the actual verified download path, prepopulated as a cached asset.
    cached = runtime.data_dir() / "downloads/tool.exe.tar.gz"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(archive.read_bytes())
    result = runtime.install_binary("tool.exe", "https://unused.invalid", expected, "uv.exe", runtime.Task())
    assert result.read_bytes() == b"executable"
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("system,machine,member", [
    ("Linux", "x86_64", "x86_64-unknown-linux-musl"),
    ("Linux", "aarch64", "aarch64-unknown-linux-musl"),
    ("Windows", "AMD64", "x86_64-pc-windows-msvc.exe"),
    ("Darwin", "arm64", "aarch64-apple-darwin"),
])
def test_binary_manifests_select_native_platform(monkeypatch, system, machine, member):
    monkeypatch.setattr(runtime.platform, "system", lambda: system)
    monkeypatch.setattr(runtime.platform, "machine", lambda: machine)
    assert runtime.binary_platform()[1] == member


def test_intel_mac_is_rejected_before_download(monkeypatch):
    monkeypatch.setattr(runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "x86_64")
    with pytest.raises(RuntimeError, match="Apple Silicon"):
        runtime.binary_platform()


def test_passive_codex_resolution_never_downloads_and_reuses_private_install(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOTALK_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(runtime.shutil, 'which', lambda _: None)
    monkeypatch.setattr(runtime, 'download', lambda *a: pytest.fail('Passive startup must not download Codex'))
    assert runtime.ensure_codex(runtime.Task(), install=False) is None
    suffix = '.exe' if runtime.platform.system() == 'Windows' else ''
    cached = tmp_path / 'tools' / f'codex-{runtime.CODEX_VERSION}{suffix}'
    cached.parent.mkdir(); cached.write_bytes(b'cached')
    assert runtime.ensure_codex(runtime.Task(), install=False) == cached
    monkeypatch.setattr(runtime.shutil, 'which', lambda _: str(tmp_path / 'system-codex'))
    assert runtime.ensure_codex(runtime.Task(), install=False) == tmp_path / 'system-codex'


@pytest.mark.parametrize("system,machine,uv_target,codex_target,backend", [
    ("Linux", "x86_64", "x86_64-unknown-linux-gnu", "x86_64-unknown-linux-musl", "vllm"),
    ("Linux", "aarch64", "aarch64-unknown-linux-gnu", "aarch64-unknown-linux-musl", "vllm"),
    ("Windows", "AMD64", "x86_64-pc-windows-msvc", "x86_64-pc-windows-msvc.exe", "torch"),
    ("Darwin", "arm64", "aarch64-apple-darwin", "aarch64-apple-darwin", "mlx"),
])
def test_native_tool_setup_and_speech_backend(monkeypatch, tmp_path, system, machine,
                                            uv_target, codex_target, backend):
    import io
    import re
    import tarfile

    monkeypatch.setenv("AUTOTALK_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(runtime.platform, "system", lambda: system)
    monkeypatch.setattr(runtime.platform, "machine", lambda: machine)
    monkeypatch.setattr(runtime.shutil, "which", lambda _: None)
    suffix = ".exe" if system == "Windows" else ""
    extension = "zip" if system == "Windows" else "tar.gz"
    expected = [(f"uv-{uv_target}.{extension}", "uv" + suffix),
                (f"codex-{codex_target}.{extension}", "codex-" + codex_target)]
    downloads = []

    def download(url, destination, checksum, task):
        filename, member = expected[len(downloads)]
        assert url.endswith("/" + filename)
        assert re.fullmatch("[0-9a-f]{64}", checksum)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if extension == "zip":
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("nested/" + member, member.encode())
        else:
            with tarfile.open(destination, "w:gz") as archive:
                entry = tarfile.TarInfo("nested/" + member)
                entry.size = len(member.encode())
                archive.addfile(entry, io.BytesIO(member.encode()))
        downloads.append(url)
        return destination

    monkeypatch.setattr(runtime, "download", download)
    uv = runtime.ensure_uv(runtime.Task())
    codex = runtime.ensure_codex(runtime.Task())
    assert uv.read_bytes() == ("uv" + suffix).encode()
    assert codex.read_bytes() == ("codex-" + codex_target).encode()
    assert runtime.speech_backend() == backend
    assert runtime.ensure_uv(runtime.Task()) == uv
    assert runtime.ensure_codex(runtime.Task()) == codex
    assert len(downloads) == 2
