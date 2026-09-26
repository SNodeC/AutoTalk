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


@pytest.mark.parametrize("qt_version", ["6.10.2", "6.11.2"])
@pytest.mark.skipif(sys.platform != "linux", reason="System Qt collection is a Linux build option")
def test_system_qt_build_requires_matching_bindings(tmp_path, monkeypatch, qt_version):
    import platform
    import PySide6

    script = tmp_path / "tools/build.py"
    script.parent.mkdir()
    shutil.copy2(Path(__file__).parents[1] / "tools/build.py", script)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.3.0"\n')
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(PySide6, "__version__", "6.10.2")
    bindings = tmp_path / "wheel/PySide6"
    (bindings / "Qt/lib").mkdir(parents=True)
    (bindings / "__init__.py").write_text("")
    (bindings / "Qt/lib/libQt6Core.so.6").write_bytes(b"wheel-core")
    (bindings / "Qt/lib/libQt6Pdf.so.6").write_bytes(b"matching-pdf")
    monkeypatch.setattr(PySide6, "__file__", str(bindings / "__init__.py"))
    monkeypatch.setattr(sys, "argv", [str(script), "--system-qt"])
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    installed = tmp_path / "installed-qt"
    (installed / "plugins").mkdir(parents=True)
    (installed / "translations").mkdir()
    (installed / "libQt6Core.so.6").write_bytes(b"system-core")
    paths = {"QT_VERSION": qt_version, "QT_INSTALL_LIBS": str(installed),
             "QT_INSTALL_PLUGINS": str(installed / "plugins"), "QT_INSTALL_TRANSLATIONS": str(installed / "translations")}
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "\n".join(f"{k}:{v}" for k, v in paths.items()))
    launches = []

    class CollectionStarted(Exception):
        pass

    def collect(command, **kwargs):
        launches.append((command, kwargs))
        raise CollectionStarted

    monkeypatch.setattr(subprocess, "run", collect)
    if qt_version == "6.11.2":
        with pytest.raises(SystemExit, match="requires matching PySide6"):
            runpy.run_path(str(script), run_name="__main__")
        assert not launches
        assert not (tmp_path / "build").exists()
    else:
        with pytest.raises(CollectionStarted):
            runpy.run_path(str(script), run_name="__main__")
        command, options = launches[0]
        assert command[0] == sys.executable
        staged = Path(options["env"]["PYTHONPATH"].split(os.pathsep)[0]) / "PySide6/Qt"
        assert options["env"]["LD_LIBRARY_PATH"] == str(staged / "lib")
        assert (staged / "lib/libQt6Core.so.6").read_bytes() == b"system-core"
        assert (staged / "lib/libQt6Pdf.so.6").read_bytes() == b"matching-pdf"
        assert (staged / "plugins").resolve() == installed / "plugins"
        assert (staged / "translations").resolve() == installed / "translations"
        assert not (tmp_path / "dist").exists()  # Collection starts before replacing any bundle.
