# SPDX-License-Identifier: MIT
"""Native build boundaries: select one Qt distribution before collection."""
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("native_kio", [False, True])
def test_package_collects_local_filesystem_backend(tmp_path, monkeypatch, native_kio):
    from PySide6.QtCore import QLibraryInfo

    worker = tmp_path / "kf6/kio/kio_file.so"
    if native_kio:
        worker.parent.mkdir(parents=True)
        worker.write_bytes(b"local filesystem plugin")
    monkeypatch.setattr(QLibraryInfo, "path", lambda _: str(tmp_path))
    spec = Path(__file__).parents[1] / "packaging/autotalk.spec"

    class AnalysisStarted(Exception):
        pass

    def analyse(*args, **kwargs):
        assert kwargs["binaries"] == ([(str(worker), "PySide6/Qt/plugins/kf6/kio")] if native_kio else [])
        raise AnalysisStarted

    with pytest.raises(AnalysisStarted):
        runpy.run_path(str(spec), init_globals={"SPECPATH": str(spec.parent), "Analysis": analyse})


@pytest.mark.parametrize("qt_version,binding_version,fail_patch", [
    ("6.10.2", "6.10.2", False), ("6.10.2", "6.10.2", True),
    ("6.11.2", "6.10.2", False), ("6.11.2", "6.11.2", False)])
@pytest.mark.skipif(sys.platform != "linux", reason="System Qt collection is a Linux build option")
def test_system_qt_build_requires_matching_bindings(tmp_path, monkeypatch, qt_version, binding_version, fail_patch):
    import platform
    import PySide6
    import tarfile
    from autotalk import runtime

    script = tmp_path / "tools/build.py"
    script.parent.mkdir()
    shutil.copy2(Path(__file__).parents[1] / "tools/build.py", script)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.3.0"\n')
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(PySide6, "__version__", binding_version)
    bindings = tmp_path / "wheel/PySide6"
    (bindings / "Qt/lib").mkdir(parents=True)
    (bindings / "__init__.py").write_text("")
    (bindings / "Qt/lib/libQt6Core.so.6").write_bytes(b"wheel-core")
    (bindings / "Qt/lib/libQt6Pdf.so.6").write_bytes(b"matching-pdf")
    (bindings / "Qt/lib/libQt6Multimedia.so.6").write_bytes(b"wheel-multimedia")
    monkeypatch.setattr(PySide6, "__file__", str(bindings / "__init__.py"))
    monkeypatch.setattr(sys, "argv", [str(script), "--system-qt"])
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    installed = tmp_path / "installed-qt"
    (installed / "plugins").mkdir(parents=True)
    (installed / "translations").mkdir()
    (installed / "libQt6Core.so.6").write_bytes(b"system-core")
    (installed / "libQt6Multimedia.so.6").write_bytes(b"system-multimedia")
    paths = {"QT_VERSION": qt_version, "QT_INSTALL_LIBS": str(installed),
             "QT_INSTALL_PLUGINS": str(installed / "plugins"), "QT_INSTALL_TRANSLATIONS": str(installed / "translations")}
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "\n".join(f"{k}:{v}" for k, v in paths.items()))
    launches = []
    def download(url, archive, checksum, task):
        assert binding_version == qt_version == "6.10.2"
        assert url.endswith('/v6.10.2.tar.gz') and len(checksum) == 64
        source = archive.parent / 'qtmultimedia-6.10.2'; source.mkdir(parents=True)
        with tarfile.open(archive, 'w:gz') as output:
            output.add(source, arcname=source.name)
    monkeypatch.setattr(runtime, 'download', download)

    class CollectionStarted(Exception):
        pass

    def collect(command, **kwargs):
        launches.append((command, kwargs))
        if command[0] == 'patch':
            if fail_patch:
                raise subprocess.CalledProcessError(1, command)
            assert Path(command[-1]).name == 'qt-6.10.2-pipewire-cleanup.patch'
            return
        if command[0] == 'cmake':
            if '--build' in command:
                library = Path(command[2]) / 'lib/libQt6Multimedia.so.6.10.2'
                library.parent.mkdir(parents=True); library.write_bytes(b'patched-multimedia')
            return
        raise CollectionStarted

    monkeypatch.setattr(subprocess, "run", collect)
    if qt_version != binding_version:
        with pytest.raises(SystemExit, match="requires matching PySide6"):
            runpy.run_path(str(script), run_name="__main__")
        assert not launches
        assert not (tmp_path / "build").exists()
    elif fail_patch:
        with pytest.raises(subprocess.CalledProcessError):
            runpy.run_path(str(script), run_name="__main__")
        assert not (tmp_path / "build/system-qt").exists()
        assert not (tmp_path / "dist").exists()
    else:
        with pytest.raises(CollectionStarted):
            runpy.run_path(str(script), run_name="__main__")
        command, options = launches[-1]
        assert command[0] == sys.executable
        staged = Path(options["env"]["PYTHONPATH"].split(os.pathsep)[0]) / "PySide6/Qt"
        assert options["env"]["LD_LIBRARY_PATH"] == str(staged / "lib")
        assert (staged / "lib/libQt6Core.so.6").read_bytes() == b"system-core"
        assert (staged / "lib/libQt6Pdf.so.6").read_bytes() == b"matching-pdf"
        assert (staged / "lib/libQt6Multimedia.so.6").read_bytes() == (b'patched-multimedia' if qt_version == '6.10.2' else b'system-multimedia')
        assert (staged / "plugins").resolve() == installed / "plugins"
        assert (staged / "translations").resolve() == installed / "translations"
        assert not (tmp_path / "dist").exists()  # Collection starts before replacing any bundle.
