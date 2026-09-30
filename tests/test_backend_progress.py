# SPDX-License-Identifier: MIT
"""Pinned backend diagnostics are observations, never readiness or GPU-transfer percentages."""
import io
import json
import sys
from pathlib import Path

import pytest

from autotalk import runtime, services
from autotalk.app import MainWindow

TRACE = Path(__file__).with_name('fixtures').joinpath('vllm-loading.txt').read_text()


def test_recorded_loading_trace_preserves_real_counts_and_stage_identity():
    events = [e for line in TRACE.splitlines() if (e := runtime.backend_loading_progress(line))]
    files = [e for e in events if e.get('unit') == 'files']
    assert files and {(e['completed'], e['total']) for e in files} == {(0, 1), (1, 1)}
    assert all('current pass' in e['stage'] for e in files)
    assert any(e.get('detail') == '606 weights reported' for e in events)
    assert any('3.88 GiB' in e.get('detail', '') and e['stage'].startswith('Speech engine 1:') for e in events)
    assert any('0.43 GiB' in e.get('detail', '') and e['stage'].startswith('Speech engine 2:') for e in events)
    assert any(e.get('detail') == 'Capacity: 8,192 tokens' for e in events)
    assert events[-1]['stage'] == 'Checking speech service'
    assert not any(e['stage'] == 'Speech model ready' for e in events)
    assert all(e['type'] == 'model_progress' for e in events)


@pytest.mark.parametrize('text', [
    'Loading safetensors checkpoint shards: 100% Completed | 2/1 [x]',
    'Loading safetensors checkpoint shards: 0% Completed | 0/0 [x]',
    'Loading safetensors checkpoint shards: 50% Completed | broken',
    'Unrecognized backend message', 'Application startup complete.',
    'GPU memory use: 95%', '{"type":"ready"}',
])
def test_unknown_or_invalid_diagnostics_cannot_report_progress_or_readiness(text):
    assert runtime.backend_loading_progress(text) is None


def test_ansi_prefixed_progress_and_eager_load_counters():
    line = '\x1b[36m(StageEngineCoreProc_stage1_replica0 pid=42)\x1b[0m Loading safetensors checkpoint shards (eager): 50% Completed | 2/4 [00:03<00:03, 1it/s]'
    event = runtime.backend_loading_progress(line)
    assert event['completed'] == 2 and event['total'] == 4
    assert event['stage'].startswith('Speech engine 2:')


@pytest.mark.parametrize('backend,phase', [('vllm', 'loading'), ('vllm', 'ready'), ('vllm', 'generating'), ('torch', 'loading'), ('mlx', 'loading')])
def test_diagnostics_only_enter_loading_queue_and_remain_in_log(backend, phase):
    logs = []
    owner = runtime.SpeechSession(runtime.Task(log=logs.append), {'backend': backend})
    owner.phase = phase
    with io.TextIOWrapper(io.BytesIO(TRACE.replace('\n', '\r').encode()), newline=None) as pipe:
        owner._read(pipe, False)
    assert len(logs) == len(TRACE.splitlines())
    assert owner.messages.empty() == (backend != 'vllm' or phase != 'loading')
    owner.messages.put({'type': 'ready'})
    events = []; owner.task.event = events.append
    owner._wait('ready')
    assert bool(events) == (backend == 'vllm' and phase == 'loading')
    # A diagnostic queued just before readiness must not leak into the next synthesis.
    owner.messages.put({'type': 'backend_log', 'line': TRACE.splitlines()[0]})
    owner.messages.put({'type': 'batch_complete'})
    before = list(events); owner._wait('batch_complete')
    assert events == before


@pytest.fixture
def loading_worker(tmp_path, monkeypatch):
    script = tmp_path / 'worker.py'
    script.write_text('''import sys,json,time,signal
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_DFL)
if hasattr(signal,'pthread_sigmask'): signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGTERM})
json.loads(sys.stdin.readline())
print('(StageEngineCoreProc_stage0_replica0 pid=42) Model loading took 3.88 GiB memory and 2.6 seconds',file=sys.stderr,flush=True)
print('Loading safetensors checkpoint shards: 100% Completed | 1/1 [00:00<00:00]',file=sys.stderr,flush=True)
print('Orchestrator ready with 2 stages',file=sys.stderr,flush=True)
while not Path(__file__).with_name('release').exists(): time.sleep(.02)
print(json.dumps({'type':'ready'}),flush=True)
for line in sys.stdin:
 print(json.dumps({'type':'batch_complete'}),flush=True)
''')
    monkeypatch.setenv('AUTOTALK_DATA_DIR', str(tmp_path/'runtime'))
    monkeypatch.setattr(runtime, 'ensure_speech', lambda task: Path(sys.executable))
    monkeypatch.setattr(runtime, 'worker_path', lambda: script)
    monkeypatch.setattr(runtime, 'speech_backend', lambda: 'vllm')
    return script


@pytest.mark.parametrize('cancel', [False, True])
def test_ui_stays_loading_after_full_counter_until_ready_or_cancel(loading_worker, qtbot, project, cancel):
    window = MainWindow(); qtbot.addWidget(window); window.adopt(project); window.show()
    seen = []; original = window.job_event
    def event(value):
        original(value)
        if value.get('type') == 'model_progress':
            seen.append((value, window.progress.text()))
    window.job_event = event
    try:
        window.load_gpu()
        qtbot.waitUntil(lambda: 'Checking speech service' in window.progress.text())
        assert window.speech.state == 'loading'
        assert any('3.88 GiB' in text for _, text in seen)
        assert any('1 / 1 files' in text for _, text in seen)
        assert window.progress.maximum() == 1 and window.progress.value() == 0
        assert not window.settings[0].load_gpu_button.isEnabled()
        if cancel:
            window.cancel()
        else:
            loading_worker.with_name('release').touch()
        qtbot.waitUntil(lambda: window.job is None)
        assert window.speech.state == ('unloaded' if cancel else 'ready')
        assert any(e['stage'] == 'Speech model ready' for e, _ in seen) == (not cancel)
        assert all('%' not in text for _, text in seen)
    finally:
        if window.job:
            window.cancel(); qtbot.waitUntil(lambda: window.job is None)
        window.speech.release()
