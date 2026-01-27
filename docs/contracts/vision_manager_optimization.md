# CONTEXT VERIFICATION

✅ **Context verified. Proceeding.**

**Received Files:**
- `vision_performance.md` (Feature Specification)
- `vision_manager.py` (Current Implementation)
- `system_style.md` (Style Guide)

---

# CONTRACT: Vision Manager (Dual-Tier Optimization)
**Version:** 1.1  
**Last Updated:** 2025-05-15  
**Status:** Draft  
**Module:** `src/services/vision_manager.py`

---

## 1. PURPOSE

The Vision Manager provides dual-tier video processing: a high-resolution capture pipeline (640x480 @ 30fps) for OCR accuracy, and a bandwidth-optimized streaming pipeline (320x240 @ 15fps) for remote operator navigation. This architecture reduces stream bandwidth by ~70% while maintaining backend analysis quality.

---

## 2. PUBLIC INTERFACE

### Method: `start_capture`

**Signature:**
```python
def start_capture(
    self,
    width: int = 640,
    height: int = 480,
    fps: int = 30
) -> bool:
    """Initialize camera and start the capture thread at Master Resolution.
    
    The Master Resolution (640x480) is MANDATORY for OCR accuracy. While parameters
    are configurable for compatibility, the system is optimized for this resolution.
    
    Args:
        width: Desired frame width. Default 640 (Master Resolution).
        height: Desired frame height. Default 480 (Master Resolution).
        fps: Desired frames per second. Default 30 (Master Capture Rate).
    
    Returns:
        True if camera opened successfully and capture thread started.
        False if no camera device found.
    
    Raises:
        ValueError: If width/height/fps outside valid ranges.
        RuntimeError: If capture already running.
    """
```

**Behavior Specification:**

- **Input Validation:**
  - `width`: Must be > 0 and <= 1920
  - `height`: Must be > 0 and <= 1080
  - `fps`: Must be > 0 and <= 60
  - Raise `ValueError` if any parameter fails validation

- **Processing Logic:**
  1. Check if capture thread already alive → Raise `RuntimeError`
  2. Iterate camera indices 0-9
  3. For each index: Attempt `cv2.VideoCapture(index)`
  4. Test with `.read()` to verify functional camera
  5. Configure `CAP_PROP_FRAME_WIDTH`, `CAP_PROP_FRAME_HEIGHT`, `CAP_PROP_FPS`
  6. Spawn daemon thread running `_capture_loop()`
  7. Return `True` on first success, `False` if all indices fail

- **Output Guarantee:**
  - Returns `bool` indicating camera initialization success
  - On success: Background thread continuously populates `self.current_frame`

- **Side Effects:**
  - Sets `self.stream` (cv2.VideoCapture object)
  - Sets `self.camera_index` (int)
  - Sets `self.stopped = False`
  - Starts `self.capture_thread` (daemon thread)

**Error Handling:**

- **Invalid Parameters:** Raise `ValueError("Invalid camera parameters: width, height, fps must be positive")`
- **Capture Already Running:** Raise `RuntimeError("Capture already started. Call stop_capture() first.")`
- **No Camera Found:** Return `False` (not an exception)

**Performance Requirements:**

- Time Complexity: O(n) where n = camera index scan range (max 10)
- Space Complexity: O(1)

---

### Method: `get_frame`

**Signature:**
```python
def get_frame(self) -> Optional[np.ndarray]:
    """Retrieve the latest captured frame at FULL RESOLUTION.
    
    This method returns the unmodified 640x480 frame for high-quality processing
    tasks such as OCR analysis. No downscaling is applied.
    
    Returns:
        A copy of the latest numpy array frame (640x480), or None if unavailable.
    """
```

**Behavior Specification:**

- **Input Validation:** None required

- **Processing Logic:**
  1. Acquire `self.frame_lock`
  2. Check if `self.current_frame` is None
  3. If None: Return None
  4. If exists: Create deep copy via `.copy()`
  5. Release lock
  6. Return copied frame

- **Output Guarantee:**
  - Returns **Full Resolution** frame (640x480 @ original quality)
  - Returns `None` if no frame captured yet
  - Returned array is a **copy**, safe for caller modification

- **Side Effects:** None (read-only operation)

**Error Handling:**

- No exceptions raised (returns None on unavailable frame)

**Performance Requirements:**

- Time Complexity: O(w × h) for frame copy
- Space Complexity: O(w × h) for copied frame array

---

### Method: `generate_mjpeg`

**Signature:**
```python
def generate_mjpeg(self, quality: int = 40) -> Generator[bytes, None, None]:
    """Generate a bandwidth-optimized MJPEG stream for HTTP transmission.
    
    This method implements the Low-Resolution Stream Path:
    - Downscales frames from 640x480 to 320x240 (75% pixel reduction)
    - Compresses with JPEG quality 40 (vs. original 80)
    - Throttles to 15 FPS (vs. 30 FPS capture rate)
    
    Target: ~70% bandwidth reduction while maintaining navigation clarity.
    
    Args:
        quality: JPEG compression quality (1-100). Default 40 for optimization.
    
    Yields:
        Bytes formatted as multipart/x-mixed-replace HTTP stream.
    
    Raises:
        ValueError: If quality not between 1 and 100.
    """
```

**Behavior Specification:**

- **Input Validation:**
  - `quality`: Must be 1 <= quality <= 100
  - Raise `ValueError` if out of range

- **Processing Logic (CRITICAL OPTIMIZATION PATH):**
  1. Call `self.get_frame()` to retrieve 640x480 frame
  2. **If frame is None:** Sleep 0.1s and continue (prevents busy loop)
  3. **Downscale:** `cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)`
  4. **Encode:** `cv2.imencode('.jpg', resized_frame, [cv2.IMWRITE_JPEG_QUALITY, quality])`
  5. **Format:** Prepend multipart headers: `b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'`
  6. **Yield:** Complete frame bytes with trailing `b'\r\n'`
  7. **Throttle:** `time.sleep(0.066)` to achieve ~15 FPS

- **Output Guarantee:**
  - Yields infinite stream of JPEG-encoded frames
  - Each frame is 320x240 resolution
  - Stream rate: ~15 FPS (66ms per frame)

- **Side Effects:**
  - Continuous CPU usage for resize/encode operations
  - Blocks generator consumer at 15 FPS rate

**Error Handling:**

- **Invalid Quality:** Raise `ValueError("JPEG quality must be between 1 and 100")`
- **Encoding Failure:** Silently skip frame (no yield) and continue loop

**Performance Requirements:**

- Time Complexity: O(w × h) per frame (resize + encode)
- Space Complexity: O(w × h) for temporary resized frame
- **Lock Contention Minimized:** Frame copy occurs via `get_frame()`, lock released before resize

---

### Method: `stop_capture`

**Signature:**
```python
def stop_capture(self) -> None:
    """Stop the capture thread and release camera resources.
    
    Safely terminates background thread and cleans up OpenCV resources.
    Idempotent: safe to call multiple times.
    """
```

**Behavior Specification:**

- **Input Validation:** None required

- **Processing Logic:**
  1. Check `self.stopped` flag (return early if already stopped)
  2. Set `self.stopped = True`
  3. Join `self.capture_thread` with 2.0s timeout
  4. Call `self.stream.release()`
  5. Set `self.stream = None`
  6. Acquire `self.frame_lock` and set `self.current_frame = None`
  7. Set `self.camera_index = None`

- **Output Guarantee:**
  - Capture thread terminated
  - Camera hardware released
  - All instance state reset

- **Side Effects:**
  - Stops background thread
  - Releases camera device
  - Clears frame buffer

**Error Handling:**

- No exceptions raised (graceful cleanup)

**Performance Requirements:**

- Time Complexity: O(1)
- Space Complexity: O(1)

---

### Method: `_capture_loop` (Internal)

**Signature:**
```python
def _capture_loop(self) -> None:
    """Internal loop running in a separate thread to capture frames.
    
    Continuously reads from camera at Master Resolution (640x480 @ 30fps)
    and updates shared frame buffer under lock protection.
    """
```

**Behavior Specification:**

- **Processing Logic:**
  1. Initialize `consecutive_failures = 0`
  2. Loop while `not self.stopped`:
     - Call `self.stream.read()`
     - If success: Update `self.current_frame` under lock, reset failure counter
     - If failure: Increment failure counter
     - If `consecutive_failures > 10`: Break loop (safety exit)
     - Sleep 0.001s (1ms) to prevent CPU saturation

- **Output Guarantee:**
  - `self.current_frame` contains latest capture
  - Loop exits on stop flag or persistent camera failure

- **Side Effects:**
  - Continuous background processing
  - Updates shared state under lock

**Error Handling:**

- Graceful exit on 10 consecutive read failures
- No exceptions propagated to main thread

**Performance Requirements:**

- Time Complexity: O(∞) (continuous loop)
- Space Complexity: O(1) (single frame buffer)

---

## 3. DEPENDENCIES

**This module CALLS:**

- `cv2.VideoCapture(index)` - Camera initialization
- `cv2.imencode()` - JPEG compression
- `cv2.resize()` - Frame downscaling for stream optimization
- `threading.Thread()` - Background capture loop
- `threading.Lock()` - Thread-safe frame access

**This module is CALLED BY:**

- `src/api/server.py::start_capture()` - Initialize camera on system boot
- `src/api/server.py::/api/vision/stream` - Consume `generate_mjpeg()` for HTTP stream
- `src/api/server.py::/api/vision/scan` - Retrieve full-resolution frame via `get_frame()`
- `src/services/ocr_service.py` (assumed) - High-quality frame analysis

---

## 4. DATA STRUCTURES

### Class Attributes

```python
stream: Optional[cv2.VideoCapture]  # OpenCV camera object
frame_lock: threading.Lock           # Protects current_frame access
current_frame: Optional[np.ndarray]  # Latest captured frame (640x480)
stopped: bool                        # Thread termination flag
camera_index: Optional[int]          # Active camera device index
capture_thread: Optional[threading.Thread]  # Background capture thread
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

### From `system_style.md`:

1. **Type Hinting:** Required for all function signatures and class attributes ✅
2. **Error Handling:** Use specific exceptions; avoid generic `except Exception` ✅
3. **Documentation:** Google-style Docstrings mandatory ✅
4. **File Header:** Must include PS_RCS_PROJECT copyright header ✅

### From `vision_performance.md`:

1. **Master Resolution:** 640x480 capture is NON-NEGOTIABLE for OCR accuracy
2. **Stream Optimization:** 320x240 @ Q40 @ 15fps for 70% bandwidth reduction
3. **Lock Minimization:** Copy frame reference, release lock, THEN resize/encode
4. **Single Client:** System assumes single remote operator (no multi-client optimization needed)

---

## 6. MEMORY COMPLIANCE

**No `_memory_snippet.txt` provided. Proceeding without additional memory rules.**

---

## 7. ACCEPTANCE CRITERIA

### Test Case 1: Successful Initialization
- **Input:** `vision_manager.start_capture(640, 480, 30)`
- **Expected Output:** `True`
- **Expected Behavior:**
  - Camera device found and opened
  - Capture thread spawned and alive
  - `get_frame()` returns 640x480 numpy array within 1 second

### Test Case 2: Invalid Parameters
- **Input:** `vision_manager.start_capture(0, 0, 0)`
- **Expected Exception:** `ValueError`
- **Expected Message:** `"Invalid camera parameters: width, height, fps must be positive"`

### Test Case 3: Dual Capture Attempt
- **Input:** Call `start_capture()` twice without `stop_capture()`
- **Expected Exception:** `RuntimeError`
- **Expected Message:** `"Capture already started. Call stop_capture() first."`

### Test Case 4: Stream Bandwidth Optimization
- **Input:** `generate_mjpeg(quality=40)` after successful capture
- **Expected Output:** Generator yielding frames
- **Expected Behavior:**
  - Each yielded frame is ~75% smaller than full-res equivalent
  - Frame rate stabilizes at ~15 FPS (66ms intervals)
  - Frames are 320x240 resolution when decoded

### Test Case 5: High-Res Frame Isolation
- **Input:** `get_frame()` called during active streaming
- **Expected Output:** 640x480 numpy array
- **Expected Behavior:**
  - Frame dimensions are (480, 640, 3)
  - Frame is independent copy (modifying it doesn't affect stream)
  - No downscaling applied

### Test Case 6: Invalid JPEG Quality
- **Input:** `generate_mjpeg(quality=150)`
- **Expected Exception:** `ValueError`
- **Expected Message:** `"JPEG quality must be between 1 and 100"`

### Test Case 7: Graceful Cleanup
- **Input:** `stop_capture()` after successful capture
- **Expected Output:** None
- **Expected Behavior:**
  - Capture thread terminates within 2 seconds
  - `get_frame()` returns `None`
  - Camera device released (accessible by other processes)

---

# WORK ORDER FOR IMPLEMENTER

**Target File:** `src/services/vision_manager.py`  
**Contract Reference:** `docs/contracts/vision_manager.md` v1.1

## Strict Constraints (NON-NEGOTIABLE)

1. **Master Resolution Lock:** Camera MUST capture at 640x480. This is the OCR quality guarantee.
2. **Stream Downscaling:** `generate_mjpeg()` MUST resize to 320x240 before encoding.
3. **Compression Target:** Default JPEG quality MUST be 40 (not 80).
4. **FPS Throttle:** Stream loop MUST sleep 0.066s (~15 FPS, not 30 FPS).
5. **Lock Discipline:** Frame copy must occur BEFORE resize operation to minimize contention.

## Memory Compliance (MANDATORY)

_No memory rules provided in this context._

## Required Logic Updates

### 1. `start_capture()` Documentation
- Update docstring to emphasize "Master Resolution" requirement for OCR
- Clarify that default parameters (640, 480, 30) are optimized values

### 2. `get_frame()` Documentation
- Add explicit statement: "Returns FULL RESOLUTION frame (no downscaling)"
- Emphasize this is the OCR analysis path

### 3. `generate_mjpeg()` Core Logic
```python
# STEP 1: Get full-res frame (lock released by get_frame)
frame = self.get_frame()
if frame is None:
    time.sleep(0.1)
    continue

# STEP 2: Downscale (lock already released - no contention)
resized = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)

# STEP 3: Encode with optimized quality
ret, jpeg = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, quality])

# STEP 4: Yield if successful
if ret:
    jpeg_bytes = jpeg.tobytes()
    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n'

# STEP 5: Throttle to 15 FPS
time.sleep(0.066)  # Changed from 0.033 (30 FPS)
```

### 4. Default Parameter Change
```python
def generate_mjpeg(self, quality: int = 40) -> Generator[bytes, None, None]:
    # Changed from quality=80 to quality=40
```

## Integration Points

- **Must preserve compatibility with:** `src/api/server.py`
- **Stream endpoint** (`/api/vision/stream`): Consumes optimized generator
- **Scan endpoint** (`/api/vision/scan`): Retrieves full-res via `get_frame()`

## Success Criteria

1. All method signatures match contract exactly
2. Docstrings follow Google style (as per `system_style.md`)
3. Stream bandwidth reduced by ~70% (measure via browser network tools)
4. OCR accuracy unchanged (verify with test images)
5. Browser achieves stable 15 FPS (no frame drops)
6. Type hints present on all signatures

---

# POST-ACTION REPORT

✅ **Contract Created:** `docs/contracts/vision_manager.md` (v1.1)  
📋 **Work Order Generated** for Implementer  
🎯 **Key Changes:**
   - Master Resolution enforcement (640x480 for OCR)
   - Stream downscaling to 320x240
   - JPEG quality reduction to 40
   - FPS throttle to 15 (0.066s sleep)
   - Lock contention minimization

🔍 **Next Verification Command:**
```
/verify-context: system_style.md, contracts/vision_manager.md, vision_manager.py
```

👉 **Next Agent:** Implementer (`AGENTS/02_implementer.md`)

---

**ARCHITECT SIGNATURE:** Contract v1.1 APPROVED for implementation.  
**Immutability Notice:** These interfaces are now FROZEN. Any deviations require Architect re-approval.