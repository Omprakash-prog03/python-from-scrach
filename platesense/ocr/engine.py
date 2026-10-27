"""OCR wrapper with lazy loading and variant-based best-of-N reading.

Two backends are supported:
  * EasyOCR (default) – installed via pip; model downloaded on first use.
  * pytesseract       – uses the system ``tesseract`` binary if available.

Both return normalized (text, confidence) pairs.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .preprocessing import build_variants
from .validator import validate_plate

LOGGER = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: float  # estimated 0..1
    variant: str = ""
    valid: bool = False


class _EasyOCRBackend:
    name = "easyocr"

    def __init__(self, languages=("en",), gpu: bool = False):
        self.reader = None
        self._tried = False
        self.languages = list(languages)
        self.gpu = gpu

    def _load(self):
        if self.reader is not None:
            return True
        if self._tried:
            return False
        self._tried = True
        try:
            import easyocr  # type: ignore
            self.reader = easyocr.Reader(self.languages, gpu=self.gpu, verbose=False)
            LOGGER.info("EasyOCR loaded (languages=%s, gpu=%s)", self.languages, self.gpu)
            return True
        except Exception as exc:
            LOGGER.warning("EasyOCR unavailable: %s", exc)
            self.reader = None
            return False

    def available(self) -> bool:
        return self._load()

    def read(self, image: np.ndarray) -> List[Tuple[str, float]]:
        if not self._load() or self.reader is None:
            return []
        try:
            results = self.reader.readtext(image, detail=1, paragraph=False)
        except Exception as exc:
            LOGGER.exception("EasyOCR read failed: %s", exc)
            return []
        # Each entry: (bbox, text, conf)
        out = []
        for entry in results:
            if len(entry) < 3:
                continue
            _, text, conf = entry
            if text and isinstance(text, str):
                out.append((text, float(conf)))
        return out


class _TesseractBackend:
    name = "pytesseract"

    def __init__(self, lang: str = "eng"):
        self.lang = lang
        self._tess = None
        self._tried = False

    def _load(self):
        if self._tess is not None:
            return True
        if self._tried:
            return False
        self._tried = True
        try:
            import pytesseract  # type: ignore
            # Check that binary is available
            pytesseract.get_tesseract_version()
            self._tess = pytesseract
            return True
        except Exception as exc:
            LOGGER.warning("pytesseract unavailable: %s", exc)
            self._tess = None
            return False

    def available(self) -> bool:
        return self._load()

    def read(self, image: np.ndarray) -> List[Tuple[str, float]]:
        if not self._load() or self._tess is None:
            return []
        try:
            from pytesseract import Output  # type: ignore
            data = self._tess.image_to_data(
                image, lang=self.lang, output_type=Output.DICT,
                config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- ",
            )
            pieces = []
            for txt, conf in zip(data["text"], data["conf"]):
                if txt and txt.strip():
                    try:
                        c = float(conf) / 100.0
                    except Exception:
                        c = 0.3
                    pieces.append((txt.strip(), max(0.0, min(1.0, c))))
            if pieces:
                combined_text = "".join(p for p, _ in pieces)
                avg_conf = float(np.mean([c for _, c in pieces]))
                return [(combined_text, avg_conf)]
        except Exception as exc:
            LOGGER.exception("Tesseract read failed: %s", exc)
        return []


class OCRProcessor:
    """OCR with lazy loading and multiple preprocessing variants."""

    def __init__(self, engine: str = "easyocr", lang: str = "en", gpu: bool = False):
        self.engine_name = engine
        self.gpu = gpu
        self.lang = lang
        self._backend = None
        self._build_backend()

    def _build_backend(self):
        eng = self.engine_name.lower()
        if eng == "easyocr":
            # "en" maps to ["en"]; allow "hi", etc.
            languages = [self.lang] if self.lang else ["en"]
            self._backend = _EasyOCRBackend(languages=languages, gpu=self.gpu)
        elif eng == "pytesseract":
            self._backend = _TesseractBackend(lang=self.lang or "eng")
        else:
            LOGGER.warning("Unknown OCR engine %s; falling back to easyocr.", eng)
            self._backend = _EasyOCRBackend(languages=["en"], gpu=self.gpu)

    def available(self) -> bool:
        return self._backend is not None and self._backend.available()

    def reload(self, engine: Optional[str] = None, lang: Optional[str] = None,
               gpu: Optional[bool] = None) -> None:
        if engine:
            self.engine_name = engine
        if lang is not None:
            self.lang = lang
        if gpu is not None:
            self.gpu = gpu
        self._backend = None
        self._build_backend()

    # --- core ---
    def read_plate(self, plate_bgr: np.ndarray) -> OCRResult:
        """Run OCR across variants and return the best validated result."""
        if self._backend is None or not self._backend.available():
            return OCRResult(text="", confidence=0.0, variant="", valid=False)

        variants = build_variants(plate_bgr)
        candidates: List[OCRResult] = []
        for name, img in variants:
            try:
                readings = self._backend.read(img)
            except Exception as exc:
                LOGGER.exception("OCR read error on variant %s: %s", name, exc)
                readings = []
            for txt, conf in readings:
                validation = validate_plate(txt)
                combined = conf * 0.6 + validation.confidence * 0.4
                candidates.append(OCRResult(
                    text=validation.normalized_text or txt.strip(),
                    confidence=combined,
                    variant=name,
                    valid=validation.valid,
                ))

        if not candidates:
            return OCRResult(text="", confidence=0.0, variant="", valid=False)

        # Prefer valid plates; among them pick highest combined confidence
        valid_ones = [c for c in candidates if c.valid]
        best = max(valid_ones, key=lambda c: c.confidence) if valid_ones else \
               max(candidates, key=lambda c: c.confidence)
        return best
