"""Qt desktop application. Heavy preparation always runs outside the GUI thread."""

import argparse
import copy
from datetime import datetime
import json
import shutil
import subprocess
import html
import sys
import time
import wave
from functools import partial
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QStandardPaths, Qt, QMicrophonePermission, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import QTableWidgetItem, QApplication, QFileDialog, QInputDialog, QLabel, QMainWindow, QMessageBox, QSizePolicy


from .codex import Codex
from .playback import Playback, Presentation
from .project import LANGUAGES, SPEAKERS, Project, Voice, wav_duration
from .recording import Recorder
from .runtime import SpeechSession, Cancelled, Task, child_env, data_dir
from .services import extract_scope, import_pdf, narrate, prepare, preview_path, preview_text, synthesize, workflow
from .media import RATE, export_prepared, export_recording, import_clip
from .voices import library, load_voice, save_voice

def clock(seconds):
    seconds = max(0, round(seconds))
    return f"{seconds//60}:{seconds%60:02d}"


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

    def resizeEvent(self, event):
        self.rescale()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = None
        self.preferences = QSettings()
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
        self.model_catalog = []
        self.after_job = None
        self.live_autostart = False
        self.pending_exports = []
        self.measurements = {}
        self.transport.recording_ready.connect(self.queue_export)
        self.recorder = Recorder()
        self.record_timer = QTimer(self)
        self.record_timer.setSingleShot(True)
        self.record_timer.timeout.connect(self.toggle_recording)
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(250)
        self.elapsed_timer.timeout.connect(self.update_timing)
        self._build()
        self.retention_changed()
        self.refresh_recordings()
        self.elapsed_timer.start()
        self.refresh()

    def _build(self):
        from .ui import build
        build(self)

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            # Qt resolves palette() in style sheets at polish time.
            stylesheet = self.styleSheet()
            self.setStyleSheet("")
            self.setStyleSheet(stylesheet)
        return result

    def place_settings_fields(self):
        destination = self.quick_form if self.project and self.project.mode == "Quick" and not self.talk_dialog.isVisible() else self.general_form
        if self.basics.parentWidget() != destination:
            destination.layout().insertWidget(1, self.basics)
        destination = self.recording_form if self.talk_dialog.isVisible() else self.record_footer
        if self.options.record.parentWidget() != destination:
            destination.layout().insertWidget(1 if self.talk_dialog.isVisible() else 0, self.options.record)
        destination = next((d for d in (self.talk_dialog, self.preferences_dialog, self.export_dialog, self.voice_dialog) if d.isVisible()), self.footer)
        if self.progress.parentWidget() != destination:
            destination.layout().insertWidget(destination.layout().count()-2, self.progress)
            self.progress.setVisible(self.job is not None)

    def error(self, message):
        self.log_message(message)
        QMessageBox.warning(self, "AutoTalk", message)

    def log_message(self, message):
        self.log.appendPlainText(message)
        self.status.setText(message.splitlines()[-1][:220] if message else "")

    def start_job(self, title, function, callback=None, live=False):
        if self.job:
            return
        if self.recorder.source:
            self.error("Stop the reference recording before starting another operation.")
            return
        if not self.save():
            return
        self.transport.stop()
        self.log_message(title)
        if not title.startswith(("Saving", "Export")):
            self.measurements = {}
        self.slide_progress.setRange(0, len(self.project.included_slides) if self.project else 1)
        self.slide_progress.setValue(0)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.job_started = time.monotonic()
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.job_live = live
        self.job = Job(function, self)
        self.job.title = title
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
            self.refresh_recordings()
        self.job.deleteLater()
        self.job = None
        self.job_live = False
        self.progress.hide()
        self.cancel_button.hide()
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

    def cancel(self):
        self.live_autostart = False
        if self.job_live and self.transport.active:
            self.transport.pause()
        if self.job:
            self.job.task.cancelled.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling…")

    def save(self):
        if self.project:
            try:
                self.project.save()
                self.statusBar().showMessage(f"Saved • {self.project.manifest}")
            except OSError as error:
                self.error(f"Could not save the project: {error}")
                return False
        return True

    def adopt(self, project):
        selected = self.transport.index if self.project and self.project.root == project.root else 0
        self.project = project
        self.loading = True
        self.mode.setCurrentText(project.mode)
        self.version_select.clear()
        for key, value in project.versions.items():
            self.version_select.addItem(value.name + " — " + value.language, key)
        self.version_select.setCurrentIndex(self.version_select.findData(project.active_version))
        self.voice_source.setCurrentIndex(self.voice_source.findData(project.voice.source))
        self.speaker.setCurrentIndex(self.speaker.findData(project.voice.speaker))
        self.voice_description.setText(project.voice.description)
        self.background_gain.setValue(project.background.gain * 100 if project.background else 15)
        self.background_loop.setChecked(project.background.loop if project.background else False)
        self.options.load(project)
        self.refresh_models()
        self.refresh_library()
        self.talk_title.setText(project.title)
        self.minutes.setValue(project.target_minutes)
        self.tolerance.setValue(project.tolerance_seconds)
        self.pause.setValue(project.pause_seconds)
        self.language.setCurrentText(project.language)
        self.scope.setPlainText(project.scope)
        self.url.setText(project.conference_url)
        self.audience.setText(project.audience)
        self.objective.setText(project.objective)
        self.transcript.setPlainText(project.voice_transcript)
        self.slide_list.clear()
        self.slide_list.addItems([f"{s.page:02d}  Slide {s.page}" for s in project.slides])
        for i, slide in enumerate(project.slides):
            self.slide_list.item(i).setIcon(QIcon(str(project.image(slide))))
        self.loading = False
        self.workspace.setCurrentWidget(self.quick_page if project.mode == "Quick" else self.editor)
        self.transport.load(project)
        self.transport.select(min(selected, len(project.slides)-1))
        self.refresh()
        self.log_message(f"Talk loaded: {project.title}")
        recent = self.preferences.value("recent_projects", [])
        recent = recent if isinstance(recent, list) else [recent]
        self.preferences.setValue("recent_projects", [str(project.root)] + [v for v in recent if v != str(project.root)][:9])
        self.refresh_recordings()

    def new_project(self):
        if not self.save():
            return
        pdf, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF slides (*.pdf)")
        if not pdf:
            return
        parent = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())) / "AutoTalk"
        base = parent / (Path(pdf).stem + "-AutoTalk")
        destination = base
        index = 2
        while destination.exists():
            destination = base.with_name(f"{base.name}-{index}")
            index += 1
        def imported(project):
            project.mode = self.mode.currentText()
            project.quick_timing = self.preferences.value("quick_timing", "once")
            project.speech_priority = self.preferences.value("speech_priority", "consistency")
            project.buffer_seconds = 2 if project.speech_priority == "earliest" else 5
            self.adopt(project)
            if project.mode != "Quick":
                self.after_job = self.talk_dialog.show_section
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
        self.transport.stop()
        p = self.project
        changes = []
        for name, value, title in (("title", self.talk_title.text(), "Title"), ("scope", self.scope.toPlainText(), "Audience topics"),
                ("target_minutes", self.minutes.value(), "Talk length"), ("tolerance_seconds", self.tolerance.value(), "Timing tolerance"),
                ("pause_seconds", self.pause.value(), "Slide pauses"), ("audience", self.audience.text(), "Audience"),
                ("objective", self.objective.text(), "Talk objective"), ("conference_url", self.url.text().strip(), "Conference website")):
            if getattr(p, name) != value:
                changes.append(title)
            setattr(p, name, value)
        self.options.load(p)
        self.transport.refresh_audio()
        self.refresh()
        if changes:
            self.log_message(", ".join(changes) + " changed. " + self.next_step()[1])

    def narration_changed(self):
        if not self.loading and self.project:
            self.project.slides[self.transport.index].narration = self.narration.toPlainText()
            self.transport.stop()
            self.refresh()

    def voice_changed(self):
        if not self.loading and self.project:
            self.transport.stop()
            self.project.voice_transcript = self.transcript.toPlainText()
            self.refresh()

    def select_slide(self, index):
        if not self.loading and index >= 0:
            self.transport.select(index)

    def show_slide(self, index):
        if not self.project:
            return
        self.loading = True
        slide = self.project.slides[index]
        self.slide_list.setCurrentRow(index)
        self.image.show_file(self.project.image(slide))
        self.play_image.show_file(self.project.image(slide))
        following = next((s for s in self.project.included_slides if s.page > slide.page), slide)
        self.next_image.show_file(self.project.image(following))
        self.next_label.setText("Up next · slide " + str(following.page) if following.page > slide.page else "Last slide")
        self.presenter_narration.setPlainText(slide.narration)
        self.narration.setPlainText(slide.narration)
        self.notes.setText(slide.notes)
        self.slide_directions.setText(slide.directions)
        self.slide_budget.setValue(slide.budget_seconds)
        self.slide_include.setChecked(slide.included)
        self.slide_after.setCurrentIndex(self.slide_after.findData(slide.after))
        self.inherit_delivery.setChecked(not bool(slide.directions))
        self.waveform.load(self.project.audio(slide) if self.project.ready(slide) else None)
        self.clip_select.clear()
        for clip in slide.clips:
            self.clip_select.addItem(Path(clip.file).name)
        self.show_clip()
        self.loading = False
        self.refresh()

    def refresh(self):
        p = self.project
        live = bool(self.job and self.job_live)
        editable = self.job is None and not self.transport.active and self.presentation is None and not self.recorder.source
        self.editor.setEnabled(p is not None)
        self.narration.setReadOnly(not editable)
        for widget in self.authoring_widgets:
            widget.setEnabled(p is not None and editable)
        self.quick_page.setEnabled(p is not None and editable)
        self.welcome.setEnabled(editable)
        for dialog in (self.talk_dialog, self.preferences_dialog, self.export_dialog, self.voice_dialog):
            dialog.pages.setEnabled(editable)
            dialog.buttons.setEnabled(self.job is None and not self.recorder.source)
            dialog.cancel_job.setVisible(self.job is not None or bool(self.recorder.source))
            dialog.cancel_job.setText("Stop voice recording" if self.recorder.source else "Cancel operation")
            if not self.job:
                dialog.status.setText(self.next_step()[1])
        self.place_settings_fields()
        self.mode.setEnabled(editable)
        self.options.record.setEnabled(p is not None and editable)
        self.options.recording_widget.setEnabled(editable)
        resumable = bool(p and p.mode == "Realtime" and not p.prepared and self.transport.state == "paused" and self.presentation is None and not self.job)
        self.start_button.setEnabled(p is not None and (editable or resumable))
        for action in self.actions:
            action.setEnabled(editable)
        for action, control in self.control_actions:
            action.setEnabled(control.isEnabled() and p is not None)
        self.talk_action.setEnabled(p is not None and editable)
        self.codex_model.setEnabled(p is not None and p.mode != "Quick")
        self.codex_effort.setEnabled(p is not None and p.mode != "Quick")
        self.options.synthesis_widget.setEnabled(p is not None and editable)
        self.summary.setText(f"Target {clock(p.target_minutes*60)} · Audio {clock(p.total_seconds) if p.prepared else 'not ready'} · {p.language}" if p else "PDF slides → spoken presentation")
        if not p:
            for control in (self.play_button, self.present_button, self.continue_button, self.end_button, self.demo_button,
                            self.previous_button, self.next_button, self.preview_button, self.fit_button, self.export_button):
                control.setEnabled(False)
            return
        self.title_label.setText(p.title or "Untitled talk")
        self.setWindowTitle((p.title or "Untitled talk") + " — AutoTalk")
        self.voice_preview_button.setText("Stop sample" if self.transport.preview_path else "Listen to a sample")
        self.voice_source.setEnabled(p.mode != "Quick")
        self.voice_panels.setCurrentIndex(self.voice_source.currentIndex())
        self.voice_panels.setEnabled(p.mode != "Quick")
        voice = p.effective_voice
        self.voice_preview_button.setEnabled(bool(self.transport.preview_path) or
            (bool(p.voice_file and p.asset(p.voice_file).is_file()) if voice.source == "Base" else
             bool(voice.description.strip()) if voice.source == "VoiceDesign" else True))
        self.accept_voice_button.setVisible(voice.source == "VoiceDesign")
        self.accept_voice_button.setEnabled(voice.source == "VoiceDesign" and preview_path(p).is_file())
        self.save_voice_button.setEnabled(p.mode != "Quick" and (self.accept_voice_button.isEnabled() if voice.source == "VoiceDesign" else self.voice_preview_button.isEnabled()))
        self.slide_directions.setEnabled(p.voice.source != "Base" and p.mode != "Quick" and not self.inherit_delivery.isChecked())
        caption, explanation, _ = self.next_step()
        self.start_button.setText(caption)
        self.start_action.setText(caption)
        self.context_warning.setText(explanation)
        if not self.job:
            self.status.setText(explanation)
        self.mode_description.setText(p.mode + " · " + self.mode.currentData(Qt.ItemDataRole.ToolTipRole))
        for widget in (self.url, self.scope, self.audience, self.objective, self.conference_button):
            widget.setEnabled(p.mode != "Quick")
        self.background_button.setText("Background: " + Path(p.background.file).name[:16] if p.background else "Add background track")
        for widget in (self.background_gain, self.background_loop, self.remove_background_button):
            widget.setEnabled(editable and p.background is not None)

        self.transcript.setEnabled(bool(p.voice_file))
        self.sources.setText("Sources: " + " · ".join(
            f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>' for url in p.sources) if p.sources else "")
        context = p.context_key()
        self.narration_progress.setRange(0, len(p.included_slides))
        self.narration_progress.setValue(sum(bool(s.passages) and s.narration_context == context for s in p.included_slides))
        self.narration_progress.setFormat("Approved text: %v / %m")
        ready = sum(p.ready(s) for s in p.included_slides)
        self.duration_label.setText(f"{clock(p.total_seconds)} prepared  /  {clock(p.target_minutes*60)} target")
        self.fit_label.setText(f"{ready}/{len(p.included_slides)} included slides have current audio. " +
            ("Within requested tolerance." if p.within_target else
             f"Difference: {p.total_seconds-p.target_minutes*60:+.1f} seconds (tolerance ±{p.tolerance_seconds:g}s)." if p.prepared
             else "Review and approve the talk text." if not p.script_current else "Generate audio to measure the complete talk."))
        self.accept_button.setVisible(any(s.passages for s in p.slides) and not p.script_current)
        self.accept_button.setEnabled(editable and not any(s.narration_origin == "translation" for s in p.included_slides))
        for i, slide in enumerate(p.slides):
            item = self.slide_list.item(i)
            if item:
                title = next((line.strip() for line in slide.source_text.splitlines() if line.strip() and
                              (len(p.slides) == 1 or not all(line in s.source_text for s in p.slides))), f"Slide {slide.page}")
                item.setText(f"{slide.page:02d}  {'✓' if p.ready(slide) else '○'}  " +
                             ("Excluded" if not slide.included else clock(slide.duration) if p.ready(slide) else "Needs audio") + "\n" + title)
                item.setToolTip(item.text())
        slide = p.slides[self.transport.index]
        self.slide_info.setText(f"Slide {slide.page} of {len(p.slides)} • " +
            (f"Audio {clock(slide.duration)}" if p.ready(slide) else "Audio needs generation") +
            (f" • Planned {slide.budget_seconds:.0f}s" if slide.budget_seconds else ""))
        can_play = (p.prepared and not self.job or p.mode == "Realtime" and live) and not self.recorder.source
        self.preview_button.setEnabled(editable and p.ready(p.slides[self.transport.index]))
        self.preview_button.setText("Stop preview" if self.transport.preview_path else "▷ Preview")
        self.slide_list.setEnabled(editable or can_play)
        self.play_button.setEnabled(can_play and self.transport.playing)
        self.present_button.setEnabled(can_play and self.presentation is None and not self.transport.active)
        self.continue_button.setEnabled(can_play and self.presentation is None and self.transport.state == "paused" and not self.transport.preview_path)
        self.start_button.setVisible(self.workspace.currentWidget() is not self.presenter or not can_play and self.presentation is None)
        self.present_button.setVisible(can_play and not self.transport.active)
        self.play_button.setVisible(self.transport.playing)
        self.continue_button.setVisible(can_play and self.transport.state == "paused")
        self.demo_button.setEnabled(can_play and self.transport.active)
        self.end_button.setEnabled(self.transport.active or self.workspace.currentWidget() is self.presenter)
        self.end_button.setText("End presentation and save video" if self.transport.capture else "End presentation" if self.transport.active else "Return to editing")
        self.end_action.setText(self.end_button.text())
        if self.job is None:
            self.slide_progress.setRange(0, len(p.included_slides))
            self.slide_progress.setValue(ready)
            self.slide_progress.setFormat("Prepared slides: %v / %m")
        self.fit_button.setEnabled(editable and bool(p.slides) and all(s.passages for s in p.included_slides))
        self.export_button.setEnabled(editable and p.prepared)
        self.previous_button.setEnabled(can_play and any(s.page < slide.page for s in p.included_slides))
        self.next_button.setEnabled(can_play and any(s.page > slide.page for s in p.included_slides))
        self.delivery_summary.setText(f"{p.delivery.style}\nVoice: {p.effective_voice.name}\n" + ("Slide override" if slide.directions else "Using talk delivery"))
        self.quick_summary.setText(f"{p.title}\n{len(p.included_slides)} slides · voice: Ryan\n" + explanation)
        for action, control in self.control_actions:
            action.setEnabled(control.isEnabled())
        self.update_timing()

    def update_timing(self):
        if not hasattr(self, "play_time"):
            return
        capture = self.transport.capture
        self.options.record.setText(f"Recording video • {clock(capture.frames / RATE)}" if capture else "Record presentation as a video · " + self.options.fields["recording_source"].currentText())
        total = self.transport.total_seconds
        elapsed = self.transport.elapsed
        remaining = clock(total-elapsed) if self.transport.complete else "estimating…"
        self.play_time.setText(f"{self.transport.state.capitalize()} • Elapsed {clock(elapsed)} • Remaining {remaining} • Buffered {self.transport.buffered_seconds:.1f}s")
        duration = self.project.slides[self.transport.index].duration if self.project else 0
        self.preview_time.setText(f"{clock(self.transport.position)} / {clock(duration)}")
        self.waveform.progress = min(1, self.transport.position / duration) if duration else 0
        self.waveform.update()
        if capture:
            recording = "Waiting for screen sharing…" if not getattr(capture, "ready", True) else ("Slides finished — recording continues" if self.transport.state == "finished" else "● Recording") + " · " + clock(capture.frames / RATE)
        elif self.pending_exports or self.job and self.job.title.startswith(("Saving", "Export")):
            recording = "Saving video…"
        else:
            recording = "Will record when presentation starts" if self.project and self.project.record_presentation else "Recording off"
        if self.output_button.isEnabled() and Path(self.output_path).is_file():
            date = datetime.fromtimestamp(Path(self.output_path).stat().st_mtime).strftime("%d %b, %H:%M")
            recording += f' · Saved {date}: <a href="video">Open video / audio</a> · <a href="folder">Open folder</a>'
        self.record_status.setText(recording)
        if self.job:
            elapsed = clock(time.monotonic()-self.job_started)
            self.statusBar().showMessage(f"Operation elapsed: {elapsed}")
            for dialog in (self.talk_dialog, self.preferences_dialog, self.export_dialog, self.voice_dialog):
                dialog.status.setText(f"{self.status.text()} · Waiting {elapsed}")

    def playback_state_changed(self):
        if self.job_live and self.transport.state == "playing":
            self.measurements.setdefault("First playback", time.monotonic()-self.job_started)
        self.refresh()

    def connect_chatgpt(self):
        def connect(task):
            with Codex(task) as codex:
                return {"account": "Connected to ChatGPT", "models": codex.models()}
        def connected(result):
            self.connection.setText(result["account"])
            self.model_catalog = result["models"]
            self.refresh_models()
        self.start_job("Connecting to ChatGPT…", connect, connected)

    def read_conference(self):
        if not self.url.text().strip():
            self.error("Enter a conference website URL, or type the scope directly below.")
            return
        def done(result):
            self.project.sources = result["sources"]
            self.scope.setPlainText(result["scope"])
            self.project.save()
            self.log_message("Review the extracted conference scope before writing the talk text.")
        self.start_job("Reading conference scope…", lambda task: extract_scope(self.url.text().strip(), task, self.project.codex_model, self.project.codex_effort), done)

    def create_narration(self):
        if not self.project:
            return
        pages = [s.page for s in self.project.included_slides if s.narration_origin == "translation"]
        if (not pages and any(s.narration.strip() for s in self.project.slides)
                and QMessageBox.question(self, "Rewrite all talk text?", "Rewrite the text for every slide? This replaces your edits in the current language version.") != QMessageBox.StandardButton.Yes):
            return
        def done(project):
            self.adopt(project)
            self.workspace.setCurrentWidget(self.editor)
            self.log_message("Talk text is ready to review.")
        self.start_job("Writing talk text…", partial(narrate, copy.deepcopy(self.project), pages=pages or None), done)

    def generate_speech(self):
        self.start_job("Preparing audio…", partial(prepare, copy.deepcopy(self.project)), self.accept_result)

    def fit_duration(self):
        if QMessageBox.question(self, "Fit duration", "AutoTalk will revise your talk text and regenerate audio, up to three times, using your Codex allowance. Continue?") != QMessageBox.StandardButton.Yes:
            return
        self.start_job("Fitting the talk to its duration…", partial(prepare, copy.deepcopy(self.project), fit=True), self.accept_result)

    def import_voice(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import your voice", "", "PCM WAV recording (*.wav)")
        if path:
            self.set_voice(Path(path))

    def set_voice(self, path):
        try:
            self.transport.stop()
            duration = wav_duration(path)
            if not 3 <= duration <= 60:
                raise ValueError("Use a WAV reference recording between 3 and 60 seconds.")
            self.project.set_voice(path)
            self.transcript.clear()
            self.project.save()
            self.adopt(self.project)
        except (OSError, ValueError, EOFError, wave.Error) as error:
            self.error(str(error))

    def toggle_recording(self):
        try:
            if self.recorder.source:
                self.record_timer.stop()
                path = self.recorder.stop(data_dir() / "recording.wav")
                self.record_button.setText("Record my voice")
                self.refresh()
                self.set_voice(path)
            else:
                permission = QMicrophonePermission()
                application = QApplication.instance()
                status = application.checkPermission(permission)
                if status == Qt.PermissionStatus.Undetermined:
                    application.requestPermission(permission, self, lambda _: self.toggle_recording())
                    return
                if status == Qt.PermissionStatus.Denied:
                    raise RuntimeError("Allow microphone access for AutoTalk in system privacy settings, or import a reference recording.")
                self.transport.stop()
                self.recorder.start()
                self.record_button.setText("Stop recording")
                self.refresh()
                self.record_timer.start(30000)
        except (RuntimeError, OSError, ValueError, wave.Error) as error:
            self.record_timer.stop()
            self.record_button.setText("Record my voice")
            self.refresh()
            self.error(str(error))

    def preview_voice(self):
        if self.transport.preview_path:
            self.transport.stop()
            return
        if self.recorder.source:
            self.error("Stop recording before previewing the voice.")
            return
        def done(path):
            self.transport.preview(path)
            self.log_message("Playing your voice preview.")
        self.start_job("Generating voice preview…", partial(synthesize, copy.deepcopy(self.project), preview=True), done)

    def present(self, resume=False, selected=False):
        if self.presentation or not self.project:
            return
        if not self.project.prepared and not (self.project.mode == "Realtime" and self.job and self.job_live):
            return
        if not self.job and not self.save():
            return
        if not resume and not selected:
            self.transport.select(self.project.included_slides[0].page-1)
        self.live_autostart = False
        self.presentation = Presentation(self.transport, self.end_action)
        screens = QApplication.screens()
        screen = screens[min(self.screen.currentIndex(), len(screens)-1)]
        self.presentation.setScreen(screen)
        self.presentation.setGeometry(screen.geometry())
        self.presentation.closed.connect(self.presentation_closed)
        self.workspace.setCurrentWidget(self.presenter)
        self.transport.fullscreen = True
        self.presentation.showFullScreen()
        self.transport.play()
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
        self.workspace.setCurrentWidget(self.quick_page if self.project and self.project.mode == "Quick" else self.editor)
        self.refresh()

    def configuration_changed(self):
        if self.loading or not self.project:
            return
        self.transport.stop()
        self.transport.refresh_audio()
        for name in ("quick_timing", "speech_priority"):
            self.preferences.setValue(name, getattr(self.project, name))
        self.refresh()

    def mode_changed(self, value):
        if self.loading or not self.project:
            return
        self.project.mode = value
        self.workspace.setCurrentWidget(self.quick_page if value == "Quick" else self.editor)
        self.options.load(self.project)
        self.configuration_changed()

    def next_step(self):
        p = self.project
        if p is None:
            return "Open PDF…", "Choose slides to begin.", self.new_project
        if any(s.narration_origin == "translation" for s in p.included_slides):
            return "Translate talk text", f"Translate the remaining text to {p.language}, or replace each slide's text yourself. Your edits and original language version are preserved.", self.create_narration
        if p.manual_review_required:
            return "Review talk text", "Review each slide's text, then choose Approve all slide text. Your edits are preserved.", self.review_speech
        if p.mode == "Prepared":
            if not any(s.passages for s in p.included_slides):
                return "Write talk text", "Your slides are ready. Write the talk text next.", self.create_narration
            if not p.script_current:
                return "Review talk text", "Review the text for these talk settings, then approve all slide text or choose Talk → Write or translate talk text.", self.review_speech
            if not p.prepared:
                return "Prepare audio", "The talk text is ready. Prepare its audio, then listen before presenting. First use downloads several GB and can take several minutes.", self.generate_speech
        if p.prepared:
            if p.mode == "Quick" and p.quick_timing == "require" and not p.within_target:
                return "Fit talk length", "The talk is outside your chosen timing range. Adjust its length before starting.", self.fit_duration
            return "Start presentation", "Speech and audio are ready. Start opens the fullscreen presentation.", self.present
        return ("Resume preparation" if self.transport.state == "paused" else "Prepare and start"), "Preparation opens fullscreen automatically when audio is ready. First use downloads speech files; later uses are faster.", self.prepare_and_present

    def review_speech(self):
        self.workspace.setCurrentWidget(self.editor)
        self.narration.setFocus()
        self.log_message(self.next_step()[1])

    def start_mode(self):
        if not self.job:
            self.next_step()[2]()

    def prepare_and_present(self):
        if self.transport.state != "paused":
            self.transport.select(self.project.included_slides[0].page-1)
        else:
            self.log_message("Resuming preparation; an unfinished slide restarts from its beginning.")
        snapshot = copy.deepcopy(self.project)
        self.live_autostart = snapshot.mode == "Realtime"
        def done(result):
            self.accept_result(result)
            if result.mode == "Quick":
                if result.quick_timing == "require" and not result.within_target:
                    self.log_message("Timing does not match. Review or revise the talk before starting.")
                else:
                    self.after_job = self.present
            elif result.mode == "Realtime" and self.live_autostart:
                self.after_job = partial(self.present, resume=True)
        self.start_job("Preparing " + snapshot.mode + " presentation…", partial(workflow, snapshot), done,
                       live=snapshot.mode == "Realtime")

    def accept_result(self, project):
        if self.transport.active or self.presentation:
            self.project = self.transport.project = project
            self.transport.refresh_audio()
            self.options.load(project)
            self.show_slide(self.transport.index)
        else:
            self.adopt(project)
        self.refresh()

    def job_error(self, message):
        self.close_requested = False
        self.live_autostart = False
        if self.transport.active:
            self.transport.pause()
        self.error(message)

    def job_event(self, value):
        if self.job is None:
            return
        kind = value.get("type")
        if kind == "progress":
            progress = self.narration_progress if value["stage"] == "Narration" else self.slide_progress
            progress.setRange(0, max(1, value["total"]))
            progress.setValue(value["completed"])
            progress.setFormat(value["stage"] + ": %v / %m")
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
            self.performance.setText(text)
            self.performance.show()
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
            elif kind == "slide_ready":
                slide = value["slide"]
                if slide.audio_key == self.project.speech_key(slide):
                    self.project.slides[slide.page-1] = slide
                    self.transport.refresh_audio(slide.page-1)
                    self.refresh()
            elif kind == "audio":
                self.measurements.setdefault("First audio", time.monotonic()-self.job_started)
                self.transport.receive_audio(value)
            if self.live_autostart:
                buffered = self.transport.buffered_seconds
                if buffered >= self.transport.required_buffer or (self.project.prepared and buffered > 0):
                    self.present(resume=True)

    def refresh_models(self):
        previous = self.loading
        self.loading = True
        wanted = self.project.codex_model if self.project else ""
        self.codex_model.clear()
        self.codex_model.addItem("Account default", "")
        for model in self.model_catalog:
            if "image" in model.get("inputModalities", ["text", "image"]):
                self.codex_model.addItem(model.get("displayName", model["model"]), model["model"])
        if wanted and self.codex_model.findData(wanted) < 0:
            self.codex_model.addItem(wanted + " (refresh availability)", wanted)
        self.codex_model.setCurrentIndex(max(0, self.codex_model.findData(wanted)))
        self.refresh_efforts()
        self.loading = previous

    def refresh_efforts(self):
        previous = self.loading
        self.loading = True
        model = self.codex_model.currentData()
        selected = next((m for m in self.model_catalog if m["model"] == model), None) if model else next(
            (m for m in self.model_catalog if m.get("isDefault")), None)
        wanted = self.project.codex_effort if self.project else ""
        self.codex_effort.clear()
        self.codex_effort.addItem("Model default" + (" (" + selected.get("defaultReasoningEffort", "") + ")" if selected else ""), "")
        for option in (selected or {}).get("supportedReasoningEfforts", []):
            effort = option["reasoningEffort"]
            self.codex_effort.addItem(effort, effort)
            self.codex_effort.setItemData(self.codex_effort.count()-1, option.get("description", ""), Qt.ItemDataRole.ToolTipRole)
        if wanted and self.codex_effort.findData(wanted) < 0:
            self.codex_effort.addItem(wanted + " (refresh availability)", wanted)
        self.codex_effort.setCurrentIndex(max(0, self.codex_effort.findData(wanted)))
        self.loading = previous

    def model_changed(self):
        if not self.loading and self.project:
            self.project.codex_model = self.codex_model.currentData() or ""
            self.project.codex_effort = ""
            self.refresh_efforts()
            self.configuration_changed()

    def model_settings_changed(self):
        if not self.loading and self.project:
            self.project.codex_effort = self.codex_effort.currentData() or ""
            self.configuration_changed()

    def version_changed(self):
        if not self.loading and self.project and self.version_select.currentData():
            self.project.active_version = self.version_select.currentData()
            self.adopt(self.project)

    def add_version(self):
        language, ok = QInputDialog.getItem(self, "New language version", "Language", LANGUAGES, editable=False)
        if ok:
            self.project.add_version(language, translate=True)
            self.adopt(self.project)
            self.save()

    def insert_passage(self):
        if self.project:
            self.narration.insertPlainText("\n\n[" + self.passage_language.currentText() + "] ")
            self.narration.setFocus()

    def slide_policy_changed(self):
        if self.loading or not self.project:
            return
        slide = self.project.slides[self.transport.index]
        if not self.slide_include.isChecked() and slide.included and len(self.project.included_slides) == 1:
            self.slide_include.setChecked(True)
            self.error("Include at least one slide.")
            return
        if slide.budget_seconds != self.slide_budget.value():
            slide.budget_seconds = self.slide_budget.value()
            slide.narration_context = ""
            slide.narration_origin = "manual"
        slide.included = self.slide_include.isChecked()
        slide.after = self.slide_after.currentData()
        if self.inherit_delivery.isChecked():
            self.slide_directions.clear()
        self.configuration_changed()

    def regenerate_slide(self):
        if not self.project:
            return
        page = self.transport.index + 1
        if QMessageBox.question(self, "Rewrite slide", f"Replace the text for slide {page}? Other slides will be preserved.") != QMessageBox.StandardButton.Yes:
            return
        def ready(project):
            self.adopt(project)
            self.transport.select(page-1)
        self.start_job(f"Regenerating slide {page}…", partial(narrate, copy.deepcopy(self.project), pages=[page]), ready)

    def preview_slide(self):
        if self.transport.preview_path:
            self.transport.stop()
        elif self.project and self.project.ready(self.project.slides[self.transport.index]):
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
        text, ok = QInputDialog.getText(self, "Find in talk text", "Text to find")
        if ok and text and not self.narration.find(text):
            self.narration.moveCursor(self.narration.textCursor().MoveOperation.Start)
            self.narration.find(text)

    def open_talk_folder(self):
        if self.project:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project.root)))

    def slide_directions_changed(self, value):
        if not self.loading and self.project:
            self.project.slides[self.transport.index].directions = value
            self.configuration_changed()

    def voice_settings_changed(self):
        if self.loading or not self.project:
            return
        voice = self.project.voice
        voice.source = self.voice_source.currentData()
        voice.speaker = self.speaker.currentData()
        voice.description = self.voice_description.text()
        voice.name = voice.speaker if voice.source == "CustomVoice" else "Designed voice" if voice.source == "VoiceDesign" else "My voice"
        self.options.load(self.project)
        self.configuration_changed()

    def refresh_library(self):
        selected = self.voice_library.item(self.voice_library.currentRow(), 0)
        selected = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        self.voice_library.setRowCount(0)
        entries = [(name, description, "Multilingual", name) for name, description in SPEAKERS.items()]
        for path in library():
            try:
                voice = json.loads(path.read_text(encoding="utf-8"))
                languages = ", ".join(k for k in voice["references"] if k != "default") or "Multilingual"
                entries.append((voice["name"], voice["source"], languages, str(path)))
            except (OSError, ValueError, KeyError):
                continue
        for name, source, languages, key in entries:
            if self.library_language.currentText() not in ("All languages", languages) and self.library_language.currentText() not in languages and languages != "Multilingual":
                continue
            row = self.voice_library.rowCount()
            self.voice_library.insertRow(row)
            for col, value in enumerate((name, source, languages)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.voice_library.setItem(row, col, item)
        self.voice_library.resizeRowsToContents()
        self.voice_library.selectRow(next((row for row in range(self.voice_library.rowCount())
            if self.voice_library.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected), 0))

    def use_saved_voice(self):
        item = self.voice_library.item(self.voice_library.currentRow(), 0)
        if item:
            try:
                key = item.data(Qt.ItemDataRole.UserRole)
                if key in SPEAKERS:
                    self.project.voice = Voice(name=key, speaker=key)
                else:
                    load_voice(self.project, key)
                self.adopt(self.project)
                self.save()
            except (OSError, ValueError) as error:
                self.error(str(error))

    def save_personal_voice(self):
        name, ok = QInputDialog.getText(self, "Save reusable voice", "Voice name", text=self.project.voice.name)
        if not ok or not name.strip():
            return
        if self.project.voice.source == "VoiceDesign" and not self.accept_designed_voice():
            return
        try:
            save_voice(self.project, name)
            self.refresh_library()
            self.save()
        except (OSError, ValueError) as error:
            self.error(str(error))


    def show_clip(self, *_):
        if not self.project:
            return
        previous = self.loading
        self.loading = True
        clips = self.project.slides[self.transport.index].clips
        index = self.clip_select.currentIndex()
        self.clip_gain.setEnabled(0 <= index < len(clips))
        self.clip_placement.setEnabled(0 <= index < len(clips))
        if 0 <= index < len(clips):
            self.clip_gain.setValue(clips[index].gain)
            self.clip_placement.setCurrentText(clips[index].placement)
        self.loading = previous

    def clip_changed(self, *_):
        if not self.loading and self.project:
            clips = self.project.slides[self.transport.index].clips
            index = self.clip_select.currentIndex()
            if 0 <= index < len(clips):
                clips[index].gain = self.clip_gain.value()
                clips[index].placement = self.clip_placement.currentText()
                self.configuration_changed()

    def add_clip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose presentation audio", "", "Audio (*.wav *.mp3 *.flac *.ogg *.m4a *.mp4);;All files (*)")
        if not path:
            return
        index = self.transport.index
        def done(clip):
            self.project.slides[index].clips.append(clip)
            self.show_slide(index)
            self.save()
        self.start_job("Importing audio clip…", partial(import_clip, self.project, Path(path)), done)

    def remove_clip(self):
        clips = self.project.slides[self.transport.index].clips
        index = self.clip_select.currentIndex()
        if 0 <= index < len(clips):
            clips.pop(index)
            self.show_slide(self.transport.index)
            self.configuration_changed()

    def add_background(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose background audio", "", "Audio (*.wav *.mp3 *.flac *.ogg *.m4a);;All files (*)")
        if path:
            def done(clip):
                clip.gain = self.background_gain.value() / 100
                clip.loop = self.background_loop.isChecked()
                self.project.background = clip
                self.transport.refresh_audio()
                self.refresh()
                self.save()
            self.start_job("Importing background track…", partial(import_clip, self.project, Path(path), placement="background"), done)

    def remove_background(self):
        self.project.background = None
        self.configuration_changed()

    def background_changed(self, *_):
        if not self.loading and self.project and self.project.background:
            self.project.background.gain = self.background_gain.value() / 100
            self.project.background.loop = self.background_loop.isChecked()
            self.configuration_changed()

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
        roots = [str(self.project.root)] if self.project else self.preferences.value("recent_projects", [])
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

    def recover_recording(self):
        item = self.recordings.item(self.recordings.currentRow(), 0)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        destination, _ = QFileDialog.getSaveFileName(self, "Save recording", "presentation.mp4", "Video (*.mp4);;WAV audio (*.wav);;M4A audio (*.m4a)")
        if destination:
            self.start_job("Exporting recording…", partial(export_recording, Path(path).parent, destination=destination), self.export_saved)

    def accept_script(self):
        try:
            self.project.accept_script()
            self.save()
            self.transport.refresh_audio()
            self.refresh()
        except ValueError as error:
            self.error(str(error))

    def language_selected(self, language):
        if self.loading or not self.project or language == self.project.language:
            return
        existing = next((key for key, version in self.project.versions.items() if version.language == language), None)
        if existing:
            self.project.active_version = existing
        elif not any(s.passages for s in self.project.slides):
            self.project.language = language
        else:
            self.project.add_version(language, translate=True)
            self.log_message("New language version created. Translate its text; your original version is preserved.")
        self.adopt(self.project)
        self.save()

    def accept_designed_voice(self):
        if self.project.voice.source != "VoiceDesign":
            return False
        path = preview_path(self.project)
        if not path.exists():
            self.error("Preview this design first, then accept the voice you heard.")
            return False
        try:
            self.project.set_voice(path, preview_text(self.project))
        except (OSError, ValueError) as error:
            self.error(str(error))
            return False
        self.project.voice.name = "Designed voice"
        self.adopt(self.project)
        self.save()
        return True

    def retention_changed(self):
        policy = self.gpu_retention.currentData()
        self.preferences.setValue("gpu_retention", policy)
        self.speech.set_retention(policy)

    def release_gpu(self):
        if not self.job and self.speech.process:
            self.start_job("Releasing speech GPU…", lambda task: self.speech.release())

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
            self.toggle_recording()
        if self.presentation:
            self.presentation.close()
        self.transport.stop()
        if self.save():
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
    window.show()
    if args.project:
        QTimer.singleShot(0, lambda: window.open_project(args.project))
    if args.smoke_test:
        QTimer.singleShot(1000, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
