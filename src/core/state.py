"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/core/state.py
Description: Central definitions for robot state management.
"""

import json
import threading
import logging
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.obstacle_avoidance import BodyMaskSector, DEFAULT_BODY_MASK

logger = logging.getLogger(__name__)


@dataclass
class LidarPoint:
    """Represents a single data point from the LiDAR sensor.

    Attributes:
        angle: The angle of measurement in degrees.
        distance: The distance measured in millimeters.
        quality: Signal quality/intensity of the return.
    """
    angle: float
    distance: int
    quality: int


@dataclass
class VisionState:
    """Dataclass representing the current state of the vision system.

    Attributes:
        camera_connected: True if camera is accessible.
        camera_index: Index of the connected camera device.
        stream_active: True if video stream is running.
        last_scan: Result dictionary from the most recent OCR scan.
    """
    camera_connected: bool = False
    camera_index: Optional[int] = None
    stream_active: bool = False
    last_scan: Optional[Dict[str, Any]] = None


@dataclass
class RobotStatus:
    """Represents the operational status of the robot hardware.

    Attributes:
        mode: Current operational mode (e.g., 'idle', 'moving').
        battery_voltage: Current battery level in volts.
        last_error: Most recent error message, if any.
        motor_connected: Connection status of motor controller.
        lidar_connected: Connection status of LiDAR sensor.
        camera_connected: Connection status of camera.
        timestamp: UTC timestamp of the last status update.
    """
    mode: str
    battery_voltage: Optional[float]
    last_error: Optional[str]
    motor_connected: bool
    lidar_connected: bool
    camera_connected: bool
    timestamp: str


class RobotState:
    """Thread-safe state container for robot data.

    Manages synchronization of shared resources between hardware drivers
    and the API server. Serves as the Single Source of Truth (SSOT).

    Attributes:
        vision: Container for vision/OCR specific state.
    """

    def __init__(self) -> None:
        """Initialize the RobotState with default 'idle' values."""
        self._lock = threading.Lock()
        self._lidar_mask_lock = threading.Lock()
        self._lidar_body_mask: Optional[List[BodyMaskSector]] = None
        
        # Hardware Sensor Data
        self._lidar_data: List[LidarPoint] = []
        
        # Subsystem States
        self.vision = VisionState()
        
        # General Status
        self._status = RobotStatus(
            mode="idle",
            battery_voltage=None,
            last_error=None,
            motor_connected=False,
            lidar_connected=False,
            camera_connected=False,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    def update_lidar_data(self, points: List[LidarPoint]) -> None:
        """Updates the current LiDAR scan data safely.

        Args:
            points: A list of LidarPoint objects representing a full scan.

        Raises:
            TypeError: If input is not a list or contains invalid objects.
        """
        if not isinstance(points, list):
            raise TypeError("points must be a list")

        for point in points:
            if not isinstance(point, LidarPoint):
                raise TypeError("All elements must be LidarPoint instances")

        with self._lock:
            self._lidar_data = points

    def update_status(
        self,
        mode: Optional[str] = None,
        battery_voltage: Optional[float] = None,
        last_error: Optional[str] = None,
        motor_connected: Optional[bool] = None,
        lidar_connected: Optional[bool] = None,
        camera_connected: Optional[bool] = None
    ) -> None:
        """Updates specific fields of the robot status.

        Only fields provided as arguments are updated; others remain unchanged.
        Automatically updates the timestamp.

        Args:
            mode: New operational mode (idle, moving, scanning, error).
            battery_voltage: New battery voltage.
            last_error: Error message string.
            motor_connected: Motor connection boolean.
            lidar_connected: LiDAR connection boolean.
            camera_connected: Camera connection boolean.

        Raises:
            ValueError: If mode is invalid or battery_voltage is negative.
        """
        if mode is not None and mode not in {"idle", "moving", "scanning", "error"}:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of: idle, moving, scanning, error")

        if battery_voltage is not None and battery_voltage < 0:
            raise ValueError("Battery voltage cannot be negative")

        with self._lock:
            if mode is not None:
                self._status.mode = mode
            if battery_voltage is not None:
                self._status.battery_voltage = battery_voltage
            if last_error is not None:
                self._status.last_error = last_error
            if motor_connected is not None:
                self._status.motor_connected = motor_connected
            if lidar_connected is not None:
                self._status.lidar_connected = lidar_connected
            if camera_connected is not None:
                self._status.camera_connected = camera_connected

            self._status.timestamp = datetime.utcnow().isoformat() + "Z"

    def update_vision_status(self, connected: bool, index: Optional[int] = None) -> None:
        """Update connectivity status of the vision system.

        Args:
            connected: Connection status.
            index: Camera device index.
        """
        with self._lock:
            self.vision.camera_connected = connected
            self.vision.camera_index = index
            self.vision.stream_active = connected
            # Sync with main status for backward compatibility
            self._status.camera_connected = connected
            self._status.timestamp = datetime.utcnow().isoformat() + "Z"

    def update_scan_result(self, result: Dict[str, Any]) -> None:
        """Update the last known scan result.

        Args:
            result: Dictionary containing scan data.
        """
        with self._lock:
            self.vision.last_scan = result

    def get_lidar_snapshot(self) -> List[Dict[str, Any]]:
        """Returns a thread-safe copy of the current LiDAR data.

        Returns:
            A list of dictionaries representing LidarPoints.
        """
        with self._lock:
            data_copy = deepcopy(self._lidar_data)

        return [asdict(point) for point in data_copy]

    def get_status_snapshot(self) -> Dict[str, Any]:
        """Returns a thread-safe copy of the current robot status.

        Returns:
            A dictionary representation of the RobotStatus.
        """
        with self._lock:
            status_copy = deepcopy(self._status)

        return asdict(status_copy)

    def set_error(self, error_message: str) -> None:
        """Sets the system state to 'error' and records the message.

        Args:
            error_message: Description of the error.
        """
        with self._lock:
            self._status.last_error = error_message
            self._status.mode = "error"
            self._status.timestamp = datetime.utcnow().isoformat() + "Z"

    def clear_error(self) -> None:
        """Clears the error state and resets mode to 'idle'."""
        with self._lock:
            self._status.last_error = None
            self._status.mode = "idle"
            self._status.timestamp = datetime.utcnow().isoformat() + "Z"

    @property
    def lidar_body_mask(self) -> List[BodyMaskSector]:
        """Return the current body mask configuration.

        Returns:
            List of BodyMaskSector dicts. Returns DEFAULT_BODY_MASK if not yet set.
        """
        with self._lidar_mask_lock:
            if self._lidar_body_mask is None:
                self._lidar_body_mask = self._load_body_mask()
            return self._lidar_body_mask

    @lidar_body_mask.setter
    def lidar_body_mask(self, mask: List[BodyMaskSector]) -> None:
        """Set and persist a new body mask configuration.

        Args:
            mask: Validated list of BodyMaskSector dicts. Caller is responsible
                  for pre-validating before assignment.

        Side Effects:
            Persists the new mask to config file.
        """
        with self._lidar_mask_lock:
            self._lidar_body_mask = mask
            self._persist_body_mask()

    def _load_body_mask(self) -> List[BodyMaskSector]:
        """Load body mask from config file.

        Returns:
            List of BodyMaskSector dicts. Returns DEFAULT_BODY_MASK if file missing or malformed.
        """
        config_path = Path(__file__).resolve().parent.parent.parent / "config" / "body_mask.json"
        if not config_path.exists():
            logger.info("No body mask config file found, using default mask")
            return DEFAULT_BODY_MASK

        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            mask = data.get('mask', [])
            # Basic validation (full validation is done on POST)
            if isinstance(mask, list):
                return mask
            else:
                logger.warning("body_mask.json has invalid format, using default mask")
                return DEFAULT_BODY_MASK
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load body mask config: {e}")
            return DEFAULT_BODY_MASK

    def _persist_body_mask(self) -> None:
        """Write current body mask to the config file.

        File: config/body_mask.json (relative to project root).
        Format: {"mask": [<BodyMaskSector>, ...]}
        Side Effects: Creates file and parent directories if they do not exist.
        Errors: Logs ERROR and does NOT raise.
        """
        config_path = Path(__file__).resolve().parent.parent.parent / "config" / "body_mask.json"
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump({"mask": self._lidar_body_mask}, f, indent=2)
            logger.info("Body mask persisted to %s", config_path)
        except Exception as e:
            logger.error(f"Failed to persist body mask: {e}")