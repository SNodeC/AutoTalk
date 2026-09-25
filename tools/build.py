"""Developer release builder; end users run the resulting autotalk executable."""

import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
    "--name", "autotalk", "--paths", str(root / "src"),
    "--add-data", str(root / "src/autotalk/speech_worker.py") + ":autotalk",
    "--add-data", str(root / "src/autotalk/models.json") + ":autotalk",
    "--add-data", str(root / "src/autotalk/speech-requirements.txt") + ":autotalk",
    str(root / "tools/entry.py"),
], cwd=root, check=True)
bundle = root / "dist/autotalk"
shutil.copy2(root / "README.md", bundle / "README.md")
shutil.copy2(root / "THIRD_PARTY.md", bundle / "THIRD_PARTY.md")
shutil.copytree(root / "docs", bundle / "docs", dirs_exist_ok=True)
archive = shutil.make_archive(str(root / "dist/AutoTalk-0.1.0-linux-x86_64"), "gztar",
                              root / "dist", "autotalk")
print(f"Built {archive}\nStart: {bundle / 'autotalk'}")
