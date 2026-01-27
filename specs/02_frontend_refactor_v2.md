Running **Analyst (Account B)** logic...

*   **Context:** Refactoring a legacy "Spaghetti Code" frontend to match a modern Python Backend.
*   **Input Analysis:**
    *   `index2.html`: Contains ~450 lines of CSS and a complex `NeuralInterface` JS class.
    *   `main.js`: Contains vestigial/conflicting function calls.
    *   **Goal:** Decouple Logic/Style/View, migrate API calls to JSON Schema, and bind real data.

Here is the structured Feature Specification for the Architect.

***

# FEATURE SPEC: Frontend Refactor (Neural Interface V2)
**Date:** 2026-01-22
**Status:** Feasible

## 1. THE VISION
*   **User Story:** As a System Operator, I want the web interface to reflect real telemetry and send compliant commands to the new backend, so that I am not looking at "fake" `Math.random()` data or sending 404 requests.
*   **Success Metrics:**
    *   Clicking UI buttons sends `POST /api/motor/control` (JSON).
    *   The "Power Level" and "Motor Status" indicators reflect real backend values.
    *   `index.html` size reduced by >60% (via CSS/JS extraction).

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed. Standard Web Refactor.
*   **New Libraries Needed:** None. (Chart.js is already included via CDN).
*   **Risk Level:** Low (Logic exists, just needs re-wiring).

## 3. ATOMIC TASKS (The Roadmap)
*   [ ] **Asset Extraction:** Create `static/css/neural-theme.css` and move inline styles.
*   [ ] **JS Unification:** Merge `main.js` and inline `<script>` into `static/js/neural-core.js`.
*   [ ] **API Migration:** Refactor `executeCommand` to use the new JSON contract.
*   [ ] **Data Binding:** Modify `updateSensorData()` to consume `/api/status` instead of random generation.
*   [ ] **Cleanup:** Update `index.html` to link new assets and remove dead code.

## 4. ARCHITECTURE & MIGRATION MAP

### A. File Structure Proposal
The current flat/inline structure is unmaintainable.
```text
static/
├── css/
│   └── neural-theme.css  (The ~450 lines of extracted CSS)
├── js/
│   └── neural-core.js    (The Unified 'NeuralInterface' class)
└── img/                  (Favicons/assets if needed)
templates/
└── index.html            (Clean HTML skeleton)
```

### B. API Migration Table
The Architect must enforce these changes in the JavaScript logic.

| Action | Old Implementation | New Implementation |
| :--- | :--- | :--- |
| **Motor Control** | `POST /api/command/{cmd}` | `POST /api/motor/control`<br>Body: `{"command": "{cmd}"}` |
| **Stop** | `POST /api/motor/stop` | `POST /api/motor/control`<br>Body: `{"command": "stop"}` |
| **Telemetry** | `GET /api/status` (Simulated) | `GET /api/status`<br>Response: `{"battery_voltage": float, "connection": bool}` |

### C. Logic Unification Strategy
*   **Deprecate:** `main.js` (Delete entirely). The global functions `sendCommand` and `holdCommand` are obsolete.
*   **Keep:** The `NeuralInterface` class structure in `index2.html` is solid.
*   **Action:** Move the `NeuralInterface` class to `static/js/neural-core.js`.

## 5. INTERFACE SKETCHES (For Architect)

**Module:** `static/js/neural-core.js`

*   `async executeCommand(command)`
    *   *Refactor:* Change the `fetch` call to use `JSON.stringify`.
    *   *Code Sketch:*
        ```javascript
        await fetch('/api/motor/control', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ command: command })
        });
        ```

*   `async updateSensorData()`
    *   *Refactor:* Remove `Math.random()` generators for critical systems.
    *   *Data Mapping:*
        *   Backend `battery_voltage` -> Frontend text `#power-level` (Format: "XX.X V").
        *   Backend `motor_connected` -> Frontend text `#motor-state` (CONNECTED/DISCONNECTED).
        *   Backend `cpu_temp` (if avail) -> Frontend `#cpu-usage`.
    *   *Note:* Keep `Math.random()` *only* for "LiDAR Points" or visual eye-candy if the backend doesn't provide those specific streams yet, but mark them clearly as visualizers.

## 6. OPEN QUESTIONS
1.  Does the new `/api/status` endpoint return CPU load and Uptime? If not, we need to ask the Backend Engineer (Account E) to add them, or we leave them as `Math.random()` visualizers for now.
2.  The `script.js` file referenced in `index2.html` line 12 is missing from the input. I assume we are ignoring it and building a fresh `neural-core.js`?

---

✅ **Spec Created:** `specs/frontend_refactor_v2.md`
📋 **Next Step:** Architect to generate the JS/CSS separation contract.
👉 **Next Agent:** Architect (AGENTS/01_architect.md)