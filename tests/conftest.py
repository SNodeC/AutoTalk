import wave

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPdfWriter

from autotalk.project import file_hash, wav_duration
from autotalk.runtime import Task
from autotalk.services import import_pdf


@pytest.fixture
def sample_pdf(tmp_path, qapp):
    path = tmp_path / "slides.pdf"
    writer = QPdfWriter(str(path))
    writer.setResolution(96)
    painter = QPainter(writer)
    for i, (title, body) in enumerate([
        ("Reliable presentations", "One controller keeps narration and slides synchronized."),
        ("Prepare, then present", "Generate audio in advance. Measure duration. Present offline.")]):
        if i:
            writer.newPage()
        painter.fillRect(0, 0, writer.width(), writer.height(), QColor("#102239"))
        painter.setPen(QColor("#ed9a4c"))
        painter.setFont(QFont("sans-serif", 28))
        painter.drawText(QRectF(65, 80, 640, 120), title)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("sans-serif", 17))
        painter.drawText(QRectF(65, 240, 620, 500), 0x1000, body)
    painter.end()
    del writer
    return path


@pytest.fixture
def project(sample_pdf, tmp_path):
    p = import_pdf(sample_pdf, tmp_path / "talk", Task(lambda _: None))
    p.scope = "Software engineering and dependable desktop applications"
    for s in p.slides:
        s.narration = f"This is the spoken explanation for slide {s.page}."
    return p


def make_audio(project, seconds=0.3):
    for slide in project.slides:
        slide.audio_key = project.speech_key(slide)
        slide.audio_file = project.audio_name(slide)
        path = project.audio(slide)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b"\x00\x00" * round(24000 * seconds))
        slide.duration = wav_duration(path)
        slide.audio_sha256 = file_hash(path)
    project.save()
