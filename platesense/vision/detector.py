"""Number-plate detection.

The detector is designed with pluggable back-ends and merges results via NMS:

  1. :class:`YOLOPlateDetector`      – optional YOLO backend when weights exist
  2. :class:`CascadePlateDetector`   – OpenCV's Haar cascade (built-in)
  3. :class:`ClassicalPlateDetector` – edges + morphology + contours (model-free)

None of the detectors raise on missing data – they degrade gracefully.
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

# Indian plates are roughly rectangular, w/h ~ 2 to 6
_AR_MIN, _AR_MAX = 1.8, 7.0
# Plate should occupy ~0.15% to ~25% of image area
_AREA_MIN, _AREA_MAX = 0.0015, 0.30


def _aspect_ratio_ok(w: int, h: int) -> bool:
    if w <= 4 or h <= 4:
        return False
    ar = w / float(h)
    return _AR_MIN <= ar <= _AR_MAX


def _size_ok(w: int, h: int, iw: int, ih: int) -> bool:
    area = w * h
    img_area = iw * ih
    return _AREA_MIN * img_area <= area <= _AREA_MAX * img_area


def _clip_box(box: Sequence[float], iw: int, ih: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = (float(v) for v in box)
    x1 = max(0, min(iw - 1, x1))
    y1 = max(0, min(ih - 1, y1))
    x2 = max(x1 + 1, min(iw, x2))
    y2 = max(y1 + 1, min(ih, y2))
    return int(x1), int(y1), int(x2), int(y2)


def _nms(detections: List[PlateDetection], iou_thresh: float = 0.5) -> List[PlateDetection]:
    """Greedy non-maximum suppression by confidence."""
    if not detections:
        return []
    dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
    keep: List[PlateDetection] = []
    while dets:
        best = dets.pop(0)
        keep.append(best)
        bx1, by1, bx2, by2 = best.bbox
        ba = max(0, bx2 - bx1) * max(0, by2 - by1)
        remaining: List[PlateDetection] = []
        for d in dets:
            x1, y1, x2, y2 = d.bbox
            ix1, iy1 = max(x1, bx1), max(y1, by1)
            ix2, iy2 = min(x2, bx2), min(y2, by2)
            iw = max(0, ix2 - ix1)
            ih = max(0, iy2 - iy1)
            inter = iw * ih
            da = max(0, x2 - x1) * max(0, y2 - y1)
            union = da + ba - inter
            iou = inter / union if union > 0 else 0.0
            if iou < iou_thresh:
                remaining.append(d)
        dets = remaining
    return keep


def _crop(image: np.ndarray, box: Tuple[int, int, int, int], pad: float = 0.06) -> np.ndarray:
    """Return a padded copy of the region defined by box."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = max(1, x2 - x1), max(1, y2 - y1)
    # Clamp padding so we don't blow out past the image
    px = int(pad * bw)
    py = int(pad * bh)
    nx1 = max(0, x1 - px)
    ny1 = max(0, y1 - py)
    nx2 = min(w, x2 + px)
    ny2 = min(h, y2 + py)
    out = image[ny1:ny2, nx1:nx2].copy()
    if out.size == 0:
        out = image[y1:y2, x1:x2].copy()
    return out


# ---------------------------------------------------------------------------
# Backend 1 – Haar cascade
# ---------------------------------------------------------------------------

class CascadePlateDetector:
    """OpenCV Haar cascade for Russian plates (serves as a weak prior
    for rectangular plates in other regions too, including India)."""

    def __init__(self, cascade_path: Optional[str] = None):
        self.cascade = None
        path = cascade_path
        if path is None:
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
                gray,
                scaleFactor=1.08,
                minNeighbors=5,
                minSize=(max(40, w // 20), max(15, h // 30)),
                maxSize=(w // 2, h // 2),
            )
        except Exception as exc:
            LOGGER.debug("Cascade detect error: %s", exc)
            return []
        out: List[PlateDetection] = []
        for (x, y, bw, bh) in plates:
            if not _aspect_ratio_ok(bw, bh):
                continue
            if not _size_ok(bw, bh, w, h):
                continue
            box = (int(x), int(y), int(x + bw), int(y + bh))
            out.append(PlateDetection(
                bbox=box,
                confidence=0.6,
                method="cascade",
                crop=_crop(image, box),
            ))
        return out


# ---------------------------------------------------------------------------
# Backend 2 – Classical (edge / morphology / contours) – multi-kernel + MSER
# ---------------------------------------------------------------------------

class ClassicalPlateDetector:
    """Model-free detector using multiple strategies:

    * Sobel/Canny edge + horizontal morphological closing at several kernel widths
    * MSER blob detection for character groups
    Results are merged via NMS.
    """

    def __init__(self):
        pass

    @staticmethod
    def _edge_boxes(gray: np.ndarray, h: int, w: int) -> List[Tuple[Tuple[int,int,int,int],float,str]]:
        """Run the edge+morphology pipeline at multiple kernel sizes."""
        candidates: List[Tuple[Tuple[int,int,int,int],float,str]] = []

        # Bilateral denoise preserves edges
        gray_d = cv2.bilateralFilter(gray, 9, 75, 75)

        # Sobel magnitude (proper 16S to avoid clipping)
        gx = cv2.Sobel(gray_d, cv2.CV_16S, 1, 0, ksize=3)
        gy = cv2.Sobel(gray_d, cv2.CV_16S, 0, 1, ksize=3)
        mag = cv2.magnitude(gx.astype(np.float32), gy.astype(np.float32))
        # Normalize to 0..255 and threshold
        mag = np.clip(mag, 0, None)
        if mag.max() > 0:
            mag = (mag / mag.max() * 255).astype(np.uint8)
        else:
            mag = np.zeros_like(gray)
        _, edges = cv2.threshold(mag, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Also try Canny as an alternative edge map
        edges2 = cv2.Canny(gray_d, 60, 180)

        for edge_map, tag in ((edges, "sobel"), (edges2, "canny")):
            # Try several horizontal closing kernels to capture plates
            # at different sizes/aspect ratios within the image.
            for kx in (max(11, w // 35), max(21, w // 20), max(35, w // 12)):
                for ky in (max(3, h // 100), max(5, h // 60)):
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kx, ky))
                    closed = cv2.morphologyEx(edge_map, cv2.MORPH_CLOSE, kernel)
                    closed = cv2.dilate(closed, cv2.getStructuringElement(cv2.MORPH_RECT, (3,3)), iterations=1)

                    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    for cnt in contours:
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        if not _aspect_ratio_ok(bw, bh):
                            continue
                        if not _size_ok(bw, bh, w, h):
                            continue

                        # Fill ratio inside the bbox (density of edge pixels)
                        roi = closed[y:y+bh, x:x+bw]
                        fill = float(cv2.countNonZero(roi)) / max(1, roi.size)

                        # Rectangularity
                        cnt_area = float(cv2.contourArea(cnt))
                        rect_area = float(bw * bh)
                        rect_score = cnt_area / rect_area if rect_area else 0

                        ar = bw / float(bh)
                        ar_bonus = 0.10 if 3.0 <= ar <= 5.5 else 0.0

                        score = 0.35 * fill + 0.45 * min(rect_score, 1.0) + 0.10 + ar_bonus
                        score = float(max(0.0, min(0.92, score)))
                        candidates.append(((int(x), int(y), int(x+bw), int(y+bh)), score, tag))
        return candidates

    def detect(self, image: np.ndarray) -> List[PlateDetection]:
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        candidates = self._edge_boxes(gray, h, w)

        # Convert to PlateDetection (pre-NMS), dedup via NMS per-method first
        dets: List[PlateDetection] = []
        for box, score, method in candidates:
            box = _clip_box(box, w, h)
            bw = box[2] - box[0]; bh = box[3] - box[1]
            if not _aspect_ratio_ok(bw, bh):
                continue
            dets.append(PlateDetection(
                bbox=box, confidence=score,
                method=f"classical_{method}", crop=_crop(image, box),
            ))

        # Merge classical detections
        merged = _nms(dets, iou_thresh=0.3)

        # Sort by score and cap
        merged.sort(key=lambda d: d.confidence, reverse=True)
        return merged[:6]


# ---------------------------------------------------------------------------
# Backend 3 – Optional YOLO detector (loaded lazily)
# ---------------------------------------------------------------------------

class YOLOPlateDetector:
    """Optional YOLO-based detector. Activated only if a .pt weights file
    exists at the configured path. ultralytics is imported lazily so the
    app works without it installed."""

    def __init__(self, weights_path: str, conf: float = 0.35, device: str = "cpu"):
        self.weights_path = weights_path
        self.conf = conf
        self.device = device
        self.model = None
        self._available = None

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
            try:
                xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.asarray(boxes.xyxy)
                confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else np.asarray(boxes.conf)
            except Exception:
                continue
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
    """Top-level detector combining all available backends, NMS-merged."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        cascade_path: Optional[str] = None,
        conf_thresh: float = 0.35,
        nms_thresh: float = 0.35,
        use_classical: bool = True,
        use_cascade: bool = True,
        device: str = "cpu",
    ):
        self.conf_thresh = conf_thresh
        self.nms_thresh = nms_thresh
        self.backends: List = []
        # Order matters: highest-quality detector first
        if model_path:
            self.backends.append(YOLOPlateDetector(model_path, conf=conf_thresh, device=device))
        if use_cascade:
            self.backends.append(CascadePlateDetector(cascade_path))
        if use_classical:
            self.backends.append(ClassicalPlateDetector())
        LOGGER.info("PlateDetector initialized with %d backend(s): %s",
                    len(self.backends), [type(b).__name__ for b in self.backends])

    def load_model(self) -> bool:
        """Eagerly load all backends; returns True if at least one works."""
        any_ok = False
        for b in self.backends:
            if hasattr(b, "available"):
                try:
                    if b.available():
                        any_ok = True
                except Exception as exc:
                    LOGGER.warning("Backend %s unavailable: %s", type(b).__name__, exc)
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

        # Filter by confidence and aspect-ratio
        filtered: List[PlateDetection] = []
        for d in raw:
            bw = d.bbox[2] - d.bbox[0]
            bh = d.bbox[3] - d.bbox[1]
            if d.confidence < self.conf_thresh:
                continue
            if not _aspect_ratio_ok(bw, bh):
                continue
            if d.crop is None or d.crop.size == 0:
                continue
            filtered.append(d)

        merged = _nms(filtered, iou_thresh=self.nms_thresh)
        merged.sort(key=lambda d: d.confidence, reverse=True)
        return merged[:max_detections]

    def get_best_detection(self, image: np.ndarray) -> Optional[PlateDetection]:
        dets = self.detect(image, max_detections=1)
        return dets[0] if dets else None

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
            (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(out, (x1, y1 - th - baseline - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(out, text, (x1 + 4, y1 - baseline - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
                        lineType=cv2.LINE_AA)
        return out
