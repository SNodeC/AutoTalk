"""Contract tests use an actual subprocess with scripted app-server messages."""

import sys

import pytest

from autotalk import codex
from autotalk.runtime import Task


@pytest.fixture
def fake_server(tmp_path, monkeypatch):
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


def test_app_server_keeps_early_events_and_structured_output(fake_server):
    with codex.Codex(Task(lambda _: None)) as client:
        assert client.login() == "Connected to ChatGPT (plus)"
        result = client.generate("Summarize scope", codex.SCOPE_SCHEMA)
    assert result == {"scope": "Engineering"}
