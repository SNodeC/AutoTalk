# SPDX-License-Identifier: MIT
"""Settings edits are isolated; Save is the sole document commit boundary."""
import copy
import random
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QWidget
from autotalk.app import MainWindow
from autotalk.project import Project, SETTING_DEFAULTS, Voice, Clip
from autotalk.settings import apply_edit
from autotalk.settings_schema import SCHEMA, CUSTOM_OWNED, PAGES
from conftest import make_audio


def snapshot(project):
    return copy.deepcopy(asdict(project))


def test_schema_complete_and_scopes():
    assert set(SETTING_DEFAULTS) == (set(SCHEMA) & set(SETTING_DEFAULTS)) | CUSTOM_OWNED
    assert not CUSTOM_OWNED & set(SCHEMA)
    for key, spec in SCHEMA.items():
        if key in SETTING_DEFAULTS:
            assert set(spec.scopes) <= set(SETTING_DEFAULTS[key][1])


@pytest.mark.parametrize('scope',[0,1,2])
def test_edit_isolated_and_cancel_never_saves(qtbot,project,monkeypatch,scope):
    project.save()
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    w.minutes.setValue(7)
    before, defaults = snapshot(project), copy.deepcopy(w.defaults)
    manifest, mtime = project.manifest.read_bytes(), project.manifest.stat().st_mtime_ns
    d=w.settings[scope];d.show_section()
    refresh=Mock(wraps=w.refresh);changed=Mock(wraps=w.configuration_changed)
    monkeypatch.setattr(w,'refresh',refresh);monkeypatch.setattr(w,'configuration_changed',changed)
    from test_surface_refresh import snapshot as widget_snapshot
    def main_state():
        widgets = [w] + w.findChildren(QWidget)
        return [state for widget, state in zip(widgets, widget_snapshot(w)) if QWidget.window(widget) is w]
    ui_before = main_state()
    d.edit_setting('delivery.style','Conversational')
    d.edit_setting('voice',Voice(speaker='Aiden'))
    assert d.setting_value('voice').speaker=='Aiden'
    assert snapshot(project)==before and w.defaults==defaults
    assert main_state() == ui_before
    assert refresh.call_count==changed.call_count==0
    d.reject()
    assert refresh.call_count==changed.call_count==0
    assert snapshot(project)==before and w.defaults==defaults and w.isWindowModified()
    assert project.manifest.read_bytes()==manifest and project.manifest.stat().st_mtime_ns==mtime


@pytest.mark.parametrize('scope',[0,1,2])
def test_save_one_refresh_mix_and_write(qtbot,project,monkeypatch,scope):
    make_audio(project)
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[scope];d.show_section()
    d.edit_setting('delivery.style','Conversational')
    refresh=Mock(wraps=w.refresh);mix=Mock(wraps=w.transport.refresh_audio)
    save=Mock(wraps=project.save);config=Mock(wraps=w.config.setValue)
    monkeypatch.setattr(w,'refresh',refresh);monkeypatch.setattr(w.transport,'refresh_audio',mix)
    monkeypatch.setattr(project,'save',save);monkeypatch.setattr(w.config,'setValue',config)
    d.accept()
    assert not d.isVisible()
    assert refresh.call_count==mix.call_count==1
    assert save.call_count==(0 if scope==0 else 1)
    assert config.call_count==(1 if scope==0 else 0)
    assert project.setting('delivery.style',project.slides[0] if scope==2 else None)=='Conversational'
    assert ('audio needs updating' in w.status.text()) == (scope != 2)


@pytest.mark.parametrize('seed',range(8))
def test_replay_matches_individual_edits(qtbot,project,seed):
    make_audio(project)
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[1];d.show_section()
    expected=copy.deepcopy(project)
    import shutil
    media=project.root/'media/test.wav';media.parent.mkdir();shutil.copy2(project.audio(project.slides[0]),media)
    rng=random.Random(seed)
    choices=[('language','German',False),('language','English',False),('language',None,True),
             ('voice',Voice(speaker='Aiden'),False),('voice',None,True),
             ('delivery.style','Conversational',False),('delivery.attributes.energy','High',False),
             ('pause_seconds',0,False),('pause_seconds',None,True),
             ('scope','Conference context',False),('sources',['https://example.org'],False),
             ('background',Clip('media/test.wav','123',1),False),('background',None,False)]
    for _ in range(25):
        operation=copy.deepcopy(rng.choice(choices))
        d.edit_setting(*operation)
        key,value,inherit=operation
        if key in SETTING_DEFAULTS:
            expected.set_setting(key,value,inherit=inherit)
        else:
            setattr(expected,key,value)
    # New version ids are random; compare per-language content, not uuid spelling.
    assert d.project.language==expected.language
    def versions(p):
        return sorted((v.language,asdict(v)) for v in p.versions.values())
    assert versions(d.project)==versions(expected)
    draft=snapshot(d.project)
    d.accept()
    assert versions(project)==sorted((v['language'],v) for v in draft['versions'].values())
    def normalized(p):
        state = snapshot(p)
        state['active_version'] = p.language
        state['versions'] = dict(versions(p))
        return state
    assert normalized(project) == normalized(expected)


def test_pin_and_clip_edits_are_logged(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[1];d.show_section();d.pin()
    assert not project.overrides.get('pause_seconds')
    d.accept()
    assert all(key in project.overrides or key=='language' for key,(_,scopes) in SETTING_DEFAULTS.items() if 1 in scopes)
    d=w.settings[2];d.show_section('Audio & recording')
    make_audio(project)
    clip=Clip(project.slides[0].audio_file,project.slides[0].audio_sha256,.3)
    d.edit_setting('clips',[clip]);d.assets.clip_gain.setValue(.5)
    assert not project.slides[0].clips and d.slide.clips[0].gain==.5
    d.accept()
    assert project.slides[0].clips[0].gain==.5


def test_stale_save_refused(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[1];d.show_section();d.edit_setting('audience','Draft audience')
    updated=copy.deepcopy(project);updated.audience='New result'
    w.accept_result(updated);d.accept()
    assert d.isVisible() and 'changed while' in d.status.text()
    assert w.project.audience=='New result'
    d.reject()


def test_cancel_cleans_only_session_media(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    old=project.root/'media/old.wav';old.parent.mkdir();old.write_bytes(b'old')
    d=w.settings[1];d.show_section()
    new=project.root/'media/new.wav';new.write_bytes(b'new')
    shared=project.root/'media/shared.wav';shared.write_bytes(b'shared')
    project.background=Clip('media/shared.wav','123',1)
    d.edit_setting('background',Clip('media/new.wav','456',1));d.reject()
    assert old.exists() and shared.exists() and not new.exists()


def test_project_job_blocks_save_but_not_cancel(qtbot,project,monkeypatch):
    import threading
    project.save();before=project.manifest.read_bytes();mtime=project.manifest.stat().st_mtime_ns
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[1];d.show_section();release=threading.Event()
    try:
        d.start_job('Reading conference…',lambda task:(release.wait(2),{'scope':'draft'})[1],
                    lambda result:d.edit_setting('scope',result['scope']),project_returning=True)
        assert not d.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
        assert d.buttons.button(QDialogButtonBox.StandardButton.Cancel).isEnabled()
        d.reject();assert not d.isVisible()
    finally:
        release.set();qtbot.waitUntil(lambda:w.job is None)
    assert project.manifest.read_bytes()==before and project.manifest.stat().st_mtime_ns==mtime
    assert project.scope!='draft'


def test_page_order_and_inheritance(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    for scope,d in w.settings.items():
        d.show_section()
        names=[d.navigation.item(i).text() for i in range(d.navigation.count())]
        assert names==[page for page in PAGES if page in names]
        for key,field in d.fields.items():
            if key in SETTING_DEFAULTS:
                assert field.source.text() in ('from app','from talk','set here','built-in')
                assert field.reset.text()=='Reset'
        assert 'after' not in d.fields and 'pause_seconds' not in d.fields if scope==2 else 'mode' in d.fields
        d.reject()
    for field in (w.inspector.after_field,w.inspector.pause_field):
        assert field.reset.text()=='Reset' and field.editor.isEnabled()


def test_preferences_immediate_close_only(qtbot,project):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.preferences;d.show_section()
    assert d.buttons.standardButtons()==QDialogButtonBox.StandardButton.Close
    d.screen.addItem('Other display',1);d.screen.setCurrentIndex(1)
    d.show_section('Speech engine')
    next(b for b in d.gpu_retention.buttons() if b.property('value')=='idle').click()
    d.reject()
    assert w.config.value('gpu_retention')=='idle' and w.speech.retention=='idle'
    assert w.config.value('presentation_display')=='Other display'


def test_every_setting_has_one_editor_per_scope(qtbot,project):
    from collections import Counter
    w=MainWindow();qtbot.addWidget(w);w.adopt(project)
    owners=Counter((widget.property('setting_key'),widget.property('setting_scope'))
                   for widget in w.findChildren(QWidget) if widget.property('value_editor'))
    for key,(_,scopes) in SETTING_DEFAULTS.items():
        for scope in scopes:
            assert owners[key,scope]==1,(key,scope,owners[key,scope])
    assert all(count==1 for count in owners.values())
    assert owners['target_minutes',1]==1


@pytest.mark.parametrize('scope',[0,1,2])
def test_reference_import_cancel_preserves_library_and_existing_files(qtbot,project,tmp_path,scope,monkeypatch):
    import wave
    from autotalk import voices, app
    monkeypatch.setattr(app,'data_dir',lambda:tmp_path/'data')
    monkeypatch.setattr(voices,'data_dir',lambda:tmp_path/'library')
    ref=tmp_path/'reference.wav'
    with wave.open(str(ref),'wb') as audio:
        audio.setparams((1,2,24000,0,'NONE','not compressed'));audio.writeframes(b'\x01\0'*4*24000)
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[scope];d.show_section();before=project.manifest.read_bytes()
    d.voice.set_voice(ref)
    path=d.project.asset(d.setting_value('voice').references['default'].file)
    assert path.is_file()
    voices.save_voice(d.voice.voice_context(),'Keep in library')
    d.reject()
    assert not path.exists() and list((tmp_path/'library').rglob('*.wav'))
    assert project.manifest.read_bytes()==before


@pytest.mark.parametrize('kind',['clip','background','conference'])
@pytest.mark.parametrize('accept',[False,True])
def test_dialog_jobs_only_commit_on_save(qtbot,project,tmp_path,monkeypatch,kind,accept):
    from autotalk import settings_components as components
    make_audio(project)
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[2 if kind=='clip' else 1];d.show_section()
    before=project.manifest.read_bytes();mtime=project.manifest.stat().st_mtime_ns
    if kind=='conference':
        d.edit_setting('conference_url','https://example.org')
        monkeypatch.setattr(components,'extract_scope',lambda *a,**kw:{'scope':'Draft scope','sources':['https://example.org']})
        d.conference.read_conference()
    else:
        monkeypatch.setattr(components.QFileDialog,'getOpenFileName',lambda *a,**kw:(str(project.audio(project.slides[0])),''))
        (d.assets.add_clip if kind=='clip' else d.assets.add_background)()
    qtbot.waitUntil(lambda:w.job is None,timeout=10000)
    assert project.manifest.read_bytes()==before and project.manifest.stat().st_mtime_ns==mtime
    assert not project.background and not project.slides[0].clips and project.scope!='Draft scope'
    (d.accept if accept else d.reject)()
    loaded=Project.load(project.manifest)
    actual=loaded.slides[0].clips if kind=='clip' else loaded.background if kind=='background' else loaded.scope=='Draft scope'
    assert bool(actual)==accept
    if not accept:
        assert project.manifest.read_bytes()==before and project.manifest.stat().st_mtime_ns==mtime
        assert not list(project.root.glob('media/*.wav'))


def test_cancelled_late_import_cannot_edit_reopened_draft(qtbot,project):
    import threading
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[1];d.show_section();release=threading.Event()
    media=project.root/'media/late.wav';media.parent.mkdir()
    def worker(task):
        release.wait(2);media.write_bytes(b'late');return Clip('media/late.wav','123',1)
    try:
        d.start_job('Importing…',worker,lambda clip:d.edit_setting('background',clip),project_returning=True)
        d.reject();d.show_section();d.edit_setting('audience','Next draft')
    finally:
        release.set();qtbot.waitUntil(lambda:w.job is None)
    assert d.project.audience=='Next draft' and d.project.background is None
    assert not media.exists()
    assert d.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    d.reject()


def test_failed_save_can_be_retried_without_a_stale_generation(qtbot,project,monkeypatch):
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[1];d.show_section();d.edit_setting('audience','Retry me')
    save=project.save;errors=[]
    monkeypatch.setattr(w,'error',errors.append)
    def fail(): raise OSError('disk unavailable')
    monkeypatch.setattr(project,'save',fail)
    d.accept();assert d.isVisible() and errors
    monkeypatch.setattr(project,'save',save)
    d.accept()
    assert not d.isVisible() and Project.load(project.manifest).audience=='Retry me'


@pytest.mark.parametrize('scope,caption,page,focus',[
    (0,'Account settings…','Account','codex_signin'),(1,'Account settings…','Account','codex_signin'),
    (0,'Speech engine settings…','Speech engine','engine_state'),(1,'Speech engine settings…','Speech engine','engine_state'),
    (0,'Display && sound settings…','Display & sound','screen'),(1,'Display && sound settings…','Display & sound','screen')])
def test_scoped_links_open_preferences_not_another_transaction(qtbot,project,scope,caption,page,focus):
    from PySide6.QtWidgets import QApplication,QPushButton
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.settings[scope];d.show_section('AI model' if page!='Display & sound' else 'Timing & playback')
    d.edit_setting('delivery.style','Storytelling')
    next(b for b in d.findChildren(QPushButton) if b.text()==caption).click()
    assert QApplication.activeModalWidget() is w.preferences and d.isVisible()
    assert w.preferences.navigation.currentItem().text()==page
    assert getattr(w.preferences,focus).isVisible()
    assert d.setting_value('delivery.style')=='Storytelling' and project.delivery.style!='Storytelling'
    w.preferences.reject();d.reject()


@pytest.mark.parametrize('page',['Display & sound','Account','Speech engine'])
def test_navigation_shortcuts_do_not_cross_preferences(qtbot,project,page):
    from PySide6.QtCore import Qt
    w=MainWindow();qtbot.addWidget(w);w.adopt(project);w.show()
    d=w.preferences;d.show_section(page)
    qtbot.keyClick(d,Qt.Key_PageDown,Qt.ControlModifier)
    w.next_action.trigger()
    assert w.transport.index==0
    d.reject()
