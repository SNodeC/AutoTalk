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
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                str(root / "packaging/autotalk.spec")], cwd=root, check=True)
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
