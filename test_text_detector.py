# tests/test_text_detector.py
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: test_text_detector.py
Description: Unit and performance tests for TextDetector.
"""

import time
from typing import Generator

import cv2
import numpy as np
import pytest

from src.services.text_detector import TextDetector


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def detector() -> TextDetector:
    """Return a TextDetector instance with default parameters."""
    return TextDetector()


@pytest.fixture
def blank_frame() -> np.ndarray:
    """Return a 320x240 black BGR frame."""
    return np.zeros((240, 320, 3), dtype=np.uint8)


@pytest.fixture
def text_frame() -> np.ndarray:
    """
    Generate a synthetic BGR image with black rectangles resembling text lines.
    Returns a 320x240 image with white background and several dark rectangles.
    """
    frame = np.full((240, 320, 3), 255, dtype=np.uint8)  # white background
    # Draw some black rectangles (simulate text lines)
    cv2.rectangle(frame, (30, 50), (280, 70), (0, 0, 0), -1)   # thick line
    cv2.rectangle(frame, (30, 80), (250, 95), (0, 0, 0), -1)
    cv2.rectangle(frame, (30, 105), (200, 120), (0, 0, 0), -1)
    cv2.rectangle(frame, (30, 130), (220, 145), (0, 0, 0), -1)
    return frame


@pytest.fixture
def corrupt_frame_2d() -> np.ndarray:
    """Return a 2D array (missing channel axis)."""
    return np.zeros((240, 320), dtype=np.uint8)


@pytest.fixture
def corrupt_frame_wrong_dtype() -> np.ndarray:
    """Return a 3D array with float dtype (invalid for detector)."""
    return np.zeros((240, 320, 3), dtype=np.float32)


# -----------------------------------------------------------------------------
# Constructor Validation Tests
# -----------------------------------------------------------------------------

def test_init_default_does_not_raise() -> None:
    """TextDetector() should instantiate without error."""
    detector = TextDetector()
    assert isinstance(detector, TextDetector)


@pytest.mark.parametrize("sensitivity", [-0.1, 1.1, 1.5])
def test_init_invalid_sensitivity_raises(sensitivity: float) -> None:
    """Sensitivity outside [0.0, 1.0] must raise ValueError."""
    with pytest.raises(ValueError, match="sensitivity must be in"):
        TextDetector(sensitivity=sensitivity)


@pytest.mark.parametrize("min_area", [0])
def test_init_invalid_min_area(min_area: int) -> None:
    """min_area < 1 must raise ValueError."""
    with pytest.raises(ValueError, match="min_area must be >= 1"):
        TextDetector(min_area=min_area)


def test_init_aspect_ratio_bounds_raises() -> None:
    """aspect_ratio_min >= aspect_ratio_max must raise ValueError."""
    with pytest.raises(ValueError, match="must be <"):
        TextDetector(aspect_ratio_min=5.0, aspect_ratio_max=0.2)


@pytest.mark.parametrize("min_solidity", [-0.1, 1.1])
def test_init_invalid_min_solidity(min_solidity: float) -> None:
    """min_solidity outside [0.0, 1.0] must raise ValueError."""
    with pytest.raises(ValueError, match="min_solidity must be in"):
        TextDetector(min_solidity=min_solidity)


@pytest.mark.parametrize("min_detections", [0])
def test_init_invalid_min_detections(min_detections: int) -> None:
    """min_detections < 1 must raise ValueError."""
    with pytest.raises(ValueError, match="min_detections must be >= 1"):
        TextDetector(min_detections=min_detections)


@pytest.mark.parametrize("threshold_count", [0])
def test_init_invalid_threshold_count(threshold_count: int) -> None:
    """threshold_count < 1 must raise ValueError."""
    with pytest.raises(ValueError, match="threshold_count must be >= 1"):
        TextDetector(threshold_count=threshold_count)


# -----------------------------------------------------------------------------
# Detection Behaviour Tests
# -----------------------------------------------------------------------------

def test_detect_returns_tuple(detector: TextDetector, blank_frame: np.ndarray) -> None:
    """detect() must return a tuple of (bool, float)."""
    result = detector.detect(blank_frame)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert isinstance(result[1], float)


def test_detect_blank_frame(detector: TextDetector, blank_frame: np.ndarray) -> None:
    """On a blank (black) frame, detect should return (False, low confidence)."""
    present, conf = detector.detect(blank_frame)
    assert present is False
    # With default params, black blank yields zero regions -> confidence 0.0
    assert conf == 0.0


def test_detect_text_frame(detector: TextDetector, text_frame: np.ndarray) -> None:
    """On a synthetic text frame, detect should return (True, confidence > 0.2)."""
    present, conf = detector.detect(text_frame)
    assert present is True
    assert conf > 0.2  # should be at least 0.3 with default threshold_count=10 and region count ~4-5


def test_detect_corrupt_2d_frame(detector: TextDetector, corrupt_frame_2d: np.ndarray) -> None:
    """On a 2D frame (missing channel), detect must return (False, 0.0) without raising."""
    present, conf = detector.detect(corrupt_frame_2d)
    assert present is False
    assert conf == 0.0


def test_detect_corrupt_wrong_dtype(detector: TextDetector, corrupt_frame_wrong_dtype: np.ndarray) -> None:
    """On a float32 frame, detect must return (False, 0.0) without raising."""
    present, conf = detector.detect(corrupt_frame_wrong_dtype)
    assert present is False
    assert conf == 0.0


def test_detect_sensitivity_zero(detector_at_zero: TextDetector, text_frame: np.ndarray) -> None:
    """With sensitivity=0.0 (most conservative), detection should still be possible."""
    present, conf = detector_at_zero.detect(text_frame)
    # Should still detect something, though maybe lower confidence
    assert present is True
    assert conf > 0.0


def test_detect_sensitivity_one(detector_at_one: TextDetector, blank_frame: np.ndarray) -> None:
    """With sensitivity=1.0 (most aggressive), blank frame may still produce false positives? Accept but no crash."""
    # Just ensure no exception and returns tuple
    result = detector_at_one.detect(blank_frame)
    assert isinstance(result, tuple)


# -----------------------------------------------------------------------------
# Edge-case fixture helpers
# -----------------------------------------------------------------------------

@pytest.fixture
def detector_at_zero() -> TextDetector:
    """Detector with sensitivity=0.0."""
    return TextDetector(sensitivity=0.0)


@pytest.fixture
def detector_at_one() -> TextDetector:
    """Detector with sensitivity=1.0."""
    return TextDetector(sensitivity=1.0)


# -----------------------------------------------------------------------------
# Performance Test (optional, marked slow)
# -----------------------------------------------------------------------------

@pytest.mark.slow
def test_performance(detector: TextDetector, text_frame: np.ndarray) -> None:
    """
    Measure average detection time over 100 calls.
    Must be below 100ms per call on Pi 4B (here we just test on any platform with a reasonable upper bound).
    """
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        detector.detect(text_frame)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)  # ms

    avg_time = sum(times) / len(times)
    # On development machine, should be < 100ms; on Pi we expect ~20ms.
    assert avg_time < 100.0, f"Average detection time {avg_time:.2f} ms exceeds 100ms"


# -----------------------------------------------------------------------------
# Optional: Test with real receipt image if available
# -----------------------------------------------------------------------------

@pytest.fixture
def receipt_image_path() -> str:
    """Return path to a sample receipt image if exists, else empty string."""
    import os
    path = "tests/data/receipt_sample.jpg"
    return path if os.path.exists(path) else ""


def test_with_real_receipt(detector: TextDetector, receipt_image_path: str) -> None:
    """
    If a real receipt image is available, test detection on it.
    This test is skipped if the file does not exist.
    """
    if not receipt_image_path:
        pytest.skip("Real receipt image not available")
    img = cv2.imread(receipt_image_path)
    if img is None:
        pytest.skip("Could not read receipt image")
    # Resize to 320x240 (as used by VisionManager)
    small = cv2.resize(img, (320, 240), interpolation=cv2.INTER_LINEAR)
    present, conf = detector.detect(small)
    assert present is True
    assert conf > 0.2