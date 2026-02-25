# src/hardware/camera/csi_provider.py
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/camera/csi_provider.py
Description: Raspberry Pi Camera Module 3 provider using picamera2 with YUV420 support.

FOCUS CALIBRATION
-----------------
This module uses manual focus (AfMode=0) with a fixed LensPosition tuned for the
typical working distance (~33 cm). LensPosition is measured in diopters:
    distance_cm ≈ 100 / LensPosition
    LensPosition 3.0 → ~33 cm
    LensPosition 2.5 → ~40 cm
    LensPosition 2.0 → ~50 cm

To find the optimal value for your setup, run:
    python scripts/calibrate_focus.py
Then update MANUAL_LENS_POSITION below with the sharpest result.
"""

import logging
import threading
from typing import Tuple, Optional

import cv2
import numpy as np

# Import guard for non-Pi platforms
try:
    import picamera2 as _picamera2_module
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    _PICAMERA2_AVAILABLE = False

from .base import CameraProvider

logger = logging.getLogger(__name__)

# ── Tunable constant ──────────────────────────────────────────────────────────
# Adjust this value if images are still blurry after deployment.
# Run scripts/calibrate_focus.py to sweep LensPosition values and pick the best.
MANUAL_LENS_POSITION: float = 3.0   # diopters → ~33 cm working distance
# ─────────────────────────────────────────────────────────────────────────────


class CsiCameraProvider(CameraProvider):
    """Camera provider for Raspberry Pi Camera Module 3 via picamera2.

    Implements the CameraProvider interface using the libcamera-based picamera2
    library. Configures a dual-stream pipeline: high-res RGB888 (1920×1080) for
    still capture and low-res YUV420 for efficient preview streaming.

    Focus strategy: manual fixed focus (AfMode=0) at MANUAL_LENS_POSITION diopters.
    Continuous AF is not used because the contrast-detection algorithm tends to
    lock onto near foreground edges (e.g. the label border or user's hand) rather
    than the flat receipt surface at ~30–40 cm.

    Attributes:
        picam2 (Optional[Picamera2]): The hardware interface instance.
        _running (bool): Internal running state flag.
        _frame_lock (threading.Lock): Mutex for thread-safe frame access.
        _width (int): Configured lores capture width.
        _height (int): Configured lores capture height.
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

        Configures a main stream (1920×1080 RGB888) for high-res capture and a
        lores stream (YUV420) at the requested dimensions for preview. All camera
        controls are baked into the configuration object before start() to ensure
        they apply from the very first frame.

        Focus is set to manual (AfMode=0) at MANUAL_LENS_POSITION diopters to
        prevent the contrast-AF algorithm from locking onto near foreground objects.

        Args:
            width: Lores capture width (320–1920).
            height: Lores capture height (240–1080).
            fps: Framerate (1–30).

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
            logger.info(f"picamera2 version: {_picamera2_module.__version__}")
        except AttributeError:
            logger.warning("Could not determine picamera2 version")

        try:
            self.picam2 = Picamera2()

            # All controls are passed via create_preview_configuration() so they
            # are applied before the ISP processes the first frame.
            config = self.picam2.create_preview_configuration(
                main={"size": (1920, 1080), "format": "RGB888"},
                lores={"size": (width, height), "format": "YUV420"},
                buffer_count=2,
                controls={
                    # ── Focus: manual, fixed lens position ────────────────────
                    # AfMode=0 disables the contrast-AF algorithm entirely.
                    # LensPosition sets the VCM to a fixed focal distance.
                    # Rationale: continuous AF (AfMode=2) locks onto near edges;
                    # manual focus eliminates hunting and gives consistent results.
                    "AfMode": 0,
                    "LensPosition": MANUAL_LENS_POSITION,

                    # ── Exposure ──────────────────────────────────────────────
                    # AeMeteringMode=2 (spot): exposes for the frame centre where
                    # the receipt is placed, ignoring bright background sources.
                    "AeEnable": True,
                    "AeMeteringMode": 2,

                    # FrameDurationLimits: cap shutter to 10–33 ms to prevent
                    # motion blur while letting AEC choose within that window.
                    "FrameDurationLimits": (10000, 33333),

                    # AnalogueGain: allow up to 8× gain to compensate for the
                    # faster shutter in typical indoor environments.
                    "AnalogueGain": 8.0,
                }
            )
            self.picam2.configure(config)
            self.picam2.start()

            self._width = width
            self._height = height
            self._running = True
            logger.info(
                f"CSI camera started: {width}x{height}@{fps}fps (YUV420). "
                f"Manual focus: LensPosition={MANUAL_LENS_POSITION} "
                f"(~{100 / MANUAL_LENS_POSITION:.0f} cm). "
                "Spot metering, frame duration 10–33 ms, gain ≤8×."
            )
            return True

        except Exception as e:
            logger.error(f"CSI initialization failed: {e}")
            self.stop()
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Acquire the next frame and convert YUV420 to BGR.

        Captures a planar YUV420 (I420) frame from the lores stream and converts
        it to BGR for OpenCV compatibility. Handles ISP stride-padding gracefully.

        Returns:
            Tuple[bool, Optional[np.ndarray]]: Success flag and BGR frame (H×W×3,
            uint8), or (False, None) on any error.
        """
        if not self._running or self.picam2 is None:
            return False, None

        try:
            with self._frame_lock:
                frame_yuv = self.picam2.capture_array("lores")

                expected_size = int(self._width * self._height * 1.5)
                if frame_yuv.size != expected_size:
                    logger.warning(
                        f"YUV size mismatch. Expected {expected_size}, got {frame_yuv.size}. "
                        "Check width alignment (mod 32)."
                    )
                    return False, None

                yuv_h_shape = int(self._height * 1.5)
                frame_yuv = frame_yuv.reshape((yuv_h_shape, self._width))

                if not frame_yuv.flags['C_CONTIGUOUS']:
                    frame_yuv = np.ascontiguousarray(frame_yuv)

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

        Explicitly stops and closes the picamera2 instance to prevent resource
        leaks that can lock the camera module until reboot. Idempotent.
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