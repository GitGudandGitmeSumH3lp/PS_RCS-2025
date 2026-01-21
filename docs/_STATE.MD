# PROJECT STATE (MIGRATION PHASE)
**Current Phase:** 0 - Legacy Stabilization

## 🎯 IMMEDIATE GOALS
- [x] Inventory file structure.
- [x] Generate and Run `migrate.sh`.
- [x] Generate `API_MAP.md`.
- [x] **Refactor `src/services/api/server.py` to fix imports.** (DONE)
- [x] Consolidate/Refactor `src/services/database/core.py`. (NEXT TARGET)
- [ ] **URGENT:** Fix `src/services/api/server.py` to use `AsyncDatabaseEngine` instead of the placeholder `Database` class. (NEW BLOCKER)
- [ ] Update Hardware Handlers (Lidar/Husky) to remove legacy dependencies.

## 🧠 RECENT LOGS
*   [Date] **Refactor:** `server.py` rewritten. Legacy imports (`backend`, `frontend`) replaced with `src.hardware` and `src.services`.


## 🧠 CRITICAL MEMORY
*   **Legacy Codebase:** 1424 files. High risk of breaking imports.
*   **Strategy:** "Lift and Shift" first. Refactor second.
*   **Hardware:** Arduino (TTY), HuskyLens, LiDAR, Camera.