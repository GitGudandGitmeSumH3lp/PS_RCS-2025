# CONTRACT: MotorController Integration
**Version:** 1.0  
**Last Updated:** 2026-02-19  
**Status:** Draft  
**Feature Spec:** `docs/specs/18_real_motor_control.md`  
**Replaces:** Mock motor driver in `HardwareManager`

---

## 1. PURPOSE

This module provides a thread-safe, singleton serial driver that bridges the PS-RCS dashboard's `HardwareManager` to a physical Arduino-based motor controller via USB serial. It translates high-level directional commands (`forward`, `backward`, `left`, `right`, `stop`) into single-character serial packets (`W`, `S`, `A`, `D`, `X`) consumed by the `wheels.ino` firmware running on the PCA9685-equipped Arduino. The driver manages connection lifecycle (connect on startup, disconnect on shutdown), propagates connection status to `RobotState` for frontend polling via `/api/status`, and returns `False` on all failure paths so the frontend toast system can surface errors without crashing the server.

---

## 2. PUBLIC INTERFACE

### Method: `connect`

**Signature:**
```python
def connect(self, port: str, baudrate: int = 9600) -> bool:
    """Establish serial connection to the Arduino motor controller.

    Args:
        port: Serial port identifier (e.g., '/dev/ttyUSB0' or 'COM3').
        baudrate: Communication baud rate. Must match Arduino firmware.
            Defaults to 9600.

    Returns:
        True if connection was established and keep-alive test passed.
        False if port unavailable, already in use, or test failed.
    """
```

**Behavior Specification:**

- **Input Validation:** `port` must be a non-empty string. `baudrate` must be a positive integer. Raise `ValueError` if either is invalid before attempting connection.
- **Processing Logic:**
  1. Acquire `_io_lock`.
  2. If `is_connected` is already `True` and serial port is open, return `True` immediately (idempotent).
  3. If a stale `serial_conn` exists, close it before re-opening.
  4. Open `serial.Serial` with `timeout=2`, `write_timeout=1`, 8N1 settings.
  5. Sleep 2 seconds to allow Arduino bootloader reset cycle to complete.
  6. Flush input and output buffers.
  7. Call internal `_test_connection()`. If it returns `False`, close port and return `False`.
  8. Set `is_connected = True`. Log success at INFO level.
- **Output Guarantee:** Returns `True` only after a successful keep-alive handshake confirms two-way communication. Returns `False` in all other cases — never raises to caller.
- **Side Effects:** Sets `self.is_connected`. Opens `self.serial_conn`. Logs to `MotorController` logger.

**Error Handling:**

- **Port does not exist / permission denied:** `serial.SerialException` → log ERROR, set `is_connected = False`, return `False`.
- **Port busy / locked by another process:** `serial.SerialException` → log ERROR with port name and hint to check other processes, return `False`.
- **`ValueError` for bad args:** Raise `ValueError` with message `"port must be a non-empty string"` or `"baudrate must be a positive integer"`.
- **Any other exception:** Log ERROR with traceback, return `False`.

**Performance Requirements:**

- Time Complexity: O(1) — single serial open + fixed 2s sleep
- Blocking duration: ~2–4 seconds (acceptable; called only at server startup)

---

### Method: `send_command`

**Signature:**
```python
def send_command(self, command: str, speed: int = 0) -> bool:
    """Translate a named command to a serial character and transmit it.

    Args:
        command: Directional command string. One of:
            'forward', 'backward', 'left', 'right', 'stop'.
            Case-insensitive.
        speed: Reserved for future use. Accepted but ignored in v1.0.
            Defaults to 0.

    Returns:
        True if the character was successfully written to serial.
        False if not connected, command unknown, or write failed.
    """
```

**Behavior Specification:**

- **Input Validation:** `command` must be one of the five valid string values (case-insensitive). If not, log WARNING and return `False` — do not raise.
- **Processing Logic:**
  1. Map `command.lower()` → serial character via internal `_CMD_MAP`.
  2. Acquire `_io_lock`.
  3. If `is_connected` is `False` or `serial_conn` is `None` or port is not open, return `False`.
  4. Encode character as ASCII bytes (single byte only; no newline).
  5. Call `serial_conn.write()` followed by `serial_conn.flush()`.
  6. Log at DEBUG level: `"Sent command: '{CHAR}'"`.
- **Output Guarantee:** Returns `True` only if `write()` and `flush()` complete without exception.
- **Side Effects:** Transmits one byte over serial. On write failure, calls `self.disconnect()` to reset state.

**Command Map (IMMUTABLE):**

| `command` string | Serial char |
|---|---|
| `'forward'` | `'W'` |
| `'backward'` | `'S'` |
| `'left'` | `'A'` |
| `'right'` | `'D'` |
| `'stop'` | `'X'` |

**Error Handling:**

- **Unknown command:** Log `WARNING: "Unknown command: '{command}'"` → return `False`.
- **Not connected:** Log `ERROR: "Cannot send command: motor controller not connected"` → return `False`.
- **`serial.SerialTimeoutException`:** Log ERROR, call `disconnect()`, return `False`.
- **Any `serial.SerialException`:** Log ERROR, call `disconnect()`, return `False`.

**Performance Requirements:**

- Time Complexity: O(1)
- Expected latency: <5ms (single byte write to local serial buffer)
- Must not block HTTP route thread for >10ms

---

### Method: `disconnect`

**Signature:**
```python
def disconnect(self) -> None:
    """Safely close the serial connection and reset internal state.

    Idempotent: safe to call multiple times or when already disconnected.
    Sends a final 'X' (stop) command before closing if connected.
    """
```

**Behavior Specification:**

- **Processing Logic:**
  1. Acquire `_io_lock`.
  2. If `serial_conn` exists and is open: attempt `send_command('stop')` (best-effort, swallow exceptions), then `serial_conn.close()`.
  3. Set `serial_conn = None`, `is_connected = False`.
  4. Log at INFO level.
- **Side Effects:** Closes serial port. Resets `is_connected`. Motors will stop via firmware watchdog or last 'X' command.

**Error Handling:**

- All exceptions during close are caught, logged at WARNING, and swallowed. Disconnect must always complete.

---

### Method: `get_status`

**Signature:**
```python
def get_status(self) -> dict:
    """Return a snapshot of connection state for status reporting.

    Returns:
        dict with keys:
            'connected' (bool): Whether serial link is active.
            'port' (str | None): Configured port string, or None if never set.
            'baudrate' (int | None): Configured baud rate, or None if never set.
    """
```

**Behavior Specification:**

- **Processing Logic:** Read current instance attributes and return a plain dict. No locking required (reading primitive values is atomic in CPython).
- **Output Guarantee:** Always returns a dict with the three specified keys. Never raises.

---

### Internal Method: `_test_connection`

**Signature:**
```python
def _test_connection(self) -> bool:
    """Send keep-alive byte and confirm serial port is writeable.

    Not part of public interface. Called only from connect().
    Does NOT require the Arduino to send a response — write success is sufficient.

    Returns:
        True if write succeeded. False on any exception.
    """
```

**Behavior Specification:**

- Write single byte `b'K'` (keep-alive) to serial.
- Wait 100ms.
- Flush input buffer (discard Arduino startup messages).
- Return `True` if no exception raised. This confirms the OS-level serial write path is functional.
- **Rationale:** Not all firmware versions echo responses. Write-success is a reliable enough signal at connect time.

---

## 3. DEPENDENCIES

**This module CALLS:**

- `serial.Serial` (pyserial) — hardware serial I/O
- `threading.Lock` — mutual exclusion for serial I/O
- `logging.getLogger("MotorController")` — structured logging
- `time.sleep()` — Arduino reset delay

**This module is CALLED BY:**

- `HardwareManager._connect_motor()` — calls `connect()` on server startup
- `HardwareManager.send_motor_command()` — calls `send_command()` on every motor API request
- `HardwareManager.shutdown()` — calls `disconnect()` on server teardown

---

## 4. DATA STRUCTURES

### Singleton Pattern

```python
_instance: ClassVar[Optional['MotorController']] = None
_class_lock: ClassVar[threading.Lock] = threading.Lock()
```

The double-checked locking pattern (check → lock → check) is required. The class-level lock guards instantiation only. The instance-level `_io_lock` guards all serial I/O operations.

### Internal Command Map

```python
_CMD_MAP: ClassVar[dict[str, str]] = {
    'forward':  'W',
    'backward': 'S',
    'left':     'A',
    'right':    'D',
    'stop':     'X',
}
```

This map is defined as a class constant. It must not be modified at runtime.

### Instance Attributes (post-`__init__`)

| Attribute | Type | Description |
|---|---|---|
| `serial_conn` | `Optional[serial.Serial]` | Active serial connection or `None` |
| `is_connected` | `bool` | True when serial link confirmed active |
| `_port` | `Optional[str]` | Port string set during `connect()` |
| `_baudrate` | `Optional[int]` | Baud rate set during `connect()` |
| `_io_lock` | `threading.Lock` | Protects all serial read/write ops |
| `logger` | `logging.Logger` | Module logger |
| `initialized` | `bool` | Guards against re-initialization in singleton |

---

## 5. CONSTRAINTS (FROM SYSTEM CONSTRAINTS)

- **Threading:** Must use `threading.Lock` exclusively. No `asyncio`. (Constraint §1 — Concurrency)
- **Hardware Abstraction:** `serial` library must NOT appear in any API route or `server.py`. All serial access routed through this class, accessed via `HardwareManager`. (Constraint §1 — Hardware Abstraction)
- **No Global State:** `_instance` is a class variable (singleton pattern), not a module-level global. `RobotState` holds all runtime state; this class holds only connection state. (Constraint §1 — No Global State)
- **Function Length:** No method may exceed 50 lines of executable code. `connect()` must be refactored to delegate to `_open_serial()` and `_test_connection()` if needed. (Constraint §4 — Code Quality)
- **Type Hints:** All public methods must have complete type annotations. (Constraint §4)
- **Docstrings:** Google-style docstrings required on all public methods and the class itself. (Constraint §4)
- **No Hardcoded Paths:** Port string comes from `Settings.MOTOR_PORT` via `HardwareManager`. Never hardcode `'COM3'` or `'/dev/ttyUSB0'` in this module. (Constraint §4 — Forbidden Patterns)
- **Allowed Library:** `pyserial` is in the approved hardware library list. (Constraint §1 — Allowed Libraries)

---

## 6. MEMORY COMPLIANCE

No `_memory_snippet.txt` was provided for this contract cycle. This section will be populated when project memory rules are applied.

---

## 7. ACCEPTANCE CRITERIA

**Test Case 1: Successful Connection**

- Input: `connect(port="/dev/ttyUSB0", baudrate=9600)` with Arduino connected and running `wheels.ino`
- Expected Output: `True`
- Expected Behavior: `is_connected == True`, INFO log contains port name, `_test_connection()` wrote `b'K'` without error.

**Test Case 2: Port Does Not Exist**

- Input: `connect(port="/dev/ttyUSB99", baudrate=9600)`
- Expected Output: `False`
- Expected Behavior: `is_connected == False`, `serial_conn == None`, ERROR log contains port name.

**Test Case 3: Successful Command Send**

- Input: `send_command("forward")` after successful `connect()`
- Expected Output: `True`
- Expected Behavior: Arduino receives byte `b'W'`, robot moves forward. DEBUG log shows `"Sent command: 'W'"`.

**Test Case 4: Unknown Command**

- Input: `send_command("hover")`
- Expected Output: `False`
- Expected Behavior: WARNING log `"Unknown command: 'hover'"`. No serial write attempted. `is_connected` unchanged.

**Test Case 5: Send When Disconnected**

- Input: `send_command("forward")` without prior `connect()` (or after disconnect)
- Expected Output: `False`
- Expected Behavior: ERROR log `"Cannot send command: motor controller not connected"`. No exception raised.

**Test Case 6: Idempotent Connect**

- Input: `connect()` called twice consecutively on open port
- Expected Output: `True` (both calls)
- Expected Behavior: Second call returns immediately without reopening port. No duplicate log entries for connection.

**Test Case 7: Disconnect Resets State**

- Input: `disconnect()` after successful connection
- Expected Output: (none — void)
- Expected Behavior: `is_connected == False`, `serial_conn == None`, port is closed. Subsequent `send_command()` returns `False`.

**Test Case 8: Invalid Port Arg**

- Input: `connect(port="", baudrate=9600)`
- Expected Output: raises `ValueError`
- Expected Message: `"port must be a non-empty string"`

---

## 8. CONFIGURATION CONTRACT

`MOTOR_PORT` and `MOTOR_BAUD_RATE` already exist in `src/core/config.py` (`Settings` dataclass) and are loaded from `config/settings.json`.

**Required `settings.json` keys (already present — no changes needed):**

```json
{
  "MOTOR_PORT": "/dev/ttyUSB0",
  "MOTOR_BAUD_RATE": 9600
}
```

**For Windows development:** Set `"MOTOR_PORT": "COM3"` (or the appropriate COM port) in `config/settings.json`. Do NOT hardcode this in source files.

**Environment override (optional):** If the project later adopts `.env` loading, `MOTOR_PORT` and `MOTOR_BAUD_RATE` can be overridden via environment variables by adding `os.getenv` fallback in `Settings.load_from_file()`. This is out of scope for v1.0.

---

## 9. HARDWARE MANAGER INTEGRATION CONTRACT

The following changes to `src/services/hardware_manager.py` are formally contracted:

### New Method: `_connect_motor`

```python
def _connect_motor(self) -> None:
    """Attempt motor controller connection on startup and update RobotState.

    Called once during HardwareManager.__init__. Failure is non-fatal:
    the server starts in degraded mode with motor_connected=False.
    """
```

- Calls `self.motor_controller.connect(self.settings.MOTOR_PORT, self.settings.MOTOR_BAUD_RATE)`
- On success: calls `self.state.update_status(motor_connected=True)`
- On failure: calls `self.state.update_status(motor_connected=False)`, logs ERROR
- Must not raise — wrap in try/except

### Updated Method: `send_motor_command`

```python
def send_motor_command(self, command: str, speed: int = 50) -> bool:
    """Delegate motor command to MotorController driver.

    Args:
        command: One of 'forward', 'backward', 'left', 'right', 'stop'.
        speed: Reserved for future use. Passed through to driver.

    Returns:
        True if command was sent successfully. False on any failure.
    """
```

- Delegates entirely to `self.motor_controller.send_command(command, speed)`
- Does NOT re-implement any serial logic
- Returns the bool result directly to the API route

### New Method: `shutdown`

```python
def shutdown(self) -> None:
    """Gracefully disconnect all hardware on server shutdown."""
```

- Calls `self.motor_controller.disconnect()`
- Calls any other existing shutdown routines (LiDAR, camera, etc.)

### `/api/status` Response Contract

The `motor_connected` field already exists in the API map (v4.2+). `HardwareManager` must keep `RobotState.motor_connected` synchronized:

- Set to `True` after successful `connect()`
- Set to `False` after `disconnect()` or on write failure (the driver sets `is_connected=False`; HardwareManager must poll or react to this)

---

## 10. ARDUINO FIRMWARE CONTRACT (`arduino/wheels.ino`)

The legacy `wheels.ino` (servo angle test script) is **replaced in full**. The new firmware must:

- Include `<Wire.h>` and `<Adafruit_PWMServoDriver.h>`
- Initialize `Adafruit_PWMServoDriver pwm` at address `0x40` (default)
- Call `Serial.begin(9600)` — must match `MOTOR_BAUD_RATE`
- Call `pwm.begin()` and `pwm.setPWMFreq(50)` in `setup()`
- Call `stopMotors()` in `setup()` to ensure safe start state
- Print `"READY"` to Serial in `setup()` (diagnostic aid)
- In `loop()`: read single char from `Serial`, call `toupper()`, switch on `W/S/A/D/X`
- Ignore unknown characters silently (no error response required)

**PCA9685 Channel Assignments (configurable via `#define`):**

| Define | Default | Description |
|---|---|---|
| `LEFT_MOTOR_CH` | `0` | PCA9685 channel for left motor |
| `RIGHT_MOTOR_CH` | `1` | PCA9685 channel for right motor |
| `STOP_PULSE` | `307` | ~1.5ms neutral (continuous servo) |
| `FWD_PULSE` | `410` | ~2.0ms full forward |
| `REV_PULSE` | `205` | ~1.0ms full reverse |

> ⚠️ **Implementer Note:** If one motor runs in reverse when both should go forward, swap `FWD_PULSE`↔`REV_PULSE` for that channel only. This is a wiring reality, not a firmware bug.

**Required Library:** `Adafruit PWM Servo Driver Library` — install via Arduino Library Manager.

---

## 11. DEPENDENCIES & REQUIREMENTS

```
# requirements.txt — ensure this line exists:
pyserial>=3.5
```

No other new Python dependencies are introduced by this contract.