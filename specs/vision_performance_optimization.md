# FEATURE SPEC: Vision Performance Optimization (Dual-Tier)
**Date:** 2025-05-15
**Status:** Feasible

## 1. THE VISION
*   **User Story:** As a Remote Operator, I want a smooth, low-bandwidth video feed for navigation, while preserving high-resolution imagery for backend OCR analysis.
*   **Success Metrics:**
    *   **Stream Bandwidth:** Reduced by ~70% (320px + Q40 vs 640px + Q80).
    *   **Browser FPS:** Stable 15 FPS.
    *   **OCR Accuracy:** Unchanged (Must use 640x480 source).
    *   **Lock Contention:** Reduced blocking between capture thread and stream generator.

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed. Uses existing `cv2` and threading primitives. No hardware changes required.
*   **New Libraries Needed:** None.
*   **Risk Level:** Low. (Primary risk is introducing thread race conditions if locking isn't handled correctly).

## 3. ATOMIC TASKS (The Roadmap)
*   [ ] Refactor `src/services/vision_manager.py`:
    *   Hardcode/Enforce capture resolution to **640x480**.
    *   Update `generate_mjpeg` to resize frames to **320x240** before encoding.
    *   Update `generate_mjpeg` compression quality to **40**.
    *   Update `generate_mjpeg` loop timing to **15 FPS** (approx 0.066s sleep).
*   [ ] Verify `src/api/server.py` usage:
    *   Ensure `start_capture()` calls remain compatible.
    *   Ensure `trigger_scan()` still retrieves the full-resolution frame.

## 4. INTERFACE SKETCHES (For Architect)

**Module:** `src/services/vision_manager.py`

*   `start_capture(width=640, height=480, fps=30)`
    *   *Refinement:* While arguments exist for compatibility, the internal capture logic should prioritize the "Master Resolution" (640x480) to ensure OCR always has data.

*   `get_frame() -> np.ndarray` (High-Res Access)
    *   *Logic:* Returns copy of the raw 640x480 frame.
    *   *Usage:* Used by OCR Service.

*   `generate_mjpeg(quality=40) -> Generator` (Low-Res Stream)
    *   *Logic:*
        1.  Acquire latest frame (640x480).
        2.  `cv2.resize` to (320, 240).
        3.  `cv2.imencode` with JPEG quality 40.
        4.  `time.sleep(0.066)` to throttle to 15 FPS.
    *   *Optimization:* Minimize time inside `frame_lock`. Copy frame reference, release lock, *then* resize/encode.

## 5. INTEGRATION POINTS
*   **Touches:** `src/api/server.py`
    *   Route `/api/vision/stream`: Consumes the throttled MJPEG generator.
    *   Route `/api/vision/scan`: Must still receive the high-quality 640px frame via `get_frame()`.
*   **Data Flow:**
    *   Camera (640x480 @ 30fps) -> `_capture_loop` -> `current_frame`
    *   `current_frame` -> [OCR Path] -> Full Res Processing
    *   `current_frame` -> [Stream Path] -> Downscale -> Compress -> HTTP Stream

## 6. OPEN QUESTIONS
*   Does `cv2.resize` add too much CPU overhead on the Pi Zero if multiple clients connect? (Mitigation: Single client limit is already assumed).
*   Should we expose the stream resolution as a config variable, or hardcode for now? (Decision: Hardcode for V1 optimization).