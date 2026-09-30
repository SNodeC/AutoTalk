# SPDX-License-Identifier: MIT
import copy
import inspect
import random
import sys
from collections import Counter
from dataclasses import asdict

import pytest

from autotalk.app import MainWindow
from autotalk.project import Passage, Project
from conftest import make_audio


def outcome(function, *args, **kwargs):
    try:
        return ('value', function(*args, **kwargs))
    except ValueError as error:
        return ('error', error.args)


def queries(project):
    return [outcome(getattr(project, name), slide) for slide in project.slides
            for name in ('speech_key', 'ready', 'text_ready', 'audio')] + [
                outcome(project.asset, name) for name in ('slides.pdf', '../outside.wav')]


@pytest.mark.parametrize('seed', range(12))
def test_randomized_pass_matches_uncached_after_mutations(project, seed):
    make_audio(project)
    rng = random.Random(seed)
    for _ in range(40):
        slide = rng.choice(project.slides)
        choice = rng.randrange(8)
        if choice == 0:
            project.set_narration(slide, rng.choice(('', 'Fresh words', '[German] Hallo')))
        elif choice == 1:
            project.set_setting('language_policy', rng.choice(('mixed', 'slide', 'version')))
        elif choice == 2:
            slide.passages = [Passage('Hi', 'English'), Passage('Hallo', 'German')]
        elif choice == 3:
            slide.overrides['delivery.instructions'] = str(rng.random())
        elif choice == 4:
            slide.audio_key = rng.choice(('', slide.audio_key))
        elif choice == 5:
            project.select_language(rng.choice(('English', 'German')))
        elif choice == 6:
            project.active_version = rng.choice(list(project.versions))
        else:
            slide.included = not slide.included
        expected = queries(project)
        with project.pass_cache():
            assert queries(project) == expected
            with project.pass_cache():
                assert queries(project) == expected
        assert queries(project) == expected
        assert not hasattr(project, '_pass_memo')


def test_mutation_invalidates_and_snapshots_exclude_cache(project):
    make_audio(project)
    with project.pass_cache():
        assert project.ready(project.slides[0])
        assert project._pass_memo
        assert '_pass_memo' not in asdict(project)
        for duplicate in (copy.copy(project), copy.deepcopy(project)):
            assert not hasattr(duplicate, '_pass_memo')
        project.save()
        assert '_pass_memo' not in project.manifest.read_text()
        project.set_narration(project.slides[0], 'Changed text')
        assert not project._pass_memo
        assert not project.ready(project.slides[0])
        project.set_setting('delivery.instructions', 'Speak quietly')
        assert not project._pass_memo
        project.speech_key(project.slides[0])
        project.select_language('German')
        assert not project._pass_memo
        assert not project.text_ready(project.slides[0])
    assert not hasattr(project, '_pass_memo')


def test_exception_is_computed_once_and_ready_stays_false(project):
    project.language_policy = 'version'
    project.slides[0].narration = '[German] Hallo'
    calls = Counter()
    code = inspect.unwrap(Project.speech_key).__code__
    def trace(frame, event, arg):
        if event == 'call' and frame.f_code is code:
            calls['speech_key'] += 1
    sys.setprofile(trace)
    try:
        with project.pass_cache():
            first = outcome(project.speech_key, project.slides[0])
            assert first[0] == 'error'
            assert outcome(project.speech_key, project.slides[0]) == first
            assert not project.ready(project.slides[0])
            assert not project.ready(project.slides[0])
    finally:
        sys.setprofile(None)
    assert calls['speech_key'] == 1
    assert outcome(project.speech_key, project.slides[0]) == first


def test_full_refresh_queries_each_slide_once(qtbot, tmp_path):
    from tools.bench_ui import prepared_project
    project = prepared_project(tmp_path/'large', 60)
    w = MainWindow(); qtbot.addWidget(w); w.adopt(project)
    codes = {inspect.unwrap(getattr(Project, name)).__code__: name
             for name in ('speech_key', 'ready', 'text_ready', 'asset')}
    calls = Counter()
    def trace(frame, event, arg):
        if event == 'call' and frame.f_code in codes:
            calls[codes[frame.f_code]] += 1
    sys.setprofile(trace)
    try:
        w.refresh()
    finally:
        sys.setprofile(None)
    assert 0 < calls['speech_key'] <= 60
    assert 0 < calls['ready'] <= 60
    assert 0 < calls['text_ready'] <= 60
    assert 0 < calls['asset'] <= 120
