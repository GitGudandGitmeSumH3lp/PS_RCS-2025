I understand the orchestration task. However, I cannot directly modify files on your filesystem. Instead, I can provide you with the complete updated content for `system_constraints.md` that you can copy and paste.

Here's the updated file content:

```markdown
# SYSTEM CONSTRAINTS (PS_RCS_PROJECT)

**Last Updated:** 2026-02-11  
**Changelog:**
- 2026-02-11: Added **Frontend Development Standards** (Section 5) from Phase 7.0 OCR Panel implementation.
- (Previous entries as needed)

Type: Absolute Rules
Enforcement: NON-NEGOTIABLE
Violation Consequences: Automatic rejection by Auditor

## 1. BACKEND & HARDWARE (The Brain)

### Environment
- **Platform:** Raspberry Pi 4B (Linux ARM64).
- **Python Version:** 3.9+.
- **Concurrency:** `threading` ONLY. Avoid `asyncio` (Compatibility with legacy Serial/SMBus libraries).

### Architectural Rules
- **No Global State:** No top-level variables for robot state. All state must live in `RobotState` class.
- **Hardware Abstraction:** No direct hardware libraries (`RPi.GPIO`, `serial`) in API routes. Use `HardwareManager` or `LegacyMotorAdapter`.
- **Non-Blocking:** HTTP routes must return immediately. Long-running tasks (Lidar scan, OCR) must run in background threads.
- **Manager Pattern:** No `sqlite3.connect()` inside routes. Use `DatabaseManager`.

### Allowed Libraries
- **Web:** `flask`, `flask_cors` (if needed).
- **Data:** `sqlite3`, `json`, `queue`.
- **Hardware:** `pyserial`, `smbus2`, `RPi.GPIO` (Only inside Adapters).

## 2. Aesthetic Guidelines (UPDATED)

- **Style:** Minimalist, Professional, "Service Dashboard" (SaaS/Industrial look).
- **Theming:** Dual Mode Required.
  - **Default:** Industrial Dark (Slate Grey `#1e293b`, White Text).
  - **Toggle:** Medical Light (White/Off-White `#f8fafc`, Dark Grey Text).
- **Typography:** Inter, Roboto, or System Sans-Serif. High legibility.
- **Forbidden:** Neon glows, "Cyberpunk" terminology, "Orbitron" font.

## 3. COMMUNICATION CONTRACT (The Bridge)

### API Protocol
- **Format:** strictly `application/json`.
- **Command Structure:** `POST /api/motor/control` -> Body: `{"command": "forward"}`.
- **Legacy Compatibility:** The Backend must maintain the keys expected by the Frontend (`success`, `mode`, `battery_voltage`).

## 4. FORBIDDEN PATTERNS (Global)

### 🔴 Security & Safety
- No `os.system`: Use `subprocess.run` with list arguments.
- No `eval()` / `exec()`: Absolute ban.
- No Hardcoded Secrets: API keys/Passwords must use Environment Variables or Config files.
- No Hardcoded Paths: Use `os.path.join` or `pathlib`. Do not assume `/home/pi`.

### 🔴 Code Quality
- **Max Function Length (Python & JavaScript):** 50 lines. Refactor if longer.
- **Type Hints:** Mandatory for all Python Backend functions.
- **Docstrings:** Google-style docstrings required for all public classes/methods.
- **Field Naming Consistency:** Backend APIs MUST use `snake_case` for all JSON field names. Frontend MUST implement defensive dual-lookup (snake_case primary, camelCase fallback) when consuming APIs.

## 5. FRONTEND DEVELOPMENT STANDARDS

### 5.1 JavaScript Code Quality
- **Function Length:** No JavaScript method may exceed **50 lines** of executable code (comments and whitespace excluded). Violations trigger automatic audit failure.
- **Documentation:** All public methods must have Google‑style JSDoc comments (`@param`, `@returns`, `@private` where applicable).
- **Error Handling:** Every `fetch()` or asynchronous operation must be wrapped in `try/catch` and display user‑facing feedback via the toast notification system. No silent failures.

### 5.2 UI/UX & Accessibility
- **Touch Targets:** All interactive elements (buttons, dropzones, clickable cards) must have **`min-height: 44px`** and **`min-width: 44px`** (WCAG AAA touch target compliance).
- **Toast Notifications:** Every dashboard HTML page **MUST** include:
  ```html
  <div id="toast-container" class="toast-container" aria-live="polite"></div>
  ```
  All user feedback must be delivered via this container. Direct `alert()` is forbidden.

- **Accessibility (ARIA):**
  - All modal dialogs must have `role="dialog"`, `aria-labelledby`, and `aria-modal="true"`.
  - Focus must be trapped inside open modals.
  - Tab navigation order must be logical.

### 5.3 HTML & DOM Conventions
- **ID Naming:** Use kebab-case for HTML id attributes (e.g., `ocr-stream`, `btn-analyze`). In JavaScript, map these to camelCase properties (e.g., `ocrStream`, `btnAnalyze`) via getter or element caching.
- **Semantic Markup:** Prefer `<button>` over `<div>` with click handlers. Use `<dialog>` for modals where supported.

### 5.4 Asset & Upload Limits
- **Image Uploads:** Maximum file size: 5 MB. Allowed formats: `image/jpeg`, `image/png`, `image/webp`. Validation must occur both in UI and before transmission.

### 5.5 Performance Guidelines (Raspberry Pi 4B)
These are targets, not hard constraints, but must be verified during testing:
- UI response to user input: <100 ms
- Camera overlay frame latency: <16 ms (60 fps capable)
- History / scan list load time: <500 ms for 50 records

### 5.6 Legacy Integration
No direct modification of legacy `dashboard-core.js` unless strictly required. New features must be added via separate modules (e.g., `ocr-panel.js`) and instantiated in `DashboardCore` only through composition.
```