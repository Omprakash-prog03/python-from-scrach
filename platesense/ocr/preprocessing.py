"""Preprocessing pipeline applied to cropped plate images before OCR."""
from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np


def upscale(plate: np.ndarray, target_h: int = 128) -> np.ndarray:
    h, w = plate.shape[:2]
    if h >= target_h:
        return plate
    scale = target_h / float(h)
    return cv2.resize(plate, (int(w * scale), int(h * scale)),
                      interpolation=cv2.INTER_CUBIC)


def to_grayscale(plate: np.ndarray) -> np.ndarray:
    if len(plate.shape) == 2:
        return plate
    return cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)


def denoise(gray: np.ndarray) -> np.ndarray:
    return cv2.bilateralFilter(gray, 7, 70, 70)


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def otsu_threshold(gray: np.ndarray) -> np.ndarray:
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 11
    )


def sharpen(gray: np.ndarray) -> np.ndarray:
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    return cv2.filter2D(gray, cv2.CV_8U, kernel)


def morph_open(th: np.ndarray) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(th, cv2.MORPH_OPEN, k)


def _gray_3ch(gray: np.ndarray) -> np.ndarray:
    """Many OCR engines expect a 3-channel image."""
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def build_variants(plate_bgr: np.ndarray) -> List[Tuple[str, np.ndarray]]:
    """Return a list of (label, prepared_image) variants to feed OCR.

    The caller selects the highest-confidence OCR output across variants.
    """
    plate = upscale(plate_bgr)
    gray = to_grayscale(plate)
    gray = denoise(gray)
    eq = enhance_contrast(gray)

    variants: List[Tuple[str, np.ndarray]] = []
    variants.append(("gray", _gray_3ch(gray)))
    variants.append(("clahe", _gray_3ch(eq)))
    variants.append(("otsu", _gray_3ch(otsu_threshold(eq))))
    variants.append(("adaptive", _gray_3ch(adaptive_threshold(eq))))
    variants.append(("sharp", _gray_3ch(sharpen(eq))))
    variants.append(("sharp_otsu", _gray_3ch(otsu_threshold(sharpen(eq)))))
    return variants
