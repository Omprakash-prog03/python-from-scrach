"""Zoomable, pan-enabled image viewer."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPixmap, QWheelEvent
from PySide6.QtWidgets import (QFrame, QGraphicsPixmapItem, QGraphicsScene,
                               QGraphicsView, QHBoxLayout, QPushButton,
                               QVBoxLayout, QWidget)


class ImageViewer(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(self.renderHints())
        from PySide6.QtGui import QPainter
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor(0, 0, 0, 0)))
        self.setFrameShape(QFrame.NoFrame)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item: QGraphicsPixmapItem | None = None
        self._zoom = 1.0

    def set_image(self, qimage: QImage):
        self._scene.clear()
        pix = QPixmap.fromImage(qimage)
        self._item = self._scene.addPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        self.reset_view()

    def reset_view(self):
        if self._item is None:
            return
        self.resetTransform()
        self.fitInView(self._item, Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def fit_to_window(self):
        self.reset_view()

    def wheelEvent(self, event: QWheelEvent):
        if self._item is None:
            return
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        new_zoom = self._zoom * factor
        if 0.1 < new_zoom < 10:
            self.scale(factor, factor)
            self._zoom = new_zoom


class ImageViewerWithControls(QWidget):
    reset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.viewer = ImageViewer()
        lay.addWidget(self.viewer, 1)

        bar = QHBoxLayout()
        bar.addStretch(1)
        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setProperty("secondary", True)
        self.btn_fit.clicked.connect(self.viewer.fit_to_window)
        self.btn_reset = QPushButton("Reset Zoom")
        self.btn_reset.setProperty("secondary", True)
        self.btn_reset.clicked.connect(self.viewer.reset_view)
        self.btn_plus = QPushButton("+")
        self.btn_plus.setProperty("secondary", True)
        self.btn_plus.clicked.connect(lambda: self.viewer.scale(1.25, 1.25))
        self.btn_minus = QPushButton("−")
        self.btn_minus.setProperty("secondary", True)
        self.btn_minus.clicked.connect(lambda: self.viewer.scale(0.8, 0.8))
        for b in (self.btn_minus, self.btn_reset, self.btn_fit, self.btn_plus):
            b.setFixedWidth(96 if b in (self.btn_fit, self.btn_reset) else 40)
            bar.addWidget(b)
        lay.addLayout(bar)

    def set_image(self, qimage: QImage):
        self.viewer.set_image(qimage)
