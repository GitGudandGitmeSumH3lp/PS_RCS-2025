#!/usr/bin/env python3
"""
VCM Movement Diagnostic
Sweeps LensPosition values, triggers captures, logs FocusFoM.
"""

import requests
import time
import json

BASE_URL = "http://192.168.100.213:5000"
FOCUS_ENDPOINT = f"{BASE_URL}/api/camera/focus"
CAPTURE_ENDPOINT = f"{BASE_URL}/api/vision/capture"
# Lens positions to test (diopters)
LENS_POSITIONS = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]

def set_focus(lp):
    resp = requests.post(FOCUS_ENDPOINT, json={"lens_position": lp})
    if resp.status_code == 200:
        print(f"  Focus set to {lp} (distance {100/lp:.1f} cm)" if lp>0 else f"  Focus set to {lp} (infinity)")
        return True
    else:
        print(f"  Failed to set focus: {resp.text}")
        return False

def capture():
    resp = requests.post(CAPTURE_ENDPOINT)
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Capture triggered, file: {data.get('download_url')}")
        return True
    else:
        print(f"  Capture failed: {resp.text}")
        return False

def main():
    print("VCM Movement Diagnostic")
    print("="*40)
    for lp in LENS_POSITIONS:
        print(f"\nTesting LensPosition = {lp}")
        if not set_focus(lp):
            continue
        time.sleep(2)  # Allow lens to settle
        if not capture():
            continue
        time.sleep(1)  # Wait a bit before next
    print("\nDiagnostic complete. Check server logs for FocusFoM values.")

if __name__ == "__main__":
    main()