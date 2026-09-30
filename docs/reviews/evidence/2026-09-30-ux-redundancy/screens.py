import json, os, tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QToolButton, QLabel
from autotalk.app import MainWindow
from autotalk.services import import_pdf
from autotalk.runtime import Task

app=QApplication([])
scale=os.environ.get('QT_SCALE_FACTOR','1')
output=Path('artifacts/ux-redundancy/screens');output.mkdir(exist_ok=True)
records=[]
base=QPalette(app.palette())
def capture(widget,name,size):
    widget.resize(*size);app.processEvents();QTest.qWait(500)
    assert widget.size().toTuple()==size,(name,widget.size().toTuple(),size)
    if hasattr(widget, 'buttons'):
        assert widget.rect().contains(widget.buttons.mapTo(widget, widget.buttons.rect().bottomRight())), name
    name=f'{name}-scale{scale}.png'
    widget.grab().save(str(output/name))
    records.append({'file':name,'logical_size':size,'style':app.style().objectName()})
with tempfile.TemporaryDirectory() as tmp:
    pdf=next(Path('/home/voc/projects/Hagenberg/DACHS/2026/DACHS').glob('*.pdf'))
    p=import_pdf(pdf,Path(tmp)/'talk',Task(lambda _:None))
    p.title='Kollaborative KI-gestützte Softwareentwicklung in der Lehre'
    p.select_language('German')
    p.set_narration(p.slides[0],'Herzlich willkommen. Heute geht es um kollaborative KI-gestützte Softwareentwicklung in der Lehre und unsere Erfahrungen mit Codex.')
    w=MainWindow();w.adopt(p);w.show();app.processEvents()
    if scale=='1':
        for mode in ('Prepared','Quick','Realtime'):
            w.mode.setCurrentText(mode)
            for size in ((940,680),(1100,850)):
                capture(w,f'main-{mode}-{size[0]}',size)
        w.mode.setCurrentText('Realtime')
        for scope,dialog in w.settings.items():
            dialog.show_section()
            for index in range(dialog.navigation.count()):
                if dialog.navigation.item(index).isHidden():continue
                title=dialog.navigation.item(index).text()
                for size in ((760,580),(920,760)):
                    dialog.show_section(title);dialog.resize(*size);app.processEvents();QTest.qWait(500)
                    bar=dialog.pages.currentWidget().verticalScrollBar()
                    positions=list(range(0,bar.maximum()+1,max(1,bar.pageStep()-40)))
                    if positions[-1]!=bar.maximum(): positions.append(bar.maximum())
                    for n,y in enumerate(positions):
                        bar.setValue(y);app.processEvents()
                        capture(dialog,f'dialog-{scope}-{index}-{size[0]}-part{n}',size)
            dialog.reject()
    for dark in (False,True):
        palette=QPalette(base)
        if dark:
            for role,value in ((QPalette.Window,'#31363b'),(QPalette.Base,'#232629'),(QPalette.AlternateBase,'#31363b'),(QPalette.Button,'#31363b'),(QPalette.WindowText,'#eff0f1'),(QPalette.Text,'#eff0f1'),(QPalette.ButtonText,'#eff0f1'),(QPalette.Mid,'#62686e')):
                palette.setColor(role,QColor(value))
        app.setPalette(palette);app.processEvents()
        w.mode.setCurrentText('Prepared')
        next(b for b in w.editor.findChildren(QToolButton) if b.text()=='Timing').setChecked(True)
        capture(w,f'inspector-{ "dark" if dark else "light"}',(940,680))
        dialog=w.settings[1];dialog.show_section('Presentation & recording')
        dialog.resize(760,580);app.processEvents()
        bar=dialog.pages.currentWidget().verticalScrollBar()
        for part,y in [('top',0),('bottom',bar.maximum())]:
            bar.setValue(y);app.processEvents()
            capture(dialog,f'recording-{ "dark" if dark else "light"}-{part}',(760,580))
        dialog.reject()
    w.close()
(output/f'manifest-{scale}.json').write_text(json.dumps(records,indent=2))
print('Captured',len(records),'screenshots at scale',scale,flush=True)
