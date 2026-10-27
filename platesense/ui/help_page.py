"""Help & Feedback page."""
from __future__ import annotations

from PySide6.QtWidgets import (QFrame, QLabel, QVBoxLayout, QWidget)


HELP_HTML = """
<h3 style="margin-top:0">Getting started</h3>
<ul>
  <li>From the <b>Overview</b> or <b>Detect Plate</b> page, drop or choose a vehicle photo.</li>
  <li>PlateSense will locate the plate, read it, and show the recognised number.</li>
  <li>Use <b>Save to History</b> to keep the detection for later; <b>Export</b> to share.</li>
</ul>

<h3>Tips for reliable recognition</h3>
<ul>
  <li>Capture the plate straight-on, not at a steep angle.</li>
  <li>Avoid strong glare, heavy shadows and motion blur.</li>
  <li>The plate should occupy roughly 5–20% of the photo.</li>
  <li>For Indian plates, include the state code and the trailing 4 digits clearly.</li>
</ul>

<h3>Supported formats</h3>
<p>JPG, JPEG, PNG, WEBP, BMP — up to 20 MB each.</p>

<h3>Privacy</h3>
<p>All processing happens on your computer. No image is sent to a cloud service.
Detections and images are stored in your local application data folder.</p>

<h3>Keyboard</h3>
<ul>
  <li><b>Ctrl/Cmd + O</b> — open an image</li>
  <li><b>Ctrl/Cmd + = / -</b> — zoom (on the result screen)</li>
  <li><b>Esc</b> — return to upload</li>
</ul>

<h3>Feedback</h3>
<p>For issues or ideas, open an issue on the project's repository.</p>
"""


class HelpPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)

        title = QLabel("Help & Feedback")
        title.setProperty("title", True)
        sub = QLabel("How to use PlateSense and get the best results.")
        sub.setProperty("subtitle", True)
        root.addWidget(title)
        root.addWidget(sub)

        card = QFrame()
        card.setProperty("card", True)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(26, 24, 26, 24)
        body = QLabel(HELP_HTML)
        body.setWordWrap(True)
        body.setOpenExternalLinks(True)
        cl.addWidget(body)
        root.addWidget(card, 1)
