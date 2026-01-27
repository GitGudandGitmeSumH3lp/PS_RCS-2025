# AGENT: ANALYST (V4.0)
**Context:** Feature Specification Generation
**Output:** `specs/01_backend_refactor.md`

Here is the atomic specification to transform the fragile legacy script into a robust system architecture.

---

# FEATURE SPEC: Backend Modularization (Code Name: "RobotBrain")
**Date:** 2026-01-22
**Status:** Feasible
**Source Material:** `api_server2.py` (Legacy)

## 1. THE VISION
*   **User Story:** As a developer, I want a modular backend architecture so that hardware failures (e.g., LiDAR disconnect) do not crash the web server, and port configurations can be changed without editing code.
*   **The "Why":** The current `api_server2.py` mixes HTTP handling, hardware drivers, and thread management in one file. This creates "Race Conditions" (locking issues) and makes the robot hard to debug.
*   **Success Metrics:**
    1.  **Zero Global Variables:** Remove `shared_data` and global locks.
    2.  **Configurability:** All serial ports (`/dev/tty...`) moved to `config.json`.
    3.  **Resilience:** Server starts even if hardware is missing (Graceful Degradation).

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed. Uses standard Python (Flask, Threading, SQLite).
*   **New Libraries Needed:** `pydantic` (recommended for settings management, but standard `json` is acceptable if strict usage required).
*   **Risk Level:** **Medium**.
    *   *Risk:* Separating the `MotorController` from the API might break the "Stop" command latency if not threaded correctly.
    *   *Mitigation:* Use a dedicated `RobotState` class that the API reads from and hardware writes to.

## 3. ATOMIC TASKS (The Roadmap)
*   [ ] **1. Create `src/core/config.py`:** Centralize constants (Serial Ports, Baud Rates, DB Path).
*   [ ] **2. Create `src/core/state_manager.py`:** A thread-safe data store to replace `shared_data`.
*   [ ] **3. Create `src/services/hardware_manager.py`:** A class that manages the lifecycle (connect/disconnect/reconnect) of LiDAR, Motor, and Camera.
*   [ ] **4. Update `src/database/db_manager.py`:** Optimize the `database.py` logic. (Stop saving *every* LiDAR point to DB unless explicitly recording a "Scan Session").
*   [ ] **5. Rewrite `api_entry.py`:** A clean Flask/FastAPI app that imports the managers above.

## 4. INTERFACE SKETCHES (For Architect)

**A. The Configuration**
Instead of hardcoded strings:
```python
# src/core/config.py
class Settings:
    MOTOR_PORT: str = "/dev/ttyUSB0"
    LIDAR_PORT: str = "/dev/ttyUSB1"
    DB_PATH: str = "data/robot.db"
    SIMULATION_MODE: bool = False  # If True, mock hardware
```

**B. The Hardware Orchestrator**
Instead of `try/import/except` blocks in the main file:
```python
# src/services/hardware_manager.py
class HardwareManager:
    def __init__(self, state_manager):
        self.motor = MotorController()
        self.lidar = LidarHandler()
        self.state = state_manager

    def start_drivers(self):
        # Attempt connections, log failures, but don't crash
        if not self.motor.connect():
            self.state.update_error("motor", "Disconnected")
    
    def shutdown(self):
        # Safe cleanup
        self.motor.stop()
        self.lidar.disconnect()
```

**C. The State Store (Thread-Safe)**
Replacing the global `data_lock`:
```python
# src/core/state.py
class RobotState:
    def __init__(self):
        self._data = {"lidar": [], "status": "idle"}
        self._lock = threading.Lock()

    def update_lidar(self, points):
        with self._lock:
            self._data["lidar"] = points
    
    def get_snapshot(self):
        with self._lock:
            return self._data.copy()
```

## 5. INTEGRATION POINTS
*   **Frontend:** The existing Flask Templates (`lidar_gui.html`) expect specific JSON structures. *Constraint:* The JSON output of `/api/lidar` and `/api/status` MUST match the legacy format exactly to save us from rewriting the frontend HTML/JS.
*   **Database:** The `Database` class needs to accept `Scan Objects` rather than raw args.

## 6. OPEN QUESTIONS
1.  **OCR Reality:** The legacy code runs `run_ocr_simulator`. Do we keep this simulation for now, or should we stub it out entirely until real OCR hardware is confirmed? (Assumption: Keep Simulation as a "Demo Mode").
2.  **LiDAR Storage:** Storing 100k points in SQLite is bad. Should we switch to saving LiDAR scans as `.json` files and only storing the filename in SQLite? (Recommendation: Yes).

---

## POST-ACTION REPORT
✅ **Spec Created:** `specs/01_backend_refactor.md`
📋 **Next Step:** Architect will convert this into a Class Structure and File Contract.
👉 **Next Agent:** Architect (AGENTS/01_architect.md)