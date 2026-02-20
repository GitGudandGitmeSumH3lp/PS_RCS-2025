# CONTRACT: Auto Text Detection & High-Resolution Capture
**Version:** 1.0
**Last Updated:** 2026-02-21
**Status:** Draft
**Feature Spec Reference:** Orchestration Report 2026-02-16 — "Auto Text Detection & Capture"

---

## 1. PURPOSE

This contract governs two new modules and extensions to existing modules that together deliver
autonomous receipt detection and high-resolution capture on the Raspberry Pi 4B camera pipeline.
`TextDetector` (`src/services/text_detector.py`) provides a lightweight, CPU-safe heuristic that
determines whether a Flash Express receipt is present in a given low-resolution frame. 
`VisionManager` gains three new public methods — `capture_highres`, `start_auto_detection`, and
`stop_auto_detection` — that consume the detector output and orchestrate the CSI main-stream
capture workflow. A new Flask endpoint `POST /api/vision/auto-detect` allows runtime
enable/disable of the background detection loop. All design decisions are constrained by the
Raspberry Pi 4B 4 GB profile and the hard limits codified in `system_constraints.md`.

---

## 2. PUBLIC INTERFACE

---

### Module A — `TextDetector` (`src/services/text_detector.py`)

---

#### Class: `TextDetector`

```python
class TextDetector:
    """Lightweight receipt presence detector for live camera frames.

    Uses brightness-contour isolation (reusing FlashExpressOCR._isolate_receipt
    logic) followed by a fast edge-density check to determine whether a
    receipt-like bright rectangular region with sufficient text texture is
    visible. Designed to run on 320×240 BGR frames at ~1 fps on Pi 4B.

    Attributes:
        sensitivity (float): Edge-density threshold in [0.0, 1.0].
            Lower = more sensitive (more false positives).
            Higher = stricter (may miss faint receipts).
            Default: 0.08 (empirically tuned).
        _min_receipt_area_ratio (float): Minimum fraction of frame area
            a candidate contour must occupy. Default: 0.05.
    """
```

---

#### Method: `__init__`

```python
def __init__(self, sensitivity: float = 0.08) -> None:
    """Initialize the TextDetector.

    Args:
        sensitivity: Edge-density threshold (0.0–1.0).
            Controls how dense the Canny edges must be within
            the isolated region to trigger detection.

    Raises:
        ValueError: If sensitivity not in [0.0, 1.0].
    """
```

**Behavior Specification:**
- **Input Validation:** Assert `0.0 <= sensitivity <= 1.0`; raise `ValueError` otherwise.
- **Processing Logic:** Store `sensitivity` as `self.sensitivity`. Pre-compute and cache the
  Canny lower/upper bounds derived from `sensitivity` so each `detect()` call is allocation-free.
- **Output Guarantee:** Object is ready for immediate `detect()` calls after `__init__`.
- **Side Effects:** None. No hardware access.

**Error Handling:**
- `sensitivity` outside `[0.0, 1.0]` → Raise `ValueError` with message
  `"sensitivity must be in [0.0, 1.0], got {sensitivity}"`

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

#### Method: `detect`

```python
def detect(
    self,
    bgr_frame: np.ndarray
) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
    """Detect whether a receipt is present in the given BGR frame.

    Runs a two-stage check:
    1. Brightness-contour isolation (identical algorithm to
       FlashExpressOCR._isolate_receipt) to find a bright rectangular region.
    2. Edge-density check within the isolated region:
       - Convert to grayscale.
       - Apply Canny edge detector.
       - Compute edge_density = (non-zero edge pixels) / (total pixels).
       - If edge_density >= self.sensitivity → receipt detected.

    The frame is expected to be pre-scaled to ≤320×240 by the caller
    (VisionManager._detection_loop). This method does NOT resize internally.

    Args:
        bgr_frame: BGR image as a numpy uint8 array, shape (H, W, 3).
            Caller is responsible for downscaling to ≤320×240.

    Returns:
        Tuple of:
            - detected (bool): True if a receipt-like region was found.
            - bbox (Optional[Tuple[int, int, int, int]]): Bounding box
              (x, y, w, h) of the isolated region in the INPUT frame's
              coordinate space, or None if no region was isolated.

    Raises:
        ValueError: If bgr_frame is None, not a 3-channel array, or empty.
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `bgr_frame` must not be `None`.
  - `bgr_frame.ndim` must equal 3 and `bgr_frame.shape[2]` must equal 3.
  - `bgr_frame.size` must be > 0.
  - Raise `ValueError` on any violation.
- **Processing Logic:**
  1. Convert to HSV; extract V channel.
  2. Threshold V at 200 → `bright_mask`.
  3. Morphological close with 20×20 rect kernel → `closed`.
  4. Find external contours. Filter by `area >= frame_area * 0.05`.
  5. If no valid contour: return `(False, None)`.
  6. Take largest valid contour → bounding rect `(x, y, w, h)`.
  7. Crop region (with 10-px padding clamped to frame bounds).
  8. If cropped region < 100×100 px: return `(False, None)`.
  9. Convert cropped region to grayscale.
  10. Apply `cv2.Canny(gray, 50, 150)`.
  11. Compute `edge_density = np.count_nonzero(edges) / edges.size`.
  12. `detected = edge_density >= self.sensitivity`.
  13. Return `(detected, (x, y, w, h))`.
- **Output Guarantee:** `bbox` coordinates are always in the input frame's coordinate space.
  When `detected=False` due to no contour, `bbox=None`. When `detected=False` due to low
  edge density, `bbox` still contains the isolated contour rect.
- **Side Effects:** None. No I/O. No state mutation.

**Error Handling:**
- `bgr_frame` is `None` or not a 3-channel uint8 ndarray →
  Raise `ValueError` with message `"bgr_frame must be a 3-channel BGR numpy array"`
- Any `cv2` internal error → caught; log warning; return `(False, None)`.

**Performance Requirements:**
- Time Complexity: O(H × W) — linear in pixel count.
- Space Complexity: O(H × W) — temporary mask and edges arrays.
- **Target latency on Pi 4B at 320×240:** < 15 ms per call.

---

### Module B — `VisionManager` Extensions (`src/services/vision_manager.py`)

Three new public methods are appended to the existing `VisionManager` class.
**Existing methods are IMMUTABLE** — no signatures may change.

---

#### Method: `capture_highres`

```python
def capture_highres(
    self,
    filename: Optional[str] = None
) -> Optional[str]:
    """Capture a high-resolution still and save to data/auto_captures/.

    Attempts to acquire a 1920×1080 frame from the CSI camera's main
    stream (RGB888) via provider.picam2.capture_array('main').
    Falls back to the latest low-res frame from get_frame() if the
    provider does not expose picam2 or if the main capture fails.

    The output directory data/auto_captures/ is created if absent.
    Applies auto-cleanup: if the directory contains more than
    _AUTO_CAPTURE_MAX_FILES files, the oldest files are deleted until
    the count is at or below the limit.

    Args:
        filename: Optional override for the output filename (no path).
            Must end in '.jpg'. If None, defaults to
            'auto_YYYYMMDD_HHMMSS.jpg' using UTC time.

    Returns:
        Absolute path of the saved file as a str, or None if no frame
        was available or saving failed.

    Raises:
        ValueError: If filename is provided but does not end in '.jpg'
            or contains path separators.
    """
```

**Behavior Specification:**
- **Input Validation:**
  - If `filename` is provided: must end with `.jpg`; must not contain `/` or `\`;
    must not be empty string. Raise `ValueError` otherwise.
- **Processing Logic:**
  1. Acquire `self._highres_lock` (a new `threading.Lock` attribute, see §4).
  2. Attempt high-res path: if `self.provider` has attribute `picam2` and
     `self.provider.picam2 is not None`, call
     `self.provider.picam2.capture_array('main')` → RGB array; convert to BGR via
     `cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)`.
  3. If step 2 fails for any reason (exception, no `picam2`), fall back to `self.get_frame()`.
  4. If both paths return `None`: release lock; return `None`.
  5. Build output path: `data/auto_captures/` joined with resolved filename.
     Use `pathlib.Path` — **no hardcoded `/home/pi`** (system_constraints §4).
  6. Create directory if absent (`exist_ok=True`).
  7. Encode with `cv2.imwrite(..., [cv2.IMWRITE_JPEG_QUALITY, 95])`.
  8. If encode fails: log error; release lock; return `None`.
  9. Call `self._cleanup_auto_captures()` (private, see §4).
  10. Release lock; return absolute path string.
- **Output Guarantee:** Returned path exists on disk and is a valid JPEG.
- **Side Effects:** Creates file on disk; may delete old files; acquires hardware lock.

**Error Handling:**
- Invalid `filename` argument → Raise `ValueError` with message
  `"filename must be a '.jpg' basename without path separators"`
- `cv2.imwrite` failure → Log `ERROR`; return `None` (do NOT raise).
- Hardware exception during `capture_array` → Log `WARNING`; fall back silently.

**Performance Requirements:**
- Time Complexity: O(N) where N = number of files in `auto_captures/` (cleanup scan).
- Space Complexity: O(1) beyond the frame buffer.
- **Target latency (Pi 4B, CSI main stream):** < 500 ms (ISP capture + encode).

---

#### Method: `start_auto_detection`

```python
def start_auto_detection(
    self,
    sensitivity: float = 0.08,
    interval: float = 1.0,
    confirm_frames: int = 3,
    detection_callback: Optional[Callable[[str], None]] = None
) -> None:
    """Start the background auto-detection loop.

    Spawns a daemon thread (_detection_loop) that samples self.current_frame
    at the specified interval, passes a downscaled copy to TextDetector.detect(),
    and triggers capture_highres() when confirm_frames consecutive positive
    detections occur.

    Idempotent: calling while already running logs a warning and returns.

    Args:
        sensitivity: Forwarded to TextDetector.__init__. Default 0.08.
        interval: Seconds between detection samples. Min 0.5, Max 10.0.
            Default 1.0 (1 fps).
        confirm_frames: Number of consecutive positive detections required
            before triggering capture. Min 1, Max 10. Default 3.
        detection_callback: Optional callable invoked with the saved file path
            after a successful capture. Called from the detection thread.
            Must be non-blocking.

    Raises:
        ValueError: If interval or confirm_frames are out of valid range.
        RuntimeError: If capture has not been started (self.provider is None).
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `0.5 <= interval <= 10.0` — raise `ValueError` with message
    `"interval must be between 0.5 and 10.0 seconds"`
  - `1 <= confirm_frames <= 10` — raise `ValueError` with message
    `"confirm_frames must be between 1 and 10"`
  - `self.provider is None` → raise `RuntimeError` with message
    `"Camera not started. Call start_capture() before start_auto_detection()."`
- **Processing Logic:**
  1. If `self._detection_thread` is not None and `.is_alive()` → log warning; return.
  2. Store params as private instance attributes (see §4).
  3. Instantiate `TextDetector(sensitivity=sensitivity)`.
  4. Set `self._detection_active = True`.
  5. Create and start daemon thread targeting `self._detection_loop`.
- **Output Guarantee:** After return, `self._detection_thread.is_alive()` is True.
- **Side Effects:** Spawns background daemon thread; allocates `TextDetector` instance.

**Error Handling:**
- Invalid parameter ranges → Raise `ValueError` as specified.
- `RuntimeError` if provider not initialized → documented above.

**Performance Requirements:**
- Time Complexity: O(1) for the call itself (thread spawn).
- Space Complexity: O(1).

---

#### Method: `stop_auto_detection`

```python
def stop_auto_detection(self) -> None:
    """Stop the background auto-detection loop.

    Sets the stop flag and waits up to 5 seconds for the detection thread
    to terminate gracefully. Idempotent: safe to call when not running.
    """
```

**Behavior Specification:**
- **Input Validation:** None.
- **Processing Logic:**
  1. Set `self._detection_active = False`.
  2. If `self._detection_thread` is not None and `.is_alive()`:
     call `.join(timeout=5.0)`.
  3. Set `self._detection_thread = None`.
- **Output Guarantee:** Detection thread is no longer running after return (within timeout).
- **Side Effects:** Terminates background thread.

**Error Handling:**
- If thread does not terminate within 5 s: log `WARNING`
  `"Detection thread did not stop within timeout"`. Do NOT raise.

**Performance Requirements:**
- Blocking time: ≤ 5 s (thread join timeout).
- Space Complexity: O(1).

---

### Module C — New API Endpoint (`src/api/server.py`)

---

#### Endpoint: `POST /api/vision/auto-detect`

**Request Body (JSON):**
```json
{
    "enabled": true,
    "sensitivity": 0.08,
    "interval": 1.0,
    "confirm_frames": 3
}
```

**Field Contracts:**
- `enabled` (bool, required): `true` starts detection, `false` stops it.
- `sensitivity` (float, optional): Default 0.08. Validated by `TextDetector`.
- `interval` (float, optional): Default 1.0. Validated by `start_auto_detection`.
- `confirm_frames` (int, optional): Default 3. Validated by `start_auto_detection`.

**Response (Success — 200):**
```json
{
    "success": true,
    "auto_detect_enabled": true,
    "sensitivity": 0.08,
    "interval": 1.0,
    "confirm_frames": 3
}
```

**Response (Error — 400):**
```json
{
    "success": false,
    "error": "interval must be between 0.5 and 10.0 seconds"
}
```

**Response (Error — 503):**
```json
{
    "success": false,
    "error": "Camera not started"
}
```

**Behavior Specification:**
- Route handler must NOT block. It delegates to `vision_manager.start_auto_detection()`
  or `vision_manager.stop_auto_detection()` — both return immediately.
- Must validate that `"enabled"` key is present in request JSON; return 400 if absent.
- On `ValueError` from `start_auto_detection`: return 400 with error message.
- On `RuntimeError` from `start_auto_detection`: return 503 with error message.
- Function length ≤ 50 lines (system_constraints §4).

---

#### Endpoint: `GET /api/status` — Extension

The existing `/api/status` response must be extended with one new field:

```json
{
    "auto_detect_enabled": false
}
```

This field reflects `vision_manager._detection_active` (or `False` if the attribute does not
exist). The implementer must add this field to the existing status dict **without modifying
the existing response structure**.

---

## 3. DEPENDENCIES

### `TextDetector`
**This module CALLS:**
- `cv2.cvtColor`, `cv2.threshold`, `cv2.morphologyEx`, `cv2.findContours`, `cv2.Canny` — OpenCV image processing.

**This module is CALLED BY:**
- `VisionManager._detection_loop()` — frame-by-frame detection sampling.

**Imports allowed:** `cv2`, `numpy`, `logging`, `typing` — no new third-party dependencies.

---

### `VisionManager` Extensions
**New methods CALL:**
- `TextDetector.detect()` — receipt presence check.
- `CsiCameraProvider.picam2.capture_array('main')` — high-res frame acquisition (via duck-typed attribute access, NOT a formal interface call).
- `self.get_frame()` — low-res fallback.
- `self._cleanup_auto_captures()` — private cleanup helper (see §4).

**Called by:**
- `POST /api/vision/auto-detect` → `start_auto_detection()` / `stop_auto_detection()`.
- `VisionManager._detection_loop()` (internal) → `capture_highres()`.
- `POST /api/vision/capture` may optionally call `capture_highres()` — **out of scope for this contract; existing endpoint is IMMUTABLE**.

---

### Server Endpoint
**Calls:**
- `vision_manager.start_auto_detection(...)` / `vision_manager.stop_auto_detection()`.
- `vision_manager._detection_active` (read-only attribute access).

---

## 4. DATA STRUCTURES

### New Private Attributes on `VisionManager`

```python
_detection_active: bool = False
_detection_thread: Optional[threading.Thread] = None
_detection_sensitivity: float = 0.08
_detection_interval: float = 1.0
_detection_confirm_frames: int = 3
_detection_callback: Optional[Callable[[str], None]] = None
_highres_lock: threading.Lock  # Initialized in __init__
_AUTO_CAPTURE_DIR: ClassVar[str] = "data/auto_captures"
_AUTO_CAPTURE_MAX_FILES: ClassVar[int] = 100
```

All must be initialized in `VisionManager.__init__` without altering existing attributes.

---

### Private Method: `_detection_loop`

```python
def _detection_loop(self) -> None:
    """Background detection sampling loop. NOT part of public interface."""
```

Behavior (for implementer reference only — no contract binding):
- While `self._detection_active and not self.stopped`:
  1. Sleep `self._detection_interval` seconds.
  2. Acquire latest frame: `frame = self.get_frame()`.
  3. If `frame is None`: continue.
  4. Downscale to 320×240: `small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)`.
  5. Call `detected, bbox = self._detector.detect(small)`.
  6. If `detected`: increment `_consecutive_detections`; else reset to 0.
  7. If `_consecutive_detections >= self._detection_confirm_frames`:
     - Reset counter.
     - Call `path = self.capture_highres()`.
     - If `path` and `self._detection_callback`: call `self._detection_callback(path)`.
     - Log `INFO f"Auto-capture saved: {path}"`.

> Note: `_consecutive_detections` is a local variable inside the loop, NOT stored as an instance attribute (avoids thread-safety complexity).

---

### Private Method: `_cleanup_auto_captures`

```python
def _cleanup_auto_captures(self) -> None:
    """Delete oldest files when auto_captures/ exceeds _AUTO_CAPTURE_MAX_FILES."""
```

Behavior:
- List all `.jpg` files in `_AUTO_CAPTURE_DIR` sorted by `mtime` ascending.
- While `len(files) > _AUTO_CAPTURE_MAX_FILES`: delete oldest; pop from list.
- Must use `pathlib.Path` — no hardcoded paths.
- Must NOT raise on file-not-found (race condition safety).

---

## 5. CONSTRAINTS (FROM SYSTEM CONSTRAINTS)

| # | Constraint | Source |
|---|-----------|--------|
| C1 | All Python functions ≤ 50 lines. Refactor `_detection_loop` into sub-methods if needed. | §4 Code Quality |
| C2 | Type hints mandatory on all public and private methods. | §4 Code Quality |
| C3 | Google-style docstrings on all public classes and methods. | §4 Code Quality |
| C4 | No `os.system`. Use `subprocess.run` (N/A here) or `pathlib.Path`. | §4 Security |
| C5 | No hardcoded paths. Use `pathlib.Path` and `os.path.join`. | §4 Security |
| C6 | No `asyncio`. Use `threading` only. | §1 Concurrency |
| C7 | HTTP routes must return immediately. `start_auto_detection` returns before thread begins work. | §1 Non-Blocking |
| C8 | No direct hardware libraries in API routes. Route calls `VisionManager` only. | §1 Hardware Abstraction |
| C9 | Image downscaling to ≤ 1000px before heavy processing. Detector works on 320×240 — compliant. | §6.1 Memory |
| C10 | Sequential processing. Detection loop runs single-threaded. No concurrent captures. `_highres_lock` enforces mutual exclusion. | §6.1 Sequential |

---

## 6. MEMORY COMPLIANCE

*No `_memory_snippet.txt` was provided. Section is intentionally blank.*

---

## 7. ACCEPTANCE CRITERIA

---

### Test Case 1: TextDetector — Receipt Detected

- **Scenario:** A synthetic 320×240 frame containing a bright white rectangle with horizontal black lines (simulated text) placed on a grey background.
- **Input:** `bgr_frame` = synthesized via `np.zeros` + white rect fill + black horizontal lines.
- **Expected Output:** `detected = True`, `bbox` is a 4-tuple of ints.
- **Expected Behavior:** Edge density in the bright region exceeds default `sensitivity=0.08`.

---

### Test Case 2: TextDetector — No Receipt (Blank Frame)

- **Scenario:** Uniform grey frame (no bright regions).
- **Input:** `bgr_frame = np.full((240, 320, 3), 128, dtype=np.uint8)`
- **Expected Output:** `(False, None)`
- **Expected Behavior:** No contour meets the area threshold; returns early.

---

### Test Case 3: TextDetector — Invalid Input

- **Scenario:** `None` passed as frame.
- **Input:** `detect(None)`
- **Expected Exception:** `ValueError`
- **Expected Message:** `"bgr_frame must be a 3-channel BGR numpy array"`

---

### Test Case 4: TextDetector — Sensitivity Boundary

- **Scenario:** `sensitivity=0.0` (maximum sensitivity).
- **Input:** Any frame with a bright region of any texture.
- **Expected Output:** `detected = True` (edge_density ≥ 0.0 always).
- **Behavior:** Acts as "detect anything with a bright contour."

---

### Test Case 5: `capture_highres` — CSI Path

- **Scenario:** `VisionManager` running with a mock `CsiCameraProvider` whose `picam2`
  attribute has a `capture_array('main')` method returning a `(1080, 1920, 3)` uint8 array.
- **Input:** `vision_manager.capture_highres()`
- **Expected Output:** A non-None string path ending in `.jpg`.
- **Expected Behavior:** File exists at returned path; directory `data/auto_captures/` created.

---

### Test Case 6: `capture_highres` — Fallback Path

- **Scenario:** `VisionManager` running with `UsbCameraProvider` (no `picam2` attribute).
- **Input:** `vision_manager.capture_highres()`
- **Expected Output:** Non-None path (from `get_frame()` fallback), or `None` if no frame available.
- **Expected Behavior:** No exception raised; falls back silently.

---

### Test Case 7: `capture_highres` — Invalid Filename

- **Input:** `vision_manager.capture_highres(filename="../../etc/passwd.jpg")`
- **Expected Exception:** `ValueError`
- **Expected Message:** `"filename must be a '.jpg' basename without path separators"`

---

### Test Case 8: `start_auto_detection` — Invalid Interval

- **Input:** `vision_manager.start_auto_detection(interval=0.1)`
- **Expected Exception:** `ValueError`
- **Expected Message:** `"interval must be between 0.5 and 10.0 seconds"`

---

### Test Case 9: Auto-Detect API Endpoint — Enable

- **Input:** `POST /api/vision/auto-detect` with `{"enabled": true, "sensitivity": 0.1, "interval": 2.0, "confirm_frames": 2}`
- **Expected Response:** `200 OK`, `{"success": true, "auto_detect_enabled": true, ...}`
- **Expected Behavior:** Detection thread is alive after call.

---

### Test Case 10: Auto-Detect API Endpoint — Missing `enabled` Key

- **Input:** `POST /api/vision/auto-detect` with `{"sensitivity": 0.1}`
- **Expected Response:** `400 Bad Request`, `{"success": false, "error": "..."}` 
- **Expected Behavior:** No thread spawned.

---

### Test Case 11: `/api/status` Extension

- **Input:** `GET /api/status` when detection is running.
- **Expected Response:** Existing fields unchanged + `"auto_detect_enabled": true`.
- **Expected Behavior:** No regression on existing status consumers.

---

### Test Case 12: End-to-End — Simulated Detection Trigger

- **Scenario:** Mock `TextDetector.detect` to return `(True, (0,0,100,100))` unconditionally.
  Set `confirm_frames=1`. Wait 1× `interval`.
- **Expected Behavior:** `capture_highres()` is called; file appears in `data/auto_captures/`.

---

## 8. INTEGRATION POINTS SUMMARY

```
POST /api/vision/auto-detect
         │
         ▼
VisionManager.start_auto_detection()
         │  spawns
         ▼
VisionManager._detection_loop()  [daemon thread, ~1 fps]
         │  reads
         ├──► self.current_frame  [via get_frame()]
         │  downscales to 320×240
         ├──► TextDetector.detect()
         │       ├── _isolate_receipt logic (brightness contour)
         │       └── Canny edge density check
         │  on confirm_frames consecutive hits
         └──► VisionManager.capture_highres()
                   ├── CsiCameraProvider.picam2.capture_array('main') [primary]
                   └── VisionManager.get_frame()  [fallback]
                   └── saves to data/auto_captures/auto_YYYYMMDD_HHMMSS.jpg
                   └── optional: detection_callback(path)

GET /api/status  ──► includes auto_detect_enabled flag
```