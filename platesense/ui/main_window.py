"""PlateSense main window with sidebar and QStackedWidget navigation."""
from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence, QPainter, QPixmap, QColor
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from config.settings import APP_NAME, APP_SUBTITLE, config
from services.detection_service import DetectionService
from services.history_service import HistoryService
from ui.dashboard import DashboardPage
from ui.detect_page import DetectPage
from ui.help_page import HelpPage
from ui.history_page import HistoryPage
from ui.models_page import ModelsPage
from ui.settings_page import SettingsPage
from ui.theme import DARK, LIGHT, build_stylesheet
from ui.widgets.toast import Toast


def _make_icon(glyph: str, color: str = "#8E8E93", size: int = 18) -> QIcon:
    """Draw simple unicode-based glyph icons (no external assets needed)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(color))
    f = QFont()
    f.setPointSize(int(size * 0.7))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, glyph)
    p.end()
    return QIcon(pm)


class SidebarNav(QFrame):
    def __init__(self, on_navigate, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 24, 14, 18)
        lay.setSpacing(22)

        # Brand
        brand = QVBoxLayout()
        brand.setSpacing(2)
        name = QLabel(APP_NAME)
        name.setObjectName("brand")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("subtitle")
        brand.addWidget(name)
        brand.addWidget(subtitle)
        lay.addLayout(brand)

        # Nav buttons
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.nav_layout = QVBoxLayout()
        self.nav_layout.setSpacing(4)

        self._buttons = []
        items = [
            ("Overview",        "⌂",  "dashboard"),
            ("Detect Plate",    "◎", "detect"),
            ("History",         "⌕", "history"),
            ("Models",          "◈", "models"),
        ]
        for label, glyph, key in items:
            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.setIcon(_make_icon(glyph))
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: on_navigate(k))
            self.group.addButton(btn)
            self.nav_layout.addWidget(btn)
            self._buttons.append((key, btn))

        lay.addLayout(self.nav_layout)
        lay.addStretch(1)

        # Bottom
        bottom = QVBoxLayout()
        bottom.setSpacing(4)
        for label, glyph, key in [("Settings", "⚙", "settings"),
                                  ("Help & Feedback", "?", "help")]:
            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.setIcon(_make_icon(glyph))
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: on_navigate(k))
            self.group.addButton(btn)
            bottom.addWidget(btn)
            self._buttons.append((key, btn))
        lay.addLayout(bottom)

    def select(self, key: str):
        for k, btn in self._buttons:
            if k == key:
                btn.setChecked(True)
                return


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1200, 720)

        # Services (lazy-ish)
        self.detection_service = DetectionService()
        self.history_service = HistoryService()

        # Apply theme
        self._theme_mode = config.settings.theme
        self._apply_theme(self._theme_mode)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = SidebarNav(self._navigate)
        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # Build pages
        self.dashboard = DashboardPage()
        self.detect_page = DetectPage(self.detection_service)
        self.history_page = HistoryPage(self.history_service)
        self.models_page = ModelsPage(self.detection_service)
        self.settings_page = SettingsPage(self.detection_service)
        self.help_page = HelpPage()

        for w in (self.dashboard, self.detect_page, self.history_page,
                  self.models_page, self.settings_page, self.help_page):
            self.stack.addWidget(w)

        # Connect signals
        self.dashboard.file_selected.connect(self._start_detection)
        self.detect_page.request_toast.connect(self.show_toast)
        self.detect_page.saved_to_history.connect(self._on_history_changed)
        self.history_page.request_toast.connect(self.show_toast)
        self.settings_page.theme_changed.connect(self._apply_theme)

        # Toast
        self.toast = Toast(self)

        # Shortcuts
        self._build_shortcuts()

        # Start at dashboard
        self._navigate("dashboard")
        self._refresh_dashboard()

    # ---------- theme ----------
    def _apply_theme(self, mode: str):
        if mode == "system":
            # Light is a safe default for system
            mode = "light"
        palette = DARK if mode == "dark" else LIGHT
        self._current_palette = palette
        self.setStyleSheet(build_stylesheet(palette))
        # force children to repolish
        QApplication.instance().setPalette(QApplication.instance().palette())

    # ---------- navigation ----------
    def _navigate(self, key: str):
        page = {
            "dashboard": self.dashboard,
            "detect": self.detect_page,
            "history": self.history_page,
            "models": self.models_page,
            "settings": self.settings_page,
            "help": self.help_page,
        }.get(key, self.dashboard)
        self.stack.setCurrentWidget(page)
        self.sidebar.select(key)
        if key == "dashboard":
            self._refresh_dashboard()
        if key == "history":
            self.history_page.refresh()
        if key == "models":
            self.models_page.refresh()

    def _start_detection(self, path: str):
        self._navigate("detect")
        # Trigger the detection: simulate choosing file via detect page
        self.detect_page._start_from_path(path)

    # ---------- misc ----------
    def _refresh_dashboard(self):
        try:
            apply_retention = config.db.apply_retention(config.settings.history_retention_days) \
                if False else None  # retention can be called optionally
            stats = self.history_service.stats()
            recent = self.history_service.recent(5)
            self.dashboard.set_stats(stats, recent)
        except Exception:
            self.dashboard.set_stats({"week": 0, "avg_confidence": 0.0,
                                      "avg_processing_time": 0.0, "total": 0}, [])

    def _on_history_changed(self, rid: int):
        self._refresh_dashboard()

    def show_toast(self, message: str):
        self.toast.setParent(self.centralWidget())
        self.toast.show_message(message)
        QTimer.singleShot(100, self.toast.update_position)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self.toast.update_position()

    def _build_shortcuts(self):
        act_open = QAction(self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(lambda: self._navigate("detect"))
        self.addAction(act_open)

        act_esc = QAction(self)
        act_esc.setShortcut(QKeySequence.Cancel)
        act_esc.triggered.connect(lambda: self.detect_page._show_upload()
                                  if self.stack.currentWidget() is self.detect_page else None)
        self.addAction(act_esc)


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("PlateSense")
    window = MainWindow()
    window.show()
    return app.exec()
