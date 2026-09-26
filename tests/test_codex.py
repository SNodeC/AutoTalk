"""Contract tests use an actual subprocess with scripted app-server messages."""

import sys
import os

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
    monkeypatch.setattr(codex, "ensure_codex", lambda task: path)
    return path


def test_app_server_keeps_early_events_and_structured_output(fake_server):
    with codex.Codex(Task(lambda _: None)) as client:
        assert client.login() == "Connected to ChatGPT (plus)"
        result = client.generate("Summarize scope", codex.SCOPE_SCHEMA)
    assert result == {"scope": "Engineering"}


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
