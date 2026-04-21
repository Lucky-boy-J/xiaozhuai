from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPainter, QColor
import math, random


class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bars = [0.2] * 8
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_bars)
        self._rms = 0.0

    def start(self):
        self._timer.start(80)

    def stop(self):
        self._timer.stop()
        self._bars = [0.1] * 8
        self.update()

    def set_rms(self, rms: float):
        self._rms = min(rms * 8, 1.0)

    def _update_bars(self):
        base = self._rms
        self._bars = [
            max(0.05, min(1.0, base + random.uniform(-0.2, 0.2)))
            for _ in self._bars
        ]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self._bars)
        bar_w = max(2, w // n - 2)
        color = QColor("#4A9EFF")
        for i, val in enumerate(self._bars):
            bar_h = int(val * h * 0.9)
            x = i * (w // n) + (w // n - bar_w) // 2
            y = (h - bar_h) // 2
            p.fillRect(x, y, bar_w, bar_h, color)
