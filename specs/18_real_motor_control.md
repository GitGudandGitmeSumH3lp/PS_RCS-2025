# FEATURE SPEC: Real Motor Control Integration

**Date:** 2026-05-22  
**Status:** Feasible (Actionable)

## 1. THE VISION
**User Story:** As a Remote Operator, I want the dashboard "Motor Control" buttons to physically move the robot using the Arduino hardware, so that I can drive the unit remotely.

## 2. ARCHITECTURAL DECISIONS
*   **Driver Protocol:** We will strictly adhere to the `W, A, S, D, X` (Forward, Left, Back, Right, Stop) protocol over Serial (USB).
*   **Hardware Reality:** The user specified a **PCA9685** driver. This is a PWM driver often used for Servos or via a motor shield. The provided `wheels.ino` was a test script. We must replace it with a firmware that translates `W/A/S/D` into PCA9685 PWM signals.
*   **Speed Control:** The current protocol is binary (Move/Stop). We will ignore the speed slider for this iteration to ensure stability, but the Python driver will accept the argument for future expansion.

## 3. ATOMIC TASKS (The Roadmap)

*   [ ] **Update Config:** Add `MOTOR_PORT` and `MOTOR_BAUD_RATE` to `src/core/config.py`.
*   [ ] **Create Driver:** Create `src/hardware/motor_controller.py` implementing the robust serial communication (Thread-safe, Keep-Alive).
*   [ ] **Update Manager:** Modify `src/services/hardware_manager.py` to use the real driver instead of the mock.
*   [ ] **Create Firmware:** Write a new `arduino/wheels.ino` that actually implements the logic (W=Forward, X=Stop) using the PCA9685 library.

---

## 4. INTERFACE SKETCHES

### A. Configuration (`src/core/config.py`)
```python
# Add these lines to the Settings class
MOTOR_PORT: str = "/dev/ttyUSB0"  # Adjust for Windows (e.g., COM3)
MOTOR_BAUD_RATE: int = 9600
```

### B. The Firmware Logic (`arduino/wheels.ino`)
*This replaces the test script.*
```cpp
// Pseudocode for the new firmware
void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    switch(toupper(cmd)) {
      case 'W': moveForward(); break;
      case 'S': moveBackward(); break;
      case 'A': turnLeft(); break;
      case 'D': turnRight(); break;
      case 'X': stopMotors(); break;
    }
  }
}
```

---

## 5. IMPLEMENTATION SPECIFICATION

### FILE 1: `src/core/config.py` (Update)
*Action: Add motor settings.*

```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing config ...
    
    # Motor Control
    MOTOR_PORT: str = "COM3" if os.name == 'nt' else "/dev/ttyUSB0"
    MOTOR_BAUD_RATE: int = 9600
    
    class Config:
        env_file = ".env"
```

### FILE 2: `src/hardware/motor_controller.py` (New)
*Action: This is the robust driver provided in the context, cleaned up for the project structure.*

```python
import serial
import time
import logging
import threading

class MotorController:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(MotorController, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, 'initialized', False):
            return
        self.initialized = True
        self.serial_conn = None
        self.logger = logging.getLogger("MotorController")
        self.is_connected = False
        self.io_lock = threading.Lock()

    def connect(self, port: str, baudrate: int = 9600) -> bool:
        with self.io_lock:
            if self.is_connected:
                return True
            try:
                self.serial_conn = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=1,
                    write_timeout=1
                )
                time.sleep(2)  # Wait for Arduino reset
                self.is_connected = True
                self.logger.info(f"Connected to motor controller on {port}")
                return True
            except Exception as e:
                self.logger.error(f"Connection failed: {e}")
                return False

    def send_command(self, command: str, speed: int = 0) -> bool:
        """
        Maps generic commands to Serial characters.
        command: 'forward', 'backward', 'left', 'right', 'stop'
        """
        cmd_map = {
            'forward': 'W',
            'backward': 'S',
            'left': 'A',
            'right': 'D',
            'stop': 'X'
        }
        
        char_cmd = cmd_map.get(command.lower())
        if not char_cmd:
            self.logger.warning(f"Unknown command: {command}")
            return False

        with self.io_lock:
            if not self.is_connected or not self.serial_conn:
                return False
            try:
                self.serial_conn.write(char_cmd.encode())
                return True
            except Exception as e:
                self.logger.error(f"Send failed: {e}")
                self.disconnect()
                return False

    def stop(self):
        self.send_command('stop')

    def disconnect(self):
        with self.io_lock:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.is_connected = False
```

### FILE 3: `src/services/hardware_manager.py` (Refactor)
*Action: Import and use the real controller.*

```python
# ... imports ...
from src.hardware.motor_controller import MotorController

class HardwareManager:
    def __init__(self, settings: Settings, state: RobotState):
        self.settings = settings
        self.state = state
        self.motor_controller = MotorController()  # Singleton
        
        # Auto-connect on startup
        self._connect_motor()

    def _connect_motor(self):
        try:
            if self.motor_controller.connect(self.settings.MOTOR_PORT, self.settings.MOTOR_BAUD_RATE):
                self.state.update_status(motor_connected=True)
            else:
                self.state.update_status(motor_connected=False)
        except Exception as e:
            logging.error(f"Motor init failed: {e}")

    def send_motor_command(self, command: str, speed: int = 50) -> bool:
        # Re-try connection if dropped? Optional.
        return self.motor_controller.send_command(command, speed)
    
    # ... rest of file (lidar, etc) ...
```

### FILE 4: `arduino/wheels.ino` (Rewrite)
*Action: Actual differential drive logic using PCA9685.*

```cpp
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// CONFIGURATION
// Assuming Continuous Rotation Servos or a Shield mapping
// Adjust these channel numbers to match your wiring!
#define LEFT_MOTOR_CH  0
#define RIGHT_MOTOR_CH 1

// Pulse widths for continuous servos (approximate)
#define STOP_PULSE     307 // ~1.5ms (Neutral)
#define FWD_PULSE      410 // ~2.0ms (Full Forward)
#define REV_PULSE      205 // ~1.0ms (Full Reverse)

void setup() {
  Serial.begin(9600);
  pwm.begin();
  pwm.setPWMFreq(50);
  stopMotors();
  Serial.println("READY");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    cmd = toupper(cmd);
    
    switch(cmd) {
      case 'W': moveForward(); break;
      case 'S': moveBackward(); break;
      case 'A': turnLeft(); break;
      case 'D': turnRight(); break;
      case 'X': stopMotors(); break;
    }
  }
}

void setMotor(int channel, int pulse) {
  pwm.setPWM(channel, 0, pulse);
}

void moveForward() {
  setMotor(LEFT_MOTOR_CH, FWD_PULSE);
  setMotor(RIGHT_MOTOR_CH, FWD_PULSE); // If one motor is inverted, swap to REV_PULSE
}

void moveBackward() {
  setMotor(LEFT_MOTOR_CH, REV_PULSE);
  setMotor(RIGHT_MOTOR_CH, REV_PULSE);
}

void turnLeft() {
  setMotor(LEFT_MOTOR_CH, REV_PULSE);
  setMotor(RIGHT_MOTOR_CH, FWD_PULSE);
}

void turnRight() {
  setMotor(LEFT_MOTOR_CH, FWD_PULSE);
  setMotor(RIGHT_MOTOR_CH, REV_PULSE);
}

void stopMotors() {
  setMotor(LEFT_MOTOR_CH, STOP_PULSE);
  setMotor(RIGHT_MOTOR_CH, STOP_PULSE);
}
```

## 6. NEXT STEPS
1.  **Analyst/Implementer:** Create the files exactly as specified above.
2.  **Hardware:** Upload the new `wheels.ino` to the Arduino.
3.  **Config:** Ensure `.env` or `config.py` has the correct COM port.