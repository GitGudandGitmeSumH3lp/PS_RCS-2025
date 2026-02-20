# src/hardware/lidar_reader.py

import serial
import serial.tools.list_ports
import threading
import time
import logging
from queue import Queue, Empty
from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class LiDARPoint:
    """Represents a single LiDAR scan point."""
    angle: float
    distance: float
    quality: int
    timestamp: float


class LiDARReader:
    """Generic LiDAR sensor reader supporting multiple protocols."""

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200) -> None:
        """
        Initialize LiDAR reader.

        Args:
            port: Serial port device path. If None, auto-detect.
            baudrate: Serial baud rate.
        """
        self.port = port or self._find_lidar_port()
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.is_scanning = False
        self.data_queue: Queue = Queue(maxsize=1000)
        self.reader_thread: Optional[threading.Thread] = None
        self._buffer = bytearray()  # efficient byte buffer

    def _find_lidar_port(self) -> str:
        """Auto-detect LiDAR sensor port based on common identifiers."""
        ports = serial.tools.list_ports.comports()
        lidar_identifiers = ['CP210', 'CH340', 'FT232', 'Arduino', 'LiDAR', 'SLAMTEC']
        for port in ports:
            for identifier in lidar_identifiers:
                if identifier.lower() in port.description.lower():
                    logger.info(f"Found potential LiDAR device: {port.device}")
                    return port.device
        common_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0']
        for port in common_ports:
            try:
                test_conn = serial.Serial(port, self.baudrate, timeout=1)
                test_conn.close()
                logger.info(f"Using fallback port: {port}")
                return port
            except Exception:
                continue
        raise Exception("No LiDAR device found. Please check connections.")

    def connect(self) -> bool:
        """
        Establish serial connection to LiDAR.

        Returns:
            True if successful, False otherwise.
        """
        try:
            self.serial_conn = serial.Serial(
                self.port,
                self.baudrate,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            logger.info(f"Connected to LiDAR on {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to LiDAR: {e}")
            return False

    def start_scan(self) -> bool:
        """
        Start LiDAR scanning in a background thread.

        Returns:
            True if scanning started or already running.
        """
        if not self.serial_conn:
            if not self.connect():
                return False
        try:
            self.serial_conn.write(b'\xA5\x20\x00\x00\x00\x00\x02\x00\x00\x00\x22')
            self.is_scanning = True
            self.reader_thread = threading.Thread(target=self._read_data, daemon=True)
            self.reader_thread.start()
            logger.info("LiDAR scanning started")
            return True
        except Exception as e:
            logger.error(f"Failed to start scanning: {e}")
            return False

    def _read_data(self) -> None:
        """Background thread: read and parse LiDAR data continuously."""
        while self.is_scanning and self.serial_conn:
            try:
                # Read all available bytes
                if self.serial_conn.in_waiting:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    self._buffer.extend(data)

                # Process complete packets using sliding window with sync detection
                while len(self._buffer) >= 5:
                    # Look for a plausible packet header (e.g., quality byte with reasonable value)
                    # Here we simply try to parse the first 5 bytes; if the parsed distance is within
                    # valid range, accept it; otherwise drop one byte and retry.
                    candidate = self._buffer[:5]
                    point = self._parse_data_packet(candidate)
                    if point:
                        try:
                            self.data_queue.put_nowait(point)
                        except Exception:
                            # Queue full: drop oldest and retry
                            try:
                                self.data_queue.get_nowait()
                                self.data_queue.put_nowait(point)
                            except Exception:
                                pass
                        self._buffer = self._buffer[5:]  # consume 5 bytes
                    else:
                        # Not a valid packet, shift by one byte
                        self._buffer = self._buffer[1:]

                # Small sleep to prevent CPU overload when no data
                time.sleep(0.001)

            except Exception as e:
                logger.error(f"Error reading LiDAR data: {e}")
                time.sleep(0.1)

    def _parse_data_packet(self, packet: bytes) -> Optional[LiDARPoint]:
        """
        Parse a 5-byte LiDAR packet.

        Args:
            packet: 5-byte raw data.

        Returns:
            LiDARPoint if valid, else None.
        """
        try:
            if len(packet) < 5:
                return None
            angle = (packet[1] | (packet[2] << 8)) / 64.0
            distance = (packet[3] | (packet[4] << 8)) / 4.0
            quality = packet[0]

            # Basic sanity checks
            if 0 <= angle < 360 and 0 < distance < 12000 and 0 <= quality <= 255:
                return LiDARPoint(
                    angle=angle % 360,
                    distance=distance,
                    quality=quality,
                    timestamp=time.time()
                )
        except Exception as e:
            logger.debug(f"Error parsing packet: {e}")
        return None

    def get_latest_data(self, max_points: int = 360) -> List[Dict]:
        """
        Retrieve up to max_points from the internal queue.

        Args:
            max_points: Maximum number of points to return.

        Returns:
            List of point dictionaries with keys: angle, distance, quality, timestamp, x, y.
        """
        points = []
        try:
            while len(points) < max_points:
                try:
                    point = self.data_queue.get_nowait()
                    points.append({
                        'angle': point.angle,
                        'distance': point.distance,
                        'quality': point.quality,
                        'timestamp': point.timestamp,
                        'x': point.distance * np.cos(np.radians(point.angle)),
                        'y': point.distance * np.sin(np.radians(point.angle))
                    })
                except Empty:
                    break
        except Exception as e:
            logger.error(f"Error getting latest data: {e}")
        return points

    def stop_scan(self) -> None:
        """Stop LiDAR scanning and close serial connection."""
        self.is_scanning = False
        if self.serial_conn:
            try:
                self.serial_conn.write(b'\xA5\x25\x00\x00\x00\x00\x02\x00\x00\x00\x27')
                self.serial_conn.close()
                logger.info("LiDAR scanning stopped")
            except Exception as e:
                logger.error(f"Error stopping scan: {e}")