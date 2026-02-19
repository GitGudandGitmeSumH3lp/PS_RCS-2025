# FEATURE SPEC: Real Motor Control Integration
**Date:** 2026-05-22  
**Status:** Feasible (with critical data fix required)

## 1. THE VISION
*   **User Story:** As a Remote Operator, I want the dashboard "Motor Control" buttons to physically move the robot using the Arduino hardware, so that I can drive the unit remotely.
*   **Success Metrics:** 
    *   Clicking "Forward" on dashboard -> Robot wheels turn forward.
    *   Releasing button/Clicking Stop -> Robot stops.
    *   Dashboard Status Bar shows "Motor: Connected".

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed. `pyserial` is standard. Threading is already in place in `server.py`.
*   **Context Discrepancy (CRITICAL):** 
    *   The user prompt describes an Arduino sketch listening for `W, A, S, D`.
    *   The provided file `wheels.ino` contains **Servo Control Code** (PCA9685) expecting inputs like `"0 90"`.
    *   **Decision:** This Spec assumes the **W/A/S/D protocol** is the intended target. The Arduino sketch must be corrected to match the Python driver.
*   **Risk Level:** Medium (Hardware/Software protocol mismatch).

## 3. ATOMIC TASKS (The Roadmap)
*   [ ] **Step 0:** Replace `wheels.ino` with actual DC Motor logic (L298N or similar) listening for chars `W, A, S, D, X`.
*   [ ] **Step 1:** Create/Move `src/hardware/motor_controller.py` (The provided Python driver).
*   [ ] **Step 2:** Update `src/core/config.py` to include `MOTOR_PORT` and `MOTOR_BAUD`.
*   [ ] **Step 3:** Refactor `src/services/hardware_manager.py` to import and use the real `MotorController`.
*   [ ] **Step 4:** Update `src/api/server.py` (Minor) to ensure error messages bubble up.

## 4. INTERFACE SKETCHES

### A. Configuration (`src/core/config.py`)
Add these settings to allow easy port switching without code changes.
```python
class Settings:
    # ... existing settings ...
    MOTOR_PORT = "/dev/ttyUSB0"  # or COM3 on Windows
    MOTOR_BAUD_RATE = 9600
    USE_REAL_HARDWARE = True     # Toggle for dev/prod
```

### B. Hardware Manager Logic (`src/services/hardware_manager.py`)
This module acts as the switchboard. It must map the "Business Logic" terms (forward) to "Hardware Protocol" terms (W).

```python
# Integration Logic
def send_motor_command(self, command: str, speed: int) -> bool:
    """
    Input: command="forward", speed=100
    Output: True if sent, False if error
    """
    if not self.motor_controller.is_connected:
        return False
        
    # Map Dashboard Command -> Driver Method
    cmd_map = {
        "forward": self.motor_controller.move_forward,   # Sends 'W'
        "backward": self.motor_controller.move_backward, # Sends 'S'
        "left": self.motor_controller.turn_left,         # Sends 'A'
        "right": self.motor_controller.turn_right,       # Sends 'D'
        "stop": self.motor_controller.stop               # Sends 'X'
    }
    
    if command in cmd_map:
        # Note: Current Arduino protocol ignores 'speed'
        return cmd_map[command]() 
    return False
```

### C. The Driver (`src/hardware/motor_controller.py`)
*Use the file provided in context, but ensure it is placed in the correct directory.*
*   **Method:** `connect()` -> Handles `serial.Serial` opening.
*   **Method:** `send_command(char)` -> Writes bytes to stream.

## 5. INTEGRATION POINTS
*   **Touches:** `src/api/server.py` -> Call `hardware_manager.start_all_drivers()` on startup.
*   **Data Flow:** 
    1.  **Frontend:** `POST /api/motor/control {command: "forward"}`
    2.  **Server:** Calls `HardwareManager.send_motor_command("forward", 50)`
    3.  **HardwareManager:** Calls `MotorController.move_forward()`
    4.  **MotorController:** Sends `b'W'` to `/dev/ttyUSB0`
    5.  **Arduino:** Reads `W`, sets pins High/Low.

## 6. OPEN QUESTIONS & WARNINGS
1.  **URGENT:** The provided `wheels.ino` controls **Servos**, not DC Motors. 
    *   *Action:* The Architect/Implementer must provide/write a standard `Serial.read()` loop for DC motors (L298N/TB6612FNG) that accepts 'W', 'A', 'S', 'D'.
2.  **Speed Control:** The frontend sends a speed value (0-100). The current W/A/S/D protocol is binary (Move/Stop).
    *   *Decision:* We will ignore the speed value for this iteration.
3.  **Power Safety:** Does the robot have a failsafe? (e.g., if Python crashes, does the robot keep moving?)
    *   *Mitigation:* The `MotorController` keeps the connection open. If the script dies, the Serial connection closes. Most Arduinos reset on serial close, stopping motors.

---

## NEXT AGENT: ARCHITECT
**Instructions:**
1.  Define the file structure for the new driver.
2.  **Write the correct Arduino Sketch (`wheels.ino`)** that actually implements the W/A/S/D protocol (the provided one is wrong).
3.  Design the `HardwareManager` modification to gracefully fallback to "Mock" mode if the serial port is missing.