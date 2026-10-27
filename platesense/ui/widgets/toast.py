"""Transient toast notifications."""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class Toast(QLabel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.hide()

    def show_message(self, text: str, duration_ms: int = 1800):
        self.setText(text)
        self.adjustSize()
        self.update_position()
        self.show()
        self.raise_()
        parent = self.parentWidget()
        if parent is not None:
            try:
                parent.update()
            except Exception:
                pass
        # Fade in/out via simple animation
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

        from PySide6.QtCore import QTimer
        QTimer.singleShot(duration_ms, self._fade_out)

    def _fade_out(self):
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(220)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(self.hide)
        anim.start()

    def update_position(self):
        parent = self.parentWidget()
        if not parent:
            return
        w = min(380, parent.width() - 40)
        self.setFixedWidth(w)
        x = (parent.width() - w) // 2
        y = parent.height() - self.height() - 40
        self.move(x, y)
