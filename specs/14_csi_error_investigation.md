# INVESTIGATION PLAN: CSI Camera "Lores Stream Must Be YUV" Error
**Date:** 2026-02-08
**Status:** In Progress
**Target:** `docs/specs/csi_error_investigation.md`

## 1. ERROR PATTERN DOCUMENTATION

### The Symptom
The `CsiCameraProvider` fails to initialize `Picamera2` with the current configuration payload.

*   **Error Message:** `RuntimeError: lores stream must be YUV`
*   **Trigger:** calling `self.picam2.configure(config)` inside `start()`.
*   **Current Payload:**
    ```python
    main={"size": (width, height), "format": "RGB888"},
    lores={"size": (width, height), "format": "RGB888"} # <-- THE CULPRIT
    ```

### The Root Cause
The `create_preview_configuration()` helper in `picamera2` enforces strict hardware pipeline constraints.
1.  **Hardware Path:** The `lores` (low resolution) stream typically comes from the ISP's "Low Resolution" output node.
2.  **Constraint:** On the VideoCore VI / Pi 4 ISP, this specific hardware node is often hardwired or driver-constrained to output YUV formats (typically `YUV420`) to feed video encoders efficiently. It usually cannot perform RGB conversion in that specific pipeline stage.
3.  **Conflict:** We requested `RGB888`, but the driver rejects it for the `lores` pipe.

## 2. PICAMERA2 CONFIGURATION MAPPING

We are using `create_preview_configuration`, which presumes a specific use case (High Res Viewfinder + Low Res Video Encode).

| Helper Method | Primary Use Case | 'Main' Stream Constraints | 'Lores' Stream Constraints |
| :--- | :--- | :--- | :--- |
| `create_preview_configuration` | UI Viewfinder + Video | Flexible (RGB/YUV/Bayer) | **Strictly YUV** (usually) |
| `create_video_configuration` | Video Recording | YUV | N/A (Single stream usually) |
| `create_still_configuration` | Photography | Flexible | N/A |
| `create_buffer_configuration` | Custom | Flexible | Flexible (Manual definition) |

**Current Mismatch:** We are trying to force an RGB workflow (for OpenCV compatibility) into a pipeline helper optimized for YUV video encoding.

## 3. YUV FORMAT REQUIREMENTS & IMPLICATIONS

If we adhere to the `picamera2` constraint, we must switch the `lores` format to `YUV420`.

### Data Structure (YUV420)
*   **Format:** Planar (Y plane full size, U/V planes quarter size).
*   **Numpy Shape:** When `capture_array("lores")` is called on YUV420, it returns a slightly complex array or list of planes depending on configuration, OR a monolithic buffer where height is 1.5x usage.
*   **OpenCV Compatibility:**
    *   OpenCV expects BGR.
    *   Conversion: `cv2.cvtColor(yuv_frame, cv2.COLOR_YUV2BGR_I420)` is required.
*   **Performance:**
    *   **Pro:** The ISP handles the resize and YUV generation efficiently.
    *   **Con:** The CPU must handle the YUV -> BGR conversion for every frame. On a Pi 4, this is acceptable for 640x480 but non-negligible.

## 4. PROPOSED SOLUTION APPROACHES

### Approach A: Compliance (Switch to YUV420)
Modify `csi_provider.py` to accept YUV from hardware and convert in software.

*   **Config:** `lores={"size": (width, height), "format": "YUV420"}`
*   **Read Logic:**
    ```python
    frame_yuv = self.picam2.capture_array("lores")
    frame_bgr = cv2.cvtColor(frame_yuv, cv2.COLOR_YUV2BGR_I420)
    ```
*   **Pros:** Uses standard `picamera2` helpers; efficient hardware usage; keeps dual-stream capability (High Res capture remains available on `main`).
*   **Cons:** CPU overhead for color conversion (~5-10ms per frame).

### Approach B: Single Stream (Main Only)
Abandon the `lores` stream entirely for the standard loop. Use the `main` stream for the 640x480 feed in RGB.

*   **Config:** `main={"size": (width, height), "format": "RGB888"}` (No `lores`).
*   **Read Logic:** `capture_array("main")` (returns RGB directly).
*   **Pros:** Simplest code; valid RGB output from ISP; zero CPU conversion.
*   **Cons:** **Major feature loss.** We lose the ability to capture High-Res stills (1920x1080) simultaneously without stopping and reconfiguring the camera (which causes stream interruption).

### Approach C: Custom Configuration (Advanced)
Manually define the stream arrays to force RGB if hardware allows it on specific nodes, or use a different resizing node.

*   **Config:** `self.picam2.configure(self.picam2.create_buffer_configuration(...))`
*   **Pros:** Ultimate flexibility.
*   **Cons:** High complexity; high risk of "Invalid Argument" errors from driver; brittle across Pi OS updates.

## 5. DECISION MATRIX

| Criteria | Approach A (YUV Convert) | Approach B (Single Stream) | Approach C (Custom) |
| :--- | :--- | :--- | :--- |
| **Fix Probability** | **High** (Standard path) | **High** (Standard path) | **Low** (Trial & error) |
| **Code Complexity** | Low (One cv2 call) | Low (Config change) | High |
| **CPU Usage** | Medium (Conversion) | **Low** (Direct RGB) | Low |
| **Feature Parity** | **Full** (Dual streams) | Partial (No concurrent Hi-Res) | Full |
| **Stability** | High | High | Low |

### Recommendation: Approach A (Compliance)

We must maintain the **High-Res Capture** feature defined in `_STATE.md`. Approach B breaks this (or complicates it significantly). Approach A incurs a small CPU penalty but guarantees stability and adheres to the `picamera2` API contract.

**Investigation Output:** Proceed with implementing **Approach A**.

1.  **Modify `csi_provider.py`:** Change `lores` format to `YUV420`.
2.  **Update `read()`:** Detect YUV format and apply `cv2.COLOR_YUV2BGR_I420`.
3.  **Validate:** Ensure `capture_array` returns the expected shape for `cvtColor`.