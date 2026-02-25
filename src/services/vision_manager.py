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

logger = logging.getLogger(__name__)


class VisionManager:
    # Class-level constants for auto-capture cleanup
    _AUTO_CAPTURE_DIR: str = "data/auto_captures"
    # Keep only 10 auto-captured images (was 100)
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
        self._detector: Optional[Any] = None          # TextDetector instance (lazy)
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

        Triggers an explicit autofocus cycle on the IMX708 VCM lens before
        grabbing the 1920×1080 RGB888 main stream frame. Falls back to the
        latest low-res frame from get_frame() if picam2 is unavailable or the
        main capture fails.

        AF cycle behaviour:
        - autofocus_cycle(wait=True) blocks until the lens converges or times out
          (picamera2 default timeout ~5s).
        - If AfState reports failure (3) after the cycle, a manual fallback to
          LensPosition=4.0 (≈25 cm) is applied before capture.
        - Full metadata is logged at DEBUG level for diagnostic purposes.

        The output directory data/auto_captures/ is created if absent.
        Applies auto-cleanup: oldest files are deleted when the count exceeds
        _AUTO_CAPTURE_MAX_FILES.

        Args:
            filename: Optional override for the output filename (no path).
                Must end in '.jpg'. If None, defaults to
                'auto_YYYYMMDD_HHMMSS.jpg' using UTC time.

        Returns:
            Absolute path of the saved file as a str, or None if no frame
            was available or saving failed.

        Raises:
            ValueError: If filename is provided but does not end in '.jpg'
                or contains path separators.
        """
        # Validate filename
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

                    # Step 1: Trigger a synchronous AF cycle.
                    # autofocus_cycle(wait=True) blocks until the VCM lens converges
                    # or times out (default ~5 s). This is the most reliable way to
                    # guarantee focus lock before grabbing the still frame.
                    af_success = False
                    try:
                        af_success = picam2.autofocus_cycle(wait=True)
                        if not af_success:
                            logger.warning(
                                "AF cycle did not converge within timeout – capturing anyway"
                            )
                    except Exception as af_err:
                        logger.error(f"autofocus_cycle() raised an exception: {af_err}")

                    # Step 2: Read back full metadata for diagnostics.
                    metadata = picam2.capture_metadata()
                    logger.debug(f"Full metadata keys: {list(metadata.keys())}")
                    logger.debug(f"Full metadata: {metadata}")

                    focus_score = metadata.get('FocusScore', 'N/A')
                    af_state    = metadata.get('AfState', 'N/A')
                    lens_pos    = metadata.get('LensPosition', 'N/A')
                    exp_time    = metadata.get('ExposureTime', 'N/A')

                    logger.info(
                        f"Pre-capture: FocusScore={focus_score}, AfState={af_state}, "
                        f"LensPosition={lens_pos}, ExposureTime={exp_time}"
                    )

                    # AfState values: 0=Idle, 1=Scanning, 2=Focused, 3=Failed
                    if af_state == 3:
                        logger.warning(
                            "AF reported failure (AfState=3). "
                            "Falling back to manual focus at LensPosition=4.0 (~25 cm)."
                        )
                        try:
                            picam2.set_controls({
                                "AfMode": 0,         # Manual focus
                                "LensPosition": 4.0, # 1 / 0.25 m = 4 diopters
                            })
                            time.sleep(0.2)          # Allow VCM to reach target position
                        except Exception as mf_err:
                            logger.error(f"Manual focus fallback failed: {mf_err}")

                    elif focus_score != 'N/A' and isinstance(focus_score, (int, float)) \
                            and focus_score < 100:
                        logger.warning(
                            f"Low focus score ({focus_score}) – image may be blurry."
                        )

                    # Step 3: Capture the high-res frame from the main (RGB888) stream.
                    rgb_frame = picam2.capture_array('main')
                    # picam2 main stream is RGB; convert to BGR for OpenCV
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
        detections occur.

        Idempotent: calling while already running logs a warning and returns.

        Args:
            sensitivity: Forwarded to TextDetector.__init__. Default 0.08.
            interval: Seconds between detection samples. Min 0.5, Max 10.0.
                Default 1.0 (1 fps).
            confirm_frames: Number of consecutive positive detections required
                before triggering capture. Min 1, Max 10. Default 3.
            detection_callback: Optional callable invoked with the saved file path
                after a successful capture. Called from the detection thread.
                Must be non-blocking.

        Raises:
            ValueError: If interval or confirm_frames are out of valid range.
            RuntimeError: If capture has not been started (self.provider is None).
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
        """Stop the background auto-detection loop.

        Sets the stop flag and waits up to 5 seconds for the detection thread
        to terminate gracefully. Idempotent: safe to call when not running.
        """
        self._detection_active = False

        if self._detection_thread is not None and self._detection_thread.is_alive():
            self._detection_thread.join(timeout=5.0)
            if self._detection_thread.is_alive():
                logger.warning("Detection thread did not stop within timeout")
            self._detection_thread = None

        logger.info("Auto-detection stopped")

    def get_latest_auto_capture(self) -> Optional[str]:
        """Return the filename of the most recently saved auto-capture.

        Returns:
            Base filename (no path) of the newest .jpg in auto_captures/,
            or None if the directory is empty or does not exist.
        """
        captures_dir = Path(self._AUTO_CAPTURE_DIR)
        if not captures_dir.exists():
            return None
        files = list(captures_dir.glob('*.jpg'))
        if not files:
            return None
        latest = max(files, key=lambda p: p.stat().st_mtime)
        return latest.name

    # ================== PRIVATE HELPERS ==================

    def _detection_loop(self) -> None:
        """Background detection sampling loop. NOT part of public interface."""
        consecutive = 0
        while self._detection_active and not self.stopped:
            time.sleep(self._detection_interval)

            frame = self.get_frame()
            if frame is None:
                continue

            # Downscale to 320×240 for detector (fast, sufficient for text presence)
            small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)

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