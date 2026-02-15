"""Image utilities for receipt alignment and deskewing."""
import cv2
import numpy as np
from typing import Tuple, Optional


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


def _four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply perspective warp using the ordered points.
    
    Args:
        image: Input image
        pts: Ordered 4-point array
    
    Returns:
        Warped image
    """
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    
    # Compute width of new image
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))
    
    # Compute height of new image
    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))
    
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


def align_receipt(image: np.ndarray) -> Tuple[np.ndarray, bool]:
    """Detects receipt paper and warps it to a front-facing view.
    
    Args:
        image: Original BGR frame (high res)
    
    Returns:
        (aligned_image, success_flag)
        If success is False, returns original image.
    """
    orig_h, orig_w = image.shape[:2]
    
    # 1. Resize for detection speed (width=640)
    scale = 640.0 / orig_w
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    
    # 2. Preprocessing
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edged = cv2.Canny(blurred, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edged, kernel, iterations=2)
    
    # 3. Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image, False
    
    # Sort by area descending
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    frame_area = small.shape[0] * small.shape[1]
    
    # 4. Find quadrilateral contour
    for contour in contours[:5]:  # Check top 5 largest
        area = cv2.contourArea(contour)
        if area < 0.1 * frame_area:  # Must be >10% of frame
            continue
        
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        
        if len(approx) == 4:
            # Found quadrilateral - scale back to original size
            pts = approx.reshape(4, 2).astype("float32")
            pts = pts / scale
            
            # Warp and return
            warped = _four_point_transform(image, pts)
            return warped, True
    
    return image, False