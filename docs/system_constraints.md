# SYSTEM CONSTRAINTS (PS_RCS_PROJECT)

**Type:** Absolute Rules
**Enforcement:** NON-NEGOTIABLE
**Violation Consequences:** Automatic rejection by Auditor

---

## 1. BACKEND & HARDWARE (The Brain)

### Environment
- **Platform:** Raspberry Pi 4B (Linux ARM64).
- **Python Version:** 3.9+.
- **Concurrency:** `threading` ONLY. **Avoid `asyncio`** (Compatibility with legacy Serial/SMBus libraries).

### Architectural Rules
- **No Global State:** No top-level variables for robot state. All state must live in `RobotState` class.
- **Hardware Abstraction:** No direct hardware libraries (`RPi.GPIO`, `serial`) in API routes. Use `HardwareManager` or `LegacyMotorAdapter`.
- **Non-Blocking:** HTTP routes must return immediately. Long-running tasks (Lidar scan, OCR) must run in background threads.
- **Manager Pattern:** No `sqlite3.connect()` inside routes. Use `DatabaseManager`.

### Allowed Libraries
- **Web:** `flask`, `flask_cors` (if needed).
- **Data:** `sqlite3`, `json`, `queue`.
- **Hardware:** `pyserial`, `smbus2`, `RPi.GPIO` (Only inside Adapters).

---

### 2. Aesthetic Guidelines (UPDATED)
*   **Style:** Minimalist, Professional, "Service Dashboard" (SaaS/Industrial look).
*   **Theming:** **Dual Mode Required.**
    *   **Default:** Industrial Dark (Slate Grey `#1e293b`, White Text).
    *   **Toggle:** Medical Light (White/Off-White `#f8fafc`, Dark Grey Text).
*   **Typography:** Inter, Roboto, or System Sans-Serif. High legibility.
*   **Forbidden:** Neon glows, "Cyberpunk" terminology, "Orbitron" font.

---

## 3. COMMUNICATION CONTRACT (The Bridge)

### API Protocol
- **Format:** strictly `application/json`.
- **Command Structure:** `POST /api/motor/control` -> Body: `{"command": "forward"}`.
- **Legacy Compatibility:** The Backend must maintain the keys expected by the Frontend (`success`, `mode`, `battery_voltage`).

---

## 4. FORBIDDEN PATTERNS (Global)

### 🔴 Security & Safety
1.  **No `os.system`:** Use `subprocess.run` with list arguments.
2.  **No `eval()` / `exec()`:** Absolute ban.
3.  **No Hardcoded Secrets:** API keys/Passwords must use Environment Variables or Config files.
4.  **No Hardcoded Paths:** Use `os.path.join` or `pathlib`. Do not assume `/home/pi`.

### 🔴 Code Quality
1.  **Max Function Length:** 50 lines. Refactor if longer.
2.  **Type Hints:** Mandatory for all Python Backend functions.
3.  **Docstrings:** Google-style docstrings required for all public classes/methods.