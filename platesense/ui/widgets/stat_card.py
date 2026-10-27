"""Dashboard stat card."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(6)

        t = QLabel(title)
        t.setProperty("muted", True)
        f = QFont()
        f.setPointSize(11)
        t.setFont(f)

        v = QLabel(value)
        v.setProperty("bigNumber", True)

        self._value = v
        self._title = t
        self._subtitle_label = None

        lay.addWidget(t)
        lay.addWidget(v)
        if subtitle:
            s = QLabel(subtitle)
            s.setProperty("muted", True)
            lay.addWidget(s)
            self._subtitle_label = s
        lay.addStretch(1)

    def set_value(self, value: str):
        self._value.setText(value)
