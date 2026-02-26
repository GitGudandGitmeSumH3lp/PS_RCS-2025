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
    YDLIDAR S2PRO / X-series reader using official YDLidar-SDK.
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
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if any(ident in port.description.lower() for ident in ['cp210', 'ch340', 'usb serial']):
                logger.info(f"Found LiDAR device: {port.device}")
                return port.device
        # Fallback
        for port in ['/dev/ttyUSB1', '/dev/ttyUSB0']:
            if self._test_port(port):
                logger.info(f"Using fallback port: {port}")
                return port
        raise Exception("No LiDAR device found")

    def _test_port(self, port: str) -> bool:
        try:
            import serial
            test = serial.Serial(port, self.baudrate, timeout=0.5)
            test.close()
            return True
        except Exception:
            return False

    def connect(self) -> bool:
        try:
            self.laser = ydlidar.CYdLidar()
            self.laser.setSerialPort(self.port)
            self.laser.setSerialBaudrate(self.baudrate)
            # Optionally set scan frequency, etc.
            # self.laser.setIntensity(True)  # if needed

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
                        'quality': int(point.intensity),
                        'timestamp': time.time(),
                        'x': x,
                        'y': y
                    })
                with self._lock:
                    self._latest_scan = points
                logger.debug(f"Scan points: {len(points)}")
            else:
                time.sleep(0.001)  # yield when no data
        logger.info("Scan loop ended")

    def get_latest_data(self, max_points: int = 360) -> List[Dict]:
        with self._lock:
            return self._latest_scan[-max_points:] if self._latest_scan else []

    def stop_scan(self):
        self._running = False
        self.is_scanning = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=3.0)
        if self.laser:
            self.laser.turnOff()
            self.laser.disconnecting()
            logger.info("YDLidar stopped")
        self.laser = None