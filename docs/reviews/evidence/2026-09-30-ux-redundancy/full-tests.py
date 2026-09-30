import json, os, subprocess, sys
from pathlib import Path
root = Path.cwd()
out = root/'artifacts/ux-redundancy'
def audio_state():
    return {kind: subprocess.check_output(['pactl','--format=json','list',kind],text=True) for kind in ('sinks','sources')}
(out/'audio-before.json').write_text(json.dumps(audio_state()))
name='autotalk_ux_verification'
module=subprocess.check_output(['pactl','load-module','module-null-sink','sink_name='+name,'channels=2','channel_map=front-left,front-right'],text=True).strip()
try:
    for tag,python in [('wheel','.venv/bin/python'),('native','artifacts/open-tasks/venv-qt610/bin/python')]:
        if len(sys.argv)>1 and tag not in sys.argv[1:]:
            continue
        env=os.environ.copy()
        env.update(QT_QPA_PLATFORM='xcb',PULSE_SINK=name,PULSE_SOURCE=name+'.monitor',PIPEWIRE_PROPS=json.dumps({'target.object':name,'node.dont-reconnect':False}))
        if tag=='native':
            env['PYTHONPATH']=str(root/'build/system-qt')+':'+str(root/'src')
            env['LD_LIBRARY_PATH']=str(root/'build/system-qt/PySide6/Qt/lib')+':'+str(root/'artifacts/open-tasks/venv-qt610/lib/python3.12/site-packages/shiboken6')
        with (out/(tag+'-full.log')).open('w') as log:
            result=subprocess.run(['xvfb-run','-a',python,'-m','pytest','-q'],env=env,stdout=log,stderr=subprocess.STDOUT)
        print(tag, result.returncode, flush=True)
finally:
    subprocess.run(['pactl','unload-module',module],check=True)
    (out/'audio-after.json').write_text(json.dumps(audio_state()))
