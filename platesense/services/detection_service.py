"""High-level detection service that ties the CV + OCR pipeline together."""
from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from config.settings import config
from ocr.engine import OCRProcessor
from ocr.validator import PlateValidationResult, validate_plate
from vision.annotator import annotate_detections, save_annotated
from vision.detector import PlateDetection, PlateDetector
from vision.preprocessing import (ensure_max_dim, load_image, normalize_image)

LOGGER = logging.getLogger(__name__)


@dataclass
class SinglePlateResult:
    detection: PlateDetection
    ocr_text: str
    ocr_confidence: float
    validation: PlateValidationResult
    crop: np.ndarray
    processing_time: float = 0.0


@dataclass
class DetectionResult:
    success: bool
    message: str
    source_image: Optional[np.ndarray] = None
    annotated_image: Optional[np.ndarray] = None
    plates: List[SinglePlateResult] = field(default_factory=list)
    processing_time: float = 0.0
    error_code: Optional[str] = None
    source_path: Optional[str] = None

    @property
    def best(self) -> Optional[SinglePlateResult]:
        if not self.plates:
            return None
        return max(self.plates, key=lambda p: p.validation.confidence * 0.5
                   + p.detection.confidence * 0.3 + p.ocr_confidence * 0.2)


class DetectionService:
    """Orchestrates loading, detection, OCR and annotation.

    The detector and OCR engine are lazily instantiated and reused across
    calls for performance.
    """

    def __init__(self):
        self._detector: Optional[PlateDetector] = None
        self._ocr: Optional[OCRProcessor] = None

    # ---- lazy getters ----
    def detector(self) -> PlateDetector:
        if self._detector is None:
            s = config.settings
            model_path = s.model_path if os.path.exists(s.model_path) else None
            self._detector = PlateDetector(
                model_path=model_path,
                cascade_path=s.cascade_path or None,
                conf_thresh=s.confidence_threshold,
                nms_thresh=s.nms_threshold,
                use_classical=s.use_classical_detector,
                use_cascade=s.use_cascade_detector,
                device=s.device,
            )
            self._detector.load_model()
        return self._detector

    def ocr(self) -> OCRProcessor:
        if self._ocr is None:
            s = config.settings
            self._ocr = OCRProcessor(engine=s.ocr_engine, lang=s.ocr_language,
                                     gpu=s.ocr_use_gpu)
        return self._ocr

    def reload(self) -> None:
        """Force models to be reloaded (e.g. after settings change)."""
        self._detector = None
        self._ocr = None

    # ---- main entry ----
    def detect_from_path(self, path: str, on_stage=None) -> DetectionResult:
        t0 = time.time()
        LOGGER.info("Detection started: %s", path)
        self._report(on_stage, "Loading image", 0.05)

        validation = load_image(path)
        if not validation.ok or validation.image is None:
            return DetectionResult(success=False,
                                   message=validation.message or "Unable to open this image.",
                                   error_code="invalid_image",
                                   source_path=path)
        img = normalize_image(validation.image)
        img, _ = ensure_max_dim(img, config.settings.max_image_dim)

        self._report(on_stage, "Detecting plate", 0.25)
        dets = self.detector().detect(img, max_detections=config.settings.max_detections)
        LOGGER.info("Detected %d plate(s)", len(dets))

        if not dets:
            return DetectionResult(
                success=False,
                message="No number plate was detected in this image. "
                        "Try a clearer photo with the plate fully visible.",
                error_code="no_plate",
                source_image=img,
                processing_time=time.time() - t0,
                source_path=path,
            )

        self._report(on_stage, "Enhancing plate", 0.55)
        plates: List[SinglePlateResult] = []
        for det in dets:
            crop = det.crop
            if crop.size == 0:
                continue
            self._report(on_stage, "Reading characters", 0.75)
            ocr_res = self.ocr().read_plate(crop)
            v = validate_plate(ocr_res.text)
            plates.append(SinglePlateResult(
                detection=det,
                ocr_text=v.normalized_text or ocr_res.text,
                ocr_confidence=float(ocr_res.confidence),
                validation=v,
                crop=crop,
            ))

        if not plates:
            return DetectionResult(
                success=False,
                message="Plate was located but could not be read. Try a sharper image.",
                error_code="ocr_failed",
                source_image=img,
                processing_time=time.time() - t0,
                source_path=path,
            )

        # If we have plates but none have readable text, still return a result
        # with empty text so the user can see the detection crop and correct it.
        if not any(p.validation.valid or p.ocr_text for p in plates):
            # Build annotated image and return success=True so UI can show the crop
            labels = [f"Plate {i+1}" for i in range(len(plates))]
            annotated = annotate_detections(img, [p.detection for p in plates], labels=labels)
            self._report(on_stage, "Validating result", 0.92)
            self._report(on_stage, "Complete", 1.0)
            LOGGER.info("Detection finished (no OCR) in %.2fs", time.time() - t0)
            return DetectionResult(
                success=True,
                message="Plate located but OCR engine unavailable. Install OCR models to read the plate.",
                source_image=img,
                annotated_image=annotated,
                plates=plates,
                processing_time=time.time() - t0,
                source_path=path,
                error_code="ocr_unavailable",
            )

        self._report(on_stage, "Validating result", 0.92)
        labels = []
        for p in plates:
            if p.validation.valid:
                labels.append(p.validation.normalized_text)
            else:
                labels.append(f"{p.detection.confidence * 100:.0f}%")
        annotated = annotate_detections(img, [p.detection for p in plates], labels=labels)

        self._report(on_stage, "Complete", 1.0)
        LOGGER.info("Detection finished in %.2fs", time.time() - t0)
        return DetectionResult(
            success=True,
            message="Detection complete",
            source_image=img,
            annotated_image=annotated,
            plates=plates,
            processing_time=time.time() - t0,
            source_path=path,
        )

    # ---- helpers ----
    @staticmethod
    def _report(cb, stage: str, progress: float) -> None:
        if cb is not None:
            try:
                cb(stage, progress)
            except Exception:
                LOGGER.debug("Stage callback failed", exc_info=True)

    # ---- persistence helper ----
    def persist_result(self, result: DetectionResult, plate: SinglePlateResult,
                       storage_dir: Optional[str] = None) -> dict:
        """Save images and return metadata ready to insert into DB."""
        storage = Path(storage_dir or config.settings.image_storage_path)
        storage.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        rid = uuid.uuid4().hex[:8]

        src_path = None
        if result.source_image is not None:
            src_path = storage / f"{stamp}_{rid}_vehicle.jpg"
            cv2.imwrite(str(src_path), result.source_image,
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
        crop_path = storage / f"{stamp}_{rid}_plate.jpg"
        cv2.imwrite(str(crop_path), plate.crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        annotated_path = storage / f"{stamp}_{rid}_annotated.jpg"
        if result.annotated_image is not None:
            save_annotated(result.annotated_image, str(annotated_path))

        return {
            "image_path": str(src_path) if src_path else None,
            "plate_crop_path": str(crop_path),
            "annotated_path": str(annotated_path) if result.annotated_image is not None else None,
        }
