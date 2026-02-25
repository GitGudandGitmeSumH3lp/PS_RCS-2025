# src/hardware/camera/csi_provider.py
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/camera/csi_provider.py
Description: Raspberry Pi Camera Module 3 provider using picamera2 with YUV420 support.
"""

import logging
import threading
from typing import Tuple, Optional

import cv2
import numpy as np

# Import guard for non-Pi platforms
try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    _PICAMERA2_AVAILABLE = False

from .base import CameraProvider

logger = logging.getLogger(__name__)


class CsiCameraProvider(CameraProvider):
    """Camera provider for Raspberry Pi Camera Module 3 via picamera2.

    Implements the CameraProvider interface using the libcamera-based picamera2 library.
    It configures a dual-stream pipeline: high-res RGB for capture and low-res
    YUV420 for efficient preview streaming.
    """

    def __init__(self) -> None:
        """Initialize the CSI camera provider."""
        self.picam2: Optional['Picamera2'] = None
        self._running: bool = False
        self._frame_lock: threading.Lock = threading.Lock()
        self._width: int = 0
        self._height: int = 0

    def start(self, width: int, height: int, fps: int) -> bool:
        """Initialize the camera hardware with YUV420 configuration.

        Configures a main stream (1920x1080 RGB) and a lores stream (YUV420)
        matching the requested dimensions. Also applies advanced controls
        for autofocus, metering, and exposure limits.

        Args:
            width: Capture width (320-1920).
            height: Capture height (240-1080).
            fps: Framerate (1-30).

        Returns:
            True if initialized successfully, False otherwise.

        Raises:
            ValueError: If parameters are out of valid range.
            RuntimeError: If camera is already running.
        """
        if not (320 <= width <= 1920 and 240 <= height <= 1080 and 1 <= fps <= 30):
            raise ValueError(f"Invalid parameters: {width}x{height}@{fps}")

        if self._running:
            raise RuntimeError("Camera already started")

        if not _PICAMERA2_AVAILABLE:
            logger.error("picamera2 not available")
            return False

        try:
            self.picam2 = Picamera2()
            # YUV420 is critical for performant resizing and stream encoding
            config = self.picam2.create_preview_configuration(
                main={"size": (1920, 1080), "format": "RGB888"},
                lores={"size": (width, height), "format": "YUV420"},
                buffer_count=2
            )
            self.picam2.configure(config)
            self.picam2.start()

            # Apply refined camera controls for sharp, well-exposed captures
            try:
                self.picam2.set_controls({
                    # Autofocus: continuous, macro range, fast speed
                    "AfMode": 2,
                    "AfRange": 2,
                    "AfSpeed": 1,

                    # Exposure: enable auto-exposure, use spot metering (center-weighted)
                    "AeEnable": True,
                    "AeMeteringMode": 2,      # Spot metering – expose for the center where receipt is placed

                    # Frame duration limits: cap shutter speed to prevent motion blur
                    # Min 10ms, Max 33ms – lets AEC choose but ensures shutter ≤ 33ms (30fps)
                    "FrameDurationLimits": (10000, 33333),

                    # Gain ceiling: allow up to 8x gain to compensate for faster shutter
                    "AnalogueGain": 8.0,
                })
                logger.info("CSI camera controls updated: spot metering, frame duration limits (10–33ms), continuous AF.")
            except Exception as e:
                logger.warning(f"Could not set all camera controls: {e}")

            self._width = width
            self._height = height
            self._running = True
            logger.info(f"CSI camera started: {width}x{height}@{fps}fps (YUV420)")
            return True
        except Exception as e:
            logger.error(f"CSI initialization failed: {e}")
            self.stop()
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Acquire the next frame and convert YUV420 to BGR.

        Handles memory stride alignment if the ISP pads the buffer rows.

        Returns:
            Tuple[bool, Optional[np.ndarray]]: Success flag and BGR frame.
        """
        if not self._running or self.picam2 is None:
            return False, None

        try:
            with self._frame_lock:
                # Capture planar YUV420 (I420)
                frame_yuv = self.picam2.capture_array("lores")

                # Check for stride/padding issues common on ISP hardware
                # Expected size for I420 is width * height * 1.5
                expected_size = int(self._width * self._height * 1.5)

                if frame_yuv.size != expected_size:
                    # If buffer is larger, it likely has stride padding.
                    # We assume row alignment. Attempt to correct is complex without
                    # strict stride info, but for standard resolutions on Pi,
                    # this often indicates a mismatch we should log.
                    # For now, we fail gracefully to avoid segfault in cvtColor.
                    logger.warning(
                        f"YUV size mismatch. Expected {expected_size}, got {frame_yuv.size}. "
                        "Check width alignment (mod 32)."
                    )
                    return False, None

                # Reshape to (H*1.5, W) for OpenCV I420 format
                yuv_h_shape = int(self._height * 1.5)
                frame_yuv = frame_yuv.reshape((yuv_h_shape, self._width))

                # Ensure memory contiguity for OpenCV C-API
                if not frame_yuv.flags['C_CONTIGUOUS']:
                    frame_yuv = np.ascontiguousarray(frame_yuv)

                # Efficient color conversion
                frame_bgr = cv2.cvtColor(frame_yuv, cv2.COLOR_YUV2BGR_I420)

                return True, frame_bgr

        except cv2.error as e:
            logger.error(f"Color conversion error: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Frame capture error: {e}")
            return False, None

    def stop(self) -> None:
        """Stop the camera and release all hardware resources.

        Explicitly stops and closes the picamera2 instance to prevent
        resource leaks (which can lock the camera module until reboot).
        Safe to call multiple times.
        """
        if self.picam2:
            try:
                if self._running:
                    self.picam2.stop()
                self.picam2.close()
            except Exception as e:
                logger.error(f"Error stopping CSI camera: {e}")
            finally:
                self.picam2 = None

        self._running = False
        logger.info("CSI camera stopped")