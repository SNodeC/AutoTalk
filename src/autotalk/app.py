# SPDX-License-Identifier: MIT
"""Qt desktop application. Heavy preparation always runs outside the GUI thread."""

import argparse
import copy
from dataclasses import asdict
from contextlib import closing, nullcontext
from datetime import datetime
import json
import shutil
import signal
import subprocess
import sys
import time
import wave
from functools import partial, wraps
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, Qt, QThread, QTimer, QUrl, Signal, QMicrophonePermission
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import QTableWidgetItem, QApplication, QFileDialog, QInputDialog, QLabel, QMainWindow, QMessageBox, QSizePolicy, QDialog


from .codex import Codex
from .playback import Playback, Presentation
from .project import LANGUAGES, Project, SETTING_DEFAULTS, read_settings, file_hash
from .recording import Recorder
from .runtime import SpeechSession, Cancelled, Task, child_env, data_dir, speech_session, check_model_update
from .services import import_pdf, reload_pdf, install_pdf_reload, narrate, prepare, workflow, speech_config
from .media import RATE, export_prepared, export_recording

def clock(seconds):
    seconds = max(0, round(seconds))
    return f"{seconds//60}:{seconds%60:02d}"


def ui_pass(method):
    @wraps(method)
    def update(self, *args):
        self.flush_refresh()
        with self.project.pass_cache() if self.project else nullcontext():
            return method(self, *args[:method.__code__.co_argcount-1])
    return update


class Job(QThread):
    message = Signal(str)
    detail = Signal(str)
    url = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    event = Signal(object)

    def __init__(self, function, parent):
        super().__init__(parent)
        self.function = function
        self.outcome = "running"
        self.task = Task(self.message.emit, self.url.emit, self.detail.emit, self.event.emit)

    def run(self):
        try:
            result = self.function(self.task)
            self.task.check()
            self.outcome = "completed"
            self.succeeded.emit(result)
        except Cancelled as error:
            self.outcome = "cancelled"
            self.message.emit(str(error))
        except Exception as error:  # noqa: BLE001 - report any worker failure at the UI boundary
            self.outcome = "failed"
            self.failed.emit(str(error))


class SlideImage(QLabel):
    clicked = Signal()

    def __init__(self):
        super().__init__("Open a PDF slide deck to begin")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(160, 100)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.original = QPixmap()

    def show_file(self, path):
        self.original = QPixmap(str(path))
        self.rescale()

    def rescale(self):
        if not self.original.isNull():
            self.setPixmap(self.original.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()) and not self.original.isNull():
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        self.rescale()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = None
        self.project_generation = 0
        self.source_notice = None
        self.source_signature = None
        self.config = QSettings()
        self.defaults = read_settings(json.loads(self.config.value("setting_defaults", "{}")))
        self.speech = SpeechSession(Task(), {})
        self.job = None
        self.job_live = False
        self.job_started = 0
        self.presentation = None
        self.loading = False
        self.close_requested = False
        self.setWindowTitle("AutoTalk")
        self.resize(1100, 850)
        self.setMinimumSize(940, 680)
        self.transport = Playback(self, producer_active=lambda: bool(self.job and self.job_live))
        self.transport.slide_changed.connect(self.show_slide)
        # Audio feeds independently; human-readable timing updates at 4 Hz.
        self.transport.state_changed.connect(self.playback_state_changed)
        self.transport.failed.connect(self.error)
        self.transport.demo_requested.connect(self.live_demo)
        self.transport.finished.connect(lambda: self.log_message("Slides finished — recording continues. End presentation to save the video." if self.transport.capture else "Presentation finished."))
        self.codex_settings = {}
        self.after_job = None
        self.live_autostart = False
        self.pending_exports = []
        self.measurements = {}
        self.transport.recording_ready.connect(self.queue_export)
        self.transport.presentation_ended.connect(self.end_speech_use, Qt.ConnectionType.QueuedConnection)
        self.recorder = Recorder()
        self.record_timer = QTimer(self)
        self.record_timer.setSingleShot(True)
        self.record_timer.timeout.connect(lambda: self.recorder.editor.toggle_recording())
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(250)
        self.elapsed_timer.timeout.connect(self.update_timing)
        self.aggregate_timer = QTimer(self)
        self.aggregate_timer.setSingleShot(True)
        self.aggregate_timer.setInterval(150)
        self.aggregate_timer.timeout.connect(self.refresh_aggregates)
        self._build()
        self.narration.installEventFilter(self)
        self.speech_preferences()
        self.refresh_recordings()
        self.elapsed_timer.start()
        self.refresh()

    def _build(self):
        from .ui import build
        build(self)

    def edit_setting(self, name, value, inherit=False, *, scope=1, slide=None):
        if self.loading or scope not in SETTING_DEFAULTS[name][1]:
            return
        def apply():
            if scope == 0:
                self.defaults.pop(name, None) if inherit else self.defaults.update({name: copy.deepcopy(value)})
                if self.project:
                    self.apply_defaults(self.project)
            elif self.project:
                self.project.set_setting(name, value, self.project.slides[slide] if scope == 2 else None, inherit)
        self.configuration_changed(apply, edited=slide + 1 if scope == 2 else None)

    def begin_settings(self, dialog):
        self.flush_refresh()
        dialog.generation = self.project_generation
        dialog.project = copy.deepcopy(self.project) if dialog.scope else Project(data_dir(), defaults=copy.deepcopy(self.defaults))

    def finish_settings(self, dialog, result):
        if result != QDialog.DialogCode.Accepted:
            if self.recorder.source and self.recorder.editor is dialog.voice:
                self.record_voice(dialog.voice)
            if self.transport.preview_path:
                self.transport.stop()
            return True
        if dialog.generation != self.project_generation:
            dialog.status.setText("The talk changed while this dialog was open. Cancel and reopen settings before saving.")
            return False
        from .settings import apply_edit
        def apply():
            target = Project(data_dir(), defaults=copy.deepcopy(self.defaults)) if dialog.scope == 0 else self.project
            for operation in dialog.operations:
                apply_edit(target, dialog.scope, dialog.slide_index, operation)
            if dialog.scope == 0:
                self.defaults = target.defaults
                self.config.setValue("setting_defaults", json.dumps(self.defaults, default=lambda v: asdict(v)))
                if self.project:
                    self.apply_defaults(self.project)
        before, modified = copy.deepcopy(self.project) if dialog.scope else None, self.isWindowModified()
        try:
            self.configuration_changed(apply, edited=dialog.slide_index+1 if dialog.scope == 2 else None)
        except Exception as error:
            if before is not None:
                self.adopt(before)
                dialog.generation = self.project_generation
            self.setWindowModified(modified)
            dialog.status.setText(f"Could not apply settings: {error}")
            return False
        dialog.generation = self.project_generation
        return True if dialog.scope == 0 else self.save()

    def apply_defaults(self, project):
        project.set_defaults(self.defaults)
        voice = project.defaults.get("voice")
        if voice:
            for ref in voice.references.values():
                if ref.file:
                    source, target = data_dir() / ref.file, project.asset(ref.file)
                    if source.is_file() and source.resolve() != target.resolve():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            shutil.copy2(source, target)

    def event(self, event):
        if event.type() == QEvent.Type.WindowActivate and hasattr(self, "source_notice"):
            QTimer.singleShot(0, self.check_source_pdf)
        result = super().event(event)
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            # Qt resolves palette() in style sheets at polish time.
            stylesheet = self.styleSheet()
            self.setStyleSheet("")
            self.setStyleSheet(stylesheet)
        return result

    def eventFilter(self, watched, event):
        if watched is self.narration and event.type() == QEvent.Type.FocusOut:
            self.flush_refresh()
        return super().eventFilter(watched, event)

    def place_progress(self):
        destination = QApplication.activeModalWidget()
        destination = destination if destination in self.dialogs else self.footer
        if self.progress.parentWidget() != destination:
            destination.layout().insertWidget(destination.layout().count()-2, self.progress)
            self.progress.setVisible(self.job is not None)

    def error(self, message):
        if self.presentation and self.transport.state == "stopped":
            self.stop_presentation()
        self.log_message(message)
        QMessageBox.warning(self, "AutoTalk", message)

    def log_message(self, message):
        self.log.appendPlainText(message)
        self.status.setText(message.splitlines()[-1][:220] if message else "")

    def start_job(self, title, function, callback=None, live=False, preserve_playback=False, *, save_before=True):
        self.flush_refresh()
        if self.job:
            return
        if self.recorder.source:
            self.error("Stop the reference recording before starting another operation.")
            return
        if save_before and not self.save():
            return
        if not preserve_playback and (self.transport.active or self.transport.preview_path):
            self.transport.stop()
        self.log_message(title)
        if not title.startswith(("Saving", "Export")):
            self.measurements = {}
        if not preserve_playback:
            self.slide_progress.setRange(0, len(self.project.included_slides) if self.project else 1)
            self.slide_progress.setValue(0)
        self.progress.setRange(0, 1 if preserve_playback else 0)
        self.progress.setValue(0)
        self.progress.setFormat(title)
        self.progress.show()
        self.job_started = time.monotonic()
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.job_live = live
        self.job = Job(function, self)
        self.job.title = title
        self.job.preserve_playback = preserve_playback
        self.job.task.speech = self.speech
        self.job.message.connect(self.log_message)
        self.job.detail.connect(self.log.appendPlainText)
        self.job.url.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.job.failed.connect(self.job_error)
        self.job.event.connect(lambda value, job=self.job: self.job_event(value) if self.job is job else None)
        if callback:
            self.job.succeeded.connect(callback)
        self.job.finished.connect(self.job_finished)
        self.refresh()
        self.job.start()
        return self.job

    def job_finished(self):
        if self.project:
            try:
                directory = self.project.asset("runs")
                directory.mkdir(exist_ok=True)
                (directory / f"{time.time_ns()}.json").write_text(json.dumps({
                    "operation": self.job.title, "outcome": self.job.outcome,
                    "elapsed": time.monotonic()-self.job_started,
                    "measurements": self.measurements}, indent=2))
            except OSError as error:
                self.log_message(f"Could not save timing summary: {error}")
        if self.job.outcome != "completed":
            self.after_job = None
            self.refresh_recordings()
        self.job.deleteLater()
        self.job = None
        self.job_live = False
        self.progress.hide()
        self.cancel_button.hide()
        self.status.setText("Start reuses current audio and prepares any missing text or speech.")
        self.refresh()
        if self.project:
            self.show_slide(self.transport.index)
        if self.close_requested == "saving" and self.pending_exports:
            self.export_next()
        elif self.close_requested:
            self.close()
        elif self.after_job:
            callback, self.after_job = self.after_job, None
            callback()
        elif self.pending_exports:
            self.export_next()
        else:
            QTimer.singleShot(0, self.check_source_pdf)

    def cancel(self):
        self.live_autostart = False
        if self.job_live and self.transport.active:
            self.transport.pause()
        if self.job:
            self.job.task.cancelled.set()
            if getattr(self.job, "preserve_playback", False):
                self.speech.request_release()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling…")

    def save(self):
        self.flush_refresh()
        if self.project:
            try:
                self.project.save()
                self.setWindowModified(False)
                self.statusBar().showMessage(f"Saved • {self.project.manifest}")
            except OSError as error:
                self.error(f"Could not save the project: {error}")
                return False
        return True

    def adopt(self, project):
        self.project_generation += 1
        if not self.project or self.project.root != project.root:
            self.source_signature = None
        selected = self.transport.index if self.project and self.project.root == project.root else 0
        self.project = project
        self.apply_defaults(project)
        self.loading = True
        self.slide_list.clear()
        self.slide_list.addItems([f"{s.page:02d}  Slide {s.page}" for s in project.slides])
        for i, slide in enumerate(project.slides):
            self.slide_list.item(i).setIcon(QIcon(str(project.image(slide))))
        self.loading = False
        self.workspace.setCurrentWidget(self.quick_page if project.mode == "Quick" else self.editor)
        self.transport.load(project)
        self.transport.select(min(selected, len(project.slides)-1))
        self.refresh()
        self.status.setText("Start reuses current audio and prepares any missing text or speech.")
        self.log.appendPlainText(f"Talk loaded: {project.title}")
        recent = self.config.value("recent_projects", [])
        recent = recent if isinstance(recent, list) else [recent]
        self.config.setValue("recent_projects", [str(project.root)] + [v for v in recent if v != str(project.root)][:9])
        self.refresh_recordings()
        QTimer.singleShot(0, self.check_source_pdf)

    def check_source_pdf(self, *, force=False):
        p = self.project
        if (not p or not p.source_pdf or self.job or self.loading or self.close_requested
                or self.presentation or self.transport.active or self.transport.preview_path
                or self.recorder.source or QApplication.activeModalWidget()):
            return False
        try:
            source = Path(p.source_pdf)
            stat = source.stat()
            signature = (p.source_pdf, stat.st_mtime_ns, stat.st_size)
            if not force and signature == self.source_signature:
                return False
            changed = file_hash(source)
            self.source_signature = signature
        except OSError:
            return False
        notice = (str(p.root), p.source_pdf, changed)
        if changed == p.pdf_hash or notice == self.source_notice:
            return False
        self.source_notice = notice
        dialog = QMessageBox(QMessageBox.Icon.Question, "Source PDF changed",
            "The source PDF has changed. Reload the slides?\n\n"
            "Unchanged slides keep their narration and audio. Changed or new slides need new text and audio. "
            "A backup of this talk will be kept.", parent=self)
        reload_button = dialog.addButton("Reload", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        accepted = dialog.clickedButton() is reload_button
        dialog.deleteLater()
        if accepted:
            self.reload_source_pdf(confirm=False)
            return True
        return False

    def reload_source_pdf(self, confirm=True):
        if not self.project or self.job or self.presentation or self.transport.active or self.recorder.source:
            return
        pdf = Path(self.project.source_pdf) if self.project.source_pdf else None
        if pdf is None or not pdf.is_file():
            name, _ = QFileDialog.getOpenFileName(self, "Locate source PDF", "", "PDF slides (*.pdf)")
            if not name:
                return
            pdf = Path(name)
        if confirm and QMessageBox.question(self, "Reload PDF",
                "Re-read the PDF and recreate all slide images? Unchanged slides keep their narration and audio. "
                "Changed or new slides need new text and audio. A backup of this talk will be kept.") != QMessageBox.StandardButton.Yes:
            return
        def installed(staged):
            try:
                self.adopt(install_pdf_reload(staged))
                self.source_signature = None
                self.log_message(f"PDF reloaded. Previous talk saved in {staged[3]}")
            except OSError as error:
                self.job.outcome = "failed"
                self.error(f"Could not replace the PDF: {error}")
        self.start_job("Reloading PDF…", partial(reload_pdf, copy.deepcopy(self.project), pdf), installed)

    def new_project(self):
        if not self.save():
            return
        pdf, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF slides (*.pdf)")
        if not pdf:
            return
        base = Path(pdf).parent / "autotalk" / (Path(pdf).stem + "-AutoTalk")
        destination = base
        index = 2
        while destination.exists():
            destination = base.with_name(f"{base.name}-{index}")
            index += 1
        def imported(project):
            self.apply_defaults(project)
            self.adopt(project)
            if project.mode != "Quick":
                self.after_job = lambda: self.settings[1].show_section("Talk")
        self.start_job("Importing PDF…", lambda task: import_pdf(Path(pdf), destination, task), imported)

    def open_project(self, path=None):
        if not self.save():
            return
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open saved talk", "", "AutoTalk project (*.autotalk.json)")
        if path:
            self.start_job("Opening talk…", lambda task: Project.load(Path(path)), self.adopt)

    def details_changed(self, *_):
        if self.loading or not self.project:
            return
        p = self.project
        value = self.minutes.value()
        changed = p.target_minutes != value
        self.configuration_changed(lambda: setattr(p, "target_minutes", value))
        if changed:
            self.log_message("Talk length changed. Existing narration is kept; use Rewrite slide text to replace it.")

    def narration_changed(self):
        if not self.loading and self.project:
            self.setWindowModified(True)
            self.project_generation += 1
            self.project.set_narration(self.project.slides[self.transport.index], self.narration.toPlainText())
            self.aggregate_timer.stop()
            self.transport.stop()
            with self.project.pass_cache():
                self.refresh_editor()
                self.refresh_slide_row(self.transport.index)
            self.request_refresh()

    def select_slide(self, index):
        if not self.loading and index >= 0:
            self.transport.select(index)

    def show_slide(self, index, *, surfaces=True):
        self.flush_refresh()
        if not self.project:
            return
        previous, self.loading = self.loading, True
        slide = self.project.slides[index]
        self.slide_list.setCurrentRow(index)
        self.image.show_file(self.project.image(slide))
        self.play_image.show_file(self.project.image(slide))
        following = next((s for s in self.project.included_slides if s.page > slide.page), slide)
        self.next_image.show_file(self.project.image(following))
        self.next_label.setText("Up next · slide " + str(following.page) if following.page > slide.page else "Last slide")
        text = slide.narration if self.project.text_ready(slide) else ""
        self.presenter_narration.setPlainText(text)
        self.narration.setPlainText(text)
        self.notes.setText(slide.notes)
        self.notes_toggle.setChecked(False)
        self.notes_toggle.setEnabled(bool(slide.notes.strip()))
        self.notes_toggle.setText("AI notes" if slide.notes.strip() else "No AI notes")
        self.loading = previous
        if not surfaces:
            return
        with self.project.pass_cache():
            self.refresh_editor()
            self.refresh_inspector()
            self.refresh_presenter()
            self.refresh_dialogs()
            self.refresh_actions()
            self.update_timing()

    @property
    def editable(self):
        return self.job is None and not self.transport.active and self.presentation is None and not self.recorder.source

    @property
    def authoring(self):
        return bool(self.project and self.editable and self.project.mode != "Quick")

    @property
    def can_play(self):
        p = self.project
        return bool(p and (p.prepared and (not self.job or getattr(self.job, "preserve_playback", False)) or
                          p.mode == "Realtime" and self.job and self.job_live) and not self.recorder.source)

    @ui_pass
    def refresh(self):
        self.refresh_frame()
        self.refresh_header()
        self.refresh_dialogs()
        self.refresh_slide_list()
        self.refresh_editor()
        self.refresh_inspector()
        self.refresh_presenter()
        self.refresh_footer()
        self.refresh_actions()

    @ui_pass
    def refresh_aggregates(self):
        self.refresh_header()
        self.refresh_dialogs()
        self.refresh_presenter()
        self.refresh_footer()
        self.refresh_actions()

    def request_refresh(self):
        self.aggregate_timer.start()

    def flush_refresh(self):
        if self.aggregate_timer.isActive():
            self.aggregate_timer.stop()
            self.refresh_aggregates()


    @ui_pass
    def refresh_frame(self):
        p = self.project
        editable, authoring = self.editable, self.authoring
        for widget in (self.toolbar, self.overview, self.record_footer, self.narration_progress, self.slide_progress):
            widget.setVisible(p is not None)
        self.footer.setVisible(p is not None or self.job is not None)
        self.statusBar().setVisible(p is not None or self.job is not None)
        self.editor.setEnabled(p is not None)
        self.narration.setReadOnly(not authoring)
        for widget in self.authoring_widgets:
            widget.setEnabled(authoring)
        self.quick_page.setEnabled(p is not None and editable)
        self.welcome.setEnabled(editable)
        self.place_progress()
        self.mode.setEnabled(editable)
        for widget in (self.minutes, self.language, self.voice_button, self.presentation_button):
            widget.setEnabled(p is not None and editable)
        self.record.setEnabled(p is not None and editable)
        self.start_button.setEnabled(p is not None)
        for action in self.actions:
            action.setEnabled(editable)
        self.talk_action.setEnabled(p is not None and editable)
        self.reload_pdf_action.setEnabled(p is not None and editable and not self.presentation)
        self.engine_action.setEnabled(True)
        if not p:
            for action, control in self.control_actions:
                action.setEnabled(False)
            for control in (self.play_button, self.continue_button, self.end_button, self.demo_button,
                            self.previous_button, self.next_button, self.editor_previous, self.editor_next, self.preview_button, self.export_button):
                control.setEnabled(False)
            return
        if self.workspace.currentWidget() in (self.editor, self.quick_page):
            self.workspace.blockSignals(True)
            self.workspace.setCurrentWidget(self.quick_page if p.mode == "Quick" else self.editor)
            self.workspace.blockSignals(False)
        self.preparation.setVisible(p.mode != "Quick" and self.workspace.currentWidget() is self.editor)
        self.view_switch.setTabText(0, "Quick" if p.mode == "Quick" else "Editor")
        self.view_switch.blockSignals(True)
        self.view_switch.setCurrentIndex(int(self.workspace.currentWidget() is self.presenter))
        self.view_switch.blockSignals(False)

    @ui_pass
    def refresh_header(self):
        p = self.project
        self.record.blockSignals(True)
        self.record.setChecked(bool(p and p.record_presentation))
        self.record.blockSignals(False)
        if p and self.minutes.value() != p.target_minutes:
            self.minutes.blockSignals(True)
            self.minutes.setValue(p.target_minutes)
            self.minutes.blockSignals(False)
        self.summary.setText(f"Audio {clock(p.total_seconds) if p.prepared else 'not ready'}" if p else "PDF slides → spoken presentation")
        if not p:
            return
        if self.mode.currentText() != p.mode:
            self.mode.blockSignals(True)
            self.mode.setCurrentText(p.mode)
            self.mode.blockSignals(False)
        self.language.blockSignals(True)
        self.language.clear()
        for key, version in p.versions.items():
            language = version.language or p.defaults.get("language", "English")
            self.language.addItem(f"{language} — {version.name}" if version.name and version.name != language else language, key)
        for language in LANGUAGES:
            if language not in {v.language or p.defaults.get("language", "English") for v in p.versions.values()}:
                self.language.addItem(language, language)
        self.language.setCurrentIndex(self.language.findData(p.active_version))
        self.language.insertSeparator(self.language.count())
        self.language.addItem("Language options…", "options")
        self.language.blockSignals(False)
        self.title_label.setText(p.title or "Untitled talk")
        self.setWindowTitle((p.title or "Untitled talk") + "[*] — AutoTalk")
        self.voice_button.setText(p.voice.label + "…")
        self.voice_button.setToolTip(p.setting_source("voice"))
        self.mode.setToolTip(self.mode.currentData(Qt.ItemDataRole.ToolTipRole))
        caption = "Prepare and start" if p.mode == "Prepared" else "Start"
        self.start_button.setText(caption)
        self.start_action.setText(caption)
        self.quick_summary.setText(f"{len(p.included_slides)} slides")

    @ui_pass
    def refresh_dialogs(self):
        p = self.project
        for dialog in self.dialogs:
            dialog.sync(self.editable, self.job)
        self.signin_button.setVisible(p is not None and self.preferences.codex_signin.isEnabled())
        self.update_speech_controls()
        self.fit_action.setEnabled(bool(self.editable and p and all(p.text_ready(s) for s in p.included_slides)))

    @ui_pass
    def refresh_slide_list(self):
        if self.project:
            for index in range(len(self.project.slides)):
                self.refresh_slide_row(index)

    @ui_pass
    def refresh_slide_row(self, index):
        p = self.project
        slide = p.slides[index]
        item = self.slide_list.item(index)
        if item:
            title = next((line.strip() for line in slide.source_text.splitlines() if line.strip() and
                          (len(p.slides) == 1 or not all(line in s.source_text for s in p.slides))), f"Slide {slide.page}")
            item.setText(f"{slide.page:02d}  {title}")
            item.setToolTip(title + "\n" + ("Excluded" if not slide.included else f"Needs {p.setting('language', slide)} narration" if not p.text_ready(slide) else clock(slide.duration) + " audio ready" if p.ready(slide) else "Needs update" if slide.audio_file else "Needs audio"))

    @ui_pass
    def refresh_editor(self):
        p = self.project
        if not p:
            return
        authoring = self.authoring
        slide = p.slides[self.transport.index]
        self.waveform.load(p.audio(slide) if p.audio(slide).is_file() else None)
        self.slide_info.setText(f"Slide {slide.page} of {len(p.slides)} • " +
            (f"Needs {p.setting('language', slide)} narration" if not p.text_ready(slide) else f"Audio ready · {clock(slide.duration)}" if p.ready(slide) else "Audio needs updating" if slide.audio_file else "Needs audio") +
            (f" • Planned {slide.budget_seconds:.0f}s" if slide.budget_seconds else ""))
        self.regenerate_button.setText("Rewrite slide text…" if p.text_ready(slide) else "Create slide text")
        self.preview_button.setText("Stop audio" if self.transport.preview_path else "Play previous audio" if slide.audio_file and not p.ready(slide) else "Play audio")
        self.preview_action.setText(self.preview_button.text())
        self.regenerate_action.setText(self.regenerate_button.text())
        self.slide_audio_button.setEnabled(authoring and slide.included and p.text_ready(slide))
        self.preview_button.setEnabled(authoring and p.audio(slide).is_file())

    @ui_pass
    def refresh_inspector(self):
        p = self.project
        if not p:
            return
        self.inspector.refresh(p, p.slides[self.transport.index])

    @ui_pass
    def refresh_presenter(self):
        p = self.project
        if not p:
            return
        editable, can_play = self.editable, self.can_play
        finished = self.transport.state == "finished"
        self.duration_label.setText(("Slides finished — recording continues" if self.transport.capture else "Presentation finished") if finished else f"{clock(p.total_seconds)} prepared  /  {clock(p.target_minutes*60)} target")
        self.slide_list.setEnabled(editable or can_play)
        self.play_button.setEnabled(can_play and self.transport.playing)
        self.more_presentation.setEnabled(can_play and self.presentation is None)
        self.continue_button.setEnabled(can_play and self.presentation is None and self.transport.state == "paused" and not self.transport.preview_path)
        self.play_button.setVisible(self.transport.playing)
        self.continue_button.setVisible(can_play and self.transport.state == "paused")
        self.demo_button.setEnabled(can_play and self.transport.active)
        self.end_button.setEnabled(self.transport.active or self.workspace.currentWidget() is self.presenter)
        self.end_button.setText("End presentation and save video" if self.transport.capture else "End presentation" if self.transport.active else "Return to editing")
        self.end_action.setText(self.end_button.text())
        if self.end_button.property("primary") != finished:
            self.end_button.setProperty("primary", finished)
            self.end_button.style().polish(self.end_button)
        stopped = self.transport.state in ("stopped", "finished") and not self.presentation
        for direction, editor, presenter in ((-1, self.editor_previous, self.previous_button), (1, self.editor_next, self.next_button)):
            editor.setEnabled((editable or can_play) and self.transport.neighbour(direction, False) is not None)
            presenter.setEnabled((editable or can_play if stopped else can_play) and self.transport.neighbour(direction) is not None)

    @ui_pass
    def refresh_footer(self):
        p = self.project
        if not p:
            return
        self.narration_progress.setRange(0, len(p.included_slides))
        self.narration_progress.setValue(sum(p.text_ready(s) for s in p.included_slides))
        self.narration_progress.setFormat("Text ready: %v / %m")
        ready = sum(p.ready(s) for s in p.included_slides)
        if self.job is None:
            self.slide_progress.setRange(0, len(p.included_slides))
            self.slide_progress.setValue(ready)
            self.slide_progress.setFormat("Prepared slides: %v / %m")
        self.update_timing()

    @ui_pass
    def refresh_actions(self):
        p = self.project
        if not p:
            self.previous_action.setEnabled(False)
            self.next_action.setEnabled(False)
            return
        editable, authoring = self.editable, self.authoring
        self.talk_text_button.setEnabled(authoring and any(not p.text_ready(s) for s in p.included_slides))
        self.talk_audio_button.setEnabled(authoring and all(p.text_ready(s) for s in p.included_slides))
        self.export_button.setEnabled(editable and p.prepared)
        for action, control in self.control_actions:
            action.setEnabled(control.isEnabled())
        for action, editor, presenter in ((self.previous_action, self.editor_previous, self.previous_button), (self.next_action, self.editor_next, self.next_button)):
            action.setEnabled(self.workspace.currentWidget() is not self.quick_page and (presenter if self.workspace.currentWidget() is self.presenter else editor).isEnabled())


    @ui_pass
    def update_timing(self):
        if not hasattr(self, "play_time"):
            return
        self.update_speech_controls()
        capture = self.transport.capture
        self.record.setToolTip("Recording source: " + ("Screen + system audio" if self.project and self.project.recording_source == "screen" else "Slide video + narration") + ". Configure it in Presentation settings → Recording.")
        total = self.transport.total_seconds
        elapsed = self.transport.elapsed
        remaining = clock(total-elapsed) if self.transport.complete else "estimating…"
        self.play_time.setText(f"{self.transport.state.capitalize()} • Elapsed {clock(elapsed)}" + ("" if self.transport.state == "finished" else f" • Remaining {remaining}"))
        duration = self.project.slides[self.transport.index].duration if self.project and len(self.waveform.peaks) else 0
        self.preview_time.setText(f"{clock(self.transport.position)} / {clock(duration)}")
        self.waveform.progress = min(1, self.transport.position / duration) if duration else 0
        self.waveform.update()
        if capture:
            recording = "Waiting for screen sharing…" if not getattr(capture, "ready", True) else ("Slides finished — recording continues" if self.transport.state == "finished" else "● Recording") + " · " + clock(capture.frames / RATE)
        elif self.pending_exports or self.job and self.job.title.startswith(("Saving", "Export")):
            recording = "Saving video…"
        else:
            recording = ""
        output = ""
        if self.output_button.isEnabled() and Path(self.output_path).is_file():
            date = datetime.fromtimestamp(Path(self.output_path).stat().st_mtime).strftime("%d %b, %H:%M")
            output = f'Saved {date}: <a href="video">Open video / audio</a> · <a href="folder">Open folder</a>'
        self.saved_output.setText(output)
        self.saved_output.setVisible(bool(output))
        self.record_status.setText(recording)
        self.record_status.setVisible(bool(recording))
        if self.job:
            elapsed = clock(time.monotonic()-self.job_started)
            self.statusBar().showMessage(f"Operation elapsed: {elapsed}")
            for dialog in self.dialogs:
                dialog.status.setText(f"{self.status.text()} · Waiting {elapsed}")

    def playback_state_changed(self):
        if self.job_live and self.transport.state == "playing":
            self.measurements.setdefault("First playback", time.monotonic()-self.job_started)
        if not self.loading:
            self.refresh()

    def connect_chatgpt(self, *, interactive=True, sign_out=False):
        def connect(task):
            try:
                with closing(Codex(task, interactive=interactive and not sign_out)) as client:
                    client.connect(sign_out=sign_out)
            except Exception as error:
                task.check()
                if interactive:
                    raise
                task.event({"type": "codex_settings", "account": f"Codex check unavailable: {error} Restart AutoTalk to retry."})
        self.start_job("Signing out of ChatGPT…" if sign_out else "Connecting to ChatGPT…" if interactive else "Checking existing ChatGPT sign-in…", connect, save_before=False)

    def create_narration(self, rewrite=False):
        if self.check_source_pdf(force=True):
            return
        if not self.project:
            return
        pages = [s.page for s in self.project.included_slides if rewrite or not self.project.text_ready(s)]
        if not pages:
            return
        if (rewrite
                and QMessageBox.question(self, "Rewrite all talk text?", f"Rewrite all included slides in {(self.project.version.name or self.project.language)}? This replaces your edits in that language version.") != QMessageBox.StandardButton.Yes):
            return
        def done(project):
            self.adopt(project)
            self.workspace.setCurrentWidget(self.editor)
            self.log_message("Talk text is ready to review.")
        self.start_job("Writing talk text…", partial(narrate, copy.deepcopy(self.project), pages=pages), done)

    def prepare_talk(self):
        if self.check_source_pdf(force=True):
            return
        self.start_job("Preparing talk audio…", partial(prepare, copy.deepcopy(self.project)), self.accept_result)

    def fit_duration(self):
        if self.check_source_pdf(force=True):
            return
        if QMessageBox.question(self, "Fit duration", "AutoTalk will revise your talk text and regenerate audio, up to three times, using your Codex allowance. Continue?") != QMessageBox.StandardButton.Yes:
            return
        self.start_job("Fitting the talk to its duration…", partial(prepare, copy.deepcopy(self.project), fit=True), self.accept_result)

    def present(self, resume=False, selected=False):
        self.flush_refresh()
        if self.presentation or not self.project:
            return
        if not self.project.prepared and not (self.project.mode == "Realtime" and self.job and self.job_live):
            return
        if self.project.mode == "Quick" and self.project.quick_timing == "require" and not self.project.within_target:
            self.log_message("Quick timing requires a duration match. Use Fit duration or change Quick timing policy in Talk settings → Preparation & timing.")
            return
        if not self.job and not self.save():
            return
        if not resume and not selected:
            self.transport.select(self.project.included_slides[0].page-1)
        self.live_autostart = False
        self.presentation = Presentation(self.transport, self.previous_action, self.next_action, self.end_action)
        screens = QApplication.screens()
        screen = screens[min(self.preferences.screen.currentIndex(), len(screens)-1)]
        self.presentation.setScreen(screen)
        self.presentation.setGeometry(screen.geometry())
        self.presentation.closed.connect(self.presentation_closed)
        self.workspace.setCurrentWidget(self.presenter)
        self.transport.fullscreen = True
        self.presentation.showFullScreen()
        self.transport.play()
        if not resume and self.config.value("gpu_loading", "needed") == "start":
            self.load_gpu()
        self.refresh()

    def presentation_closed(self):
        self.presentation.deleteLater()
        self.presentation = None
        self.live_autostart = False
        self.refresh()

    def continue_presentation(self):
        self.present(resume=True)

    def restart_presentation(self):
        self.transport.stop()
        self.present()

    def stop_presentation(self):
        self.live_autostart = False
        if self.job and self.job_live:
            self.cancel()
        if self.presentation:
            self.presentation.close()
        self.transport.stop()
        if not self.transport.capture:
            self.workspace.setCurrentWidget(self.quick_page if self.project and self.project.mode == "Quick" else self.editor)
        self.refresh()

    def configuration_changed(self, mutation=lambda: None, *, edited=None, inclusion=False):
        if self.loading:
            return
        self.flush_refresh()
        p = self.project
        self.loading = True
        try:
            with p.pass_cache() if p else nullcontext():
                before = {s.page: p.pause_after(s) for s in p.included_slides if p.ready(s)} if p else {}
                mutation()
                self.project_generation += 1
                self.transport.stop()
                self.transport.refresh_audio()
                if p:
                    self.setWindowModified(True)
                    self.show_slide(self.transport.index, surfaces=False)
                self.refresh()
                stale = [s for s in p.included_slides if s.page != edited and s.page in before and not p.ready(s)] if p else []
                if stale:
                    pages = ", ".join(str(s.page) for s in stale[:3]) + (f" and {len(stale)-3} more" if len(stale) > 3 else "")
                    cause = ": trailing pause changed after changing the included slides." if inclusion and all(before[s.page] != p.pause_after(s) for s in stale) else " after this change."
                    self.log_message(f"Slide{'s' if len(stale) > 1 else ''} {pages} audio needs updating" + cause)
        finally:
            self.loading = False

    def mode_changed(self, value):
        self.edit_setting("mode", value)

    def navigate_slide(self, direction):
        presenter = self.workspace.currentWidget() is self.presenter
        control = (self.previous_button if direction < 0 else self.next_button) if presenter else (self.editor_previous if direction < 0 else self.editor_next)
        if QApplication.activeModalWidget() or not control.isEnabled() or self.workspace.currentWidget() is self.quick_page:
            return
        index = self.transport.neighbour(direction, presenter)
        if index is not None:
            self.transport.select(index, play=self.transport.playing) if presenter else self.slide_list.setCurrentRow(index)

    def start_mode(self):
        self.flush_refresh()
        if self.check_source_pdf(force=True):
            return
        if not self.project:
            return
        if self.recorder.source:
            self.log_message("Stop voice recording before starting the presentation.")
            return
        if self.transport.state == "finished":
            self.stop_presentation()
        if self.presentation:
            self.presentation.raise_()
            self.transport.play()
        elif self.job and not (self.project.prepared and getattr(self.job, "preserve_playback", False)):
            if self.job_live:
                self.live_autostart = True
                self.start_when_buffered()
            else:
                self.after_job = self.start_mode
                self.log_message("Presentation will start" + (", including a new recording," if self.project.record_presentation else "") + " after " + ("saving the video" if self.job.title.startswith(("Saving", "Export")) else "the current operation") + " finishes.")
        elif self.project.prepared:
            self.present(resume=self.transport.state == "paused")
        else:
            self.prepare_and_present()

    def prepare_and_present(self):
        if self.transport.state != "paused":
            self.transport.select(self.project.included_slides[0].page-1)
        else:
            self.log_message("Resuming preparation; an unfinished slide restarts from its beginning.")
        snapshot = copy.deepcopy(self.project)
        self.live_autostart = snapshot.mode == "Realtime"
        def done(result):
            self.accept_result(result)
            if result.mode != "Realtime":
                self.after_job = self.present
            elif result.mode == "Realtime" and self.live_autostart:
                self.after_job = partial(self.present, resume=True)
        self.start_job("Preparing " + snapshot.mode + " presentation…", partial(workflow, snapshot), done,
                       live=snapshot.mode == "Realtime")
        self.start_when_buffered()

    def start_when_buffered(self):
        if self.live_autostart and self.job and self.job_live:
            buffered = self.transport.buffered_seconds
            if buffered >= self.transport.required_buffer or (self.transport.complete and buffered > 0):
                self.present(resume=True)

    def accept_result(self, project):
        self.project_generation += 1
        if self.transport.active or self.presentation:
            self.project = self.transport.project = project
            self.transport.refresh_audio()
            self.show_slide(self.transport.index)
        else:
            self.adopt(project)
        self.refresh()

    def job_error(self, message):
        self.close_requested = False
        self.live_autostart = False
        if self.transport.active and not getattr(self.job, "preserve_playback", False):
            self.transport.pause()
        self.error(message)

    def job_event(self, value):
        if self.job is None:
            return
        kind = value.get("type")
        if kind == "codex_settings":
            self.codex_settings.update(value)
        elif kind in ("progress", "model_progress"):
            model = kind == "model_progress"
            progress = self.progress if model else self.narration_progress if value["stage"] == "Narration" else self.slide_progress
            completed, total, unit = value.get("completed", 0), value.get("total"), value.get("unit", "")
            scale = 2**20 if unit == "bytes" else 1
            progress.setRange(0, max(1, min(int(total or 1), 2**31-1)))
            progress.setValue(int(completed * progress.maximum() // total) if total else 0)
            counts = f"{completed} / {total} {unit}" if total else "Progress not reported"
            if unit == "bytes":
                counts = f"{completed/scale:.1f} / {total/scale:.1f} MiB" if total else f"{completed/scale:.1f} MiB · total unknown"
            counts = value.get("detail") or counts
            progress.setFormat(value["stage"] + (" · " + counts if unit or not total else "") if model else value["stage"] + ": %v / %m")
        elif kind == "measurement":
            stage = value["stage"]
            self.measurements[stage] = self.measurements.get(stage, 0) + value["seconds"]
            if value.get("audio_seconds"):
                self.measurements["Audio produced"] = self.measurements.get("Audio produced", 0) + value["audio_seconds"]
            text = " • ".join(f"{stage}: {seconds:.1f}s" for stage, seconds in self.measurements.items())
            generated = self.measurements.get("Audio produced", 0)
            cost = self.measurements.get("Speech", 0)
            if generated and cost and self.project:
                remaining = max(0, self.project.target_minutes*60-self.project.total_seconds)
                text += f" • Speech {generated/cost:.2f}× realtime • Estimated remaining synthesis {remaining*cost/generated:.0f}s"
            self.log.appendPlainText(text)
        elif self.project and value.get("version") == self.project.active_version:
            if kind == "voice":
                self.project.voice = value["voice"]
                self.adopt(self.project)
            elif kind == "narration":
                self.project.title = value["title"]
                for slide in value["slides"]:
                    self.project.slides[slide.page-1] = slide
                    self.transport.refresh_audio(slide.page-1)
                self.show_slide(self.transport.index)
                self.refresh()
            elif kind == "slide_ready":
                slide = value["slide"]
                if slide.audio_key == self.project.speech_key(slide):
                    self.project.slides[slide.page-1] = slide
                    self.transport.refresh_audio(slide.page-1)
                    self.refresh()
            elif kind == "audio":
                self.measurements.setdefault("First audio", time.monotonic()-self.job_started)
                self.transport.receive_audio(value)
            self.start_when_buffered()

    def insert_passage(self):
        language, ok = QInputDialog.getItem(self, "Insert language passage", "Language", LANGUAGES, editable=False)
        if ok and self.project:
            self.narration.insertPlainText("\n\n[" + language + "] ")
            self.narration.setFocus()

    def regenerate_slide(self):
        if self.check_source_pdf(force=True):
            return
        if not self.project:
            return
        page = self.transport.index + 1
        if self.project.text_ready(self.project.slides[page-1]) and QMessageBox.question(self, "Rewrite slide", f"Replace slide {page} text in {self.project.setting('language', self.project.slides[page-1])}? Other slides and language versions will be preserved.") != QMessageBox.StandardButton.Yes:
            return
        def ready(project):
            self.adopt(project)
            self.transport.select(page-1)
        self.start_job(f"Writing slide {page} text…", partial(narrate, copy.deepcopy(self.project), pages=[page]), ready)

    def prepare_slide(self):
        if self.check_source_pdf(force=True):
            return
        if not self.project:
            return
        slide = self.project.slides[self.transport.index]
        if not self.project.text_ready(slide):
            return
        page = slide.page
        def ready(project):
            self.adopt(project)
            self.transport.select(page-1)
            self.preview_slide()
        self.start_job(f"Preparing slide {page} audio…", partial(prepare, copy.deepcopy(self.project), pages=[page], force=True), ready)

    def preview_slide(self):
        if self.transport.preview_path:
            self.transport.stop()
        elif self.project and self.project.audio(self.project.slides[self.transport.index]).is_file():
            self.transport.preview(self.project.audio(self.project.slides[self.transport.index]))

    def live_demo(self):
        self.transport.pause()
        if self.presentation:
            self.presentation.close()
        self.workspace.setCurrentWidget(self.presenter)
        self.log_message("Narration paused for a live demo. Continue presentation when ready." +
                         (" Screen recording continues." if self.project.recording_source == "screen" and self.transport.capture else ""))

    def save_as(self):
        if not self.project or not self.save():
            return
        parent = QFileDialog.getExistingDirectory(self, "Save a copy of this talk in…")
        if parent:
            destination = Path(parent) / (self.project.root.name + "-copy")
            def copy_project(task):
                shutil.copytree(self.project.root, destination)
                return Project.load(destination / "talk.autotalk.json")
            self.start_job("Saving a copy…", copy_project, self.adopt)

    def find_narration(self):
        text, ok = QInputDialog.getText(self, "Find in slide text", "Text to find")
        if ok and text and not self.narration.find(text):
            self.narration.moveCursor(self.narration.textCursor().MoveOperation.Start)
            self.narration.find(text)

    def open_talk_folder(self):
        if self.project:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project.root)))

    def record_voice(self, dialog):
        try:
            if self.recorder.source:
                self.record_timer.stop()
                path = self.recorder.stop(data_dir() / "recording.wav")
                dialog.record_button.setText("Record my voice")
                self.refresh()
                dialog.set_voice(path)
            else:
                permission = QMicrophonePermission()
                application = QApplication.instance()
                status = application.checkPermission(permission)
                if status == Qt.PermissionStatus.Undetermined:
                    application.requestPermission(permission, dialog, lambda _: dialog.toggle_recording())
                    return
                if status == Qt.PermissionStatus.Denied:
                    raise RuntimeError("Allow microphone access for AutoTalk in system privacy settings, or import a reference recording.")
                self.transport.stop()
                self.recorder.editor = dialog
                self.recorder.start()
                dialog.record_button.setText("Stop recording")
                self.refresh()
                self.record_timer.start(30000)
        except (RuntimeError, OSError, ValueError, wave.Error) as error:
            self.record_timer.stop()
            dialog.record_button.setText("Record my voice")
            self.refresh()
            self.error(str(error))


    def system_audio_settings(self):
        import shutil
        if sys.platform == "win32":
            QDesktopServices.openUrl(QUrl("ms-settings:apps-volume"))
        elif sys.platform == "darwin":
            QDesktopServices.openUrl(QUrl("x-apple.systempreferences:com.apple.Sound-Settings.extension"))
        else:
            choices = [("systemsettings", "kcm_pulseaudio"), ("gnome-control-center", "sound"), ("pavucontrol",)]
            for command in choices:
                executable = shutil.which(command[0])
                if executable:
                    subprocess.Popen([executable, *command[1:]], env=child_env(), start_new_session=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
            self.error("Open your desktop's Sound settings to choose AutoTalk's audio output.")

    def test_audio(self):
        import numpy as np
        path = data_dir() / "test-output.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        samples = (np.sin(np.arange(24000) * (2*np.pi*440/24000)) * 3000).astype("<i2")
        samples[:480] = (samples[:480] * np.linspace(0, 1, 480)).astype("<i2")
        samples[-480:] = (samples[-480:] * np.linspace(1, 0, 480)).astype("<i2")
        with wave.open(str(path), "wb") as output:
            output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            output.writeframes(samples.tobytes())
        self.transport.preview(path)

    def queue_export(self, root):
        self.pending_exports.append(root)
        if not self.job and not self.close_requested:
            QTimer.singleShot(0, self.export_next)

    def export_next(self):
        if self.job or self.transport.active or not self.pending_exports or self.close_requested is True:
            return
        root = self.pending_exports.pop(0)
        self.start_job("Saving presentation video…", partial(export_recording, root),
                       self.export_saved)

    def refresh_recordings(self):
        selected = self.recordings.item(self.recordings.currentRow(), 0)
        selected = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        self.recordings.setRowCount(0)
        roots = [str(self.project.root)] if self.project else self.config.value("recent_projects", [])
        for root in roots if isinstance(roots, list) else [roots]:
            for path in sorted(Path(root).glob("recordings/*/session.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    info = json.loads(path.read_text())
                    size = (path.parent / "audio.pcm").stat().st_size
                    if not size:
                        continue
                    title = info.get("title") or (self.project.title if self.project and self.project.root == Path(root) else Path(root).name)
                    date = datetime.fromtimestamp(info.get("started_at", path.stat().st_mtime)).strftime("%d %b %Y, %H:%M")
                    duration = size / (2 * info.get("channels", 1) * info.get("rate", 24000))
                    ready = bool(info.get("output") and Path(info["output"]).is_file())
                    row = self.recordings.rowCount()
                    self.recordings.insertRow(row)
                    for col, text in enumerate((title, date, clock(duration), "Ready" if ready else "Needs saving")):
                        item = QTableWidgetItem(text)
                        item.setData(Qt.ItemDataRole.UserRole, str(path))
                        self.recordings.setItem(row, col, item)
                except (OSError, ValueError):
                    continue
        self.recordings.selectRow(next((row for row in range(self.recordings.rowCount())
            if self.recordings.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected), 0))
        self.recordings.resizeRowsToContents()
        self.recordings_empty.setVisible(not self.recordings.rowCount())
        self.recording_selected()

    def recording_selected(self):
        item = self.recordings.item(self.recordings.currentRow(), 0)
        try:
            info = json.loads(Path(item.data(Qt.ItemDataRole.UserRole)).read_text()) if item else {}
            self.output_path = info.get("output", "")
        except (OSError, ValueError):
            self.output_path = ""
        self.recover_button.setEnabled(item is not None)
        for button in (self.output_button, self.folder_button):
            button.setEnabled(bool(self.output_path and Path(self.output_path).is_file()))
        self.recover_button.setText("Save another format…" if self.output_button.isEnabled() else "Save unfinished recording…")

    def recover_recording(self):
        item = self.recordings.item(self.recordings.currentRow(), 0)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        destination, _ = QFileDialog.getSaveFileName(self, "Save recording", "presentation.mp4", "Video (*.mp4);;WAV audio (*.wav);;M4A audio (*.m4a)")
        if destination:
            self.start_job("Exporting recording…", partial(export_recording, Path(path).parent, destination=destination), self.export_saved)

    def language_selected(self, *_):
        if self.loading or not self.project:
            return
        value = self.language.currentData()
        if value == "options":
            self.refresh()
            self.settings[1].show_section("Voice & language", focus=self.settings[1].fields["language_policy"].editor)
        else:
            if value in self.project.versions:
                self.configuration_changed(lambda: self.project.activate_version(value))
            else:
                self.edit_setting("language", value)
            self.save()

    def speech_preferences(self, save=False):
        for name, default in (("gpu_loading", "needed"), ("gpu_retention", "session")):
            group = getattr(self.preferences, name)
            if save:
                self.config.setValue(name, group.checkedButton().property("value"))
            else:
                value = self.config.value(name, default)
                next((b for b in group.buttons() if b.property("value") == value), group.buttons()[0]).setChecked(True)
        policy = self.config.value("gpu_retention", "session")
        if self.speech.retention != policy:
            self.speech.set_retention(policy)
        self.update_speech_controls()

    def selected_speech_config(self):
        return speech_config(self.project, self.project.slides[self.transport.index]) if self.project else speech_config(Project(data_dir(), defaults=copy.deepcopy(self.defaults)))

    def update_speech_controls(self):
        try:
            config = self.selected_speech_config()
        except ValueError:
            config = None
        dialog = self.preferences
        description = dialog.sync_engine(self.speech, config, self.job)
        self.engine_status.setText("Speech engine: " + description.removesuffix("…") + "…")
        self.load_gpu_action.setEnabled(dialog.load_gpu_button.isEnabled())
        self.unload_gpu_action.setEnabled(dialog.unload_gpu_button.isEnabled())

    def load_gpu(self):
        if self.job:
            return
        try:
            config = self.selected_speech_config()
        except ValueError as error:
            self.error(str(error))
            return
        if self.speech.matches(config) and not self.speech.release_requested:
            return
        def load(task):
            with speech_session(task, config, preload=True):
                pass
        self.start_job("Loading speech model…", load, preserve_playback=True, save_before=False)

    def check_model_updates(self):
        if not self.preferences.check_model_button.isEnabled():
            return
        spec = self.selected_speech_config()["model"]
        def checked(latest):
            message = ("This AutoTalk model matches the latest upstream revision." if latest == spec["revision"] else
                       "A different upstream revision is available. To use a newer model, install an AutoTalk release that includes its verified revision.")
            QMessageBox.information(self, "Model update check", f"{spec['repo']}\n\n{message}\n\nAutoTalk revision: {spec['revision']}\nUpstream revision: {latest}\n\nThis check does not download or replace model files.")
        self.start_job("Checking model updates…", partial(check_model_update, spec), checked, save_before=False)

    def release_gpu(self):
        if not self.speech.guard.locked() and self.speech.process:
            self.speech.request_release()
            self.update_speech_controls()

    def end_speech_use(self):
        if not self.close_requested and not self.transport.active and self.speech.retention == "presentation":
            if getattr(self.job, "preserve_playback", False):
                self.cancel()
            else:
                self.speech.request_release()

    def export_talk(self):
        destination, _ = QFileDialog.getSaveFileName(self, "Export prepared talk", "presentation.mp4", "Video (*.mp4);;WAV audio (*.wav);;M4A audio (*.m4a)")
        if destination:
            self.start_job("Exporting prepared talk…", partial(export_prepared, copy.deepcopy(self.project), destination=destination), self.export_saved)

    def export_saved(self, path):
        self.log_message("Saved: " + str(path))
        self.refresh_recordings()
        for row in range(self.recordings.rowCount()):
            info = json.loads(Path(self.recordings.item(row, 0).data(Qt.ItemDataRole.UserRole)).read_text())
            if info.get("output") == str(Path(path).resolve()):
                self.recordings.selectRow(row)
                break
        self.output_path = str(Path(path).resolve())
        for button in (self.output_button, self.folder_button):
            button.setEnabled(Path(path).is_file())
        self.update_timing()

    def closeEvent(self, event):
        self.flush_refresh()
        if not self.close_requested and (self.transport.capture or self.pending_exports or (self.job and self.job.title.startswith(("Saving", "Export")))):
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Save presentation")
            dialog.setText("A recording or export is unfinished.")
            finish = dialog.addButton("Finish saving and close", QMessageBox.ButtonRole.AcceptRole)
            later = dialog.addButton("Close and save later", QMessageBox.ButtonRole.DestructiveRole)
            dialog.addButton(QMessageBox.StandardButton.Cancel)
            dialog.exec()
            if dialog.clickedButton() not in (finish, later):
                event.ignore()
                return
            self.close_requested = "saving" if dialog.clickedButton() == finish else True
            if self.job_live:
                self.cancel()
            self.transport.stop()
            if self.transport.capture:
                self.close_requested = False
                event.ignore()
                return
        if self.close_requested == "saving":
            if not self.job and self.pending_exports:
                self.export_next()
            if self.job:
                event.ignore()
                return
        self.close_requested = True
        if self.job:
            self.cancel()
            event.ignore()
            return
        if self.recorder.source:
            self.recorder.editor.toggle_recording()
        if self.presentation:
            self.presentation.close()
        self.transport.stop()
        if self.transport.capture:
            self.close_requested = False
            event.ignore()
            return
        if self.save():
            self.transport.close()
            self.speech.release()
            event.accept()
        else:
            self.close_requested = False
            event.ignore()


def main():
    parser = argparse.ArgumentParser(description="AutoTalk — timed PDF presentations in your own voice")
    parser.add_argument("project", nargs="?", help="Saved talk.autotalk.json to open")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("AutoTalk")
    app.setOrganizationName("SNodeC")
    window = MainWindow()
    signal.signal(signal.SIGINT, lambda *_: QTimer.singleShot(0, window.close))
    window.show()
    if args.project:
        window.after_job = partial(window.connect_chatgpt, interactive=False)
        QTimer.singleShot(0, lambda: window.open_project(args.project))
    else:
        QTimer.singleShot(0, partial(window.connect_chatgpt, interactive=False))
    if args.smoke_test:
        QTimer.singleShot(1000, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
