# Session: 2026-02-11/12 – Environment Setup & Async Audit

- **Fresh SD card provisioning** – Raspberry Pi OS Bookworm, system packages, Python 3.13 venv (`--system-site-packages`).
- **Core dependencies installed** – `picamera2`, `flask`, `flask-cors`, `numpy`, `nodejs` (optional).
- **Database directories** – `data/` and `instance/` created, verified writable.
- **Version control** – Comprehensive `.gitignore` added, directory placeholders (`.gitkeep`) staged.
- **Frontend bug fix** – Double file-dialog in OCR upload zone eliminated (removed redundant click listener in `ocr-panel.js`).
- **Performance testing (Phase 7.4)** – **Skipped** – not required (dashboard accessed from PC, not Pi touchscreen).
- **Async violation audit** – Researcher identified **12 critical async/sync mismatches** in `core.py` vs `server.py`. Full inventory documented.
- **Current blocker** – OCR history endpoints (`/api/vision/results`, `/api/ocr/scans`) fail due to async DB calls in sync Flask routes.
- **Pending** – Awaiting `receipt_database.py`, `db_manager.py`, full `server.py` to design synchronous refactor.

## 🔍 Session Discoveries (Context-Only)

### 🔴 Discovery 1: Async/Sync Database Violation
- **Approach:** Used `sqlalchemy.ext.asyncio` + `aiosqlite` in `core.py` for database operations.
- **Failed due to:** Incompatibility with Flask’s synchronous request-response cycle and `ThreadPoolExecutor` background tasks. Results in `no running event loop` errors and silent failures.
- **Learned:** `system_constraints.md` (Section 1) explicitly forbids `asyncio`. The async layer was an architectural drift; must be reverted to synchronous SQLAlchemy or raw `sqlite3`.
- **Affects future:** All OCR history endpoints (`/api/vision/results/<id>`, `/api/ocr/scans`), background OCR save, and database initialization.
- **Decided:** Full refactor of `core.py` to use synchronous `create_engine` + `sessionmaker` with thread-safety via `scoped_session` or explicit locks. This will restore compatibility and unblock Phase 8.0.

### 🟡 Discovery 2: Performance Testing (Phase 7.4) Scope Clarification
- **Approach:** Prepared detailed Pi 4B performance test plan with FPS counter, memory profiler, touch response.
- **Failed due to:** User clarified that dashboard is accessed from a PC browser, not on the Pi touchscreen. Performance on Pi client is irrelevant for current integration.
- **Learned:** Not all hardware-specific testing is required when the device is used as a server only.
- **Affects future:** Performance testing will be deferred to a later phase if client-side Pi deployment becomes necessary.
- **Decided:** **Skip Phase 7.4** entirely; mark as completed (skipped) in state. Proceed directly to Phase 8.0 Integration Testing.

### 🟢 Discovery 3: Double File-Dialog Root Cause
- **Approach:** Used `<label for="...">` + explicit `click` listener on dropzone.
- **Failed due to:** Redundant event binding – `<label>` already triggers file input via `for` attribute; extra listener caused two dialogs.
- **Learned:** Always verify event propagation when mixing native HTML behaviour with custom listeners.
- **Affects future:** Similar patterns in other UI components will be audited.
- **Decided:** Remove explicit `click` listener in `_setupDragDrop()`. Fix applied and tested.

### 🟠 Discovery 4: Missing File Dependencies
- **Approach:** Attempted to design sync refactor plan without full source context.
- **Failed due to:** Critical files (`receipt_database.py`, `db_manager.py`, full `server.py`) not yet provided – cannot determine dependency graph or migration path.
- **Learned:** The refactor cannot proceed without these files; they are required to confirm whether `ReceiptDatabase` uses async `core.py` and to unify with existing `DatabaseManager`.
- **Affects future:** Phase 8.1 is blocked until these files are supplied.
- **Decided:** Halt all database work; request missing files before proceeding. This discovery is now the **top priority**.