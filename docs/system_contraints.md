# SYSTEM CONSTRAINTS & ARCHITECTURE LAWS
**Project:** Parcel Robot V3.5
**Status:** Legacy Migration Phase

## 1. HARDWARE INTERFACES (NON-NEGOTIABLE)
*   **Safety First:** No changes to `src/firmware/arduino/` logic are allowed without explicit Human Review.
*   **Serial Ports:** Must be loaded from Environment Variables (e.g., `os.getenv('ARDUINO_PORT')`). NEVER hardcode `/dev/ttyUSB0`.
*   **Concurrency:** Hardware handlers (LiDAR, HuskyLens) must run in separate Threads or Processes to avoid blocking the Flask Main Loop.

## 2. TECHNOLOGY STACK
*   **Backend:** Python 3.9+ (Flask).
*   **Frontend:** Vanilla JavaScript + HTML Templates (Jinja2).
    *   *Constraint:* Do NOT introduce React, Vue, or Webpack build steps yet. Keep it simple.
*   **Database:** SQLite.
    *   *Constraint:* All legacy DBs (`robot_data`, `huskylens`) must be consolidated into a single schema. No raw SQL strings in handlers; use the `Database` class.

## 3. CODING STANDARDS (V3.5)
*   **Imports:** Must use absolute imports from project root (e.g., `from src.hardware.motor import ...`).
*   **Type Hints:** Required for all new function signatures.
*   **Error Handling:** Hardware failures must not crash the API Server. Use `try/except` blocks and log errors to `shared_data["status"]`.

## 4. FILE STRUCTURE
*   **Source:** All logic goes in `src/`.
*   **Web:** All UI code goes in `web/`.
*   **Config:** No `config.py` in source folders. Use `.env` and `config/` directory.

## 🖥️ WORK ENVIRONMENT (Windows)
**Project Root:** `F:\PORTFOLIO\ps_rcs_project`

### 📋 OUTPUT FORMATTING RULES
1.  **File References:** When listing target files, created artifacts, or work orders in Markdown, you MUST use the **Windows Absolute Path**.
    *   ❌ `docs/contracts/auth.md`
    *   ✅ `F:\PORTFOLIO\ps_rcs_project\docs\contracts\auth.md`
2.  **Code Paths:** Inside Python/JS code, continue using relative paths or `pathlib` to ensure cross-platform compatibility.
    *   ✅ `Path("docs") / "contracts"`