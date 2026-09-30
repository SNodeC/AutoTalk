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
    ("Windows", "AMD64", "x86_64-pc-windows-msvc.exe"),
    ("Darwin", "arm64", "aarch64-apple-darwin"),
])
def test_binary_manifests_select_native_platform(monkeypatch, system, machine, member):
    monkeypatch.setattr(runtime.platform, "system", lambda: system)
    monkeypatch.setattr(runtime.platform, "machine", lambda: machine)
    assert runtime.binary_platform()[2] == member


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
