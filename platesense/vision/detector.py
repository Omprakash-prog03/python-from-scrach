"""Number-plate detection.

The detector is designed with a simple pluggable back-end:

  1. :class:`CascadePlateDetector`   – uses OpenCV's Haar cascade (fast, built-in)
  2. :class:`ClassicalPlateDetector` – edges + morphology + contours (model-free)
  3. :class:`YOLOPlateDetector`      – optional YOLO backend when weights exist

The main :class:`PlateDetector` orchestrates them in order of confidence and
returns a list of :class:`PlateDetection` results.  None of the detectors are
allowed to raise on missing data – they degrade gracefully.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass
class PlateDetection:
    """A single plate detection in the source image."""
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    method: str
    crop: np.ndarray = field(repr=False)

    @property
    def area(self) -> int:
        x1, y1, x2, y2 = self.bbox
        return max(0, x2 - x1) * max(0, y2 - y1)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _aspect_ratio_ok(w: int, h: int) -> bool:
    """Indian plates are roughly rectangular: w/h between ~2 and ~7."""
    if w <= 0 or h <= 0:
        return False
    ar = w / float(h)
    return 1.8 <= ar <= 8.0


def _size_ok(w: int, h: int, iw: int, ih: int) -> bool:
    area = w * h
    img_area = iw * ih
    # plate should occupy between ~0.2% and 20% of image area
    return 0.002 * img_area <= area <= 0.25 * img_area


def _clip_box(box: Tuple[int, int, int, int], iw: int, ih: int):
    x1, y1, x2, y2 = box
    x1 = max(0, min(iw - 1, x1))
    y1 = max(0, min(ih - 1, y1))
    x2 = max(0, min(iw, x2))
    y2 = max(0, min(ih, y2))
    return int(x1), int(y1), int(x2), int(y2)


def _nms(detections: List[PlateDetection], iou_thresh: float = 0.5) -> List[PlateDetection]:
    """Simple greedy NMS on detections by confidence."""
    if not detections:
        return []
    dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
    keep: List[PlateDetection] = []
    while dets:
        best = dets.pop(0)
        keep.append(best)
        remaining = []
        bx1, by1, bx2, by2 = best.bbox
        ba = max(0, bx2 - bx1) * max(0, by2 - by1)
        for d in dets:
            x1, y1, x2, y2 = d.bbox
            ix1, iy1 = max(x1, bx1), max(y1, by1)
            ix2, iy2 = min(x2, bx2), min(y2, by2)
            iw = max(0, ix2 - ix1)
            ih = max(0, iy2 - iy1)
            inter = iw * ih
            da = max(0, x2 - x1) * max(0, y2 - y1)
            union = da + ba - inter
            iou = inter / union if union else 0.0
            if iou < iou_thresh:
                remaining.append(d)
        dets = remaining
    return keep


def _crop(image: np.ndarray, box: Tuple[int, int, int, int], pad: float = 0.03) -> np.ndarray:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    x1 = int(max(0, x1 - pad * bw))
    y1 = int(max(0, y1 - pad * bh))
    x2 = int(min(w, x2 + pad * bw))
    y2 = int(min(h, y2 + pad * bh))
    return image[y1:y2, x1:x2].copy()


# ---------------------------------------------------------------------------
# Backend 1 – Haar cascade
# ---------------------------------------------------------------------------

class CascadePlateDetector:
    """OpenCV Haar cascade for Russian plates (works as a weak prior
    for rectangular plates of other regions too, including India)."""

    def __init__(self, cascade_path: Optional[str] = None):
        self.cascade = None
        path = cascade_path
        if path is None:
            # Try to find the built-in OpenCV data directory
            try:
                data_dir = Path(cv2.data.haarcascades)
                candidate = data_dir / "haarcascade_russian_plate_number.xml"
                if candidate.exists():
                    path = str(candidate)
            except Exception:
                path = None
        self.cascade_path = path
        if path and os.path.exists(path):
            self.cascade = cv2.CascadeClassifier(path)
            if self.cascade.empty():
                self.cascade = None
                LOGGER.warning("Cascade empty: %s", path)
        else:
            LOGGER.info("No plate Haar cascade found; cascade detector disabled.")

    def available(self) -> bool:
        return self.cascade is not None

    def detect(self, image: np.ndarray) -> List[PlateDetection]:
        if not self.available():
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        h, w = image.shape[:2]
        try:
            plates = self.cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4,
                minSize=(max(30, w // 20), max(15, h // 30)),
            )
        except Exception as exc:
            LOGGER.debug("Cascade detect error: %s", exc)
            return []
        out: List[PlateDetection] = []
        for (x, y, bw, bh) in plates:
            box = (x, y, x + bw, y + bh)
            if not _aspect_ratio_ok(bw, bh):
                continue
            conf = 0.65  # Cascade doesn't return confidence; use a static estimate
            out.append(PlateDetection(
                bbox=box, confidence=conf, method="cascade", crop=_crop(image, box)
            ))
        return out


# ---------------------------------------------------------------------------
# Backend 2 – Classical (edge / morphology / contours)
# ---------------------------------------------------------------------------

class ClassicalPlateDetector:
    """Model-free detector using edge detection, morphological closing
    and contour aspect-ratio filtering."""

    def __init__(self):
        pass

    def detect(self, image: np.ndarray) -> List[PlateDetection]:
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
        _, edges = cv2.threshold(edges, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Close horizontally to connect characters into a plate blob
        kh, kw = max(3, h // 80), max(7, w // 25)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        closed = cv2.morphologyEx(closed, cv2.MORPH_DILATE,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
                                  iterations=1)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: List[Tuple[Tuple[int, int, int, int], float]] = []
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) < 4:
                continue
            x, y, bw, bh = cv2.boundingRect(approx)
            if not _aspect_ratio_ok(bw, bh):
                continue
            if not _size_ok(bw, bh, w, h):
                continue
            # Score by fill ratio of edges inside the bounding rect
            roi = closed[y:y + bh, x:x + bw]
            fill = roi.mean() / 255.0 if roi.size else 0
            # Rectangularity (area of rect vs contour area)
            rect_area = float(bw * bh)
            cnt_area = float(cv2.contourArea(cnt))
            rect_score = cnt_area / rect_area if rect_area else 0
            score = 0.4 * fill + 0.5 * rect_score + 0.1
            # Strong penalty for contours that are too "tall" or too "wide"
            ar = bw / float(bh)
            if 3.0 <= ar <= 5.5:
                score += 0.05
            score = max(0.0, min(0.9, score))
            candidates.append(((x, y, x + bw, y + bh), score))

        candidates.sort(key=lambda c: c[1], reverse=True)
        out: List[PlateDetection] = []
        for box, score in candidates[:10]:
            box = _clip_box(box, w, h)
            out.append(PlateDetection(
                bbox=box, confidence=float(score),
                method="classical", crop=_crop(image, box),
            ))
        return out


# ---------------------------------------------------------------------------
# Backend 3 – Optional YOLO detector (loaded lazily)
# ---------------------------------------------------------------------------

class YOLOPlateDetector:
    """Optional YOLO-based detector. Activated only if a .pt weights file
    exists at the configured path. We do *not* require ultralytics at import
    time – the detector degrades gracefully if it isn't installed."""

    def __init__(self, weights_path: str, conf: float = 0.35, device: str = "cpu"):
        self.weights_path = weights_path
        self.conf = conf
        self.device = device
        self.model = None
        self._available = None  # tri-state

    def _load(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from ultralytics import YOLO  # type: ignore
        except Exception as exc:
            LOGGER.info("ultralytics not installed (%s); YOLO detector disabled.", exc)
            self._available = False
            return False
        if not os.path.exists(self.weights_path):
            LOGGER.info("YOLO weights missing at %s.", self.weights_path)
            self._available = False
            return False
        try:
            self.model = YOLO(self.weights_path)
            self._available = True
            LOGGER.info("Loaded YOLO weights from %s", self.weights_path)
        except Exception as exc:
            LOGGER.warning("Failed to load YOLO weights: %s", exc)
            self._available = False
        return self._available

    def available(self) -> bool:
        return self._load()

    def detect(self, image: np.ndarray) -> List[PlateDetection]:
        if not self._load() or self.model is None:
            return []
        h, w = image.shape[:2]
        try:
            results = self.model.predict(
                image, conf=self.conf, device=self.device, verbose=False,
            )
        except Exception as exc:
            LOGGER.exception("YOLO inference failed: %s", exc)
            return []
        out: List[PlateDetection] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy
            confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else boxes.conf
            for (x1, y1, x2, y2), c in zip(xyxy, confs):
                box = (int(x1), int(y1), int(x2), int(y2))
                bw, bh = x2 - x1, y2 - y1
                if not _aspect_ratio_ok(bw, bh):
                    continue
                out.append(PlateDetection(
                    bbox=_clip_box(box, w, h),
                    confidence=float(c),
                    method="yolo",
                    crop=_crop(image, box),
                ))
        return out


# ---------------------------------------------------------------------------
# Orchestrating detector
# ---------------------------------------------------------------------------

class PlateDetector:
    """Top-level detector that combines all available backends and returns
    NMS-merged detections."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        cascade_path: Optional[str] = None,
        conf_thresh: float = 0.45,
        nms_thresh: float = 0.45,
        use_classical: bool = True,
        use_cascade: bool = True,
        device: str = "cpu",
    ):
        self.conf_thresh = conf_thresh
        self.nms_thresh = nms_thresh
        self.backends: List = []
        if model_path:
            self.backends.append(YOLOPlateDetector(model_path, conf=conf_thresh, device=device))
        if use_cascade:
            self.backends.append(CascadePlateDetector(cascade_path))
        if use_classical:
            self.backends.append(ClassicalPlateDetector())
        LOGGER.info("PlateDetector initialized with %d backend(s).", len(self.backends))

    def load_model(self) -> bool:
        """Eagerly load all backends; returns True if at least one works."""
        any_ok = False
        for b in self.backends:
            if hasattr(b, "available"):
                if b.available():
                    any_ok = True
            else:
                any_ok = True
        return any_ok

    def detect(self, image: np.ndarray, max_detections: int = 5) -> List[PlateDetection]:
        raw: List[PlateDetection] = []
        for b in self.backends:
            try:
                raw.extend(b.detect(image))
            except Exception as exc:
                LOGGER.exception("Backend %s failed: %s", type(b).__name__, exc)

        # Filter by confidence and aspect-ratio (defensive)
        filtered = [d for d in raw if d.confidence >= self.conf_thresh and
                    _aspect_ratio_ok(d.bbox[2] - d.bbox[0], d.bbox[3] - d.bbox[1])]
        merged = _nms(filtered, iou_thresh=self.nms_thresh)
        merged.sort(key=lambda d: d.confidence, reverse=True)
        return merged[:max_detections]

    def get_best_detection(self, image: np.ndarray) -> Optional[PlateDetection]:
        dets = self.detect(image, max_detections=1)
        return dets[0] if dets else None

    # Keep signature symmetric with the API request
    def draw_detection(
        self,
        image: np.ndarray,
        detections: Sequence[PlateDetection],
        labels: Optional[Sequence[str]] = None,
        color: Tuple[int, int, int] = (88, 209, 48),  # BGR green
    ) -> np.ndarray:
        out = image.copy()
        for i, d in enumerate(detections):
            x1, y1, x2, y2 = d.bbox
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 3, lineType=cv2.LINE_AA)
            text = (labels[i] if labels and i < len(labels)
                    else f"{d.confidence * 100:.1f}%")
            # Label background
            (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(out, (x1, y1 - th - baseline - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(out, text, (x1 + 4, y1 - baseline - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
                        lineType=cv2.LINE_AA)
        return out
