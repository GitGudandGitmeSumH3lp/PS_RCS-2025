# CONTRACT: TextDetector (MSER-Based)
**Version:** 1.0
**Last Updated:** 2026-02-25
**Status:** Draft
**Target File:** `src/services/text_detector.py`

---

## 1. PURPOSE

`TextDetector` is a lightweight, single-class service that detects the presence
of text-like regions in a BGR image frame using OpenCV's MSER (Maximally Stable
Extremal Regions) algorithm combined with geometric filtering. It is consumed
exclusively by `VisionManager._detection_loop()` to determine whether a Flash
Express receipt has entered the camera's field of view, gating the high-resolution
auto-capture trigger. The class has no I/O side-effects and carries no mutable
shared state, making it safe for use from background threads.

---

## 2. PUBLIC INTERFACE

### Class: `TextDetector`

```python
class TextDetector:
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
        """Initialise the MSER-based text detector.

        Maps `sensitivity` (0.0–1.0) to MSER `_delta` via an inverse linear
        function so that higher sensitivity produces more candidate blob
        detections. All geometric filtering thresholds are configurable via
        constructor kwargs to allow future calibration without contract changes.

        Args:
            sensitivity: Detection aggressiveness in range [0.0, 1.0].
                Translated to MSER `_delta` by the formula:
                    delta = max(2, int(20 - sensitivity * 18))
                At sensitivity=0.08 (default) → delta=18 (conservative).
                At sensitivity=1.0 → delta=2   (aggressive).
            min_area: Minimum pixel area for a MSER region to be considered.
                Regions smaller than this are discarded as noise. Default 50.
            aspect_ratio_min: Lower bound of bounding-box width/height ratio
                for a valid text blob. Default 0.2.
            aspect_ratio_max: Upper bound of bounding-box width/height ratio
                for a valid text blob. Default 5.0.
            min_solidity: Minimum ratio of region area to its convex hull area.
                Rejects highly irregular blobs. Default 0.2.
            min_detections: Minimum number of qualifying regions required before
                the frame is declared as text-present. Default 5.
            threshold_count: Denominator used to normalise confidence:
                confidence = min(1.0, region_count / threshold_count). Default 10.

        Raises:
            ValueError: If sensitivity is not in [0.0, 1.0].
            ValueError: If min_area < 1.
            ValueError: If aspect_ratio_min >= aspect_ratio_max.
            ValueError: If min_solidity not in [0.0, 1.0].
            ValueError: If min_detections < 1 or threshold_count < 1.
        """
        ...
```

---

### Method: `detect`

**Signature:**
```python
def detect(self, frame: np.ndarray) -> tuple[bool, float]:
    """Detect text presence in a single BGR frame.

    Converts the frame to grayscale, runs MSER to find candidate blobs,
    applies geometric filters (area, aspect ratio, solidity), counts
    surviving regions, and returns a boolean decision plus a normalised
    confidence score.

    Args:
        frame: BGR uint8 NumPy array. Expected shape: (240, 320, 3).
            Other shapes are accepted but performance is only guaranteed
            for the nominal size.

    Returns:
        A tuple (text_present, confidence) where:
            - text_present (bool): True if qualifying region count >=
              self._min_detections.
            - confidence (float): Normalised score in [0.0, 1.0], computed
              as min(1.0, region_count / self._threshold_count).

    Raises:
        None: All exceptions are caught internally. On any error the method
            logs the exception at ERROR level and returns (False, 0.0).
    """
    ...
```

**Behavior Specification:**

- **Input Validation:** Frame must be a NumPy ndarray with `dtype == np.uint8`
  and `ndim == 3`. If this check fails, log at ERROR level and return
  `(False, 0.0)` — do NOT raise.
- **Processing Logic:**
  1. Convert frame to grayscale: `cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)`.
  2. Detect MSER regions: `self._mser.detectRegions(gray)` — returns
     `(regions, bboxes)` where `bboxes` is a list of `(x, y, w, h)` tuples.
  3. For each `(x, y, w, h)` in `bboxes`:
     a. Discard if `w * h < self._min_area`.
     b. Compute `aspect = w / h` (guard against `h == 0`). Discard if outside
        `[self._aspect_ratio_min, self._aspect_ratio_max]`.
     c. Retrieve the corresponding region point list (parallel to `bboxes`).
        Compute `solidity = len(region_points) / (w * h)`. Discard if
        `solidity < self._min_solidity`.
  4. Count surviving regions as `region_count`.
  5. Compute `confidence = min(1.0, region_count / self._threshold_count)`.
  6. Return `(region_count >= self._min_detections, confidence)`.
- **Output Guarantee:** Return type is always `tuple[bool, float]`. The float
  is always in `[0.0, 1.0]`.
- **Side Effects:** None. All variables are local. No shared mutable state is
  read or written.

**Error Handling:**

- **Any `cv2.error`:** Log `f"TextDetector cv2 error: {e}"` at ERROR. Return `(False, 0.0)`.
- **Any `Exception`:** Log `f"TextDetector unexpected error: {e}"` at ERROR. Return `(False, 0.0)`.

**Performance Requirements:**

- Time Complexity: O(N) where N = number of pixels in the downscaled frame.
  MSER on 320×240 is empirically ~20ms on Pi 4B.
- Space Complexity: O(R) where R = number of MSER regions detected (typically < 500).
- **Hard Target:** `detect()` must complete in < 100ms on Pi 4B under normal load.

---

## 3. DEPENDENCIES

**This module CALLS:**
- `cv2.MSER_create(...)` — OpenCV MSER detector construction (in `__init__`)
- `cv2.cvtColor(...)` — Grayscale conversion (in `detect`)
- `mser.detectRegions(gray)` — MSER blob detection (in `detect`)
- `logging.getLogger(__name__)` — Error reporting

**This module is CALLED BY:**
- `VisionManager._detection_loop()` — Passes a 320×240 BGR frame once per
  `_detection_interval` seconds (default 1.0 s). Reads only the boolean from
  the tuple; confidence is currently unused but must still be returned.

**Allowed Imports (per `system_constraints.md` Section 1):**
```python
import logging
from typing import Optional
import cv2
import numpy as np
```
No other third-party libraries. No deep learning models.

---

## 4. DATA STRUCTURES

No custom types or dataclasses are required. The sole public return type is the
built-in `tuple[bool, float]`.

**Internal State (private attributes set in `__init__`):**

| Attribute | Type | Description |
|---|---|---|
| `_mser` | `cv2.MSER` | Configured MSER detector instance |
| `_min_area` | `int` | Minimum blob pixel area |
| `_aspect_ratio_min` | `float` | Lower aspect ratio bound |
| `_aspect_ratio_max` | `float` | Upper aspect ratio bound |
| `_min_solidity` | `float` | Minimum convex-hull fill ratio |
| `_min_detections` | `int` | Region count threshold for positive decision |
| `_threshold_count` | `int` | Denominator for confidence normalisation |

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

- **Python 3.9+** (system_constraints.md §1 — Environment): Use
  `tuple[bool, float]` lowercase generic syntax (valid from 3.9).
- **Type Hints Mandatory** (§4 — Code Quality): All method signatures must carry
  complete type annotations.
- **Google-Style Docstrings Required** (§4): All public methods must have
  `Args:`, `Returns:`, `Raises:` sections as shown above.
- **Max Function Length 50 lines** (§4): `detect()` must not exceed 50 lines.
  If filtering logic grows, extract `_filter_regions(bboxes, regions)` helper.
- **No Global State** (§1 — Architectural Rules): Detector state lives entirely
  within the `TextDetector` instance. No module-level variables.
- **Threading** (§1): `detect()` is called from a background `threading.Thread`.
  It is inherently thread-safe because it uses only local variables and a
  stateless `cv2.MSER` instance (reads only, no writes).
- **No Hardcoded Paths** (§4): Not applicable — this module has no file I/O.

---

## 6. MEMORY COMPLIANCE

No `_memory_snippet.txt` was provided for this task. If project memory is
available when implementing, the implementer MUST check it and apply all
applicable rules before submitting for audit.

**Applied Constraints from Context:**

- `csi_provider_yuv420_fix.md` (2026-02-22) — YUV420 Contract: Frames arriving
  at `detect()` are guaranteed to be BGR uint8 arrays produced by the
  `CsiCameraProvider.read()` pipeline. The implementer must not assume RGB input.

---

## 7. SENSITIVITY-TO-DELTA MAPPING

The `sensitivity` parameter (public-facing, 0.0–1.0) is an abstraction over
MSER's internal `_delta` parameter, which controls how much the intensity of a
region boundary must differ from its surroundings. A lower `_delta` → more
regions detected (more sensitive).

**Mapping Formula:**
```
delta = max(2, int(20 - sensitivity * 18))
```

| `sensitivity` | `_delta` | Behaviour |
|---|---|---|
| 0.0 | 20 | Very conservative — only sharp, high-contrast text |
| 0.08 (default) | 18 | Balanced — production default from `VisionManager` |
| 0.5 | 11 | Moderate — picks up lighter print |
| 1.0 | 2 | Aggressive — may produce false positives in busy scenes |

The formula is a simple inverse-linear map over the empirically useful MSER
delta range of [2, 20]. Values below 2 cause MSER instability and are clamped.

---

## 8. ACCEPTANCE CRITERIA

**Test Case 1 — Positive Detection (Receipt Frame)**
- Input: A 320×240 BGR array containing a Flash Express receipt with dense
  printed text (≥10 distinct text blobs expected by MSER at default sensitivity).
- Expected Output: `(True, confidence)` where `confidence > 0.5`.
- Expected Behavior: `region_count >= 5` after geometric filtering.

**Test Case 2 — Negative Detection (Blank Background)**
- Input: A 320×240 BGR array of a uniformly grey surface (no text).
- Expected Output: `(False, 0.0)` or `(False, confidence < 0.3)`.
- Expected Behavior: `region_count < 5` after geometric filtering.

**Test Case 3 — Error Resilience (Corrupt Frame)**
- Input: A 2-dimensional array `np.zeros((240, 320), dtype=np.uint8)` (missing
  channel axis, simulating a bad frame).
- Expected Exception: None raised.
- Expected Output: `(False, 0.0)`.
- Expected Behavior: Exception caught internally; error logged at ERROR level.

**Test Case 4 — Boundary: sensitivity=0.0**
- Input: `TextDetector(sensitivity=0.0)`. Call `detect()` with a blank frame.
- Expected Output: `(False, 0.0)`.
- Expected Behavior: `_delta` set to 20; no crash.

**Test Case 5 — Boundary: sensitivity=1.0**
- Input: `TextDetector(sensitivity=1.0)`. Call `detect()` with a receipt frame.
- Expected Output: `(True, confidence)` where `confidence >= 0.5`.
- Expected Behavior: `_delta` set to 2; more regions detected than default.

**Test Case 6 — Constructor Validation**
- Input: `TextDetector(sensitivity=1.5)`.
- Expected Exception: `ValueError`.
- Expected Message: Contains `"sensitivity"` and `"[0.0, 1.0]"`.

**Test Case 7 — Performance**
- Input: 100 consecutive calls to `detect()` with a 320×240 BGR frame.
- Expected Behavior: Average wall-clock time per call < 100ms on Pi 4B.

---

## 9. INTEGRATION NOTES

### How `VisionManager` uses `TextDetector`

```python
# In VisionManager.start_auto_detection():
from src.services.text_detector import TextDetector
self._detector = TextDetector(sensitivity=self._detection_sensitivity)

# In VisionManager._detection_loop():
small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)
detected, _ = self._detector.detect(small)
consecutive = consecutive + 1 if detected else 0
if consecutive >= self._detection_confirm_frames:
    path = self.capture_highres()
```

The underscore in `detected, _ = ...` confirms that `confidence` is currently
unused by the consumer but **must still be returned** to satisfy the contract.
Future phases may surface this value in the API response.

### 3-Frame Confirmation Gate

`VisionManager` requires `_detection_confirm_frames` (default 3) consecutive
positive detections before firing `capture_highres()`. This gate exists entirely
in `VisionManager` — `TextDetector` has no knowledge of it and must not
implement frame-to-frame state.

### Planned Future Improvement

If MSER proves insufficient at higher frame rates or in low-contrast conditions,
the detector may be upgraded to an EAST text-detector model
(`cv2.dnn.readNet`). The `detect()` signature is intentionally identical to what
an EAST-based implementation would require, ensuring a drop-in upgrade path with
no contract changes.

---

## 10. POTENTIAL PITFALLS FOR IMPLEMENTER

- **`detectRegions` returns `(regions, bboxes)`** where `regions` is a list of
  point arrays and `bboxes` is a list of `(x, y, w, h)` tuples. The two lists
  are parallel — do not separate them before filtering.
- **Solidity approximation:** True solidity requires computing a convex hull
  (`cv2.convexHull`). For performance on Pi 4B, use the approximation
  `solidity ≈ len(region_points) / (w * h)` which is faster and sufficient for
  this use case.
- **`h == 0` guard:** MSER can occasionally produce degenerate bounding boxes
  with zero height. Guard with `if h == 0: continue` before computing aspect ratio.
- **MSER is stateless for `detect()`:** The same `cv2.MSER` instance can be
  called from multiple threads safely (read-only), but do not call
  `detectRegions` concurrently on the same instance. This is safe here because
  `VisionManager` uses a single detection thread.

---

✅ **Contract Created:** `docs/contracts/text_detector_mser.md` v1.0
📋 **Work Order:** See section below.

---

# WORK ORDER FOR IMPLEMENTER

**Target File:** `src/services/text_detector.py`
**Contract Reference:** `docs/contracts/text_detector_mser.md` v1.0
**Priority:** HIGH (Blocks `VisionManager.start_auto_detection()`)
**Estimated Effort:** 1–2 hours

---

## STRICT CONSTRAINTS (NON-NEGOTIABLE)

1. **Type Hints Mandatory** — All parameters and return values annotated.
2. **Google-Style Docstrings** — `__init__` and `detect` must have full
   `Args:`, `Returns:`, `Raises:` blocks.
3. **Max 50 lines per function** — If `detect()` exceeds 50 lines, extract
   `_filter_regions(bboxes: list, regions: list) -> int` as a private helper.
4. **No Global State** — No module-level variables. All state in instance.
5. **Allowed imports only:** `logging`, `typing`, `cv2`, `numpy`.
6. **`detect()` MUST NOT raise** — Wrap entire body in `try/except Exception`.

---

## MEMORY COMPLIANCE (MANDATORY)

No `_memory_snippet.txt` was provided. Check for one before implementing and
apply all applicable entries.

---

## REQUIRED LOGIC

### Step 1 — `__init__`

```python
import cv2
import logging
import numpy as np

logger = logging.getLogger(__name__)

class TextDetector:
    def __init__(self, sensitivity: float = 0.08, ...) -> None:
        if not (0.0 <= sensitivity <= 1.0):
            raise ValueError(f"sensitivity must be in [0.0, 1.0], got {sensitivity}")
        # ... validate other params ...
        delta = max(2, int(20 - sensitivity * 18))
        self._mser = cv2.MSER_create(_delta=delta)
        self._min_area = min_area
        self._aspect_ratio_min = aspect_ratio_min
        self._aspect_ratio_max = aspect_ratio_max
        self._min_solidity = min_solidity
        self._min_detections = min_detections
        self._threshold_count = threshold_count
```

### Step 2 — `detect`

```python
def detect(self, frame: np.ndarray) -> tuple[bool, float]:
    try:
        # 1. Validate input
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.dtype != np.uint8:
            logger.error("TextDetector.detect: invalid frame format")
            return (False, 0.0)

        # 2. Grayscale conversion
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 3. MSER detection
        regions, bboxes = self._mser.detectRegions(gray)

        # 4. Geometric filtering (delegate to _filter_regions if needed)
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
```

### Step 3 — `_filter_regions` (private helper, if `detect` would exceed 50 lines)

```python
def _filter_regions(
    self,
    regions: list,
    bboxes: list,
) -> int:
    """Count MSER bboxes that pass geometric filters.

    Args:
        regions: List of point arrays from MSER.detectRegions.
        bboxes: Parallel list of (x, y, w, h) bounding boxes.

    Returns:
        Count of regions passing all filters.
    """
    count = 0
    for region_pts, (x, y, w, h) in zip(regions, bboxes):
        if h == 0:
            continue
        if w * h < self._min_area:
            continue
        aspect = w / h
        if not (self._aspect_ratio_min <= aspect <= self._aspect_ratio_max):
            continue
        solidity = len(region_pts) / (w * h)
        if solidity < self._min_solidity:
            continue
        count += 1
    return count
```

---

## INTEGRATION POINTS

- **Will be called by:** `VisionManager._detection_loop()` in `src/services/vision_manager.py`
- **Lazy import location:** `VisionManager.start_auto_detection()`:
  ```python
  from src.services.text_detector import TextDetector
  self._detector = TextDetector(sensitivity=sensitivity)
  ```
- **Call site:**
  ```python
  detected, _ = self._detector.detect(small)  # small is 320x240 BGR
  ```

---

## SUCCESS CRITERIA

- [ ] `TextDetector(sensitivity=0.08)` instantiates without error.
- [ ] `detect()` returns `(bool, float)` for any input without raising.
- [ ] `detect()` returns `(False, 0.0)` for a corrupt/wrong-shape frame.
- [ ] All functions ≤ 50 lines.
- [ ] `mypy src/services/text_detector.py --strict` → zero errors.
- [ ] Docstrings present with `Args:`, `Returns:`, `Raises:` sections.
- [ ] Average call time on Pi 4B < 100ms (target ~20ms).
- [ ] Auditor approval required before merging.

---

## APPENDIX: API MAP UPDATE

Copy this snippet into `docs/API_MAP_LITE.md` under **Section: Services Layer**:

```markdown
### Module: `text_detector`
**Location:** `src/services/text_detector.py`
**Status:** Designed (not yet implemented)
**Contract:** `docs/contracts/text_detector_mser.md` v1.0

**Public Interface:**
- `TextDetector(sensitivity: float = 0.08, min_area: int = 50, ...) -> None`
  - Purpose: Initialise MSER detector with sensitivity-to-delta mapping.
- `detect(frame: np.ndarray) -> tuple[bool, float]`
  - Purpose: Detect text presence in 320×240 BGR frame. Returns (text_present, confidence).
  - Thread-safe: Yes (local variables only, no shared mutable state).

**Dependencies:**
- Imports: `cv2`, `numpy`, `logging`
- Called by: `VisionManager._detection_loop()`
```

---

## HUMAN WORKFLOW CHECKPOINT

**Files You Should Have:**
- ✅ `docs/contracts/text_detector_mser.md` v1.0 — The formal contract (this file)
- ✅ API Map snippet (above) — Ready to paste

**Before Moving to Implementer:**
1. Review contract — does it capture all requirements from the spec?
2. Update `API_MAP_LITE.md` — paste the snippet above into the Services Layer section.
3. Save this file to `docs/contracts/text_detector_mser.md`.

**Next Agent:** `02_implementer.md`

**Required Files for Implementer:**
- `docs/contracts/text_detector_mser.md` v1.0
- `docs/API_MAP_LITE.md` (updated)
- `docs/system_constraints.md`
- `src/services/vision_manager.py` (for integration context)
- `_memory_snippet.txt` (if applicable)

**Verification Command (copy-paste to Implementer):**
```
/verify-context: docs/contracts/text_detector_mser.md, API_MAP_LITE.md, system_constraints.md, src/services/vision_manager.py
```