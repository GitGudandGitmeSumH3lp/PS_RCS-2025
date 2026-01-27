# 🟢 PROJECT STATE: PS_RCS_PROJECT
**Phase:** 3.5 - UI Pivot (Service Dashboard)
**Last Updated:** 2026-01-23
**Architecture:** Flask + SQLite + HardwareManager (Thread-Safe)

## 🎯 IMMEDIATE GOAL
Refactor Frontend from "Cyberpunk" to "Minimalist Industrial" (Service Dashboard).
*Paused:* Lidar/Camera Backend Integration:
Integrate isolated legacy visualizers (Lidar, Camera, OCR) into the new unified Backend API.

## 📋 ACTIVE TASK LIST
### ⏳ In Progress (UI Pivot)
- [ ] **Architect:** Design CSS Variables for Light/Dark mode switching.
- [ ] **Implementer:** Add state persistence (localStorage) for theme preference.
- [ ] **Cleanup:** Delete Cyberpunk assets.

### ✅ Completed (Phase 1 & 2)
- [x] **Backend Core:** Refactored `main.py` to use `HardwareManager` and `RobotState`.
- [x] **Database:** Standardized `database.py` with thread-safe connection pooling.
- [x] **Frontend:** Created Neural Interface (dark mode) with real-time API polling.
- [x] **Motor Control:** Wrapped legacy `motor_controller.py` in `LegacyMotorAdapter`.
- [x] **Constraint Update:** Amended `docs/system_constraints.md` to Minimalist/Industrial.
- [x] **Architect:** Designed Modular Hub & Spoke Grid.
- [x] **Implementer:** Created `service_dashboard.html`, `service_theme.css`, `dashboard-core.js`.
- [x] **Audit:** Passed 100/100.

### ⏳ Backlog (Phase 3)
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

## 🧩 CONTEXT & ARCHITECTURAL RULES
- **Single Source of Truth:** `RobotState` class holds all sensor data.
- **Hardware Access:** ONLY `HardwareManager` is allowed to touch GPIO/Serial.
- **Frontend Logic:** purely visual; no direct hardware calls.

## 🚧 BLOCKERS / NOTES
- Need to decide if visualizers remain separate pages or become components of the main Dashboard.