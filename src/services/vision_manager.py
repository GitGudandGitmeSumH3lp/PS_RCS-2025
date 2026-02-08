"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/services/vision_manager.py
Description: Vision service manager with Camera HAL integration.
"""

import logging
import threading
import time
from typing import Optional, Generator, Any

import cv2
import numpy as np

from src.hardware.camera import get_camera_provider, CameraProvider

logger = logging.getLogger(__name__)


class VisionManager:
    """Manages camera hardware interaction via HAL and provides frame access.
    
    Attributes:
        provider (Optional[CameraProvider]): Active camera provider.
        frame_lock (threading.Lock): Mutex for thread-safe frame access.
        current_frame (Optional[np.ndarray]): Latest captured frame.
        stopped (bool): Flag indicating if capture loop should terminate.
        capture_thread (Optional[threading.Thread]): Background capture thread.
    """

    def __init__(self) -> None:
        """Initialize the VisionManager state."""
        self.provider: Optional[CameraProvider] = None
        self.frame_lock = threading.Lock()
        self.current_frame: Optional[np.ndarray] = None
        self.stopped = False
        self.capture_thread: Optional[threading.Thread] = None

    @property
    def stream(self) -> Any:
        """Backward compatibility property for API server checks.
        
        Returns:
            The provider if running (truthy), else None.
        """
        if self.provider and getattr(self.provider, 'is_running', False):
            return self.provider
        return None

    @property
    def camera_index(self) -> int:
        """Backward compatibility property for camera index.
        
        Returns:
            0 (default) if index not available on provider.
        """
        return getattr(self.provider, 'camera_index', 0)

    def start_capture(self, width: int = 640, height: int = 480, fps: int = 30) -> bool:
        """Initialize camera hardware via HAL factory.

        Args:
            width: Capture width (1-3840).
            height: Capture height (1-2160).
            fps: Capture framerate (1-120).

        Returns:
            True if initialized successfully, False otherwise.

        Raises:
            ValueError: If parameters are invalid.
            RuntimeError: If capture is already running.
        """
        if width <= 0 or width > 1920 or height <= 0 or height > 1080 or fps <= 0 or fps > 60:
            raise ValueError("Invalid camera parameters: width, height, fps must be positive")

        if self.capture_thread is not None and self.capture_thread.is_alive():
            raise RuntimeError("Capture already started. Call stop_capture() first.")

        try:
            self.provider = get_camera_provider()
            if not self.provider.start(width, height, fps):
                logger.error("Camera provider initialization failed")
                return False
        except Exception as e:
            logger.error(f"Failed to get camera provider: {e}")
            return False

        self.stopped = False
        self.current_frame = None
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )
        self.capture_thread.start()
        logger.info(f"Camera initialized via HAL ({width}x{height}@{fps}fps)")
        return True

    def get_frame(self) -> Optional[np.ndarray]:
        """Retrieve the latest captured frame.

        Returns:
            A copy of the current frame or None if unavailable.
        """
        with self.frame_lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()

    def generate_mjpeg(self, quality: int = 40) -> Generator[bytes, None, None]:
        """Generate MJPEG stream for HTTP response.

        Args:
            quality: JPEG quality (1-100).

        Yields:
            Multipart MJPEG bytes.
        """
        if quality < 1 or quality > 100:
            raise ValueError("JPEG quality must be between 1 and 100")

        while True:
            frame = self.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            try:
                resized = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)
                ret, jpeg = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if ret:
                    jpeg_bytes = jpeg.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(jpeg_bytes)).encode() + b'\r\n'
                           b'\r\n' + jpeg_bytes + b'\r\n')
            except Exception:
                pass

            time.sleep(0.066)

    def stop_capture(self) -> None:
        """Stop camera capture and release resources."""
        if self.stopped:
            return

        self.stopped = True

        if self.capture_thread is not None:
            self.capture_thread.join(timeout=2.0)

        if self.provider is not None:
            self.provider.stop()
            self.provider = None

        with self.frame_lock:
            self.current_frame = None
        
        logger.info("VisionManager capture stopped")

    def _capture_loop(self) -> None:
        """Background loop for frame acquisition."""
        consecutive_failures = 0
        if self.provider is None:
            return

        while not self.stopped:
            ret, frame = self.provider.read()
            if ret:
                with self.frame_lock:
                    self.current_frame = frame
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures > 10:
                    logger.error("Camera disconnected (10 consecutive failures)")
                    break
            time.sleep(0.001)