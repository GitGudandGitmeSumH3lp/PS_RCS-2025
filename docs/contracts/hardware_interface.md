# CONTRACT: Hardware Abstraction Layer (Base Interface)
**Version:** 1.0  
**Last Updated:** 2026-01-21  
**Status:** Draft  
**File Location:** `src/hardware/base.py`

---

## 1. PURPOSE
Defines the abstract base class that ALL hardware drivers must inherit from. Enforces a standardized interface for sensor/actuator communication, ensuring thread-safe state management and consistent error handling across LiDAR, HuskyLens, and Motor services.

---

## 2. PUBLIC INTERFACE

### Abstract Class: `HardwareInterface`

**Signature:**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

class DeviceStatus(Enum):
    """Hardware device connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class HardwareInterface(ABC):
    """
    Abstract base class for all hardware drivers.
    
    All concrete implementations (LidarService, HuskyService, MotorService)
    MUST inherit from this class and implement all abstract methods.
    
    Enforces System Constraint 1: "Hardware handlers must run in separate
    Threads to avoid blocking the Flask Main Loop."
    
    Attributes:
        device_id: Unique identifier for this hardware instance
        port: Serial port path (e.g., /dev/ttyUSB0)
        is_connected: Current connection status (read-only property)
        last_reading: Most recent sensor data snapshot (read-only property)
    """
    
    def __init__(self, device_id: str, port: str) -> None:
        """
        Initialize hardware interface.
        
        Args:
            device_id: Unique identifier (e.g., "lidar_front", "husky_main")
            port: Serial port path loaded from environment config
        
        Raises:
            ValueError: If device_id is empty or port is invalid format
        """
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to physical hardware device.
        
        This method MUST be implemented by all concrete hardware services.
        Should handle serial port initialization, baud rate configuration,
        and initial handshake protocols.
        
        Returns:
            True if connection successful, False otherwise
        
        Raises:
            SerialException: If port cannot be opened
            TimeoutError: If device doesn't respond within timeout period
        
        Side Effects:
            - Opens serial port file descriptor
            - Updates internal _is_connected flag
            - May write initialization commands to device
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Safely close hardware connection and release resources.
        
        This method MUST gracefully shut down the device, close serial
        ports, and clean up any allocated resources. Should never raise
        exceptions during normal shutdown.
        
        Returns:
            None
        
        Side Effects:
            - Closes serial port file descriptor
            - Updates internal _is_connected flag to False
            - May send shutdown commands to device
        """
        pass
    
    @abstractmethod
    async def read(self) -> Dict[str, Any]:
        """
        Read current sensor data or actuator state.
        
        This is the PRIMARY data acquisition method called by Service Manager
        at the configured poll rate (default 10 Hz).
        
        Returns:
            Standardized data dictionary with keys:
                - "timestamp": datetime (UTC)
                - "device_id": str (matches self.device_id)
                - "status": DeviceStatus enum value
                - "data": Dict[str, Any] (device-specific payload)
                - "error_message": Optional[str] (if status is ERROR)
        
        Raises:
            SerialException: If communication fails during read
            TimeoutError: If device doesn't respond within timeout
            ValueError: If received data fails validation
        
        Side Effects:
            - Reads from serial port buffer
            - Updates internal _last_reading cache
            - May clear device read buffers
        
        Example Return Value (LiDAR):
        {
            "timestamp": datetime(2026, 1, 21, 14, 30, 0),
            "device_id": "lidar_front",
            "status": DeviceStatus.CONNECTED,
            "data": {
                "distances": [120, 125, 130, ...],  # mm
                "angles": [0, 1, 2, ...],           # degrees
                "quality": [15, 15, 14, ...]        # signal strength
            }
        }
        """
        pass
    
    @abstractmethod
    async def emergency_stop(self) -> None:
        """
        Immediately halt all actuator motion and enter safe state.
        
        This method MUST execute within 100ms per Safety Requirement 4.1.
        For sensors (LiDAR, HuskyLens): Enter read-only safe mode.
        For actuators (Motors): Set velocity to zero and disable PWM.
        
        Returns:
            None
        
        Raises:
            SerialException: If stop command cannot be sent
        
        Side Effects:
            - Sends emergency stop command to hardware
            - Updates internal _error_state flag
            - Sets status to DeviceStatus.EMERGENCY_STOP
        
        Performance Requirement:
            MUST complete within 100ms (hard deadline)
        """
        pass
    
    @property
    def is_connected(self) -> bool:
        """
        Check if hardware is currently connected.
        
        Returns:
            True if device status is CONNECTED, False otherwise
        """
        pass
    
    @property
    def last_reading(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve most recent sensor reading without triggering new read.
        
        Returns:
            Last cached reading from read() method, or None if no data yet
        """
        pass
    
    @property
    def status(self) -> DeviceStatus:
        """
        Get current device status.
        
        Returns:
            Current DeviceStatus enum value
        """
        pass
```

---

## 3. CONCRETE IMPLEMENTATIONS (Sketches)

### 3.1 LidarService

**File:** `src/hardware/lidar/service.py`

**Signature Sketch:**
```python
from src.hardware.base import HardwareInterface, DeviceStatus

class LidarService(HardwareInterface):
    """LiDAR distance sensor driver (LD19 model)."""
    
    async def connect(self) -> bool:
        """Open serial port at 230400 baud."""
        pass
    
    async def read(self) -> Dict[str, Any]:
        """
        Read 360-degree distance scan.
        
        Returns data format:
        {
            "data": {
                "distances": List[int],  # 360 values in mm
                "angles": List[float],   # Corresponding angles
                "quality": List[int]     # Signal strength 0-15
            }
        }
        """
        pass
```

### 3.2 HuskyService

**File:** `src/hardware/huskylens/service.py`

**Signature Sketch:**
```python
class HuskyService(HardwareInterface):
    """HuskyLens AI vision sensor driver."""
    
    async def connect(self) -> bool:
        """Initialize I2C/UART connection at 9600 baud."""
        pass
    
    async def read(self) -> Dict[str, Any]:
        """
        Read detected objects (face recognition, object tracking).
        
        Returns data format:
        {
            "data": {
                "blocks": List[Dict],    # Detected bounding boxes
                "arrows": List[Dict],    # Tracked objects
                "learned_ids": List[int] # Recognized faces
            }
        }
        """
        pass
```

### 3.3 MotorService

**File:** `src/hardware/motor/service.py`

**Signature Sketch:**
```python
class MotorService(HardwareInterface):
    """Arduino-based motor controller driver."""
    
    async def connect(self) -> bool:
        """Open serial to Arduino at 115200 baud."""
        pass
    
    async def read(self) -> Dict[str, Any]:
        """
        Read current motor state (RPM, encoder ticks).
        
        Returns data format:
        {
            "data": {
                "left_rpm": float,
                "right_rpm": float,
                "battery_voltage": float
            }
        }
        """
        pass
    
    async def set_velocity(self, left: float, right: float) -> None:
        """Send velocity command to motors (NOT part of base interface)."""
        pass
```

---

## 4. DEPENDENCIES

**This module CALLS:**
- `abc.ABC`, `abc.abstractmethod` - Abstract base class decorators
- `typing.Dict`, `typing.Any`, `typing.Optional` - Type hints
- `datetime.datetime` - Timestamp generation
- `enum.Enum` - DeviceStatus enumeration

**This module is CALLED BY:**
- `src/hardware/lidar/service.py` - Inherits from HardwareInterface
- `src/hardware/huskylens/service.py` - Inherits from HardwareInterface
- `src/hardware/motor/service.py` - Inherits from HardwareInterface
- `src/core/service_manager.py` - Type checks and polymorphic calls

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

1. **Concurrency Requirement** (System Constraint 1)
   - All I/O methods MUST be `async def` to enable non-blocking execution
   - Service Manager will run these in separate threads via `asyncio.run()`

2. **Type Hints Required** (System Constraint 3)
   - All method signatures must include parameter and return type annotations
   - Use `Dict[str, Any]` for flexible device-specific payloads

3. **Error Handling** (System Constraint 3)
   - Hardware failures must NOT crash the application
   - All exceptions must be caught by Service Manager and logged to state

4. **No Hardcoded Ports** (System Constraint 1)
   - `port` parameter MUST come from `Settings` config object
   - Constructor must accept port as string argument

---

## 6. ACCEPTANCE CRITERIA (Test Cases)

### Test Case 1: Abstract Method Enforcement
**Scenario:** Attempt to instantiate incomplete subclass

**Input:**
```python
class IncompleteDriver(HardwareInterface):
    async def connect(self) -> bool:
        return True
    # Missing: disconnect, read, emergency_stop

driver = IncompleteDriver("test", "/dev/ttyUSB0")
```

**Expected Exception:** `TypeError`

**Expected Message Pattern:**
```
Can't instantiate abstract class IncompleteDriver with abstract methods disconnect, emergency_stop, read
```

---

### Test Case 2: Successful Connection Flow
**Scenario:** Mock hardware service connects successfully

**Input:**
```python
class MockSensor(HardwareInterface):
    async def connect(self) -> bool:
        self._is_connected = True
        return True
    
    async def disconnect(self) -> None:
        self._is_connected = False
    
    async def read(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.utcnow(),
            "device_id": self.device_id,
            "status": DeviceStatus.CONNECTED,
            "data": {"value": 42}
        }
    
    async def emergency_stop(self) -> None:
        pass

sensor = MockSensor("mock1", "/dev/ttyUSB0")
result = await sensor.connect()
```

**Expected Output:**
```python
assert result == True
assert sensor.is_connected == True
assert sensor.status == DeviceStatus.CONNECTED
```

---

### Test Case 3: Read Data Format Validation
**Scenario:** Verify returned data matches contract structure

**Input:**
```python
sensor = MockSensor("test", "/dev/ttyUSB0")
await sensor.connect()
data = await sensor.read()
```

**Expected Behavior:**
```python
assert "timestamp" in data
assert "device_id" in data
assert "status" in data
assert "data" in data
assert isinstance(data["timestamp"], datetime)
assert data["device_id"] == "test"
assert isinstance(data["status"], DeviceStatus)
```

---

### Test Case 4: Emergency Stop Response Time
**Scenario:** Measure E-stop execution time

**Input:**
```python
import time

sensor = MockSensor("test", "/dev/ttyUSB0")
await sensor.connect()

start = time.perf_counter()
await sensor.emergency_stop()
duration = time.perf_counter() - start
```

**Expected Behavior:**
```python
assert duration < 0.1  # Must complete within 100ms
assert sensor.status == DeviceStatus.EMERGENCY_STOP
```

---

## 7. PERFORMANCE REQUIREMENTS

**Method: `read()`**
- **Time Complexity:** O(n) where n = number of sensor data points
- **Space Complexity:** O(n) for data dictionary
- **Execution Time:** < 50ms per call (to support 20 Hz polling)

**Method: `emergency_stop()`**
- **Time Complexity:** O(1)
- **Execution Time:** < 100ms (HARD DEADLINE per Safety Requirements)

---

## 8. IMPLEMENTATION NOTES

### For the Builder:

1. **Thread Safety:**
   - Use `threading.RLock()` for internal state variables (`_is_connected`, `_last_reading`)
   - Service Manager will call methods from background threads

2. **Async Best Practices:**
   - Use `asyncio.sleep()` instead of `time.sleep()`
   - Serial I/O should use `asyncio.create_subprocess_exec()` or `serial_asyncio` library

3. **Error State Management:**
   - If `read()` fails 3 consecutive times, set status to `DeviceStatus.ERROR`
   - Store error message in `_error_state` attribute

4. **Logging:**
   - Log all connection attempts, disconnections, and errors
   - Use `logging.getLogger(__name__)` pattern

5. **Existing Code Integration:**
   - Legacy handlers in `src/hardware/lidar/handler.py` should be refactored into `LidarService`
   - Preserve existing protocol implementations (LD19 packet parsing logic)

---

**END OF CONTRACT**