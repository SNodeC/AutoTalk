"""Measured loader progress at download, verification and Qt job boundaries."""
import hashlib
import io
import sys
from types import ModuleType

import pytest

from autotalk import runtime, speech_worker
from autotalk.app import MainWindow


@pytest.mark.parametrize('known_total,resume', [(True, False), (False, False), (True, True)])
def test_runtime_download_reports_actual_bytes_without_inventing_unknown_total(tmp_path, monkeypatch, known_total, resume):
    content = b'a' * (2 * 2**20 + 11)
    destination = tmp_path / 'runtime.tar.gz'
    offset = 19 if resume else 0
    if resume:
        destination.with_suffix('.gz.part').write_bytes(content[:offset])
    response = io.BytesIO(content[offset:])
    response.headers = {'Content-Length': str(len(content)-offset)} if known_total else {}
    response.status = 206 if resume else 200
    requests, events = [], []
    def open_response(request, timeout):
        requests.append(request)
        return response
    monkeypatch.setattr(runtime.urllib.request, 'urlopen', open_response)
    runtime.download('https://example.invalid/runtime', destination, hashlib.sha256(content).hexdigest(),
                     runtime.Task(event=events.append))
    assert destination.read_bytes() == content
    assert requests[0].get_header('Range') == f'bytes={offset}-'
    progress = [e for e in events if e.get('unit') == 'bytes']
    assert progress and progress[0]['completed'] == offset + 2**20
    assert progress[0]['total'] == (len(content) if known_total else None)
    # The verified cached artifact must not contact the network a second time.
    runtime.download('https://example.invalid/runtime', destination, hashlib.sha256(content).hexdigest(), runtime.Task())
    assert len(requests) == 1


@pytest.mark.parametrize('cached,damaged', [(True, False), (False, False), (True, True)])
def test_model_cache_download_and_integrity_progress(tmp_path, monkeypatch, cached, damaged):
    events, downloads = [], []
    spec = {'repo': 'fixture/model', 'revision': 'pinned', 'files': {
        'weights': {'algorithm': 'sha256', 'digest': hashlib.sha256(b'weights').hexdigest()},
        'config': {'algorithm': 'git-sha1', 'digest': hashlib.sha1(b'blob 6\0config').hexdigest()}}}
    for name in spec['files']: (tmp_path/name).write_bytes(name.encode())
    if damaged: (tmp_path/'weights').write_bytes(b'damaged')
    class Missing(Exception): pass
    class Progress:
        def __init__(self, **kwargs):
            self.n, self.total, self.unit = kwargs.get('initial', 0), kwargs.get('total'), kwargs.get('unit', 'it')
            assert kwargs['disable'] is False
            self.display()
    def snapshot(repo, revision, local_files_only=False, tqdm_class=None):
        if local_files_only:
            if cached: return str(tmp_path)
            raise Missing()
        downloads.append('snapshot')
        # The pinned Linux hub has parallel byte bars with evolving totals.
        # File completion is the stable, known-total measure across backends.
        tqdm_class(total=100, unit='B')
        progress = tqdm_class(total=2)
        progress.n = 1; progress.display()
        progress.n = 2; progress.display()
        return str(tmp_path)
    def repair(repo, name, **kwargs):
        downloads.append(name); (tmp_path/name).write_bytes(name.encode())
    for name in ('huggingface_hub', 'huggingface_hub.errors', 'tqdm', 'tqdm.auto'):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules['huggingface_hub'].snapshot_download = snapshot
    sys.modules['huggingface_hub'].hf_hub_download = repair
    sys.modules['huggingface_hub.errors'].LocalEntryNotFoundError = Missing
    sys.modules['tqdm.auto'].tqdm = Progress
    monkeypatch.setattr(speech_worker, 'emit', events.append)
    assert speech_worker.model_snapshot(spec) == tmp_path
    assert downloads == (['weights'] if damaged else [] if cached else ['snapshot'])
    checks = [e for e in events if e['stage'] == 'Checking model files']
    assert [(e['completed'], e['total']) for e in checks] == [(0, 2), (1, 2), (2, 2)]
    if not cached:
        measured = [e for e in events if e['stage'] == 'Downloading model files' and e['total']]
        assert [(e['completed'], e['total']) for e in measured] == [(0, 2), (1, 2), (2, 2)]
    if damaged: assert any(e['stage'].startswith('Repairing model file:') for e in events)


def test_model_progress_is_distinct_from_concurrent_narration_and_follows_dialog(qtbot, project):
    from queue import Queue, Empty
    from PySide6.QtWidgets import QDialogButtonBox
    commands = Queue()
    w = MainWindow(); w.adopt(project); w.show()
    def finish(widget):
        if widget.job:
            widget.cancel(); qtbot.waitUntil(lambda: widget.job is None)
    qtbot.addWidget(w, before_close_func=finish)
    def work(task):
        while not task.cancelled.is_set():
            try: event = commands.get(timeout=.05)
            except Empty: continue
            if event is None: return
            task.event(event)
    w.start_job('Loading speech model…', work, preserve_playback=True)
    assert w.progress.maximum() == 1 and w.progress.isTextVisible()
    commands.put({'type':'model_progress','stage':'Checking model files','completed':4,'total':13,'unit':'files'})
    qtbot.waitUntil(lambda: w.progress.value() == 4)
    assert w.progress.maximum() == 13 and '4 / 13 files' in w.progress.text()
    assert '%' not in w.progress.text()
    commands.put({'type':'progress','stage':'Narration','completed':1,'total':2})
    qtbot.waitUntil(lambda: w.narration_progress.value() == 1)
    assert 'Checking model files' in w.progress.text()
    commands.put({'type':'model_progress','stage':'Loading model into GPU and starting speech engine'})
    qtbot.waitUntil(lambda: 'Progress not reported' in w.progress.text())
    assert w.progress.minimum() == 0 and w.progress.maximum() == 1 and w.progress.value() == 0
    w.settings[0].show_section("AI & speech engine")
    assert w.progress.parentWidget() is w.settings[0] and w.progress.isVisible()
    w.log_message('Codex is creating narration…'); w.update_timing()
    assert 'Loading model into GPU' in w.progress.text()
    assert 'Codex' in w.settings[0].status.text()
    assert w.settings[0].cancel_job.isVisible()
    w.settings[0].buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert w.progress.parentWidget() is w.footer and w.progress.isVisible()
    commands.put({'type':'model_progress','stage':'Speech model ready','completed':1,'total':1,'unit':''})
    qtbot.waitUntil(lambda: w.progress.text() == 'Speech model ready')
    assert w.progress.value() == w.progress.maximum() == 1
    commands.put(None); qtbot.waitUntil(lambda: w.job is None)
    assert w.progress.isHidden()


@pytest.mark.parametrize('total', [None, 5 * 2**30])
def test_large_and_unknown_download_totals_are_safe_and_honest(qtbot, project, total):
    from types import SimpleNamespace
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    w.job = SimpleNamespace()
    try:
        w.job_event({'type':'model_progress','stage':'Downloading runtime',
                     'completed':3 * 2**30,'total':total,'unit':'bytes'})
        assert '3072.0' in w.progress.text()
        assert 0 < w.progress.maximum() < 2**31
        assert w.progress.value() / w.progress.maximum() == pytest.approx(.6 if total else 0)
        assert ('total unknown' in w.progress.text()) == (total is None)
        assert '%' not in w.progress.text()
    finally:
        w.job = None


def test_byte_bar_does_not_fill_before_a_fractional_megabyte_download_finishes(qtbot, project):
    from types import SimpleNamespace
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project); w.job = SimpleNamespace()
    try:
        progress = {'type':'model_progress','stage':'Downloading runtime',
                    'completed':2**20,'total':2**20+200,'unit':'bytes'}
        w.job_event(progress)
        assert w.progress.value() < w.progress.maximum()
        w.job_event({**progress,'completed':progress['total']})
        assert w.progress.value() == w.progress.maximum()
    finally:
        w.job = None


@pytest.mark.parametrize('revision', ['a' * 40, 'b' * 40])
def test_update_check_reads_metadata_only_and_keeps_pinned_revision(monkeypatch, revision):
    import json
    spec = {'repo':'Qwen/test-model','revision':'a' * 40,'files':{}}
    before = json.dumps(spec, sort_keys=True)
    requests, events = [], []
    def respond(request, timeout):
        requests.append((request.full_url, timeout))
        return io.BytesIO(json.dumps({'sha':revision}).encode())
    monkeypatch.setattr(runtime.urllib.request, 'urlopen', respond)
    assert runtime.check_model_update(spec, runtime.Task(event=events.append)) == revision
    assert requests == [('https://huggingface.co/api/models/Qwen/test-model?expand=sha', 20)]
    assert json.dumps(spec, sort_keys=True) == before
    assert events[0]['stage'] == 'Checking model updates online'


@pytest.mark.parametrize('failure', ['network', 'invalid', 'cancelled', 'cancelled_network'])
def test_update_check_failure_and_cancellation_are_not_reported_as_up_to_date(monkeypatch, failure):
    import json
    task = runtime.Task()
    def respond(*args, **kwargs):
        if failure.startswith('cancelled'): task.cancelled.set()
        if failure == 'cancelled_network': raise OSError('timeout after cancellation')
        if failure == 'network': raise OSError('offline')
        return io.BytesIO(json.dumps({'sha':'invalid' if failure == 'invalid' else 'a' * 40}).encode())
    monkeypatch.setattr(runtime.urllib.request, 'urlopen', respond)
    expected = runtime.Cancelled if failure.startswith('cancelled') else RuntimeError
    with pytest.raises(expected):
        runtime.check_model_update({'repo':'Qwen/test-model'}, task)
