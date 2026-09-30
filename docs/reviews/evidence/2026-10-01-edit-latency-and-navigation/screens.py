import sys, tempfile
from pathlib import Path
from PySide6.QtCore import QSettings, QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
sys.path.insert(0, str(Path.cwd()))
from tools.bench_ui import prepared_project
from autotalk.app import MainWindow
app=QApplication([])
with tempfile.TemporaryDirectory() as temp:
 QSettings.setDefaultFormat(QSettings.Format.IniFormat)
 QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,temp)
 w=MainWindow();w.adopt(prepared_project(Path(temp)/'talk',6));w.show()
 w.elapsed_timer.stop();w.transport.timer.stop()
 for mode in ['Prepared','Quick','Realtime']:
  w.mode.setCurrentText(mode)
  for size in [(940,680),(1100,850)]:
   w.resize(*size);app.processEvents();QTest.qWait(100)
   assert w.size().toTuple()==size
   if mode!='Quick':
    for control in [w.editor_next,w.editor_previous]:
     assert control.isVisible()
     assert w.rect().contains(control.mapTo(w,control.rect().bottomRight()))
   w.grab().save('artifacts/edit-latency-and-navigation/screens/'+mode+'-'+str(size[0])+'.png')
 w.mode.setCurrentText('Prepared');w.select_slide(5)
 w.inspector.slide_include.setChecked(False)
 w.workspace.setCurrentWidget(w.presenter)
 w.resize(940,680);app.processEvents();QTest.qWait(100)
 w.grab().save('artifacts/edit-latency-and-navigation/screens/presenter-stale.png')
 w.close()
