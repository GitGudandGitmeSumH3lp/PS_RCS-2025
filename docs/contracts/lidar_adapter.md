# CONTRACT: LiDARAdapter
**Version:** 1.0
**Last Updated:** 2026-02-20
**Status:** Draft

---

## 1. PURPOSE

`LiDARAdapter` wraps the legacy `LiDARReader` class from `handler.py` and exposes a clean, `HardwareManager`-compliant interface for LiDAR sensor management. It eliminates all global state, enforces hardware abstraction behind a Manager-owned instance, and provides thread-safe scan data access and optional Socket.IO callback registration for real-time streaming. This module is the sole integration point between Flask routes and the physical LiDAR sensor.

---

## 2. PUBLIC INTERFACE

### Class: `LiDARAdapter`

**Location:** `backend/hardware/lidar_adapter.py`

---

### Method: `__init__`
**Signature:**
```python
def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
    """
    Initialize LiDARAdapter with optional configuration.

    Args:
        config: Optional dict with keys:
            - port (str): Serial port override. Default: auto-detect.
            - baudrate (int): Serial baud rate. Default: 115200.
            - max_queue_size (int): Internal point queue size. Default: 1000.
            - enable_simulation (bool): Use simulated data if True. Default: False.
    """
```

**Behavior Specification:**
- **Input Validation:** If `config` is provided, validate types for each known key. Raise `ValueError` on invalid type or out-of-range value (e.g., `baudrate <= 0`).
- **Processing Logic:** Store config into instance attributes. Initialize `threading.Lock` as `self._lock`. Do NOT open serial connection here. Lazy connection is mandatory.
- **Output Guarantee:** Adapter is in `disconnected`, `not scanning` state after `__init__`.
- **Side Effects:** None. No hardware access.

**Error Handling:**
- **Invalid config value type** → Raise `ValueError` with message `"LiDARAdapter config key '{key}' expects {expected_type}, got {actual_type}"`
- **Unsupported config key** → Log `WARNING: Unknown config key '{key}' ignored.` Do not raise.

---

### Method: `connect`
**Signature:**
```python
def connect(self) -> bool:
    """
    Establish serial connection to LiDAR hardware.

    Returns:
        bool: True if connection succeeded or was already connected. False on failure.
    """
```

**Behavior Specification:**
- **Input Validation:** None.
- **Processing Logic:** If already connected, return `True` immediately (idempotent). Otherwise, instantiate `LiDARReader(port, baudrate)` and call `LiDARReader.connect()`. Record `self._connect_time = time.monotonic()` on success.
- **Output Guarantee:** Returns `True` only if `serial_conn` is open and ready.
- **Side Effects:** Opens serial port. Sets `self._connected = True` on success.

**Error Handling:**
- **Serial port not found / OS error** → Log `ERROR`, set `self._last_error`, return `False`. Do NOT raise.
- **Already connected (idempotent call)** → Return `True`. Log `DEBUG: LiDARAdapter.connect() called while already connected.`

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

### Method: `disconnect`
**Signature:**
```python
def disconnect(self) -> bool:
    """
    Disconnect from LiDAR hardware and release serial port.

    Returns:
        bool: True if disconnected successfully or was already disconnected.
    """
```

**Behavior Specification:**
- **Input Validation:** None.
- **Processing Logic:** If scanning, call `stop_scanning()` first. Then call `LiDARReader.stop_scan()` to close serial. Set `self._connected = False` and `self._connect_time = None`. Idempotent — safe to call when already disconnected.
- **Output Guarantee:** After return, serial port is closed.
- **Side Effects:** Stops any active scanning thread. Closes serial connection.

**Error Handling:**
- **Exception during disconnect** → Log `ERROR`, set `self._last_error`, return `False`. Never raise.

---

### Method: `start_scanning`
**Signature:**
```python
def start_scanning(self) -> bool:
    """
    Begin continuous LiDAR scanning in a background thread.

    Returns:
        bool: True if scanning started or was already active. False on failure.
    """
```

**Behavior Specification:**
- **Input Validation:** Must be connected first. If not connected, attempt `connect()` automatically; fail with `False` if that fails.
- **Processing Logic:** If already scanning, return `True` (idempotent). Call `LiDARReader.start_scan()` which internally starts its own reader thread. Set `self._scanning = True`.
- **Output Guarantee:** Returns `True` only if background read thread is alive.
- **Side Effects:** Background `threading.Thread` started inside `LiDARReader`. No `asyncio`. Sets `self._scanning = True`.

**Error Handling:**
- **Not connected and auto-connect fails** → Log `ERROR: Cannot start scanning – connection failed.`, return `False`.
- **`LiDARReader.start_scan()` returns False** → Log `ERROR`, set `self._last_error`, return `False`.

---

### Method: `stop_scanning`
**Signature:**
```python
def stop_scanning(self) -> bool:
    """
    Stop LiDAR scanning and join background reader thread.

    Returns:
        bool: True if stopped successfully or was already stopped.
    """
```

**Behavior Specification:**
- **Input Validation:** None.
- **Processing Logic:** If not scanning, return `True` (idempotent). Set `self._reader._is_scanning = False`. Join `reader_thread` with a 3-second timeout. Set `self._scanning = False`.
- **Output Guarantee:** Reader thread is no longer running after return (within timeout window).
- **Side Effects:** Background thread stopped. `self._scanning = False`.

**Error Handling:**
- **Thread join timeout (>3s)** → Log `WARNING: LiDAR reader thread did not stop cleanly within 3s.` Still set `self._scanning = False` and return `True`. Do not block indefinitely.

---

### Method: `get_latest_scan`
**Signature:**
```python
def get_latest_scan(self) -> Dict[str, Any]:
    """
    Retrieve the most recent scan data in frontend-compatible format.

    Returns:
        dict: {
            'points': List[Dict],       # Each: {angle, distance, quality, x, y}
            'timestamp': float,          # Unix timestamp of retrieval
            'point_count': int,          # Number of points in this scan
            'obstacles': List[Dict]      # Points where distance < 1000mm
        }
        Returns empty structure (zero points) if not scanning or no data yet.
    """
```

**Behavior Specification:**
- **Input Validation:** None.
- **Processing Logic:** Acquire `self._lock`. Drain up to 360 points from `LiDARReader.data_queue` via `get_latest_data(max_points=360)`. Compute `x` and `y` for each point. Filter `obstacles` where `distance < 1000`. Build and return result dict.
- **Output Guarantee:** Always returns a valid dict with all four keys. Never returns `None`. Returns `{'points': [], 'timestamp': time.time(), 'point_count': 0, 'obstacles': []}` when no data is available.
- **Side Effects:** Drains points from internal queue (consuming them).

**Error Handling:**
- **Any exception during queue drain** → Log `ERROR`, return empty structure.

**Performance Requirements:**
- Time Complexity: O(n) where n = drained points (max 360)
- Space Complexity: O(n)

**Frontend Contract (JSON shape):**
```json
{
  "points": [
    {"angle": 45.0, "distance": 1200.0, "quality": 200, "x": 848.5, "y": 848.5}
  ],
  "timestamp": 1708470000.123,
  "point_count": 1,
  "obstacles": []
}
```

---

### Method: `get_status`
**Signature:**
```python
def get_status(self) -> Dict[str, Any]:
    """
    Return current adapter status.

    Returns:
        dict: {
            'connected': bool,
            'scanning': bool,
            'port': Optional[str],
            'error': Optional[str],
            'uptime': float           # Seconds since last connect. 0.0 if disconnected.
        }
    """
```

**Behavior Specification:**
- **Input Validation:** None.
- **Processing Logic:** Acquire `self._lock`. Read `self._connected`, `self._scanning`, `self._port`, `self._last_error`. Compute uptime as `time.monotonic() - self._connect_time` if connected, else `0.0`.
- **Output Guarantee:** Always returns a valid dict. Never raises.
- **Side Effects:** None.

**Error Handling:**
- **Any exception** → Return `{'connected': False, 'scanning': False, 'port': None, 'error': str(e), 'uptime': 0.0}`.

---

### Method: `register_callback`
**Signature:**
```python
def register_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
    """
    Register a callback to receive real-time scan data.
    Used by Socket.IO streaming task to push data to clients.

    Args:
        callback: Callable accepting one argument: the scan dict from get_latest_scan().

    Raises:
        TypeError: If callback is not callable.
    """
```

**Behavior Specification:**
- **Input Validation:** Raise `TypeError` if `callback` is not `callable(callback)`.
- **Processing Logic:** Store callback reference in `self._callback`. Only one callback is supported at a time; calling again replaces the previous one.
- **Output Guarantee:** Callback will be invoked from the background streaming thread each cycle when data is available.
- **Side Effects:** Sets `self._callback`. The streaming task reads this attribute from a background thread — access must be protected by `self._lock`.

**Error Handling:**
- **Not callable** → Raise `TypeError` with message `"callback must be callable, got {type(callback).__name__}"`
- **Exception raised inside callback during invocation** → Log `ERROR: LiDAR callback raised exception: {e}`. Do NOT crash the streaming thread.

---

## 3. DEPENDENCIES

**This module CALLS:**
- `LiDARReader.__init__()` — Instantiated during `connect()`
- `LiDARReader.connect()` — Opens serial port
- `LiDARReader.start_scan()` — Starts hardware reader thread
- `LiDARReader.stop_scan()` — Stops scanning and closes serial
- `LiDARReader.get_latest_data(max_points)` — Drains point queue
- `LiDARReader.data_queue.qsize()` — For status reporting

**This module is CALLED BY:**
- `HardwareManager.__init__()` — Instantiates `LiDARAdapter` during initialization
- `HardwareManager` (connection lifecycle) — Calls `connect()`, `disconnect()`, `start_scanning()`, `stop_scanning()`
- Flask route `/api/lidar/status` — Calls `get_status()`
- Flask route `/api/lidar/start` — Calls `start_scanning()`
- Flask route `/api/lidar/stop` — Calls `stop_scanning()`
- Socket.IO background streaming task — Calls `get_latest_scan()` and is registered via `register_callback()`

---

## 4. DATA STRUCTURES

```python
# Internal state attributes (not public, defined in __init__)
self._reader: Optional[LiDARReader]     # Wrapped legacy reader
self._lock: threading.Lock              # Guards all public method access
self._connected: bool                   # Current connection state
self._scanning: bool                    # Current scanning state
self._port: Optional[str]               # Resolved serial port string
self._baudrate: int                     # Configured baudrate
self._max_queue_size: int               # Queue capacity passed to LiDARReader
self._enable_simulation: bool           # Simulation mode flag
self._last_error: Optional[str]         # Last caught exception message
self._connect_time: Optional[float]     # time.monotonic() at last connect
self._callback: Optional[Callable]      # Registered Socket.IO callback
```

---

## 5. CONSTRAINTS (FROM SYSTEM CONSTRAINTS)

- **§1 No Global State:** `LiDARAdapter` instance MUST be owned by `HardwareManager`. No top-level `lidar_adapter` variable permitted in `server.py` or any route file.
- **§1 Concurrency – threading ONLY:** No `asyncio` anywhere in this module. Background thread (inside `LiDARReader`) uses `threading.Thread(daemon=True)`. Streaming task also uses `threading`.
- **§1 Hardware Abstraction:** No `serial` import in Flask route files. `LiDARAdapter` is the only permitted boundary.
- **§1 Non-Blocking Routes:** Flask routes `/api/lidar/start`, `/api/lidar/stop`, `/api/lidar/status` must return immediately. No polling loops inside routes.
- **§4 No Global State:** `lidar_reader` global from legacy `handler.py` (line 168) is explicitly prohibited. Must be eliminated.
- **§4 Type Hints Mandatory:** All method signatures must carry full type annotations.
- **§4 Docstrings:** Google-style docstrings required on all public methods.
- **§5.1 Max Function Length:** No method body may exceed 50 executable lines.
- **§6.2 Hardware Initialization:** Must not block main Flask thread on startup if LiDAR is not connected. `connect()` failure must be silent (log + return False).

---

## 6. MEMORY COMPLIANCE

No `_memory_snippet.txt` was provided. Memory compliance check skipped per protocol. Constraints above are sourced entirely from `system_constraints.md`.

---

## 7. ACCEPTANCE CRITERIA

**Test Case 1 – Successful Connect and Scan**
- Input: `LiDARAdapter()` → `connect()` → `start_scanning()`
- Expected: `connect()` returns `True`, `start_scanning()` returns `True`
- Expected Behavior: `get_status()` returns `{'connected': True, 'scanning': True, ...}`

**Test Case 2 – Idempotent connect()**
- Input: Call `connect()` twice
- Expected Output: Both calls return `True`
- Expected Behavior: No duplicate serial open; second call returns early with `DEBUG` log

**Test Case 3 – get_latest_scan() when not scanning**
- Input: `LiDARAdapter()` (no connect, no scan) → `get_latest_scan()`
- Expected Output: `{'points': [], 'timestamp': <float>, 'point_count': 0, 'obstacles': []}`
- Expected Behavior: Does not raise; returns empty structure

**Test Case 4 – Obstacle filtering**
- Input: Queue contains points with distances `[500, 1200, 800, 3000]`
- Expected: `obstacles` list contains only the two points where distance < 1000 (`500`, `800`)
- Expected Behavior: `point_count` == 4, `len(obstacles)` == 2

**Test Case 5 – register_callback with non-callable**
- Input: `register_callback("not_a_function")`
- Expected Exception: `TypeError`
- Expected Message: `"callback must be callable, got str"`

**Test Case 6 – stop_scanning() when not scanning (idempotent)**
- Input: `stop_scanning()` without prior `start_scanning()`
- Expected Output: Returns `True`
- Expected Behavior: No exception, no state corruption

**Test Case 7 – No global state violation**
- Audit Check: `grep -n "lidar_reader\s*=" server.py` returns no top-level assignments
- Expected Behavior: All access goes through `HardwareManager` instance

**Test Case 8 – Thread safety under concurrent reads**
- Input: 5 concurrent threads call `get_latest_scan()` simultaneously
- Expected Behavior: No race condition, no data corruption, all return valid dicts

---

## 8. SEQUENCE DIAGRAM

```
Flask Route (/api/lidar/start)
    │
    ▼
HardwareManager.start_lidar()
    │
    ├──► LiDARAdapter.connect()      [if not connected]
    │        │
    │        └──► LiDARReader.__init__(port, baudrate)
    │             LiDARReader.connect()  → opens serial port
    │
    └──► LiDARAdapter.start_scanning()
             │
             └──► LiDARReader.start_scan()
                      │
                      └──► threading.Thread(target=_read_data, daemon=True).start()


Socket.IO Streaming Task (background thread, 20fps / 50ms)
    │
    ├──► LiDARAdapter.get_latest_scan()
    │        │
    │        ├── acquire self._lock
    │        ├── LiDARReader.get_latest_data(max_points=360)
    │        │       └── drains data_queue
    │        ├── compute x, y, filter obstacles
    │        └── release self._lock
    │
    └──► invoke self._callback(scan_dict)
             │
             └──► socketio.emit('lidar_data', scan_dict)
```

---

## 9. CONFIGURATION SCHEMA

```python
DEFAULT_CONFIG = {
    "port": None,               # None → auto-detect via LiDARReader._find_lidar_port()
    "baudrate": 115200,         # int, > 0
    "max_queue_size": 1000,     # int, > 0, max points buffered internally
    "enable_simulation": False  # bool, use simulated data (future use)
}
```

Override via `HardwareManager` initialization, e.g.:
```python
lidar = LiDARAdapter(config={"port": "/dev/ttyUSB1", "baudrate": 115200})
```

---

## 10. FLASK ROUTE & SOCKET.IO INTEGRATION NOTES

### New Flask Routes Required (in `src/api/server.py`)

```python
GET  /api/lidar/status   → hardware_manager.lidar.get_status()
POST /api/lidar/start    → hardware_manager.lidar.start_scanning()
POST /api/lidar/stop     → hardware_manager.lidar.stop_scanning()
```

All routes must follow the existing `jsonify({'success': bool, ...})` response pattern.

### Socket.IO Namespace

Register callback once at app startup (not per-connection):
```python
hardware_manager.lidar.register_callback(
    lambda data: socketio.emit('lidar_data', data, namespace='/lidar')
)
```

The Socket.IO streaming thread (ported from `data_streaming_task()` in legacy `handler.py`) must be started as a `daemon=True` threading.Thread — NOT using `asyncio`.

### `/api/status` Update

The existing `/api/status` endpoint already includes `"lidar_connected": false`. Update server to populate this from `hardware_manager.lidar.get_status()['connected']`.

---

## 11. DEPENDENCIES (requirements.txt additions)

Verify or add the following:
```
flask-socketio>=5.3.0
pyserial>=3.5
eventlet>=0.33.0      # Or gevent — required for flask-socketio threading mode
```

⚠️ **Serial Port Conflict Risk:** Motor controller may also claim `/dev/ttyUSB0`. Implement a port reservation strategy or configure explicit `port` values in `.env`. Do not silently grab the first available port if the motor controller is already active.