

**DIAGNOSIS:** The Implementer agent is enforcing strict Context Hygiene again. Since this is a new phase, the global context files need to be updated for Frontend specific rules.

**ACTION:** I will bootstrap the missing files now based on the Architect's contract and the Backend we just built.

---

### 📄 FILE 1: `system_constraints.md` (Frontend Version)
*(Copy and paste this into the Implementer context)*

```markdown
# System Constraints for Neural Interface (Frontend)

## Environment
- **Platform:** Modern Web Browsers (Chrome/Edge/Firefox/Safari)
- **Language:** Vanilla JavaScript (ES6+)
- **Runtime:** Client-side (Browser)

## Tech Stack (Allowed)
- **Logic:** Native JavaScript (ES6 Classes, Async/Await). No jQuery.
- **Styling:** CSS3 (Variables, Grid, Flexbox).
- **Visualization:** Chart.js (CDN provided in HTML).

## Forbidden Patterns
1.  **Spaghetti Code:** No inline `<style>` blocks or inline `style=""` attributes.
2.  **Inline Logic:** No inline `<script>` blocks in HTML body.
3.  **Global Pollution:** Encapsulate logic in `NeuralInterface` class.
4.  **Blocking UI:** All network requests must be `async`.

## Integration Constraints
- **Backend API:** Must use JSON payload `{"command": "forward"}`. No URL-based commands.
- **Visual Integrity:** Preserve the "Cyberpunk/Neural" aesthetic defined in the source HTML.
- **Performance:** Debounce rapid button clicks if necessary to prevent API flooding.
```

---

### 📄 FILE 2: `API_MAP_lite.md`
*(Copy and paste this into the Implementer context)*

```markdown
# API Map (Backend to Frontend)

## Backend Endpoints (Source of Truth)
These endpoints are provided by the `src/api/server.py` module built in Ref Phase 1.

## Frontend Usage Contract

### Telemetry
- **Endpoint:** `GET /api/status`
- **Response:**
  ```json
  {
    "mode": "idle",
    "battery_voltage": 12.4,
    "motor_connected": true,
    "lidar_connected": true
  }
  ```
- **Usage:** Poll every 1000ms to update dashboard.

### Motor Control
- **Endpoint:** `POST /api/motor/control`
- **Request:** `{"command": "forward"}` (Must be JSON)
- **Response:** `{"success": true, "message": "..."}`
- **Usage:** Send on button click (Up/Down/Left/Right/Stop).

## Legacy Endpoints (Deprecated)
- `POST /api/command/{cmd}` -> DO NOT USE.
- `POST /motor/stop` -> DO NOT USE.
```

---

### 📄 FILE 3: `_memory_snippet.txt`
*(Copy and paste this into the Implementer context)*

```markdown
# Project Memory: Frontend Refactor

## Visual Style
- "Cyberpunk / Neural" theme.
- Colors: Cyan, Neon Blue, Void Black.
- Fonts: 'Orbitron' (headers), 'Fira Code' (data).

## Chart.js Integration
- The frontend uses Chart.js for visualizations.
- Ensure charts update dynamically if new data streams are added.

## User Experience
- Buttons should provide visual feedback (flash on click).
- Connection status should be obvious (Green/Red indicators).
```

---
