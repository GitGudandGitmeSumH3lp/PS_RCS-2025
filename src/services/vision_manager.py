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
    the latest frame is always available. It provides a specialized MJPEG stream
    generation method optimized for low-bandwidth scenarios by resizing frames
    and throttling the frame rate.

    Attributes:
        stream (Optional[cv2.VideoCapture]): The OpenCV video capture object.
        frame_lock (threading.Lock): Mutex to ensure thread-safe access to frames.
        current_frame (Optional[np.ndarray]): The most recently captured frame.
        stopped (bool): Flag to signal the capture thread to terminate.
        camera_index (Optional[int]): The index of the currently active camera.
        capture_thread (Optional[threading.Thread]): The background capture thread.
    """

    def __init__(self) -> None:
        """Initialize the VisionManager state."""
        self.stream: Optional[cv2.VideoCapture] = None
        self.frame_lock = threading.Lock()
        self.current_frame: Optional[np.ndarray] = None
        self.stopped = False
        self.camera_index: Optional[int] = None
        self.capture_thread: Optional[threading.Thread] = None

    def start_capture(self, width: int = 640, height: int = 480, fps: int = 30) -> bool:
        """Initialize camera hardware and start the capture thread.

        Scans camera indices 0 through 9 to find an available device. Configures
        the hardware with the requested parameters and launches a daemon thread
        to maintain the frame buffer.

        Args:
            width: Desired capture width in pixels. Must be positive.
            height: Desired capture height in pixels. Must be positive.
            fps: Desired capture framerate. Must be positive.

        Returns:
            True if a camera was found and the thread started, False otherwise.

        Raises:
            ValueError: If width, height, or fps are not positive.
            RuntimeError: If capture is already running.
        """
        if width <= 0 or width > 1920 or height <= 0 or height > 1080 or fps <= 0 or fps > 60:
            raise ValueError("Invalid camera parameters: width, height, fps must be positive")

        if self.capture_thread is not None and self.capture_thread.is_alive():
            raise RuntimeError("Capture already started. Call stop_capture() first.")

        for index in range(10):
            try:
                # Use default backend - DO NOT FORCE V4L2
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
        """Retrieve a copy of the latest captured frame.

        Returns:
            A copy of the current numpy array frame, or None if no frame
            has been captured yet.
        """
        with self.frame_lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()

    def generate_mjpeg(self, quality: int = 40) -> Generator[bytes, None, None]:
        """Generate an optimized MJPEG stream for HTTP transmission.

        This method implements Dual-Tier logic for performance:
        1. Resizes high-res source frames to 320x240 for low bandwidth usage.
        2. Throttles transmission to ~15 FPS (0.066s sleep) to reduce CPU load.
        
        Includes correct Content-Length headers for client compatibility.

        Args:
            quality: JPEG compression quality (1-100). Defaults to 40.

        Returns:
            A generator yielding multipart/x-mixed-replace byte chunks.

        Raises:
            ValueError: If quality is not between 1 and 100.
        """
        if quality < 1 or quality > 100:
            raise ValueError("JPEG quality must be between 1 and 100")

        while True:
            frame = self.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            try:
                # Optimization: Resize to 320x240 for Web UI performance
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

            # Optimization: Throttle to ~15 FPS
            time.sleep(0.066)

    def stop_capture(self) -> None:
        """Stop the background capture thread and release hardware resources."""
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
        """Internal background loop for fetching frames from the camera."""
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
                    break
            time.sleep(0.001)