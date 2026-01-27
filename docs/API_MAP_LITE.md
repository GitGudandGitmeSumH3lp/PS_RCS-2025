```markdown
# API MAP (LITE) - PS_RCS_PROJECT
**Version:** 4.0 (Unified Backend)
**Status:** Active Source of Truth

---

## 1. EXTERNAL HTTP INTERFACE (Flask)
**Base URL:** `/api`
**Consumer:** `frontend/neural-core.js`

### 📡 Telemetry & Status
**Endpoint:** `GET /api/status`
**Description:** Returns real-time sensor data and connection states.
**Response Model:**
```json
{
  "mode": "manual",              // "manual" | "auto"
  "battery_voltage": 12.4,       // float
  "cpu_temp": 45.2,              // float (optional)
  "connections": {
    "motor": true,               // boolean
    "lidar": false,              // boolean
    "camera": false              // boolean
  },
  "active_task": null            // string | null
}
```

### ⚙️ Motor Control
**Endpoint:** `POST /api/motor/control`
**Description:** Execute movement commands.
**Request Model:**
```json
{
  "command": "forward",          // "forward"|"backward"|"left"|"right"|"stop"
  "speed": 100                   // int (0-255), optional, defaults to current
}
```
**Response:** `{"success": true, "message": "Moving forward"}`

### ⚙️ Motor Speed
**Endpoint:** `POST /api/motor/speed`
**Description:** Set global speed limit.
**Request Model:** `{"speed": 150}`
**Response:** `{"success": true, "speed": 150}`

### 🪵 System Logs (Database)
**Endpoint:** `GET /api/logs`
**Query Params:** `?limit=10`
**Description:** Fetch recent system events from SQLite.
**Response:**
```json
[
  {"id": 1, "timestamp": "2026-01-23 10:00:00", "level": "INFO", "message": "System Boot"}
]
```

---

## 2. INTERNAL PYTHON MODULES (Backend)
**Root:** `backend/`

### 🧠 `HardwareManager` (Singleton)
**File:** `backend/hardware_manager.py`
**Usage:** The ONLY class allowed to touch hardware.
*   `init_hardware() -> None`
*   `move(direction: str, speed: int) -> bool`
*   `stop() -> None`
*   `get_status() -> dict` (Returns dict for `/api/status`)
*   `cleanup() -> None`

### 💾 `DatabaseManager`
**File:** `backend/database.py`
**Usage:** Thread-safe SQLite access.
*   `log_event(level: str, message: str) -> None`
*   `get_recent_logs(limit: int) -> list[dict]`
*   `save_sensor_data(type: str, value: any) -> None`

### 🤖 `LegacyMotorAdapter`
**File:** `backend/adapters/motor_adapter.py`
**Usage:** Wraps the old `motor_controller.py`.
*   `forward(speed: int)`
*   `backward(speed: int)`
*   `left(speed: int)`
*   `right(speed: int)`
*   `stop()`

---

## 3. FRONTEND MODULES (Client)
**Root:** `frontend/`

### 🧠 `NeuralInterface` (Class)
**File:** `static/js/neural-core.js`
*   `pollStatus()`: Fetches `/api/status` loop.
*   `sendCommand(cmd)`: POSTs to `/api/motor/control`.
*   `updateDashboard(data)`: Updates DOM elements.
```

***
