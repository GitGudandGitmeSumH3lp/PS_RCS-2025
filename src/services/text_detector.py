# src/services/text_detector.py
"""
TextDetector module – lightweight receipt presence detector using brightness
isolation and edge‑density analysis.
"""

import cv2
import logging
import numpy as np
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class TextDetector:
    """
    Lightweight receipt presence detector for live camera frames.

    Uses brightness‑contour isolation followed by a fast edge‑density check
    to determine whether a receipt‑like bright rectangular region with
    sufficient text texture is visible. Designed to run on 320×240 BGR frames
    at ~1 fps on Pi 4B.

    Attributes:
        sensitivity (float): Edge‑density threshold in [0.0, 1.0].
            Lower = more sensitive (more false positives).
            Higher = stricter (may miss faint receipts).
        _canny_lo (int): Lower threshold for Canny edge detector.
        _canny_hi (int): Upper threshold for Canny edge detector.
        _min_receipt_area_ratio (float): Minimum fraction of frame area
            a candidate contour must occupy.
    """

    def __init__(self, sensitivity: float = 0.08) -> None:
        """
        Initialize the TextDetector.

        Args:
            sensitivity: Edge‑density threshold (0.0–1.0).
                Controls how dense the Canny edges must be within
                the isolated region to trigger detection.

        Raises:
            ValueError: If sensitivity not in [0.0, 1.0].
        """
        if not (0.0 <= sensitivity <= 1.0):
            raise ValueError(f"sensitivity must be in [0.0, 1.0], got {sensitivity}")

        self.sensitivity = sensitivity

        # Pre‑compute Canny thresholds based on sensitivity.
        # As sensitivity increases, thresholds decrease (more edges detected).
        self._canny_lo = max(1, int(50 * (1 - sensitivity)))
        self._canny_hi = max(1, int(150 * (1 - sensitivity)))

        self._min_receipt_area_ratio = 0.05

    def detect(
        self,
        bgr_frame: np.ndarray
    ) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
        """
        Detect whether a receipt is present in the given BGR frame.

        Args:
            bgr_frame: BGR image as a numpy uint8 array, shape (H, W, 3).
                Caller is responsible for downscaling to ≤320×240.

        Returns:
            Tuple of:
                - detected (bool): True if a receipt‑like region was found.
                - bbox (Optional[Tuple[int, int, int, int]]): Bounding box
                  (x, y, w, h) of the isolated region in the INPUT frame's
                  coordinate space, or None if no region was isolated.

        Raises:
            ValueError: If bgr_frame is None, not a 3‑channel array, or empty.
        """
        # --- Input validation ---
        if bgr_frame is None:
            raise ValueError("bgr_frame must be a 3‑channel BGR numpy array")
        if bgr_frame.ndim != 3 or bgr_frame.shape[2] != 3:
            raise ValueError("bgr_frame must be a 3‑channel BGR numpy array")
        if bgr_frame.size == 0:
            raise ValueError("bgr_frame cannot be empty")

        try:
            # --- Stage 1: Brightness‑contour isolation ---
            hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)
            v = hsv[:, :, 2]

            # Threshold at 200 (bright regions)
            _, bright_mask = cv2.threshold(v, 200, 255, cv2.THRESH_BINARY)

            # Morphological close to fill gaps
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
            closed = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)

            # Find contours
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return False, None

            # Filter by area
            frame_h, frame_w = bgr_frame.shape[:2]
            min_area = frame_h * frame_w * self._min_receipt_area_ratio
            valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) >= min_area]
            if not valid_contours:
                return False, None

            # Take largest contour
            largest = max(valid_contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)

            # --- Stage 2: Edge density check ---
            # Crop region with 10‑pixel padding (clamped to frame)
            pad = 10
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(frame_w, x + w + pad)
            y2 = min(frame_h, y + h + pad)
            cropped = bgr_frame[y1:y2, x1:x2]

            # Minimum size sanity
            if cropped.shape[0] < 100 or cropped.shape[1] < 100:
                return False, (x, y, w, h)   # bbox returned but not detected

            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, self._canny_lo, self._canny_hi)

            edge_density = np.count_nonzero(edges) / edges.size
            detected = edge_density >= self.sensitivity

            return detected, (x, y, w, h)

        except cv2.error as e:
            logger.warning(f"OpenCV error during detection: {e}")
            return False, None