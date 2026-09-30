"""Old manifests retain evidence; absent language metadata is never invented."""
import json

import pytest

from autotalk.project import Project
from conftest import make_audio


@pytest.mark.parametrize('language', ['', 'Chinese'])
@pytest.mark.parametrize('origin', ['manual', 'generated', 'translation'])
def test_v4_language_migration_and_backup(project, language, origin):
    project.defaults = {'language': 'Chinese'}
    if language:
        project.language = language
    for slide in project.slides:
        project.set_narration(slide, '这是中文演讲。')
    make_audio(project)
    raw = json.loads(project.manifest.read_text())
    raw['version'] = 4
    for slide in raw['versions']['main']['slides']:
        slide.pop('narration_language')
        slide['narration_origin'] = origin
    text = json.dumps(raw, ensure_ascii=False)
    project.manifest.write_text(text)
    loaded = Project.load(project.manifest)
    loaded.defaults = {'language': 'German'}
    expected = bool(language) and origin != 'translation'
    assert loaded.prepared == expected
    assert all(loaded.text_ready(s) == expected for s in loaded.slides)
    assert all(s.narration == '这是中文演讲。' for s in loaded.slides)
    assert project.manifest.read_text() == text
    loaded.save()
    assert loaded.manifest.with_suffix('.v4-backup.json').read_text() == text
    saved = json.loads(loaded.manifest.read_text())
    assert saved['version'] == 5 and 'narration_origin' not in saved['versions']['main']['slides'][0]
    reopened = Project.load(loaded.manifest)
    reopened.defaults = loaded.defaults
    assert reopened.prepared == expected


def test_reset_to_same_language_then_reopen_under_new_defaults(project):
    project.defaults = {'language': 'Chinese'}
    project.language = 'Chinese'
    for slide in project.slides:
        project.set_narration(slide, '这是中文演讲。')
    make_audio(project)
    project.set_setting('language', None, inherit=True)
    assert project.prepared and project.version.language == ''
    project.save()
    loaded = Project.load(project.manifest)
    loaded.defaults = {'language': 'German'}
    assert not loaded.prepared and not any(loaded.text_ready(s) for s in loaded.slides)
    loaded.defaults = {'language': 'Chinese'}
    assert loaded.prepared


@pytest.mark.parametrize('language', [None, 0, False, 'Invalid language'])
def test_narration_language_is_validated_on_load(project, language):
    project.save()
    raw = json.loads(project.manifest.read_text())
    raw['versions']['main']['slides'][0]['narration_language'] = language
    project.manifest.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='narration language'):
        Project.load(project.manifest)


def test_source_language_and_explicit_passages_survive_reopening(project):
    project.set_narration(project.slides[0], 'Authored words.\n\n[French] Bonjour.')
    make_audio(project)
    project.set_setting('language', 'German', project.slides[0])
    project.save()
    loaded = Project.load(project.manifest)
    assert loaded.slides[0].narration_language == 'English'
    assert loaded.slides[0].passages[1].language == 'French'
    assert not loaded.text_ready(loaded.slides[0])
    loaded.set_setting('language', 'English', loaded.slides[0])
    assert loaded.prepared
