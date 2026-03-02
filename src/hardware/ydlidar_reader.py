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
    Supports USB Serial and Raspberry Pi GPIO UART.
    """
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200) -> None:
        # If port is provided, use it; otherwise, auto-detect
        self.port = port or self._find_lidar_port()
        self.baudrate = baudrate
        self.laser: Optional[ydlidar.CYdLidar] = None
        self.is_scanning = False
        self.reader_thread: Optional[threading.Thread] = None
        self._latest_scan: List[Dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()

    def _find_lidar_port(self) -> str:
        """Auto-detect LiDAR port. Checks SDK list, USB fallbacks, and GPIO UART."""
        # 1. Try SDK built-in discovery
        ports = ydlidar.lidarPortList()
        if ports:
            for key, value in ports.items():
                logger.info(f"Found LiDAR device via SDK: {value}")
                return value

        # 2. Fallback list: Includes USB and Raspberry Pi GPIO UART ports
        # /dev/serial0 is the default primary UART on Pi
        # /dev/ttyAMA0 is the hardware UART on Pi
        common_ports = [
            '/dev/ttyUSB0', 
            '/dev/ttyUSB1', 
            '/dev/serial0', 
            '/dev/ttyAMA0'
        ]
        
        for port in common_ports:
            try:
                import serial
                # Attempt to open port to see if it exists and is accessible
                test = serial.Serial(port, self.baudrate, timeout=0.1)
                test.close()
                logger.info(f"Using found serial port: {port}")
                return port
            except Exception:
                continue
                
        raise Exception("No LiDAR device found on USB or GPIO. Check permissions and 'raspi-config'.")

    def connect(self) -> bool:
        """Initialize and configure the LiDAR using setlidaropt."""
        try:
            self.laser = ydlidar.CYdLidar()
            
            # Configuration based on YDLIDAR S2/S2PRO parameters
            # See YDLIDAR SDK API documentation for reference
            self.laser.setlidaropt(ydlidar.LidarPropSerialPort, self.port)
            self.laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, self.baudrate)  # 115200 for S2
            self.laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)  # Triangle LiDAR
            self.laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
            self.laser.setlidaropt(ydlidar.LidarPropScanFrequency, 8.0)  # S2 range 4-8 Hz
            self.laser.setlidaropt(ydlidar.LidarPropSampleRate, 3)        # 3K samples/sec for S2
            self.laser.setlidaropt(ydlidar.LidarPropSingleChannel, True)  # S2 uses single channel
            self.laser.setlidaropt(ydlidar.LidarPropMaxAngle, 180.0)
            self.laser.setlidaropt(ydlidar.LidarPropMinAngle, -180.0)
            self.laser.setlidaropt(ydlidar.LidarPropMaxRange, 16.0)       # meters
            self.laser.setlidaropt(ydlidar.LidarPropMinRange, 0.08)       # meters
            self.laser.setlidaropt(ydlidar.LidarPropIntenstiy, False)     # Intensity not needed
            # Motor DTR control – disabled for GPIO UART (no DTR line)
            self.laser.setlidaropt(ydlidar.LidarPropSupportMotorDtrCtrl, False)
            # Optional: enable auto reconnect
            # self.laser.setlidaropt(ydlidar.LidarPropAutoReconnect, True, sizeof(bool))

            if not self.laser.initialize():
                # Use DescribeError to get more details
                err_msg = self.laser.DescribeError() if hasattr(self.laser, 'DescribeError') else "Unknown error"
                logger.error(f"YDLidar initialization failed on {self.port}: {err_msg}")
                return False

            if not self.laser.turnOn():
                err_msg = self.laser.DescribeError() if hasattr(self.laser, 'DescribeError') else "Unknown error"
                logger.error(f"YDLidar motor start failed: {err_msg}")
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
        self._stop_event.clear()
        self.reader_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.reader_thread.start()
        logger.info("YDLidar scanning started")
        return True

    def _scan_loop(self):
        """Background thread: continuously get scan data."""
        scan = ydlidar.LaserScan()
        while self._running and self.is_scanning and not self._stop_event.is_set():
            if self.laser and self.laser.doProcessSimple(scan):
                points = []
                for point in scan.points:
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
                logger.debug(f"Scan received: {len(points)} points")
            else:
                self._stop_event.wait(0.001)
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
        self._stop_event.set()
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