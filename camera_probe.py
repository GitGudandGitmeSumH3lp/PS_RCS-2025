"""
FILE: camera_probe.py
PURPOSE: Interrogate USB Camera capabilities via OpenCV and V4L2.
"""
import cv2
import subprocess
import os

def check_v4l2_capabilities():
    """Checks Linux V4L2 controls if available (Raspberry Pi/Linux specific)."""
    print("\n---  LINUX V4L2 DIAGNOSTIC ---")
    try:
        # Check available devices
        result = subprocess.run(['v4l2-ctl', '--list-devices'], capture_output=True, text=True)
        print(f"DEVICES:\n{result.stdout}")

        # Check controls for video0 (usually the webcam)
        result = subprocess.run(['v4l2-ctl', '-d', '/dev/video0', '--list-ctrls'], capture_output=True, text=True)
        output = result.stdout
        print(f"CONTROLS (video0):\n{output}")
        
        if "focus_auto" in output:
            print(" HARDWARE SUPPORT: 'focus_auto' detected!")
        elif "focus_absolute" in output:
            print(" HARDWARE NOTE: 'focus_absolute' detected (Manual Focus Control possible).")
        else:
            print(" HARDWARE RESULT: No focus controls detected via driver.")
            
    except FileNotFoundError:
        print("Note: 'v4l2-ctl' not found (Not Linux or not installed). Skipping system-level check.")

def check_opencv_capabilities():
    """Checks what OpenCV can see and set."""
    print("\n---  OPENCV DIAGNOSTIC ---")
    
    # Try indices 0 to 4
    for index in range(5):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            print(f"\n[CAMERA INDEX {index}] CONNECTED")
            
            # 1. READ Current Values
            focus_val = cap.get(cv2.CAP_PROP_FOCUS)
            autofocus_val = cap.get(cv2.CAP_PROP_AUTOFOCUS)
            print(f"  > Current Focus Value: {focus_val}")
            print(f"  > Current Autofocus State: {autofocus_val}")
            
            # 2. TEST Autofocus Toggle
            print("  > Testing Autofocus Toggle...")
            if cap.set(cv2.CAP_PROP_AUTOFOCUS, 1):
                print("    - Command SENT: Enable Autofocus (Success return)")
                # Verify if it stuck
                new_val = cap.get(cv2.CAP_PROP_AUTOFOCUS)
                print(f"    - Verification Read: {new_val}")
            else:
                print("    - Command FAILED: Driver rejected Autofocus enable.")

            cap.release()
        else:
            pass

if __name__ == "__main__":
    print(" STARTING CAMERA PROBE...")
    check_v4l2_capabilities()
    check_opencv_capabilities()
    print("\nDONE.")