# src/services/vision_manager.py

import threading
import time
from typing import Optional, Generator

import cv2
import numpy as np


class VisionManager:
    def __init__(self) -> None:
        self.stream: Optional[cv2.VideoCapture] = None
        self.frame_lock = threading.Lock()
        self.current_frame: Optional[np.ndarray] = None
        self.stopped = False
        self.camera_index: Optional[int] = None
        self.capture_thread: Optional[threading.Thread] = None

    def start_capture(self, width: int = 640, height: int = 480, fps: int = 30) -> bool:
        """Initialize camera hardware and start the capture thread.
        
        Implements proven architecture from working version:
        1. Prioritizes index 0 (USB webcam standard)
        2. Sets resolution BEFORE first read (USB handshake)
        3. Uses MJPG format for USB compatibility
        4. Double-read pattern to complete negotiation
        
        Args:
            width: Desired capture width in pixels.
            height: Desired capture height in pixels.
            fps: Desired capture framerate.
        
        Returns:
            True if camera initialized successfully, False otherwise.
        """
        if width <= 0 or width > 1920 or height <= 0 or height > 1080 or fps <= 0 or fps > 60:
            raise ValueError("Invalid camera parameters")

        if self.capture_thread is not None and self.capture_thread.is_alive():
            raise RuntimeError("Capture already started. Call stop_capture() first.")

        # ✅ FIX 1: Try index 0 FIRST (USB webcam standard)
        try:
            # Use V4L2 backend for Pi compatibility
            cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            
            if cap.isOpened():
                # ✅ FIX 2: Set MJPG format BEFORE resolution (USB requirement)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
                
                # ✅ FIX 3: Set resolution BEFORE first read (USB handshake)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap.set(cv2.CAP_PROP_FPS, fps)
                
                # ✅ FIX 4: Double-read pattern (complete USB negotiation)
                ret, _ = cap.read()  # First read (may fail during handshake)
                ret, _ = cap.read()  # Second read (should succeed)
                
                if ret:
                    # Initialize capture thread
                    self.stream = cap
                    self.camera_index = 0
                    self.stopped = False
                    self.current_frame = None
                    
                    self.capture_thread = threading.Thread(
                        target=self._capture_loop,
                        daemon=True
                    )
                    self.capture_thread.start()
                    
                    print(f"[Vision] Camera started on index 0 (MJPG {width}x{height})")
                    return True
                
                cap.release()
                print("[Vision] Index 0 opened but frame read failed")
        except Exception as e:
            print(f"[Vision] Index 0 failed: {e}")

        # Fallback: Scan indices 1-9 (other USB devices)
        for index in range(1, 10):
            try:
                cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
                
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    cap.set(cv2.CAP_PROP_FPS, fps)
                    
                    ret, _ = cap.read()
                    ret, _ = cap.read()
                    
                    if ret:
                        self.stream = cap
                        self.camera_index = index
                        self.stopped = False
                        self.current_frame = None
                        
                        self.capture_thread = threading.Thread(
                            target=self._capture_loop,
                            daemon=True
                        )
                        self.capture_thread.start()
                        
                        print(f"[Vision] Camera started on index {index} (MJPG)")
                        return True
                    
                    cap.release()
            except Exception:
                continue

        print("[Vision] No working camera found")
        return False


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
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(jpeg_bytes)).encode() + b'\r\n'
                           b'\r\n' + jpeg_bytes + b'\r\n')
            except Exception:
                pass

            time.sleep(0.066)

    def stop_capture(self) -> None:
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