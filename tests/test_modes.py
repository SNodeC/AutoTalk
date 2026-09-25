import copy
import json
import shutil
import threading

import pytest

from autotalk import services, speech_worker
from autotalk.media import AudioFile
from autotalk.project import Project
from autotalk.runtime import Cancelled, Task


@pytest.fixture
def local_speech(monkeypatch):
    class Backend:
        def generate(self, passage, settings):
            yield b"\0\0" * 2400
            yield b"\1\0" * 2400
    class Session:
        def __init__(self, task, config): self.task, self.config = task, config
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, request, on_event=None):
            def emit(value):
                self.task.check()
                (on_event or self.task.event)(value)
            monkeypatch.setattr(speech_worker, "emit", emit)
            speech_worker.generate_items(Backend(), request, self.config)
    monkeypatch.setattr(services, "SpeechSession", Session)
    def command(task, request):
        with Session(task, request) as session: session.generate(request)
    monkeypatch.setattr(services, "speech_command", command)


def test_stream_files_remain_readable_through_completion(project, local_speech):
    audio_events = []
    def event(value):
        if value["type"] == "audio":
            audio_events.append(value)
            assert len(AudioFile(value["path"], frames=value["frames"], offset=value["offset"]).read(0, 10)) == 10
    services.prepare(project, Task(event=event))
    assert project.prepared
    assert Project.load(project.manifest).prepared
    for value in audio_events:
        assert AudioFile(value["path"]).frames >= value["frames"]


def test_cancelled_stream_retains_only_completed_slides(project, local_speech):
    task = Task()
    def event(value):
        if value["type"] == "slide_ready": task.cancelled.set()
    task.event = event
    with pytest.raises(Cancelled): services.prepare(project, task)
    reopened = Project.load(project.manifest)
    assert reopened.ready(reopened.slides[0])
    assert not reopened.ready(reopened.slides[1])


@pytest.mark.parametrize("policy,fit", [("once", False), ("fit", True), ("require", True)])
def test_quick_mode_uses_automatic_defaults(project, monkeypatch, policy, fit):
    project.mode, project.quick_timing = "Quick", policy
    project.codex_model, project.codex_effort = "configured-model", "high"
    project.voice.speaker = "Aiden"
    seen = {}
    class Client:
        def generate(self, prompt, schema, images, **options):
            seen.update(options=options, data=json.loads(prompt.split("INPUT:\n")[1]))
            return {"title": "Talk", "slides": [{"page": s.page, "narration": "Welcome.", "notes": "", "budget_seconds": 1} for s in project.slides]}
    monkeypatch.setattr(services, "narrate", lambda p,t: services.apply_narration(p, services.narration_result(p,t,Client()),t))
    monkeypatch.setattr(services, "prepare", lambda p,t,fit: seen.update(fit=fit) or p)
    services.workflow(project, Task())
    assert seen["fit"] is fit
    assert seen["data"]["scope"] == ""
    assert seen["options"] == {"model": "", "effort": ""}
    assert project.effective_voice.speaker == "Ryan"
    assert project.voice.speaker == "Aiden"


def test_realtime_writes_next_batch_while_first_batch_synthesizes(project, local_speech, monkeypatch):
    for original in project.slides[:2]:
        slide = copy.deepcopy(original); slide.page += 2
        project.slides.append(slide)
        shutil.copy2(project.image(original), project.image(slide))
    project.mode, project.realtime_script = "Realtime", "ahead"
    writing, speech = threading.Event(), threading.Event()
    class Client:
        def __init__(self, task): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate(self, prompt, schema, images, **options):
            pages = json.loads(prompt.split("INPUT:\n")[1])["requested_pages"] if "INPUT:\n" in prompt else [1,2,3,4]
            if pages == [3,4]:
                writing.set()
                assert speech.wait(3)
            return {"title": "Talk", "slides": [{"page": p, "narration": f"Page {p}.", "notes": "", "budget_seconds": 1} for p in pages]}
    monkeypatch.setattr(services, "Codex", Client)
    synthesize = services.synthesize
    def overlapping(p,t,**kwargs):
        if kwargs["pages"] == [1,2]:
            assert writing.wait(3)
            speech.set()
        return synthesize(p,t,**kwargs)
    monkeypatch.setattr(services, "synthesize", overlapping)
    services.workflow(project, Task())
    assert project.prepared
    assert all(s.narration == f"Page {s.page}." for s in project.slides)
