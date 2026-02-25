#!/usr/bin/env python3
"""
scripts/calibrate_focus.py
PS_RCS_PROJECT – one-time focus calibration for the IMX708 camera.

Usage:
    python scripts/calibrate_focus.py [--start 1.5] [--end 5.0] [--step 0.5]

This script sweeps LensPosition values across the specified range, captures a
1920×1080 still at each position, and saves the images to /tmp/focus_sweep/.

After running, SCP the images to your workstation and pick the sharpest one:
    scp sorter@<pi-ip>:/tmp/focus_sweep/*.jpg ./focus_sweep/

Then update MANUAL_LENS_POSITION in src/hardware/camera/csi_provider.py with
the value from the sharpest filename (e.g. focus_3.0.jpg → LensPosition=3.0).

Distance reference:
    LensPosition 1.5 → ~67 cm
    LensPosition 2.0 → ~50 cm
    LensPosition 2.5 → ~40 cm
    LensPosition 3.0 → ~33 cm  ← default
    LensPosition 3.5 → ~29 cm
    LensPosition 4.0 → ~25 cm
    LensPosition 5.0 → ~20 cm
"""

import argparse
import sys
import time
from pathlib import Path

try:
    import cv2
    import numpy as np
    from picamera2 import Picamera2
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Run on the Raspberry Pi inside the project venv.")
    sys.exit(1)

OUTPUT_DIR = Path("/tmp/focus_sweep")


def compute_sharpness(image_bgr: np.ndarray) -> float:
    """Compute a sharpness score using the Laplacian variance method."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def main() -> None:
    parser = argparse.ArgumentParser(description="IMX708 focus calibration sweep")
    parser.add_argument("--start", type=float, default=1.5, help="Start LensPosition (default 1.5)")
    parser.add_argument("--end",   type=float, default=5.0, help="End LensPosition (default 5.0)")
    parser.add_argument("--step",  type=float, default=0.5, help="Step size (default 0.5)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    positions = []
    pos = args.start
    while pos <= args.end + 1e-6:
        positions.append(round(pos, 2))
        pos += args.step

    print(f"[INFO] Sweeping LensPosition: {positions}")
    print(f"[INFO] Output: {OUTPUT_DIR}")

    cam = Picamera2()
    config = cam.create_preview_configuration(
        main={"size": (1920, 1080), "format": "RGB888"},
        controls={
            "AfMode": 0,
            "LensPosition": positions[0],
            "AeEnable": True,
            "FrameDurationLimits": (10000, 33333),
            "AnalogueGain": 8.0,
        }
    )
    cam.configure(config)
    cam.start()
    time.sleep(1.0)  # Allow AEC to stabilise

    results = []

    for lp in positions:
        cam.set_controls({"LensPosition": lp})
        time.sleep(0.4)  # Allow VCM to settle

        frame_rgb = cam.capture_array("main")
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        score = compute_sharpness(frame_bgr)
        out_path = OUTPUT_DIR / f"focus_{lp:.1f}.jpg"
        cv2.imwrite(str(out_path), frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])

        results.append((lp, score))
        print(f"  LensPosition={lp:.1f}  sharpness={score:.1f}  → {out_path.name}")

    cam.stop()
    cam.close()

    # Report best position
    best_lp, best_score = max(results, key=lambda x: x[1])
    print(f"\n[RESULT] Best LensPosition = {best_lp:.1f}  (sharpness={best_score:.1f})")
    print(f"[ACTION] Update MANUAL_LENS_POSITION = {best_lp} in src/hardware/camera/csi_provider.py")


if __name__ == "__main__":
    main()