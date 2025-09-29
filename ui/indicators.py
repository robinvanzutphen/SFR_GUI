# ui/indicators.py

from PyQt5.QtWidgets import QLabel

class IndicatorLabel(QLabel):
    """Small circular indicator: red (off) or green (on)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.set_red()

    def set_green(self):
        self.setStyleSheet("background-color: green; border-radius: 6px;")

    def set_red(self):
        self.setStyleSheet("background-color: red; border-radius: 6px;")
