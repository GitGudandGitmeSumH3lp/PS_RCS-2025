"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/lidar_adapter.py
Description: Hardware-compliant adapter for YDLiDAR sensor with SDK integration.
"""
import threading
import time
import logging
from typing import Dict, Any, Optional, List, Callable

try:
    from .ydlidar_reader import YDLidarReader
except ImportError:
    YDLidarReader = None
    logging.warning("YDLidarReader not available. LiDAR will be disabled.")

logger = logging.getLogger(__name__)


class LiDARAdapter:
    """HardwareManager-compliant adapter for LiDAR sensor."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize LiDARAdapter with optional configuration.

        Args:
            config: Optional dict with keys:
                - port (str): Serial port override. Default: auto-detect.
                - baudrate (int): Serial baud rate. Default: 115200.
                - max_queue_size (int): Internal point queue size. Default: 1000.
                - enable_simulation (bool): Use simulated data if True. Default: False.

        Raises:
            ValueError: If any config value has an invalid type or out-of-range value.
        """
        self._lock = threading.Lock()
        self._reader: Optional[YDLidarReader] = None
        self._connected = False
        self._scanning = False
        self._port: Optional[str] = None
        self._baudrate = 115200
        self._max_queue_size = 1000
        self._enable_simulation = False
        self._last_error: Optional[str] = None
        self._connect_time: Optional[float] = None
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None

        if config is not None:
            for key, value in config.items():
                if key == "port":
                    if value is not None and not isinstance(value, str):
                        raise ValueError(
                            f"LiDARAdapter config key 'port' expects str, got {type(value).__name__}"
                        )
                    self._port = value
                elif key == "baudrate":
                    if not isinstance(value, int) or value <= 0:
                        raise ValueError(
                            f"LiDARAdapter config key 'baudrate' expects positive int, got {type(value).__name__}"
                        )
                    self._baudrate = value
                elif key == "max_queue_size":
                    if not isinstance(value, int) or value <= 0:
                        raise ValueError(
                            f"LiDARAdapter config key 'max_queue_size' expects positive int, got {type(value).__name__}"
                        )
                    self._max_queue_size = value
                elif key == "enable_simulation":
                    if not isinstance(value, bool):
                        raise ValueError(
                            f"LiDARAdapter config key 'enable_simulation' expects bool, got {type(value).__name__}"
                        )
                    self._enable_simulation = value
                else:
                    logger.warning(f"Unknown config key '{key}' ignored.")

    def connect(self) -> bool:
        """
        Establish serial connection to LiDAR hardware.

        Returns:
            bool: True if connection succeeded or was already connected. False on failure.
        """
        with self._lock:
            if self._connected:
                logger.debug("LiDARAdapter.connect() called while already connected.")
                return True
            try:
                if YDLidarReader is None:
                    self._last_error = "YDLidarReader not available (SDK not installed)"
                    return False
                self._reader = YDLidarReader(port=self._port, baudrate=self._baudrate)
                if not self._reader.connect():
                    self._last_error = "LiDARReader.connect() failed"
                    return False
                self._connected = True
                self._connect_time = time.monotonic()
                return True
            except Exception as e:
                logger.error(f"LiDARAdapter.connect error: {e}")
                self._last_error = str(e)
                return False

    def disconnect(self) -> bool:
        """
        Disconnect from LiDAR hardware and release serial port.

        Returns:
            bool: True if disconnected successfully or was already disconnected.
        """
        with self._lock:
            try:
                if self._scanning:
                    self.stop_scanning()
                if self._reader:
                    self._reader.stop_scan()
                self._connected = False
                self._connect_time = None
                return True
            except Exception as e:
                logger.error(f"LiDARAdapter.disconnect error: {e}")
                self._last_error = str(e)
                return False

    def start_scanning(self) -> bool:
        """
        Begin continuous LiDAR scanning in a background thread.

        Returns:
            bool: True if scanning started or was already active. False on failure.
        """
        with self._lock:
            if not self._connected:
                if not self.connect():
                    logger.error("Cannot start scanning - connection failed.")
                    return False
            if self._scanning:
                return True
            try:
                if not self._reader.start_scan():
                    self._last_error = "LiDARReader.start_scan() failed"
                    return False
                self._scanning = True
                return True
            except Exception as e:
                logger.error(f"LiDARAdapter.start_scanning error: {e}")
                self._last_error = str(e)
                return False

    def stop_scanning(self) -> bool:
        """
        Stop LiDAR scanning and join background reader thread.

        Returns:
            bool: True if stopped successfully or was already stopped.
        """
        with self._lock:
            if not self._scanning:
                return True
            try:
                self._reader.is_scanning = False
                if self._reader.reader_thread and self._reader.reader_thread.is_alive():
                    self._reader.reader_thread.join(timeout=3)
                    if self._reader.reader_thread.is_alive():
                        logger.warning("LiDAR reader thread did not stop cleanly within 3s.")
                self._scanning = False
                return True
            except Exception as e:
                logger.error(f"LiDARAdapter.stop_scanning error: {e}")
                self._last_error = str(e)
                return False

    def get_latest_scan(self) -> Dict[str, Any]:
        """
        Retrieve the most recent scan data in frontend-compatible format.

        Returns:
            dict: {
                'points': List[Dict],
                'timestamp': float,
                'point_count': int,
                'obstacles': List[Dict]
            }
        """
        with self._lock:
            try:
                points_data = []
                obstacles = []
                if self._reader and self._scanning:
                    raw_points = self._reader.get_latest_data(max_points=360)
                    for p in raw_points:
                        point_dict = {
                            'angle': p['angle'],
                            'distance': p['distance'],
                            'quality': p['quality'],
                            'x': p['x'],
                            'y': p['y']
                        }
                        points_data.append(point_dict)
                        if p['distance'] < 1000:
                            obstacles.append(point_dict)
                return {
                    'points': points_data,
                    'timestamp': time.time(),
                    'point_count': len(points_data),
                    'obstacles': obstacles
                }
            except Exception as e:
                logger.error(f"LiDARAdapter.get_latest_scan error: {e}")
                return {'points': [], 'timestamp': time.time(), 'point_count': 0, 'obstacles': []}

    def get_status(self) -> Dict[str, Any]:
        """
        Return current adapter status.

        Returns:
            dict: {
                'connected': bool,
                'scanning': bool,
                'port': Optional[str],
                'error': Optional[str],
                'uptime': float
            }
        """
        with self._lock:
            try:
                uptime = time.monotonic() - self._connect_time if self._connected and self._connect_time else 0.0
                return {
                    'connected': self._connected,
                    'scanning': self._scanning,
                    'port': self._port,
                    'error': self._last_error,
                    'uptime': uptime
                }
            except Exception as e:
                return {'connected': False, 'scanning': False, 'port': None, 'error': str(e), 'uptime': 0.0}

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a callback to receive real-time scan data.

        Args:
            callback: Callable accepting one argument: the scan dict from get_latest_scan().

        Raises:
            TypeError: If callback is not callable.
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback).__name__}")
        with self._lock:
            self._callback = callback