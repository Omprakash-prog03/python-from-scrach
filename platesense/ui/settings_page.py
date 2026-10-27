"""Settings page with sections: Appearance, Detection, OCR, Storage, Performance, About."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSizePolicy,
                               QSpinBox, QDoubleSpinBox, QVBoxLayout, QWidget)

from config.settings import APP_NAME, APP_VERSION, config


class _Section(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)
        t = QLabel(title)
        f = t.font()
        f.setPointSize(15)
        f.setBold(True)
        t.setFont(f)
        lay.addWidget(t)
        self._form = QGridLayout()
        self._form.setHorizontalSpacing(20)
        self._form.setVerticalSpacing(14)
        self._row = 0
        lay.addLayout(self._form)
        lay.addStretch(1)

    def add_row(self, label: str, widget: QWidget, help_text: str = ""):
        l = QLabel(label)
        l.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._form.addWidget(l, self._row, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self._form.addWidget(widget, self._row, 1, alignment=Qt.AlignRight)
        if help_text:
            h = QLabel(help_text)
            h.setProperty("muted", True)
            h.setWordWrap(True)
            self._form.addWidget(h, self._row + 1, 0, 1, 2)
            self._row += 2
        else:
            self._row += 1


class SettingsPage(QWidget):
    theme_changed = Signal(str)

    def __init__(self, detection_service, parent=None):
        super().__init__(parent)
        self.service = detection_service

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)

        title = QLabel("Settings")
        title.setProperty("title", True)
        sub = QLabel("Customize detection, appearance and storage.")
        sub.setProperty("subtitle", True)
        root.addWidget(title)
        root.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(18)

        s = config.settings

        # ---- Appearance ----
        appearance = _Section("Appearance")
        self.theme = QComboBox()
        self.theme.addItems(["Light", "Dark", "System"])
        self.theme.setCurrentText(s.theme.capitalize())
        self.theme.currentTextChanged.connect(self._on_theme_changed)
        appearance.add_row("Theme", self.theme,
                           "Choose how PlateSense looks. A restart is not required.")
        cl.addWidget(appearance)

        # ---- Detection ----
        det = _Section("Detection")
        self.conf_thr = QDoubleSpinBox()
        self.conf_thr.setRange(0.05, 0.95)
        self.conf_thr.setSingleStep(0.05)
        self.conf_thr.setValue(s.confidence_threshold)
        det.add_row("Confidence threshold", self.conf_thr,
                    "Only plates above this detection score are shown.")
        self.max_det = QSpinBox()
        self.max_det.setRange(1, 20)
        self.max_det.setValue(s.max_detections)
        det.add_row("Maximum detections per image", self.max_det)
        self.use_classical = QCheckBox()
        self.use_classical.setChecked(s.use_classical_detector)
        det.add_row("Use classical (no-model) detector", self.use_classical)
        self.use_cascade = QCheckBox()
        self.use_cascade.setChecked(s.use_cascade_detector)
        det.add_row("Use Haar cascade detector", self.use_cascade)
        cl.addWidget(det)

        # ---- OCR ----
        ocr_sec = _Section("OCR")
        self.ocr_engine = QComboBox()
        self.ocr_engine.addItems(["easyocr", "pytesseract"])
        self.ocr_engine.setCurrentText(s.ocr_engine)
        ocr_sec.add_row("OCR engine", self.ocr_engine,
                        "EasyOCR is recommended. Pytesseract requires a system tesseract install.")
        self.ocr_lang = QLineEdit(s.ocr_language)
        self.ocr_lang.setFixedWidth(120)
        ocr_sec.add_row("Language code", self.ocr_lang,
                        "e.g. 'en' for English. EasyOCR accepts comma-separated codes.")
        self.ocr_pre = QComboBox()
        self.ocr_pre.addItems(["auto", "minimal", "aggressive"])
        self.ocr_pre.setCurrentText(s.preprocessing_mode)
        ocr_sec.add_row("Preprocessing mode", self.ocr_pre)
        self.ocr_gpu = QCheckBox()
        self.ocr_gpu.setChecked(s.ocr_use_gpu)
        ocr_sec.add_row("Use GPU for OCR (if available)", self.ocr_gpu)
        cl.addWidget(ocr_sec)

        # ---- Storage ----
        stor = _Section("Storage")
        db_row = QHBoxLayout()
        self.db_path = QLineEdit(s.database_path)
        db_browse = QPushButton("Choose…")
        db_browse.setProperty("secondary", True)
        db_browse.clicked.connect(lambda: self._browse_dir(self.db_path))
        db_row.addWidget(self.db_path)
        db_row.addWidget(db_browse)
        db_wrap = QWidget()
        db_wrap.setLayout(db_row)
        stor.add_row("Database location", db_wrap)

        img_row = QHBoxLayout()
        self.img_path = QLineEdit(s.image_storage_path)
        img_browse = QPushButton("Choose…")
        img_browse.setProperty("secondary", True)
        img_browse.clicked.connect(lambda: self._browse_dir(self.img_path, dirs=True))
        img_row.addWidget(self.img_path)
        img_row.addWidget(img_browse)
        img_wrap = QWidget()
        img_wrap.setLayout(img_row)
        stor.add_row("Image storage location", img_wrap)

        self.retention = QSpinBox()
        self.retention.setRange(0, 3650)
        self.retention.setSuffix(" days")
        self.retention.setValue(s.history_retention_days)
        stor.add_row("History retention", self.retention,
                     "0 = keep forever. Old entries are removed on startup.")
        cl.addWidget(stor)

        # ---- Performance ----
        perf = _Section("Performance")
        self.max_dim = QSpinBox()
        self.max_dim.setRange(800, 6000)
        self.max_dim.setSingleStep(100)
        self.max_dim.setValue(s.max_image_dim)
        perf.add_row("Maximum image dimension (px)", self.max_dim,
                     "Images larger than this are downscaled before detection.")
        self.device = QComboBox()
        self.device.addItems(["cpu", "cuda"])
        self.device.setCurrentText(s.device)
        perf.add_row("Compute device", self.device,
                     "Only affects the YOLO detector when installed.")
        cl.addWidget(perf)

        # ---- About ----
        about = _Section("About")
        info = QLabel(
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
            "Local-first vehicle number-plate detection for Indian plates. "
            "Computer vision and OCR run entirely on your computer — no cloud required."
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(True)
        cl.addWidget(about)
        cl.addWidget(info)

        cl.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # Save button
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.setProperty("secondary", True)
        self.reset_btn.clicked.connect(self._reset)
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._save)
        save_row.addWidget(self.reset_btn)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

    def _browse_dir(self, target: QLineEdit, dirs: bool = False):
        if dirs:
            path = QFileDialog.getExistingDirectory(self, "Choose directory")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Choose file")
        if path:
            target.setText(path)

    def _on_theme_changed(self, name: str):
        # Apply immediately for instant feedback
        self.theme_changed.emit(name.lower())

    def _reset(self):
        from config.settings import Settings
        defaults = Settings()
        self.theme.setCurrentText(defaults.theme.capitalize())
        self.conf_thr.setValue(defaults.confidence_threshold)
        self.max_det.setValue(defaults.max_detections)
        self.use_classical.setChecked(defaults.use_classical_detector)
        self.use_cascade.setChecked(defaults.use_cascade_detector)
        self.ocr_engine.setCurrentText(defaults.ocr_engine)
        self.ocr_lang.setText(defaults.ocr_language)
        self.ocr_pre.setCurrentText(defaults.preprocessing_mode)
        self.ocr_gpu.setChecked(defaults.ocr_use_gpu)
        self.max_dim.setValue(defaults.max_image_dim)
        self.device.setCurrentText(defaults.device)
        self.retention.setValue(defaults.history_retention_days)

    def _save(self):
        config.update(
            theme=self.theme.currentText().lower(),
            confidence_threshold=float(self.conf_thr.value()),
            max_detections=int(self.max_det.value()),
            use_classical_detector=bool(self.use_classical.isChecked()),
            use_cascade_detector=bool(self.use_cascade.isChecked()),
            ocr_engine=self.ocr_engine.currentText(),
            ocr_language=self.ocr_lang.text().strip() or "en",
            preprocessing_mode=self.ocr_pre.currentText(),
            ocr_use_gpu=bool(self.ocr_gpu.isChecked()),
            database_path=self.db_path.text().strip(),
            image_storage_path=self.img_path.text().strip(),
            history_retention_days=int(self.retention.value()),
            max_image_dim=int(self.max_dim.value()),
            device=self.device.currentText(),
        )
        self.service.reload()
        self.theme_changed.emit(config.settings.theme)
        parent = self.window()
        if hasattr(parent, "show_toast"):
            parent.show_toast("Settings saved.")
