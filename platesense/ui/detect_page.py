"""Detection workflow page: upload → processing → result."""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from config.settings import config
from database.database import DetectionRecord
from services.detection_service import (DetectionResult, DetectionService,
                                         SinglePlateResult)
from ui.widgets.drop_area import DropArea
from ui.widgets.image_viewer import ImageViewerWithControls
from workers.detection_worker import DetectionWorker


def cv2_to_qimage(img: np.ndarray) -> QImage:
    """Convert a BGR or grayscale numpy image to a QImage (RGB)."""
    if img is None:
        return QImage()
    if len(img.shape) == 2:
        h, w = img.shape
        return QImage(img.data, w, h, w, QImage.Format_Grayscale8).copy()
    h, w, _ = img.shape
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def _overall_confidence(plate: SinglePlateResult) -> float:
    return float(0.45 * plate.detection.confidence +
                 0.35 * plate.ocr_confidence +
                 0.20 * plate.validation.confidence)


def guess_vehicle_type(image_shape) -> str:
    h, w = image_shape[:2]
    ar = w / float(h)
    if ar > 1.7:
        return "Car / SUV"
    if ar < 1.1:
        return "Two-wheeler"
    return "Vehicle"


class DetectPage(QWidget):
    request_toast = Signal(str)
    saved_to_history = Signal(int)

    def __init__(self, detection_service: DetectionService, parent=None):
        super().__init__(parent)
        self.service = detection_service
        self._worker: Optional[DetectionWorker] = None
        self._result: Optional[DetectionResult] = None
        self._selected_plate_idx: int = 0
        self._stages = [
            "Loading image", "Detecting plate", "Enhancing plate",
            "Reading characters", "Validating result", "Complete",
        ]

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)

        # Header
        self.header = QLabel("Detect a number plate")
        self.header.setProperty("title", True)
        self.sub = QLabel("Upload a vehicle photo to locate and read its number plate.")
        self.sub.setProperty("subtitle", True)
        root.addWidget(self.header)
        root.addWidget(self.sub)

        # Stack area
        self._stack_area = QFrame()
        self._stack_area.setProperty("card", True)
        stack_lay = QVBoxLayout(self._stack_area)
        stack_lay.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack_area, 1)

        # Build upload state
        self._build_upload_state(stack_lay)
        self._build_processing_state()
        self._build_result_state()
        self._build_error_state()
        self._show_upload()

    # -------- states --------
    def _build_upload_state(self, parent_lay):
        self.upload_widget = QWidget()
        lay = QVBoxLayout(self.upload_widget)
        lay.setContentsMargins(40, 40, 40, 40)
        self.drop_area = DropArea()
        self.drop_area.file_selected.connect(self._start_from_path)
        self.drop_area.setMinimumHeight(360)
        lay.addWidget(self.drop_area)
        parent_lay.addWidget(self.upload_widget)

    def _build_processing_state(self):
        self.processing_widget = QWidget()
        lay = QVBoxLayout(self.processing_widget)
        lay.setContentsMargins(60, 60, 60, 60)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(18)

        title = QLabel("Analyzing vehicle image…")
        title.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(20)
        f.setWeight(QFont.DemiBold)
        title.setFont(f)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(380)
        self.progress.setFixedHeight(10)

        self.stage_label = QLabel("Loading image")
        self.stage_label.setAlignment(Qt.AlignCenter)
        self.stage_label.setProperty("muted", True)

        wrap = QVBoxLayout()
        wrap.setAlignment(Qt.AlignCenter)
        wrap.addWidget(title)
        wrap.addSpacing(20)
        wrap.addWidget(self.progress, alignment=Qt.AlignCenter)
        wrap.addWidget(self.stage_label, alignment=Qt.AlignCenter)
        wrap.addStretch(1)
        lay.addLayout(wrap)

        self._stack_area.layout().addWidget(self.processing_widget)
        self.processing_widget.hide()

    def _build_result_state(self):
        self.result_widget = QWidget()
        outer = QVBoxLayout(self.result_widget)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)

        # Header row
        head = QHBoxLayout()
        head_l = QVBoxLayout()
        head_l.setSpacing(4)
        self.result_title = QLabel("Detection complete")
        self.result_title.setProperty("title", True)
        self.result_title.setStyleSheet("font-size:22px;")
        self.result_subtitle = QLabel("One plate detected with high confidence.")
        self.result_subtitle.setProperty("subtitle", True)
        head_l.addWidget(self.result_title)
        head_l.addWidget(self.result_subtitle)
        head.addLayout(head_l, 1)

        self.btn_new = QPushButton("New Scan")
        self.btn_new.setProperty("secondary", True)
        self.btn_new.clicked.connect(self._show_upload)
        head.addWidget(self.btn_new)
        outer.addLayout(head)

        # Body: left image, right info
        body = QHBoxLayout()
        body.setSpacing(20)
        left = QFrame()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        self.viewer = ImageViewerWithControls()
        left_l.addWidget(self.viewer)
        body.addWidget(left, 3)

        right = QFrame()
        right.setProperty("card", "alt")
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(22, 22, 22, 22)
        right_l.setSpacing(12)

        self.plate_label = QLabel("PLATE NUMBER")
        self.plate_label.setProperty("section", True)
        self.plate_text = QLabel("")
        self.plate_text.setProperty("plateBig", True)
        self.conf_label = QLabel("0.0% confidence")
        self.conf_label.setProperty("success", True)

        right_l.addWidget(self.plate_label)
        right_l.addWidget(self.plate_text)
        right_l.addWidget(self.conf_label)
        right_l.addSpacing(10)

        # Metadata grid
        self.meta_label = QLabel("DETAILS")
        self.meta_label.setProperty("section", True)
        right_l.addWidget(self.meta_label)
        self.meta_grid = QGridLayout()
        self.meta_grid.setHorizontalSpacing(10)
        self.meta_grid.setVerticalSpacing(8)
        self._meta_labels = {}
        for i, key in enumerate(["Vehicle Type", "Region", "Processing Time",
                                  "Detection", "OCR"]):
            k = QLabel(key)
            k.setProperty("muted", True)
            v = QLabel("—")
            self.meta_grid.addWidget(k, i, 0)
            self.meta_grid.addWidget(v, i, 1, alignment=Qt.AlignRight)
            self._meta_labels[key] = v
        right_l.addLayout(self.meta_grid)
        right_l.addSpacing(10)

        # Multiple plates
        self.multi_label = QLabel("MULTIPLE PLATES DETECTED")
        self.multi_label.setProperty("section", True)
        self.multi_list = QListWidget()
        self.multi_list.setFixedHeight(110)
        self.multi_list.itemClicked.connect(self._on_multi_select)
        right_l.addWidget(self.multi_label)
        right_l.addWidget(self.multi_list)

        right_l.addStretch(1)

        # Action buttons
        actions = QGridLayout()
        actions.setSpacing(10)
        self.btn_copy = QPushButton("Copy Plate Number")
        self.btn_copy.clicked.connect(self._copy_plate)
        self.btn_save = QPushButton("Save to History")
        self.btn_save.clicked.connect(self._save_to_history)
        self.btn_export = QPushButton("Export Result")
        self.btn_export.setProperty("secondary", True)
        self.btn_export.clicked.connect(self._export_result)
        actions.addWidget(self.btn_copy, 0, 0)
        actions.addWidget(self.btn_save, 0, 1)
        actions.addWidget(self.btn_export, 1, 0, 1, 2)
        right_l.addLayout(actions)

        body.addWidget(right, 2)
        outer.addLayout(body, 1)

        self._stack_area.layout().addWidget(self.result_widget)
        self.result_widget.hide()

    def _build_error_state(self):
        self.error_widget = QWidget()
        lay = QVBoxLayout(self.error_widget)
        lay.setContentsMargins(60, 60, 60, 60)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(14)
        icon = QLabel("⚠")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size:44px;color:#FF9F0A;")
        self.err_title = QLabel("Unable to complete detection")
        self.err_title.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(20)
        f.setWeight(QFont.DemiBold)
        self.err_title.setFont(f)
        self.err_message = QLabel("")
        self.err_message.setAlignment(Qt.AlignCenter)
        self.err_message.setWordWrap(True)
        self.err_message.setProperty("muted", True)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        retry = QPushButton("Try Another Image")
        retry.setProperty("secondary", True)
        retry.clicked.connect(self._show_upload)
        btn_row.addWidget(retry)
        btn_row.addStretch(1)
        lay.addWidget(icon)
        lay.addWidget(self.err_title)
        lay.addWidget(self.err_message)
        lay.addSpacing(10)
        lay.addLayout(btn_row)
        self._stack_area.layout().addWidget(self.error_widget)
        self.error_widget.hide()

    # -------- state switching --------
    def _swap(self, w):
        for widget in (self.upload_widget, self.processing_widget,
                       self.result_widget, self.error_widget):
            widget.hide()
        w.show()

    def _show_upload(self):
        self._swap(self.upload_widget)

    def _show_processing(self):
        self.progress.setValue(0)
        self.stage_label.setText("Loading image")
        self._swap(self.processing_widget)

    def _show_result(self, result: DetectionResult):
        self._result = result
        self._selected_plate_idx = 0
        self.multi_list.clear()
        if len(result.plates) > 1:
            self.result_subtitle.setText(f"{len(result.plates)} plates detected. Select one to inspect.")
            self.multi_label.show()
            self.multi_list.show()
            for i, p in enumerate(result.plates):
                item = QListWidgetItem(
                    f"Plate {i+1}  •  {p.ocr_text or 'Unknown'}  "
                    f"•  {p.detection.confidence*100:.1f}% det."
                )
                self.multi_list.addItem(item)
        else:
            self.result_subtitle.setText("One plate detected with high confidence.")
            self.multi_label.hide()
            self.multi_list.hide()

        self._populate_for_selected()
        if result.annotated_image is not None:
            self.viewer.set_image(cv2_to_qimage(result.annotated_image))
        elif result.source_image is not None:
            self.viewer.set_image(cv2_to_qimage(result.source_image))

        self._swap(self.result_widget)

    def _populate_for_selected(self):
        if not self._result or not self._result.plates:
            return
        plate = self._result.plates[self._selected_plate_idx]
        overall = _overall_confidence(plate)
        txt = plate.validation.normalized_text or plate.ocr_text or "—"
        self.plate_text.setText(txt)
        self.conf_label.setText(f"{overall * 100:.1f}% overall confidence")

        region = plate.validation.region or "—"
        vtype = guess_vehicle_type(self._result.source_image.shape if self._result.source_image is not None else (0,0))
        self._meta_labels["Vehicle Type"].setText(vtype)
        self._meta_labels["Region"].setText(region)
        self._meta_labels["Processing Time"].setText(
            f"{self._result.processing_time:.2f} seconds")
        self._meta_labels["Detection"].setText(f"{plate.detection.confidence * 100:.1f}%")
        self._meta_labels["OCR"].setText(f"{plate.ocr_confidence * 100:.1f}%")

    def _show_error(self, message: str):
        self.err_message.setText(message)
        self._swap(self.error_widget)

    # -------- actions --------
    def _start_from_path(self, path: str):
        # Validate extension & size before going further
        ext = os.path.splitext(path)[1].lower()
        if ext not in config.supported_exts:
            self._show_error(
                "Unsupported file format. Please choose a JPG, PNG, WEBP or BMP image.")
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            self._show_error("Cannot read the selected file.")
            return
        if size > config.max_file_size:
            self._show_error("This image is larger than 20 MB. Please choose a smaller file.")
            return
        self._show_processing()
        self._worker = DetectionWorker(self.service, path)
        self._worker.stage_changed.connect(self._on_stage)
        self._worker.finished_success.connect(self._on_success)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    @Slot(str, float)
    def _on_stage(self, name: str, progress: float):
        self.stage_label.setText(name)
        self.progress.setValue(int(progress * 100))

    @Slot(object)
    def _on_success(self, result: DetectionResult):
        self._show_result(result)

    @Slot(str, str)
    def _on_fail(self, message: str, code: str):
        user_msg = message
        if code == "no_plate":
            user_msg = message or (
                "We couldn't locate a number plate in this image. Try a photo with the "
                "plate clearly visible, well-lit and not at an extreme angle.")
        elif code == "ocr_failed":
            user_msg = message or "The plate was located but could not be read."
        self._show_error(user_msg)

    def _on_multi_select(self, item: QListWidgetItem):
        row = self.multi_list.row(item)
        if 0 <= row < len(self._result.plates):
            self._selected_plate_idx = row
            self._populate_for_selected()
            # Re-annotate to highlight the selected plate
            if self._result and self._result.annotated_image is not None:
                # Show the plate's crop crop
                plate = self._result.plates[row]
                # Re-paint annotated to highlight selected
                from vision.annotator import annotate_detections
                dets = [p.detection for p in self._result.plates]
                labels = [p.validation.normalized_text or f"{p.detection.confidence*100:.0f}%"
                          for p in self._result.plates]
                img = annotate_detections(self._result.source_image, dets, labels=labels)
                # Draw thicker box around selected
                import cv2
                x1, y1, x2, y2 = plate.detection.bbox
                cv2.rectangle(img, (x1, y1), (x2, y2), (48, 209, 255), 4, lineType=cv2.LINE_AA)
                self.viewer.set_image(cv2_to_qimage(img))

    def _selected_plate(self) -> Optional[SinglePlateResult]:
        if not self._result:
            return None
        return self._result.plates[self._selected_plate_idx]

    def _copy_plate(self):
        plate = self._selected_plate()
        if not plate:
            return
        text = plate.validation.normalized_text or plate.ocr_text
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.request_toast.emit("Plate number copied.")

    def _save_to_history(self):
        plate = self._selected_plate()
        if not plate or not self._result:
            return
        # Persist files
        try:
            paths = self.service.persist_result(self._result, plate)
        except Exception as exc:
            self.request_toast.emit(f"Could not save files: {exc}")
            return
        overall = _overall_confidence(plate)
        rec = DetectionRecord(
            id=None,
            plate_number=plate.ocr_text,
            normalized_plate=plate.validation.normalized_text or plate.ocr_text,
            state=plate.validation.region,
            state_code=plate.validation.state_code,
            detection_confidence=float(plate.detection.confidence),
            ocr_confidence=float(plate.ocr_confidence),
            overall_confidence=float(overall),
            image_path=paths["image_path"],
            plate_crop_path=paths["plate_crop_path"],
            annotated_path=paths["annotated_path"],
            processing_time=float(self._result.processing_time),
            vehicle_type=guess_vehicle_type(self._result.source_image.shape),
            notes=None,
            valid=plate.validation.valid,
            created_at=datetime.utcnow().isoformat(timespec="seconds"),
        )
        from services.history_service import HistoryService
        try:
            rid = HistoryService().add(rec)
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Saved to History")
            self.saved_to_history.emit(rid)
            self.request_toast.emit("Saved to history.")
        except Exception as exc:
            self.request_toast.emit(f"Database error: {exc}")

    def _export_result(self):
        plate = self._selected_plate()
        if not plate or not self._result:
            return
        # Popup to pick format
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("Export as CSV")
        menu.addAction("Export as JSON")
        menu.addAction("Export as TXT")
        menu.addAction("Export annotated image (JPG)")
        act = menu.exec(self.btn_export.mapToGlobal(self.btn_export.rect().bottomLeft()))
        if act is None:
            return
        fmt = {"Export as CSV": "csv", "Export as JSON": "json", "Export as TXT": "txt",
               "Export annotated image (JPG)": "image"}[act.text()]

        # Make sure it's saved first
        from services.history_service import HistoryService
        overall = _overall_confidence(plate)
        paths = self.service.persist_result(self._result, plate)
        rec = DetectionRecord(
            id=None,
            plate_number=plate.ocr_text,
            normalized_plate=plate.validation.normalized_text or plate.ocr_text,
            state=plate.validation.region,
            state_code=plate.validation.state_code,
            detection_confidence=float(plate.detection.confidence),
            ocr_confidence=float(plate.ocr_confidence),
            overall_confidence=float(overall),
            image_path=paths["image_path"],
            plate_crop_path=paths["plate_crop_path"],
            annotated_path=paths["annotated_path"],
            processing_time=float(self._result.processing_time),
            vehicle_type=guess_vehicle_type(self._result.source_image.shape),
            notes=None,
            valid=plate.validation.valid,
            created_at=datetime.utcnow().isoformat(timespec="seconds"),
        )
        out_dir = config.export_dir
        default_name = f"{rec.normalized_plate.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if fmt == "image":
            out_path, _ = QFileDialog.getSaveFileName(
                self, "Export annotated image",
                os.path.join(str(out_dir), default_name + ".jpg"),
                "JPEG Image (*.jpg);;PNG Image (*.png)")
        else:
            filt = {"csv": "CSV (*.csv)", "json": "JSON (*.json)", "txt": "Text (*.txt)"}[fmt]
            ext = f".{fmt}"
            out_path, _ = QFileDialog.getSaveFileName(
                self, "Export result",
                os.path.join(str(out_dir), default_name + ext), filt)
        if not out_path:
            return
        try:
            from services import export_service
            export_service.export_record(rec, fmt, os.path.dirname(out_path))
            # If chosen name differs, move
            if os.path.exists(os.path.join(os.path.dirname(out_path), os.path.basename(out_path))):
                # already saved by default naming; rename to requested path if different
                default_file = os.path.join(os.path.dirname(out_path), default_name + ext if fmt != "image" else default_name + ".jpg")
                if default_file != out_path and os.path.exists(default_file):
                    shutil.move(default_file, out_path)
            self.request_toast.emit(f"Exported to {os.path.basename(out_path)}.")
        except Exception as exc:
            self.request_toast.emit(f"Export failed: {exc}")
