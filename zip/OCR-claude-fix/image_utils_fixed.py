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


def _detect_rotation_angle(gray: np.ndarray) -> float:
    """Detect rotation angle using Hough line transform.
    
    Args:
        gray: Grayscale image
        
    Returns:
        Rotation angle in degrees (negative = counterclockwise)
    """
    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Detect lines
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
    
    if lines is None:
        return 0.0
    
    # Calculate angles
    angles = []
    for rho, theta in lines[:, 0]:
        angle = np.degrees(theta) - 90
        # Normalize to [-45, 45]
        if angle < -45:
            angle += 90
        elif angle > 45:
            angle -= 90
        angles.append(angle)
    
    # Return median angle
    if angles:
        return float(np.median(angles))
    return 0.0


def _rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate image by given angle.
    
    Args:
        image: Input image
        angle: Rotation angle in degrees
        
    Returns:
        Rotated image
    """
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    
    # Get rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Calculate new dimensions
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    
    # Adjust rotation matrix
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    
    # Rotate
    rotated = cv2.warpAffine(image, M, (new_w, new_h), 
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(255, 255, 255))
    
    return rotated


def align_receipt(image: np.ndarray, use_simple_rotation: bool = True) -> Tuple[np.ndarray, bool]:
    """Detects receipt paper and warps it to a front-facing view.
    
    NEW: Falls back to simple rotation if contour detection fails.
    
    Args:
        image: Original BGR frame (high res)
        use_simple_rotation: If True, uses rotation-based alignment as fallback
    
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
        # Fallback to rotation-based alignment
        if use_simple_rotation:
            return _rotation_based_alignment(image)
        return image, False
    
    # Sort by area descending
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    frame_area = small.shape[0] * small.shape[1]
    
    # 4. Find quadrilateral contour (RELAXED threshold)
    for contour in contours[:10]:  # Check top 10 (was 5)
        area = cv2.contourArea(contour)
        if area < 0.05 * frame_area:  # RELAXED: 5% (was 10%)
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
    
    # Fallback to rotation-based alignment
    if use_simple_rotation:
        return _rotation_based_alignment(image)
    
    return image, False


def _rotation_based_alignment(image: np.ndarray) -> Tuple[np.ndarray, bool]:
    """Align receipt using rotation detection (fallback method).
    
    This is more robust for images with complex backgrounds where
    contour detection fails.
    
    Args:
        image: Original BGR frame
        
    Returns:
        (rotated_image, success_flag)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Detect rotation angle
    angle = _detect_rotation_angle(gray)
    
    # Only rotate if angle is significant (> 1 degree)
    if abs(angle) > 1.0:
        rotated = _rotate_image(image, angle)
        return rotated, True
    
    # No significant rotation detected
    return image, False
