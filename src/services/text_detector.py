# src/services/text_detector.py
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: text_detector.py
Description: MSER‑based text presence detector for auto‑capture gating.
"""

import logging
from typing import Optional, Tuple, List

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class TextDetector:
    """
    Lightweight text presence detector using MSER + geometric filtering.
    Thread‑safe and stateless during detection.
    """

    def __init__(
        self,
        sensitivity: float = 0.08,
        min_area: int = 50,
        aspect_ratio_min: float = 0.2,
        aspect_ratio_max: float = 5.0,
        min_solidity: float = 0.2,
        min_detections: int = 5,
        threshold_count: int = 10,
    ) -> None:
        """
        Initialise the MSER‑based text detector.

        Maps `sensitivity` (0.0–1.0) to MSER `_delta` via:
            delta = max(2, int(20 - sensitivity * 18))

        Args:
            sensitivity: Detection aggressiveness in [0.0, 1.0].
                Default 0.08 → delta=18 (conservative).
            min_area: Minimum pixel area for a region to be considered.
            aspect_ratio_min: Lower bound of bounding‑box width/height ratio.
            aspect_ratio_max: Upper bound of bounding‑box width/height ratio.
            min_solidity: Minimum ratio of region area to convex hull area.
            min_detections: Minimum qualifying regions to declare text present.
            threshold_count: Denominator for confidence normalisation.

        Raises:
            ValueError: If any parameter is outside its valid range.
        """
        # Validate sensitivity
        if not (0.0 <= sensitivity <= 1.0):
            raise ValueError(f"sensitivity must be in [0.0, 1.0], got {sensitivity}")

        # Validate min_area
        if min_area < 1:
            raise ValueError(f"min_area must be >= 1, got {min_area}")

        # Validate aspect ratio bounds
        if aspect_ratio_min >= aspect_ratio_max:
            raise ValueError(
                f"aspect_ratio_min ({aspect_ratio_min}) must be < aspect_ratio_max ({aspect_ratio_max})"
            )

        # Validate min_solidity
        if not (0.0 <= min_solidity <= 1.0):
            raise ValueError(f"min_solidity must be in [0.0, 1.0], got {min_solidity}")

        # Validate min_detections and threshold_count
        if min_detections < 1:
            raise ValueError(f"min_detections must be >= 1, got {min_detections}")
        if threshold_count < 1:
            raise ValueError(f"threshold_count must be >= 1, got {threshold_count}")

        # Compute MSER delta from sensitivity
        delta = max(2, int(20 - sensitivity * 18))
        self._mser = cv2.MSER_create(_delta=delta)

        # Store parameters
        self._min_area = min_area
        self._aspect_ratio_min = aspect_ratio_min
        self._aspect_ratio_max = aspect_ratio_max
        self._min_solidity = min_solidity
        self._min_detections = min_detections
        self._threshold_count = threshold_count

    def detect(self, frame: np.ndarray) -> Tuple[bool, float]:
        """
        Detect text presence in a single BGR frame.

        Args:
            frame: BGR uint8 array, expected shape (H, W, 3). Typically 320×240.

        Returns:
            A tuple (text_present, confidence) where:
                - text_present: True if qualifying region count >= min_detections.
                - confidence: Normalised score in [0.0, 1.0] = min(1.0, region_count / threshold_count).

        Notes:
            All exceptions are caught internally. On error logs and returns (False, 0.0).
        """
        try:
            # 1. Input validation
            if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.dtype != np.uint8:
                logger.error("TextDetector.detect: invalid frame format")
                return (False, 0.0)

            # 2. Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 3. Run MSER
            regions, bboxes = self._mser.detectRegions(gray)

            # 4. Apply geometric filters
            region_count = self._filter_regions(regions, bboxes)

            # 5. Compute outputs
            confidence = min(1.0, region_count / self._threshold_count)
            return (region_count >= self._min_detections, confidence)

        except cv2.error as e:
            logger.error(f"TextDetector cv2 error: {e}")
            return (False, 0.0)
        except Exception as e:
            logger.error(f"TextDetector unexpected error: {e}")
            return (False, 0.0)

    def _filter_regions(self, regions: List, bboxes: List) -> int:
        """
        Count bounding boxes that pass geometric filters.

        Args:
            regions: List of point arrays from MSER.detectRegions.
            bboxes: Parallel list of (x, y, w, h) tuples.

        Returns:
            Number of regions passing all filters.
        """
        count = 0
        for region_pts, (x, y, w, h) in zip(regions, bboxes):
            # Skip degenerate boxes
            if h == 0:
                continue

            # Minimum area filter
            if w * h < self._min_area:
                continue

            # Aspect ratio filter
            aspect = w / h
            if not (self._aspect_ratio_min <= aspect <= self._aspect_ratio_max):
                continue

            # Solidity filter (approximated as points count / bounding box area)
            solidity = len(region_pts) / (w * h)
            if solidity < self._min_solidity:
                continue

            count += 1
        return count