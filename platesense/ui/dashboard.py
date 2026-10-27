"""Overview/Dashboard page."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from ui.widgets.drop_area import DropArea
from ui.widgets.stat_card import StatCard


class DashboardPage(QWidget):
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(24)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)
        self.greeting = QLabel("Good afternoon.")
        self.greeting.setProperty("title", True)
        sub = QLabel("Detect a vehicle plate in seconds.")
        sub.setProperty("subtitle", True)
        header.addWidget(self.greeting)
        header.addWidget(sub)
        root.addLayout(header)

        # Scrollable area to keep everything responsive
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(28)

        # Upload card
        self.drop_area = DropArea()
        self.drop_area.file_selected.connect(self.file_selected)
        cl.addWidget(self.drop_area)

        # Stat cards
        grid = QGridLayout()
        grid.setSpacing(16)
        self.card_week = StatCard("Detections This Week", "0", "Last 7 days")
        self.card_conf = StatCard("Average Confidence", "0.0%", "Across all time")
        self.card_time = StatCard("Average Processing Time", "0.00s", "Per detection")
        self.card_total = StatCard("Total Detections", "0", "Saved in history")
        for i, w in enumerate((self.card_week, self.card_conf, self.card_time, self.card_total)):
            grid.addWidget(w, 0, i)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)
        cl.addLayout(grid)

        # Recent detections
        recent_holder = QFrame()
        recent_holder.setProperty("card", True)
        rl = QVBoxLayout(recent_holder)
        rl.setContentsMargins(24, 22, 24, 22)
        rl.setSpacing(12)
        rh = QLabel("Recent Detections")
        rh.setProperty("cardTitle", True)
        rl.addWidget(rh)
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(8)
        self.recent_list.addStretch(1)
        rl.addLayout(self.recent_list)
        self._empty_recent = QLabel("No detections yet. Upload an image to get started.")
        self._empty_recent.setProperty("muted", True)
        rl.insertWidget(self.recent_list.count(), self._empty_recent)
        cl.addWidget(recent_holder, 1)

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # Initialize greetings by time
        self._set_greeting()

    def _set_greeting(self):
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            greet = "Good morning."
        elif hour < 18:
            greet = "Good afternoon."
        else:
            greet = "Good evening."
        self.greeting.setText(greet)

    def set_stats(self, stats: dict, recent: list):
        self.card_week.set_value(str(stats.get("week", 0)))
        avg_conf = stats.get("avg_confidence", 0.0)
        self.card_conf.set_value(f"{avg_conf * 100:.1f}%")
        avg_t = stats.get("avg_processing_time", 0.0)
        self.card_time.set_value(f"{avg_t:.2f}s")
        self.card_total.set_value(str(stats.get("total", 0)))

        # Clear existing recent items (but not the stretch)
        while self.recent_list.count() > 1:
            item = self.recent_list.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._empty_recent.setVisible(not recent)
        for r in recent[:5]:
            row = QHBoxLayout()
            plate = QLabel(r.normalized_plate)
            f = QFont()
            f.setPointSize(15)
            f.setWeight(QFont.DemiBold)
            plate.setFont(f)
            region = QLabel(r.state or "Unknown region")
            region.setProperty("muted", True)
            conf = QLabel(f"{r.overall_confidence * 100:.1f}%")
            conf.setProperty("success", True)
            f2 = QFont()
            f2.setPointSize(13)
            f2.setWeight(QFont.DemiBold)
            conf.setFont(f2)
            row.addWidget(plate)
            row.addSpacing(12)
            row.addWidget(region, 1)
            row.addWidget(conf, alignment=Qt.AlignRight)
            wrap = QWidget()
            wrap.setLayout(row)
            self.recent_list.insertWidget(self.recent_list.count() - 1, wrap)
