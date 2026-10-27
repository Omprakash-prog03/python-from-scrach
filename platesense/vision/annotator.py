"""Annotation utilities for drawing detection boxes, labels and metadata."""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

import cv2
import numpy as np

from .detector import PlateDetection

GREEN = (88, 209, 48)
BLUE = (255, 127, 10)  # BGR
RED = (70, 70, 240)
DARK = (40, 40, 40)
WHITE = (255, 255, 255)


def draw_rounded_rect(img, pt1, pt2, color, thickness=2, radius=12, fill=False):
    x1, y1 = pt1
    x2, y2 = pt2
    if fill:
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1)
    else:
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, thickness,
                      lineType=cv2.LINE_AA)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, thickness,
                      lineType=cv2.LINE_AA)
    cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color,
                thickness if not fill else -1, lineType=cv2.LINE_AA)
    cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color,
                thickness if not fill else -1, lineType=cv2.LINE_AA)
    cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color,
                thickness if not fill else -1, lineType=cv2.LINE_AA)
    cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color,
                thickness if not fill else -1, lineType=cv2.LINE_AA)


def annotate_detections(
    image: np.ndarray,
    detections: Iterable[PlateDetection],
    labels: Optional[Iterable[str]] = None,
    primary_color: Tuple[int, int, int] = GREEN,
) -> np.ndarray:
    out = image.copy()
    labels = list(labels) if labels is not None else []
    for i, det in enumerate(detections):
        x1, y1, x2, y2 = det.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), primary_color, 3, lineType=cv2.LINE_AA)
        label = labels[i] if i < len(labels) else f"{det.confidence * 100:.1f}%"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.7
        thick = 2
        (tw, th), base = cv2.getTextSize(label, font, scale, thick)
        # Label pill
        pad = 8
        ly2 = y1
        ly1 = y1 - th - base - pad * 2
        lx1, lx2 = x1, x1 + tw + pad * 2
        cv2.rectangle(out, (lx1, ly1), (lx2, ly2), primary_color, -1, lineType=cv2.LINE_AA)
        cv2.putText(out, label, (lx1 + pad, ly1 + th + pad // 2),
                    font, scale, WHITE, thick, lineType=cv2.LINE_AA)
    return out


def save_annotated(image: np.ndarray, path: str) -> None:
    """Save a BGR image as JPEG/PNG using the extension from path."""
    import os
    ext = os.path.splitext(path)[1].lower() or ".jpg"
    params = []
    if ext in (".jpg", ".jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, 92]
    elif ext == ".png":
        params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
    ok, buf = cv2.imencode(ext, image, params)
    if ok:
        with open(path, "wb") as f:
            f.write(buf.tobytes())
