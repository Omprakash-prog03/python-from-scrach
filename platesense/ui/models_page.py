"""Models page – shows installed detectors/OCR backends and helps set them up."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from config.settings import config


def _detector_status(service) -> list[dict]:
    rows = []
    det = service.detector()
    # Classical
    rows.append({
        "name": "Classical Detector",
        "desc": "Edges + contour analysis. No model required.",
        "state": "ready" if config.settings.use_classical_detector else "disabled",
    })
    # Cascade
    from vision.detector import CascadePlateDetector
    c = CascadePlateDetector(config.settings.cascade_path or None)
    rows.append({
        "name": "Haar Cascade",
        "desc": "OpenCV built-in plate cascade (Russian plates, works as a weak prior).",
        "state": "ready" if c.available() and config.settings.use_cascade_detector else (
            "disabled" if not config.settings.use_cascade_detector else "not found"),
    })
    # YOLO
    yolo_path = config.settings.model_path
    yolo_exists = bool(yolo_path and os.path.exists(yolo_path))
    try:
        import ultralytics  # noqa: F401
        yolo_lib = True
    except Exception:
        yolo_lib = False
    if not yolo_exists:
        ystate = "not installed"
    elif not yolo_lib:
        ystate = "needs ultralytics"
    else:
        ystate = "ready"
    rows.append({
        "name": "YOLO Plate Detector",
        "desc": f"Path: {yolo_path or '(not set)'}",
        "state": ystate,
    })
    # OCR
    ocr_state = "ready" if service.ocr().available() else "not ready (model download needed on first use)"
    rows.append({
        "name": f"OCR Engine ({config.settings.ocr_engine})",
        "desc": f"Language: {config.settings.ocr_language}",
        "state": ocr_state,
    })
    return rows


_STATE_COLOR = {
    "ready": "#30D158",
    "loading on first use": "#FF9F0A",
    "not installed": "#8E8E93",
    "not found": "#FF9F0A",
    "disabled": "#8E8E93",
    "needs ultralytics": "#FF9F0A",
    "unavailable": "#FF3B30",
}


class ModelsPage(QWidget):
    def __init__(self, detection_service, parent=None):
        super().__init__(parent)
        self.service = detection_service

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)

        title = QLabel("Detection Models")
        title.setProperty("title", True)
        sub = QLabel("Manage the detection and OCR backends used by PlateSense.")
        sub.setProperty("subtitle", True)
        root.addWidget(title)
        root.addWidget(sub)

        self.list_container = QVBoxLayout()
        root.addLayout(self.list_container)

        note = QLabel(
            "The classical detector and the built-in Haar cascade work out of the box "
            "and don't require downloading anything. For best accuracy on Indian plates "
            "you can place a YOLOv8 weights file at the path shown above and restart the "
            "app. PlateSense will automatically use it when present."
        )
        note.setWordWrap(True)
        note.setProperty("muted", True)
        root.addWidget(note)

        # YOLO path picker
        path_row = QHBoxLayout()
        yolo_label = QLabel("YOLO weights path:")
        self.path_label = QLabel(config.settings.model_path or "(not set)")
        self.path_label.setProperty("muted", True)
        btn_pick = QPushButton("Choose File…")
        btn_pick.setProperty("secondary", True)
        btn_pick.clicked.connect(self._pick_yolo)
        path_row.addWidget(yolo_label)
        path_row.addWidget(self.path_label, 1)
        path_row.addWidget(btn_pick)
        root.addLayout(path_row)

        root.addStretch(1)
        self.refresh()

    def refresh(self):
        # Clear container
        while self.list_container.count():
            item = self.list_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for row in _detector_status(self.service):
            card = QFrame()
            card.setProperty("card", True)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(20, 16, 20, 16)
            info = QVBoxLayout()
            n = QLabel(row["name"])
            f = n.font()
            f.setPointSize(14)
            f.setBold(True)
            n.setFont(f)
            d = QLabel(row["desc"])
            d.setWordWrap(True)
            d.setProperty("muted", True)
            info.addWidget(n)
            info.addWidget(d)
            cl.addLayout(info, 1)
            pill = QLabel(row["state"].title())
            pill.setStyleSheet(
                f"color:white;background:{_STATE_COLOR.get(row['state'], '#8E8E93')};"
                "padding:6px 14px;border-radius:12px;font-weight:600;"
            )
            cl.addWidget(pill, alignment=Qt.AlignVCenter)
            self.list_container.addWidget(card)

    def _pick_yolo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select YOLO weights file", "",
            "Weights (*.pt *.pth *.onnx);;All files (*)")
        if not path:
            return
        config.update(model_path=path)
        self.path_label.setText(path)
        self.service.reload()
        self.refresh()
