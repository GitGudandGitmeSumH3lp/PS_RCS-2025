# MERGED FILE: src/services/hardware_manager.py
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/services/hardware_manager.py
Description: Coordinates interactions with robot hardware including motor controllers and LiDAR sensors.
"""
import logging
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import serial
except ImportError:
    serial = None

from src.core.config import Settings
from src.core.state import LidarPoint, RobotState
from src.hardware.motor_controller import MotorController

try:
    from src.hardware.lidar_adapter import LiDARAdapter
except ImportError:
    LiDARAdapter = None

try:
    from lidar_handler import LidarHandler
    LEGACY_LIDAR_AVAILABLE = True
except ImportError:
    LEGACY_LIDAR_AVAILABLE = False

try:
    from src.services.obstacle_avoidance import SimpleObstacleAvoidance
except ImportError:
    SimpleObstacleAvoidance = None
    logging.warning("SimpleObstacleAvoidance not available. Autonomous mode disabled.")


class MockMotorController:
    """Mock motor controller for PC testing without hardware."""

    def __init__(self) -> None:
        self._connected = True

    def connect(self, port: str, baud: int) -> bool:
        logging.info(f"[MOCK] Motor connected to {port} @ {baud}")
        self._connected = True
        return True

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected

    @property
    def connected(self) -> bool:
        """Alias for backward compatibility."""
        return self._connected

    def send_command(self, command: str, speed: int) -> bool:
        logging.info(f"[MOCK] Motor command: {command} @ speed {speed}")
        return True

    def stop(self) -> None:
        logging.info("[MOCK] Motor stopped")

    def disconnect(self) -> None:
        logging.info("[MOCK] Motor disconnected")
        self._connected = False


class MockLidarHandler:
    """Mock LiDAR handler for PC testing without hardware."""

    def __init__(self) -> None:
        self._connected = True
        self.scanning = False

    def connect(self, port: str = None, baud: int = 115200) -> bool:
        logging.info(f"[MOCK] LiDAR connected to {port} @ {baud}")
        self._connected = True
        return True

    def start_scanning(self) -> bool:
        self.scanning = True
        logging.info("[MOCK] LiDAR scanning started")
        return True

    def stop_scanning(self) -> bool:
        self.scanning = False
        logging.info("[MOCK] LiDAR scanning stopped")
        return True

    def get_latest_scan(self) -> List[Dict[str, float]]:
        return [{"angle": i * 1.5, "distance": 1000 + i * 10, "quality": 50} for i in range(240)]

    def get_scan(self) -> List[Tuple[float, float, int]]:
        return [(i * 1.5, 1000 + i * 10, 50) for i in range(240)]

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "scanning": self.scanning,
            "rpm": 0.0
        }

    def disconnect(self) -> None:
        self._connected = False
        logging.info("[MOCK] LiDAR disconnected")


class HardwareManager:
    """Coordinates hardware interactions (motor, LiDAR, camera)."""

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

        if motor_controller_class is not None:
            motor_class = motor_controller_class
        elif settings.SIMULATION_MODE:
            motor_class = MockMotorController
        else:
            motor_class = MotorController
        self.motor_controller = motor_class()

        if settings.SIMULATION_MODE:
            self.lidar = MockLidarHandler()
        else:
            if LiDARAdapter:
                self.lidar = LiDARAdapter(config={
                    "port": settings.LIDAR_PORT,
                    "baudrate": settings.LIDAR_BAUD_RATE,
                    "max_queue_size": 1000,
                    "enable_simulation": False
                })
            else:
                self.lidar = None
                logging.warning("LiDARAdapter not found. LiDAR disabled.")

        self.lidar_thread: Optional[threading.Thread] = None
        self.avoidance_thread: Optional[threading.Thread] = None
        self.avoidance: Optional[Any] = None
        self._connected = False
        self._lock = threading.Lock()
        self._logger = logging.getLogger(__name__)

        self._connect_motor()

    def _connect_motor(self) -> None:
        """Attempt motor controller connection on startup. Non-fatal on failure."""
        try:
            if sys.platform.startswith('win') and self.settings.MOTOR_PORT == '/dev/ttyUSB0':
                self._logger.warning("Default Linux port on Windows - motor disabled.")
                self.state.update_status(motor_connected=False)
                return

            if self.motor_controller.connect(self.settings.MOTOR_PORT, self.settings.MOTOR_BAUD_RATE):
                self.state.update_status(motor_connected=self.motor_controller.is_connected)
                self._logger.info("Motor controller connected.")
            else:
                self.state.update_status(motor_connected=False)
                self._logger.warning("Motor controller connection failed. Running in degraded mode.")
        except (FileNotFoundError, OSError) as e:
            self._logger.error(f"Motor connection error (port not available): {e}")
            self.state.update_status(motor_connected=False)
        except Exception as e:
            self._logger.error(f"Unexpected motor init error: {e}")
            self.state.update_status(motor_connected=False)

    def start_all_drivers(self) -> Dict[str, str]:
        """Initialize all hardware drivers and return status."""
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
            self.motor_controller.connect("MOCK_PORT", 9600)
            if self.lidar:
                self.lidar.connect("MOCK_PORT", 115200)
                self.lidar.start_scanning()
            status["motor"] = "simulated"
            status["lidar"] = "simulated"
            self.state.update_status(motor_connected=True, lidar_connected=True)
        else:
            self._logger.info("Starting in REAL HARDWARE MODE")
            motor_ok = self.motor_controller.is_connected
            if motor_ok:
                status["motor"] = "connected"
            if self.lidar:
                try:
                    try:
                        connected = self.lidar.connect()
                    except TypeError:
                        connected = self.lidar.get_status().get('connected', False)
                    if connected:
                        status["lidar"] = "connected"
                        self.state.update_status(lidar_connected=True)
                        self._logger.info("LiDAR connected successfully")
                        if self.lidar.start_scanning():
                            self._logger.info("LiDAR scanning started")
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

    def enable_obstacle_avoidance(self, safety_distance_mm: int = 500) -> bool:
        """
        Enable autonomous obstacle avoidance.

        Args:
            safety_distance_mm: Minimum distance to obstacles in millimeters.

        Returns:
            bool: True if avoidance enabled successfully, False otherwise.
        """
        if SimpleObstacleAvoidance is None:
            self._logger.error("SimpleObstacleAvoidance not available")
            return False
        if not self.lidar or not self.motor_controller:
            self._logger.error("Cannot enable avoidance - LiDAR or motors unavailable")
            return False
        try:
            self.avoidance = SimpleObstacleAvoidance(self, safety_distance_mm)
            self.avoidance_thread = self.avoidance.start_continuous(
                interval_ms=100,
                speed=80
            )
            self._logger.info(f"Obstacle avoidance enabled (safety: {safety_distance_mm}mm)")
            return True
        except Exception as e:
            self._logger.error(f"Failed to enable obstacle avoidance: {e}")
            return False

    def disable_obstacle_avoidance(self) -> None:
        """Disable autonomous obstacle avoidance mode."""
        if hasattr(self, 'avoidance') and self.avoidance is not None:
            try:
                self.avoidance.stop()
                self.avoidance = None
                self._logger.info("Obstacle avoidance disabled")
            except Exception as e:
                self._logger.error(f"Error disabling obstacle avoidance: {e}")

    def get_status(self) -> dict:
        """Return current hardware status snapshot."""
        return self.state.get_status_snapshot()

    def _lidar_scan_loop(self) -> None:
        """Background loop to fetch data from LiDAR adapter and update state."""
        self._logger.info("LiDAR scan loop started")
        while self._running and self.lidar:
            try:
                raw_data = self.lidar.get_latest_scan()
                if raw_data:
                    lidar_points = []
                    for p in raw_data:
                        if isinstance(p, dict):
                            lidar_points.append(LidarPoint(
                                angle=p.get('angle', 0.0),
                                distance=p.get('distance', 0.0),
                                quality=p.get('quality', 0)
                            ))
                        elif isinstance(p, (list, tuple)) and len(p) >= 2:
                            lidar_points.append(LidarPoint(
                                angle=p[0],
                                distance=p[1],
                                quality=p[2] if len(p) > 2 else 0
                            ))
                    self.state.update_lidar_data(lidar_points)
                if not self.settings.SIMULATION_MODE:
                    adapter_status = self.lidar.get_status()
                    if not adapter_status.get('connected', False):
                        self._logger.warning("LiDAR reported disconnected in loop")
                        self.state.update_status(lidar_connected=False)
            except Exception as e:
                self._logger.error(f"LiDAR scan loop error: {e}")
                self.state.set_error(f"LiDAR loop error: {e}")
                time.sleep(1)
            time.sleep(0.05)
        self._logger.info("LiDAR scan loop stopped")

    def send_motor_command(self, command: str, speed: int = 50) -> bool:
        """Send directional command to motor controller."""
        try:
            if not self.motor_controller.is_connected:
                self._logger.warning("Cannot send command: motor not connected")
                return False
            return self.motor_controller.send_command(command, speed)
        except Exception as e:
            self._logger.error(f"Motor command error: {e}")
            return False

    def stop_motors(self) -> None:
        """Emergency stop for all motors."""
        if self.motor_controller is None:
            self._logger.warning("Stop motors called but controller not initialized")
            return
        try:
            self.motor_controller.stop()
            self._logger.info("Motors stopped")
        except Exception as e:
            self._logger.error(f"Failed to stop motors: {e}")

    def is_connected(self) -> bool:
        """Return overall hardware connection status."""
        with self._lock:
            return self._connected

    def shutdown(self) -> None:
        """Gracefully disconnect all hardware peripherals."""
        self._logger.info("Shutting down hardware manager...")
        self._running = False

        if self.avoidance_thread and self.avoidance_thread.is_alive():
            self._logger.info("Stopping obstacle avoidance thread...")
            self.disable_obstacle_avoidance()

        # Stop LiDAR first
        if self.lidar:
            try:
                # Handle both generic adapter and direct reader class types
                if hasattr(self.lidar, 'stop_scan'):
                    self.lidar.stop_scan()
                elif hasattr(self.lidar, 'stop_scanning'):
                    self.lidar.stop_scanning()
                
                if hasattr(self.lidar, 'disconnect'):
                    self.lidar.disconnect()
            except Exception as e:
                self._logger.error(f"Error stopping LiDAR: {e}")

        # Wait for LiDAR thread (if any) with timeout
        if self.lidar_thread and self.lidar_thread.is_alive():
            self._logger.info("Waiting for LiDAR thread to finish...")
            self.lidar_thread.join(timeout=3.0)
            if self.lidar_thread.is_alive():
                self._logger.warning("LiDAR thread did not terminate; continuing shutdown")

        # Disconnect motor controller
        if self.motor_controller:
            try:
                self.motor_controller.disconnect()
                self._logger.info("Motor controller disconnected")
            except Exception as e:
                self._logger.error(f"Error disconnecting motor: {e}")

        self.state.update_status(mode="idle")
        self._logger.info("Hardware shutdown complete")