"""Motor Interface Definition.

This module defines the abstract base class for motor drivers, ensuring
consistent API surfaces for both legacy adapters and mock drivers.
"""

from abc import ABC, abstractmethod


class IMotorDriver(ABC):
    """Abstract base class for motor driver implementations.
    
    This interface defines the standard contract that all motor drivers
    must fulfill, including connection management and movement commands.
    """

    @abstractmethod
    def connect(self, port: str, baud: int) -> bool:
        """Establish connection to the motor controller.

        Args:
            port: Serial port identifier (e.g., '/dev/ttyUSB0', 'COM3').
            baud: Baud rate for communication (e.g., 9600, 115200).

        Returns:
            True if connection was successful, False otherwise.

        Raises:
            ValueError: If parameters are invalid.
            ConnectionError: If a hardware failure occurs.
        """
        pass

    @abstractmethod
    def send_command(self, command: str, speed: int) -> None:
        """Send a movement command to the motor controller.

        Args:
            command: Directional command ('FORWARD', 'BACKWARD', 'LEFT', 'RIGHT', 'STOP').
            speed: Speed value (0-100).

        Raises:
            RuntimeError: If driver is not connected.
            ValueError: If command is invalid.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Emergency stop the motors.

        Raises:
            RuntimeError: If driver is not connected.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Safely disconnect from the motor controller."""
        pass