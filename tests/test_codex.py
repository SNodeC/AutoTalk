# SPDX-License-Identifier: MIT
"""Contract tests use an actual subprocess with scripted app-server messages."""

import sys
import os
import json

import pytest

from autotalk import codex
from autotalk.runtime import Task


@pytest.fixture
def fake_server(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX executable fake server; native Windows smoke coverage is separate")
    path = tmp_path / "codex"
    path.write_text(f"#!{sys.executable}\n" + '''
import json,sys
def send(value):
 print(json.dumps(value),flush=True)
for line in sys.stdin:
 msg=json.loads(line);method=msg.get('method');rid=msg.get('id')
 with open(__file__+'.requests','a') as log: log.write(json.dumps(msg)+'\\n')
 if method=='initialized': continue
 if method=='account/read':
  result={'account':{'type':'chatgpt','planType':'plus'}}
 elif method=='thread/start':
  result={'thread':{'id':'thread-test'}}
 elif method=='model/list':
  result={'data':[{'model':'test-vision','displayName':'Vision','isDefault':True,'inputModalities':['text','image'], 'supportedReasoningEfforts':[{'reasoningEffort':'high'}]}],'nextCursor':None}
 elif method=='turn/start':
  # Events may arrive before the request response.
  send({'method':'item/completed','params':{'threadId':'thread-test','item':{'type':'agentMessage','text':json.dumps({'scope':'Engineering'})}}})
  result={'turn':{'id':'turn-test'}}
  send({'id':rid,'result':result})
  send({'method':'turn/completed','params':{'threadId':'thread-test','turn':{'id':'turn-test','status':'completed'}}})
  continue
 else: result={}
 send({'id':rid,'result':result})
''')
    path.chmod(0o755)
    monkeypatch.setattr(codex, "ensure_codex", lambda task, **kwargs: path)
    return path


def test_app_server_keeps_early_events_and_structured_output(fake_server):
    with codex.Codex(Task(lambda _: None)) as client:
        assert client.login() == "Connected to ChatGPT (plus)"
        result = client.generate("Summarize scope", codex.SCOPE_SCHEMA, images=[fake_server])
    assert result == {"scope": "Engineering"}
    turn = next(r['params'] for r in requests(fake_server) if r['method'] == 'turn/start')
    assert turn['outputSchema'] == codex.SCOPE_SCHEMA
    assert turn['input'][0]['text'].startswith('Summarize scope ')
    assert 'compact JSON' in turn['input'][0]['text']
    assert turn['input'][1:] == [{'type': 'localImage', 'path': str(fake_server)}]


def test_response_progress_counts_only_current_turn_and_resets(fake_server, qtbot, project):
    from autotalk.app import MainWindow
    from threading import Event
    fake_server.write_text(fake_server.read_text().replace(
        "  # Events may arrive before the request response.", """  # Progress can also arrive before the request response.
  for thread,turn,text in [('foreign','turn-test','ignore'),('thread-test','old','ignore'),
                            ('thread-test','turn-test','{\"scope\":'),('thread-test','turn-test','\"Engineering\"}')]:
   send({'method':'item/agentMessage/delta','params':{'threadId':thread,'turnId':turn,'delta':text}})
"""))
    window = MainWindow(); window.adopt(project); window.show()
    release = Event()
    qtbot.addWidget(window, before_close_func=lambda _: release.set())
    events, results = [], []
    def work(task):
        def report(value):
            events.append(value); task.event(value)
        with codex.Codex(Task(event=report)) as client:
            for _ in range(2):
                results.append(client.generate('Scope', codex.SCOPE_SCHEMA))
        assert release.wait(10)
    try:
        window.start_job('Creating talk text…', work)
        qtbot.waitUntil(lambda: '23 characters received' in window.progress.text())
        assert 'total unknown' in window.progress.text() and '%' not in window.progress.text()
        assert window.progress.value() == 0 and window.progress.maximum() == 1
        if directory := os.environ.get('AUTOTALK_EVIDENCE_DIR'):
            from pathlib import Path
            target = Path(directory); target.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(target / 'codex-response-progress.png'))
        qtbot.waitUntil(lambda: len(results) == 2)
        assert results == [{'scope': 'Engineering'}] * 2
        assert [e.get('completed') for e in events if e['type'] == 'model_progress'] == [None, 9, 23, None, 9, 23]
    finally:
        release.set()
        qtbot.waitUntil(lambda: window.job is None)


def test_discovery_and_effort_validation(fake_server):
    with codex.Codex(Task()) as client:
        assert client.models()[0]["model"] == "test-vision"
        assert client.generate("Scope", codex.SCOPE_SCHEMA, model="test-vision", effort="high")["scope"] == "Engineering"
        with pytest.raises(ValueError, match="effort"):
            client.generate("Scope", codex.SCOPE_SCHEMA, model="test-vision", effort="invalid")
        assert client.generate("Revise", codex.SCOPE_SCHEMA)["scope"] == "Engineering"


@pytest.mark.parametrize('cancel', [False, True])
def test_missing_account_guides_signin_and_closes_on_cancellation(fake_server, cancel):
    from autotalk.runtime import Cancelled
    source = fake_server.read_text().replace("result={'account':{'type':'chatgpt','planType':'plus'}}", "result={'account':None}")
    source = source.replace(" elif method=='thread/start':", """ elif method=='account/login/start':
  send({'id':rid,'result':{'authUrl':'https://example.test/signin','loginId':'test-login'}})
  send({'method':'account/login/completed','params':{'loginId':'test-login','success':True}})
  continue
 elif method=='thread/start':""")
    fake_server.write_text(source)
    urls = []
    task = Task(lambda _: None)
    def open_url(url):
        urls.append(url)
        if cancel: task.cancelled.set()
    task.open_url = open_url
    client = codex.Codex(task)
    if cancel:
        with pytest.raises(Cancelled):
            with client:
                pytest.fail('Cancelled sign-in must not continue')
    else:
        with client:
            assert client.generate('Scope', codex.SCOPE_SCHEMA)['scope'] == 'Engineering'
    assert urls == ['https://example.test/signin']
    assert client.process.poll() is not None


def requests(server):
    return [json.loads(line) for line in server.with_name(server.name + '.requests').read_text().splitlines()]


@pytest.mark.parametrize('account', [None, {'type': 'apiKey'}, {'type': 'chatgpt', 'planType': 'plus'}])
def test_passive_discovery_never_starts_login_or_generation(fake_server, account):
    fake_server.write_text(fake_server.read_text().replace(
        "{'account':{'type':'chatgpt','planType':'plus'}}", repr({'account': account})))
    events, urls = [], []
    with codex.Codex(Task(open_url=urls.append, event=events.append), interactive=False) as client:
        assert client.settings['models'] == ([] if not account or account['type'] != 'chatgpt' else client.models())
        assert bool(client.login()) == bool(account and account['type'] == 'chatgpt')
    methods = [r['method'] for r in requests(fake_server)]
    assert not urls and 'account/login/start' not in methods and 'thread/start' not in methods
    assert events[-1]['type'] == 'codex_settings'
    assert ('config/read' in methods) == bool(account and account['type'] == 'chatgpt')
    assert client.process.poll() is not None


def test_configured_default_is_used_for_effort_only_and_catalog_paginates(fake_server):
    fake_server.write_text(fake_server.read_text().replace(" elif method=='model/list':", """ elif method=='config/read':
  result={'config':{'model':'configured-vision','model_reasoning_effort':'high'}}
 elif method=='model/list' and msg['params'].get('cursor')=='page2':
  result={'data':[{'model':'configured-vision','displayName':'Configured','inputModalities':['text','image'],'defaultReasoningEffort':'low','supportedReasoningEfforts':[{'reasoningEffort':'low'},{'reasoningEffort':'high'}]}],'nextCursor':None}
 elif method=='model/list':""").replace("'nextCursor':None}\n elif method=='turn/start'", "'nextCursor':'page2'}\n elif method=='turn/start'"))
    events = []
    with codex.Codex(Task(event=events.append)) as client:
        client.generate('Scope', codex.SCOPE_SCHEMA, effort='high')
    settings = [e for e in events if e['type'] == 'codex_settings'][-1]
    assert settings['model'] == 'configured-vision'
    assert settings['effort'] == 'high'
    assert len(settings['models']) == 2
    turn = next(r['params'] for r in requests(fake_server) if r['method'] == 'turn/start')
    assert turn['model'] == 'configured-vision' and turn['effort'] == 'high'


@pytest.mark.parametrize('mode', ['Prepared', 'Quick', 'Realtime'])
def test_discovery_updates_ui_without_changing_saved_selections(fake_server, qtbot, project, mode):
    from autotalk.app import MainWindow
    from autotalk.project import Project
    project.mode, project.codex_model, project.codex_effort = mode, 'test-vision', 'high'
    project.save()
    window = MainWindow(); qtbot.addWidget(window); window.adopt(project)
    window.connect_chatgpt(interactive=False)
    qtbot.waitUntil(lambda: window.job is None)
    assert 'Connected to ChatGPT' in window.settings[0].connection.text()
    assert window.settings[1].codex_model.itemText(0) == 'Account default (Vision)'
    assert window.settings[1].codex_model.currentData() == 'test-vision'
    assert window.settings[1].codex_effort.currentData() == 'high'
    assert window.settings[1].codex_model.isEnabled()
    saved = Project.load(project.manifest)
    assert (saved.codex_model, saved.codex_effort) == ('test-vision', 'high')
    # A different talk reuses account discovery but retains its own unavailable selections.
    saved.codex_model, saved.codex_effort = 'old-model', 'old-effort'
    window.adopt(saved)
    assert window.settings[1].codex_model.currentData() == 'old-model'
    assert window.settings[1].codex_effort.currentData() == 'old-effort'
    assert 'refresh availability' in window.settings[1].codex_model.currentText()


@pytest.mark.parametrize('failure', ['missing', 'offline', 'cancel'])
def test_passive_startup_failure_is_nonmodal_and_closes(fake_server, monkeypatch, qtbot, failure):
    from autotalk.app import MainWindow, QMessageBox
    from autotalk.runtime import Cancelled
    def unavailable(task, **kwargs):
        if failure == 'cancel':
            task.cancelled.set(); raise Cancelled('Cancelled')
        if failure == 'offline':
            raise OSError('Offline')
        return None
    monkeypatch.setattr(codex, 'ensure_codex', unavailable)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: pytest.fail('Startup check must not open a modal error'))
    window = MainWindow(); qtbot.addWidget(window)
    window.connect_chatgpt(interactive=False)
    qtbot.waitUntil(lambda: window.job is None)
    assert window.welcome.isEnabled() and not window.codex_settings.get('models')
    if failure != 'cancel':
        assert 'Restart AutoTalk to retry' in window.settings[0].connection.text()
    window.close()


@pytest.mark.parametrize('open_saved', [False, True])
def test_application_startup_discovers_without_pdf_and_preserves_launch_project(fake_server, monkeypatch, qtbot, qapp, project, open_saved):
    from types import SimpleNamespace
    from autotalk import app
    windows = []
    original = app.MainWindow
    def window():
        w = original(); qtbot.addWidget(w); windows.append(w); return w
    def event_loop():
        qtbot.waitUntil(lambda: bool(windows[0].codex_settings) and windows[0].job is None)
        assert bool(windows[0].project) == open_saved
        assert windows[0].settings[1 if open_saved else 0].codex_model.count() == 2
        assert windows[0].settings[1 if open_saved else 0].codex_effort.findData('high') >= 0
        windows[0].close()
        return 0
    project.save()
    monkeypatch.setattr(app, 'MainWindow', window)
    monkeypatch.setattr(app, 'QApplication', lambda *_: SimpleNamespace(
        setApplicationName=lambda *_: None, setOrganizationName=lambda *_: None, exec=event_loop))
    app.QApplication.activeModalWidget = qapp.activeModalWidget
    monkeypatch.setattr(sys, 'argv', ['autotalk'] + ([str(project.manifest)] if open_saved else []))
    assert app.main() == 0


def test_discovery_protocol_failure_can_be_retried_explicitly(fake_server, monkeypatch, qtbot):
    from autotalk.app import MainWindow, QMessageBox
    healthy = fake_server.read_text()
    fake_server.write_text(healthy.replace(" elif method=='model/list':", """ elif method=='model/list':
  send({'id':rid,'error':{'message':'Models unavailable offline'}})
  continue
 elif method=='unused':"""))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: pytest.fail('No startup modal'))
    window = MainWindow(); qtbot.addWidget(window)
    window.connect_chatgpt(interactive=False)
    qtbot.waitUntil(lambda: window.job is None)
    assert 'offline' in window.settings[0].connection.text() and window.welcome.isEnabled()
    fake_server.write_text(healthy)
    window.connect_chatgpt()
    qtbot.waitUntil(lambda: window.job is None)
    assert window.settings[1].codex_model.count() == 2 and 'Connected' in window.settings[0].connection.text()


def test_ui_displays_configured_effort_instead_of_catalog_suggestion(fake_server, qtbot, project):
    from autotalk.app import MainWindow
    fake_server.write_text(fake_server.read_text().replace(" elif method=='thread/start':", """ elif method=='config/read':
  result={'config':{'model':'test-vision','model_reasoning_effort':'high'}}
 elif method=='thread/start':""").replace("'displayName':'Vision'", "'displayName':'Vision','defaultReasoningEffort':'low'"))
    window = MainWindow(); qtbot.addWidget(window); window.adopt(project)
    window.connect_chatgpt(interactive=False)
    qtbot.waitUntil(lambda: window.job is None)
    assert window.settings[1].codex_effort.currentText() == 'Codex default (high)'
    assert window.settings[1].codex_effort.currentData() == ''
    assert project.codex_model == project.codex_effort == ''


def test_client_closes_input_without_waiting_for_forced_shutdown(fake_server):
    import time
    fake_server.write_text(fake_server.read_text().replace('import json,sys',
        'import json,sys,signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)'))
    started = time.monotonic()
    with codex.Codex(Task(), interactive=False) as client:
        assert client.settings['models']
    assert time.monotonic() - started < 2
    assert client.process.poll() is not None


@pytest.mark.parametrize('signed_in', [False, True])
def test_auth_buttons_follow_account_and_logout_preserves_talk(fake_server, qtbot, project, signed_in):
    from PySide6.QtCore import Qt
    from autotalk.app import MainWindow
    from autotalk.project import Project
    project.codex_model, project.codex_effort = 'test-vision', 'high'
    project.save()
    healthy = fake_server.read_text()
    if not signed_in:
        fake_server.write_text(healthy.replace("{'account':{'type':'chatgpt','planType':'plus'}}", "{'account':None}"))
    window = MainWindow(); qtbot.addWidget(window); window.adopt(project)
    window.connect_chatgpt(interactive=False)
    assert not window.settings[0].codex_signin.isEnabled() and not window.settings[0].codex_signout.isEnabled()
    qtbot.waitUntil(lambda: window.job is None)
    assert window.settings[0].codex_signin.isEnabled() == (not signed_in)
    assert window.settings[0].codex_signout.isEnabled() == signed_in
    if not signed_in:
        fake_server.write_text(healthy)
        qtbot.mouseClick(window.settings[0].codex_signin, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: window.job is None)
        assert not window.settings[0].codex_signin.isEnabled() and window.settings[0].codex_signout.isEnabled()
    before = len(requests(fake_server))
    qtbot.mouseClick(window.settings[0].codex_signout, Qt.MouseButton.LeftButton)
    assert not window.settings[0].codex_signin.isEnabled() and not window.settings[0].codex_signout.isEnabled()
    qtbot.waitUntil(lambda: window.job is None)
    assert window.settings[0].codex_signin.isEnabled() and not window.settings[0].codex_signout.isEnabled()
    assert not window.codex_settings['signed_in'] and window.codex_settings['models'] == []
    assert window.settings[1].codex_model.currentData() == 'test-vision'
    assert window.settings[1].codex_effort.currentData() == 'high'
    saved = Project.load(project.manifest)
    assert (saved.codex_model, saved.codex_effort) == ('test-vision', 'high')
    methods = [r['method'] for r in requests(fake_server)[before:]]
    assert 'account/logout' in methods
    assert not set(methods) & {'account/login/start', 'model/list', 'config/read', 'thread/start'}


def test_catalog_failure_keeps_account_known_and_signout_available(fake_server, qtbot, monkeypatch):
    from autotalk.app import MainWindow, QMessageBox
    healthy = fake_server.read_text()
    fake_server.write_text(healthy.replace(" elif method=='model/list':", """ elif method=='model/list':
  send({'id':rid,'error':{'message':'Catalog offline'}})
  continue
 elif method=='unused':"""))
    window = MainWindow(); qtbot.addWidget(window)
    window.connect_chatgpt(interactive=False)
    qtbot.waitUntil(lambda: window.job is None)
    assert window.codex_settings['signed_in'] and not window.codex_settings['models']
    assert not window.settings[0].codex_signin.isEnabled() and window.settings[0].codex_signout.isEnabled()
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: errors.append(a[-1]))
    fake_server.write_text(healthy.replace(" elif method=='thread/start':", """ elif method=='account/logout':
  send({'id':rid,'error':{'message':'Sign-out failed'}})
  continue
 elif method=='thread/start':"""))
    window.settings[0].codex_signout.click()
    qtbot.waitUntil(lambda: window.job is None)
    assert errors == ['Sign-out failed']
    assert window.codex_settings['signed_in']
    assert not window.settings[0].codex_signin.isEnabled() and window.settings[0].codex_signout.isEnabled()
