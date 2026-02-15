**System Online.**
**Agent:** ANALYST (V4.0)
**Account:** B (Gemini 1.5 Pro)
**Status:** Designing Deskew Module.

I have analyzed the provided receipt images and current codebase. The current "Fixed Zone" approach is highly efficient but brittle; it assumes the user is a robot. Real-world users hold receipts at angles, or place them on messy backgrounds (like the patterned bedsheets in your sample images).

The challenge here is high: **Messy Backgrounds**. Standard edge detection often fails when the background has high-contrast patterns (stripes, wires).

Here is the design for a robust **Perspective Alignment Module** that prioritizes the "Orange Footer" and "Header Block" as anchors, which are unique to Flash Express receipts and easier to isolate than white paper on a white/patterned background.

---

# FEATURE SPEC: Receipt Deskewing & Alignment
**Date:** 2026-02-15
**Target:** Raspberry Pi 4B (CPU Optimization)
**Status:** Proposed

## 1. THE VISION
*   **User Story:** As a user, I want to hold the receipt naturally (slightly tilted or rotated) and still get 100% accurate OCR, so I don't have to fiddle with perfect alignment.
*   **Success Metrics:**
    *   **Detection Rate:** >80% of frames yield a valid quadrilateral.
    *   **Accuracy:** Zonal OCR extraction improves from <50% to >90% on skewed images.
    *   **Latency:** Alignment calculation < 100ms; Total transformation < 300ms.

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed. Uses `opencv-python` (already installed) and `numpy`. No GPU required.
*   **Risk Level:** **Medium**. Background noise (patterned sheets) is the main enemy. The algorithm must be aggressive in filtering small contours.
*   **Hardware Impact:** Perspective Warping (`cv2.warpPerspective`) is computationally expensive on high-res images. **Mitigation:** We will detect on a low-res copy (width=600px) and map coordinates to the high-res frame.

## 3. ALGORITHM: "The Anchor Hunter"
Because the background is noisy (bedsheets/wires), seeking the "white paper" edge is unreliable. Instead, we will use the **Flash Express Schema**:
1.  **Orange Footer:** Large solid block at the bottom.
2.  **Header:** Black horizontal lines / Orange Logo at the top.
3.  **Shape:** The paper is rectangular.

### The Pipeline
1.  **Downscale:** Resize to `width=640` (preserve aspect) for speed.
2.  **Preprocessing:**
    *   Convert to Grayscale.
    *   **Gaussian Blur** (kernel `7x7`) to remove text noise/bedsheet textures.
    *   **Canny Edge Detection** (thresholds `50, 150`).
    *   **Dilation** (kernel `3x3`, 2 iterations) to close gaps in the paper edge.
3.  **Contour Extraction:**
    *   Find contours.
    *   Sort by Area (Descending).
    *   Filter: Area must be > 10% of frame area.
4.  **Quadrilateral Fitting:**
    *   Loop through top 5 contours.
    *   Apply `cv2.approxPolyDP` (epsilon `0.02 * perimeter`).
    *   If result has **4 points**, we found our candidate.
5.  **Perspective Warp:**
    *   Order points (Top-Left, Top-Right, Bottom-Right, Bottom-Left).
    *   Scale points back up to original resolution.
    *   Compute transform matrix (`cv2.getPerspectiveTransform`).
    *   Apply warp (`cv2.warpPerspective`).

## 4. INTERFACE SKETCHES (For Architect/Implementer)

**Module:** `src/services/image_utils.py` (New Helper Module)

```python
def align_receipt(image: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    Detects receipt paper and warps it to a front-facing view.
    
    Args:
        image: Original BGR frame (high res)
    
    Returns:
        (aligned_image, success_flag)
        If success is False, returns original image.
    """
    # 1. Resize for detection speed
    scale = 640 / image.shape[1]
    small = cv2.resize(image, None, fx=scale, fy=scale)
    
    # 2. Find Document Contour
    contour = _find_document_contour(small)
    if contour is None:
        return image, False
        
    # 3. Scale contour up to original size
    contour = contour / scale
    
    # 4. Warp
    warped = _four_point_transform(image, contour)
    return warped, True
```

**Integration into `FlashExpressOCR`:**

```python
# src/services/ocr_processor.py

def process_frame(self, bgr_frame, scan_id=None):
    # ... setup ...
    
    # NEW STEP: Alignment
    # Only try alignment if we suspect the frame needs it 
    # (Optional: or just run it always if fast enough)
    aligned_frame, was_aligned = self._align_receipt_internal(bgr_frame)
    
    # Pass aligned frame to Zonal OCR
    zone_results = self._process_zones(aligned_frame)
    
    # ... rest of logic ...
```

## 5. ATOMIC TASKS (The Roadmap)

*   [ ] Create `src/services/image_utils.py` (Keep main processor clean).
*   [ ] Implement `_order_points` (Standard computer vision utility).
*   [ ] Implement `_four_point_transform`.
*   [ ] Implement `align_receipt` using the Canny/ApproxPolyDP method.
*   [ ] Update `FlashExpressOCR.process_frame` to utilize alignment.
*   [ ] Add a "Debug Mode" flag to save the pre-warp and post-warp images for tuning.

## 6. OPEN QUESTIONS / FALLBACKS
*   **What if the background is white?** (White table).
    *   *Fallback strategy:* If `approxPolyDP` fails to find 4 points, we assume the user has aligned it manually and return the original frame.
*   **What if the top is cut off?**
    *   The algorithm requires 4 points. If 2 are off-screen, it fails.
    *   *Mitigation:* The user must frame the receipt fully. The UI should prompt "Ensure full receipt is visible".

---
