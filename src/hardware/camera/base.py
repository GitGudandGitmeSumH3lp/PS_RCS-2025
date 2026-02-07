"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/camera/base.py
Description: Abstract base class for camera hardware providers.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np


class CameraProvider(ABC):
    """Abstract base class defining camera hardware interface contract.
    
    This class enforces a uniform interface for different camera backends
    (e.g., USB/OpenCV, CSI/Picamera2), ensuring the VisionManager remains
    hardware-agnostic.
    """

    @abstractmethod
    def start(self, width: int, height: int, fps: int) -> bool:
        """Initialize camera hardware with specified parameters.

        This method MUST be called from the main thread for compatibility with
        certain hardware drivers (e.g., picamera2).

        Args:
            width: Capture width in pixels (1-3840).
            height: Capture height in pixels (1-2160).
            fps: Capture framerate (1-120).

        Returns:
            True if camera successfully initialized and ready for reads.
            False if initialization failed (hardware unavailable/busy).

        Raises:
            ValueError: If parameters are outside valid ranges.
            RuntimeError: If called when already running.
        """
        pass
    
    @abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Acquire the next available frame from camera.

        This method blocks until a frame is available or a timeout occurs.
        It is safe to call from a background capture thread.

        Returns:
            A tuple containing:
                - success (bool): True if frame acquired successfully.
                - frame (Optional[np.ndarray]): BGR image array if success, else None.
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Release hardware and cleanup resources.
        
        This method is idempotent (safe to call multiple times) and thread-safe.
        It ensures all hardware handles are released and background threads
        terminated.
        """
        pass


class CameraError(Exception):
    """Base exception for camera-related errors."""
    pass


class CameraInitializationError(CameraError):
    """Raised when camera hardware cannot be initialized."""
    pass


class CameraConfigurationError(CameraError):
    """Raised when configuration parameters are invalid."""
    pass