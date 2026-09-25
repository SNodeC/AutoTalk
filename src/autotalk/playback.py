"""One transport owns both slide selection and the audio position."""

from PySide6.QtCore import QObject, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QWidget


class Playback(QObject):
    changed = Signal()
    slide_changed = Signal(int)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.index = 0
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.positionChanged.connect(lambda _: self.changed.emit())
        self.player.playbackStateChanged.connect(lambda _: self.changed.emit())
        self.player.mediaStatusChanged.connect(self._status)
        self.player.errorOccurred.connect(lambda _, text: self.failed.emit(text))

    def load(self, project):
        self.stop()
        self.project = project
        self.select(0)

    def select(self, index, play=False):
        if not self.project or not 0 <= index < len(self.project.slides):
            return
        # Stop old media before changing the index, so stale end events cannot advance it.
        self.player.stop()
        self.index = index
        slide = self.project.slides[index]
        self.player.setSource(QUrl.fromLocalFile(str(self.project.audio(slide)))
                              if self.project.ready(slide) else QUrl())
        self.slide_changed.emit(index)
        self.changed.emit()
        if play:
            self.play()

    def play(self):
        if not self.project or not self.project.prepared:
            self.failed.emit("Generate current audio for every slide before presenting.")
            return
        expected = QUrl.fromLocalFile(str(self.project.audio(self.project.slides[self.index])))
        if self.player.source() != expected:
            self.player.setSource(expected)
        self.player.play()

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.play()

    def step(self, amount):
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.select(self.index + amount, play=playing)

    def stop(self):
        self.player.stop()
        self.changed.emit()

    def _status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.project:
            if self.index + 1 < len(self.project.slides):
                self.select(self.index + 1, play=True)
            else:
                self.finished.emit()

    @property
    def elapsed(self):
        if not self.project:
            return 0
        return sum(s.duration for s in self.project.slides[:self.index]) + self.player.position()/1000


class Presentation(QWidget):
    closed = Signal()

    def __init__(self, transport, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.transport = transport
        self.setWindowTitle("AutoTalk — Presentation")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.document = QPdfDocument(self)
        self.document.load(str(transport.project.asset("slides.pdf")))
        self.rendered = None
        transport.slide_changed.connect(self.refresh)

    def refresh(self, *_):
        self.rendered = None
        self.update()

    def resizeEvent(self, event):
        self.refresh()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#06090f"))
        page = self.transport.index
        size = self.document.pagePointSize(page)
        if size.isEmpty():
            return
        ratio = min(self.width()/size.width(), self.height()/size.height())
        target = QSize(round(size.width()*ratio), round(size.height()*ratio))
        if self.rendered is None:
            self.rendered = self.document.render(page, target)
        painter.drawImage((self.width()-target.width())//2, (self.height()-target.height())//2, self.rendered)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Space:
            self.transport.toggle()
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self.transport.step(1)
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self.transport.step(-1)

    def closeEvent(self, event):
        self.transport.stop()
        self.closed.emit()
        super().closeEvent(event)
