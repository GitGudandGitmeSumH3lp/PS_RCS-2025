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

# ESC deadband compensation: map 0–255 to MIN_EFFECTIVE_PWM–255
MIN_EFFECTIVE_PWM = 40   # Tune based on your motors (start with 40)


class MotorController:
    """Communicates with Arduino motor controller via serial."""

    # Map high‑level commands to single characters expected by Arduino
    _CMD_MAP = {
        'forward': 'W',
        'backward': 'S',
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
            speed:   Speed 0-255. 0 = stop (if command is not 'stop'),
                    255 = full speed. For 'stop', speed is ignored.
            source:  "manual" or "auto". If "auto", speed is remapped to
                     MIN_EFFECTIVE_PWM..255 for low‑speed control.

        Returns:
            True if command was sent successfully.
        """
        cmd_lower = command.lower()
        if cmd_lower not in self._CMD_MAP:
            logger.warning(f"Unknown motor command: {command}")
            return False

        char_cmd = self._CMD_MAP[cmd_lower]

        # Clamp speed to 0-255
        speed = max(0, min(255, speed))

        # ESC deadband compensation: apply only for auto mode (and not for stop)
        if source == "auto" and char_cmd != 'X' and speed > 0:
            speed = MIN_EFFECTIVE_PWM + int((255 - MIN_EFFECTIVE_PWM) * speed / 255)

        with self._lock:
            if not self._connected or not self.serial_conn or not self.serial_conn.is_open:
                logger.error("Motor controller not connected")
                return False

            try:
                # Send 2-byte packet: speed byte then command byte
                packet = bytes([speed]) + char_cmd.encode('ascii')
                self.serial_conn.write(packet)
                self.serial_conn.flush()
                logger.info(f"Sent motor command: {char_cmd} speed={speed} (source={source})")
                return True
            except Exception as e:
                logger.error(f"Error sending motor command: {e}")
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