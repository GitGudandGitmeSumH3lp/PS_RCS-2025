# Feature Specification: Hardware Abstraction Layer (HAL) & Service Manager

**Document Version:** 1.0  
**Date:** 2026-01-21  
**Status:** Draft  
**Author:** Lead Product Owner  

---

## 1. Executive Summary

This specification defines the architectural refactor to decouple Flask from direct hardware control by introducing:
- A **Config System** for environment-aware settings
- A **Hardware Abstraction Layer (HAL)** with standardized interfaces
- A **Service Manager** to orchestrate background hardware loops and database operations
- Clear **Integration Points** for Flask to consume hardware data thread-safely

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Flask App                           │
│                       (server.py)                           │
└──────────────┬──────────────────────────────────────────────┘
               │ Read-Only Access
               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Manager                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Hardware   │  │   Database   │  │   State      │     │
│  │   Loop       │  │   Loop       │  │   Manager    │     │
│  │  (Thread)    │  │  (Thread)    │  │ (Thread-Safe)│     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│              Hardware Abstraction Layer (HAL)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  LiDAR   │  │  Husky   │  │  Motor   │  │ Base HW  │   │
│  │ Service  │  │ Service  │  │ Service  │  │Interface │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│         Physical Hardware (USB/Serial Devices)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Component Specification

### 3.1 Config System

**File:** `src/config/settings.py`

**Requirements:**
- Use **Pydantic Settings v2** for type-safe configuration
- Load from `.env` file with sensible defaults
- Support environment-specific overrides (dev, prod, test)
- Validate serial ports exist before service startup

**Configuration Schema:**

```python
# Required Fields
DATABASE_URL: str              # PostgreSQL connection string
LIDAR_PORT: str                # e.g., "/dev/ttyUSB0"
HUSKY_PORT: str                # e.g., "/dev/ttyUSB1"
MOTOR_PORT: str                # e.g., "/dev/ttyACM0"

# Optional with Defaults
LOG_LEVEL: str = "INFO"
HARDWARE_POLL_RATE_HZ: int = 10
DB_POOL_SIZE: int = 5
EMERGENCY_STOP_GPIO_PIN: int | None = None
ENABLE_HARDWARE: bool = True   # False for testing without devices
```

**Validation Rules:**
1. Serial ports must match pattern `/dev/tty*`
2. `DATABASE_URL` must be valid PostgreSQL URI
3. Poll rate must be 1-100 Hz
4. If `EMERGENCY_STOP_GPIO_PIN` is set, validate GPIO availability

**Example `.env`:**
```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/robotics
LIDAR_PORT=/dev/ttyUSB0
HUSKY_PORT=/dev/ttyUSB1
MOTOR_PORT=/dev/ttyACM0
HARDWARE_POLL_RATE_HZ=20
LOG_LEVEL=DEBUG
```

---

### 3.2 Base Hardware Interface

**File:** `src/hardware/base.py`

**Abstract Base Class:**

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime

class HardwareInterface(ABC):
    """Base class all hardware drivers must inherit from."""
    
    def __init__(self, device_id: str, port: str):
        self.device_id = device_id
        self.port = port
        self._is_connected = False
        self._last_reading = None
        self._error_state = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to hardware. Return success status."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Safely close hardware connection."""
        pass
    
    @abstractmethod
    async def read(self) -> Dict[str, Any]:
        """
        Read current sensor data.
        Returns: {
            "timestamp": datetime,
            "device_id": str,
            "data": {...},  # Device-specific payload
            "status": "ok" | "error"
        }
        """
        pass
    
    @abstractmethod
    async def emergency_stop(self) -> None:
        """Immediately halt hardware (motors, actuators)."""
        pass
    
    @property
    def is_connected(self) -> bool:
        return self._is_connected
    
    @property
    def last_reading(self) -> Dict[str, Any] | None:
        return self._last_reading
```

**Concrete Implementations:**
- `LidarService(HardwareInterface)` → Returns distance arrays
- `HuskyService(HardwareInterface)` → Returns IMU/Odometry data
- `MotorService(HardwareInterface)` → Accepts velocity commands

---

### 3.3 State Manager

**File:** `src/core/state_manager.py`

**Purpose:** Thread-safe storage for latest hardware readings and system state.

**Implementation:**

```python
from threading import RLock
from typing import Dict, Any
from datetime import datetime

class StateManager:
    """Thread-safe state container for hardware data."""
    
    def __init__(self):
        self._state: Dict[str, Any] = {
            "lidar": None,
            "husky": None,
            "motor": None,
            "system": {
                "emergency_stop": False,
                "started_at": datetime.utcnow(),
                "errors": []
            }
        }
        self._lock = RLock()
    
    def update(self, device_id: str, data: Dict[str, Any]) -> None:
        """Update device state atomically."""
        with self._lock:
            self._state[device_id] = {
                "data": data,
                "updated_at": datetime.utcnow()
            }
    
    def get(self, device_id: str) -> Dict[str, Any] | None:
        """Retrieve latest device reading."""
        with self._lock:
            return self._state.get(device_id)
    
    def get_all(self) -> Dict[str, Any]:
        """Snapshot of entire system state."""
        with self._lock:
            return self._state.copy()
    
    def trigger_emergency_stop(self) -> None:
        """Set global E-stop flag."""
        with self._lock:
            self._state["system"]["emergency_stop"] = True
    
    def is_emergency_stopped(self) -> bool:
        with self._lock:
            return self._state["system"]["emergency_stop"]
```

---

### 3.4 Service Manager

**File:** `src/core/service_manager.py`

**Responsibilities:**
1. Initialize all hardware services
2. Start background threads for hardware polling and database operations
3. Coordinate shutdown and emergency stop
4. Provide Flask with read-only access to `StateManager`

**Architecture:**

```python
import asyncio
from threading import Thread, Event
from typing import List
from src.hardware.base import HardwareInterface
from src.database.engine import AsyncDatabaseEngine
from src.core.state_manager import StateManager
from src.config.settings import Settings

class ServiceManager:
    """Orchestrates hardware services and database operations."""
    
    def __init__(self, config: Settings):
        self.config = config
        self.state = StateManager()
        self.db_engine = AsyncDatabaseEngine(config.DATABASE_URL)
        
        self.hardware_services: List[HardwareInterface] = []
        self._stop_event = Event()
        self._threads: List[Thread] = []
    
    def register_hardware(self, service: HardwareInterface) -> None:
        """Add hardware service to managed pool."""
        self.hardware_services.append(service)
    
    async def _hardware_loop(self) -> None:
        """Background task: Poll all hardware at configured rate."""
        while not self._stop_event.is_set():
            for service in self.hardware_services:
                try:
                    if self.state.is_emergency_stopped():
                        await service.emergency_stop()
                        continue
                    
                    data = await service.read()
                    self.state.update(service.device_id, data)
                
                except Exception as e:
                    self.state.update(service.device_id, {
                        "status": "error",
                        "message": str(e)
                    })
            
            await asyncio.sleep(1 / self.config.HARDWARE_POLL_RATE_HZ)
    
    async def _database_loop(self) -> None:
        """Background task: Persist state snapshots to DB."""
        while not self._stop_event.is_set():
            try:
                snapshot = self.state.get_all()
                # Use AsyncDatabaseEngine to save snapshot
                await self.db_engine.save_snapshot(snapshot)
            except Exception as e:
                print(f"DB Error: {e}")
            
            await asyncio.sleep(1.0)  # Persist every 1 second
    
    def start(self) -> None:
        """Initialize services and start background threads."""
        # Connect all hardware
        for service in self.hardware_services:
            asyncio.run(service.connect())
        
        # Start threads
        hw_thread = Thread(target=self._run_async_loop, args=(self._hardware_loop,))
        db_thread = Thread(target=self._run_async_loop, args=(self._database_loop,))
        
        hw_thread.daemon = True
        db_thread.daemon = True
        
        hw_thread.start()
        db_thread.start()
        
        self._threads = [hw_thread, db_thread]
    
    def stop(self) -> None:
        """Graceful shutdown of all services."""
        self._stop_event.set()
        
        # Disconnect hardware
        for service in self.hardware_services:
            asyncio.run(service.disconnect())
        
        # Wait for threads
        for thread in self._threads:
            thread.join(timeout=5.0)
    
    def emergency_stop(self) -> None:
        """Trigger immediate hardware halt."""
        self.state.trigger_emergency_stop()
    
    @staticmethod
    def _run_async_loop(coro):
        """Helper to run async coroutine in thread."""
        asyncio.run(coro)
```

---

### 3.5 Integration with Flask

**File:** `server.py` (Refactored)

**Changes:**
1. Remove direct hardware script calls
2. Initialize `ServiceManager` at startup
3. Expose read-only state via API endpoints

**Example Integration:**

```python
from flask import Flask, jsonify
from src.core.service_manager import ServiceManager
from src.config.settings import Settings
from src.hardware.lidar_service import LidarService
from src.hardware.husky_service import HuskyService

app = Flask(__name__)
config = Settings()

# Initialize Service Manager
service_manager = ServiceManager(config)
service_manager.register_hardware(LidarService("lidar", config.LIDAR_PORT))
service_manager.register_hardware(HuskyService("husky", config.HUSKY_PORT))

@app.before_first_request
def startup():
    service_manager.start()

@app.route('/api/state')
def get_state():
    """Return current system state."""
    return jsonify(service_manager.state.get_all())

@app.route('/api/lidar')
def get_lidar():
    """Return latest LiDAR reading."""
    data = service_manager.state.get("lidar")
    if data is None:
        return jsonify({"error": "No data available"}), 503
    return jsonify(data)

@app.route('/api/emergency_stop', methods=['POST'])
def emergency_stop():
    """Trigger global emergency stop."""
    service_manager.emergency_stop()
    return jsonify({"status": "emergency_stop_activated"})

@app.teardown_appcontext
def shutdown(exception=None):
    service_manager.stop()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## 4. Safety Requirements

### 4.1 Emergency Stop Mechanism

**Trigger Conditions:**
1. Manual API call to `/api/emergency_stop`
2. GPIO button press (if configured)
3. Critical hardware error detected

**Behavior:**
- Set `StateManager.emergency_stop = True`
- Call `emergency_stop()` on all hardware services
- Motors: Set velocity to 0
- Sensors: Enter safe read-only mode
- Log event to database

### 4.2 Error Handling

**Hardware Failures:**
- If `service.read()` throws exception, mark device as `status: "error"`
- Continue polling other devices
- Flask returns 503 for unavailable devices

**Database Failures:**
- Log error but continue hardware operations
- State remains available via `StateManager`

---

## 5. Testing Strategy

### 5.1 Unit Tests
- `test_state_manager.py`: Thread-safety under concurrent access
- `test_config.py`: Validation of invalid `.env` values
- `test_base_hardware.py`: Mock implementations of `HardwareInterface`

### 5.2 Integration Tests
- `test_service_manager.py`: Full lifecycle (start, poll, stop)
- `test_emergency_stop.py`: Verify all services halt correctly

### 5.3 Hardware Mocking
- Use `ENABLE_HARDWARE=False` for CI/CD
- Implement `MockLidarService` that returns synthetic data

---

## 6. Migration Plan

### Phase 1: Config & Base Classes (Week 1)
- Implement `settings.py` with Pydantic
- Create `HardwareInterface` ABC
- Build `StateManager`

### Phase 2: Hardware Services (Week 2)
- Refactor existing scripts into `LidarService`, `HuskyService`, `MotorService`
- Unit test each service in isolation

### Phase 3: Service Manager (Week 3)
- Implement thread orchestration
- Integrate with `AsyncDatabaseEngine`
- Add emergency stop logic

### Phase 4: Flask Integration (Week 4)
- Refactor `server.py` to use `ServiceManager`
- Remove legacy script calls
- Deploy to staging environment

---

## 7. Success Metrics

- **Decoupling:** Flask endpoints contain zero direct hardware calls
- **Reliability:** System survives hardware disconnection/reconnection
- **Performance:** Hardware polling maintains 20 Hz without thread blocking
- **Safety:** Emergency stop responds within 100ms

---

## 8. Open Questions

1. **Database Schema:** Should snapshots be stored as JSON or normalized tables?
2. **GPIO Integration:** Should we use `gpiozero` or direct `/sys/class/gpio`?
3. **Logging:** Centralized logging format (JSON structured logs)?

---

**Appendix A: File Structure**
```
project_root/
├── src/
│   ├── config/
│   │   └── settings.py          # Pydantic config
│   ├── core/
│   │   ├── state_manager.py     # Thread-safe state
│   │   └── service_manager.py   # Orchestrator
│   ├── hardware/
│   │   ├── base.py              # Abstract interface
│   │   ├── lidar_service.py
│   │   ├── husky_service.py
│   │   └── motor_service.py
│   └── database/
│       └── engine.py            # AsyncDatabaseEngine
├── server.py                    # Refactored Flask app
├── .env                         # Config values
└── tests/
    ├── test_state_manager.py
    └── test_service_manager.py
```

---

**Document End**