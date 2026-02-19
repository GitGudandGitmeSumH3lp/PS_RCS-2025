# WORK ORDER FOR IMPLEMENTER

**Target Files:**
- `src/hardware/motor_controller.py` ← CREATE NEW
- `src/services/hardware_manager.py` ← MODIFY (3 targeted changes)
- `arduino/wheels.ino` ← REPLACE IN FULL
- `requirements.txt` ← VERIFY `pyserial>=3.5` exists

**Contract Reference:** `docs/contracts/contract_motor_controller.md` v1.0  
**Do NOT touch:** `src/core/config.py` — `MOTOR_PORT` and `MOTOR_BAUD_RATE` already exist.

---

## Strict Constraints (NON-NEGOTIABLE)

1. **No `serial` import outside `src/hardware/motor_controller.py`** — pyserial is banned from routes and managers.
2. **No `asyncio`** — use `threading.Lock` exclusively.
3. **No hardcoded port strings** — port comes from `Settings.MOTOR_PORT` passed in by `HardwareManager`.
4. **No function longer than 50 lines** — refactor if needed.
5. **Type hints on every public method.**
6. **Google-style docstrings on every public method and class.**
7. **`send_motor_command()` must return `False` on failure** — never raise to the route layer.

---

## FILE 1: `src/hardware/motor_controller.py` (CREATE)

### Class Structure

```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/motor_controller.py
Description: Thread-safe singleton serial driver for Arduino motor controller.
"""

import serial
import time
import logging
import threading
from typing import ClassVar, Optional


class MotorController:
    """Thread-safe singleton driver for Arduino-based motor control via serial.

    Translates high-level directional commands to W/A/S/D/X serial characters.
    Connection lifecycle is managed by HardwareManager.

    Attributes:
        is_connected: True when serial link is confirmed active.
    """

    _instance: ClassVar[Optional['MotorController']] = None
    _class_lock: ClassVar[threading.Lock] = threading.Lock()

    _CMD_MAP: ClassVar[dict] = {
        'forward':  'W',
        'backward': 'S',
        'left':     'A',
        'right':    'D',
        'stop':     'X',
    }
```

### Required Logic — `__new__` and `__init__`

- `__new__`: Double-checked locking singleton (check `_instance` → acquire `_class_lock` → check again → create).
- `__init__`: Guard with `if getattr(self, 'initialized', False): return`. Set `initialized = True`. Initialize: `serial_conn = None`, `is_connected = False`, `_port = None`, `_baudrate = None`, `_io_lock = threading.Lock()`, `logger = logging.getLogger("MotorController")`.

### Required Logic — `connect(self, port: str, baudrate: int = 9600) -> bool`

1. Validate: `port` non-empty string → raise `ValueError("port must be a non-empty string")` if not.
2. Validate: `baudrate > 0` int → raise `ValueError("baudrate must be a positive integer")` if not.
3. Acquire `_io_lock`.
4. If `is_connected` and `serial_conn` and `serial_conn.is_open` → return `True` (idempotent).
5. If stale `serial_conn` exists → `serial_conn.close()` (suppress exceptions).
6. Open `serial.Serial(port=port, baudrate=baudrate, timeout=2, write_timeout=1, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)`.
7. `time.sleep(2)` — Arduino bootloader reset.
8. `serial_conn.flushInput()`, `serial_conn.flushOutput()`.
9. Store `_port = port`, `_baudrate = baudrate`.
10. Call `_test_connection()`. If `False` → close port, return `False`.
11. Set `is_connected = True`, log INFO, return `True`.
12. Wrap steps 6–11 in `except Exception as e` → log ERROR, reset state, return `False`.

### Required Logic — `_test_connection(self) -> bool`

1. Write `b'K'` to `serial_conn`, call `flush()`.
2. `time.sleep(0.1)`.
3. `serial_conn.flushInput()` (discard any Arduino startup output).
4. Return `True`.
5. Wrap in `except Exception` → log ERROR, return `False`.

### Required Logic — `send_command(self, command: str, speed: int = 0) -> bool`

1. Lookup `command.lower()` in `_CMD_MAP`. If not found → log WARNING → return `False`.
2. Acquire `_io_lock`.
3. If not connected or port not open → log ERROR → return `False`.
4. `serial_conn.write(char_cmd.encode('ascii'))`.
5. `serial_conn.flush()`.
6. Log DEBUG: `f"Sent command: '{char_cmd}'"`.
7. Return `True`.
8. On any `serial.SerialException` → log ERROR, call `disconnect()`, return `False`.

### Required Logic — `disconnect(self) -> None`

1. Acquire `_io_lock`.
2. If `serial_conn` and `serial_conn.is_open`:
   - Best-effort: write `b'X'` (stop) — suppress all exceptions.
   - `serial_conn.close()`.
3. Set `serial_conn = None`, `is_connected = False`.
4. Log INFO.
5. Entire method wrapped in outer `except Exception` — disconnect must never raise.

### Required Logic — `get_status(self) -> dict`

Return:
```python
{
    'connected': self.is_connected,
    'port': self._port,
    'baudrate': self._baudrate,
}
```
No locking needed. Never raises.

---

## FILE 2: `src/services/hardware_manager.py` (MODIFY — 3 changes)

### Change 1: Add Import (top of file)
```python
from src.hardware.motor_controller import MotorController
```

### Change 2: In `__init__` — add motor controller instantiation and startup connect
```python
self.motor_controller = MotorController()  # Singleton
self._connect_motor()
```

### Change 3: Add three new methods

**`_connect_motor(self) -> None`:**
```python
def _connect_motor(self) -> None:
    """Attempt motor controller connection on startup. Non-fatal on failure."""
    try:
        if self.motor_controller.connect(self.settings.MOTOR_PORT, self.settings.MOTOR_BAUD_RATE):
            self.state.update_status(motor_connected=True)
            logging.info("Motor controller connected.")
        else:
            self.state.update_status(motor_connected=False)
            logging.warning("Motor controller connection failed. Running in degraded mode.")
    except Exception as e:
        logging.error(f"Motor init error: {e}")
        self.state.update_status(motor_connected=False)
```

**`send_motor_command(self, command: str, speed: int = 50) -> bool`:**
```python
def send_motor_command(self, command: str, speed: int = 50) -> bool:
    """Send directional command to motor controller.

    Args:
        command: One of 'forward', 'backward', 'left', 'right', 'stop'.
        speed: Reserved for future use. Defaults to 50.

    Returns:
        True if sent successfully. False on any failure.
    """
    return self.motor_controller.send_command(command, speed)
```

**`shutdown(self) -> None`:**
```python
def shutdown(self) -> None:
    """Gracefully disconnect all hardware peripherals."""
    self.motor_controller.disconnect()
    # Add calls to other shutdown routines here (lidar, camera, etc.)
```

> **Note:** If `send_motor_command` already exists as a mock, REPLACE it. Do not leave the mock in place.

---

## FILE 3: `arduino/wheels.ino` (REPLACE IN FULL)

Delete all existing content. Write the following exactly:

```cpp
/*
 * PS_RCS_PROJECT - Motor Controller Firmware
 * File: arduino/wheels.ino
 * Description: PCA9685 differential drive controller.
 *              Accepts W/A/S/D/X commands via Serial at 9600 baud.
 *
 * Wiring: Connect PCA9685 via I2C (SDA=A4, SCL=A5 on Uno).
 *         Left motor on channel LEFT_MOTOR_CH.
 *         Right motor on channel RIGHT_MOTOR_CH.
 *         If one motor runs backwards, swap FWD_PULSE <-> REV_PULSE for that channel.
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(); // Default I2C addr 0x40

// ── Channel Assignment ────────────────────────────────────────────────────────
#define LEFT_MOTOR_CH   0
#define RIGHT_MOTOR_CH  1

// ── Pulse Widths (continuous rotation servos @ 50Hz) ─────────────────────────
#define STOP_PULSE  307   // ~1.5ms neutral
#define FWD_PULSE   410   // ~2.0ms forward
#define REV_PULSE   205   // ~1.0ms reverse

// ─────────────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(9600);
  pwm.begin();
  pwm.setPWMFreq(50);
  stopMotors();
  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = toupper(Serial.read());
    switch (cmd) {
      case 'W': moveForward();  break;
      case 'S': moveBackward(); break;
      case 'A': turnLeft();     break;
      case 'D': turnRight();    break;
      case 'X': stopMotors();   break;
      // Unknown chars ignored silently
    }
  }
}

void setMotor(int channel, int pulse) {
  pwm.setPWM(channel, 0, pulse);
}

void moveForward() {
  setMotor(LEFT_MOTOR_CH,  FWD_PULSE);
  setMotor(RIGHT_MOTOR_CH, FWD_PULSE);
}

void moveBackward() {
  setMotor(LEFT_MOTOR_CH,  REV_PULSE);
  setMotor(RIGHT_MOTOR_CH, REV_PULSE);
}

void turnLeft() {
  setMotor(LEFT_MOTOR_CH,  REV_PULSE);
  setMotor(RIGHT_MOTOR_CH, FWD_PULSE);
}

void turnRight() {
  setMotor(LEFT_MOTOR_CH,  FWD_PULSE);
  setMotor(RIGHT_MOTOR_CH, REV_PULSE);
}

void stopMotors() {
  setMotor(LEFT_MOTOR_CH,  STOP_PULSE);
  setMotor(RIGHT_MOTOR_CH, STOP_PULSE);
}
```

---

## FILE 4: `requirements.txt` (VERIFY)

Confirm this line exists. Add if missing:
```
pyserial>=3.5
```

---

## Integration Points

- **Motor controller is called by:** `HardwareManager.send_motor_command()` on every `POST /api/motor/control` request
- **Motor controller connects during:** `HardwareManager.__init__()` (server startup)
- **Motor controller disconnects during:** `HardwareManager.shutdown()` (server teardown — wire to Flask `atexit` or `SIGTERM` handler)
- **Status surface:** `RobotState.motor_connected` → `GET /api/status` response (`motor_connected` field already in API map v4.2+)

---

## Testing Procedure

**Step 1 — Upload Firmware:**
1. Open Arduino IDE.
2. Install `Adafruit PWM Servo Driver Library` via Library Manager.
3. Open `arduino/wheels.ino`.
4. Select correct board (Arduino Uno) and port.
5. Upload. Open Serial Monitor at 9600 baud. Confirm `"READY"` printed.

**Step 2 — Identify Serial Port:**
- Linux/RPi: `ls /dev/ttyUSB*` or `ls /dev/ttyACM*` after plugging Arduino.
- Windows: Device Manager → Ports (COM & LPT).

**Step 3 — Update Config:**
- Set correct port in `config/settings.json`: `"MOTOR_PORT": "/dev/ttyUSB0"` (or `"COM3"`).

**Step 4 — Run Server:**
```bash
python src/main.py
```
Confirm log output: `"Connected to motor controller on /dev/ttyUSB0"`.

**Step 5 — Verify via Dashboard:**
1. Open dashboard in browser.
2. Check `GET /api/status` → confirm `"motor_connected": true`.
3. Press Forward button → confirm robot moves.
4. Press Stop → confirm motors halt.

**Step 6 — Test Failure Modes:**
- Unplug Arduino mid-session → next motor command returns `False` → frontend shows error toast.
- Restart server with Arduino unplugged → `"motor_connected": false` in status → server runs in degraded mode.

---

## Success Criteria

- [ ] All public methods match contract signatures exactly (types, defaults, return types).
- [ ] All 8 test cases in contract Section 7 pass.
- [ ] `pyserial` is in `requirements.txt`.
- [ ] No `serial` import outside `motor_controller.py`.
- [ ] No function exceeds 50 lines.
- [ ] Type hints present on all public methods.
- [ ] Google-style docstrings on class and all public methods.
- [ ] `GET /api/status` returns `"motor_connected": true` when Arduino is connected.
- [ ] Arduino Serial Monitor shows `"READY"` after firmware upload.
- [ ] Auditor approval required before merging.