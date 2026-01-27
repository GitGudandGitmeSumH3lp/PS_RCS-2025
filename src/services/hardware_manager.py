"""Hardware Manager Module.

This module provides the HardwareManager class, which acts as the central
coordinator for robot hardware interactions. It manages the lifecycle of
motor controllers and LiDAR sensors, handles threading for background
scanning, and provides a unified interface for hardware command and control.
It supports both real hardware connections and simulation modes.

Typical usage example:
    settings = Settings()
    state = RobotState()
    manager = HardwareManager(settings, state)
    status = manager.start_all_drivers()
    manager.send_motor_command("forward", 100)
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Union

from src.core.config import Settings
from src.core.state import RobotState, LidarPoint

# Soft dependency loading for hardware libraries
try:
    from motor_controller import MotorController
    LEGACY_MOTOR_AVAILABLE = True
except ImportError:
    LEGACY_MOTOR_AVAILABLE = False

try:
    from lidar_handler import LidarHandler
    LEGACY_LIDAR_AVAILABLE = True
except ImportError:
    LEGACY_LIDAR_AVAILABLE = False


class MockMotorController:
    """Mock implementation of MotorController for simulation and testing.
    
    Simulates connection, command sending, and disconnection without
    requiring physical hardware.
    """
    
    def __init__(self) -> None:
        """Initialize the mock motor controller."""
        self.connected = True
    
    def connect(self, port: str, baud: int) -> bool:
        """Simulate connecting to a motor controller.
        
        Args:
            port: Serial port name.
            baud: Baud rate.
            
        Returns:
            bool: Always True in mock mode.
        """
        logging.info(f"[MOCK] Motor connected to {port} @ {baud}")
        return True
    
    def send_command(self, command: str, speed: int) -> None:
        """Simulate sending a movement command.
        
        Args:
            command: Direction string.
            speed: Speed value.
        """
        logging.info(f"[MOCK] Motor command: {command} @ speed {speed}")
    
    def stop(self) -> None:
        """Simulate stopping the motors."""
        logging.info("[MOCK] Motor stopped")
    
    def disconnect(self) -> None:
        """Simulate disconnecting from the motor controller."""
        logging.info("[MOCK] Motor disconnected")


class MockLidarHandler:
    """Mock implementation of LidarHandler for simulation and testing.
    
    Generates fake scan data to simulate environmental sensing.
    """
    
    def __init__(self) -> None:
        """Initialize the mock LiDAR handler."""
        self.connected = True
    
    def connect(self, port: str, baud: int) -> bool:
        """Simulate connecting to a LiDAR unit.
        
        Args:
            port: Serial port name.
            baud: Baud rate.
            
        Returns:
            bool: Always True in mock mode.
        """
        logging.info(f"[MOCK] LiDAR connected to {port} @ {baud}")
        return True
    
    def get_scan(self) -> List[Tuple[float, float, int]]:
        """Generate fake scan data.
        
        Returns:
            List[Tuple[float, float, int]]: A list of tuples representing
            (angle, distance, quality).
        """
        # Generates fake scan data: (angle, distance, quality)
        return [(i * 1.5, 1000 + i * 10, 50) for i in range(240)]
    
    def disconnect(self) -> None:
        """Simulate disconnecting from the LiDAR unit."""
        logging.info("[MOCK] LiDAR disconnected")


class HardwareManager:
    """Manager for Robot Hardware interactions.
    
    Coordinates motor controller and LiDAR handler, managing their
    lifecycle, threads, and error states. It serves as the bridge
    between the high-level application logic and low-level drivers.
    
    Attributes:
        settings: Application configuration settings.
        state: Shared RobotState object for telemetry updates.
        motor_controller: Instance of the active motor controller.
        lidar_handler: Instance of the active LiDAR handler.
        lidar_thread: Background thread for continuous LiDAR scanning.
    """
    
    def __init__(
        self,
        settings: Settings,
        state: RobotState,
        motor_controller_class: Optional[Any] = None,
        lidar_handler_class: Optional[Any] = None
    ) -> None:
        """Initialize hardware manager with configuration.
        
        Args:
            settings: Application settings.
            state: Shared RobotState object.
            motor_controller_class: Dependency injection for motor class (optional).
                Used primarily for testing to inject mocks.
            lidar_handler_class: Dependency injection for LiDAR class (optional).
                Used primarily for testing to inject mocks.
        """
        self.settings = settings
        self.state = state
        self._running = True
        
        self.motor_controller_class = motor_controller_class
        self.lidar_handler_class = lidar_handler_class
        
        self.motor_controller: Optional[Any] = None
        self.lidar_handler: Optional[Any] = None
        self.lidar_thread: Optional[threading.Thread] = None
        self._connected = False
        self._lock = threading.Lock()
        self._logger = logging.getLogger(__name__)
    
    def start_all_drivers(self) -> Dict[str, str]:
        """Initializes and connects all hardware drivers.
        
        Handles logic for simulation mode vs real hardware, including
        fallback mechanisms if drivers are missing. Updates the shared
        state with connection results.
        
        Returns:
            Dict[str, str]: Mapping of component names ('motor', 'lidar', 
            'camera') to their connection status ('connected', 'disconnected', 
            'simulated', 'failed', 'unavailable', 'error').
        """
        status = {
            "motor": "disconnected",
            "lidar": "disconnected",
            "camera": "disabled"
        }
        
        if self.settings.SIMULATION_MODE:
            self._logger.info("Starting in SIMULATION MODE")
            self.motor_controller = MockMotorController()
            self.lidar_handler = MockLidarHandler()
            
            # Simulate connection
            self.motor_controller.connect("MOCK_PORT", 9600)
            self.lidar_handler.connect("MOCK_PORT", 115200)
            
            status["motor"] = "simulated"
            status["lidar"] = "simulated"
            self.state.update_status(motor_connected=True, lidar_connected=True)
            
        else:
            self._logger.info("Starting in REAL HARDWARE MODE")
            
            # --- Motor Initialization ---
            if self.motor_controller_class is None:
                if LEGACY_MOTOR_AVAILABLE:
                    motor_class = MotorController
                else:
                    self._logger.warning("motor_controller module not found, motor disabled")
                    self.state.update_status(motor_connected=False)
                    status["motor"] = "unavailable"
                    motor_class = None
            else:
                motor_class = self.motor_controller_class
            
            if motor_class is not None:
                try:
                    self.motor_controller = motor_class()
                    if self.motor_controller.connect(
                        self.settings.MOTOR_PORT, 
                        self.settings.MOTOR_BAUD_RATE
                    ):
                        status["motor"] = "connected"
                        self.state.update_status(motor_connected=True)
                        self._logger.info("Motor controller connected successfully")
                    else:
                        status["motor"] = "failed"
                        self.state.update_status(motor_connected=False)
                        self._logger.error("Motor controller connection failed")
                except Exception as e:
                    self._logger.error(f"Motor connection error: {e}")
                    status["motor"] = "error"
                    self.state.update_status(motor_connected=False)
            
            # --- LiDAR Initialization ---
            if self.lidar_handler_class is None:
                if LEGACY_LIDAR_AVAILABLE:
                    lidar_class = LidarHandler
                else:
                    self._logger.warning("lidar_handler module not found, lidar disabled")
                    self.state.update_status(lidar_connected=False)
                    status["lidar"] = "unavailable"
                    lidar_class = None
            else:
                lidar_class = self.lidar_handler_class
            
            if lidar_class is not None:
                try:
                    self.lidar_handler = lidar_class()
                    if self.lidar_handler.connect(
                        self.settings.LIDAR_PORT, 
                        self.settings.LIDAR_BAUD_RATE
                    ):
                        status["lidar"] = "connected"
                        self.state.update_status(lidar_connected=True)
                        self._logger.info("LiDAR connected successfully")
                        
                        # Start background scanning thread
                        self.lidar_thread = threading.Thread(
                            target=self._lidar_scan_loop, 
                            daemon=True
                        )
                        self.lidar_thread.start()
                    else:
                        status["lidar"] = "failed"
                        self.state.update_status(lidar_connected=False)
                        self._logger.error("LiDAR connection failed")
                except Exception as e:
                    self._logger.error(f"LiDAR connection error: {e}")
                    status["lidar"] = "error"
                    self.state.update_status(lidar_connected=False)
        
        self.state.update_status(camera_connected=False)
        return status
    
    def get_status(self) -> dict:
        """Retrieves a snapshot of the current hardware and system status.
        
        Returns:
            dict: Current state telemetry including connection status,
            errors, and mode.
        """
        return self.state.get_status_snapshot()
    
    def _lidar_scan_loop(self) -> None:
        """Background thread loop for fetching LiDAR data.
        
        Continuously polls LiDAR handler for new scans and updates
        shared state. Stops if _running is False or an error occurs.
        Handles data conversion from raw tuples to LidarPoint objects.
        """
        self._logger.info("LiDAR scan loop started")
        while self._running and self.lidar_handler:
            try:
                raw_points = self.lidar_handler.get_scan()
                lidar_points = [
                    LidarPoint(angle=angle, distance=distance, quality=quality)
                    for angle, distance, quality in raw_points
                ]
                self.state.update_lidar_data(lidar_points)
            except Exception as e:
                self._logger.error(f"LiDAR scan error: {e}")
                self.state.set_error(f"LiDAR disconnected: {e}")
                self.state.update_status(lidar_connected=False)
                break
            time.sleep(0.1)  # 10Hz scan rate
        
        self._logger.info("LiDAR scan loop stopped")
    
    def send_motor_command(self, command: str, speed: int = 50) -> bool:
        """Sends a movement command to the motor controller.
        
        Args:
            command: Direction string ('forward', 'backward', 'left', 'right', 'stop').
            speed: Desired speed 0-255. Defaults to 50.
            
        Returns:
            True if command was sent successfully, False otherwise.
            
        Raises:
            ValueError: If command is invalid or speed is out of range.
        """
        allowed_commands = {"forward", "backward", "left", "right", "stop"}
        if command not in allowed_commands:
            raise ValueError(
                f"Invalid motor command '{command}'. Allowed: {', '.join(sorted(allowed_commands))}"
            )
        
        if not (0 <= speed <= 255):
            raise ValueError(f"Speed must be 0-255, got {speed}")
        
        # Check connection using state snapshot to be safe
        is_connected = self.state.get_status_snapshot().get("motor_connected", False)
        if not self.motor_controller or not is_connected:
            self._logger.error("Motor command failed: Motor not connected")
            self.state.set_error("Motor disconnected")
            return False
        
        try:
            self.motor_controller.send_command(command, speed)
            self._logger.info(f"Motor command sent: {command} @ {speed}")
            return True
        except Exception as e:
            self._logger.error(f"Motor communication error: {e}")
            self.state.set_error(f"Motor communication failed: {e}")
            return False
    
    def stop_motors(self) -> None:
        """Emergency stop for all motors.
        
        Attempts to send a stop command to the motor controller regardless
        of current speed or direction.
        """
        if self.motor_controller is None:
            self._logger.warning("Stop motors called but controller not initialized")
            return
        
        try:
            self.motor_controller.stop()
            self._logger.info("Motors stopped")
        except Exception as e:
            self._logger.error(f"Failed to stop motors: {e}")
    
    def is_connected(self) -> bool:
        """Thread-safe connection status check.
        
        Returns:
            bool: True if the manager believes hardware is connected.
        """
        with self._lock:
            return self._connected
    
    def shutdown(self) -> None:
        """Clean shutdown of hardware connections.
        
        Stops background threads, disconnects hardware drivers, and updates
        state to idle. Should be called on application exit.
        """
        self._logger.info("Shutting down hardware manager...")
        self._running = False
        
        # Stop LiDAR thread
        if self.lidar_thread and self.lidar_thread.is_alive():
            self._logger.info("Stopping LiDAR scan thread...")
            self.lidar_thread.join(timeout=2.0)
        
        # Disconnect motor controller
        if self.motor_controller:
            try:
                self.motor_controller.stop()
                self.motor_controller.disconnect()
                self._logger.info("Motor controller disconnected")
            except Exception as e:
                self._logger.error(f"Error disconnecting motor: {e}")
        
        # Disconnect LiDAR
        if self.lidar_handler:
            try:
                self.lidar_handler.disconnect()
                self._logger.info("LiDAR disconnected")
            except Exception as e:
                self._logger.error(f"Error disconnecting LiDAR: {e}")
        
        self.state.update_status(mode="idle")
        self._logger.info("Hardware shutdown complete")