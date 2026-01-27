"""
Thread-safe in-memory storage for real-time hardware sensor readings and system state.

This module serves as the central state repository accessed by both the
ServiceManager's background threads and Flask's read-only API endpoints,
ensuring atomic updates and consistent snapshots across concurrent operations.
"""

import copy
from datetime import datetime
from threading import RLock
from typing import Any, Dict, List, Optional, TypedDict


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

class ErrorRecord(TypedDict):
    """Record of a system or device error."""

    timestamp: datetime
    message: str
    device_id: Optional[str]


class DeviceReading(TypedDict):
    """Device state with timestamp."""

    data: Dict[str, Any]
    updated_at: datetime


class SystemMetadata(TypedDict):
    """System-level metadata and status."""

    emergency_stop: bool
    started_at: datetime
    errors: List[ErrorRecord]


class StateDict(TypedDict):
    """Complete system state structure."""

    lidar: Optional[DeviceReading]
    husky: Optional[DeviceReading]
    motor: Optional[DeviceReading]
    system: SystemMetadata


# ============================================================================
# STATE MANAGER
# ============================================================================


class StateManager:
    """
    Thread-safe state container for hardware data and system status.

    Attributes:
        _state: Internal dictionary storing device readings and system metadata
        _lock: Reentrant lock for thread-safe operations
    """

    def __init__(self) -> None:
        """
        Initialize empty state with system metadata section.

        Initial state structure:
        {
            "lidar": None,
            "husky": None,
            "motor": None,
            "system": {
                "emergency_stop": False,
                "started_at": datetime.utcnow(),
                "errors": []
            }
        }
        """
        self._lock = RLock()
        self._state: StateDict = {
            "lidar": None,
            "husky": None,
            "motor": None,
            "system": {
                "emergency_stop": False,
                "started_at": datetime.utcnow(),
                "errors": [],
            },
        }

    def update(self, device_id: str, data: Dict[str, Any]) -> None:
        """
        Atomically update the state for a specific device.

        Args:
            device_id: Device identifier (e.g., "lidar", "husky", "motor")
            data: Device reading dictionary containing sensor data

        Raises:
            ValueError: If device_id is empty string or None
            TypeError: If data is not a dictionary
        """
        # Input validation
        if not device_id:
            raise ValueError("device_id cannot be empty")

        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary")

        with self._lock:
            self._state[device_id] = {
                "data": copy.copy(data),
                "updated_at": datetime.utcnow(),
            }

    def get(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the latest reading for a specific device.

        Args:
            device_id: Device identifier to query

        Returns:
            Dictionary containing:
            {
                "data": {...},           # Device-specific payload
                "updated_at": datetime   # Timestamp of last update
            }
            Returns None if device has no data or device_id is invalid.

        Raises:
            ValueError: If device_id is empty string or None
        """
        # Input validation
        if not device_id:
            raise ValueError("device_id cannot be empty")

        with self._lock:
            device_state = self._state.get(device_id)
            if device_state is None:
                return None
            return copy.copy(device_state)

    def get_all(self) -> Dict[str, Any]:
        """
        Retrieve a snapshot of the entire system state.

        Returns:
            Deep copy of complete state dictionary containing all device
            readings and system metadata. Safe to modify without affecting
            internal state.

        Example return value:
        {
            "lidar": {"data": {...}, "updated_at": datetime},
            "husky": {"data": {...}, "updated_at": datetime},
            "motor": None,  # No data received yet
            "system": {
                "emergency_stop": False,
                "started_at": datetime,
                "errors": []
            }
        }
        """
        with self._lock:
            # Create deep copy to ensure complete isolation
            result = copy.deepcopy(self._state)
            return result

    def trigger_emergency_stop(self) -> None:
        """
        Set the global emergency stop flag.

        This method is idempotent - calling multiple times has same effect as once.
        Once set to True, flag persists until system restart (no reset mechanism).
        """
        with self._lock:
            self._state["system"]["emergency_stop"] = True

    def is_emergency_stopped(self) -> bool:
        """
        Check current emergency stop status.

        Returns:
            True if emergency stop has been triggered, False otherwise
        """
        with self._lock:
            return self._state["system"]["emergency_stop"]

    def add_error(self, error_message: str, device_id: Optional[str] = None) -> None:
        """
        Record a system or device error.

        Args:
            error_message: Human-readable error description
            device_id: Optional device that caused error (for context)

        Raises:
            ValueError: If error_message is empty string or None
        """
        # Input validation
        if not error_message:
            raise ValueError("error_message cannot be empty")

        with self._lock:
            error_record: ErrorRecord = {
                "timestamp": datetime.utcnow(),
                "message": error_message,
                "device_id": device_id,
            }
            self._state["system"]["errors"].append(error_record)