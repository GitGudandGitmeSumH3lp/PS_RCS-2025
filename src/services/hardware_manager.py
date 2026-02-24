# MERGED FILE: src/services/hardware_manager.py
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: hardware_manager.py
Description: Coordinates interactions with robot hardware including motor controllers and LiDAR sensors.
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import Settings
from src.core.state import LidarPoint, RobotState
from src.hardware.motor_controller import MotorController
# NEW: Import the LiDAR Adapter
try:
    from src.hardware.lidar_adapter import LiDARAdapter
except ImportError:
    LiDARAdapter = None

try:
    from lidar_handler import LidarHandler
    LEGACY_LIDAR_AVAILABLE = True
except ImportError:
    LEGACY_LIDAR_AVAILABLE = False


class MockMotorController:
    def __init__(self) -> None:
        self.connected = True

    def connect(self, port: str, baud: int) -> bool:
        logging.info(f"[MOCK] Motor connected to {port} @ {baud}")
        return True

    def send_command(self, command: str, speed: int) -> None:
        logging.info(f"[MOCK] Motor command: {command} @ speed {speed}")

    def stop(self) -> None:
        logging.info("[MOCK] Motor stopped")

    def disconnect(self) -> None:
        logging.info("[MOCK] Motor disconnected")


class MockLidarHandler:
    def __init__(self) -> None:
        self.connected = True
        self.scanning = False

    def connect(self, port: str = None, baud: int = 115200) -> bool:
        logging.info(f"[MOCK] LiDAR connected to {port} @ {baud}")
        return True

    def start_scanning(self) -> bool:
        self.scanning = True
        logging.info("[MOCK] LiDAR scanning started")
        return True

    def stop_scanning(self) -> bool:
        self.scanning = False
        logging.info("[MOCK] LiDAR scanning stopped")
        return True

    def get_latest_scan(self) -> Dict[str, Any]:
        # Return format matching LiDARAdapter: dict with 'points' key
        return {
            "points": [{"angle": i * 1.5, "distance": 1000 + i * 10, "quality": 50} for i in range(240)],
            "timestamp": time.time()
        }
    
    # Keep legacy method for compatibility if needed during transition
    def get_scan(self) -> List[Tuple[float, float, int]]:
        return [(i * 1.5, 1000 + i * 10, 50) for i in range(240)]

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "scanning": self.scanning,
            "rpm": 0.0
        }

    def disconnect(self) -> None:
        self.connected = False
        logging.info("[MOCK] LiDAR disconnected")


class HardwareManager:
    def __init__(
        self,
        settings: Settings,
        state: RobotState,
        motor_controller_class: Optional[Any] = None,
        lidar_handler_class: Optional[Any] = None
    ) -> None:
        self.settings = settings
        self.state = state
        self._running = True

        self.motor_controller_class = motor_controller_class
        self.lidar_handler_class = lidar_handler_class

        # Instantiate motor controller (singleton or mock based on mode)
        if motor_controller_class is not None:
            motor_class = motor_controller_class
        elif settings.SIMULATION_MODE:
            motor_class = MockMotorController
        else:
            motor_class = MotorController
        self.motor_controller = motor_class()

        # NEW: Initialize LiDAR Adapter
        # If simulation, use Mock; otherwise use LiDARAdapter if available
        if settings.SIMULATION_MODE:
            self.lidar = MockLidarHandler()
        else:
            if LiDARAdapter:
                self.lidar = LiDARAdapter(config={
                    "port": settings.LIDAR_PORT,  # Set from env/settings
                    "baudrate": settings.LIDAR_BAUD_RATE,
                    "max_queue_size": 1000,
                    "enable_simulation": False
                })
            else:
                self.lidar = None
                logging.warning("LiDARAdapter not found. LiDAR disabled.")

        self.lidar_thread: Optional[threading.Thread] = None
        
        self._connected = False
        self._lock = threading.Lock()
        self._logger = logging.getLogger(__name__)

        # Attempt motor connection at startup (if real hardware)
        self._connect_motor()

    def _connect_motor(self) -> None:
        """Attempt motor controller connection on startup. Non-fatal on failure."""
        try:
            if self.motor_controller.connect(self.settings.MOTOR_PORT, self.settings.MOTOR_BAUD_RATE):
                self.state.update_status(motor_connected=True)
                logging.info("Motor controller connected.")
            else:
                self.state.update_status(motor_connected=False)
                logging.warning("Motor controller connection failed. Running in degraded mode.")
        except Exception as e:
            logging.error(f"Motor init error: {e}")
            self.state.update_status(motor_connected=False)

    def start_all_drivers(self) -> Dict[str, str]:
        if self.lidar_thread and self.lidar_thread.is_alive():
            self.shutdown()

        self._running = True

        status = {
            "motor": "disconnected",
            "lidar": "disconnected",
            "camera": "disabled"
        }

        if self.settings.SIMULATION_MODE:
            self._logger.info("Starting in SIMULATION MODE")
            
            # Motor connect (idempotent)
            self.motor_controller.connect("MOCK_PORT", 9600)
            
            # LiDAR connect
            if self.lidar:
                self.lidar.connect("MOCK_PORT", 115200)
                self.lidar.start_scanning()

            status["motor"] = "simulated"
            status["lidar"] = "simulated"
            self.state.update_status(motor_connected=True, lidar_connected=True)

        else:
            self._logger.info("Starting in REAL HARDWARE MODE")

            # Motor status check – use robot state
            if getattr(self.state, 'motor_connected', False):
                status["motor"] = "connected"
            else:
                status["motor"] = "disconnected"

            # LiDAR setup
            if self.lidar:
                try:
                    # LiDARAdapter handles connection internally or via explicit connect
                    # Assuming connect() takes no args or uses config, but keeping signature safe
                    try:
                        connected = self.lidar.connect() 
                    except TypeError:
                        # Fallback if signature differs or it was auto-connected
                        connected = self.lidar.get_status().get('connected', False)

                    if connected:
                        status["lidar"] = "connected"
                        self.state.update_status(lidar_connected=True)
                        self._logger.info("LiDAR connected successfully")
                        
                        # Start scanning
                        if self.lidar.start_scanning():
                            self._logger.info("LiDAR scanning started")
                            
                            # Start data collection thread
                            self.lidar_thread = threading.Thread(
                                target=self._lidar_scan_loop,
                                daemon=True
                            )
                            self.lidar_thread.start()
                        else:
                            self._logger.error("Failed to start LiDAR scanning")
                            status["lidar"] = "failed"
                    else:
                        status["lidar"] = "failed"
                        self.state.update_status(lidar_connected=False)
                        self._logger.error("LiDAR connection failed")
                except Exception as e:
                    self._logger.error(f"LiDAR connection error: {e}")
                    status["lidar"] = "error"
                    self.state.update_status(lidar_connected=False)
            else:
                status["lidar"] = "unavailable"
                self.state.update_status(lidar_connected=False)

        self.state.update_status(camera_connected=False)
        return status

    def get_status(self) -> dict:
        return self.state.get_status_snapshot()

    def _lidar_scan_loop(self) -> None:
        """Background loop to fetch data from LiDAR adapter and update state."""
        self._logger.info(f"Updated state with {len(lidar_points)} LiDAR points")
        while self._running and self.lidar:
            try:
                # Use the new adapter method
                # Assuming get_latest_scan returns the processed data points
                raw_data = self.lidar.get_latest_scan()
                self._logger.info(f"Raw data received: {type(raw_data)} – keys: {raw_data.keys() if raw_data else 'None'}")
                if raw_data and 'points' in raw_data:
                    # Convert to LidarPoint objects expected by RobotState
                    # raw_data is a dict: {'points': [...], 'timestamp': ..., etc.}
                    lidar_points = []
                    for p in raw_data['points']:
                        # Handle both dictionary and tuple formats for compatibility
                        if isinstance(p, dict):
                            lidar_points.append(LidarPoint(
                                angle=p.get('angle', 0.0), 
                                distance=p.get('distance', 0.0), 
                                quality=p.get('quality', 0)
                            ))
                        elif isinstance(p, (list, tuple)) and len(p) >= 2:
                            # Legacy tuple format (angle, distance, quality)
                            lidar_points.append(LidarPoint(
                                angle=p[0], 
                                distance=p[1], 
                                quality=p[2] if len(p) > 2 else 0
                            ))
                    
                    self.state.update_lidar_data(lidar_points)
                    self._logger.debug(f"Updated state with {len(lidar_points)} LiDAR points")
                
                # Check connection status periodically
                if not self.settings.SIMULATION_MODE:
                    adapter_status = self.lidar.get_status()
                    if not adapter_status.get('connected', False):
                        self._logger.warning("LiDAR reported disconnected in loop")
                        self.state.update_status(lidar_connected=False)
                        
            except Exception as e:
                self._logger.error(f"LiDAR scan loop error: {e}")
                self.state.set_error(f"LiDAR loop error: {e}")
                # Don't break immediately, retry? or break? 
                # For robustness, maybe sleep and retry unless fatal
                time.sleep(1) 
                
            time.sleep(0.05) # 20Hz update rate

        self._logger.info("LiDAR scan loop stopped")

    def send_motor_command(self, command: str, speed: int = 50) -> bool:
        """Send directional command to motor controller."""
        return self.motor_controller.send_command(command, speed)

    def stop_motors(self) -> None:
        if self.motor_controller is None:
            self._logger.warning("Stop motors called but controller not initialized")
            return

        try:
            self.send_motor_command('stop')
            self._logger.info("Motors stopped")
        except Exception as e:
            self._logger.error(f"Failed to stop motors: {e}")

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def shutdown(self) -> None:
        """Gracefully disconnect all hardware peripherals."""
        self._logger.info("Shutting down hardware manager...")
        self._running = False

        if self.lidar_thread and self.lidar_thread.is_alive():
            self._logger.info("Stopping LiDAR scan thread...")
            self.lidar_thread.join(timeout=2.0)

        if self.motor_controller:
            try:
                self.motor_controller.disconnect()
                self._logger.info("Motor controller disconnected")
            except Exception as e:
                self._logger.error(f"Error disconnecting motor: {e}")

        if self.lidar:
            try:
                self.lidar.stop_scanning()
                self.lidar.disconnect()
                self._logger.info("LiDAR disconnected")
            except Exception as e:
                self._logger.error(f"Error disconnecting LiDAR: {e}")

        self.state.update_status(mode="idle")
        self._logger.info("Hardware shutdown complete")