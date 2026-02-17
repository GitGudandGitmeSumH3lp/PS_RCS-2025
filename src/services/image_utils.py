# src/services/image_utils.py

"""Image utilities for receipt alignment and deskewing."""
import cv2
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Default HSV ranges for orange footer (Flash Express)
ORANGE_LOWER = (10, 100, 100)   # Hue ~10–25, moderate saturation/value
ORANGE_UPPER = (25, 255, 255)

# Dark sidebar range (for additional stability)
DARK_LOWER = (0, 0, 0)
DARK_UPPER = (180, 50, 80)


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order points in consistent top-left, top-right, bottom-right, bottom-left order.

    Args:
        pts: Array of 4 (x, y) coordinates

    Returns:
        Ordered array of 4 points
    """
    rect = np.zeros((4, 2), dtype="float32")

    # Sum and difference to identify corners
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)

    rect[0] = pts[np.argmin(s)]      # Top-left (smallest sum)
    rect[2] = pts[np.argmax(s)]      # Bottom-right (largest sum)
    rect[1] = pts[np.argmin(diff)]   # Top-right (smallest diff)
    rect[3] = pts[np.argmax(diff)]   # Bottom-left (largest diff)

    return rect


def _four_point_transform(image: np.ndarray, pts: np.ndarray, dst_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
    """Apply perspective warp using the ordered points.

    Args:
        image: Input image
        pts: Ordered 4-point array
        dst_size: Optional (width, height) of output. If None, computed from points.

    Returns:
        Warped image
    """
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect

    if dst_size is None:
        # Compute width of new image
        width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        max_width = max(int(width_a), int(width_b))

        # Compute height of new image
        height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        max_height = max(int(height_a), int(height_b))
    else:
        max_width, max_height = dst_size

    # Destination points
    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")

    # Compute perspective transform matrix and apply
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (max_width, max_height))

    return warped


def align_receipt_color(image: np.ndarray,
                        orange_lower: Tuple[int, int, int] = ORANGE_LOWER,
                        orange_upper: Tuple[int, int, int] = ORANGE_UPPER,
                        use_dark_sidebar: bool = True,
                        debug: bool = False) -> Tuple[np.ndarray, bool]:
    """Detect receipt using orange footer and optionally dark sidebars, then warp to front view.

    Args:
        image: Original BGR frame
        orange_lower: HSV lower bound for orange
        orange_upper: HSV upper bound for orange
        use_dark_sidebar: Whether to include dark sidebars in mask
        debug: If True, save intermediate debug images

    Returns:
        (aligned_image, success_flag). If success False, returns original image.
    """
    orig = image.copy()
    h, w = image.shape[:2]

    # 1. Convert to HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # 2. Create orange mask
    orange_mask = cv2.inRange(hsv, orange_lower, orange_upper)

    # 3. Optionally combine with dark sidebar mask
    if use_dark_sidebar:
        dark_mask = cv2.inRange(hsv, DARK_LOWER, DARK_UPPER)
        combined_mask = cv2.bitwise_or(orange_mask, dark_mask)
    else:
        combined_mask = orange_mask

    # 4. Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    cleaned = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

    # 5. Find largest contour
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        if debug:
            logger.debug("No contours found in color mask.")
        return image, False

    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < 0.05 * w * h:  # must be at least 5% of image
        if debug:
            logger.debug(f"Largest contour area too small: {area} < {0.05*w*h}")
        return image, False

    # 6. Approximate to quadrilateral
    peri = cv2.arcLength(largest, True)
    epsilon = 0.02 * peri
    approx = cv2.approxPolyDP(largest, epsilon, True)

    if len(approx) != 4:
        if debug:
            logger.debug(f"Contour approximated to {len(approx)} points, need 4.")
        return image, False

    # 7. Reshape and order points
    pts = approx.reshape(4, 2).astype("float32")

    # 8. Compute destination size (use average width/height or fixed aspect)
    # For Flash Express, receipt aspect is roughly 400:500 (0.8) but we'll compute dynamically.
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    avg_width = int((width_top + width_bottom) / 2)
    height_left = np.linalg.norm(tl - bl)
    height_right = np.linalg.norm(tr - br)
    avg_height = int((height_left + height_right) / 2)

    # 9. Perspective transform
    warped = _four_point_transform(image, pts, dst_size=(avg_width, avg_height))

    if debug:
        # Save intermediate images for tuning
        cv2.imwrite("debug_color_mask.jpg", cleaned)
        # Draw contour on original
        contour_draw = image.copy()
        cv2.drawContours(contour_draw, [largest], -1, (0, 255, 0), 2)
        cv2.imwrite("debug_contour.jpg", contour_draw)
        cv2.imwrite("debug_warped.jpg", warped)

    return warped, True


def align_receipt_edge(image: np.ndarray, debug: bool = False) -> Tuple[np.ndarray, bool]:
    """Legacy edge‑based alignment (original fallback)."""
    orig_h, orig_w = image.shape[:2]

    # Resize for detection speed (width=640)
    scale = 640.0 / orig_w
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edged = cv2.Canny(blurred, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edged, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image, False

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    frame_area = small.shape[0] * small.shape[1]

    for contour in contours[:5]:
        area = cv2.contourArea(contour)
        if area < 0.1 * frame_area:
            continue

        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype("float32")
            pts = pts / scale
            warped = _four_point_transform(image, pts)
            return warped, True

    return image, False


def align_receipt(image: np.ndarray, debug: bool = False) -> Tuple[np.ndarray, bool]:
    """Main alignment function: tries color‑based method first, falls back to edge‑based.

    Args:
        image: Original BGR frame
        debug: If True, enable debug image saving

    Returns:
        (aligned_image, success_flag). If both fail, returns original and False.
    """
    # Try color method first
    warped, success = align_receipt_color(image, debug=debug)
    if success:
        if debug:
            logger.info("Color-based alignment succeeded.")
        return warped, True

    # Fallback to edge-based
    if debug:
        logger.info("Color-based failed, falling back to edge-based.")
    warped, success = align_receipt_edge(image, debug=debug)
    if success and debug:
        logger.info("Edge-based alignment succeeded.")
    return warped, success