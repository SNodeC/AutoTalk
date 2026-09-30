# SPDX-License-Identifier: MIT
"""Reusable delivery presets write only to the shared library."""
import json
import uuid
from dataclasses import asdict
from PySide6.QtWidgets import QWidget,QVBoxLayout,QComboBox,QInputDialog,QMessageBox
from .project import Delivery,SETTING_DEFAULTS,read_settings
from .runtime import data_dir
from .ui import button,row,label

class DeliveryPresets(QWidget):
    def __init__(self,dialog):
        super().__init__()
        self.dialog=dialog
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0,0,0,0)
        self.layout().addWidget(label('Delivery presets are saved to the shared library immediately. They contain delivery directions, not voice identity or synthesis sampling.'))
        self.presets=QComboBox()
        self.layout().addWidget(self.presets)
        self.use_preset_button=button('Use preset',self.use_preset)
        self.layout().addLayout(row(button('Save delivery preset…',self.save_preset),self.use_preset_button))
        self.refresh_presets()

    def refresh_presets(self):
        self.presets.clear()
        for path in sorted((data_dir() / "delivery").glob("*.json")):
            try:
                self.presets.addItem(json.loads(path.read_text(encoding="utf-8"))["name"], path)
            except (OSError, ValueError, KeyError):
                continue

        self.use_preset_button.setEnabled(bool(self.presets.count()))


    def save_preset(self):
        name, accepted = QInputDialog.getText(self, "Save delivery", "Preset name")
        if accepted and name.strip():
            try:
                directory = data_dir() / "delivery"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (uuid.uuid4().hex + ".json")).write_text(json.dumps({
                    "name": name.strip(), "delivery": {k: v for k, v in asdict(self.dialog.voice.voice_context().delivery).items() if k != "sampling"}}, ensure_ascii=False), encoding="utf-8")
                self.refresh_presets()
            except OSError as error:
                QMessageBox.warning(self, "Save preset", str(error))


    def use_preset(self):
        if not self.presets.currentData():
            return
        try:
            value = json.loads(self.presets.currentData().read_text(encoding="utf-8"))["delivery"]
            delivery = Delivery(**(value | {"sampling": {}}))
            settings = {key: delivery.attributes.get(key.split(".")[2], "") if key.startswith("delivery.attributes.") else getattr(delivery, key.split(".")[1])
                        for key in SETTING_DEFAULTS if key.startswith("delivery.") and key != "delivery.sampling"}
            self.dialog.edit_many([(key,value,False) for key,value in read_settings(settings).items() if self.dialog.scope in SETTING_DEFAULTS[key][1]])
        except (OSError, ValueError, TypeError, KeyError) as error:
            QMessageBox.warning(self, "Load preset", str(error))
