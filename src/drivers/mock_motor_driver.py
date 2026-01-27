"""Mock Motor Driver for Simulation.

This module provides a simulation-safe implementation of the IMotorDriver
interface. It logs commands and maintains a history of actions without
accessing physical hardware.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Set

from src.interfaces.motor_interface import IMotorDriver


class MockMotorDriver(IMotorDriver):
    """Mock implementation of the motor driver for testing and simulation.

    This class mimics the behavior of a real driver but directs output
    to an internal history log instead of a serial port.
    """

    def __init__(self) -> None:
        """Initialize the mock driver."""
        self._connected = False
        self._command_history: List[Dict[str, Any]] = []
        self._logger = logging.getLogger(__name__)

    def connect(self, port: str, baud: int) -> bool:
        """Simulate a hardware connection.

        Args:
            port: Target port (non-empty string).
            baud: Target baud rate (positive integer).

        Returns:
            True always, simulating successful connection.

        Raises:
            ValueError: If port is empty or baud is non-positive.
        """
        if not isinstance(port, str) or not port:
            raise ValueError("Port must be non-empty string")

        if not isinstance(baud, int) or baud <= 0:
            raise ValueError("Baud must be positive integer")

        self._logger.info(f"Mock connection established: {port} @ {baud}")
        self._connected = True
        return True

    def send_command(self, command: str, speed: int) -> None:
        """Record a movement command in history.

        Args:
            command: Movement command (FORWARD, BACKWARD, LEFT, RIGHT, STOP).
            speed: Speed value (0-100).

        Raises:
            RuntimeError: If not connected.
            TypeError: If arguments are of wrong type.
            ValueError: If command is not valid.
        """
        if not self._connected:
            raise RuntimeError("Driver not connected. Call connect() first.")

        if not isinstance(command, str):
            raise TypeError(f"Command must be string, got {type(command)}")

        if not isinstance(speed, int):
            raise TypeError(f"Speed must be integer, got {type(speed)}")

        command = command.upper().strip()

        VALID_COMMANDS: Set[str] = {"FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"}

        if command not in VALID_COMMANDS:
            valid = ", ".join(sorted(VALID_COMMANDS))
            raise ValueError(f"Invalid command: {command}. Must be one of: {valid}")

        if speed < 0 or speed > 100:
            self._logger.warning(f"Speed {speed} outside recommended range 0-100")

        entry = {
            "command": command,
            "speed": speed,
            "timestamp": datetime.now().isoformat()
        }

        self._command_history.append(entry)
        self._logger.info(f"Mock command executed: {command} at speed {speed}")

    def stop(self) -> None:
        """Record a stop command in history.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._connected:
            raise RuntimeError("Driver not connected. Call connect() first.")

        entry = {
            "command": "STOP",
            "speed": 0,
            "timestamp": datetime.now().isoformat()
        }

        self._command_history.append(entry)
        self._logger.info("Mock stop command executed")

    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        self._logger.info("Mock driver disconnected")

    def get_command_history(self) -> List[Dict[str, Any]]:
        """Retrieve the history of executed commands.

        Returns:
            A list of dictionaries containing command, speed, and timestamp.
        """
        return self._command_history.copy()

    def clear_history(self) -> None:
        """Clear the internal command history log."""
        self._command_history.clear()
        self._logger.info("Command history cleared")