# src/hardware/ydlidar_reader.py

import ydlidar
import threading
import time
import logging
from typing import List, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class YDLidarReader:
    """
    YDLIDAR reader using official SDK with setlidaropt configuration.
    """
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200) -> None:
        self.port = port or self._find_lidar_port()
        self.baudrate = baudrate
        self.laser: Optional[ydlidar.CYdLidar] = None
        self.is_scanning = False
        self.reader_thread: Optional[threading.Thread] = None
        self._latest_scan: List[Dict] = []
        self._lock = threading.Lock()
        self._running = False

    def _find_lidar_port(self) -> str:
        """Auto-detect LiDAR port using ydlidar's port list."""
        ports = ydlidar.lidarPortList()
        if ports:
            # Take the first port found
            for key, value in ports.items():
                logger.info(f"Found LiDAR device: {value}")
                return value
        # Fallback to common ports
        common_ports = ['/dev/ttyUSB1', '/dev/ttyUSB0']
        for port in common_ports:
            try:
                import serial
                test = serial.Serial(port, self.baudrate, timeout=0.5)
                test.close()
                logger.info(f"Using fallback port: {port}")
                return port
            except Exception:
                continue
        raise Exception("No LiDAR device found. Check connections and permissions.")

    def connect(self) -> bool:
        """Initialize and configure the LiDAR using setlidaropt."""
        try:
            self.laser = ydlidar.CYdLidar()
            
            # Set all necessary options (mirroring tri_test.py)
            self.laser.setlidaropt(ydlidar.LidarPropSerialPort, self.port)
            self.laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, self.baudrate)
            self.laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)
            self.laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
            self.laser.setlidaropt(ydlidar.LidarPropScanFrequency, 10.0)   # 10 Hz
            self.laser.setlidaropt(ydlidar.LidarPropSampleRate, 3)          # 3K samples/sec
            self.laser.setlidaropt(ydlidar.LidarPropSingleChannel, True)    # Single channel
            self.laser.setlidaropt(ydlidar.LidarPropMaxAngle, 180.0)        # degrees
            self.laser.setlidaropt(ydlidar.LidarPropMinAngle, -180.0)       # degrees
            self.laser.setlidaropt(ydlidar.LidarPropMaxRange, 16.0)         # meters
            self.laser.setlidaropt(ydlidar.LidarPropMinRange, 0.08)         # meters
            self.laser.setlidaropt(ydlidar.LidarPropIntenstiy, False)       # intensity not needed

            # Initialize and turn on
            if not self.laser.initialize():
                logger.error("YDLidar initialization failed")
                return False

            if not self.laser.turnOn():
                logger.error("YDLidar motor start failed")
                return False

            logger.info(f"YDLidar connected on {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            logger.error(f"YDLidar connect error: {e}")
            return False

    def start_scan(self) -> bool:
        """Start scanning in background thread."""
        if not self.laser:
            if not self.connect():
                return False

        self.is_scanning = True
        self._running = True
        self.reader_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.reader_thread.start()
        logger.info("YDLidar scanning started")
        return True

    def _scan_loop(self):
        """Background thread: continuously get scan data."""
        scan = ydlidar.LaserScan()
        while self._running and self.is_scanning:
            if self.laser and self.laser.doProcessSimple(scan):
                points = []
                for point in scan.points:
                    # point has attributes: angle (rad), range (m), intensity
                    angle_deg = np.degrees(point.angle)
                    distance_mm = point.range * 1000.0
                    x = distance_mm * np.cos(point.angle)
                    y = distance_mm * np.sin(point.angle)
                    points.append({
                        'angle': angle_deg,
                        'distance': distance_mm,
                        'quality': int(point.intensity),  # intensity as quality
                        'timestamp': time.time(),
                        'x': x,
                        'y': y
                    })
                with self._lock:
                    self._latest_scan = points
                logger.debug(f"Scan received: {len(points)} points")
            else:
                # Small sleep to avoid CPU spin when no data
                time.sleep(0.001)
        logger.info("Scan loop ended")

    def get_latest_data(self, max_points: int = 360) -> List[Dict]:
        """Return the most recent scan points."""
        with self._lock:
            if not self._latest_scan:
                return []
            return self._latest_scan[-max_points:]

    def stop_scan(self):
        """Stop scanning and shut down LiDAR."""
        self._running = False
        self.is_scanning = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=3.0)
        if self.laser:
            try:
                self.laser.turnOff()
                self.laser.disconnecting()
                logger.info("YDLidar stopped")
            except Exception as e:
                logger.error(f"Error stopping LiDAR: {e}")
        self.laser = None