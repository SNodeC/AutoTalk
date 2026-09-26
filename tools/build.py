"""Build on the target OS. End users launch the resulting native application."""
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
system = platform.system()
machine = platform.machine().lower()
if (system, machine) not in (("Linux", "x86_64"), ("Windows", "amd64"), ("Darwin", "arm64")):
    raise SystemExit("Build on Linux x86_64, Windows x64, or Apple Silicon macOS.")
build_env = os.environ.copy()
if sys.argv[1:] == ["--system-qt"] and system == "Linux":
    from PySide6 import __version__ as binding_version, __file__ as binding_file
    qt = dict(line.split(":", 1) for line in subprocess.check_output(["qtpaths6", "--query"], text=True).splitlines())
    if qt["QT_VERSION"] != binding_version:
        raise SystemExit(f"System Qt {qt['QT_VERSION']} requires matching PySide6; found {binding_version}.")
    native = root / "build" / "system-qt" / "PySide6"
    shutil.copytree(Path(binding_file).parent, native, ignore=shutil.ignore_patterns("Qt", "__pycache__"), dirs_exist_ok=True)
    (native / "Qt/lib").mkdir(parents=True, exist_ok=True)
    for library in Path(binding_file).with_name("Qt").joinpath("lib").glob("libQt6*.so.6"):
        installed = Path(qt["QT_INSTALL_LIBS"]) / library.name
        shutil.copy2(installed if installed.exists() else library, native / "Qt/lib" / library.name)
    for directory, key in (("plugins", "PLUGINS"), ("translations", "TRANSLATIONS")):
        target = native / "Qt" / directory
        target.unlink(missing_ok=True)
        target.symlink_to(qt["QT_INSTALL_" + key], target_is_directory=True)
    build_env.update(PYTHONPATH=os.pathsep.join([str(native.parent), *sys.path]),
                     LD_LIBRARY_PATH=os.pathsep.join(filter(None, (str(native / "Qt/lib"), build_env.get("LD_LIBRARY_PATH")))))
elif sys.argv[1:]:
    raise SystemExit("Usage: build.py [--system-qt (Linux only)]")
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                str(root / "packaging/autotalk.spec")], cwd=root, env=build_env, check=True)
bundle = root / "dist" / ("AutoTalk.app" if system == "Darwin" else "autotalk")
documents = bundle / "Contents/Resources" if system == "Darwin" else bundle
for name in ("README.md", "THIRD_PARTY.md"):
    shutil.copy2(root / name, documents / name)
shutil.copytree(root / "docs", documents / "docs", dirs_exist_ok=True)
base = root / "dist" / f"AutoTalk-{version}-{system.lower()}-{machine}"
if system == "Darwin":
    identity = os.environ.get("AUTOTALK_SIGN_IDENTITY")
    if identity:
        subprocess.run(["codesign", "--force", "--deep", "--options", "runtime", "--timestamp", "--sign", identity,
                        "--entitlements", str(root / "packaging/entitlements.plist"), str(bundle)], check=True)
    archive = Path(str(base) + ".dmg")
    subprocess.run(["hdiutil", "create", "-ov", "-volname", "AutoTalk", "-srcfolder", str(bundle), str(archive)], check=True)
    profile = os.environ.get("AUTOTALK_NOTARY_PROFILE")
    if profile:
        subprocess.run(["xcrun", "notarytool", "submit", str(archive), "--keychain-profile", profile, "--wait"], check=True)
        subprocess.run(["xcrun", "stapler", "staple", str(archive)], check=True)
else:
    if system == "Windows" and os.environ.get("AUTOTALK_SIGN_CERT"):
        command = ["signtool", "sign", "/sha1", os.environ["AUTOTALK_SIGN_CERT"], "/fd", "SHA256"]
        if os.environ.get("AUTOTALK_TIMESTAMP_URL"):
            command += ["/tr", os.environ["AUTOTALK_TIMESTAMP_URL"], "/td", "SHA256"]
        subprocess.run(command + [str(bundle / "autotalk.exe")], check=True)
    archive = Path(shutil.make_archive(str(base), "zip" if system == "Windows" else "gztar", root / "dist", "autotalk"))
with archive.open("rb") as stream:
    checksum = hashlib.file_digest(stream, "sha256").hexdigest()
archive.with_name(archive.name + ".sha256").write_text(checksum + "  " + archive.name + "\n")
print(f"Built {archive}\nApplication: {bundle}")
