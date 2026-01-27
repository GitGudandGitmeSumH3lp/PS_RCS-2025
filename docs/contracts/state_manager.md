# CONTRACT: State Manager
**Version:** 1.0
**Last Updated:** 2026-01-21
**Status:** Draft - Awaiting Approval

## 1. PURPOSE
Provides thread-safe in-memory storage for real-time hardware sensor readings and system state. This module serves as the central state repository accessed by both the ServiceManager's background threads and Flask's read-only API endpoints, ensuring atomic updates and consistent snapshots across concurrent operations.

## 2. PUBLIC INTERFACE

### Class: `StateManager`
**Signature:**
```python
from threading import RLock
from typing import Dict, Any, Optional
from datetime import datetime

class StateManager:
    """
    Thread-safe state container for hardware data and system status.
    
    Attributes:
        _state: Internal dictionary storing device readings and system metadata
        _lock: Reentrant lock for thread-safe operations
    """
    
    def __init__(self):
        """
        Initialize empty state with system metadata section.
        
        Initial state structure:
        {
            "lidar": None,
            "husky": None,
            "motor": None,
            "system": {
                "emergency_stop": False,
                "started_at": datetime.utcnow(),
                "errors": []
            }
        }
        """
```

**Behavior Specification:**
- **Input Validation:** N/A (no parameters)
- **Processing Logic:**
  - Creates RLock (reentrant to prevent deadlock if same thread re-acquires)
  - Initializes state dict with device slots (None) and system section
  - Records startup timestamp in UTC
- **Output Guarantee:** StateManager instance ready for concurrent access
- **Side Effects:** None

---

### Method: `update`
**Signature:**
```python
def update(self, device_id: str, data: Dict[str, Any]) -> None:
    """
    Atomically update the state for a specific device.
    
    Args:
        device_id: Device identifier (e.g., "lidar", "husky", "motor")
        data: Device reading dictionary containing sensor data
    
    Raises:
        ValueError: If device_id is empty string or None
        TypeError: If data is not a dictionary
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `device_id` must be non-empty string
  - `data` must be dict type
  - Raises `ValueError` if `device_id` is `""` or `None`
  - Raises `TypeError` if `data` is not dict
- **Processing Logic:**
  - Acquire lock
  - Store data wrapped with metadata: `{"data": data, "updated_at": datetime.utcnow()}`
  - Release lock (automatic via context manager)
- **Output Guarantee:** Device state updated atomically with timestamp
- **Side Effects:** Modifies `_state[device_id]` in-place

**Error Handling:**
- **Empty device_id:** `device_id in ["", None]` → Raise `ValueError` with message "device_id cannot be empty"
- **Invalid data type:** `not isinstance(data, dict)` → Raise `TypeError` with message "data must be a dictionary"

**Performance Requirements:**
- Time Complexity: O(1) - dictionary assignment
- Space Complexity: O(1) - single dict entry

---

### Method: `get`
**Signature:**
```python
def get(self, device_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the latest reading for a specific device.
    
    Args:
        device_id: Device identifier to query
    
    Returns:
        Dictionary containing:
        {
            "data": {...},           # Device-specific payload
            "updated_at": datetime   # Timestamp of last update
        }
        Returns None if device has no data or device_id is invalid.
    
    Raises:
        ValueError: If device_id is empty string or None
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `device_id` must be non-empty string
  - Raises `ValueError` if `device_id` is `""` or `None`
- **Processing Logic:**
  - Acquire lock
  - Retrieve `_state.get(device_id)`
  - Release lock
- **Output Guarantee:** Returns copy of device state or None if not found
- **Side Effects:** None (read-only operation)

**Error Handling:**
- **Empty device_id:** `device_id in ["", None]` → Raise `ValueError` with message "device_id cannot be empty"

**Performance Requirements:**
- Time Complexity: O(1) - dictionary lookup
- Space Complexity: O(1)

---

### Method: `get_all`
**Signature:**
```python
def get_all(self) -> Dict[str, Any]:
    """
    Retrieve a snapshot of the entire system state.
    
    Returns:
        Deep copy of complete state dictionary containing all device
        readings and system metadata. Safe to modify without affecting
        internal state.
    
    Example return value:
    {
        "lidar": {"data": {...}, "updated_at": datetime},
        "husky": {"data": {...}, "updated_at": datetime},
        "motor": None,  # No data received yet
        "system": {
            "emergency_stop": False,
            "started_at": datetime,
            "errors": []
        }
    }
    """
```

**Behavior Specification:**
- **Input Validation:** N/A (no parameters)
- **Processing Logic:**
  - Acquire lock
  - Create shallow copy of `_state` dictionary
  - Release lock
- **Output Guarantee:** Returns consistent snapshot of all state at call time
- **Side Effects:** None (read-only operation)

**Performance Requirements:**
- Time Complexity: O(n) where n = number of devices (typically 3-5)
- Space Complexity: O(n) for the copied dictionary

**Thread Safety Note:**
The copy operation is atomic under lock, ensuring callers receive a consistent view even if updates occur immediately after.

---

### Method: `trigger_emergency_stop`
**Signature:**
```python
def trigger_emergency_stop(self) -> None:
    """
    Set the global emergency stop flag.
    
    This method is idempotent - calling multiple times has same effect as once.
    Once set to True, flag persists until system restart (no reset mechanism).
    """
```

**Behavior Specification:**
- **Input Validation:** N/A
- **Processing Logic:**
  - Acquire lock
  - Set `_state["system"]["emergency_stop"] = True`
  - Release lock
- **Output Guarantee:** Emergency stop flag is set to True
- **Side Effects:** Modifies system state; ServiceManager will halt hardware on next poll

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

### Method: `is_emergency_stopped`
**Signature:**
```python
def is_emergency_stopped(self) -> bool:
    """
    Check current emergency stop status.
    
    Returns:
        True if emergency stop has been triggered, False otherwise
    """
```

**Behavior Specification:**
- **Input Validation:** N/A
- **Processing Logic:**
  - Acquire lock
  - Read `_state["system"]["emergency_stop"]`
  - Release lock
- **Output Guarantee:** Returns current emergency stop flag state
- **Side Effects:** None (read-only operation)

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

### Method: `add_error`
**Signature:**
```python
def add_error(self, error_message: str, device_id: Optional[str] = None) -> None:
    """
    Record a system or device error.
    
    Args:
        error_message: Human-readable error description
        device_id: Optional device that caused error (for context)
    
    Raises:
        ValueError: If error_message is empty string or None
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `error_message` must be non-empty string
  - Raises `ValueError` if empty
- **Processing Logic:**
  - Acquire lock
  - Append error dict to `_state["system"]["errors"]`:
    ```python
    {
        "timestamp": datetime.utcnow(),
        "message": error_message,
        "device_id": device_id  # None if system-level error
    }
    ```
  - Release lock
- **Output Guarantee:** Error recorded with timestamp
- **Side Effects:** Modifies `_state["system"]["errors"]` list

**Error Handling:**
- **Empty message:** `error_message in ["", None]` → Raise `ValueError` with message "error_message cannot be empty"

**Performance Requirements:**
- Time Complexity: O(1) - list append
- Space Complexity: O(1) per error

---

## 3. DEPENDENCIES

**This module CALLS:**
- `threading.RLock()` - Reentrant lock creation
- `datetime.datetime.utcnow()` - Timestamp generation
- `copy.copy()` - Shallow dictionary copying (implied by `.copy()`)

**This module is CALLED BY:**
- `src/core/service_manager.py` - Background threads update state during hardware polling
- `server.py` - Flask endpoints read state for API responses

---

## 4. DATA STRUCTURES

### State Dictionary Structure
```python
StateDict = {
    "lidar": Optional[DeviceReading],
    "husky": Optional[DeviceReading],
    "motor": Optional[DeviceReading],
    "system": SystemMetadata
}

DeviceReading = {
    "data": Dict[str, Any],        # Device-specific sensor data
    "updated_at": datetime          # UTC timestamp of reading
}

SystemMetadata = {
    "emergency_stop": bool,         # Global E-stop flag
    "started_at": datetime,         # Service start time (UTC)
    "errors": List[ErrorRecord]     # Accumulated errors
}

ErrorRecord = {
    "timestamp": datetime,          # UTC timestamp of error
    "message": str,                 # Error description
    "device_id": Optional[str]      # Device that caused error (if applicable)
}
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

- **Thread Safety Paramount:** All public methods MUST acquire `_lock` before accessing `_state`
- **No external dependencies:** Only stdlib modules (`threading`, `datetime`, `typing`)
- **Type hints required:** All method signatures must have complete type annotations
- **Immutable reads:** `get()` and `get_all()` return copies, never direct references to internal state
- **No hardcoded device IDs:** Device identifiers passed as parameters, not hardcoded

---

## 6. MEMORY COMPLIANCE (FROM PROJECT MEMORY)

**Applied Rules:**
- **[HAL Spec Section 3.3]:** StateManager uses `threading.RLock` (not `Lock`) to prevent deadlock in reentrant scenarios
- **[HAL Spec Section 3.3]:** Structure matches ServiceManager's expected interface exactly
- **[HAL Spec Section 4.1]:** Emergency stop mechanism integrated as system-level flag

---

## 7. ACCEPTANCE CRITERIA (Test Cases)

**Test Case 1:** Thread-Safe Concurrent Updates
- Input: 10 threads simultaneously call `update("lidar", {...})` with different data
- Expected Output: All 10 updates complete without exception
- Expected Behavior: Final state contains data from one of the updates (last writer wins)

**Test Case 2:** Read During Write
- Input: Thread A calls `update()` while Thread B calls `get_all()`
- Expected Output: Both operations complete without blocking indefinitely
- Expected Behavior: `get_all()` returns consistent snapshot (either before or after update, never partial)

**Test Case 3:** Emergency Stop Idempotency
- Input: Call `trigger_emergency_stop()` three times
- Expected Output: `is_emergency_stopped()` returns True
- Expected Behavior: No errors, no duplicate side effects

**Test Case 4:** Invalid Device ID
- Input: `update("", {"value": 42})`
- Expected Exception: `ValueError`
- Expected Message: "device_id cannot be empty"

**Test Case 5:** Get Nonexistent Device
- Input: `get("nonexistent_device")`
- Expected Output: `None`
- Expected Behavior: No exception raised

**Test Case 6:** Error Logging
- Input: `add_error("Sensor timeout", device_id="lidar")`
- Expected Output: `get_all()["system"]["errors"]` contains 1 entry with timestamp, message, device_id
- Expected Behavior: Error persists across subsequent calls

---

## 8. IMPLEMENTATION NOTES

### Why RLock vs Lock?
Using `threading.RLock` (reentrant lock) instead of `Lock` prevents deadlock if the same thread needs to acquire the lock multiple times (e.g., if a method calls another method on the same instance).

### Memory Considerations
The `errors` list grows unbounded. For production, consider:
- Max error list size (e.g., keep last 100 errors)
- Error log rotation or persistence to database

### Performance Optimization
For high-frequency polling (20+ Hz):
- Lock contention is minimal with short critical sections
- Consider `get_all()` caching if Flask polls faster than hardware updates

### Integration with ServiceManager
Expected usage pattern:
```python
# In ServiceManager._hardware_loop()
try:
    data = await service.read()
    state_manager.update(service.device_id, data)
except Exception as e:
    state_manager.add_error(str(e), device_id=service.device_id)
    if critical_error:
        state_manager.trigger_emergency_stop()
```

### Testing Strategy
- Use `threading.Thread` in tests to simulate concurrent access
- Use `time.sleep()` to create race conditions
- Mock `datetime.utcnow()` for deterministic timestamp testing

---

# ADDENDUM: DATABASE CORE CONTRACT UPDATE

## NEW METHOD: `save_snapshot`

Add the following method to `AsyncDatabaseEngine` class in `docs/contracts/database_core.md`:

### Method: `save_snapshot`
**Signature:**
```python
async def save_snapshot(self, data: Dict[str, Any]) -> None:
    """
    Persist a StateManager snapshot to the database.
    
    This method stores the complete system state (all device readings and
    system metadata) as a single JSON blob for historical analysis and
    system recovery.
    
    Args:
        data: Complete state dictionary from StateManager.get_all()
              Expected structure:
              {
                  "lidar": {"data": {...}, "updated_at": "..."},
                  "husky": {"data": {...}, "updated_at": "..."},
                  "motor": {"data": {...}, "updated_at": "..."},
                  "system": {
                      "emergency_stop": bool,
                      "started_at": "...",
                      "errors": [...]
                  }
              }
    
    Raises:
        ValueError: If data is None or empty dictionary
        DatabaseSessionError: If snapshot insertion fails
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `data` must be non-None dict
  - `data` must not be empty dict (`{}`)
  - Raises `ValueError` if validation fails
- **Processing Logic:**
  1. Convert datetime objects to ISO 8601 strings for JSON serialization
  2. Create new `Snapshot` ORM record with:
     - `snapshot_data`: JSON string of complete state
     - `created_at`: Server-side timestamp (automatic)
  3. Insert via async session
  4. Commit transaction
- **Output Guarantee:** State persisted to database with timestamp
- **Side Effects:** Inserts one row into `snapshots` table

**Error Handling:**
- **None or empty data:** `data is None or data == {}` → Raise `ValueError` with message "data cannot be None or empty"
- **Session failure:** Any exception during insert → Raise `DatabaseSessionError` with original exception wrapped
- **JSON serialization failure:** datetime not converted → Log warning, skip problematic device

**Performance Requirements:**
- Time Complexity: O(n) where n = size of data dict (JSON serialization)
- Space Complexity: O(n) for JSON string storage

**Storage Decision:** JSON Blob Approach

After analyzing the HAL spec requirements, the JSON blob approach is chosen for the following reasons:

1. **Simplicity:** StateManager returns pre-structured dict; no normalization needed
2. **Flexibility:** Schema can evolve without migrations (new devices, new fields)
3. **Performance:** Single INSERT operation vs. multiple normalized inserts
4. **Use Case Alignment:** Snapshots are for historical analysis, not transactional queries
5. **Recovery:** Complete system state in one record simplifies disaster recovery

**Alternative (Rejected):** Normalized tables would require:
- Separate `device_snapshots` table with FK to `snapshots`
- Complex JOIN queries to reconstruct state
- Migration overhead when device schema changes

**New ORM Model Required:**

Add the following class to `src/services/database/core.py`:

```python
from sqlalchemy import Text
import json

class Snapshot(Base, BaseMixin):
    """
    Represents a point-in-time snapshot of entire system state.
    Used for historical analysis and system recovery.
    """
    
    __tablename__ = "snapshots"
    
    snapshot_data: Mapped[str] = mapped_column(Text, nullable=False)
    
    def set_data(self, state_dict: Dict[str, Any]) -> None:
        """
        Serialize StateManager dictionary to JSON string.
        Handles datetime conversion automatically.
        """
        # Convert datetimes to ISO strings
        serializable = self._convert_datetimes(state_dict)
        self.snapshot_data = json.dumps(serializable)
    
    def get_data(self) -> Dict[str, Any]:
        """
        Deserialize JSON string back to dictionary.
        Converts ISO strings back to datetime objects.
        """
        data = json.loads(self.snapshot_data)
        return self._restore_datetimes(data)
    
    @staticmethod
    def _convert_datetimes(obj):
        """Recursively convert datetime objects to ISO strings."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: Snapshot._convert_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [Snapshot._convert_datetimes(item) for item in obj]
        return obj
    
    @staticmethod
    def _restore_datetimes(obj):
        """Recursively convert ISO strings to datetime objects."""
        if isinstance(obj, str):
            try:
                return datetime.fromisoformat(obj)
            except (ValueError, AttributeError):
                return obj
        elif isinstance(obj, dict):
            return {k: Snapshot._restore_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [Snapshot._restore_datetimes(item) for item in obj]
        return obj
```

**Integration with ServiceManager:**

Example usage in `src/core/service_manager.py`:

```python
async def _database_loop(self) -> None:
    """Background task: Persist state snapshots to DB."""
    while not self._stop_event.is_set():
        try:
            snapshot_data = self.state.get_all()
            await self.db_engine.save_snapshot(snapshot_data)
        except ValueError as e:
            print(f"Invalid snapshot data: {e}")
        except DatabaseSessionError as e:
            print(f"DB save failed: {e}")
        
        await asyncio.sleep(1.0)  # Persist every 1 second
```

**Database Schema Migration:**

```sql
-- Add to migration script
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    snapshot_data TEXT NOT NULL,  -- JSON blob
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_snapshots_created_at ON snapshots(created_at);
```

**Query Examples:**

```python
# Retrieve last 10 snapshots
async with db_engine.get_session() as session:
    result = await session.execute(
        select(Snapshot)
        .order_by(Snapshot.created_at.desc())
        .limit(10)
    )
    snapshots = result.scalars().all()
    
    for snapshot in snapshots:
        state = snapshot.get_data()
        print(f"Snapshot at {snapshot.created_at}: {state['system']['emergency_stop']}")

# Find snapshots during emergency stops
async with db_engine.get_session() as session:
    result = await session.execute(
        select(Snapshot)
        .where(Snapshot.snapshot_data.like('%"emergency_stop": true%'))
    )
    emergency_snapshots = result.scalars().all()
```

**Acceptance Criteria for save_snapshot:**

**Test Case 1:** Valid Snapshot Insertion
- Input: `save_snapshot(state_manager.get_all())`
- Expected Output: No exception, snapshot record created
- Expected Behavior: `snapshots` table contains 1 new row with JSON data

**Test Case 2:** Datetime Serialization
- Input: Snapshot with `updated_at` datetime objects
- Expected Output: JSON contains ISO 8601 strings (e.g., "2026-01-21T10:30:00")
- Expected Behavior: Data can be deserialized back to datetime objects

**Test Case 3:** Empty Data Rejection
- Input: `save_snapshot({})`
- Expected Exception: `ValueError`
- Expected Message: "data cannot be None or empty"

**Test Case 4:** Round-Trip Data Integrity
- Input: Save snapshot, retrieve via `get_data()`
- Expected Output: Retrieved dict matches original (including datetime types)
- Expected Behavior: No data loss during serialization/deserialization

**Test Case 5:** Concurrent Snapshot Saves
- Input: Two threads save snapshots simultaneously
- Expected Output: Both snapshots persisted with different timestamps
- Expected Behavior: No database lock contention or lost writes