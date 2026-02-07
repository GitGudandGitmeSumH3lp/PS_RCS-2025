"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/camera/csi_provider.py
Description: Raspberry Pi Camera Module 3 provider using picamera2.
"""

import logging
import threading
from typing import Tuple, Optional

import cv2
import numpy as np

from .base import CameraProvider

logger = logging.getLogger(__name__)

# Import guard for non-Pi platforms
try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    _PICAMERA2_AVAILABLE = False


class CsiCameraProvider(CameraProvider):
    """Camera provider implementation for Pi Camera Module via Libcamera.

    This provider uses the `picamera2` library to interface with CSI cameras.
    It handles RGB to BGR conversion automatically, as OpenCV expects BGR.

    Attributes:
        picam2 (Optional[Picamera2]): The picamera2 interface object.
        is_running (bool): Flag indicating if the camera is active.
        lock (threading.Lock): Mutex for thread-safe shutdown.
    """

    def __init__(self) -> None:
        """Initialize the CSI camera provider state."""
        self.picam2: Optional['Picamera2'] = None
        self.is_running: bool = False
        self.lock = threading.Lock()

    def start(self, width: int, height: int, fps: int) -> bool:
        """Initialize the CSI camera using picamera2.

        CRITICAL: This method MUST be called from the main thread.

        Args:
            width: Desired capture width (1-3840).
            height: Desired capture height (1-2160).
            fps: Desired framerate (1-120).

        Returns:
            True if initialized successfully, False otherwise.

        Raises:
            ValueError: If parameters are invalid.
            RuntimeError: If camera is already running.
        """
        if not (0 < width <= 3840 and 0 < height <= 2160 and 0 < fps <= 120):
            raise ValueError(f"Invalid parameters: {width}x{height}@{fps}")

        if not _PICAMERA2_AVAILABLE:
            logger.error("picamera2 not available. Install via: sudo apt install python3-picamera2")
            return False

        with self.lock:
            if self.is_running:
                raise RuntimeError("Camera already started. Call stop() first.")

            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_still_configuration(
                    main={"size": (width, height), "format": "RGB888"},
                    lores={"size": (width, height), "format": "RGB888"}
                )
                self.picam2.configure(config)
                self.picam2.start()
                self.is_running = True
                logger.info(f"CSI camera initialized ({width}x{height}@{fps}fps)")
                return True
            except RuntimeError as e:
                logger.error(f"CSI initialization failed (RuntimeError): {e}")
                self._cleanup_on_fail()
                return False
            except Exception as e:
                # picamera2 can raise various exceptions, catch broadly to prevent crash
                logger.error(f"CSI initialization failed (Unexpected): {e}")
                self._cleanup_on_fail()
                return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Acquire the next frame from the CSI camera.

        Captures an array from the 'lores' stream and converts it from RGB
        to BGR for OpenCV compatibility.

        Returns:
            Tuple[bool, Optional[np.ndarray]]: (True, BGR_frame) on success,
            (False, None) on failure.
        """
        if not self.is_running or self.picam2 is None:
            return False, None

        try:
            # Capture array is thread-safe in picamera2
            frame_rgb = self.picam2.capture_array("lores")
            # Convert RGB (PiCamera default) to BGR (OpenCV default)
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            return True, frame_bgr
        except RuntimeError as e:
            logger.error(f"CSI read failed: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected CSI read error: {e}")
            return False, None

    def stop(self) -> None:
        """Release the CSI camera resource.

        Thread-safe and idempotent. Ensures proper closure of the picamera2
        instance to free the hardware resource.
        """
        with self.lock:
            if not self.is_running and self.picam2 is None:
                return

            try:
                if self.picam2 is not None:
                    self.picam2.stop()
                    self.picam2.close()
            except Exception as e:
                logger.error(f"CSI cleanup error: {e}")
            finally:
                self.picam2 = None
                self.is_running = False
                logger.info("CSI camera stopped")

    def _cleanup_on_fail(self) -> None:
        """Internal helper to cleanup resources if start() fails."""
        if self.picam2 is not None:
            try:
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None