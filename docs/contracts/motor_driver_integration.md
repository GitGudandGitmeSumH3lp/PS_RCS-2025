# CONTRACT: Motor Driver Integration (V1.0)
**Version:** 1.0
**Last Updated:** 2026-01-23
**Status:** Draft
**Analyst Reference:** `specs/03_motor_controller.md`

---

## 1. PURPOSE

This contract defines the standardized interface for motor control drivers in the modular backend system. It establishes:
- A strict contract (`IMotorDriver`) that all motor drivers must implement
- An adapter pattern to wrap the legacy `motor_controller.py` without modifying its hardware-tested logic
- A mock implementation for development/testing without physical hardware
- Integration logic for `HardwareManager` to switch between real and simulated drivers

**Why this exists:** The legacy motor controller uses specific method names (`move_forward()`, `turn_left()`, etc.) and relative speed control (`+`/`-`). The new system requires a generic interface with `send_command(command, speed)` for future extensibility and testability.

---

## 2. PUBLIC INTERFACE

### 2.1 Protocol: `IMotorDriver`

**File:** `src/interfaces/motor_interface.py`

**Signature:**
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class IMotorDriver(Protocol):
    """
    Contract for all motor driver implementations.
    
    Defines the standard interface for controlling robot motors,
    whether real hardware or simulated.
    """
    
    def connect(self, port: str, baud: int) -> bool:
        """
        Establish connection to motor controller hardware.
        
        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0')
            baud: Baud rate (e.g., 9600)
            
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            ConnectionError: If hardware communication fails critically
        """
        ...
    
    def send_command(self, command: str, speed: int) -> None:
        """
        Send a movement command to the motor controller.
        
        Args:
            command: Movement directive. Valid values:
                - "FORWARD" / "forward"
                - "BACKWARD" / "backward"
                - "LEFT" / "left"
                - "RIGHT" / "right"
                - "STOP" / "stop"
            speed: Desired speed (0-100). 
                   Note: Legacy hardware may ignore this value.
                   
        Raises:
            ValueError: If command string is not recognized
            RuntimeError: If driver not connected
        """
        ...
    
    def stop(self) -> None:
        """
        Immediately halt all motor movement.
        
        Raises:
            RuntimeError: If driver not connected
        """
        ...
    
    def disconnect(self) -> None:
        """
        Close connection and release hardware resources.
        
        Should be idempotent (safe to call multiple times).
        """
        ...
```

**Behavior Specification:**
- **Input Validation:** 
  - `connect()`: Port must be non-empty string, baud must be positive integer
  - `send_command()`: Command must be one of the valid strings (case-insensitive), speed must be 0-100
  - All methods must check if connection is established before operating
  
- **Processing Logic:**
  - Connection establishment may block (implementation-dependent)
  - Commands are processed synchronously
  - Invalid commands fail fast with exceptions
  
- **Output Guarantee:**
  - `connect()` returns boolean status (does not raise on connection failure, only on critical errors)
  - Command methods return `None` but modify hardware state
  
- **Side Effects:**
  - Serial port communication (real driver)
  - Log entries
  - Thread blocking (during `connect()` for legacy driver)

**Error Handling:**
- **Port not found** → `connect()` returns `False`, logs error
- **Invalid command** → Raise `ValueError` with message "Invalid command: {command}. Must be one of: FORWARD, BACKWARD, LEFT, RIGHT, STOP"
- **Not connected** → Raise `RuntimeError` with message "Driver not connected. Call connect() first."
- **Critical hardware failure** → Raise `ConnectionError` with descriptive message

**Performance Requirements:**
- Time Complexity: O(1) for all operations
- Space Complexity: O(1)
- Blocking Tolerance: `connect()` may block up to 5 seconds (hardware reset time)

---

### 2.2 Class: `LegacyMotorAdapter`

**File:** `src/drivers/legacy_motor_adapter.py`

**Signature:**
```python
from src.interfaces.motor_interface import IMotorDriver
import logging
from typing import Optional

class LegacyMotorAdapter:
    """
    Adapter wrapping the legacy motor_controller.MotorController.
    
    Translates the new IMotorDriver interface to legacy-specific
    method calls without modifying the original hardware-tested code.
    """
    
    def __init__(self, legacy_controller: Optional[object] = None):
        """
        Initialize adapter with legacy controller instance.
        
        Args:
            legacy_controller: Instance of motor_controller.MotorController.
                              If None, will import and use singleton.
        """
        ...
    
    def connect(self, port: str, baud: int) -> bool:
        """
        Adapt connect interface to legacy controller.
        
        NOTE: Legacy controller uses instance variables for port/baud
        set in __init__. This method will update those before connecting.
        
        WARNING: Blocks for ~4 seconds during Arduino reset.
        """
        ...
    
    def send_command(self, command: str, speed: int) -> None:
        """
        Map generic command strings to legacy-specific methods.
        
        Command Mapping:
            "FORWARD"  -> legacy.move_forward()
            "BACKWARD" -> legacy.move_backward()
            "LEFT"     -> legacy.turn_left()
            "RIGHT"    -> legacy.turn_right()
            "STOP"     -> legacy.stop()
        
        Speed Handling:
            Legacy hardware does NOT support absolute speed.
            Speed parameter is logged but ignored.
            Future: Could map to repeated +/- calls.
        """
        ...
    
    def stop(self) -> None:
        """Direct pass-through to legacy.stop()"""
        ...
    
    def disconnect(self) -> None:
        """Clean shutdown of serial connection"""
        ...
```

**Behavior Specification:**

- **Input Validation:**
  - Port: Must be valid file path string (e.g., `/dev/ttyUSB0`)
  - Baud: Must be in [9600, 19200, 38400, 57600, 115200]
  - Command: Case-insensitive, strip whitespace, must match valid set
  - Speed: Warn if not in range 0-100

- **Processing Logic:**
  1. `connect()`: Update legacy controller's port/baud attributes, call `legacy.connect()`, return result
  2. `send_command()`: 
     - Normalize command to uppercase
     - Look up in mapping dictionary
     - Call corresponding legacy method
     - Log warning about ignored speed parameter
  3. Connection state tracked via legacy controller's internal state

- **Output Guarantee:**
  - `connect()` returns exact boolean from legacy controller
  - Command execution returns `None` on success
  - Exceptions propagate from legacy controller

- **Side Effects:**
  - Modifies legacy controller's instance variables
  - Sends serial commands to hardware
  - Logs warning messages for speed parameter

**Error Handling:**
- **Unknown command** → Raise `ValueError("Invalid command: {cmd}. Must be one of: FORWARD, BACKWARD, LEFT, RIGHT, STOP")`
- **Not connected** → Raise `RuntimeError("Driver not connected. Call connect() first.")`
- **Serial port error** → Propagate from legacy controller

**Performance Requirements:**
- Time Complexity: O(1) - dictionary lookup + method call
- Space Complexity: O(1) - single command mapping dict
- Blocking: `connect()` blocks ~4 seconds (Arduino reset)

---

### 2.3 Class: `MockMotorDriver`

**File:** `src/drivers/mock_motor_driver.py`

**Signature:**
```python
from src.interfaces.motor_interface import IMotorDriver
import logging
from typing import Dict, List

class MockMotorDriver:
    """
    Simulated motor driver for development/testing.
    
    Implements IMotorDriver interface without requiring physical hardware.
    Records all commands for inspection and logs activity.
    """
    
    def __init__(self):
        """Initialize mock driver with empty command history."""
        ...
    
    def connect(self, port: str, baud: int) -> bool:
        """
        Simulate connection (always succeeds).
        
        Logs port/baud parameters but performs no I/O.
        """
        ...
    
    def send_command(self, command: str, speed: int) -> None:
        """
        Simulate command execution.
        
        Records command in history and logs action.
        Respects same validation rules as real driver.
        """
        ...
    
    def stop(self) -> None:
        """Simulate stop command."""
        ...
    
    def disconnect(self) -> None:
        """Simulate disconnect (always succeeds)."""
        ...
    
    def get_command_history(self) -> List[Dict[str, any]]:
        """
        Retrieve recorded command history for testing.
        
        Returns:
            List of dicts with keys: 'command', 'speed', 'timestamp'
        """
        ...
    
    def clear_history(self) -> None:
        """Clear command history (useful for test isolation)."""
        ...
```

**Behavior Specification:**

- **Input Validation:**
  - Same validation rules as `IMotorDriver` contract
  - Command must be valid (case-insensitive)
  - Speed must be 0-100
  
- **Processing Logic:**
  1. `connect()`: Set internal `_connected` flag to True, log params
  2. `send_command()`: Append to `_command_history` list with timestamp, log INFO
  3. `stop()`: Append "STOP" to history, log INFO
  4. No actual I/O operations performed

- **Output Guarantee:**
  - `connect()` always returns `True`
  - Commands recorded with ISO-8601 timestamp
  - History preserved until `clear_history()` or object destruction

- **Side Effects:**
  - Writes to logger (INFO level)
  - Appends to internal command history list
  - No serial communication

**Error Handling:**
- **Invalid command** → Raise `ValueError` (same as real driver)
- **Not connected** → Raise `RuntimeError` (same as real driver)
- **No critical failures** (mock cannot have hardware issues)

**Performance Requirements:**
- Time Complexity: O(1) per command
- Space Complexity: O(n) where n = number of commands recorded
- Blocking: None (all operations instantaneous)

---

### 2.4 Service Update: `HardwareManager`

**File:** `src/services/hardware_manager.py`

**Signature:**
```python
from src.interfaces.motor_interface import IMotorDriver
import threading
import logging
from typing import Optional

class HardwareManager:
    """
    Central hardware coordination service.
    
    Manages driver lifecycle and provides unified interface
    for hardware control across the application.
    """
    
    def __init__(self, config: dict):
        """
        Initialize hardware manager with configuration.
        
        Args:
            config: Dict with keys:
                - SIMULATION_MODE: bool (default False)
                - SERIAL_PORT: str (default '/dev/ttyUSB0')
                - BAUD_RATE: int (default 9600)
        """
        self.config = config
        self.driver: Optional[IMotorDriver] = None
        self._connection_thread: Optional[threading.Thread] = None
        self._connected = False
        self._lock = threading.Lock()
    
    def _get_driver(self) -> IMotorDriver:
        """
        Factory method: Select driver based on configuration.
        
        Returns:
            IMotorDriver instance (Mock or Legacy-wrapped Real)
        """
        if self.config.get("SIMULATION_MODE", False):
            from src.drivers.mock_motor_driver import MockMotorDriver
            logging.info("HardwareManager: Using MockMotorDriver")
            return MockMotorDriver()
        else:
            from src.drivers.legacy_motor_adapter import LegacyMotorAdapter
            logging.info("HardwareManager: Using LegacyMotorAdapter")
            return LegacyMotorAdapter()
    
    def initialize_hardware(self) -> None:
        """
        Start hardware initialization in background thread.
        
        Non-blocking: Returns immediately, connection happens async.
        Use is_connected() to check status.
        """
        with self._lock:
            if self.driver is None:
                self.driver = self._get_driver()
            
            # Prevent multiple connection attempts
            if self._connection_thread and self._connection_thread.is_alive():
                logging.warning("Connection already in progress")
                return
            
            self._connection_thread = threading.Thread(
                target=self._connect_safe,
                daemon=True
            )
            self._connection_thread.start()
    
    def _connect_safe(self) -> None:
        """
        Thread-safe connection handler.
        
        Handles 4-second blocking Arduino reset without freezing app.
        """
        try:
            port = self.config.get("SERIAL_PORT", "/dev/ttyUSB0")
            baud = self.config.get("BAUD_RATE", 9600)
            
            logging.info(f"Connecting to motor controller: {port} @ {baud}")
            success = self.driver.connect(port, baud)
            
            with self._lock:
                self._connected = success
            
            if success:
                logging.info("Motor controller connected successfully")
            else:
                logging.error("Motor controller connection failed")
        except Exception as e:
            logging.error(f"Connection error: {e}", exc_info=True)
            with self._lock:
                self._connected = False
    
    def send_motor_command(self, command: str, speed: int = 50) -> None:
        """
        Send command to motor driver.
        
        Args:
            command: Movement command (FORWARD, BACKWARD, LEFT, RIGHT, STOP)
            speed: Desired speed 0-100 (may be ignored by legacy hardware)
        
        Raises:
            RuntimeError: If hardware not initialized or not connected
        """
        if self.driver is None:
            raise RuntimeError("Hardware not initialized. Call initialize_hardware() first.")
        
        self.driver.send_command(command, speed)
    
    def stop_motors(self) -> None:
        """Emergency stop for all motors."""
        if self.driver is None:
            raise RuntimeError("Hardware not initialized")
        self.driver.stop()
    
    def is_connected(self) -> bool:
        """Thread-safe connection status check."""
        with self._lock:
            return self._connected
    
    def shutdown(self) -> None:
        """Clean shutdown of hardware connections."""
        if self.driver is not None:
            try:
                self.driver.stop()
                self.driver.disconnect()
                logging.info("Hardware shutdown complete")
            except Exception as e:
                logging.error(f"Error during shutdown: {e}")
```

**Behavior Specification:**

- **Input Validation:**
  - Config dict must contain valid types for SIMULATION_MODE (bool), SERIAL_PORT (str), BAUD_RATE (int)
  - Commands passed to `send_motor_command` validated by driver

- **Processing Logic:**
  1. `__init__`: Store config, initialize state variables
  2. `initialize_hardware()`: Spawn background thread for connection
  3. `_connect_safe()`: Thread worker that calls driver.connect() with 4s blocking
  4. `send_motor_command()`: Direct pass-through to driver after null check
  5. Thread-safe flag access via `threading.Lock`

- **Output Guarantee:**
  - `initialize_hardware()` returns immediately (non-blocking)
  - Connection status available via `is_connected()`
  - Commands execute synchronously after connection

- **Side Effects:**
  - Spawns daemon thread for hardware connection
  - Logs initialization events
  - Modifies `_connected` flag (thread-safe)

**Error Handling:**
- **Not initialized** → Raise `RuntimeError("Hardware not initialized. Call initialize_hardware() first.")`
- **Connection failure** → Log error, set `_connected = False`, do not raise
- **Driver exceptions** → Propagate to caller
- **Shutdown errors** → Log but suppress (cleanup should not crash app)

**Performance Requirements:**
- Time Complexity: O(1) for all operations
- Space Complexity: O(1)
- Threading: One daemon thread for connection, auto-cleanup on exit

---

## 3. DEPENDENCIES

**This module CALLS:**
- `motor_controller.MotorController` (legacy) - Hardware communication
- `logging` - Event tracking
- `threading.Thread` - Non-blocking initialization
- `typing.Protocol` - Interface definition

**This module is CALLED BY:**
- `src/api/routes.py` - Web API endpoints
- `src/cli/commands.py` - CLI control interface
- `src/services/navigation_service.py` - High-level movement logic

---

## 4. DATA STRUCTURES

### Command Mapping (Internal to LegacyMotorAdapter)

```python
COMMAND_MAP = {
    "FORWARD": "move_forward",
    "BACKWARD": "move_backward",
    "LEFT": "turn_left",
    "RIGHT": "turn_right",
    "STOP": "stop"
}
```

### Command History Entry (MockMotorDriver)

```python
{
    "command": str,      # e.g., "FORWARD"
    "speed": int,        # 0-100
    "timestamp": str     # ISO-8601 format
}
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

**Assumed Constraints (No `system_constraints.md` provided):**
- Must use Python 3.8+ type hints
- Must not modify legacy `motor_controller.py` code
- Must support both real hardware and simulation modes
- Must handle blocking operations without freezing application
- Must use standard library + `pyserial` only (no exotic dependencies)

---

## 6. MEMORY COMPLIANCE

**No `_memory_snippet.txt` provided.**

If project memory exists, this contract must be reviewed for compliance before implementation.

---

## 7. ACCEPTANCE CRITERIA

### Test Case 1: Mock Driver Command Recording
**Scenario:** Development mode with simulation
- **Setup:** `config = {"SIMULATION_MODE": True}`
- **Input:** 
  ```python
  hw = HardwareManager(config)
  hw.initialize_hardware()
  hw.send_motor_command("FORWARD", 75)
  hw.send_motor_command("LEFT", 50)
  hw.stop_motors()
  ```
- **Expected Output:** 
  - No exceptions raised
  - `hw.driver.get_command_history()` contains 3 entries
  - Entries: `[{"command": "FORWARD", "speed": 75, ...}, {"command": "LEFT", "speed": 50, ...}, {"command": "STOP", "speed": 0, ...}]`
- **Expected Behavior:** 
  - Logs show "Using MockMotorDriver"
  - No serial communication attempted

### Test Case 2: Legacy Adapter Integration
**Scenario:** Production mode with real hardware
- **Setup:** `config = {"SIMULATION_MODE": False, "SERIAL_PORT": "/dev/ttyUSB0", "BAUD_RATE": 9600}`
- **Input:**
  ```python
  hw = HardwareManager(config)
  hw.initialize_hardware()
  time.sleep(5)  # Wait for background connection
  hw.send_motor_command("FORWARD", 100)
  ```
- **Expected Output:**
  - `hw.is_connected()` returns `True` after 5 seconds
  - Legacy controller's `move_forward()` method is called
  - Warning logged about ignored speed parameter
- **Expected Behavior:**
  - Serial command `b'W'` sent to `/dev/ttyUSB0`
  - No blocking during `initialize_hardware()` call
  - Main thread remains responsive

### Test Case 3: Invalid Command Error
**Scenario:** Error handling validation
- **Input:**
  ```python
  hw = HardwareManager({"SIMULATION_MODE": True})
  hw.initialize_hardware()
  hw.send_motor_command("TURBO_MODE", 200)
  ```
- **Expected Exception:** `ValueError`
- **Expected Message:** `"Invalid command: TURBO_MODE. Must be one of: FORWARD, BACKWARD, LEFT, RIGHT, STOP"`

### Test Case 4: Not Connected Error
**Scenario:** Command before initialization
- **Input:**
  ```python
  hw = HardwareManager({"SIMULATION_MODE": True})
  hw.send_motor_command("FORWARD", 50)  # No initialize_hardware() call
  ```
- **Expected Exception:** `RuntimeError`
- **Expected Message:** `"Hardware not initialized. Call initialize_hardware() first."`

### Test Case 5: Thread Safety
**Scenario:** Concurrent connection status checks
- **Input:**
  ```python
  hw = HardwareManager({"SIMULATION_MODE": False})
  hw.initialize_hardware()
  
  # Multiple threads checking status simultaneously
  results = []
  def check():
      results.append(hw.is_connected())
  
  threads = [threading.Thread(target=check) for _ in range(10)]
  [t.start() for t in threads]
  [t.join() for t in threads]
  ```
- **Expected Output:** All results are consistent (no race conditions)
- **Expected Behavior:** No deadlocks, no corrupted state

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:** 
- `src/interfaces/motor_interface.py`
- `src/drivers/legacy_motor_adapter.py`
- `src/drivers/mock_motor_driver.py`
- `src/services/hardware_manager.py`

**Contract Reference:** `docs/contracts/motor_driver_integration.md` v1.0

---

## Strict Constraints (NON-NEGOTIABLE)

1. **DO NOT modify `motor_controller.py`** - Legacy code must remain untouched
2. **All public methods MUST have type hints** - Enforce `IMotorDriver` protocol
3. **Thread safety required** - Use `threading.Lock` for shared state in `HardwareManager`
4. **Blocking operations MUST run in background threads** - `connect()` cannot freeze main thread
5. **Exception messages MUST match contract exactly** - Error text is part of the interface
6. **Case-insensitive command handling** - "forward" and "FORWARD" are equivalent
7. **Speed parameter validation** - Must be 0-100, warn if outside range
8. **Logging required** - All state changes must be logged at INFO level

---

## Memory Compliance (MANDATORY)

**No memory snippet provided.**

Implementer must check for `_memory_snippet.txt` before starting work and apply any rules found.

---

## Required Logic

### For `LegacyMotorAdapter`:

1. **Initialization:**
   - Import legacy `motor_controller.MotorController`
   - Store reference to singleton instance
   - Initialize connection state flag

2. **Connect Method:**
   - Update legacy controller's `port` and `baudrate` attributes
   - Call legacy `connect()` method
   - Return boolean result (do not raise on failure)
   - Log connection attempt with parameters

3. **Send Command Method:**
   - Normalize command string to uppercase
   - Look up method name in `COMMAND_MAP`
   - If not found, raise `ValueError` with exact contract message
   - Log warning: "Speed parameter {speed} ignored by legacy hardware (uses relative +/- only)"
   - Call legacy method (e.g., `self.legacy_controller.move_forward()`)

4. **Stop Method:**
   - Direct call to `legacy_controller.stop()`

5. **Disconnect Method:**
   - Check if legacy controller has active serial connection
   - Close serial port safely
   - Log disconnection

### For `MockMotorDriver`:

1. **Initialization:**
   - Create empty list `_command_history = []`
   - Set `_connected = False`

2. **Connect Method:**
   - Set `_connected = True`
   - Log: "Mock connection established: {port} @ {baud}"
   - Always return `True`

3. **Send Command Method:**
   - Validate command is in allowed set (case-insensitive)
   - If not connected, raise `RuntimeError`
   - Create history entry dict with command, speed, ISO timestamp
   - Append to `_command_history`
   - Log: "Mock command executed: {command} at speed {speed}"

4. **Get History Method:**
   - Return copy of `_command_history` (prevent external mutation)

### For `HardwareManager`:

1. **Factory Method (`_get_driver`):**
   - Read `SIMULATION_MODE` from config
   - If True: Import and return `MockMotorDriver()`
   - If False: Import and return `LegacyMotorAdapter()`
   - Log which driver was selected

2. **Initialize Hardware:**
   - Check if driver already exists, create if not
   - Create daemon thread targeting `_connect_safe`
   - Start thread immediately
   - Return without waiting

3. **Connect Safe (Thread Worker):**
   - Extract port/baud from config with defaults
   - Wrap `driver.connect()` in try-except
   - Update `_connected` flag with lock protection
   - Log success or failure

4. **Send Command:**
   - Check `driver is not None`, raise if uninitialized
   - Pass command and speed directly to `driver.send_command()`
   - Let driver exceptions propagate

---

## Integration Points

**Must call:**
- `motor_controller.MotorController.connect()` - In `LegacyMotorAdapter.connect()`
- `motor_controller.MotorController.move_forward()` - When command="FORWARD"
- `motor_controller.MotorController.stop()` - In adapter and direct stop methods

**Will be called by:**
- API routes (`/api/motor/move`) - Via `HardwareManager.send_motor_command()`
- Navigation service - Via `HardwareManager` for autonomous movement
- CLI commands - For manual control during development

**Critical Dependencies:**
- `pyserial` must be in `requirements.txt`
- Legacy `motor_controller.py` must be importable
- `logging` configured before hardware initialization

---

## Success Criteria

- [ ] All method signatures match contract exactly (including type hints)
- [ ] All 5 acceptance test cases pass
- [ ] `mypy` type checking passes with no errors
- [ ] No modifications to `motor_controller.py`
- [ ] Thread-safe access to `_connected` flag
- [ ] Background connection thread is daemon (auto-cleanup on exit)
- [ ] Speed parameter warnings logged in adapter
- [ ] Mock driver records command history correctly
- [ ] Exception messages match contract word-for-word
- [ ] Code passes linting (flake8/pylint)
- [ ] Auditor approval required before merge

---

## Post-Implementation Checklist

1. Run unit tests: `pytest tests/test_motor_driver.py`
2. Run integration test with mock: `pytest tests/integration/test_hardware_manager.py`
3. Verify type safety: `mypy src/`
4. Manual verification: Start app in simulation mode, send commands via API
5. Hardware verification (if available): Connect to real robot, test movement
6. Documentation: Update `docs/API_MAP_lite.md` with new modules
7. Submit for Auditor review

---

✅ **Contract Created:** `docs/contracts/motor_driver_integration.md`
📋 **Work Order Generated** for Implementer
🔍 **Next Verification Command:** `/verify-context: motor_driver_integration.md, API_MAP_lite.md`
👉 **Next Agent:** Implementer (AGENTS/02_implementer.md)

**ARCHITECT SIGNING OFF.**