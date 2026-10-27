"""General image preprocessing utilities.

These functions operate on NumPy BGR images (OpenCV format) and are used
before plate detection and before OCR.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np


@dataclass
class ImageValidationResult:
    ok: bool
    message: str
    image: np.ndarray | None = None


def is_valid_image_bytes(data: bytes) -> bool:
    """Validate raw bytes decode to an image using Pillow first (safer)."""
    try:
        from PIL import Image, UnidentifiedImageError
        import io
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        return True
    except Exception:
        return False


def load_image(path: str) -> ImageValidationResult:
    """Load and validate an image from disk. Returns BGR (OpenCV) image."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except (OSError, PermissionError) as exc:
        return ImageValidationResult(False, f"Cannot read file: {exc}")

    if not is_valid_image_bytes(data):
        return ImageValidationResult(False, "File is not a valid image.")

    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return ImageValidationResult(False, "Unable to decode image.")
    return ImageValidationResult(True, "ok", img)


def ensure_max_dim(image: np.ndarray, max_dim: int = 2400) -> Tuple[np.ndarray, float]:
    """Downscale *image* so its longest side is <= max_dim; returns (img, scale)."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return image, 1.0
    scale = max_dim / longest
    new_size = (int(round(w * scale)), int(round(h * scale)))
    resized = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
    return resized, scale


def normalize_image(image: np.ndarray) -> np.ndarray:
    """Basic normalization: 8-bit, BGR, no-op if already good."""
    if image.dtype != np.uint8:
        image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image


def to_rgb(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def to_bgr(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
