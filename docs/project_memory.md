# PROJECT EPISODIC MEMORY
**Purpose:** Persistent storage of lessons and constraints.

## 🚫 LEGACY CONSTRAINTS (DO NOT BREAK)
*   **Hardware Stack:** Arduino (Motor), HuskyLens (Vision), LiDAR (Mapping), USB Camera.
*   **Communication:** Serial Ports are hardcoded (Risk: High).
*   **Frontend:** Vanilla JS + HTML Templates. (No React/Vue build step yet).
*   **Backend:** Python 3.9+ (Flask).

## 🛠️ TECHNICAL DEBT ALERT
*   **API Duplication:** `api_server.py`, `api_server2.py`, etc. must be diffed before deletion.
*   **Database:** Multiple SQLite DBs exist. Consolidate to `src/services/database/core.py`.
*   **Imports:** Moving files will break `from backend import X`. Mass search/replace required.


---
**Wisdom ID:** WM-001
**Date:** 2026-01-28
**Topic:** Raspberry Pi 4 - Hardware Driver Failures (`ioctl`)

### The Problem
- **Symptom:** The application failed to initialize the USB camera on the Raspberry Pi 4, even though `v4l2-ctl --list-devices` detected it at `/dev/video0`.
- **Error Log:** `ioctl(VIDIOC_STREAMON): Input/output error` and `cap.read()` consistently returned `False`.

### The Investigation (What Didn't Work)
- **Software Fixes:** We attempted multiple software patches, including:
    1.  Forcing the `cv2.CAP_V4L2` backend.
    2.  Implementing codec fallbacks (MJPG -> YUYV).
    3.  Adding a 2-second "warmup" sleep.
    4.  Removing all `cap.set()` configurations to emulate legacy behavior.
- **Verification:** The final `ffmpeg` test failed with the same `ioctl` error, proving the issue was outside the Python application's control.

### The Root Cause
- **Layer 1 Failure:** The issue was physical, not logical. The USB webcam was connected to a **USB 2.0 (black) port**.
- **Analysis:** The USB 2.0 port could not supply sufficient **power** or **bandwidth** for the camera's driver to successfully initiate a video stream (`VIDIOC_STREAMON`). The driver would initialize but crash upon the request for data.

### 💡 The Lesson (Mandatory Rule)
On Raspberry Pi 4, high-bandwidth peripherals like webcams **MUST** be connected to the **USB 3.0 (blue) ports**. Always debug the physical layer (power supply, USB port, cables) before assuming a complex software or driver bug, especially when `ioctl` errors appear.