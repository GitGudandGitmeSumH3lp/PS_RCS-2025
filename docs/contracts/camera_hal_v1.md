# CONTRACT: Camera Hardware Abstraction Layer (HAL)
**Version:** 1.0
**Last Updated:** 2026-02-07
**Status:** Draft

## 1. PURPOSE

This contract defines the Camera Hardware Abstraction Layer (HAL) that decouples the `VisionManager` service from specific camera hardware implementations. The HAL enables seamless switching between USB webcams (via OpenCV) and Raspberry Pi Camera Module 3 (via picamera2) through a unified interface, ensuring backward compatibility while supporting future hardware expansion.

## 2. PUBLIC INTERFACE

### Abstract Base Class: `CameraProvider`

**Location:** `src/hardware/camera/base.py`

#### Method: `start`

**Signature:**
```python
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np

class CameraProvider(ABC):
    @abstractmethod
    def start(self, width: int, height: int, fps: int) -> bool:
        """Initialize camera hardware with specified parameters.
        
        Args:
            width: Capture width in pixels (1-3840).
            height: Capture height in pixels (1-2160).
            fps: Capture framerate (1-120).
        
        Returns:
            True if camera successfully initialized and ready for reads.
            False if initialization failed (hardware unavailable/busy).
        
        Raises:
            ValueError: If parameters outside valid ranges.
            RuntimeError: If start() called when already running.
        
        Thread Safety:
            Must be called from main thread only.
            Must complete before any read() calls.
        """
        pass
```

**Behavior Specification:**

- **Input Validation:**
  - `1 <= width <= 3840` (Standard HD to 4K UHD range)
  - `1 <= height <= 2160` (Standard HD to 4K UHD range)
  - `1 <= fps <= 120` (Standard camera range)
  - Raise `ValueError` with descriptive message if violated
  
- **Processing Logic:**
  1. Verify camera hardware is available (not already in use)
  2. Negotiate hardware capabilities (format, resolution, framerate)
  3. Complete hardware handshake (driver-specific sequence)
  4. Validate successful frame acquisition (test read)
  
- **Output Guarantee:**
  - `True`: Camera is streaming and `read()` will succeed
  - `False`: Initialization failed, hardware unavailable
  
- **Side Effects:**
  - Acquires exclusive lock on camera device
  - Initializes internal buffers
  - May create background threads (implementation-specific)

**Error Handling:**

- **Case 1:** Invalid parameters → Raise `ValueError("Parameter {param} must be between {min} and {max}, got {value}")`
- **Case 2:** Already running → Raise `RuntimeError("Camera already started. Call stop() first.")`
- **Case 3:** Hardware unavailable → Return `False` (not an exception)
- **Case 4:** Initialization timeout → Return `False` after cleanup

**Performance Requirements:**

- Time Complexity: O(1) - constant time hardware negotiation
- Space Complexity: O(1) - fixed buffer allocation
- Max Initialization Time: 2 seconds

---

#### Method: `read`

**Signature:**
```python
@abstractmethod
def read(self) -> Tuple[bool, Optional[np.ndarray]]:
    """Acquire the next available frame from camera.
    
    Returns:
        Tuple of (success, frame):
            - success (bool): True if frame acquired successfully
            - frame (Optional[np.ndarray]): BGR image array or None on failure
                Shape: (height, width, 3) with dtype=uint8
    
    Thread Safety:
        Safe to call from background capture thread.
        Must not be called before start() returns True.
        Must not be called after stop() completes.
    """
    pass
```

**Behavior Specification:**

- **Input Validation:**
  - No input parameters
  - Must verify `start()` was successful before calling
  
- **Processing Logic:**
  1. Block until next frame available (driver-dependent timing)
  2. Acquire frame from hardware buffer
  3. Convert to BGR format (OpenCV standard)
  4. Validate frame integrity (non-zero dimensions, correct dtype)
  
- **Output Guarantee:**
  - Success case: `(True, np.ndarray)` with shape `(H, W, 3)` and `dtype=uint8`
  - Failure case: `(False, None)`
  - **CRITICAL:** Frame must always be in BGR format regardless of hardware
  
- **Side Effects:**
  - Advances internal frame buffer pointer
  - May drop frames if reader is slower than producer

**Error Handling:**

- **Case 1:** Hardware disconnected → Return `(False, None)` gracefully
- **Case 2:** Frame corruption → Return `(False, None)` and log error
- **Case 3:** Not started → Return `(False, None)` (defensive, not exception)
- **Case 4:** Timeout → Return `(False, None)` after max wait period

**Performance Requirements:**

- Time Complexity: O(1) - direct buffer access
- Space Complexity: O(1) - single frame allocation
- Blocking Time: Max 1/fps seconds (driver-dependent)

---

#### Method: `stop`

**Signature:**
```python
@abstractmethod
def stop(self) -> None:
    """Release camera hardware and cleanup resources.
    
    Idempotent: Safe to call multiple times.
    Blocking: Waits for in-flight reads to complete.
    
    Raises:
        No exceptions. All errors handled internally with logging.
    
    Thread Safety:
        Safe to call from any thread.
        Blocks until capture thread terminates (if exists).
        Subsequent read() calls will return (False, None).
    """
    pass
```

**Behavior Specification:**

- **Input Validation:**
  - No input parameters
  - No preconditions (idempotent design)
  
- **Processing Logic:**
  1. Signal any background threads to terminate
  2. Wait for threads to complete (with timeout)
  3. Release hardware lock
  4. Free internal buffers
  5. Reset state to "not started"
  
- **Output Guarantee:**
  - Camera device is released for other processes
  - All internal resources deallocated
  - Object ready for restart via `start()`
  
- **Side Effects:**
  - Terminates background threads (if any)
  - Invalidates any cached frames
  - Releases OS-level device handle

**Error Handling:**

- **Case 1:** Already stopped → No-op (idempotent)
- **Case 2:** Thread won't terminate → Force kill after 2s timeout
- **Case 3:** Hardware release fails → Log error but don't raise
- **Case 4:** Memory cleanup fails → Log error but don't raise

**Performance Requirements:**

- Time Complexity: O(1) - fixed cleanup sequence
- Space Complexity: O(1) - no allocation during cleanup
- Max Termination Time: 2.5 seconds (thread join + cleanup)

---

### Factory Function: `get_camera_provider`

**Location:** `src/hardware/camera/factory.py`

**Signature:**
```python
from typing import Optional
from .base import CameraProvider

def get_camera_provider(
    interface: Optional[str] = None
) -> CameraProvider:
    """Factory function to instantiate appropriate camera provider.
    
    Args:
        interface: Override for CAMERA_INTERFACE env var.
            Valid values: 'usb', 'csi', 'auto', None.
            If None, reads from environment (default: 'auto').
    
    Returns:
        CameraProvider instance (UsbCameraProvider or CsiCameraProvider).
    
    Raises:
        ValueError: If interface is invalid string.
        ImportError: If required provider unavailable (only if forced).
    
    Selection Logic (when interface='auto'):
        1. If picamera2 available, try CsiCameraProvider()
        2. If CSI initialization fails, fallback to UsbCameraProvider()
        3. If USB initialization fails, raise ImportError
    """
    pass
```

**Behavior Specification:**

- **Input Validation:**
  - If `interface` provided: must be in `{'usb', 'csi', 'auto'}`
  - If invalid: Raise `ValueError("CAMERA_INTERFACE must be 'usb', 'csi', or 'auto'")`
  
- **Processing Logic:**
  1. Determine interface mode (parameter > env var > default 'auto')
  2. Check provider availability (try imports)
  3. Instantiate and return provider instance
  
- **Output Guarantee:**
  - Returns concrete `CameraProvider` implementation
  - Instance is NOT started (caller must call `start()`)
  
- **Side Effects:**
  - Loads provider module (import side effects)
  - No hardware acquisition (happens in `start()`)

**Error Handling:**

- **Case 1:** `interface='csi'` but picamera2 unavailable → Raise `ImportError("picamera2 not available. Install via: sudo apt install python3-picamera2")`
- **Case 2:** `interface='auto'` and all providers fail → Raise `ImportError("No camera providers available")`
- **Case 3:** Invalid interface string → Raise `ValueError` with valid options

**Performance Requirements:**

- Time Complexity: O(1) - simple instantiation
- Space Complexity: O(1) - single object allocation

---

## 3. DEPENDENCIES

### This module CALLS:

- `cv2.VideoCapture()` - USB provider hardware interface
- `cv2.cvtColor()` - Format conversion (CSI provider only)
- `Picamera2` - CSI provider hardware interface (optional import)
- `os.getenv()` - Configuration retrieval
- `threading.Lock()` - Thread safety primitives

### This module is CALLED BY:

- `VisionManager.start_capture()` - Service layer initialization
- `VisionManager._capture_loop()` - Background frame acquisition

---

## 4. DATA STRUCTURES

### Exception Classes

```python
class CameraError(Exception):
    """Base exception for camera-related errors."""
    pass

class CameraInitializationError(CameraError):
    """Raised when camera hardware cannot be initialized."""
    pass

class CameraConfigurationError(CameraError):
    """Raised when configuration parameters are invalid."""
    pass
```

### Configuration Dataclass

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CameraConfig:
    """Immutable camera configuration."""
    interface: str  # 'usb', 'csi', or 'auto'
    width: int
    height: int
    fps: int
    
    def __post_init__(self) -> None:
        """Validate configuration on creation."""
        if self.interface not in {'usb', 'csi', 'auto'}:
            raise ValueError(f"Invalid interface: {self.interface}")
        if not (1 <= self.width <= 3840):
            raise ValueError(f"Invalid width: {self.width}")
        if not (1 <= self.height <= 2160):
            raise ValueError(f"Invalid height: {self.height}")
        if not (1 <= self.fps <= 120):
            raise ValueError(f"Invalid fps: {self.fps}")
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

### From `system_constraints.md`:

1. **Concurrency Model:**
   - Use `threading` only (no `asyncio`)
   - All hardware interfaces must be thread-safe
   - Background threads must be daemon threads

2. **Code Quality:**
   - Max function length: 50 lines (refactor if longer)
   - Type hints mandatory for all signatures
   - Google-style docstrings required

3. **Hardware Abstraction:**
   - No hardware library imports outside providers
   - Service layer must remain hardware-agnostic
   - All hardware failures must be recoverable (no crashes)

4. **Error Handling:**
   - No generic `except Exception` (use specific types)
   - Hardware errors must not propagate to Flask routes
   - All resources must be released in `stop()` (no leaks)

---

## 6. MEMORY COMPLIANCE

**Applied Rules:**

- **2026-02-07 | Stream Lifecycle Management:**
  - Camera streams must start only when needed (on-demand)
  - Streams must stop when inactive (bandwidth optimization)
  - Contract ensures `stop()` is idempotent for safe lifecycle management

- **2026-02-06 | Hardware Abstraction:**
  - All hardware-specific code isolated in providers
  - VisionManager remains hardware-agnostic
  - Factory pattern enables runtime hardware switching

---

## 7. THREAD SAFETY GUARANTEES

### USB Provider (`UsbCameraProvider`):

**Thread Safety Strategy:** OpenCV's Internal Locking

- **`start()` Thread Safety:**
  - MUST be called from main thread only
  - NOT thread-safe (single-writer assumption)
  - Raises `RuntimeError` if called while running
  
- **`read()` Thread Safety:**
  - Thread-safe via OpenCV's internal locks
  - Safe for background capture thread
  - Multiple readers NOT supported (undefined behavior)
  
- **`stop()` Thread Safety:**
  - Thread-safe (can be called from any thread)
  - Blocks until resources released
  - Idempotent (safe to call multiple times)

**Concurrency Model:**
```
Main Thread: VisionManager.__init__() → get_camera_provider() → provider.start()
                                    ↓
Capture Thread: while not stopped: provider.read() → store frame
                                    ↓
Any Thread: provider.stop() → signal stop → join capture thread
```

---

### CSI Provider (`CsiCameraProvider`):

**Thread Safety Strategy:** Explicit Locking + Main Thread Constraint

- **`start()` Thread Safety:**
  - MUST be called from main thread only (picamera2 requirement)
  - Protected by initialization lock
  - Raises `RuntimeError` if called while running
  
- **`read()` Thread Safety:**
  - Safe to call from capture thread
  - `capture_array()` is blocking and internally synchronized
  - Single reader only (picamera2 limitation)
  
- **`stop()` Thread Safety:**
  - Thread-safe via explicit lock
  - Safe to call from any thread
  - Idempotent

**Critical picamera2 Constraints:**

1. **Initialization Constraint:**
   ```python
   # MUST happen in main thread
   picam2 = Picamera2()
   picam2.configure(...)
   picam2.start()
   ```

2. **Capture Constraint:**
   ```python
   # Safe in ANY thread after start()
   frame = picam2.capture_array("lores")
   ```

3. **Shutdown Constraint:**
   ```python
   # Thread-safe with lock protection
   with self.lock:
       picam2.stop()
       picam2.close()
   ```

**Concurrency Model:**
```
Main Thread: VisionManager.__init__() → get_camera_provider()
                                    ↓
Main Thread: provider.start() → Picamera2() → configure() → start()
                                    ↓
Capture Thread: while not stopped: provider.read() → capture_array() → cvtColor()
                                    ↓
Any Thread: provider.stop() → with lock: stop() → close()
```

---

### VisionManager Integration Contract:

**Threading Rules:**

1. **Initialization Sequence (Main Thread):**
   ```python
   manager = VisionManager()  # Main thread
   manager.start_capture(640, 480, 30)  # Calls provider.start() in main thread
   ```

2. **Capture Loop (Background Daemon Thread):**
   ```python
   def _capture_loop(self):
       while not self.stopped:
           ret, frame = self.provider.read()  # Thread-safe
           if ret:
               with self.frame_lock:
                   self.current_frame = frame
   ```

3. **Shutdown Sequence (Any Thread):**
   ```python
   manager.stop_capture()  # Can be called from any thread
   # → Signals background thread to stop
   # → Joins thread (blocks max 2.0s)
   # → Calls provider.stop()
   ```

---

## 8. CONFIGURATION SCHEMA

### Environment Variables

**Location:** `src/core/config.py` or `.env` file

| Variable | Type | Valid Values | Default | Required |
|----------|------|--------------|---------|----------|
| `CAMERA_INTERFACE` | str | `'usb'`, `'csi'`, `'auto'` | `'auto'` | No |
| `CAMERA_WIDTH` | int | `1-3840` | `640` | No |
| `CAMERA_HEIGHT` | int | `1-2160` | `480` | No |
| `CAMERA_FPS` | int | `1-120` | `30` | No |

**Validation Rules:**

```python
def validate_camera_config() -> CameraConfig:
    """Load and validate camera configuration from environment.
    
    Returns:
        CameraConfig instance with validated parameters.
    
    Raises:
        CameraConfigurationError: If any parameter invalid.
    """
    interface = os.getenv('CAMERA_INTERFACE', 'auto').lower()
    
    try:
        width = int(os.getenv('CAMERA_WIDTH', '640'))
        height = int(os.getenv('CAMERA_HEIGHT', '480'))
        fps = int(os.getenv('CAMERA_FPS', '30'))
    except ValueError as e:
        raise CameraConfigurationError(f"Invalid numeric config: {e}")
    
    return CameraConfig(
        interface=interface,
        width=width,
        height=height,
        fps=fps
    )
```

**Runtime Override:**

The factory accepts optional `interface` parameter to override environment:

```python
# Force USB mode (ignore environment)
provider = get_camera_provider(interface='usb')

# Use environment configuration
provider = get_camera_provider()  # Reads CAMERA_INTERFACE
```

---

## 9. ERROR HANDLING PROTOCOL

### Error Classification

| Error Type | When Raised | Handler Response |
|------------|-------------|------------------|
| `ValueError` | Invalid parameters to `start()` | Log error, return False to caller |
| `RuntimeError` | `start()` called while running | Log error, return False to caller |
| `ImportError` | Required provider unavailable | Log error, try fallback provider |
| `CameraInitializationError` | Hardware negotiation failed | Log error, return False from `start()` |
| `OSError` | Device disconnected during read | Log error, return `(False, None)` |

### Failure Modes and Recovery

**Mode 1: Initialization Failure**

```python
# Scenario: start() returns False
provider = get_camera_provider()
if not provider.start(640, 480, 30):
    # Recovery: Log error, retry with different provider
    logger.error("Camera initialization failed")
    # System continues without camera
    # API routes return 503 Service Unavailable
```

**Mode 2: Runtime Disconnection**

```python
# Scenario: USB cable unplugged during operation
while not stopped:
    ret, frame = provider.read()
    if not ret:
        consecutive_failures += 1
        if consecutive_failures > 10:
            # Recovery: Stop provider, notify system
            provider.stop()
            self.stopped = True
            logger.error("Camera disconnected")
            break
```

**Mode 3: Configuration Error**

```python
# Scenario: Invalid environment variable
try:
    config = validate_camera_config()
except CameraConfigurationError as e:
    # Recovery: Use default configuration
    logger.warning(f"Config error: {e}, using defaults")
    config = CameraConfig('auto', 640, 480, 30)
```

**Mode 4: Provider Unavailability**

```python
# Scenario: picamera2 not installed, CAMERA_INTERFACE='csi'
try:
    provider = get_camera_provider(interface='csi')
except ImportError as e:
    # Recovery: Fallback to USB
    logger.warning(f"CSI unavailable: {e}, falling back to USB")
    provider = get_camera_provider(interface='usb')
```

### Logging Requirements

All providers must log:

- **INFO:** Successful initialization with hardware details
- **WARNING:** Fallback to alternate provider
- **ERROR:** Hardware failures, disconnections
- **DEBUG:** Frame acquisition statistics (every 100 frames)

Example log output:
```
[2026-02-07 14:32:10] INFO [CsiCameraProvider] Camera initialized: IMX708 640x480@30fps
[2026-02-07 14:32:45] ERROR [CsiCameraProvider] Frame read failed: timeout
[2026-02-07 14:32:45] INFO [CsiCameraProvider] Camera stopped, releasing resources
```

---

## 10. MIGRATION STRATEGY

### Phase 1: Preparation (No Code Changes)

**Duration:** 1 day

1. Create `src/hardware/camera/` package directory
2. Review existing `VisionManager` tests (if any)
3. Document current USB camera behavior
4. Verify Pi Camera Module 3 hardware connectivity

**Rollback:** N/A (no changes made)

---

### Phase 2: Provider Implementation (Isolated)

**Duration:** 2 days

1. Implement `src/hardware/camera/base.py` (CameraProvider ABC)
2. Implement `src/hardware/camera/usb_provider.py` (port existing logic)
3. Implement `src/hardware/camera/csi_provider.py` (new picamera2 logic)
4. Implement `src/hardware/camera/factory.py`
5. Unit test each provider in isolation

**Testing Strategy:**
```bash
# Test USB provider (on any system with webcam)
CAMERA_INTERFACE=usb python3 -m pytest tests/hardware/camera/test_usb_provider.py

# Test CSI provider (on Pi 4B only)
CAMERA_INTERFACE=csi python3 -m pytest tests/hardware/camera/test_csi_provider.py
```

**Rollback:** Delete `src/hardware/camera/` package (VisionManager unchanged)

---

### Phase 3: VisionManager Refactor (Breaking Change)

**Duration:** 1 day

1. **Backup Current VisionManager:**
   ```bash
   cp src/services/vision_manager.py src/services/vision_manager.py.backup
   ```

2. **Refactor VisionManager:**
   - Replace `self.stream: cv2.VideoCapture` with `self.provider: CameraProvider`
   - Update `start_capture()` to use `get_camera_provider()`
   - Update `_capture_loop()` to use `self.provider.read()`
   - Update `stop_capture()` to use `self.provider.stop()`

3. **Preserve Public API:**
   ```python
   # THESE MUST NOT CHANGE
   def start_capture(self, width: int = 640, height: int = 480, fps: int = 30) -> bool
   def get_frame(self) -> Optional[np.ndarray]
   def generate_mjpeg(self, quality: int = 40) -> Generator[bytes, None, None]
   def stop_capture(self) -> None
   ```

**Testing Strategy:**
```bash
# Integration test (USB mode)
CAMERA_INTERFACE=usb python3 -m pytest tests/services/test_vision_manager.py

# Integration test (CSI mode, Pi 4B only)
CAMERA_INTERFACE=csi python3 -m pytest tests/services/test_vision_manager.py
```

**Rollback:**
```bash
# Restore backup
cp src/services/vision_manager.py.backup src/services/vision_manager.py
```

---

### Phase 4: System Integration Testing

**Duration:** 1 day

1. **Test OCR Pipeline:**
   - Verify OCR scanner modal works with USB camera
   - Verify OCR scanner modal works with CSI camera
   - Verify stream quality and performance

2. **Test Dashboard:**
   - Verify live stream renders correctly
   - Verify capture feature works
   - Verify theme toggle doesn't break stream

3. **Test Edge Cases:**
   - Camera disconnect during operation
   - Multiple rapid start/stop cycles
   - Configuration changes via environment variables

**Acceptance Criteria:** All existing features work identically with new HAL

**Rollback:** Revert to Phase 3 backup if any test fails

---

### Phase 5: Production Deployment

**Duration:** 0.5 day

1. Set `CAMERA_INTERFACE=auto` in production `.env`
2. Deploy to Pi 4B
3. Monitor logs for first 24 hours
4. Verify no performance degradation

**Rollback Plan:**
```bash
# Emergency rollback
git revert <migration_commit_hash>
sudo systemctl restart ps-rcs-service
```

---

## 11. ACCEPTANCE CRITERIA

### Test Case 1: USB Camera Initialization (Functional)

**Given:** USB webcam connected to Raspberry Pi 4B  
**When:** `CAMERA_INTERFACE=usb` environment variable set  
**And:** `VisionManager.start_capture(640, 480, 30)` called  
**Then:**
- Factory selects `UsbCameraProvider`
- V4L2 backend negotiates MJPG format
- Camera initializes at index 0
- `start_capture()` returns `True`
- Log contains: `"[Vision] Camera FOUND at index 0 (MJPG 640x480)"`

**Expected Behavior:**
- Frame acquisition successful within 100ms
- Frames are BGR format, shape `(480, 640, 3)`
- No errors in logs

---

### Test Case 2: CSI Camera Initialization (Functional)

**Given:** Pi Camera Module 3 connected via CSI ribbon cable  
**When:** `CAMERA_INTERFACE=csi` environment variable set  
**And:** `VisionManager.start_capture(640, 480, 30)` called  
**Then:**
- Factory selects `CsiCameraProvider`
- picamera2 library successfully imported
- Camera initializes as `Picamera2(0)`
- `start_capture()` returns `True`
- Log contains: `"[Vision] Pi Camera Module 3 initialized (640x480@30fps)"`

**Expected Behavior:**
- Frames are converted from RGB to BGR
- Frame shape is `(480, 640, 3)`, dtype `uint8`
- Frame acquisition latency < 50ms (hardware accelerated)

---

### Test Case 3: Auto-Selection with Fallback (Robustness)

**Given:** Pi 4B with both CSI camera AND USB webcam connected  
**When:** `CAMERA_INTERFACE=auto` environment variable set  
**And:** CSI camera is physically disconnected  
**And:** `VisionManager.start_capture(640, 480, 30)` called  
**Then:**
- Factory attempts `CsiCameraProvider()` first
- CSI initialization fails (returns `False`)
- Factory falls back to `UsbCameraProvider()`
- USB initialization succeeds
- `start_capture()` returns `True`
- Log contains: `"[Vision] CSI initialization failed, falling back to USB"`

**Expected Behavior:**
- System continues operating with USB camera
- No crashes or exceptions
- Dashboard stream works normally

---

### Test Case 4: Hardware Disconnection During Operation (Resilience)

**Given:** Camera streaming successfully  
**When:** USB cable physically unplugged  
**Then:**
- `provider.read()` returns `(False, None)` for 10 consecutive reads
- `_capture_loop` increments `consecutive_failures` counter
- After 10 failures, loop breaks
- `stop_capture()` called automatically
- Log contains: `"[Vision] Camera disconnected (10 consecutive read failures)"`

**Expected Behavior:**
- No segmentation faults or crashes
- Flask API remains responsive
- Dashboard displays "Camera Unavailable" message
- Stream reconnects if cable re-plugged and `start_capture()` called again

---

### Test Case 5: Invalid Configuration (Error Handling)

**Given:** `.env` file contains `CAMERA_WIDTH=9999`  
**When:** `validate_camera_config()` called  
**Then:**
- Raises `CameraConfigurationError("Invalid width: 9999")`

**And Given:** `CAMERA_INTERFACE=invalid_value`  
**When:** `validate_camera_config()` called  
**Then:**
- Raises `CameraConfigurationError("Invalid interface: invalid_value")`

**Expected Behavior:**
- Errors logged with full context
- System falls back to default configuration
- No silent failures

---

### Test Case 6: Thread Safety Verification (Concurrency)

**Given:** Camera initialized and streaming  
**When:** `stop_capture()` called from Flask request thread (Thread A)  
**And:** `_capture_loop()` running in background daemon thread (Thread B)  
**Then:**
- Thread A blocks until Thread B terminates
- `provider.stop()` called AFTER Thread B completes
- No deadlocks occur
- Max blocking time: 2.5 seconds

**Expected Behavior:**
- All resources properly released
- No memory leaks (verify with `tracemalloc`)
- System ready for immediate `start_capture()` call

---

### Test Case 7: Multiple Start/Stop Cycles (Stability)

**Given:** Camera in stopped state  
**When:** Following sequence executed 10 times:
```python
assert manager.start_capture(640, 480, 30) == True
time.sleep(2.0)  # Stream for 2 seconds
manager.stop_capture()
time.sleep(0.5)  # Wait for cleanup
```
**Then:**
- All 10 iterations succeed
- No resource leaks (verify file descriptors)
- No performance degradation over iterations

**Expected Behavior:**
- Memory usage stable (±5% variance)
- CPU usage returns to baseline after each `stop_capture()`
- Log contains no errors or warnings

---

### Test Case 8: Performance Benchmarks (Non-Functional)

**USB Camera Performance:**
- Frame acquisition rate: ≥ 28 FPS @ 640x480
- Frame latency (read call to frame available): ≤ 35ms
- CPU usage: ≤ 15% on Pi 4B (single core)

**CSI Camera Performance:**
- Frame acquisition rate: ≥ 29 FPS @ 640x480
- Frame latency: ≤ 50ms (includes RGB→BGR conversion)
- CPU usage: ≤ 20% on Pi 4B (conversion overhead)

**Stream Bandwidth (Dashboard):**
- MJPEG stream @ quality=40: 50-70 KB/s
- No degradation with HAL vs. original implementation

---

### Test Case 9: Backward Compatibility (Integration)

**Given:** Existing OCR scanner modal code unchanged  
**When:** Camera HAL deployed to production  
**Then:**
- OCR scanner opens camera modal successfully
- Live camera feed renders in modal
- "Capture" button works (high-res 1920x1080 save)
- "Paste Image" source selection works
- All existing frontend JavaScript works unchanged

**Expected Behavior:**
- Zero frontend code changes required
- All API endpoints maintain response format
- Dashboard theme toggle doesn't break streams

---

### Test Case 10: Cross-Platform Development (Portability)

**Given:** Developer working on Windows 10 machine  
**When:** Project cloned and `pip install -r requirements.txt` executed  
**Then:**
- `import CameraProvider` succeeds
- `get_camera_provider()` returns `UsbCameraProvider` (picamera2 unavailable)
- No import errors or crashes
- Developer can run and test VisionManager with USB webcam

**Expected Behavior:**
- `try/except ImportError` guards prevent crashes
- Factory logs: `"[Warning] picamera2 not available, using USB provider"`
- Windows development workflow unaffected

---

## 12. PERFORMANCE REQUIREMENTS

### Initialization Performance

| Metric | USB Provider | CSI Provider | Acceptable Range |
|--------|--------------|--------------|------------------|
| `start()` duration | 200-800ms | 500-1200ms | < 2000ms |
| Memory allocation | ~5 MB | ~8 MB | < 20 MB |
| File descriptors | 1 | 2-3 | < 10 |

### Runtime Performance

| Metric | USB Provider | CSI Provider | Acceptable Range |
|--------|--------------|--------------|------------------|
| Frame rate (640x480) | 28-30 FPS | 29-30 FPS | ≥ 25 FPS |
| CPU usage (idle) | 5-8% | 8-12% | ≤ 20% |
| CPU usage (streaming) | 12-15% | 18-22% | ≤ 30% |
| Frame latency | 30-35ms | 40-50ms | ≤ 100ms |

### Cleanup Performance

| Metric | Both Providers | Acceptable Range |
|--------|----------------|------------------|
| `stop()` duration | 100-500ms | < 2500ms |
| Thread join timeout | 2000ms | Fixed |
| Memory release | 100% | 100% |

---

## POST-ACTION REPORT

```
✅ **Contract Created:** `docs/contracts/camera_hal_v1.md`
📋 **Work Order Generated:** See below
```

---

