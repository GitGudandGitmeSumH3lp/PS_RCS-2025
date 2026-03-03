#!/usr/bin/env python3
"""
Quick hardware test for Raspberry Pi Camera Module 3 using picamera2.
Run with: python3 test_camera_pi.py
"""

import cv2
import numpy as np
import time
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    logger.info("picamera2 imported successfully")
except ImportError:
    logger.error("picamera2 not installed. Run: pip install picamera2")
    sys.exit(1)

def test_camera():
    """Initialize camera, capture a frame, save it."""
    try:
        picam2 = Picamera2()
        logger.info("Picamera2 object created")

        # Create a preview configuration with a single stream (RGB)
        config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
        picam2.configure(config)
        logger.info("Camera configured")

        picam2.start()
        logger.info("Camera started")

        # Allow auto‑exposure to settle
        time.sleep(2)

        # Capture a frame
        frame = picam2.capture_array("main")
        logger.info(f"Frame captured, shape: {frame.shape}, dtype: {frame.dtype}")

        # Convert RGB to BGR for OpenCV saving
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Save to file
        filename = "test_capture.jpg"
        cv2.imwrite(filename, frame_bgr)
        logger.info(f"Test image saved as {filename}")

        picam2.stop()
        picam2.close()
        logger.info("Camera stopped and closed")

        return True

    except Exception as e:
        logger.error(f"Camera test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_camera()
    if success:
        print("\n✅ Camera test PASSED – hardware and picamera2 are working.")
    else:
        print("\n❌ Camera test FAILED – check hardware connections and picamera2 installation.")