#!/usr/bin/env python3
"""
LiDAR Web Visualization Server
Real-time LiDAR data streaming and visualization for Raspberry Pi 4B
"""

import asyncio
import json
import logging
import time
from typing import List, Dict, Optional
import serial
import serial.tools.list_ports
import threading
from dataclasses import dataclass
from queue import Queue, Empty

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LiDARPoint:
    angle: float
    distance: float
    quality: int
    timestamp: float

class LiDARReader:
    """Generic LiDAR sensor reader supporting multiple protocols"""
    
    def __init__(self, port: str = None, baudrate: int = 115200):
        self.port = port or self.find_lidar_port()
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_scanning = False
        self.data_queue = Queue(maxsize=1000)
        self.reader_thread = None
        
    def find_lidar_port(self) -> str:
        """Auto-detect LiDAR sensor port"""
        ports = serial.tools.list_ports.comports()
        
        # Common LiDAR device identifiers
        lidar_identifiers = [
            'CP210', 'CH340', 'FT232', 'Arduino', 'LiDAR', 'SLAMTEC'
        ]
        
        for port in ports:
            for identifier in lidar_identifiers:
                if identifier.lower() in port.description.lower():
                    logger.info(f"Found potential LiDAR device: {port.device}")
                    return port.device
        
        # Fallback to common ports
        common_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0']
        for port in common_ports:
            try:
                test_conn = serial.Serial(port, self.baudrate, timeout=1)
                test_conn.close()
                logger.info(f"Using fallback port: {port}")
                return port
            except:
                continue
                
        raise Exception("No LiDAR device found. Please check connections.")
    
    def connect(self):
        """Establish serial connection to LiDAR"""
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
    
    def start_scan(self):
        """Start LiDAR scanning"""
        if not self.serial_conn:
            if not self.connect():
                return False
        
        try:
            # Send scan command (adjust based on your LiDAR protocol)
            # This is a generic approach - modify based on your specific LiDAR
            self.serial_conn.write(b'\xA5\x20\x00\x00\x00\x00\x02\x00\x00\x00\x22')  # Example command
            self.is_scanning = True
            
            # Start reading thread
            self.reader_thread = threading.Thread(target=self._read_data, daemon=True)
            self.reader_thread.start()
            
            logger.info("LiDAR scanning started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start scanning: {e}")
            return False
    
    def _read_data(self):
        """Read data from LiDAR sensor"""
        buffer = b''
        
        while self.is_scanning and self.serial_conn:
            try:
                # Read available data
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    buffer += data
                    
                    # Process buffer for complete packets
                    while len(buffer) >= 5:  # Minimum packet size
                        point = self._parse_data_packet(buffer)
                        if point:
                            try:
                                self.data_queue.put_nowait(point)
                            except:
                                # Queue is full, remove oldest item
                                try:
                                    self.data_queue.get_nowait()
                                    self.data_queue.put_nowait(point)
                                except:
                                    pass
                            buffer = buffer[5:]  # Move to next packet
                        else:
                            buffer = buffer[1:]  # Skip invalid byte
                
                time.sleep(0.001)  # Small delay to prevent CPU overload
                
            except Exception as e:
                logger.error(f"Error reading LiDAR data: {e}")
                time.sleep(0.1)
    
    def _parse_data_packet(self, buffer: bytes) -> Optional[LiDARPoint]:
        """Parse LiDAR data packet - customize based on your LiDAR protocol"""
        try:
            # Generic parsing - modify based on your specific LiDAR format
            if len(buffer) < 5:
                return None
            
            # Example parsing for common LiDAR format
            # Adjust these calculations based on your LiDAR's data format
            angle = (buffer[1] | (buffer[2] << 8)) / 64.0  # Convert to degrees
            distance = (buffer[3] | (buffer[4] << 8)) / 4.0  # Convert to mm
            quality = buffer[0]
            
            # Filter invalid readings
            if distance > 0 and distance < 12000:  # Reasonable range limits
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
        """Get latest LiDAR points"""
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
    
    def stop_scan(self):
        """Stop LiDAR scanning"""
        self.is_scanning = False
        if self.serial_conn:
            try:
                # Send stop command (adjust based on your LiDAR)
                self.serial_conn.write(b'\xA5\x25\x00\x00\x00\x00\x02\x00\x00\x00\x27')
                self.serial_conn.close()
                logger.info("LiDAR scanning stopped")
            except Exception as e:
                logger.error(f"Error stopping scan: {e}")

# Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lidar_viz_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global LiDAR reader instance
lidar_reader = None

@app.route('/')
def index():
    """Main visualization page"""
    return render_template('lidar_viz.html')

@app.route('/api/status')
def get_status():
    """Get LiDAR system status"""
    global lidar_reader
    
    status = {
        'connected': lidar_reader is not None and lidar_reader.serial_conn is not None,
        'scanning': lidar_reader is not None and lidar_reader.is_scanning,
        'port': lidar_reader.port if lidar_reader else None,
        'queue_size': lidar_reader.data_queue.qsize() if lidar_reader else 0
    }
    
    return jsonify(status)

@app.route('/api/start')
def start_scanning():
    """Start LiDAR scanning"""
    global lidar_reader
    
    try:
        if not lidar_reader:
            lidar_reader = LiDARReader()
        
        if lidar_reader.start_scan():
            return jsonify({'success': True, 'message': 'Scanning started'})
        else:
            return jsonify({'success': False, 'message': 'Failed to start scanning'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/stop')
def stop_scanning():
    """Stop LiDAR scanning"""
    global lidar_reader
    
    try:
        if lidar_reader:
            lidar_reader.stop_scan()
        return jsonify({'success': True, 'message': 'Scanning stopped'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('Client connected')
    emit('status', {'message': 'Connected to LiDAR server'})

@socketio.on('request_data')
def handle_data_request():
    """Handle data request from client"""
    global lidar_reader
    
    if lidar_reader and lidar_reader.is_scanning:
        data = lidar_reader.get_latest_data(max_points=360)
        emit('lidar_data', {'points': data, 'timestamp': time.time()})

def data_streaming_task():
    """Background task to stream LiDAR data"""
    global lidar_reader
    
    while True:
        try:
            if lidar_reader and lidar_reader.is_scanning:
                data = lidar_reader.get_latest_data(max_points=100)
                if data:
                    socketio.emit('lidar_data', {
                        'points': data, 
                        'timestamp': time.time()
                    })
            
            time.sleep(0.05)  # 20 FPS update rate
            
        except Exception as e:
            logger.error(f"Error in data streaming: {e}")
            time.sleep(1)

if __name__ == '__main__':
    # Start background data streaming
    streaming_thread = threading.Thread(target=data_streaming_task, daemon=True)
    streaming_thread.start()
    
    # Start Flask-SocketIO server
    logger.info("Starting LiDAR Web Server...")
    logger.info("Access the visualization at: http://localhost:5000")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)