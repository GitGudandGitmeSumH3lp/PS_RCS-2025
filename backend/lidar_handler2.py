import time
import threading
import json
import math
from typing import Dict, List, Tuple, Optional
import serial
import numpy as np
from dataclasses import dataclass

@dataclass
class LiDARPoint:
    angle: float
    distance: float
    quality: int
    timestamp: float

class LiDARHandler:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        """
        Initialize LiDAR handler for real-time scanning
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_scanning = False
        self.scan_data = {}
        self.current_scan = []
        self.scan_lock = threading.Lock()
        
        # LiDAR configuration
        self.max_distance = 8000  # 8 meters in mm
        self.min_distance = 100   # 10 cm in mm
        self.scan_frequency = 10  # Hz
        
        # Callbacks for real-time data
        self.data_callbacks = []
        
    def connect(self) -> bool:
        """
        Connect to LiDAR sensor
        """
        try:
            self.serial_conn = serial.Serial(
                self.port, 
                self.baudrate, 
                timeout=1
            )
            time.sleep(2)
            print(f"Connected to LiDAR on {self.port}")
            return True
        except Exception as e:
            print(f"Failed to connect to LiDAR: {e}")
            return False
    
    def disconnect(self):
        """
        Disconnect from LiDAR sensor
        """
        self.stop_scanning()
        if self.serial_conn:
            self.serial_conn.close()
            self.serial_conn = None
        print("LiDAR disconnected")
    
    def start_scanning(self):
        """
        Start continuous LiDAR scanning in a separate thread
        """
        if not self.serial_conn:
            print("LiDAR not connected")
            return False
            
        self.is_scanning = True
        self.scan_thread = threading.Thread(target=self._scan_loop)
        self.scan_thread.daemon = True
        self.scan_thread.start()
        print("LiDAR scanning started")
        return True
    
    def stop_scanning(self):
        """
        Stop LiDAR scanning
        """
        self.is_scanning = False
        if hasattr(self, 'scan_thread'):
            self.scan_thread.join(timeout=2)
        print("LiDAR scanning stopped")
    
    def _scan_loop(self):
        """
        Main scanning loop - runs in separate thread
        """
        while self.is_scanning:
            try:
                # Send scan command (adjust based on your LiDAR model)
                self.serial_conn.write(b'SCAN\n')
                
                # Read scan data
                scan_points = self._read_scan_data()
                
                if scan_points:
                    with self.scan_lock:
                        self.current_scan = scan_points
                        self.scan_data = self._process_scan_data(scan_points)
                    
                    # Notify callbacks
                    self._notify_callbacks(self.scan_data)
                
                time.sleep(1.0 / self.scan_frequency)
                
            except Exception as e:
                print(f"Scan error: {e}")
                time.sleep(0.1)
    
    def _read_scan_data(self) -> List[LiDARPoint]:
        """
        Read and parse raw LiDAR data
        Adjust this method based on your specific LiDAR protocol
        """
        scan_points = []
        timestamp = time.time()
        
        try:
            # This is a generic implementation
            # You'll need to adjust based on your LiDAR's data format
            
            # Simulate 360-degree scan with 1-degree resolution
            for angle in range(0, 360, 1):
                # Read data from serial (adjust protocol as needed)
                if self.serial_conn.in_waiting > 0:
                    raw_data = self.serial_conn.readline().decode().strip()
                    if raw_data:
                        try:
                            # Parse data format: "angle,distance,quality"
                            parts = raw_data.split(',')
                            if len(parts) >= 2:
                                angle_deg = float(parts[0])
                                distance_mm = float(parts[1])
                                quality = int(parts[2]) if len(parts) > 2 else 255
                                
                                if (self.min_distance <= distance_mm <= self.max_distance):
                                    point = LiDARPoint(
                                        angle=angle_deg,
                                        distance=distance_mm,
                                        quality=quality,
                                        timestamp=timestamp
                                    )
                                    scan_points.append(point)
                        except ValueError:
                            continue
                else:
                    # If no data available, simulate some data for demo
                    # Remove this in production
                    distance = 1000 + 500 * math.sin(math.radians(angle * 2))
                    point = LiDARPoint(
                        angle=float(angle),
                        distance=distance,
                        quality=255,
                        timestamp=timestamp
                    )
                    scan_points.append(point)
                    
        except Exception as e:
            print(f"Data reading error: {e}")
        
        return scan_points
    
    def _process_scan_data(self, scan_points: List[LiDARPoint]) -> Dict:
        """
        Process raw scan points into structured data for visualization
        """
        processed_data = {
            'timestamp': time.time(),
            'points': [],
            'polar_data': [],
            'cartesian_data': [],
            'obstacles': [],
            'scan_quality': 0,
            'point_count': len(scan_points)
        }
        
        if not scan_points:
            return processed_data
        
        total_quality = 0
        
        for point in scan_points:
            # Convert to cartesian coordinates
            angle_rad = math.radians(point.angle)
            x = point.distance * math.cos(angle_rad)
            y = point.distance * math.sin(angle_rad)
            
            point_data = {
                'angle': point.angle,
                'distance': point.distance,
                'quality': point.quality,
                'x': x,
                'y': y
            }
            
            processed_data['points'].append(point_data)
            processed_data['polar_data'].append([point.angle, point.distance])
            processed_data['cartesian_data'].append([x, y])
            
            total_quality += point.quality
            
            # Detect obstacles (points closer than 1 meter)
            if point.distance < 1000:
                processed_data['obstacles'].append(point_data)
        
        # Calculate average scan quality
        if scan_points:
            processed_data['scan_quality'] = total_quality / len(scan_points)
        
        return processed_data
    
    def get_latest_scan(self) -> Dict:
        """
        Get the latest scan data thread-safely
        """
        with self.scan_lock:
            return self.scan_data.copy()
    
    def register_callback(self, callback):
        """
        Register a callback function for real-time data updates
        """
        self.data_callbacks.append(callback)
    
    def _notify_callbacks(self, data):
        """
        Notify all registered callbacks with new data
        """
        for callback in self.data_callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def get_scan_statistics(self) -> Dict:
        """
        Get scanning statistics and health information
        """
        with self.scan_lock:
            if not self.scan_data:
                return {'status': 'No data available'}
            
            return {
                'status': 'Active' if self.is_scanning else 'Stopped',
                'point_count': self.scan_data.get('point_count', 0),
                'scan_quality': self.scan_data.get('scan_quality', 0),
                'obstacle_count': len(self.scan_data.get('obstacles', [])),
                'last_update': self.scan_data.get('timestamp', 0),
                'connection_status': 'Connected' if self.serial_conn else 'Disconnected'
            }
    
    def export_scan_data(self, filename: str = None) -> str:
        """
        Export current scan data to JSON file
        """
        if filename is None:
            filename = f"lidar_scan_{int(time.time())}.json"
        
        with self.scan_lock:
            with open(filename, 'w') as f:
                json.dump(self.scan_data, f, indent=2)
        
        return filename

# Example usage for testing
if __name__ == "__main__":
    lidar = LiDARHandler()
    
    def data_callback(data):
        print(f"New scan: {data['point_count']} points, Quality: {data['scan_quality']:.1f}")
    
    lidar.register_callback(data_callback)
    
    if lidar.connect():
        lidar.start_scanning()
        
        try:
            time.sleep(10)  # Scan for 10 seconds
            stats = lidar.get_scan_statistics()
            print("Statistics:", stats)
            
        except KeyboardInterrupt:
            pass
        finally:
            lidar.disconnect()