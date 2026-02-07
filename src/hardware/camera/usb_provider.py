"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/camera/usb_provider.py
Description: USB webcam provider implementation using OpenCV.
"""

import logging
import threading
from typing import Tuple, Optional

import cv2
import numpy as np

from .base import CameraProvider

logger = logging.getLogger(__name__)


class UsbCameraProvider(CameraProvider):
    """Camera provider implementation for USB webcams via OpenCV.

    Manages video capture using the V4L2 backend. Supports automatic device
    index scanning and MJPEG stream configuration.

    Attributes:
        stream (Optional[cv2.VideoCapture]): The OpenCV capture object.
        is_running (bool): Flag indicating if the camera is active.
        camera_index (Optional[int]): The index of the active camera device.
    """

    def __init__(self) -> None:
        """Initialize the USB camera provider state."""
        self.stream: Optional[cv2.VideoCapture] = None
        self.is_running: bool = False
        self.camera_index: Optional[int] = None
        self._lock = threading.Lock()

    def start(self, width: int, height: int, fps: int) -> bool:
        """Initialize USB camera with V4L2 backend.

        Scans camera indices 0-5 to find a working device. Configures the
        stream for MJPEG format to optimize USB bandwidth.

        Args:
            width: Desired capture width (1-3840).
            height: Desired capture height (1-2160).
            fps: Desired framerate (1-120).

        Returns:
            True if a camera was successfully opened and configured, False otherwise.

        Raises:
            ValueError: If parameters are outside valid ranges.
            RuntimeError: If camera is already running.
        """
        if not (0 < width <= 3840 and 0 < height <= 2160 and 0 < fps <= 120):
            raise ValueError(f"Invalid parameters: {width}x{height}@{fps}")

        if self.is_running:
            raise RuntimeError("Camera already started. Call stop() first.")

        # Try index 0 first, then 1-5
        indices = [0] + list(range(1, 6))
        
        for index in indices:
            if self._try_init_camera(index, width, height, fps):
                self.is_running = True
                self.camera_index = index
                logger.info(f"USB camera started at index {index}")
                return True

        logger.error("No usable USB camera found")
        return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Acquire the next frame from the USB camera.

        Returns:
            Tuple[bool, Optional[np.ndarray]]: (True, frame) on success,
            (False, None) on failure or if not running.
        """
        if not self.is_running or self.stream is None:
            return False, None

        try:
            ret, frame = self.stream.read()
            if ret and frame is not None:
                return True, frame
            return False, None
        except cv2.error as e:
            logger.error(f"OpenCV read error: {e}")
            return False, None

    def stop(self) -> None:
        """Release the USB camera resource.

        Safe to call from any thread and idempotent.
        """
        with self._lock:
            if self.stream is not None:
                self.stream.release()
                self.stream = None
            self.is_running = False
            self.camera_index = None
            logger.info("USB camera stopped")

    def _try_init_camera(self, index: int, width: int, height: int, fps: int) -> bool:
        """Attempt to initialize a specific camera index.

        Args:
            index: Device index to test.
            width: Target width.
            height: Target height.
            fps: Target FPS.

        Returns:
            True if successful, False otherwise.
        """
        try:
            cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
            if not cap.isOpened():
                return False

            # Set MJPG first to allow higher resolutions/framerates on USB 2.0
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)

            # Double-read handshake to ensure stream is stable
            for _ in range(2):
                ret, _ = cap.read()
                if not ret:
                    cap.release()
                    return False

            self.stream = cap
            return True
        except cv2.error:
            if 'cap' in locals():
                cap.release()
            return False