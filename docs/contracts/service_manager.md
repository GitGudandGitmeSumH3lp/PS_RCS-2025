# CONTRACT: Service Manager (System Orchestrator)
**Version:** 1.0  
**Last Updated:** 2026-01-21  
**Status:** Draft  
**File Location:** `src/core/service_manager.py`

---

## 1. PURPOSE
Orchestrates all hardware services, database operations, and thread management. Acts as the central coordinator between Flask application and hardware layer. Provides thread-safe read-only access to system state while managing background polling loops.

Enforces System Constraint 1: "Hardware handlers must run in separate Threads to avoid blocking the Flask Main Loop."

---

## 2. PUBLIC INTERFACE

### Class: `ServiceManager`

**Signature:**
```python
from typing import List, Optional, Dict, Any
from threading import Thread, Event, RLock
import asyncio
from src.hardware.base import HardwareInterface
from src.core.state_manager import StateManager
from src.config.settings import Settings

class ServiceManager:
    """
    Central orchestrator for hardware services and background operations.
    
    Responsibilities:
    - Register and initialize hardware services (LiDAR, HuskyLens, Motors)
    - Start background threads for hardware polling and database persistence
    - Coordinate graceful shutdown and emergency stop procedures
    - Provide thread-safe read-only access to system state for Flask
    
    Enforces separation of concerns: Flask only READS state, never writes.
    
    Attributes:
        config: Application configuration from Pydantic Settings
        state: Thread-safe StateManager instance
        hardware_services: List of registered HardwareInterface instances
    """
    
    def __init__(self, config: Settings) -> None:
        """
        Initialize Service Manager with application configuration.
        
        Args:
            config: Validated Settings instance from src/config/settings.py
        
        Raises:
            ValueError: If config validation fails
        
        Side Effects:
            - Creates StateManager instance
            - Initializes empty hardware_services list
            - Creates stop event for thread coordination
        """
        pass
    
    def register_hardware(self, service: HardwareInterface) -> None:
        """
        Add hardware service to managed pool.
        
        Services must be registered BEFORE calling start(). Can be called
        multiple times to register different devices.
        
        Args:
            service: Concrete HardwareInterface implementation
                    (e.g., LidarService, HuskyService)
        
        Raises:
            ValueError: If service with duplicate device_id already registered
            TypeError: If service doesn't inherit from HardwareInterface
        
        Side Effects:
            - Appends service to internal hardware_services list
        
        Example:
            manager = ServiceManager(config)
            manager.register_hardware(LidarService("lidar", config.LIDAR_PORT))
            manager.register_hardware(HuskyService("husky", config.HUSKY_PORT))
        """
        pass
    
    def start(self) -> None:
        """
        Initialize all services and start background threads.
        
        Execution Flow:
        1. Call connect() on all registered hardware services
        2. Start hardware polling thread (_hardware_loop)
        3. Start database persistence thread (_database_loop)
        4. Mark threads as daemon for automatic cleanup on app exit
        
        Returns:
            None
        
        Raises:
            RuntimeError: If start() called multiple times without stop()
            ConnectionError: If any hardware service fails to connect
        
        Side Effects:
            - Opens serial connections to all hardware
            - Spawns 2 background threads (hardware + database)
            - Begins continuous polling at configured rate
        
        Threading Model:
            - Hardware Loop: asyncio event loop in thread
            - Database Loop: asyncio event loop in thread
            - Both threads check _stop_event for shutdown signal
        """
        pass
    
    def stop(self) -> None:
        """
        Gracefully shutdown all services and background threads.
        
        Execution Flow:
        1. Set stop event to signal threads to exit
        2. Wait for threads to complete (max 5 seconds each)
        3. Call disconnect() on all hardware services
        4. Close database connections
        
        Returns:
            None
        
        Side Effects:
            - Stops background threads
            - Closes all serial port connections
            - Flushes pending database writes
        
        Timeout Behavior:
            If threads don't exit within 5 seconds, force termination
            and log warning message.
        """
        pass
    
    def emergency_stop(self) -> None:
        """
        Trigger immediate hardware halt across all services.
        
        This method MUST complete within 100ms per Safety Requirement 4.1.
        Sets global emergency stop flag in StateManager, which causes
        hardware loop to call emergency_stop() on all devices.
        
        Returns:
            None
        
        Side Effects:
            - Sets StateManager.emergency_stop = True
            - Next hardware loop iteration calls HardwareInterface.emergency_stop()
            - Motors: Velocity set to zero
            - Sensors: Enter safe read-only mode
        
        Performance Requirement:
            MUST complete within 100ms (hard deadline)
        """
        pass
    
    def get_state(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Thread-safe read access to system state.
        
        This is the PRIMARY method Flask uses to retrieve hardware data.
        Returns a snapshot of state at call time (defensive copy).
        
        Args:
            device_id: Optional device identifier. If None, returns full state.
                      If specified, returns only that device's data.
        
        Returns:
            Dictionary with keys:
                - If device_id is None: Full state snapshot
                - If device_id specified: Device-specific data or None
        
        Example Return (Full State):
        {
            "lidar": {
                "data": {...},
                "updated_at": datetime(...)
            },
            "husky": {
                "data": {...},
                "updated_at": datetime(...)
            },
            "system": {
                "emergency_stop": False,
                "started_at": datetime(...),
                "errors": []
            }
        }
        
        Raises:
            None (returns None for missing device_id instead of raising)
        
        Thread Safety:
            Uses StateManager's internal RLock for atomic read
        """
        pass
    
    def is_running(self) -> bool:
        """
        Check if background threads are currently active.
        
        Returns:
            True if hardware and database loops are running, False otherwise
        """
        pass
    
    def get_registered_devices(self) -> List[str]:
        """
        Get list of all registered device IDs.
        
        Returns:
            List of device_id strings (e.g., ["lidar", "husky", "motor"])
        """
        pass
```

---

### Private Methods (Implementation Guidance)

```python
async def _hardware_loop(self) -> None:
    """
    Background coroutine: Poll all hardware at configured rate.
    
    Pseudo-code:
    1. While not stopped:
        2. For each service in hardware_services:
            3. If emergency_stop active:
                4. Call service.emergency_stop()
                5. Continue to next service
            6. Try:
                7. data = await service.read()
                8. state.update(service.device_id, data)
            9. Except Exception as e:
                10. state.update(service.device_id, {"status": "error", "message": str(e)})
        11. Sleep for (1 / HARDWARE_POLL_RATE_HZ) seconds
    """
    pass

async def _database_loop(self) -> None:
    """
    Background coroutine: Persist state snapshots to database.
    
    Pseudo-code:
    1. While not stopped:
        2. Try:
            3. snapshot = state.get_all()
            4. await db_engine.save_snapshot(snapshot)
        5. Except Exception as e:
            6. Log error but continue (hardware operations are priority)
        7. Sleep for 1 second
    """
    pass

@staticmethod
def _run_async_loop(coro) -> None:
    """
    Helper: Run async coroutine in thread.
    
    Creates new asyncio event loop for the thread and runs
    the provided coroutine until completion.
    """
    pass
```

---

## 3. DEPENDENCIES

**This module CALLS:**
- `src.hardware.base.HardwareInterface` - Type checking and polymorphic calls
- `src.core.state_manager.StateManager` - Thread-safe state storage
- `src.config.settings.Settings` - Configuration access
- `threading.Thread`, `threading.Event`, `threading.RLock` - Thread management
- `asyncio` - Async/await event loop management

**This module is CALLED BY:**
- `server.py` - Flask initialization and route handlers
- `tests/test_service_manager.py` - Integration tests

---

## 4. DATA FLOW

```
Flask Request → ServiceManager.get_state()
                      ↓ (Thread-safe read)
                StateManager._state
                      ↑ (Async update)
              _hardware_loop (Thread)
                      ↑
              HardwareInterface.read()
                      ↑
              Physical Hardware
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

1. **Thread Separation** (System Constraint 1)
   - Hardware polling MUST run in separate thread from Flask
   - Never block Flask's main event loop

2. **Type Hints** (System Constraint 3)
   - All methods must include parameter and return type annotations
   - Use `List[HardwareInterface]` for service collection

3. **Error Resilience** (System Constraint 3)
   - Single hardware failure must not crash entire system
   - Database failures must not stop hardware operations

4. **No Direct Hardware in Flask** (Architecture Requirement)
   - Flask only calls `get_state()` - never `read()` directly
   - Service Manager owns all hardware lifecycle

---

## 6. ACCEPTANCE CRITERIA (Test Cases)

### Test Case 1: Basic Lifecycle
**Scenario:** Start and stop service manager with mock hardware

**Input:**
```python
config = Settings()
manager = ServiceManager(config)

mock_lidar = MockLidarService("lidar", config.LIDAR_PORT)
manager.register_hardware(mock_lidar)

manager.start()
time.sleep(2)  # Let hardware loop run
manager.stop()
```

**Expected Behavior:**
```python
assert manager.is_running() == False
assert mock_lidar.is_connected == False
# No exceptions raised
```

---

### Test Case 2: Thread-Safe State Access
**Scenario:** Concurrent reads while hardware loop updates state

**Input:**
```python
manager.start()

def reader_thread():
    for _ in range(100):
        state = manager.get_state()
        assert isinstance(state, dict)

threads = [Thread(target=reader_thread) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

**Expected Behavior:**
- No race conditions or corrupted data
- All reads return valid dictionaries

---

### Test Case 3: Emergency Stop Propagation
**Scenario:** E-stop triggers all hardware services

**Input:**
```python
mock_motor = MockMotorService("motor", config.MOTOR_PORT)
manager.register_hardware(mock_motor)
manager.start()

manager.emergency_stop()
time.sleep(0.2)  # Wait for hardware loop iteration
```

**Expected Behavior:**
```python
assert mock_motor.status == DeviceStatus.EMERGENCY_STOP
assert manager.get_state()["system"]["emergency_stop"] == True
```

---

### Test Case 4: Hardware Failure Isolation
**Scenario:** One service fails, others continue

**Input:**
```python
class FailingService(HardwareInterface):
    async def read(self):
        raise SerialException("Port disconnected")

failing = FailingService("broken", "/dev/ttyUSB9")
working = MockLidarService("lidar", "/dev/ttyUSB0")

manager.register_hardware(failing)
manager.register_hardware(working)
manager.start()
time.sleep(1)
```

**Expected Behavior:**
```python
state = manager.get_state()
assert state["broken"]["status"] == "error"
assert state["lidar"]["status"] == "ok"
# Manager still running despite one failure
assert manager.is_running() == True
```

---

### Test Case 5: Duplicate Device Registration
**Scenario:** Attempt to register two services with same device_id

**Input:**
```python
lidar1 = MockLidarService("lidar", "/dev/ttyUSB0")
lidar2 = MockLidarService("lidar", "/dev/ttyUSB1")

manager.register_hardware(lidar1)
manager.register_hardware(lidar2)  # Duplicate ID
```

**Expected Exception:** `ValueError`

**Expected Message:**
```
Device with ID 'lidar' already registered
```

---

## 7. PERFORMANCE REQUIREMENTS

**Method: `get_state()`**
- **Time Complexity:** O(1) for single device, O(n) for full state
- **Execution Time:** < 5ms (must not block Flask response)

**Method: `emergency_stop()`**
- **Time Complexity:** O(1)
- **Execution Time:** < 100ms (hard deadline per Safety Requirements)

**Hardware Loop:**
- **Poll Rate:** Configurable (1-100 Hz)
- **CPU Usage:** < 10% on Raspberry Pi 4

---

## 8. INTEGRATION WITH FLASK

**Example Usage in `server.py`:**

```python
from flask import Flask, jsonify
from src.core.service_manager import ServiceManager
from src.config.settings import Settings
from src.hardware.lidar.service import LidarService

app = Flask(__name__)
config = Settings()

# Initialize Service Manager (global scope)
service_manager = ServiceManager(config)
service_manager.register_hardware(LidarService("lidar", config.LIDAR_PORT))

@app.before_first_request
def startup():
    """Start hardware services when Flask initializes."""
    service_manager.start()

@app.route('/api/state')
def get_full_state():
    """Return complete system state."""
    return jsonify(service_manager.get_state())

@app.route('/api/lidar')
def get_lidar_data():
    """Return only LiDAR data."""
    data = service_manager.get_state(device_id="lidar")
    if data is None:
        return jsonify({"error": "LiDAR not available"}), 503
    return jsonify(data)

@app.route('/api/emergency_stop', methods=['POST'])
def trigger_emergency_stop():
    """Halt all hardware immediately."""
    service_manager.emergency_stop()
    return jsonify({"status": "emergency_stop_activated"})

@app.teardown_appcontext
def shutdown(exception=None):
    """Cleanup when Flask shuts down."""
    service_manager.stop()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## 9. IMPLEMENTATION NOTES

### For the Builder:

1. **Thread Management:**
   - Use `daemon=True` for background threads
   - Implement proper timeout logic in `stop()` method
   - Use `Event` instead of boolean flags for thread coordination

2. **Async in Threads:**
   - Each thread needs its own `asyncio.run()` call
   - Don't share event loops between threads
   - Use `asyncio.sleep()` not `time.sleep()` inside async functions

3. **Database Integration:**
   - Import `AsyncDatabaseEngine` from `src.services.database.core`
   - Handle database unavailability gracefully (log and continue)
   - Consider batching writes to reduce I/O overhead

4. **Error Logging:**
   - Use Python's `logging` module with structured format
   - Log all hardware errors to `shared_data["errors"]` list
   - Include timestamps and device IDs in error messages

5. **Graceful Degradation:**
   - If database unavailable, continue hardware operations
   - If one hardware service fails, others continue normally
   - Emergency stop takes precedence over all other operations

---

## 10. STATE MANAGER DEPENDENCY

**Required Interface from `src/core/state_manager.py`:**

```python
class StateManager:
    def update(self, device_id: str, data: Dict[str, Any]) -> None:
        """Update device state atomically."""
        pass
    
    def get(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve latest device reading."""
        pass
    
    def get_all(self) -> Dict[str, Any]:
        """Snapshot of entire system state."""
        pass
    
    def trigger_emergency_stop(self) -> None:
        """Set global E-stop flag."""
        pass
    
    def is_emergency_stopped(self) -> bool:
        """Check if E-stop active."""
        pass
```

**Note:** StateManager contract should be created separately if it doesn't exist.

---

**END OF CONTRACT**