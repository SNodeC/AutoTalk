"""Compare native Qt screenshots byte-for-byte at decoded RGBA pixel level."""
import json, sys
from pathlib import Path
import numpy as np
from PySide6.QtGui import QImage
base, current = map(Path, sys.argv[1:3])
rows = []
for path in sorted(current.glob('*.png')):
    original = QImage(str(base/path.name)).convertToFormat(QImage.Format_RGBA8888)
    changed = QImage(str(path)).convertToFormat(QImage.Format_RGBA8888)
    if original.size() != changed.size():
        rows.append({'file': path.name, 'different_size': True})
        continue
    before = np.frombuffer(original.bits(), dtype=np.uint8).reshape(original.height(), original.width(), 4)
    after = np.frombuffer(changed.bits(), dtype=np.uint8).reshape(changed.height(), changed.width(), 4)
    y, x = np.nonzero(np.any(before != after, axis=2))
    rows.append({'file': path.name, 'pixels': len(x),
                 'bbox': [int(x.min()), int(y.min()), int(x.max()), int(y.max())] if len(x) else None})
print(json.dumps(rows, indent=2))
