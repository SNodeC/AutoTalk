# SPDX-License-Identifier: MIT
"""Model lifecycle through the subprocess protocol and user-visible controls."""
import sys
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox

from autotalk import runtime, services
from autotalk.app import MainWindow
from autotalk.runtime import Task, SpeechSession, speech_session
from conftest import make_audio


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOTALK_DATA_DIR', str(tmp_path / 'runtime'))
    script = tmp_path / 'worker.py'
    script.write_text('''import json,sys,time,signal
signal.signal(signal.SIGTERM, signal.SIG_DFL)
if hasattr(signal,'pthread_sigmask'): signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGTERM})
from pathlib import Path
config=json.loads(sys.stdin.readline())
delay=Path(__file__).with_name('delay')
if delay.exists(): time.sleep(float(delay.read_text()))
print(json.dumps({'type':'ready'}),flush=True)
for line in sys.stdin:
    request=json.loads(line)
    for item in request['items']: time.sleep(item.get('delay',0))
    print(json.dumps({'type':'batch_complete'}),flush=True)
''')
    monkeypatch.setattr(runtime, 'ensure_speech', lambda task: Path(sys.executable))
    monkeypatch.setattr(runtime, 'worker_path', lambda: script)
    return script


def finish_job(w, qtbot):
    if w.job:
        w.cancel()
        qtbot.waitUntil(lambda: w.job is None, timeout=15000)


def select_policy(w, name, value):
    next(b for b in getattr(w.preferences, name).buttons() if b.property('value') == value).click()


def save_policy(w, retention, loading='needed'):
    w.preferences.show_section("Speech engine")
    select_policy(w, 'gpu_retention', retention)
    select_policy(w, 'gpu_loading', loading)
    w.preferences.buttons.button(QDialogButtonBox.StandardButton.Close).click()


def load(w, qtbot):
    qtbot.waitUntil(w.load_gpu_action.isEnabled, timeout=5000)
    w.load_gpu_action.trigger()
    qtbot.waitUntil(lambda: w.job is None, timeout=5000)
    assert w.speech.state == 'ready'
    return w.speech.process.pid


@pytest.mark.parametrize('policy', ['session', 'presentation', 'idle', 'operation'])
def test_manual_preload_is_retained_and_next_generation_uses_same_owner(engine, project, policy):
    task = Task(report=lambda _: None)
    owner = task.speech = SpeechSession(task, {})
    owner.set_retention(policy)
    try:
        with speech_session(task, services.speech_config(project), preload=True):
            pid = owner.process.pid
        assert owner.state == 'ready' and owner.process.pid == pid
        with speech_session(task, services.speech_config(project)) as session:
            assert session is owner and session.process.pid == pid
            session.generate({'items': []})
        assert (owner.process is None) == (policy == 'operation')
    finally:
        owner.release()


def test_policy_changes_do_not_release_without_a_real_trigger(engine, project, qtbot):
    task = Task(report=lambda _: None); owner = task.speech = SpeechSession(task, {})
    try:
        with speech_session(task, services.speech_config(project), preload=True): pass
        pid = owner.process.pid
        for policy in ('operation', 'presentation', 'session'):
            owner.set_retention(policy); qtbot.wait(30)
            assert owner.process.pid == pid and owner.state == 'ready'
        owner.request_release()
        qtbot.waitUntil(lambda: owner.process is None)
        assert owner.retention == 'session'
        with speech_session(task, services.speech_config(project), preload=True):
            assert owner.process.pid != pid
    finally:
        owner.release()


def test_idle_countdown_starts_when_saved_and_restarts_after_generation(engine, project, monkeypatch):
    timers = []
    class Timer:
        def __init__(self, seconds, callback):
            self.seconds, self.callback, self.cancelled = seconds, callback, False
            timers.append(self)
        def start(self): pass
        def cancel(self): self.cancelled = True
    monkeypatch.setattr(runtime.threading, 'Timer', Timer)
    task = Task(report=lambda _: None); owner = task.speech = SpeechSession(task, {})
    try:
        with speech_session(task, services.speech_config(project), preload=True): pass
        owner.set_retention('idle')
        first = timers[-1]
        assert first.seconds == 300
        with speech_session(task, services.speech_config(project)) as session:
            assert first.cancelled
            session.generate({'items': []})
        current = timers[-1]
        assert current is not first and current.seconds == 300
        monkeypatch.setattr(runtime.threading, 'current_thread', lambda: first)
        first.callback(); assert owner.process is not None
        monkeypatch.setattr(runtime.threading, 'current_thread', lambda: current)
        current.callback(); assert owner.process is None
    finally:
        owner.release()


def test_deferred_release_finishes_owning_operation_before_unloading(engine, project):
    task = Task(report=lambda _: None); owner = task.speech = SpeechSession(task, {})
    try:
        with speech_session(task, services.speech_config(project)) as session:
            process = owner.process
            owner.request_release()
            assert process.poll() is None
            session.generate({'items': []})
        assert process.poll() is not None and owner.state == 'unloaded'
    finally:
        owner.release()


def test_saved_preferences_and_cancel_do_not_undo_manual_load(engine, project, qtbot):
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    w.preferences.show_section("Speech engine")
    select_policy(w, 'gpu_retention', 'operation')
    assert w.speech.retention == 'operation' and 'immediately' in w.preferences.engine_policy_note.text()
    pid = load(w, qtbot)
    w.preferences.reject()
    assert w.speech.process.pid == pid and w.speech.retention == 'operation'
    save_policy(w, 'operation', 'start')
    assert w.speech.process.pid == pid
    reopened = MainWindow(); qtbot.addWidget(reopened)
    assert reopened.preferences.gpu_loading.checkedButton().property('value') == 'start'
    assert reopened.speech.retention == 'operation' and reopened.speech.process is None
    w.unload_gpu_action.trigger()
    qtbot.waitUntil(lambda: w.speech.process is None)
    assert w.config.value('gpu_loading') == 'start' and w.speech.retention == 'operation'


@pytest.mark.parametrize('loading', ['needed', 'start'])
def test_prepared_playback_does_not_wait_for_or_require_a_model(engine, project, qtbot, loading):
    engine.with_name('delay').write_text('0.4')
    make_audio(project, seconds=3)
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    save_policy(w, 'session', loading)
    w.start_button.click()
    assert w.presentation is not None and w.transport.playing
    if loading == 'needed':
        assert w.job is None and w.speech.process is None
    else:
        assert w.job is not None
        qtbot.waitUntil(lambda: w.transport.position > .08)
        assert w.job is not None  # The prepared audio advances before model readiness.
        qtbot.waitUntil(lambda: w.job is None)
        assert w.speech.state == 'ready' and w.transport.playing
        w.unload_gpu_action.trigger()
        qtbot.waitUntil(lambda: w.speech.process is None)
        assert w.transport.playing and w.presentation is not None
    w.stop_presentation()


def test_pausing_and_leaving_fullscreen_are_not_presentation_end(engine, project, qtbot):
    make_audio(project, seconds=3)
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    save_policy(w, 'presentation'); pid = load(w, qtbot)
    w.present()
    qtbot.keyClick(w.presentation, Qt.Key.Key_Escape)
    qtbot.wait(50)
    assert w.transport.state == 'paused' and w.speech.process.pid == pid
    w.continue_presentation()
    assert w.speech.process.pid == pid
    w.stop_presentation()
    qtbot.waitUntil(lambda: w.speech.process is None)
    # Returning from a completed screen is not another end event.
    pid = load(w, qtbot); w.stop_presentation(); qtbot.wait(50)
    assert w.speech.process.pid == pid


@pytest.mark.parametrize('recording', [False, True])
def test_natural_completion_unloads_once_even_with_automatic_export(engine, project, qtbot, recording):
    make_audio(project, seconds=.15); project.record_presentation = recording
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    save_policy(w, 'presentation'); load(w, qtbot)
    w.present()
    qtbot.waitUntil(lambda: w.transport.state == 'finished' and w.speech.process is None, timeout=5000)
    qtbot.waitUntil(lambda: not w.job and not w.pending_exports, timeout=10000)
    if recording: assert Path(w.output_path).is_file()
    w.stop_presentation()


def test_audio_preview_completion_keeps_presentation_policy_model(engine, project, qtbot):
    make_audio(project, seconds=.1)
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    save_policy(w, 'presentation'); pid = load(w, qtbot)
    w.preview_slide()
    qtbot.waitUntil(lambda: w.transport.state == 'stopped')
    assert w.preview_button.text() == 'Play audio'
    qtbot.wait(50)
    assert w.speech.process.pid == pid


def test_screen_recording_keeps_session_open_after_last_slide(engine, project, qtbot):
    make_audio(project, seconds=.1)
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    save_policy(w, 'presentation'); pid = load(w, qtbot)
    class ScreenSession:
        ready = True
        frames = 0
        def close(self): return project.root
    w.transport.capture = ScreenSession()
    w.transport.state = 'playing'
    w.transport._finish(); qtbot.wait(50)
    assert w.speech.process.pid == pid
    w.stop_presentation()
    qtbot.waitUntil(lambda: w.speech.process is None)


def test_cancel_load_and_end_during_load_leave_no_worker(engine, project, qtbot):
    engine.with_name('delay').write_text('1')
    make_audio(project, seconds=3)
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    w.preferences.show_section("Speech engine"); w.preferences.load_gpu_button.click()
    qtbot.waitUntil(lambda: w.speech.process is not None)
    assert w.progress.isVisible() and w.progress.parentWidget() is w.preferences
    w.preferences.cancel_job.click()
    qtbot.waitUntil(lambda: w.job is None)
    assert w.speech.process is None and w.speech.state == 'unloaded'
    w.preferences.reject()
    save_policy(w, 'presentation', 'start'); w.present()
    assert w.transport.playing and w.job is not None
    w.stop_presentation()
    qtbot.waitUntil(lambda: w.job is None)
    assert w.speech.process is None and not w.speech.release_requested


def test_changing_policy_during_work_waits_for_the_safe_boundary(engine, project, qtbot):
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    release = threading.Event()
    def operation(task):
        with speech_session(task, services.speech_config(project)) as session:
            session.generate({'items': []})
            release.wait(3)
    try:
        w.start_job('Preparing speech…', operation)
        qtbot.waitUntil(lambda: w.speech.state == 'in_use')
        w.preferences.show_section("Speech engine")
        assert w.preferences.gpu_retention.buttons()[0].isEnabled()
        assert not w.preferences.unload_gpu_button.isEnabled()
        select_policy(w, 'gpu_retention', 'operation')
        w.preferences.accept()
        assert w.speech.process is not None and w.speech.retention == 'operation'
    finally:
        release.set(); qtbot.waitUntil(lambda: w.job is None)
    assert w.speech.process is None


def test_load_failure_does_not_stop_prepared_playback_and_retry_works(engine, project, qtbot, monkeypatch):
    make_audio(project, seconds=3)
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    errors = []; monkeypatch.setattr(w, 'error', errors.append)
    original = engine.read_text(); engine.write_text("raise RuntimeError('Simulated model failure')")
    save_policy(w, 'session', 'start'); w.present()
    qtbot.waitUntil(lambda: w.job is None)
    assert errors and w.speech.state == 'failed'
    assert w.transport.playing and w.presentation is not None
    engine.write_text(original); load(w, qtbot)
    assert w.transport.playing
    w.stop_presentation()


def test_saving_end_policy_without_a_running_presentation_does_not_unload(engine, project, qtbot):
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot)); w.adopt(project); w.show()
    pid = load(w, qtbot); save_policy(w, 'presentation'); qtbot.wait(50)
    assert w.speech.process.pid == pid
    w.release_gpu(); qtbot.waitUntil(lambda: w.speech.process is None)
    # Ending an unloaded session cannot disable future manual loading.
    w.transport.state = 'playing'; w.transport.stop(); qtbot.wait(50)
    assert not w.speech.release_requested
    load(w, qtbot)


def test_slow_gpu_teardown_keeps_prepared_audio_and_controls_responsive(engine, project, qtbot):
    # A deliberately slow child exit represents model/server cleanup, not synthesis.
    engine.write_text(engine.read_text().replace("print(json.dumps({'type':'ready'}),flush=True)",
        "signal.signal(signal.SIGTERM, lambda *_: (time.sleep(.5), sys.exit(0)))\n"
        "print(json.dumps({'type':'ready'}),flush=True)"))
    make_audio(project, seconds=3)
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot))
    w.adopt(project); w.show(); load(w, qtbot); w.present()
    qtbot.waitUntil(lambda: w.transport.position > .08)
    position = w.transport.position
    w.unload_gpu_action.trigger()
    qtbot.waitUntil(lambda: w.speech.state == 'unloading')
    w.preferences.show_section("Speech engine")
    assert not w.preferences.load_gpu_button.isEnabled() and not w.preferences.unload_gpu_button.isEnabled()
    qtbot.waitUntil(lambda: w.transport.position > position + .1)
    assert w.speech.process is not None and w.transport.playing
    w.preferences.reject()
    qtbot.waitUntil(lambda: w.speech.state == 'unloaded')
    assert w.transport.playing and w.presentation is not None
    w.stop_presentation()


@pytest.mark.parametrize('newer', [False, True])
def test_explicit_update_check_keeps_loaded_model_and_policies(engine, project, qtbot, monkeypatch, newer):
    import io, json
    from autotalk import app
    messages = []
    monkeypatch.setattr(app.QMessageBox, 'information', lambda *args: messages.append(args[2]))
    spec = services.speech_config(project)['model']
    latest = 'f' * 40 if newer else spec['revision']
    monkeypatch.setattr(runtime.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(json.dumps({'sha':latest}).encode()))
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot))
    w.adopt(project); w.show(); save_policy(w, 'operation'); pid = load(w, qtbot)
    manifest = project.manifest.read_bytes()
    w.preferences.show_section("Speech engine"); w.preferences.check_model_button.click()
    qtbot.waitUntil(lambda: w.job is None)
    assert messages and ('different upstream revision' in messages[0]) == newer
    assert w.speech.process.pid == pid and w.speech.retention == 'operation'
    assert spec['revision'] == services.speech_config(project)['model']['revision']
    assert project.manifest.read_bytes() == manifest
    w.preferences.reject()
    make_audio(project, seconds=3); w.adopt(project); w.present()
    assert not w.preferences.check_model_button.isEnabled()
    w.stop_presentation()


@pytest.mark.parametrize('outcome', ['cancel', 'error'])
@pytest.mark.parametrize('mode', ['Prepared', 'Realtime'])
def test_narration_interruption_retains_idle_preloaded_worker(engine, project, qtbot, monkeypatch, outcome, mode):
    """A narration failure must not invalidate an unused, ready speech protocol."""
    from autotalk.project import Project
    project.mode = mode
    for slide in project.slides:
        slide.narration = ''
    entered, release = threading.Event(), threading.Event()
    class Client:
        def __init__(self, task): self.task = task
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, *args, **kwargs):
            entered.set()
            while not release.wait(.01): self.task.check()
            raise ValueError('Narration service unavailable')
    monkeypatch.setattr(services, 'Codex', Client)
    errors = []
    monkeypatch.setattr(MainWindow, 'error', lambda self, text: errors.append(text))
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot))
    w.adopt(project); w.show(); save_policy(w, 'session')
    pid = load(w, qtbot)
    try:
        w.start_button.click()
        qtbot.waitUntil(entered.is_set)
        qtbot.waitUntil(lambda: w.speech.state == 'in_use')
        w.cancel_button.click() if outcome == 'cancel' else release.set()
        qtbot.waitUntil(lambda: w.job is None)
        assert w.speech.process is not None and w.speech.process.pid == pid
        assert w.speech.state == 'ready' and w.mode.isEnabled() and w.start_button.isEnabled()
        assert bool(errors) == (outcome == 'error')
        w.adopt(Project.load(w.project.manifest))
        def speech(task):
            with speech_session(task, services.speech_config(w.project)) as session:
                session.generate({'items': []})
        w.start_job('Prepare slide audio', speech)
        qtbot.waitUntil(lambda: w.job is None)
        assert w.speech.process.pid == pid and w.speech.state == 'ready'
    finally:
        release.set(); finish_job(w, qtbot)


def test_cancel_during_synthesis_discards_unfinished_protocol(engine, project, qtbot):
    w = MainWindow(); qtbot.addWidget(w, before_close_func=lambda widget: finish_job(widget, qtbot))
    w.adopt(project); w.show(); save_policy(w, 'session'); load(w, qtbot)
    process = w.speech.process
    def generate(task):
        with speech_session(task, services.speech_config(project)) as session:
            session.generate({'items': [{'delay': 10}]})
    w.start_job('Create slide audio', generate)
    qtbot.waitUntil(lambda: w.speech.phase == 'generating')
    w.cancel_button.click(); qtbot.waitUntil(lambda: w.job is None)
    assert w.speech.process is None and process.poll() is not None
    assert w.speech.state == 'unloaded' and w.start_button.isEnabled()
