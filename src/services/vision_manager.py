"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/services/vision_manager.py
Description: Manages camera hardware, frame capture threading, and stream generation.
"""

import threading
import time
from typing import Optional, Generator

import cv2
import numpy as np


class VisionManager:
    """Handles video capture from hardware cameras.

    This class manages a background thread for continuous frame capture to ensure
    the latest frame is always available without blocking the main application.
    It also provides MJPEG stream generation.

    Attributes:
        stream: The cv2.VideoCapture object (None if not started).
        frame_lock: Thread lock for safe frame access.
        current_frame: The most recently captured numpy array frame.
        stopped: Boolean flag to control the capture loop.
        camera_index: The index of the active camera.
        capture_thread: The background thread object.
    """

    def __init__(self) -> None:
        """Initialize the VisionManager."""
        self.stream: Optional[cv2.VideoCapture] = None
        self.frame_lock = threading.Lock()
        self.current_frame: Optional[np.ndarray] = None
        self.stopped = False
        self.camera_index: Optional[int] = None
        self.capture_thread: Optional[threading.Thread] = None

    def start_capture(self, width: int = 640, height: int = 480, fps: int = 30) -> bool:
        """Initialize camera and start the capture thread.

        Attempts to connect to camera indices 0 through 9. Stops at the first
        successful connection.

        Args:
            width: Desired frame width. Must be positive.
            height: Desired frame height. Must be positive.
            fps: Desired frames per second. Must be positive.

        Returns:
            True if a camera was successfully opened and thread started, False otherwise.

        Raises:
            ValueError: If parameters are out of valid ranges.
            RuntimeError: If capture is already running.
        """
        if width <= 0 or width > 1920 or height <= 0 or height > 1080 or fps <= 0 or fps > 60:
            raise ValueError("Invalid camera parameters: width, height, fps must be positive")

        if self.capture_thread is not None and self.capture_thread.is_alive():
            raise RuntimeError("Capture already started. Call stop_capture() first.")

        # Iterate through common camera indices to find a working device
        for index in range(10):
            try:
                cap = cv2.VideoCapture(index)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        self.stream = cap
                        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                        self.stream.set(cv2.CAP_PROP_FPS, fps)
                        
                        self.camera_index = index
                        self.stopped = False
                        self.current_frame = None
                        
                        self.capture_thread = threading.Thread(
                            target=self._capture_loop, 
                            daemon=True
                        )
                        self.capture_thread.start()
                        return True
                    cap.release()
                else:
                    cap.release()
            except Exception:
                continue

        return False

    def get_frame(self) -> Optional[np.ndarray]:
        """Retrieve the latest captured frame.

        Returns:
            A copy of the latest numpy array frame, or None if no frame is available.
        """
        with self.frame_lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()

    def generate_mjpeg(self, quality: int = 80) -> Generator[bytes, None, None]:
        """Generate an MJPEG stream for HTTP transmission.

        Args:
            quality: JPEG compression quality (1-100).

        Returns:
            A generator yielding bytes formatted for multipart/x-mixed-replace.
        
        Raises:
            ValueError: If quality is not between 1 and 100.
        """
        if quality < 1 or quality > 100:
            raise ValueError("JPEG quality must be between 1 and 100")

        while True:
            frame = self.get_frame()
            if frame is None:
                # Small sleep to prevent busy loop if camera is initializing
                time.sleep(0.1)
                continue

            try:
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if ret:
                    jpeg_bytes = jpeg.tobytes()
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n'
            except Exception:
                pass

            time.sleep(0.033)  # Approx 30 FPS

    def stop_capture(self) -> None:
        """Stop the capture thread and release camera resources."""
        if self.stopped:
            return

        self.stopped = True

        if self.capture_thread is not None:
            self.capture_thread.join(timeout=2.0)

        if self.stream is not None:
            self.stream.release()
            self.stream = None

        with self.frame_lock:
            self.current_frame = None
        self.camera_index = None

    def _capture_loop(self) -> None:
        """Internal loop running in a separate thread to capture frames."""
        consecutive_failures = 0
        if self.stream is None:
            return

        while not self.stopped:
            ret, frame = self.stream.read()
            if ret:
                with self.frame_lock:
                    self.current_frame = frame
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures > 10:
                    # Safety break to prevent infinite looping on disconnected camera
                    break
            time.sleep(0.001)