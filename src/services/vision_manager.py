# src/services/vision_manager.py

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator, Any, Callable

import cv2
import numpy as np

from src.hardware.camera import get_camera_provider, CameraProvider

# Expected manual LensPosition – used only for a calibration-drift warning.
# Keep in sync with MANUAL_LENS_POSITION in csi_provider.py.
_EXPECTED_LENS_POSITION: float = 4.0
_LENS_POSITION_TOLERANCE: float = 0.5

# Sharpness threshold for detection (Laplacian variance) on 320×240 frames.
# Values below this are considered too blurry to trigger capture.
# Calibration on full-res frames gave ~83.7; downscaled will be lower.
# Set to 40 as a safe starting point.
_SHARPNESS_THRESHOLD = 40.0

# Initialize logger
logger = logging.getLogger(__name__)

# Enable DEBUG logging temporarily for sharpness monitoring
logger.setLevel(logging.DEBUG)


class VisionManager:
    # Class-level constants for auto-capture cleanup
    _AUTO_CAPTURE_DIR: str = "data/auto_captures"
    _AUTO_CAPTURE_MAX_FILES: int = 10

    def __init__(self) -> None:
        self.provider: Optional[CameraProvider] = None
        self.frame_lock = threading.Lock()
        self.current_frame: Optional[np.ndarray] = None
        self.stopped = False
        self.capture_thread: Optional[threading.Thread] = None

        # Auto-detection attributes
        self._detection_active: bool = False
        self._detection_thread: Optional[threading.Thread] = None
        self._detection_sensitivity: float = 0.08
        self._detection_interval: float = 1.0
        self._detection_confirm_frames: int = 3
        self._detection_callback: Optional[Callable[[str], None]] = None
        self._detector: Optional[Any] = None
        self._highres_lock: threading.Lock = threading.Lock()

    @property
    def stream(self) -> Any:
        if self.provider and self.capture_thread and self.capture_thread.is_alive():
            return self.provider
        return None

    @property
    def camera_index(self) -> int:
        return getattr(self.provider, 'camera_index', 0)

    def start_capture(self, width: int = 640, height: int = 480, fps: int = 30) -> bool:
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
        with self.frame_lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()

    def generate_mjpeg(self, quality: int = 40) -> Generator[bytes, None, None]:
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
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
            except Exception:
                pass

            time.sleep(0.066)

    def stop_capture(self) -> None:
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

    # ================== NEW METHODS ==================

    def capture_highres(self, filename: Optional[str] = None) -> Optional[str]:
        """Capture a high-resolution still and save to data/auto_captures/.

        Acquires a 1920×1080 RGB888 frame from the CSI camera's main stream.
        Manual focus (AfMode=0) is configured at startup, so no AF cycle is
        needed here. A short settle delay allows the frame buffer to stabilise
        before capture.

        Falls back to the latest low-res frame from get_frame() if picam2 is
        unavailable or the main capture fails.

        Applies auto-cleanup: oldest files are deleted when the directory
        exceeds _AUTO_CAPTURE_MAX_FILES entries.

        Args:
            filename: Optional override for the output filename (no path).
                Must end in '.jpg'. Defaults to 'auto_YYYYMMDD_HHMMSS.jpg'.

        Returns:
            Absolute path of the saved file as a str, or None on failure.

        Raises:
            ValueError: If filename does not end in '.jpg' or contains
                path separators.
        """
        if filename is not None:
            if not isinstance(filename, str) or not filename.endswith('.jpg'):
                raise ValueError("filename must be a '.jpg' basename")
            if '/' in filename or '\\' in filename:
                raise ValueError("filename must not contain path separators")

        with self._highres_lock:
            frame = None

            # --- High-res path: CSI camera with picam2 ---
            if hasattr(self.provider, 'picam2') and self.provider.picam2 is not None:
                try:
                    picam2 = self.provider.picam2

                    # Manual focus is pre-configured at startup (AfMode=0,
                    # LensPosition=MANUAL_LENS_POSITION). No AF cycle is needed.
                    # A short delay lets the frame buffer settle after any prior
                    # activity before we grab the still.
                    time.sleep(0.1)

                    # Log metadata for diagnostics and calibration verification
                    metadata = picam2.capture_metadata()
                    logger.debug(f"Full metadata keys: {list(metadata.keys())}")
                    logger.debug(f"Full metadata: {metadata}")

                    lens_pos    = metadata.get('LensPosition', 'N/A')
                    exp_time    = metadata.get('ExposureTime', 'N/A')
                    logger.info(f"Pre-capture: LensPosition={lens_pos}, ExposureTime={exp_time}")

                    # Warn if the actual lens position has drifted from the
                    # expected value – indicates a misconfiguration or HW issue.
                    if (lens_pos != 'N/A'
                            and isinstance(lens_pos, (int, float))
                            and abs(lens_pos - _EXPECTED_LENS_POSITION) > _LENS_POSITION_TOLERANCE):
                        logger.warning(
                            f"LensPosition {lens_pos:.1f} differs from expected "
                            f"{_EXPECTED_LENS_POSITION} by more than "
                            f"{_LENS_POSITION_TOLERANCE}. "
                            "Update MANUAL_LENS_POSITION in csi_provider.py or run "
                            "scripts/calibrate_focus.py."
                        )

                    # Capture the high-res frame from the main (RGB888) stream
                    rgb_frame = picam2.capture_array('main')
                    frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
                    logger.debug("High-res capture from picam2.main succeeded")

                except Exception as e:
                    logger.warning(f"High-res capture failed, falling back to lores: {e}")

            # --- Fallback: latest low-res frame ---
            if frame is None:
                frame = self.get_frame()
                if frame is not None:
                    logger.debug("Using fallback low-res frame for capture")

            if frame is None:
                return None

            # --- Persist to disk ---
            captures_dir = Path(self._AUTO_CAPTURE_DIR)
            captures_dir.mkdir(parents=True, exist_ok=True)

            if filename is None:
                ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = f"auto_{ts}.jpg"

            save_path = captures_dir / filename

            success = cv2.imwrite(str(save_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not success:
                logger.error(f"Failed to write image to {save_path}")
                return None

            self._cleanup_auto_captures()
            return str(save_path.resolve())

    def start_auto_detection(
        self,
        sensitivity: float = 0.08,
        interval: float = 1.0,
        confirm_frames: int = 3,
        detection_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """Start the background auto-detection loop.

        Spawns a daemon thread (_detection_loop) that samples self.current_frame
        at the specified interval, passes a downscaled copy to TextDetector.detect(),
        and triggers capture_highres() when confirm_frames consecutive positive
        detections occur. Idempotent.

        Args:
            sensitivity: Forwarded to TextDetector.__init__. Default 0.08.
            interval: Seconds between detection samples (0.5–10.0). Default 1.0.
            confirm_frames: Consecutive positive detections required (1–10). Default 3.
            detection_callback: Optional non-blocking callable invoked with the
                saved file path after a successful capture.

        Raises:
            ValueError: If interval or confirm_frames are out of valid range.
            RuntimeError: If capture has not been started.
        """
        if not (0.5 <= interval <= 10.0):
            raise ValueError("interval must be between 0.5 and 10.0 seconds")
        if not (1 <= confirm_frames <= 10):
            raise ValueError("confirm_frames must be between 1 and 10")
        if self.provider is None:
            raise RuntimeError(
                "Camera not started. Call start_capture() before start_auto_detection()."
            )

        if self._detection_thread is not None and self._detection_thread.is_alive():
            logger.warning("Auto-detection already running")
            return

        self._detection_sensitivity = sensitivity
        self._detection_interval = interval
        self._detection_confirm_frames = confirm_frames
        self._detection_callback = detection_callback

        from src.services.text_detector import TextDetector
        self._detector = TextDetector(sensitivity=sensitivity)

        self._detection_active = True
        self._detection_thread = threading.Thread(
            target=self._detection_loop,
            daemon=True
        )
        self._detection_thread.start()
        logger.info(f"Auto-detection started (interval={interval}s, confirm={confirm_frames})")

    def stop_auto_detection(self) -> None:
        """Stop the background auto-detection loop. Idempotent."""
        self._detection_active = False

        if self._detection_thread is not None and self._detection_thread.is_alive():
            self._detection_thread.join(timeout=5.0)
            if self._detection_thread.is_alive():
                logger.warning("Detection thread did not stop within timeout")
            self._detection_thread = None

        logger.info("Auto-detection stopped")

    def get_latest_auto_capture(self) -> Optional[str]:
        """Return the base filename of the most recently saved auto-capture.

        Returns:
            Base filename (no path) of the newest .jpg, or None if none exist.
        """
        captures_dir = Path(self._AUTO_CAPTURE_DIR)
        if not captures_dir.exists():
            return None
        files = list(captures_dir.glob('*.jpg'))
        if not files:
            return None
        return max(files, key=lambda p: p.stat().st_mtime).name

    def set_lens_position(self, lens_position: float) -> bool:
        """Set the camera lens position for manual focus adjustment.

        Applies a new LensPosition control to the running picamera2 instance
        without restarting the camera. Allows live focus tuning while the
        MJPEG stream and auto-detection remain active.

        Valid range: 0.0 (infinity) to 10.0 (~10 cm).
        Distance formula: distance_cm ≈ 100 / lens_position

        Common values:
            1.5 → ~67 cm    2.0 → ~50 cm    2.5 → ~40 cm
            3.0 → ~33 cm    3.5 → ~29 cm    4.0 → ~25 cm

        Args:
            lens_position: Diopter value (0.0–10.0).

        Returns:
            True if the control was applied successfully, False otherwise.

        Raises:
            ValueError: If lens_position is outside the 0.0–10.0 range.
        """
        if not (0.0 <= lens_position <= 10.0):
            raise ValueError(
                f"lens_position {lens_position} out of range [0.0, 10.0]"
            )

        if not hasattr(self.provider, 'picam2') or self.provider.picam2 is None:
            logger.warning("set_lens_position: CSI camera not available")
            return False

        try:
            self.provider.picam2.set_controls({
                "AfMode": 0,                   # Ensure manual mode stays active
                "LensPosition": lens_position,
            })
            logger.info(
                f"LensPosition set to {lens_position:.1f} "
                f"(~{100 / lens_position:.0f} cm)" if lens_position > 0
                else f"LensPosition set to 0.0 (infinity)"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set LensPosition: {e}")
            return False

    # ================== PRIVATE HELPERS ==================

    def _detection_loop(self) -> None:
        """Background detection sampling loop. NOT part of public interface."""
        consecutive = 0
        while self._detection_active and not self.stopped:
            time.sleep(self._detection_interval)

            frame = self.get_frame()
            if frame is None:
                continue

            # Downscale to 320×240 for detector
            small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)

            # Compute sharpness using Laplacian variance
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            if sharpness < _SHARPNESS_THRESHOLD:
                # Frame too blurry – reset consecutive counter and skip detection
                consecutive = 0
                logger.debug(f"Frame too blurry (sharpness={sharpness:.1f} < {_SHARPNESS_THRESHOLD})")
                continue

            try:
                detected, _ = self._detector.detect(small)
            except Exception as e:
                logger.error(f"Detection error: {e}")
                continue

            consecutive = consecutive + 1 if detected else 0

            if consecutive >= self._detection_confirm_frames:
                consecutive = 0
                path = self.capture_highres()
                if path is not None:
                    logger.info(f"Auto-capture saved: {path}")
                    if self._detection_callback is not None:
                        try:
                            self._detection_callback(path)
                        except Exception as e:
                            logger.error(f"Detection callback failed: {e}")

    def _cleanup_auto_captures(self) -> None:
        """Delete oldest files when auto_captures/ exceeds _AUTO_CAPTURE_MAX_FILES."""
        captures_dir = Path(self._AUTO_CAPTURE_DIR)
        if not captures_dir.exists():
            return

        files = sorted(
            captures_dir.glob('*.jpg'),
            key=lambda p: p.stat().st_mtime
        )

        while len(files) > self._AUTO_CAPTURE_MAX_FILES:
            oldest = files.pop(0)
            try:
                oldest.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete old capture {oldest}: {e}")

    def _capture_loop(self) -> None:
        """Continuous low-res frame acquisition loop. NOT part of public interface."""
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