"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/core/config.py
Description: Configuration management for the robot system.
"""

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    """Immutable application settings container.
    
    Attributes:
        MOTOR_PORT: Serial port for the motor controller.
        LIDAR_PORT: Serial port for the LiDAR sensor.
        CAMERA_PORT: Serial port or ID for the camera (Optional).
        DB_PATH: Filepath to the SQLite database.
        SIMULATION_MODE: If True, uses mock hardware drivers.
        MOTOR_BAUD_RATE: Baud rate for motor communication.
        LIDAR_BAUD_RATE: Baud rate for LiDAR communication.
        API_HOST: Host address to bind the API server.
        API_PORT: Port number to bind the API server.
    """
    MOTOR_PORT: str
    LIDAR_PORT: str
    CAMERA_PORT: Optional[str]
    DB_PATH: str
    SIMULATION_MODE: bool
    MOTOR_BAUD_RATE: int
    LIDAR_BAUD_RATE: int
    API_HOST: str
    API_PORT: int
    
    @classmethod
    def load_from_file(cls, filepath: str = "config/settings.json") -> "Settings":
        """Loads and validates settings from a JSON file.
        
        Args:
            filepath: Path to the configuration JSON file.
                Defaults to "config/settings.json".
        
        Returns:
            A new instance of Settings with validated values.
        
        Raises:
            FileNotFoundError: If the config file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
            ValueError: If required keys are missing or values are invalid 
                (e.g., negative baud rates, invalid ports).
        """
        try:
            with open(filepath, 'r') as f:
                config_data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found at {filepath}")
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Malformed JSON in config file", e.doc, e.pos)
        
        required_keys = [
            "MOTOR_PORT", "LIDAR_PORT", "DB_PATH", "SIMULATION_MODE", 
            "MOTOR_BAUD_RATE", "LIDAR_BAUD_RATE", "API_HOST", "API_PORT"
        ]
        
        for key in required_keys:
            if key not in config_data:
                raise ValueError(f"Missing required configuration key: {key}")
        
        if not isinstance(config_data.get("SIMULATION_MODE"), bool):
            raise ValueError("Invalid type for SIMULATION_MODE: expected bool")
        
        api_port = config_data.get("API_PORT")
        if not isinstance(api_port, int):
            raise ValueError(f"Invalid type for API_PORT: expected int, got {type(api_port)}")
        if not (1024 <= api_port <= 65535):
            raise ValueError(f"API_PORT must be 1024-65535, got {api_port}")
        
        motor_baud = config_data.get("MOTOR_BAUD_RATE")
        if not isinstance(motor_baud, int) or motor_baud <= 0:
            raise ValueError(f"Invalid type for MOTOR_BAUD_RATE: expected positive int")
        
        lidar_baud = config_data.get("LIDAR_BAUD_RATE")
        if not isinstance(lidar_baud, int) or lidar_baud <= 0:
            raise ValueError(f"Invalid type for LIDAR_BAUD_RATE: expected positive int")
        
        return cls(
            MOTOR_PORT=config_data["MOTOR_PORT"],
            LIDAR_PORT=config_data["LIDAR_PORT"],
            CAMERA_PORT=config_data.get("CAMERA_PORT"),
            DB_PATH=config_data["DB_PATH"],
            SIMULATION_MODE=config_data["SIMULATION_MODE"],
            MOTOR_BAUD_RATE=config_data["MOTOR_BAUD_RATE"],
            LIDAR_BAUD_RATE=config_data["LIDAR_BAUD_RATE"],
            API_HOST=config_data["API_HOST"],
            API_PORT=config_data["API_PORT"]
        )


@dataclass(frozen=True)
class CameraConfig:
    """Immutable camera configuration."""
    interface: str
    width: int
    height: int
    fps: int
    
    @classmethod
    def from_environment(cls) -> 'CameraConfig':
        interface = os.getenv('CAMERA_INTERFACE', 'auto').lower()
        
        try:
            width = int(os.getenv('CAMERA_WIDTH', '640'))
            height = int(os.getenv('CAMERA_HEIGHT', '480'))
            fps = int(os.getenv('CAMERA_FPS', '30'))
        except ValueError as e:
            raise ValueError(f"Invalid camera configuration: {e}")
        
        if interface not in {'usb', 'csi', 'auto'}:
            raise ValueError(f"Invalid CAMERA_INTERFACE: {interface}")
        if not (1 <= width <= 3840):
            raise ValueError(f"CAMERA_WIDTH must be 1-3840, got {width}")
        if not (1 <= height <= 2160):
            raise ValueError(f"CAMERA_HEIGHT must be 1-2160, got {height}")
        if not (1 <= fps <= 120):
            raise ValueError(f"CAMERA_FPS must be 1-120, got {fps}")
        
        return cls(
            interface=interface,
            width=width,
            height=height,
            fps=fps
        )