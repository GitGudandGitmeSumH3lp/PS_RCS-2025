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
                logger.error(f"CSI initialization failed (Unexpected): {e}")
                self._cleanup_on_fail()
                return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.is_running or self.picam2 is None:
            return False, None

        try:
            frame = self.picam2.capture_array("lores")
            
            logger.debug(f"CSI frame captured: shape={frame.shape}, dtype={frame.dtype}, channels={frame.shape[2] if frame.ndim == 3 else 1}")
            
            if frame.ndim == 3:
                channels = frame.shape[2]
                if channels == 4:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                    logger.debug("Converted RGBA (4-channel) to BGR")
                elif channels == 3:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    logger.debug("Converted RGB (3-channel) to BGR")
                else:
                    logger.warning(f"Unexpected number of channels: {channels}. Converting as grayscale.")
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            else:
                logger.debug(f"Grayscale frame (2D array). Converting to BGR.")
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