"""Legacy Motor Controller Adapter.

This module provides an adapter pattern implementation to bridge the
standard IMotorDriver interface with the legacy 'motor_controller' library.
It handles module loading, connection management, and command translation.
"""

import logging
from typing import Optional

from src.interfaces.motor_interface import IMotorDriver


class LegacyMotorAdapter(IMotorDriver):
    """Adapter for legacy motor hardware controllers.

    This class wraps a legacy `MotorController` object (or attempts to import it)
    and exposes it via the standard `IMotorDriver` interface.

    Attributes:
        legacy_controller: The underlying controller instance.
    """

    def __init__(self, legacy_controller: Optional[object] = None) -> None:
        """Initialize the legacy adapter.

        Args:
            legacy_controller: An existing instance of a legacy MotorController.
                If None, the adapter attempts to import `motor_controller` and
                instantiate a new one.

        Raises:
            ImportError: If legacy_controller is None and the 'motor_controller'
                module cannot be found.
        """
        self._connected = False
        self._logger = logging.getLogger(__name__)

        if legacy_controller is None:
            try:
                # pylint: disable=import-outside-toplevel
                from motor_controller import MotorController
                self.legacy_controller = MotorController()
            except ImportError as e:
                self._logger.error(f"Failed to import legacy motor controller: {e}")
                raise ImportError("Legacy motor_controller module not found") from e
        else:
            self.legacy_controller = legacy_controller

    def connect(self, port: str, baud: int) -> bool:
        """Connect to the physical motor hardware.

        Sets the port and baudrate on the legacy controller and attempts
        connection.

        Args:
            port: Serial port path (must be non-empty string).
            baud: Baud rate (must be positive integer).

        Returns:
            True if connection succeeded, False otherwise.

        Raises:
            ValueError: If port is empty or baud is non-positive.
            ConnectionError: If a critical hardware failure occurs.
        """
        if not isinstance(port, str) or not port:
            raise ValueError("Port must be non-empty string")

        if not isinstance(baud, int) or baud <= 0:
            raise ValueError("Baud must be positive integer")

        self._logger.info(f"Connecting to motor controller: {port} @ {baud}")

        try:
            if hasattr(self.legacy_controller, 'port'):
                self.legacy_controller.port = port
            if hasattr(self.legacy_controller, 'baudrate'):
                self.legacy_controller.baudrate = baud

            result = self.legacy_controller.connect()

            self._connected = result
            return result

        except ConnectionError as e:
            self._logger.error(f"Critical hardware failure: {e}")
            raise ConnectionError(f"Critical hardware failure: {e}") from e
        except Exception as e:
            self._logger.error(f"Connection failed: {e}")
            self._connected = False
            return False

    def send_command(self, command: str, speed: int) -> None:
        """Translate and send a command to the legacy controller.

        Note:
            The legacy hardware does not support absolute speed setting via
            this method. The `speed` parameter is validated but ignored for
            hardware control, logging a warning instead.

        Args:
            command: Movement command (FORWARD, BACKWARD, LEFT, RIGHT, STOP).
            speed: Intended speed (0-100). Checked for range but ignored by hardware.

        Raises:
            RuntimeError: If not connected.
            TypeError: If arguments are of wrong type.
            ValueError: If command is not in the supported map.
        """
        if not self._connected:
            raise RuntimeError("Driver not connected. Call connect() first.")

        if not isinstance(command, str):
            raise TypeError(f"Command must be string, got {type(command)}")

        if not isinstance(speed, int):
            raise TypeError(f"Speed must be integer, got {type(speed)}")

        command = command.upper().strip()

        COMMAND_MAP = {
            "FORWARD": "move_forward",
            "BACKWARD": "move_backward",
            "LEFT": "turn_left",
            "RIGHT": "turn_right",
            "STOP": "stop"
        }

        if command not in COMMAND_MAP:
            valid = ", ".join(sorted(COMMAND_MAP.keys()))
            raise ValueError(f"Invalid command: {command}. Must be one of: {valid}")

        if speed < 0 or speed > 100:
            self._logger.warning(f"Speed {speed} outside recommended range 0-100")

        self._logger.warning(
            f"Speed parameter {speed} ignored by legacy hardware (uses relative +/- only)"
        )

        method_name = COMMAND_MAP[command]
        method = getattr(self.legacy_controller, method_name)
        method()

    def stop(self) -> None:
        """Halt the motors immediately.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._connected:
            raise RuntimeError("Driver not connected. Call connect() first.")

        self.legacy_controller.stop()

    def disconnect(self) -> None:
        """Close the connection to the legacy controller.

        Attempts to call `disconnect` or `close` on the underlying object.
        """
        if hasattr(self.legacy_controller, 'disconnect'):
            self.legacy_controller.disconnect()
        elif hasattr(self.legacy_controller, 'close'):
            self.legacy_controller.close()

        self._connected = False
        self._logger.info("Motor controller disconnected")