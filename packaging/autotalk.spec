import os
import sys
from pathlib import Path

root = Path(SPECPATH).parent
assets = ["speech_worker.py", "compiler.py", "models.json", "speech-linux.yaml",
          "speech-linux.txt", "speech-windows.txt", "speech-macos.txt"]
a = Analysis([str(root / "tools/entry.py")], pathex=[str(root / "src")],
             datas=[(str(root / "src/autotalk" / name), "autotalk") for name in assets],
             hiddenimports=[], excludes=["tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="autotalk",
          console=sys.platform == "linux", strip=False, upx=False,
          codesign_identity=os.environ.get("AUTOTALK_SIGN_IDENTITY"),
          entitlements_file=str(root / "packaging/entitlements.plist") if sys.platform == "darwin" else None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="autotalk")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="AutoTalk.app", bundle_identifier="org.snodec.autotalk",
                 info_plist={"CFBundleName": "AutoTalk", "CFBundleShortVersionString": "0.2.0",
                             "LSMinimumSystemVersion": "14.0",
                             "NSMicrophoneUsageDescription": "Record a reference of your voice for local speech synthesis.",
                             "NSHighResolutionCapable": True})
