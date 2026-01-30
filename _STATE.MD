# 🟢 PROJECT STATE: PS_RCS_PROJECT
**ROOT:** `F:\PORTFOLIO\ps_rcs_project`
**Phase:** 3.5 - UI Pivot (Service Dashboard)
**Last Updated:** 2026-01-23
**Architecture:** Flask + SQLite + HardwareManager (Thread-Safe)

## 🎯 IMMEDIATE GOAL
Refactor Frontend from "Cyberpunk" to "Minimalist Industrial" (Service Dashboard).
*Paused:* Lidar/Camera Backend Integration:
Integrate isolated legacy visualizers (Lidar, Camera, OCR) into the new unified Backend API.

## 📋 ACTIVE TASK LIST
### ⏳ In Progress (UI Pivot)
- [ ] **UI Restoration:** Debugging missing "Scan" and "Control" buttons in the Dashboard.
- [ ] **State Sync:** Ensure JS `VisionPanel` is correctly initialized in the browser.
- [ ] **Implementer:** Add state persistence (localStorage) for theme preference.
- [ ] **Cleanup:** Delete Cyberpunk assets.
- [ ] **Live Testing:** Verify OCR accuracy with physical Flash Express labels.

### ✅ Completed (Phase 1 & 2)
- [x] **Backend Core:** Refactored `main.py` to use `HardwareManager` and `RobotState`.
- [x] **Database:** Standardized `database.py` with thread-safe connection pooling.
- [x] **Frontend:** Created Neural Interface (dark mode) with real-time API polling.
- [x] **Motor Control:** Wrapped legacy `motor_controller.py` in `LegacyMotorAdapter`.
- [x] **Constraint Update:** Amended `docs/system_constraints.md` to Minimalist/Industrial.
- [x] **Architect:** Designed Modular Hub & Spoke Grid.
- [x] **Implementer:** Created `service_dashboard.html`, `service_theme.css`, `dashboard-core.js`.
- [x] **Audit:** Passed 100/100.
- [x] **Service Layer:** Created `VisionManager` (threaded capture) and `OCRService` (asynchronous parsing).
- [x] **Logic Port:** Successfully ported MSER and Levenshtein logic from legacy assets.
- [x] **Backend Integration:** Unified Motor, Lidar, and Vision into `RobotState` and `APIServer`.
- [x] **Frontend Integration:** Added live MJPEG feed and OCR results panel to Dashboard.
- [x] **Audit:** Full-stack verification passed (Score: 98/100).
- [x] **Service Layer:** Created `VisionManager` (threaded capture) and `OCRService` (asynchronous parsing).
- [x] **Logic Port:** Successfully ported MSER and Levenshtein logic from legacy assets.
- [x] **Backend Integration:** Unified Motor, Lidar, and Vision into `RobotState` and `APIServer`.
- [x] **Frontend Integration:** Added live MJPEG feed and OCR results panel to Dashboard.
- [x] **Hardware Debugging:** Resolved `ioctl(VIDIOC_STREAMON)` error on Raspberry Pi 4.
- [x] **Performance Tuning:** Implemented Dual-Tier pipeline (640p OCR, 320p UI) for stable streaming on Pi.

### ⏳ Backlog (Phase 3)
- [ ] **Sorting Logic:** Implement motor control based on OCR `district` results.
- [ ] **Persistence Engine:** Save successful OCR scans to the SQLite database.
- [ ] **Feature Spec:** Defining the unified `VisionManager` and `OCRService` workflow.
- [ ] **Camera Integration:** Porting `find_camera_index` logic to a threaded `VisionManager`.
- [ ] **OCR Porting:** Wrapping the "Flash Express" knowledge base and preprocessor into a V4.0 Service.





- [ ] **Lidar Integration:**
    - [ ] Analyze `lidar-visualizer` logic.
    - [ ] Create `LidarManager` class in backend.
    - [ ] Expose Lidar data via `/api/lidar`.
- [ ] **Camera/AI Integration:**
    - [ ] Analyze `huskylens-visualizer` and `camera-visualizer`.
    - [ ] Create `VisionManager` in backend.
- [ ] **OCR Feature:**
    - [ ] Port `ocr_sim` logic to backend.
- [ ] **Arduino Firmware:**
    - [ ] Audit `arduino/` code for protocol consistency.
- [ ] **Backend Update:** Add `ocr` key to `/api/status` response (Auditor Recommendation).
- [ ] **Polling Optimization:** Implement timestamp-based polling for OCR results (Auditor Suggestion).

## 🧩 CONTEXT & ARCHITECTURAL RULES
- **Single Source of Truth:** `RobotState` class holds all sensor data.
- **Hardware Access:** ONLY `HardwareManager` is allowed to touch GPIO/Serial.
- **Frontend Logic:** purely visual; no direct hardware calls.
- **Non-Blocking Logic:** OCR processing MUST run in a separate thread to prevent UI/Motor lag.
- **Aesthetic:** Maintain "Minimalist Industrial" (No neons, no Orbitron).

## 🚧 BLOCKERS / NOTES
- Need to decide if visualizers remain separate pages or become components of the main Dashboard.
- **OCR Engine:** System requires `tesseract-ocr` binary to be installed on the host OS.
- **Camera Access:** Ensure the user has permissions (`video` group on Linux).
