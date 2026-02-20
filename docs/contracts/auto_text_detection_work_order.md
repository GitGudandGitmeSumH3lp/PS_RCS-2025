# WORK ORDER FOR IMPLEMENTER

**Target Files:**
- `src/services/text_detector.py` ← NEW FILE
- `src/services/vision_manager.py` ← EXTEND (3 new methods + private helpers + new `__init__` attrs)
- `src/api/server.py` ← EXTEND (1 new endpoint + 1 status field)

**Contract Reference:** `docs/contracts/auto_text_detection.md` v1.0
**Phase:** 8.0 — Integration Testing & Polish (Sub-phase 8.2)

---

## Strict Constraints (NON-NEGOTIABLE)

1. All Python functions ≤ 50 lines. If `_detection_loop` exceeds 50 lines, split into sub-methods.
2. Type hints mandatory on every function signature (args + return).
3. Google-style docstrings on all public classes and methods.
4. No hardcoded paths. Use `pathlib.Path(__file__).parent` anchors or `os.path.join`. Never `/home/pi`.
5. No `asyncio`. `threading` only.
6. HTTP route handlers must return immediately — no `join()` or `sleep()` inside a route.
7. No direct `picam2` imports in `server.py`. Access hardware ONLY through `VisionManager`.

---

## Memory Compliance (MANDATORY)

*No memory snippet provided. Standard project memory applies.*

---

## File 1: `src/services/text_detector.py` (NEW)

### Required Logic

1. Import: `cv2`, `numpy as np`, `logging`, `typing.Tuple`, `typing.Optional`.
2. Implement `TextDetector.__init__(self, sensitivity: float = 0.08)`:
   - Validate `0.0 <= sensitivity <= 1.0` → `ValueError` on fail.
   - Store `self.sensitivity = sensitivity`.
   - Pre-compute Canny thresholds: `self._canny_lo = int(50 * (1 - sensitivity))`,
     `self._canny_hi = int(150 * (1 - sensitivity))`. Clamp lo ≥ 1.
3. Implement `TextDetector.detect(self, bgr_frame)`:
   - Validate frame is non-None, ndim==3, shape[2]==3 → `ValueError` on fail.
   - **Stage 1 — Isolate (copy of `FlashExpressOCR._isolate_receipt` algorithm):**
     - Convert to HSV; threshold V channel at 200.
     - Morphological close (20×20 rect kernel).
     - Find external contours. Filter area ≥ `frame_H * frame_W * 0.05`.
     - If none: return `(False, None)`.
     - Take largest. Get bounding rect `(x, y, w, h)`. Crop with 10-px pad.
     - If cropped < 100×100: return `(False, None)`.
   - **Stage 2 — Edge density:**
     - `gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)`
     - `edges = cv2.Canny(gray, self._canny_lo, self._canny_hi)`
     - `density = np.count_nonzero(edges) / edges.size`
     - `detected = density >= self.sensitivity`
   - Wrap in try/except; on `cv2.error` log warning and return `(False, None)`.
   - Return `(detected, (x, y, w, h))`.

> ⚠️ Do NOT import `FlashExpressOCR` inside `TextDetector`. Re-implement the isolation logic
> directly to avoid circular imports and keep the module self-contained and fast.

---

## File 2: `src/services/vision_manager.py` (EXTEND)

### Required Logic

**In `__init__`**, add after existing attribute assignments:
```python
self._detection_active: bool = False
self._detection_thread: Optional[threading.Thread] = None
self._detection_sensitivity: float = 0.08
self._detection_interval: float = 1.0
self._detection_confirm_frames: int = 3
self._detection_callback: Optional[Any] = None
self._detector: Optional[Any] = None  # TextDetector instance
self._highres_lock: threading.Lock = threading.Lock()
```

**Add class-level constants** (at top of class, after existing ClassVar if any):
```python
_AUTO_CAPTURE_DIR: ClassVar[str] = "data/auto_captures"
_AUTO_CAPTURE_MAX_FILES: ClassVar[int] = 100
```

**New Method 1 — `capture_highres`:**
1. Validate `filename` arg if provided (ends `.jpg`, no separators).
2. Acquire `self._highres_lock`.
3. Try: `self.provider.picam2.capture_array('main')` → convert RGB→BGR.
4. On AttributeError or any Exception: fall back to `self.get_frame()`.
5. If frame is `None`: release lock, return `None`.
6. Build path using `pathlib.Path(self._AUTO_CAPTURE_DIR)`.
7. Create dir (`exist_ok=True`).
8. Generate filename: `auto_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg` if not provided.
9. `cv2.imwrite(str(save_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])`.
10. Call `self._cleanup_auto_captures()`.
11. Release lock. Return `str(save_path.resolve())`.

**New Method 2 — `start_auto_detection`:**
1. Validate `interval` in [0.5, 10.0], `confirm_frames` in [1, 10].
2. Check `self.provider is None` → `RuntimeError`.
3. Check thread already alive → log warning, return.
4. Store params. Import and instantiate `TextDetector(sensitivity=sensitivity)` → `self._detector`.
5. Set `self._detection_active = True`.
6. Create daemon thread → `self._detection_thread`. Start it.

**New Method 3 — `stop_auto_detection`:**
1. Set `self._detection_active = False`.
2. If thread alive: `.join(timeout=5.0)`.
3. Set `self._detection_thread = None`.

**Private Method — `_detection_loop`:**
> This method MUST be ≤ 50 lines. Split into `_run_detection_cycle` if needed.
1. `consecutive = 0`
2. While `self._detection_active and not self.stopped`:
   - `time.sleep(self._detection_interval)`
   - `frame = self.get_frame()` → skip if None
   - `small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)`
   - `detected, _ = self._detector.detect(small)`
   - `consecutive = consecutive + 1 if detected else 0`
   - If `consecutive >= self._detection_confirm_frames`:
     - `consecutive = 0`
     - `path = self.capture_highres()`
     - If `path`: log INFO; call callback if set.

**Private Method — `_cleanup_auto_captures`:**
1. `from pathlib import Path`
2. `p = Path(self._AUTO_CAPTURE_DIR)`
3. If not exists: return.
4. `files = sorted(p.glob('*.jpg'), key=lambda f: f.stat().st_mtime)`
5. While `len(files) > self._AUTO_CAPTURE_MAX_FILES`: `files.pop(0).unlink(missing_ok=True)`

---

## File 3: `src/api/server.py` (EXTEND)

### Required Logic

**New route — `POST /api/vision/auto-detect`:**
```python
@app.route('/api/vision/auto-detect', methods=['POST'])
def api_auto_detect():
    # 1. Parse JSON body. Validate 'enabled' key present → 400 if missing.
    # 2. Extract optional: sensitivity, interval, confirm_frames with defaults.
    # 3. If enabled:
    #      try: vision_manager.start_auto_detection(...)
    #      except ValueError as e: return jsonify({'success': False, 'error': str(e)}), 400
    #      except RuntimeError as e: return jsonify({'success': False, 'error': str(e)}), 503
    # 4. Else: vision_manager.stop_auto_detection()
    # 5. Return 200 with current state.
```

**Extend existing `/api/status` route:**
- Add to the existing response dict:
  ```python
  'auto_detect_enabled': getattr(vision_manager, '_detection_active', False)
  ```
- Do NOT restructure or remove any existing keys.

---

## Integration Points

- **`TextDetector` imported by:** `vision_manager.py` (lazy import inside `start_auto_detection` to avoid circular import risks).
- **`capture_highres` called by:** `_detection_loop` (internal), and may be called externally in future (contract is public).
- **Status flag `_detection_active` read by:** `server.py` `/api/status` route.
- **`detection_callback` invoked from:** `_detection_loop` thread — callback MUST be non-blocking.

---

## Approved Import List for `text_detector.py`

```python
import cv2
import logging
import numpy as np
from typing import Optional, Tuple
```

No additional third-party imports. No Tesseract. No picamera2.

---

## Approved New Imports for `vision_manager.py`

```python
from pathlib import Path
from datetime import datetime
from typing import Callable  # add to existing typing import
# TextDetector import: lazy inside start_auto_detection method body
```

---

## Success Criteria

- [ ] All 12 test cases in contract §7 pass.
- [ ] All method signatures match the contract exactly (including default values).
- [ ] No existing `VisionManager` method signatures altered.
- [ ] No existing server routes altered (status route extended, not replaced).
- [ ] `text_detector.py` has zero imports outside the approved list.
- [ ] All functions ≤ 50 lines (verified by auditor line-count check).
- [ ] `data/auto_captures/` created automatically on first capture.
- [ ] Auditor approval required before merging.

---

## ⚠️ Known Design Decisions to Preserve

1. **Duck-typed `picam2` access:** `capture_highres` checks `hasattr(self.provider, 'picam2')`
   rather than `isinstance(self.provider, CsiCameraProvider)`. This preserves HAL abstraction.
2. **Lazy `TextDetector` import:** Import inside method body to avoid module-level circular
   dependency between `vision_manager` → `text_detector` if `text_detector` ever needs
   vision utilities in the future.
3. **No new thread for cleanup:** `_cleanup_auto_captures` runs synchronously inside
   `_highres_lock` context — acceptable because file-count scan on ≤100 files is O(ms).
4. **`confirm_frames` counter is local:** `consecutive` lives inside `_detection_loop` stack
   frame, not as an instance attribute, to eliminate a thread-safety concern.