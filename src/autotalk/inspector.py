# SPDX-License-Identifier: MIT
"""Slide inspector owns its widgets. Controller access is limited to project,
edit_setting, codex_settings, error, log_message, start_job, voice_context,
configuration_changed, transport (selection/previews), recorder (read-only),
and refresh/request_refresh. Dialog navigation is an explicit signal.
"""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox
from .ui import label, button, combo, column, number, form, disclosure


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
        self.layout().addWidget(label("This slide", "title"))
        self.slide_include = QCheckBox("Include in presentation")
        self.slide_include.toggled.connect(self.include_changed)
        self.layout().addWidget(self.slide_include)
        self.slide_after = combo([("Use talk setting", None), ("Advance automatically", "advance"), ("Pause for live demo", "demo"), ("Wait for presenter", "pause")], self.after_changed)
        self.slide_after_source = label("After this slide")
        self.layout().addWidget(self.slide_after_source)
        self.layout().addWidget(self.slide_after)
        timing = column(margin=0)
        self.slide_budget = number(0, 14400, 0, self.budget_changed, " sec")
        self.slide_budget.setSpecialValueText("Automatic")
        timing.layout().addWidget(self.slide_budget)
        self.inherit_pause = QCheckBox("Use talk pause")
        self.inherit_pause.toggled.connect(self.pause_changed)
        timing.layout().addWidget(self.inherit_pause)
        self.slide_pause = number(0, 10, .6, self.pause_changed, " sec")
        self.slide_pause.setSingleStep(.1)
        form(timing).addRow("Pause after slide", self.slide_pause)
        disclosure(self, "Timing", timing)
        self.layout().addWidget(button("Slide voice && delivery…", lambda: self.open_settings.emit("Voice & language")))
        self.delivery_summary = label("")
        self.layout().addWidget(self.delivery_summary)
        self.layout().addWidget(button("Additional audio…", lambda: self.open_settings.emit("Presentation & recording")))
        self.layout().addWidget(label("Changes here affect only the selected slide."))
        self.layout().addStretch()

    def refresh(self, project, slide):
        with project.pass_cache():
            self.loading = True
            try:
                self.slide_budget.setValue(slide.budget_seconds)
                self.slide_include.setChecked(slide.included)
                source = "app" if project.setting_source("after") == "Application default" else "talk"
                wording = self.slide_after.itemText(self.slide_after.findData(project.setting("after")))
                self.slide_after_source.setText(f"After this slide\nFrom {source}: {wording}")
                self.slide_after.setItemText(0, f"Use {source} setting")
                self.slide_after.setCurrentIndex(self.slide_after.findData(slide.overrides.get("after")))
                self.inherit_pause.setText(f"Use talk pause ({project.setting('pause_seconds'):g} s)")
                self.inherit_pause.setChecked("pause_seconds" not in slide.overrides)
                self.slide_pause.setValue(project.setting("pause_seconds", slide))
                self.slide_pause.setEnabled(self.isEnabled() and not self.inherit_pause.isChecked())
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

    def after_changed(self):
        if not self.loading:
            value = self.slide_after.currentData()
            self.window.edit_setting("after", value, value is None, scope=2, slide=self.window.transport.index)

    def pause_changed(self):
        if not self.loading:
            self.window.edit_setting("pause_seconds", self.slide_pause.value(), self.inherit_pause.isChecked(), scope=2, slide=self.window.transport.index)
