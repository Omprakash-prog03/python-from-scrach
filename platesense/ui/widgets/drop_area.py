"""Drag-and-drop upload card."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QColor, QPixmap, QFont
from PySide6.QtWidgets import (QFileDialog, QFrame, QLabel, QPushButton,
                               QVBoxLayout, QWidget)


class DropArea(QFrame):
    file_selected = Signal(str)

    SUPPORTED = "JPG, JPEG, PNG, WEBP, BMP"
    MAX_SIZE_MB = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setProperty("card", True)
        self.setMinimumHeight(320)
        self.setAcceptDrops(True)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)

        self._icon = QLabel()
        self._icon.setAlignment(Qt.AlignCenter)
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor("#8E8E93"))
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(6, 6, 52, 44, 8, 8)
        p.drawPath(path)
        # arrow up
        p.setPen(QColor("#8E8E93"))
        p.setBrush(QColor("#C7C7CC"))
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        poly = QPolygon([QPoint(32, 14), QPoint(22, 28), QPoint(42, 28)])
        p.drawPolygon(poly)
        p.drawRect(29, 28, 6, 12)
        p.end()
        self._icon.setPixmap(pix)

        self._title = QLabel("Drop a vehicle image here")
        self._title.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(18)
        f.setWeight(QFont.DemiBold)
        self._title.setFont(f)

        self._sub = QLabel("or choose a file from your computer")
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setProperty("muted", True)

        self._btn = QPushButton("Choose Image")
        self._btn.setFixedWidth(180)
        self._btn.clicked.connect(self._choose_file)
        btn_wrap = QWidget()
        bl = QVBoxLayout(btn_wrap)
        bl.setContentsMargins(0, 8, 0, 0)
        bl.addWidget(self._btn, alignment=Qt.AlignCenter)

        self._hint = QLabel(f"Supports {self.SUPPORTED}  •  Max {self.MAX_SIZE_MB} MB")
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setProperty("muted", True)
        f2 = QFont()
        f2.setPointSize(11)
        self._hint.setFont(f2)

        lay.addWidget(self._icon)
        lay.addWidget(self._title)
        lay.addWidget(self._sub)
        lay.addWidget(btn_wrap)
        lay.addWidget(self._hint)

    # ----- events -----
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet("QFrame#DropArea{border:2px dashed #0A84FF;}")
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.setStyleSheet("")
        super().dragLeaveEvent(e)

    def dropEvent(self, e: QDropEvent):
        self.setStyleSheet("")
        urls = e.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path:
            self.file_selected.emit(path)

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select vehicle image", "",
            "Images (*.jpg *.jpeg *.png *.webp *.bmp)",
        )
        if path:
            self.file_selected.emit(path)

    def sizeHint(self) -> QSize:
        return QSize(480, 340)
