"""Tests for image preprocessing helpers."""
import numpy as np
import cv2
import pytest

from vision import preprocessing as p
from vision import detector as d


def test_ensure_max_dim_noop():
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    out, scale = p.ensure_max_dim(img, 1000)
    assert out.shape == img.shape
    assert scale == 1.0


def test_ensure_max_dim_downscale():
    img = np.zeros((3000, 4000, 3), dtype=np.uint8)
    out, scale = p.ensure_max_dim(img, 1200)
    assert out.shape[0] <= 1200 and out.shape[1] <= 1200
    assert 0 < scale < 1


def test_normalize_gray_to_bgr():
    img = np.zeros((100, 100), dtype=np.uint8)
    out = p.normalize_image(img)
    assert len(out.shape) == 3


def test_classical_detector_runs():
    det = d.ClassicalPlateDetector()
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (60, 60, 70)
    cv2.rectangle(img, (200, 300), (480, 370), (250, 250, 250), -1)
    plates = det.detect(img)
    # may or may not fire on this synthetic input but must not crash
    assert isinstance(plates, list)
