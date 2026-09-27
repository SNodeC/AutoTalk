"""Standalone Qt-only crash reproducer; requires an available audio server."""
import faulthandler

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import QApplication

faulthandler.enable()
app = QApplication([])
devices = QMediaDevices()
devices.audioOutputsChanged.connect(lambda: None)
assert not QMediaDevices.defaultAudioOutput().isNull()
QTimer.singleShot(50, app.quit)
app.exec()
