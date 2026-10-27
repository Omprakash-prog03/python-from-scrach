"""History page with search/filter/sort."""
from __future__ import annotations

import os
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton,
                               QScrollArea, QSplitter, QVBoxLayout, QWidget)

from database.database import DetectionRecord
from services.export_service import (export_annotated_image, export_csv,
                                     export_json, export_txt)
from services.history_service import HistoryService
from ui.widgets.image_viewer import ImageViewerWithControls


def cv2_to_qimage(img: np.ndarray) -> QImage:
    if img is None:
        return QImage()
    if len(img.shape) == 2:
        h, w = img.shape
        return QImage(img.data, w, h, w, QImage.Format_Grayscale8).copy()
    h, w, _ = img.shape
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def _load_image(path: str | None):
    if not path or not os.path.exists(path):
        return None
    try:
        return cv2.imread(path)
    except Exception:
        return None


class HistoryPage(QWidget):
    request_toast = Signal(str)
    item_opened = Signal(int)

    def __init__(self, service: HistoryService, parent=None):
        super().__init__(parent)
        self.service = service
        self._records: list[DetectionRecord] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)

        # Header
        title = QLabel("Detection History")
        title.setProperty("title", True)
        sub = QLabel("Search, filter and revisit every plate you've scanned.")
        sub.setProperty("subtitle", True)
        root.addWidget(title)
        root.addWidget(sub)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search plate number, state, notes…")
        self.search.textChanged.connect(self._refresh)
        self.sort = QComboBox()
        self.sort.addItems(["Newest first", "Oldest first",
                            "Highest confidence", "Lowest confidence",
                            "Plate (A–Z)"])
        self.sort.currentIndexChanged.connect(self._refresh)
        self.state_filter = QComboBox()
        self.state_filter.addItem("All states", "")
        self.state_filter.currentIndexChanged.connect(self._refresh)
        self.btn_export = QPushButton("Export All")
        self.btn_export.setProperty("secondary", True)
        self.btn_export.clicked.connect(self._export_all)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.state_filter)
        toolbar.addWidget(self.sort)
        toolbar.addWidget(self.btn_export)
        root.addLayout(toolbar)

        # Splitter: list + preview
        splitter = QSplitter(Qt.Horizontal)

        left = QFrame()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_select)
        ll.addWidget(self.list_widget)
        splitter.addWidget(left)

        right = QFrame()
        right.setProperty("card", True)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(24, 22, 24, 22)
        rl.setSpacing(12)
        self.detail_title = QLabel("Select a detection")
        self.detail_title.setProperty("cardTitle", True)
        self.detail_image = ImageViewerWithControls()
        self.detail_info = QLabel("")
        self.detail_info.setWordWrap(True)
        self.detail_info.setProperty("muted", True)
        btns = QHBoxLayout()
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setProperty("danger", True)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_export_one = QPushButton("Export")
        self.btn_export_one.setProperty("secondary", True)
        self.btn_export_one.clicked.connect(self._export_selected)
        btns.addStretch(1)
        btns.addWidget(self.btn_export_one)
        btns.addWidget(self.btn_delete)

        rl.addWidget(self.detail_title)
        rl.addWidget(self.detail_image, 1)
        rl.addWidget(self.detail_info)
        rl.addLayout(btns)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)

        self._selected_id: int | None = None
        self.refresh()

    # ---------- population ----------
    def refresh(self):
        # Populate state filter options
        current = self.state_filter.currentData() if self.state_filter.count() else ""
        from ocr.validator import STATE_CODES
        self.state_filter.blockSignals(True)
        self.state_filter.clear()
        self.state_filter.addItem("All states", "")
        for code, name in sorted(STATE_CODES.items()):
            self.state_filter.addItem(f"{code} – {name}", code)
        # Restore previous selection if still present
        if current:
            idx = self.state_filter.findData(current)
            if idx >= 0:
                self.state_filter.setCurrentIndex(idx)
        self.state_filter.blockSignals(False)
        self._refresh()

    def _refresh(self):
        order_by, descending = self._current_sort()
        q = self.search.text().strip() or None
        state = self.state_filter.currentData() or None
        records = self.service.search(query=q, state_code=state,
                                      order_by=order_by, descending=descending)
        self._records = records
        self.list_widget.clear()
        for r in records:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, r.id)
            date_str = r.created_at
            try:
                dt = datetime.fromisoformat(r.created_at)
                date_str = dt.strftime("%d %b %Y, %H:%M")
            except Exception:
                pass
            lines = [
                f"<b>{r.normalized_plate}</b>",
                f"<span style='color:#8E8E93;'>{r.state or 'Unknown'}</span>   "
                f"<span style='color:#30D158;'>{r.overall_confidence*100:.1f}%</span>   "
                f"<span style='color:#8E8E93;'>{date_str}</span>",
            ]
            item.setText("\n".join(lines))
            from PySide6.QtGui import QFont
            f = QFont()
            f.setPointSize(13)
            item.setFont(f)
            self.list_widget.addItem(item)
        if self._selected_id is not None and not any(r.id == self._selected_id for r in records):
            self._selected_id = None
            self.detail_title.setText("Select a detection")
            self.detail_info.setText("")
            self.detail_image.viewer._scene.clear()

    def _current_sort(self):
        idx = self.sort.currentIndex()
        return [
            ("created_at", True),
            ("created_at", False),
            ("overall_confidence", True),
            ("overall_confidence", False),
            ("normalized_plate", False),
        ][idx]

    # ---------- actions ----------
    def _on_select(self, item: QListWidgetItem):
        rid = item.data(Qt.UserRole)
        rec = self.service.get(rid)
        if rec is None:
            return
        self._selected_id = rid
        self.detail_title.setText(rec.normalized_plate)
        date_str = rec.created_at
        try:
            dt = datetime.fromisoformat(rec.created_at)
            date_str = dt.strftime("%d %b %Y %H:%M")
        except Exception:
            pass
        self.detail_info.setText(
            f"<div style='font-size:13px;'>"
            f"<b>Region:</b> {rec.state or '—'}<br>"
            f"<b>Confidence:</b> {rec.overall_confidence*100:.1f}% "
            f"(det {rec.detection_confidence*100:.0f}% · ocr {rec.ocr_confidence*100:.0f}%)<br>"
            f"<b>Processing:</b> {rec.processing_time:.2f}s<br>"
            f"<b>Vehicle:</b> {rec.vehicle_type or '—'}<br>"
            f"<b>Date:</b> {date_str}"
            f"</div>"
        )
        img = _load_image(rec.annotated_path) or _load_image(rec.image_path)
        if img is not None:
            self.detail_image.set_image(cv2_to_qimage(img))
        else:
            self.detail_image.viewer._scene.clear()

    def _delete_selected(self):
        if self._selected_id is None:
            return
        btn = QMessageBox.question(self, "Delete detection",
                                   "Permanently delete this detection? This cannot be undone.",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if btn == QMessageBox.Yes:
            self.service.delete(self._selected_id)
            self._selected_id = None
            self._refresh()
            self.request_toast.emit("Detection deleted.")

    def _export_selected(self):
        if self._selected_id is None:
            return
        rec = self.service.get(self._selected_id)
        if rec is None:
            return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("CSV")
        menu.addAction("JSON")
        menu.addAction("TXT")
        menu.addAction("Annotated Image (JPG)")
        act = menu.exec(self.btn_export_one.mapToGlobal(self.btn_export_one.rect().bottomLeft()))
        if act is None:
            return
        fmt = act.text().split()[0].lower()
        out_dir = str(QFileDialog.getExistingDirectory(self, "Choose export directory"))
        if not out_dir:
            return
        try:
            from services import export_service
            export_service.export_record(rec, fmt, out_dir)
            self.request_toast.emit(f"Exported to {out_dir}.")
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def _export_all(self):
        if not self._records:
            self.request_toast.emit("Nothing to export.")
            return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("CSV")
        menu.addAction("JSON")
        menu.addAction("TXT")
        act = menu.exec(self.btn_export.mapToGlobal(self.btn_export.rect().bottomLeft()))
        if act is None:
            return
        fmt = act.text().lower()
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export as {fmt.upper()}",
            f"platesense_history_{datetime.now().strftime('%Y%m%d')}.{fmt}",
            f"{fmt.upper()} files (*.{fmt})")
        if not path:
            return
        try:
            if fmt == "csv":
                export_csv(self._records, path)
            elif fmt == "json":
                export_json(self._records, path)
            elif fmt == "txt":
                export_txt(self._records, path)
            self.request_toast.emit(f"Exported {len(self._records)} records.")
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
