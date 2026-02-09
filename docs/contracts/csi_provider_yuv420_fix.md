# WORK ORDER FOR IMPLEMENTER

**Target File:** `src/hardware/camera/csi_provider.py`
**Contract Reference:** `docs/contracts/csi_provider_yuv420_fix.md` v1.0
**Priority:** HIGH (Blocks `/api/vision/stream` functionality)
**Estimated Effort:** 2-3 hours (implementation + testing)

---

## STRICT CONSTRAINTS (NON-NEGOTIABLE)

### From `system_constraints.md`:

1. **Type Hints Mandatory:** ALL functions must have complete type annotations
   ```python
   def read(self) -> Tuple[bool, Optional[np.ndarray]]:
   ```

2. **Google-Style Docstrings Required:** All public methods need comprehensive docs
   ```python
   """Acquire the next available frame from camera.
   
   This method retrieves YUV420 frames from the ISP and converts them to BGR
   format for OpenCV compatibility.
   
   Returns:
       A tuple containing:
           - success (bool): True if frame acquired and converted successfully.
           - frame (Optional[np.ndarray]): BGR image array (HxWx3) if success, else None.
           
   Raises:
       None: Errors are returned as (False, None) for graceful degradation.
   """
   ```

3. **Max Function Length:** 50 lines per function. If `read()` exceeds this, refactor conversion logic into `_convert_yuv_to_bgr()` helper method.

4. **Threading Only:** Use `threading.Lock` for frame acquisition (already in contract)

5. **No Hardcoded Paths:** Use `pathlib` for any log file paths

### From Investigation Document:

6. **MANDATORY Format:** `lores` stream MUST use `"YUV420"` (not YUV422, YUYV, or RGB)

7. **Conversion Flag:** MUST use `cv2.COLOR_YUV2BGR_I420` (not `YUV420p2BGR` or other variants)

8. **Dual-Stream Preservation:** `main` stream remains at 1920x1080 RGB888 for high-res capture

---

## MEMORY COMPLIANCE (MANDATORY)

**No project memory entries provided in this work order.**

If `_memory_snippet.txt` exists with entries related to:
- Camera initialization patterns
- Color space conversion strategies
- Performance budgets for frame processing
- Error handling conventions

You MUST apply those rules. Check with project lead if unsure.

---

## REQUIRED LOGIC

### Step 1: Update Configuration in `start()` Method

**Current (Broken) Code:**
```python
config = self.picam2.create_preview_configuration(
    main={"size": (width, height), "format": "RGB888"},
    lores={"size": (width, height), "format": "RGB888"}  # ← WRONG
)
```

**Required Implementation:**
```python
config = self.picam2.create_preview_configuration(
    main={"size": (1920, 1080), "format": "RGB888"},  # Fixed high-res
    lores={"size": (width, height), "format": "YUV420"},  # COMPLIANT
    buffer_count=2  # Thread safety
)
```

**Validation Before Configure:**
```python
# Add parameter validation (see contract section 4.2)
if not (320 <= width <= 1920):
    raise ValueError(f"Width {width} outside valid range [320, 1920]")
if not (240 <= height <= 1080):
    raise ValueError(f"Height {height} outside valid range [240, 1080]")
if not (1 <= fps <= 30):
    raise ValueError(f"FPS {fps} outside valid range [1, 30]")
```

### Step 2: Modify `read()` Method for YUV→BGR Conversion

**Current (RGB Assumption) Code:**
```python
def read(self) -> Tuple[bool, Optional[np.ndarray]]:
    if not self._running:
        return (False, None)
    
    try:
        frame = self.picam2.capture_array("lores")  # Assumes RGB
        return (True, frame)
    except Exception as e:
        return (False, None)
```

**Required Implementation:**
```python
def read(self) -> Tuple[bool, Optional[np.ndarray]]:
    """Acquire frame with YUV420→BGR conversion.
    
    Retrieves YUV420 planar frame from ISP and converts to BGR format
    for OpenCV compatibility. Thread-safe via internal locking.
    
    Returns:
        Tuple[bool, Optional[np.ndarray]]: Success flag and BGR frame.
    """
    if not self._running:
        return (False, None)
    
    try:
        # Thread-safe capture (see contract section 7.3)
        with self._frame_lock:
            frame_yuv = self.picam2.capture_array("lores")
            
            # Shape validation (see contract section 5.1)
            expected_yuv_height = int(self._height * 1.5)
            if frame_yuv.shape[0] != expected_yuv_height:
                # Log error but return gracefully
                print(f"ERROR: YUV shape mismatch - expected {expected_yuv_height}x{self._width}, "
                      f"got {frame_yuv.shape[0]}x{frame_yuv.shape[1]}")
                return (False, None)
            
            # Color space conversion (see contract section 5.2)
            frame_bgr = cv2.cvtColor(frame_yuv, cv2.COLOR_YUV2BGR_I420)
            
        return (True, frame_bgr)
        
    except cv2.error as e:
        print(f"ERROR: Color conversion failed - {e}")
        return (False, None)
    except Exception as e:
        print(f"ERROR: Frame capture failed - {e}")
        return (False, None)
```

### Step 3: Add Internal State for Cached Dimensions

**Required Class Attributes (in `__init__`):**
```python
def __init__(self):
    super().__init__()
    self.picam2: Optional[Picamera2] = None
    self._running: bool = False
    self._frame_lock: threading.Lock = threading.Lock()
    
    # NEW: Cache dimensions for YUV validation
    self._width: int = 0
    self._height: int = 0
    self._fps: int = 0
```

**Update in `start()` Method:**
```python
def start(self, width: int, height: int, fps: int) -> bool:
    # ... validation code ...
    
    # Cache dimensions for read() validation
    self._width = width
    self._height = height
    self._fps = fps
    
    # ... rest of start logic ...
```

### Step 4: Handle Memory Contiguity (Optional but Recommended)

**Add to `read()` before conversion:**
```python
# Ensure buffer is contiguous for cv2.cvtColor
if not frame_yuv.flags['C_CONTIGUOUS']:
    frame_yuv = np.ascontiguousarray(frame_yuv)
```

**Rationale:** ISP may use strided memory. `cv2.cvtColor` requires contiguous arrays.

---

## INTEGRATION POINTS

### Upstream Dependencies (Already Imported)

**Must Have Imports:**
```python
from typing import Tuple, Optional
import threading
import numpy as np
import cv2
from picamera2 import Picamera2
```

**New Import (if not present):**
```python
from pathlib import Path  # For log file paths
```

### Downstream Consumers

**VisionManager Expectations:**

1. **`start()` Return Value:**
   - `True` if camera initialized successfully
   - `False` if hardware unavailable or configuration failed
   - VisionManager sets `self.camera_active = result`

2. **`read()` Output Contract:**
   - **MUST** return BGR format (not RGB, not YUV)
   - Shape: `(height, width, 3)` - consistent with `start()` parameters
   - Dtype: `np.uint8`
   - VisionManager encodes this as JPEG for `/api/vision/stream`

3. **Thread Safety:**
   - `read()` called from `_frame_capture_loop()` background thread
   - Must handle concurrent calls gracefully (lock provided in contract)

---

## SUCCESS CRITERIA

### Functional Requirements

✅ **Camera Initializes:**
```bash
# Test command:
python3 -c "
from src.hardware.camera.csi_provider import CsiCameraProvider
cam = CsiCameraProvider()
assert cam.start(640, 480, 15) == True
print('✅ Initialization successful')
"
```

✅ **Frames are BGR:**
```bash
# Test command:
python3 -c "
from src.hardware.camera.csi_provider import CsiCameraProvider
cam = CsiCameraProvider()
cam.start(640, 480, 15)
success, frame = cam.read()
assert success == True
assert frame.shape == (480, 640, 3)
assert frame.dtype == np.uint8
print('✅ BGR conversion successful')
cam.stop()
"
```

✅ **High-Res Capture Works:**
```bash
# Test command:
python3 -c "
from src.hardware.camera.csi_provider import CsiCameraProvider
cam = CsiCameraProvider()
cam.start(640, 480, 15)
frame_hr = cam.picam2.capture_array('main')
assert frame_hr.shape == (1080, 1920, 3)
print('✅ Dual-stream functional')
cam.stop()
"
```

### Code Quality Requirements

✅ **Type Hints Complete:**
- Run `mypy src/hardware/camera/csi_provider.py --strict`
- Zero errors expected

✅ **Docstrings Present:**
- All public methods have Google-style docstrings
- Include Args, Returns, Raises sections

✅ **Line Count Compliance:**
- No function exceeds 50 lines
- If `read()` is too long, refactor conversion into `_convert_yuv_to_bgr()`

✅ **Imports Valid:**
- No wildcard imports (`from module import *`)
- All imports alphabetically sorted
- Standard library → Third party → Local

### Performance Requirements

✅ **Conversion Time:**
```bash
# Measure with:
python3 -c "
import time
from src.hardware.camera.csi_provider import CsiCameraProvider
cam = CsiCameraProvider()
cam.start(640, 480, 15)

times = []
for _ in range(100):
    t0 = time.perf_counter()
    success, frame = cam.read()
    t1 = time.perf_counter()
    if success:
        times.append((t1 - t0) * 1000)

avg_time = sum(times) / len(times)
print(f'Average conversion time: {avg_time:.2f}ms')
assert avg_time < 10, f'Conversion too slow: {avg_time}ms'
cam.stop()
"
```

Expected: < 10ms @ 640x480 on Pi 4B

---

## TESTING CHECKLIST

Before submitting for audit:

- [ ] Run `python3 src/hardware/camera/csi_provider.py` (no import errors)
- [ ] Test with physical Camera Module 3 attached
- [ ] Verify `/api/vision/stream` endpoint works in browser
- [ ] Verify `/api/vision/capture` returns 1920x1080 images
- [ ] Run `mypy` type checker
- [ ] Check function line counts (max 50)
- [ ] Validate docstrings are complete
- [ ] Test thread safety (concurrent `read()` calls)
- [ ] Test `stop()` idempotency (multiple calls)
- [ ] Measure frame acquisition time (< 10ms target)

---

## COMMON PITFALLS TO AVOID

### ❌ WRONG: Using RGB888 for lores stream
```python
# This will cause RuntimeError: lores stream must be YUV
config = self.picam2.create_preview_configuration(
    lores={"format": "RGB888"}  # ← FAILS
)
```

### ✅ CORRECT: Using YUV420 for lores stream
```python
config = self.picam2.create_preview_configuration(
    lores={"format": "YUV420"}  # ← WORKS
)
```

---

### ❌ WRONG: Incorrect conversion flag
```python
frame_bgr = cv2.cvtColor(frame_yuv, cv2.COLOR_YUV2BGR)  # Generic, may fail
```

### ✅ CORRECT: Specific I420 conversion
```python
frame_bgr = cv2.cvtColor(frame_yuv, cv2.COLOR_YUV2BGR_I420)  # Correct for YUV420
```

---

### ❌ WRONG: Ignoring shape validation
```python
frame_bgr = cv2.cvtColor(frame_yuv, cv2.COLOR_YUV2BGR_I420)  # May crash
```

### ✅ CORRECT: Validate shape first
```python
if frame_yuv.shape[0] != int(self._height * 1.5):
    return (False, None)
frame_bgr = cv2.cvtColor(frame_yuv, cv2.COLOR_YUV2BGR_I420)
```

---

### ❌ WRONG: Missing thread lock
```python
def read(self):
    frame = self.picam2.capture_array("lores")  # Race condition!
```

### ✅ CORRECT: Lock protected
```python
def read(self):
    with self._frame_lock:
        frame = self.picam2.capture_array("lores")
```

---

## DEBUG TIPS

### If initialization still fails:

1. **Check picamera2 version:**
   ```bash
   python3 -c "import picamera2; print(picamera2.__version__)"
   # Expected: >= 0.3.12
   ```

2. **Verify Camera Module 3 detection:**
   ```bash
   libcamera-hello --list-cameras
   # Should show: 0 : imx708 [4608x2592] (/base/soc/i2c0mux/i2c@1/imx708@1a)
   ```

3. **Test minimal YUV420 config:**
   ```python
   from picamera2 import Picamera2
   cam = Picamera2()
   config = cam.create_preview_configuration(
       main={"size": (1920, 1080), "format": "RGB888"},
       lores={"size": (640, 480), "format": "YUV420"}
   )
   cam.configure(config)
   cam.start()
   frame = cam.capture_array("lores")
   print(f"YUV shape: {frame.shape}")  # Should be (720, 640, 1)
   cam.stop()
   ```

### If conversion produces wrong colors:

**Symptoms:** Blue sky appears orange, skin tones greenish

**Cause:** Wrong conversion flag (e.g., using `YV12` instead of `I420`)

**Fix:** Verify flag is exactly `cv2.COLOR_YUV2BGR_I420`

**Verify conversion:**
```python
# Capture known color (e.g., blue paper)
success, frame = cam.read()
blue_pixel = frame[240, 320]  # Center pixel
print(f"BGR: {blue_pixel}")  # Should be [high, low, low] for blue
```

---

## REFERENCES

- **Contract:** `docs/contracts/csi_provider_yuv420_fix.md` v1.0
- **Investigation:** `docs/specs/14_csi_error_investigation.md`
- **Base Class:** `src/hardware/camera/base.py` (CameraProvider ABC)
- **API Map:** `docs/API_MAP_LITE.md` (Section 5: Camera HAL Layer)
- **Picamera2 Docs:** https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
- **OpenCV Color Codes:** https://docs.opencv.org/4.x/d8/d01/group__imgproc__color__conversions.html

---

## FINAL NOTES

This fix is CRITICAL for the vision system to function. The investigation has already determined that **Approach A (YUV420 Compliance)** is the correct path. Do not deviate from this solution.

**Estimated Timeline:**
- Implementation: 1-2 hours
- Testing: 1 hour
- Documentation: 30 minutes
- **Total: 2.5-3.5 hours**

**Auditor will verify:**
1. Contract signatures match exactly
2. All test cases pass
3. Code quality standards met
4. Performance requirements achieved

**Questions?** Refer back to the contract document for detailed specifications.

---

**Status:** Ready for implementation
**Next Step:** Implement changes in `src/hardware/camera/csi_provider.py`
**Auditor Contact:** TBD