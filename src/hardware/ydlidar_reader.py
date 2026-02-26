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
    YDLIDAR X3/X4 compatible reader using official YDLidar-SDK.
    Replaces the incompatible RPLIDAR-protocol parser in lidar_reader.py.
    """
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200) -> None:
        """
        Initialize YDLIDAR reader with SDK.
        
        Args:
            port: Serial port (e.g., /dev/ttyUSB1). Auto-detect if None.
            baudrate: Serial baud rate. X3=115200, X4=128000.
        """
        self.port = port or self._find_lidar_port()
        self.baudrate = baudrate
        self.laser: Optional[ydlidar.YDLidar] = None
        self.is_scanning = False
        self.reader_thread: Optional[threading.Thread] = None
        self._latest_scan: List[Dict] = []
        self._lock = threading.Lock()
        self._running = False
        
    def _find_lidar_port(self) -> str:
        """Auto-detect LiDAR on common USB-Serial ports."""
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        # YDLIDAR typically uses CP210x or CH340 USB-Serial chips
        lidar_identifiers = ['CP210', 'CH340', 'USB Serial']
        
        for port in ports:
            desc = port.description.lower()
            for identifier in lidar_identifiers:
                if identifier.lower() in desc:
                    logger.info(f"Found potential LiDAR device: {port.device}")
                    return port.device
        
        # Fallback to common ports
        common_ports = ['/dev/ttyUSB1', '/dev/ttyUSB0', '/dev/ttyACM0']
        for port in common_ports:
            if self._test_port(port):
                logger.info(f"Using fallback port: {port}")
                return port
        
        raise Exception("No LiDAR device found. Check connections and permissions.")
    
    def _test_port(self, port: str) -> bool:
        """Test if port exists and is accessible."""
        try:
            import serial
            test = serial.Serial(port, self.baudrate, timeout=0.5)
            test.close()
            return True
        except Exception:
            return False

    def connect(self) -> bool:
        """
        Initialize YDLidar-SDK and connect to hardware.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Initialize SDK laser instance
            self.laser = ydlidar.CYdLidar()
            
            # Set properties
            self.laser.setlidaropt(ydlidar.LidarPropSerialPort, self.port)
            self.laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, self.baudrate)
            self.laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)
            self.laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
            self.laser.setlidaropt(ydlidar.LidarPropScanFrequency, 10.0)  # 10 Hz
            self.laser.setlidaropt(ydlidar.LidarPropSampleRate, 3)  # 3K samples/sec for X3
            
            # Initialize connection
            ret = self.laser.initialize()
            if ret != ydlidar.SUCCESS:
                logger.error(f"YDLidar initialization failed: {ret}")
                return False
            
            # Turn on motor
            ret = self.laser.turnOn()
            if ret != ydlidar.SUCCESS:
                logger.error(f"YDLidar motor start failed: {ret}")
                return False
            
            logger.info(f"YDLidar connected on {self.port} @ {self.baudrate}")
            return True
            
        except Exception as e:
            logger.error(f"YDLidar connect error: {e}")
            return False

    def start_scan(self) -> bool:
        """
        Start scanning in background thread.
        
        Returns:
            True if scanning started.
        """
        if not self.laser:
            if not self.connect():
                return False
        
        try:
            # Start scan process
            ret = self.laser.startScan()
            if ret != ydlidar.SUCCESS:
                logger.error(f"YDLidar start scan failed: {ret}")
                return False
            
            self.is_scanning = True
            self._running = True
            self.reader_thread = threading.Thread(target=self._scan_loop, daemon=True)
            self.reader_thread.start()
            
            logger.info("YDLidar scanning started")
            return True
            
        except Exception as e:
            logger.error(f"YDLidar start_scan error: {e}")
            return False

    def _scan_loop(self) -> None:
        """Background thread: continuously read scan data from SDK."""
        scan = ydlidar.LaserScan()
        
        while self._running and self.is_scanning:
            try:
                ret = self.laser.doProcessSimple(scan)
                if ret == ydlidar.SUCCESS:
                    points = []
                    obstacles = []
                    
                    # Convert SDK LaserScan to our point format
                    for point in scan.points:
                        # SDK provides: angle (rad), range (m), intensity
                        angle_deg = np.degrees(point.angle)
                        distance_mm = point.range * 1000.0  # Convert m to mm
                        intensity = point.intensity
                        
                        # Calculate Cartesian coordinates
                        x = distance_mm * np.cos(point.angle)
                        y = distance_mm * np.sin(point.angle)
                        
                        point_dict = {
                            'angle': angle_deg,
                            'distance': distance_mm,
                            'quality': int(intensity),
                            'timestamp': time.time(),
                            'x': x,
                            'y': y
                        }
                        points.append(point_dict)
                        
                        # Flag obstacles within 1 meter
                        if distance_mm < 1000:
                            obstacles.append(point_dict)
                    
                    # Atomic update
                    with self._lock:
                        self._latest_scan = points
                        
                    logger.debug(f"Scan received: {len(points)} points, {len(obstacles)} obstacles")
                else:
                    logger.warning(f"YDLidar scan error: {ret}")
                    
                time.sleep(0.001)  # Small yield to prevent CPU spin
                
            except Exception as e:
                logger.error(f"YDLidar scan loop error: {e}")
                time.sleep(0.1)

    def get_latest_data(self, max_points: int = 360) -> List[Dict]:
        """
        Retrieve latest scan points.
        
        Args:
            max_points: Maximum points to return (limits data size).
            
        Returns:
            List of point dictionaries.
        """
        with self._lock:
            if not self._latest_scan:
                return []
            # Return most recent points up to max_points
            return self._latest_scan[-max_points:]

    def stop_scan(self) -> None:
        """Stop scanning and disconnect."""
        self._running = False
        self.is_scanning = False
        
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=3.0)
        
        if self.laser:
            try:
                self.laser.stopScan()
                self.laser.turnOff()
                self.laser.disconnecting()
                logger.info("YDLidar stopped and disconnected")
            except Exception as e:
                logger.error(f"YDLidar stop error: {e}")
        
        self.laser = None