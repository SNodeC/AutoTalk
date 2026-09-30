# SPDX-License-Identifier: MIT
"""Native Qt integration: rejected portal requests report once, stop, and permit retry."""
import tempfile,json,sys
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from autotalk.app import MainWindow
from conftest import project,sample_pdf,make_audio
app=QApplication([])
root=Path(tempfile.mkdtemp());p=project.__wrapped__(sample_pdf.__wrapped__(root,app),root);make_audio(p);p.record_presentation=True;p.recording_source='screen'
w=MainWindow();w.adopt(p);w.show();errors=[]
QMessageBox.warning=lambda *args:errors.append(str(args[2]))
for attempt in range(2):
 QTest.mouseClick(w.start_button,Qt.MouseButton.LeftButton);QTest.qWait(1500)
 print(json.dumps({'attempt':attempt,'errors':errors,'state':w.transport.state,'capture':bool(w.transport.capture),'label':w.recording_status.text() if hasattr(w,'recording_status') else w.status.text()}),flush=True)
 assert len(errors)==attempt+1, errors
 assert errors[-1]==("Screen sharing was cancelled." if sys.argv[1]=="1" else "The screen-sharing service could not start capture.")
 assert w.transport.capture is None and w.transport.state=="stopped"
 assert w.presentation is None and w.workspace.currentWidget()==w.editor
 assert w.narration.isEnabled() and w.start_button.isEnabled()
 assert not w.pending_exports
 # Retry uses Start directly; no End action or manual capture cleanup.
 QTest.qWait(100)
w.close_requested=True;w.close()
