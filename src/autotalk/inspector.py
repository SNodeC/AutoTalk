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
        self.slide_include.toggled.connect(self.slide_policy_changed)
        self.layout().addWidget(self.slide_include)
        self.slide_after = combo([("Use talk setting", None), ("Advance automatically", "advance"), ("Pause for live demo", "demo"), ("Wait for presenter", "pause")], self.slide_policy_changed)
        self.slide_after_source = label("After this slide")
        self.layout().addWidget(self.slide_after_source)
        self.layout().addWidget(self.slide_after)
        timing = column(margin=0)
        self.slide_budget = number(0, 14400, 0, self.slide_policy_changed, " sec")
        self.slide_budget.setSpecialValueText("Automatic")
        timing.layout().addWidget(self.slide_budget)
        self.inherit_pause = QCheckBox("Use talk pause")
        self.inherit_pause.toggled.connect(self.slide_policy_changed)
        timing.layout().addWidget(self.inherit_pause)
        self.slide_pause = number(0, 10, .6, self.slide_policy_changed, " sec")
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
            self.loading = False

    def slide_policy_changed(self):
        if self.loading or not self.window.project:
            return
        slide = self.window.project.slides[self.window.transport.index]
        if not self.slide_include.isChecked() and slide.included and len(self.window.project.included_slides) == 1:
            self.slide_include.setChecked(True)
            self.window.error("Include at least one slide.")
            return
        if slide.budget_seconds != self.slide_budget.value():
            slide.budget_seconds = self.slide_budget.value()
        slide.included = self.slide_include.isChecked()
        after, pause, inherit = self.slide_after.currentData(), self.slide_pause.value(), self.inherit_pause.isChecked()
        index = self.window.transport.index
        self.window.edit_setting("after", after, after is None, scope=2, slide=index)
        self.window.edit_setting("pause_seconds", pause, inherit, scope=2, slide=index)
