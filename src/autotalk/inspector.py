# SPDX-License-Identifier: MIT
"""Slide inspector owns its widgets. Controller access is limited to project,
edit_setting, codex_settings, error, log_message, start_job, voice_context,
configuration_changed, transport (selection/previews), recorder (read-only),
and refresh/request_refresh. Dialog navigation is an explicit signal.
"""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox
from .ui import label, button, column, number, disclosure
from .settings_schema import SCHEMA
from .settings_fields import SettingField
from .settings import inheritance


class InspectorPanel(QWidget):
    open_settings = Signal(str)

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.loading = False
        self.setObjectName("chrome")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 10, 10, 10)
        box.setSpacing(10)
        self.layout().addWidget(label("Slide flow", "title"))
        self.slide_include = QCheckBox("Include in presentation")
        self.slide_include.toggled.connect(self.include_changed)
        self.layout().addWidget(self.slide_include)
        self.after_field = SettingField(SCHEMA['after'], 2, self.edit, compact=True)
        self.slide_after = self.after_field.editor
        self.layout().addWidget(label('After this slide'))
        self.layout().addWidget(self.after_field)
        timing = column(margin=0)
        self.slide_budget = number(0, 14400, 0, self.budget_changed, " sec")
        self.slide_budget.setSpecialValueText("Automatic")
        timing.layout().addWidget(self.slide_budget)
        self.pause_field = SettingField(SCHEMA['pause_seconds'], 2, self.edit, compact=True)
        self.slide_pause = self.pause_field.editor
        timing.layout().addWidget(label('Pause after slide'))
        timing.layout().addWidget(self.pause_field)
        disclosure(self, "Timing", timing)
        self.layout().addWidget(button("Slide sound…", lambda: self.open_settings.emit("Voice & language")))
        self.delivery_summary = label("")
        self.layout().addWidget(self.delivery_summary)
        self.layout().addWidget(button("Additional audio…", lambda: self.open_settings.emit("Audio & recording")))
        self.layout().addWidget(label("Changes here affect only the selected slide."))
        self.layout().addStretch()

    def refresh(self, project, slide):
        with project.pass_cache():
            self.loading = True
            try:
                self.slide_budget.setValue(slide.budget_seconds)
                self.slide_include.setChecked(slide.included)
                for key, field in [('after', self.after_field), ('pause_seconds', self.pause_field)]:
                    field.load(project.setting(key, slide), *inheritance(project, key, 2, slide))
                self.delivery_summary.setText(project.setting("voice", slide).label + "\n" + project.setting_source("voice", slide) + "\n" + ("Reference delivery" if project.setting("voice", slide).source == "Base" else project.setting("delivery.style", slide)))
            finally:
                self.loading = False

    def include_changed(self):
        if self.loading or not self.window.project:
            return
        slide = self.window.project.slides[self.window.transport.index]
        if not self.slide_include.isChecked() and slide.included and len(self.window.project.included_slides) == 1:
            self.refresh(self.window.project, slide)
            self.window.error("Include at least one slide.")
            return
        self.window.configuration_changed(lambda: self.window.project.set_included(slide, self.slide_include.isChecked()), edited=slide.page, inclusion=True)

    def budget_changed(self):
        if not self.loading and self.window.project:
            slide = self.window.project.slides[self.window.transport.index]
            self.window.configuration_changed(lambda: setattr(slide, "budget_seconds", self.slide_budget.value()), edited=slide.page)

    def edit(self, name, value, inherit=False):
        if not self.loading:
            self.window.edit_setting(name, value, inherit, scope=2, slide=self.window.transport.index)
