# F:\PORTFOLIO\ps_rcs_project\src\hardware\camera\csi_provider.py

import logging
import threading
from typing import Tuple, Optional

import cv2
import numpy as np

from .base import CameraProvider

logger = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    _PICAMERA2_AVAILABLE = False


class CsiCameraProvider(CameraProvider):
    def __init__(self) -> None:
        self.picam2: Optional['Picamera2'] = None
        self.is_running: bool = False
        self.lock = threading.Lock()
        self._lores_format: str = 'RGB888'

    def start(self, width: int, height: int, fps: int) -> bool:
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
                
                # Create preview configuration (allows RGB for lores stream)
                config = self.picam2.create_preview_configuration(
                    main={"size": (width, height), "format": "RGB888"},
                    lores={"size": (width, height), "format": "RGB888"},
                    controls={"FrameRate": fps}
                )
                
                self.picam2.configure(config)
                self.picam2.start()
                self.is_running = True
                self._lores_format = 'RGB888'
                logger.info(f"CSI camera initialized with preview config ({width}x{height}@{fps}fps)")
                return True
                
            except RuntimeError as e:
                logger.error(f"CSI initialization failed (RuntimeError): {e}")
                self._cleanup_on_fail()
                return False
            except Exception as e:
                logger.error(f"CSI initialization failed (Unexpected): {e}")
                self._cleanup_on_fail()
                return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
            """Acquire the next frame from the CSI camera.

            Captures an array from the 'lores' stream and converts it from RGB/RGBA
            to BGR for OpenCV compatibility.

            Returns:
                Tuple[bool, Optional[np.ndarray]]: (True, BGR_frame) on success,
                (False, None) on failure.
            """
            if not self.is_running or self.picam2 is None:
                return False, None

            try:
                # Capture array is thread-safe in picamera2
                frame = self.picam2.capture_array("lores")

                # Handle RGB/RGBA formats
                if frame.ndim == 3:
                    channels = frame.shape[2]
                    if channels == 3:
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    elif channels == 4:
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                    else:
                        # Unexpected channel count, treat as grayscale
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else:
                    # 2D array (grayscale)
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                
                return True, frame_bgr
                
            except RuntimeError as e:
                logger.error(f"CSI read failed: {e}")
                return False, None
            except cv2.error as e:
                logger.error(f"CSI frame conversion error: {e}")
                return False, None
            except Exception as e:
                logger.error(f"Unexpected CSI read error: {e}")
                return False, None

    def stop(self) -> None:
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
        if self.picam2 is not None:
            try:
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None