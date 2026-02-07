# WORK ORDER FOR IMPLEMENTER

**Target Files:**
- `src/hardware/camera/base.py`
- `src/hardware/camera/usb_provider.py`
- `src/hardware/camera/csi_provider.py`
- `src/hardware/camera/factory.py`
- `src/hardware/camera/__init__.py`
- `src/services/vision_manager.py` (refactor)
- `src/core/config.py` (modify)

**Contract Reference:** `docs/contracts/camera_hal_v1.md` v1.0

---

## STRICT CONSTRAINTS (NON-NEGOTIABLE)

### From `system_constraints.md`:

1. **Max Function Length:** 50 lines per function. Refactor if longer.
2. **Type Hints:** Mandatory for ALL function signatures and class attributes.
3. **Docstrings:** Google-style docstrings required for ALL public classes/methods.
4. **Concurrency:** Use `threading` only. No `asyncio`.
5. **Error Handling:** Use specific exception types. No generic `except Exception`.
6. **Logging:** Use Python `logging` module. No `print()` statements in production code.
7. **Imports:** Absolute imports from project root (`from src.hardware.camera import ...`).

### From Contract:

8. **Thread Safety:**
   - `start()` MUST be called from main thread only (both providers)
   - `read()` MUST be safe for background thread
   - `stop()` MUST be safe from any thread
9. **Idempotency:** `stop()` must be safe to call multiple times
10. **BGR Format:** All frames MUST be BGR regardless of hardware source
11. **Graceful Degradation:** Hardware failures return `False`, not exceptions
12. **Resource Cleanup:** ALL resources released in `stop()` (no leaks)

---

## MEMORY COMPLIANCE (MANDATORY)

### From `_STATE.md`:

- **2026-02-07 | Stream Lifecycle Management:**
  - Providers must support on-demand start/stop (bandwidth optimization)
  - `stop()` must be idempotent for safe lifecycle management
  
- **2026-02-06 | Hardware Abstraction:**
  - NO hardware library imports outside of provider implementations
  - VisionManager must remain hardware-agnostic after refactor

---

## REQUIRED LOGIC

### File 1: `src/hardware/camera/base.py`

```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: base.py
Description: Abstract base class for camera hardware providers.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np


class CameraProvider(ABC):
    """Abstract base class defining camera hardware interface contract."""
    
    @abstractmethod
    def start(self, width: int, height: int, fps: int) -> bool:
        """Initialize camera with specified parameters.
        
        Args:
            width: Capture width (1-3840).
            height: Capture height (1-2160).
            fps: Framerate (1-120).
        
        Returns:
            True if successful, False otherwise.
        
        Raises:
            ValueError: If parameters outside valid ranges.
            RuntimeError: If already started.
        """
        pass
    
    @abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Acquire next frame (blocking).
        
        Returns:
            (success, frame_bgr) tuple.
            Frame is None if success is False.
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Release hardware and cleanup. Idempotent."""
        pass


class CameraError(Exception):
    """Base exception for camera errors."""
    pass


class CameraInitializationError(CameraError):
    """Camera hardware initialization failed."""
    pass


class CameraConfigurationError(CameraError):
    """Invalid configuration parameters."""
    pass
```

**Constraints:**
- Must be pure interface definition (no implementation)
- All methods abstract (use `@abstractmethod`)
- Exception hierarchy for error handling

---

### File 2: `src/hardware/camera/usb_provider.py`

**Critical Requirements:**

1. **Preserve Existing USB Negotiation Logic:**
   - V4L2 backend (`cv2.CAP_V4L2`)
   - MJPG format set BEFORE resolution
   - Double-read handshake pattern
   - Index scanning (0, then 1-5)

2. **Refactor for 50-Line Limit:**
   - Break `start()` into helper methods:
     - `_try_camera_index(index: int, width: int, height: int, fps: int) -> bool`
     - `_configure_capture(cap: cv2.VideoCapture, width: int, height: int, fps: int) -> bool`
   
3. **Method Signatures (from contract):**
   ```python
   def start(self, width: int, height: int, fps: int) -> bool
   def read(self) -> Tuple[bool, Optional[np.ndarray]]
   def stop(self) -> None
   ```

4. **State Management:**
   - `self.stream: Optional[cv2.VideoCapture] = None`
   - `self.is_running: bool = False`
   - Track `self.camera_index: Optional[int] = None`

5. **Logging:**
   ```python
   import logging
   logger = logging.getLogger(__name__)
   
   logger.info(f"USB camera initialized at index {index}")
   logger.error(f"USB camera initialization failed: {e}")
   ```

**Implementation Checklist:**
- [ ] Parameter validation (raise `ValueError` if invalid)
- [ ] Already-running check (raise `RuntimeError`)
- [ ] Try index 0 first with V4L2 backend
- [ ] Set MJPG fourcc BEFORE resolution
- [ ] Double-read handshake
- [ ] Fallback to indices 1-5 if index 0 fails
- [ ] Return `False` if all indices fail (not exception)
- [ ] `read()` wraps `self.stream.read()`
- [ ] `stop()` is idempotent (check `self.stream is not None`)
- [ ] Release in `stop()` and set `self.stream = None`

---

### File 3: `src/hardware/camera/csi_provider.py`

**Critical Requirements:**

1. **Import Guarding:**
   ```python
   try:
       from picamera2 import Picamera2
       _PICAMERA2_AVAILABLE = True
   except ImportError:
       _PICAMERA2_AVAILABLE = False
   ```

2. **Initialization (Main Thread Only):**
   ```python
   def start(self, width: int, height: int, fps: int) -> bool:
       if not _PICAMERA2_AVAILABLE:
           logger.error("picamera2 not available")
           return False
       
       if self.is_running:
           raise RuntimeError("Camera already started")
       
       try:
           self.picam2 = Picamera2()
           config = self.picam2.create_still_configuration(
               main={"size": (width, height), "format": "RGB888"},
               lores={"size": (width, height), "format": "RGB888"}
           )
           self.picam2.configure(config)
           self.picam2.start()
           self.is_running = True
           logger.info(f"CSI camera initialized ({width}x{height}@{fps}fps)")
           return True
       except Exception as e:
           logger.error(f"CSI initialization failed: {e}")
           return False
   ```

3. **Frame Reading (Any Thread):**
   ```python
   def read(self) -> Tuple[bool, Optional[np.ndarray]]:
       if not self.is_running or self.picam2 is None:
           return False, None
       
       try:
           frame_rgb = self.picam2.capture_array("lores")
           frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
           return True, frame_bgr
       except Exception as e:
           logger.error(f"CSI frame read failed: {e}")
           return False, None
   ```

4. **Thread-Safe Shutdown:**
   ```python
   def stop(self) -> None:
       with self.lock:  # Thread safety
           if self.picam2 is not None:
               try:
                   self.picam2.stop()
                   self.picam2.close()
               except Exception as e:
                   logger.error(f"CSI cleanup error: {e}")
               finally:
                   self.picam2 = None
                   self.is_running = False
   ```

5. **State Attributes:**
   ```python
   def __init__(self):
       self.picam2: Optional[Picamera2] = None
       self.is_running: bool = False
       self.lock = threading.Lock()
   ```

**Implementation Checklist:**
- [ ] Import guard for picamera2
- [ ] Parameter validation (raise `ValueError`)
- [ ] Main thread initialization requirement documented
- [ ] RGB to BGR conversion in `read()`
- [ ] Thread-safe `stop()` with explicit lock
- [ ] Idempotent `stop()` (check `self.picam2 is not None`)
- [ ] Error logging for all failure cases
- [ ] Return `(False, None)` on read errors (not exception)

---

### File 4: `src/hardware/camera/factory.py`

**Logic Flow:**

```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: factory.py
Description: Factory for camera provider selection.
"""

import os
import logging
from typing import Optional

from .base import CameraProvider, CameraConfigurationError
from .usb_provider import UsbCameraProvider

logger = logging.getLogger(__name__)

# Attempt CSI provider import
try:
    from .csi_provider import CsiCameraProvider
    _CSI_AVAILABLE = True
except ImportError:
    _CSI_AVAILABLE = False
    logger.warning("CSI provider unavailable (picamera2 not installed)")


def get_camera_provider(interface: Optional[str] = None) -> CameraProvider:
    """Factory function to select camera provider.
    
    Args:
        interface: Override for CAMERA_INTERFACE env var.
            Valid: 'usb', 'csi', 'auto', or None.
    
    Returns:
        CameraProvider instance.
    
    Raises:
        ValueError: If interface invalid.
        ImportError: If forced provider unavailable.
    """
    # Determine interface mode
    if interface is None:
        interface = os.getenv('CAMERA_INTERFACE', 'auto').lower()
    else:
        interface = interface.lower()
    
    # Validate interface
    if interface not in {'usb', 'csi', 'auto'}:
        raise ValueError(
            f"Invalid CAMERA_INTERFACE: '{interface}'. "
            "Must be 'usb', 'csi', or 'auto'."
        )
    
    # Force USB mode
    if interface == 'usb':
        logger.info("Factory: Forcing USB camera provider")
        return UsbCameraProvider()
    
    # Force CSI mode
    if interface == 'csi':
        if not _CSI_AVAILABLE:
            raise ImportError(
                "CSI provider requested but picamera2 not available. "
                "Install via: sudo apt install python3-picamera2"
            )
        logger.info("Factory: Forcing CSI camera provider")
        return CsiCameraProvider()
    
    # Auto mode: Try CSI first, fallback to USB
    if interface == 'auto':
        if _CSI_AVAILABLE:
            logger.info("Factory: Auto mode, trying CSI provider first")
            try:
                return CsiCameraProvider()
            except Exception as e:
                logger.warning(f"CSI provider failed, falling back to USB: {e}")
        else:
            logger.info("Factory: Auto mode, CSI unavailable, using USB")
        
        return UsbCameraProvider()
```

**Implementation Checklist:**
- [ ] Environment variable lookup (`CAMERA_INTERFACE`)
- [ ] Override parameter support
- [ ] Input validation (valid interface strings)
- [ ] CSI import guard with fallback
- [ ] Auto-selection logic (CSI → USB)
- [ ] Informative logging at each decision point
- [ ] Proper exception types (`ValueError`, `ImportError`)

---

### File 5: `src/hardware/camera/__init__.py`

```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: __init__.py
Description: Camera HAL package exports.
"""

from .base import (
    CameraProvider,
    CameraError,
    CameraInitializationError,
    CameraConfigurationError,
)
from .factory import get_camera_provider

# Conditional exports
try:
    from .usb_provider import UsbCameraProvider
    __all__ = [
        'CameraProvider',
        'CameraError',
        'CameraInitializationError',
        'CameraConfigurationError',
        'get_camera_provider',
        'UsbCameraProvider',
    ]
except ImportError:
    __all__ = [
        'CameraProvider',
        'CameraError',
        'CameraInitializationError',
        'CameraConfigurationError',
        'get_camera_provider',
    ]

# CSI provider export (optional)
try:
    from .csi_provider import CsiCameraProvider
    __all__.append('CsiCameraProvider')
except ImportError:
    pass
```

---

### File 6: `src/services/vision_manager.py` (REFACTOR)

**Changes Required:**

1. **Remove:**
   ```python
   self.stream: Optional[cv2.VideoCapture] = None
   self.camera_index: Optional[int] = None
   ```

2. **Add:**
   ```python
   from src.hardware.camera import get_camera_provider, CameraProvider
   
   self.provider: Optional[CameraProvider] = None
   ```

3. **Update `start_capture()`:**
   ```python
   def start_capture(self, width: int = 640, height: int = 480, fps: int = 30) -> bool:
       """Initialize camera hardware."""
       # Validation (keep existing logic)
       if width <= 0 or width > 1920 or height <= 0 or height > 1080 or fps <= 0 or fps > 60:
           raise ValueError("Invalid camera parameters")
       
       if self.capture_thread is not None and self.capture_thread.is_alive():
           raise RuntimeError("Capture already started. Call stop_capture() first.")
       
       # NEW: Use factory to get provider
       self.provider = get_camera_provider()
       if not self.provider.start(width, height, fps):
           logger.error("Camera provider initialization failed")
           return False
       
       # Start background thread (keep existing logic)
       self.stopped = False
       self.current_frame = None
       self.capture_thread = threading.Thread(
           target=self._capture_loop,
           daemon=True
       )
       self.capture_thread.start()
       return True
   ```

4. **Update `_capture_loop()`:**
   ```python
   def _capture_loop(self) -> None:
       """Background frame acquisition loop."""
       consecutive_failures = 0
       
       while not self.stopped:
           # NEW: Use provider.read() instead of self.stream.read()
           ret, frame = self.provider.read()
           
           if ret:
               with self.frame_lock:
                   self.current_frame = frame
               consecutive_failures = 0
           else:
               consecutive_failures += 1
               if consecutive_failures > 10:
                   logger.error("Camera disconnected (10 consecutive failures)")
                   break
           
           time.sleep(0.001)
   ```

5. **Update `stop_capture()`:**
   ```python
   def stop_capture(self) -> None:
       """Stop camera and cleanup."""
       if self.stopped:
           return
       
       self.stopped = True
       
       # Join background thread
       if self.capture_thread is not None:
           self.capture_thread.join(timeout=2.0)
       
       # NEW: Use provider.stop() instead of self.stream.release()
       if self.provider is not None:
           self.provider.stop()
           self.provider = None
       
       # Clear frame buffer
       with self.frame_lock:
           self.current_frame = None
   ```

6. **Keep Unchanged:**
   ```python
   def get_frame(self) -> Optional[np.ndarray]:
       """NO CHANGES - this method stays exactly the same"""
       with self.frame_lock:
           if self.current_frame is None:
               return None
           return self.current_frame.copy()
   
   def generate_mjpeg(self, quality: int = 40) -> Generator[bytes, None, None]:
       """NO CHANGES - this method stays exactly the same"""
       # ... existing implementation ...
   ```

**Refactor Checklist:**
- [ ] Import `get_camera_provider` from hardware layer
- [ ] Replace `self.stream` with `self.provider`
- [ ] Update `start_capture()` to use factory
- [ ] Update `_capture_loop()` to use `provider.read()`
- [ ] Update `stop_capture()` to use `provider.stop()`
- [ ] Keep `get_frame()` unchanged (public API preservation)
- [ ] Keep `generate_mjpeg()` unchanged (public API preservation)
- [ ] Add logging for provider failures

---

### File 7: `src/core/config.py` (MODIFY)

**Add Configuration Class:**

```python
from dataclasses import dataclass
import os
from typing import Optional

@dataclass(frozen=True)
class CameraConfig:
    """Immutable camera configuration."""
    interface: str  # 'usb', 'csi', or 'auto'
    width: int
    height: int
    fps: int
    
    @classmethod
    def from_environment(cls) -> 'CameraConfig':
        """Load configuration from environment variables.
        
        Returns:
            Validated CameraConfig instance.
        
        Raises:
            ValueError: If any parameter invalid.
        """
        interface = os.getenv('CAMERA_INTERFACE', 'auto').lower()
        
        try:
            width = int(os.getenv('CAMERA_WIDTH', '640'))
            height = int(os.getenv('CAMERA_HEIGHT', '480'))
            fps = int(os.getenv('CAMERA_FPS', '30'))
        except ValueError as e:
            raise ValueError(f"Invalid camera configuration: {e}")
        
        # Validate ranges
        if interface not in {'usb', 'csi', 'auto'}:
            raise ValueError(f"Invalid CAMERA_INTERFACE: {interface}")
        if not (1 <= width <= 3840):
            raise ValueError(f"CAMERA_WIDTH must be 1-3840, got {width}")
        if not (1 <= height <= 2160):
            raise ValueError(f"CAMERA_HEIGHT must be 1-2160, got {height}")
        if not (1 <= fps <= 120):
            raise ValueError(f"CAMERA_FPS must be 1-120, got {fps}")
        
        return cls(
            interface=interface,
            width=width,
            height=height,
            fps=fps
        )
```

---

## INTEGRATION POINTS

### Must Call:
- `VisionManager.start_capture()` → `get_camera_provider()` → `provider.start()`
- `VisionManager._capture_loop()` → `provider.read()`
- `VisionManager.stop_capture()` → `provider.stop()`

### Will Be Called By:
- Flask routes (`/api/camera/start`, `/api/camera/stop`)
- OCR service (`analyze_image()` method)
- Dashboard frontend (stream initialization)

---

## SUCCESS CRITERIA

### Code Quality:
- [ ] All functions under 50 lines
- [ ] Type hints on all signatures
- [ ] Google-style docstrings on all public methods
- [ ] No generic `except Exception` (use specific types)
- [ ] Logging instead of print statements

### Functional:
- [ ] USB camera works with `CAMERA_INTERFACE=usb`
- [ ] CSI camera works with `CAMERA_INTERFACE=csi`
- [ ] Auto-selection works with `CAMERA_INTERFACE=auto`
- [ ] All 10 acceptance test cases pass (from contract)
- [ ] No regressions in existing features (OCR, dashboard, stream)

### Performance:
- [ ] Frame rate ≥ 25 FPS at 640x480
- [ ] CPU usage ≤ 30% during streaming
- [ ] Memory stable over 10 start/stop cycles

### Deployment:
- [ ] Auditor approval on all files
- [ ] Integration tests pass on Pi 4B hardware
- [ ] Production deployment successful with zero downtime

---

## TESTING REQUIREMENTS

### Unit Tests (Create):

```bash
tests/hardware/camera/
├── test_base.py          # ABC interface tests
├── test_usb_provider.py  # USB provider tests
├── test_csi_provider.py  # CSI provider tests (Pi only)
└── test_factory.py       # Factory selection tests
```

### Integration Tests (Modify):

```bash
tests/services/
└── test_vision_manager.py  # Update to use HAL
```

### Manual Tests (Execute):

1. **USB Camera Test:**
   ```bash
   export CAMERA_INTERFACE=usb
   python3 -m src.services.vision_manager
   # Verify: Camera initializes, frames acquired
   ```

2. **CSI Camera Test (Pi 4B only):**
   ```bash
   export CAMERA_INTERFACE=csi
   python3 -m src.services.vision_manager
   # Verify: Module 3 initializes, RGB→BGR conversion works
   ```

3. **Dashboard Integration Test:**
   ```bash
   # Start Flask server
   python3 web/client/app.py
   # Navigate to: http://localhost:5000/dashboard
   # Verify: Live stream renders, OCR modal works
   ```

---

## MIGRATION CHECKLIST

### Pre-Migration:
- [ ] Backup current `vision_manager.py`
- [ ] Review all test cases in contract
- [ ] Verify Pi Camera Module 3 hardware connected

### Implementation:
- [ ] Create `src/hardware/camera/` package
- [ ] Implement `base.py` (ABC)
- [ ] Implement `usb_provider.py` (port existing logic)
- [ ] Implement `csi_provider.py` (new picamera2 logic)
- [ ] Implement `factory.py`
- [ ] Update `__init__.py`
- [ ] Refactor `vision_manager.py`
- [ ] Modify `config.py`

### Testing:
- [ ] Run unit tests (USB provider on dev machine)
- [ ] Run integration tests (VisionManager)
- [ ] Deploy to Pi 4B staging
- [ ] Run CSI provider tests on Pi
- [ ] Run all acceptance test cases
- [ ] Verify no performance regressions

### Deployment:
- [ ] Set `CAMERA_INTERFACE=auto` in production `.env`
- [ ] Deploy to production Pi 4B
- [ ] Monitor logs for 24 hours
- [ ] Confirm zero regressions in dashboard/OCR

---

## ROLLBACK PLAN

### If Issues Detected:

1. **Immediate Rollback:**
   ```bash
   cp src/services/vision_manager.py.backup src/services/vision_manager.py
   sudo systemctl restart ps-rcs-service
   ```

2. **Git Revert:**
   ```bash
   git log --oneline  # Find migration commit hash
   git revert <commit_hash>
   git push origin main
   ```

3. **Notification:**
   - Log incident in `_STATE.md`
   - Document failure mode
   - Schedule post-mortem review

---

## FINAL NOTES FOR IMPLEMENTER

### Critical Points:

1. **50-Line Limit is ABSOLUTE:**
   - Use helper methods liberally
   - Refactor any function exceeding limit
   - Auditor will reject files with violations

2. **Thread Safety is CRITICAL:**
   - `start()` must ONLY be called from main thread
   - `read()` must be safe from background thread
   - `stop()` must be safe from ANY thread
   - Use explicit locks in CSI provider

3. **BGR Format is NON-NEGOTIABLE:**
   - All frames MUST be BGR (OpenCV standard)
   - CSI provider MUST convert RGB→BGR
   - Test with `assert frame.shape == (H, W, 3)`

4. **Error Handling Must Be Graceful:**
   - Hardware failures return `False`, not exceptions
   - Log ALL errors with context
   - System must continue operating without camera

5. **Public API Must Not Change:**
   - `VisionManager.start_capture()` signature UNCHANGED
   - `VisionManager.get_frame()` signature UNCHANGED
   - `VisionManager.generate_mjpeg()` signature UNCHANGED
   - `VisionManager.stop_capture()` signature UNCHANGED

### Questions for Architect (if needed):

- Thread safety concerns with specific provider?
- Performance optimization trade-offs?
- Error handling strategy clarification?
- Testing strategy on hardware-limited dev environment?

---

**Estimated Effort:** 16-20 hours
**Complexity:** High (hardware abstraction, threading, backward compatibility)
**Risk Level:** Medium (migration of critical service component)

**Ready for implementation? Proceed to Implementer agent.**
