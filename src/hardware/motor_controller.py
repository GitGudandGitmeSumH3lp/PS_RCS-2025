# src/hardware/motor_controller.py
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: motor_controller.py
Description: Low-level motor controller communicating with Arduino over serial.
"""

import logging
import threading
import time
import serial
from typing import Optional

logger = logging.getLogger(__name__)

# --- HARDWARE SAFETY LIMITS ---
# MIN: Minimum PWM required to overcome physical friction (Deadband)
# MAX: Maximum PWM the battery can handle before browning-out/crashing
# Tuned for heavier prototype – increased MAX from 90 to 105 for more torque.
MIN_EFFECTIVE_PWM = 40
MAX_SAFE_PWM = 120          # Increased 2026-03-04 (was 90)


class MotorController:
    """Communicates with Arduino motor controller via serial."""

    # Map high‑level commands to single characters expected by Arduino
    # NOTE: Forward/backward swapped on 2026-03-04 to correct wiring orientation.
    _CMD_MAP = {
        'forward': 'S',      # Was 'W' – swapped to fix reversed movement
        'backward': 'W',     # Was 'S' – swapped to fix reversed movement
        'left': 'A',
        'right': 'D',
        'stop': 'X',
    }

    def __init__(self, port: Optional[str] = None, baudrate: int = 9600) -> None:
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self._connected = False
        self._lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False

    def connect(self, port: str, baudrate: int) -> bool:
        """Establish serial connection to Arduino."""
        try:
            self.serial_conn = serial.Serial(
                port,
                baudrate,
                timeout=1,
                write_timeout=1,
                exclusive=True
            )
            self._connected = True
            logger.info(f"Connected to motor controller on {port} @ {baudrate}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to motor controller: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def send_command(self, command: str, speed: int = 0, source: str = "manual") -> bool:
        """
        Send a motor command with optional speed.

        Args:
            command: One of 'forward', 'backward', 'left', 'right', 'stop'.
            speed:   Speed 0-255 from the UI.
            source:  "manual" or "auto".
        """
        cmd_lower = command.lower()
        if cmd_lower not in self._CMD_MAP:
            logger.warning(f"Unknown motor command: {command}")
            return False

        char_cmd = self._CMD_MAP[cmd_lower]

        # 1. Clamp raw input speed to 0-255 just in case
        speed = max(0, min(255, speed))

        # 2. THE GOVERNOR: Scale the UI's 1-255 range into our safe physical range (40-105)
        # This fixes the battery brown-out AND the wheel friction stall in both modes!
        if char_cmd != 'X' and speed > 0:
            speed = MIN_EFFECTIVE_PWM + int((MAX_SAFE_PWM - MIN_EFFECTIVE_PWM) * (speed / 255.0))

        with self._lock:
            if not self._connected or not self.serial_conn or not self.serial_conn.is_open:
                logger.error("Motor controller not connected")
                return False

            try:
                # Send command byte FIRST, then speed byte (matches Arduino logic)
                packet = char_cmd.encode('ascii') + bytes([speed])
                
                self.serial_conn.write(packet)
                self.serial_conn.flush()
                logger.info(f"Sent motor command: {char_cmd} speed={speed} (source={source})")
                return True
            except Exception as e:
                logger.error(f"Error sending motor command: {e}")
                return False

    def beep(self, duration_ms: int) -> bool:
        """
        Sound the buzzer for a given duration (in milliseconds).
        Duration 0 turns the buzzer off immediately.
        """
        if not self._connected or not self.serial_conn or not self.serial_conn.is_open:
            logger.error("Cannot beep – motor controller not connected")
            return False

        # Convert ms to 100ms units, clamp to 0-255
        if duration_ms <= 0:
            duration_byte = 0
        else:
            duration_byte = max(1, min(255, duration_ms // 100))

        packet = b'B' + bytes([duration_byte])
        try:
            with self._lock:
                self.serial_conn.write(packet)
                self.serial_conn.flush()
                logger.info(f"Buzzer command sent: duration={duration_ms}ms")
            return True
        except Exception as e:
            logger.error(f"Failed to send buzzer command: {e}")
            return False

    def disconnect(self) -> None:
        """Close serial connection."""  
        with self._lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.close()
                    logger.info("Motor controller disconnected")
                except Exception as e:
                    logger.error(f"Error disconnecting motor controller: {e}")
            self._connected = False

    def stop(self) -> None:
        """Convenience method to send stop command."""
        self.send_command('stop')