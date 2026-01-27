# CONTRACT: Frontend Neural Interface Module
**Version:** 2.0
**Last Updated:** 2026-01-22
**Status:** Draft

---

## 1. PURPOSE

This module provides the web-based control interface for the Neural Interface system. It manages bidirectional communication with the Python backend, transforms JSON telemetry into visual representations, and transmits user commands via standardized API contracts. The refactor separates presentation (CSS), structure (HTML), and behavior (JS) while eliminating simulated data in favor of real backend integration.

---

## 2. FILE STRUCTURE CONTRACT

### 2.1 Directory Layout (IMMUTABLE)

```
static/
├── css/
│   └── neural-theme.css          # All visual styling (extracted from inline)
├── js/
│   └── neural-core.js            # NeuralInterface class (single source of truth)
└── img/                          # (Reserved for future assets)

templates/
└── index.html                    # Clean HTML skeleton (no inline CSS/JS)
```

**Constraints:**
- `index.html` MUST NOT contain `<style>` tags or inline `style=""` attributes
- `index.html` MUST NOT contain `<script>` tags except asset loading
- All JavaScript logic MUST reside in `neural-core.js`
- CSS file size MUST be ≥400 lines (capturing extracted styles)
- HTML file size MUST be ≤150 lines (60%+ reduction from 450-line baseline)

---

## 3. PUBLIC INTERFACE

### Module: `static/js/neural-core.js`

#### Class: `NeuralInterface`

**Signature:**
```javascript
class NeuralInterface {
    constructor(config?: {
        statusEndpoint?: string,
        controlEndpoint?: string,
        pollInterval?: number
    })
}
```

**Configuration Defaults:**
```javascript
{
    statusEndpoint: '/api/status',
    controlEndpoint: '/api/motor/control',
    pollInterval: 1000  // milliseconds
}
```

**Behavior Specification:**
- **Initialization:** Binds DOM event listeners, starts telemetry polling
- **Lifecycle:** Auto-starts on instantiation, stops on page unload
- **State Management:** Maintains connection status, last known telemetry

---

### Method: `executeCommand`

**Signature:**
```javascript
async executeCommand(command: string): Promise<void>
```

**Parameters:**
- `command` (string, required): One of `["forward", "backward", "left", "right", "stop"]`

**Behavior Specification:**

**Input Validation:**
```javascript
const VALID_COMMANDS = ['forward', 'backward', 'left', 'right', 'stop'];
if (!VALID_COMMANDS.includes(command)) {
    throw new Error(`Invalid command: ${command}. Must be one of ${VALID_COMMANDS.join(', ')}`);
}
```

**Processing Logic:**
1. Validate command against whitelist
2. Construct JSON payload: `{ command: <string> }`
3. Send POST request to `this.config.controlEndpoint`
4. Set `Content-Type: application/json` header
5. Parse response JSON
6. Update UI feedback based on `response.success`

**Output Guarantee:**
- Promise resolves on successful API response (HTTP 200-299)
- Promise rejects on network failure or HTTP error status

**Side Effects:**
- DOM updates: Flash visual feedback on command button
- Console logging: `[NeuralInterface] Executed: ${command}`
- Network I/O: Single POST request

**Error Handling:**
- **Network Failure:** `throw new Error('Network error: Failed to reach control endpoint')`
- **Invalid JSON Response:** `throw new Error('Backend returned malformed JSON')`
- **HTTP 4xx/5xx:** `throw new Error(\`Command rejected: ${response.status} ${response.statusText}\`)`

**Performance Requirements:**
- Time Complexity: O(1)
- Max Response Time: 500ms (network + backend processing)
- Timeout: 5000ms (reject promise if exceeded)

---

### Method: `fetchTelemetry`

**Signature:**
```javascript
async fetchTelemetry(): Promise<TelemetryData>
```

**Return Type:**
```typescript
interface TelemetryData {
    mode: string;
    battery_voltage: number;
    motor_connected: boolean;
    cpu_temp?: number;
    uptime?: number;
}
```

**Behavior Specification:**

**Processing Logic:**
1. Send GET request to `this.config.statusEndpoint`
2. Parse JSON response
3. Validate required fields: `mode`, `battery_voltage`, `motor_connected`
4. Return typed object

**Output Guarantee:**
- Returns object conforming to `TelemetryData` interface
- All required fields are present and correctly typed

**Side Effects:**
- Network I/O: Single GET request
- No DOM manipulation (caller responsible for rendering)

**Error Handling:**
- **Missing Required Field:** `throw new Error('Backend response missing required field: <field_name>')`
- **Type Mismatch:** `throw new Error('Field <field_name> has invalid type')`
- **Network Failure:** `throw new Error('Failed to fetch telemetry')`

**Performance Requirements:**
- Time Complexity: O(1)
- Cache: None (always fetch fresh data)

---

### Method: `updateUI`

**Signature:**
```javascript
updateUI(telemetry: TelemetryData): void
```

**Behavior Specification:**

**Data Binding Map:**

| Backend Field | Frontend Element | Transform | Fallback |
|--------------|------------------|-----------|----------|
| `battery_voltage` | `#power-level` | `${value.toFixed(1)} V` | "-- V" |
| `motor_connected` | `#motor-state` | `true` → "CONNECTED"<br>`false` → "DISCONNECTED" | "UNKNOWN" |
| `mode` | `#system-mode` | Uppercase | "IDLE" |
| `cpu_temp` | `#cpu-usage` | `${value}°C` | Keep existing visualization |
| `uptime` | `#uptime-display` | `${Math.floor(value/3600)}h ${Math.floor((value%3600)/60)}m` | Keep existing visualization |

**Processing Logic:**
1. For each mapping, query DOM element by ID
2. If element exists, apply transform function
3. Update `textContent` or `innerHTML` as appropriate
4. If backend field is `undefined`, use fallback behavior

**Side Effects:**
- DOM updates: Text content of multiple elements
- Visual state changes: CSS classes for connection status

**Error Handling:**
- **Element Not Found:** Log warning, continue processing other elements
- **Invalid Data Type:** Use fallback value, log warning

---

### Method: `startPolling`

**Signature:**
```javascript
startPolling(): void
```

**Behavior Specification:**

**Processing Logic:**
1. Clear any existing polling interval
2. Create new `setInterval` with `this.config.pollInterval`
3. On each tick:
   - Call `this.fetchTelemetry()`
   - Call `this.updateUI(telemetry)`
   - Handle errors silently (log to console, don't break loop)

**Side Effects:**
- Persistent timer: Runs until `stopPolling()` called
- Repeated network I/O

**Error Handling:**
- **Fetch Failure:** Log to console, retry on next interval
- **Consecutive Failures (3+):** Update connection indicator to "OFFLINE"

---

### Method: `stopPolling`

**Signature:**
```javascript
stopPolling(): void
```

**Behavior Specification:**
- Clear active polling interval
- Update connection status to "STOPPED"

---

## 4. DEPENDENCIES

### This module CALLS:
- **Backend API `/api/status`** - Retrieves telemetry data (polled every 1s)
- **Backend API `/api/motor/control`** - Sends motor commands
- **DOM API** - `document.getElementById()`, `element.textContent`, event listeners
- **Fetch API** - All network requests

### This module is CALLED BY:
- **index.html** - Instantiated on `DOMContentLoaded`
- **User Interactions** - Button clicks trigger `executeCommand()`

---

## 5. DATA STRUCTURES

### Configuration Object
```javascript
{
    statusEndpoint: string,      // URL path to status API
    controlEndpoint: string,     // URL path to control API
    pollInterval: number         // Milliseconds between telemetry fetches
}
```

### TelemetryData Interface
```javascript
{
    mode: string,                // System mode (idle/active/error)
    battery_voltage: number,     // Volts (e.g., 12.4)
    motor_connected: boolean,    // Hardware connection status
    cpu_temp: number | undefined,    // Celsius (optional)
    uptime: number | undefined       // Seconds since boot (optional)
}
```

---

## 6. CONSTRAINTS (FROM SYSTEM RULES)

### Asset Separation
- **FORBIDDEN:** Inline `<style>` tags in HTML
- **FORBIDDEN:** Inline `<script>` blocks in HTML (except asset loading)
- **REQUIRED:** All CSS in `static/css/neural-theme.css`
- **REQUIRED:** All JS in `static/js/neural-core.js`

### API Contract Compliance
- **REQUIRED:** All POST requests MUST use `Content-Type: application/json`
- **REQUIRED:** Command payload MUST be `{"command": "<string>"}`
- **FORBIDDEN:** Legacy endpoints (`/api/command/{cmd}`, `/api/motor/stop`)

### Data Integrity
- **FORBIDDEN:** `Math.random()` for critical telemetry (battery, connection, mode)
- **ALLOWED:** `Math.random()` for visual enhancements (LiDAR visualization) if clearly marked
- **REQUIRED:** Display "--" or equivalent for missing backend data

### Browser Compatibility
- **REQUIRED:** Support modern browsers with ES6+ (async/await, Fetch API)
- **FORBIDDEN:** Dependencies on external libraries (Chart.js already included)

---

## 7. MEMORY COMPLIANCE

**No prior memory entries provided.** This is a greenfield refactor.

**Established Rules (for future reference):**
- [2026-01-22] **Asset Separation:** All CSS extracted to `neural-theme.css`, all JS to `neural-core.js`
- [2026-01-22] **API Migration:** Motor control uses JSON body, not URL parameters
- [2026-01-22] **Real Data Only:** Critical telemetry must reflect backend truth

---

## 8. ACCEPTANCE CRITERIA

### Test Case 1: Command Execution (Success)
**Scenario:** User clicks "Forward" button
- **Input:** Button click event
- **Expected Network Call:**
  ```
  POST /api/motor/control
  Content-Type: application/json
  Body: {"command": "forward"}
  ```
- **Expected Response:** `{"success": true}`
- **Expected UI Behavior:** Button flashes green, console logs "Executed: forward"

### Test Case 2: Command Execution (Invalid Command)
**Scenario:** Code calls `executeCommand('invalid')`
- **Input:** `executeCommand('invalid')`
- **Expected Exception:** `Error: Invalid command: invalid. Must be one of forward, backward, left, right, stop`
- **Expected Behavior:** No network request sent

### Test Case 3: Telemetry Fetch (Success)
**Scenario:** Polling interval triggers
- **Input:** Timer tick after 1000ms
- **Expected Network Call:** `GET /api/status`
- **Expected Response:**
  ```json
  {
    "mode": "idle",
    "battery_voltage": 12.4,
    "motor_connected": true,
    "cpu_temp": 45
  }
  ```
- **Expected UI Updates:**
  - `#power-level` displays "12.4 V"
  - `#motor-state` displays "CONNECTED"
  - `#system-mode` displays "IDLE"
  - `#cpu-usage` displays "45°C"

### Test Case 4: Telemetry Fetch (Missing Optional Field)
**Scenario:** Backend omits `cpu_temp`
- **Input:** Response `{"mode": "active", "battery_voltage": 11.8, "motor_connected": false}`
- **Expected Behavior:**
  - Required fields update normally
  - `#cpu-usage` retains previous value or shows fallback
  - No error thrown

### Test Case 5: Network Failure
**Scenario:** Backend is unreachable
- **Input:** Fetch times out after 5000ms
- **Expected Exception:** `Error: Network error: Failed to reach control endpoint`
- **Expected UI Behavior:** Connection indicator shows "OFFLINE" after 3 consecutive failures

### Test Case 6: File Size Reduction
**Scenario:** Compare `index.html` before/after refactor
- **Baseline:** 450 lines (with inline CSS/JS)
- **Expected Result:** ≤150 lines (66% reduction)
- **Verification:** `wc -l templates/index.html` output ≤ 150

### Test Case 7: Asset Loading
**Scenario:** Open index.html in browser
- **Expected Network Requests:**
  ```
  GET /static/css/neural-theme.css (200 OK)
  GET /static/js/neural-core.js (200 OK)
  ```
- **Expected Console:** No 404 errors, no inline script warnings

---

## 9. INTEGRATION POINTS

### Backend API Contract (MUST MATCH EXACTLY)

#### Endpoint: `GET /api/status`
**Response Schema:**
```json
{
  "mode": "string (idle|active|error)",
  "battery_voltage": "float",
  "motor_connected": "boolean",
  "cpu_temp": "float (optional)",
  "uptime": "integer (optional)"
}
```

#### Endpoint: `POST /api/motor/control`
**Request Schema:**
```json
{
  "command": "string (forward|backward|left|right|stop)"
}
```
**Response Schema:**
```json
{
  "success": "boolean",
  "message": "string (optional)"
}
```

### DOM Requirements
**Required Element IDs:**
- `#power-level` - Battery voltage display
- `#motor-state` - Motor connection status
- `#system-mode` - Current operational mode
- `#cpu-usage` - CPU temperature (optional field)
- `#uptime-display` - System uptime (optional field)

**Required Button Classes/IDs:**
- `.control-btn[data-command="forward"]`
- `.control-btn[data-command="backward"]`
- `.control-btn[data-command="left"]`
- `.control-btn[data-command="right"]`
- `.control-btn[data-command="stop"]`

---

## 10. MIGRATION NOTES

### Deprecated Code (DELETE)
- `main.js` - Entire file (obsolete global functions)
- `index2.html` inline `<style>` block (lines 1-450 approx)
- `index2.html` inline `<script>` block containing `NeuralInterface` class

### Preserved Logic (MIGRATE)
- `NeuralInterface` class structure → Move to `neural-core.js`
- Chart.js initialization → Keep in separate `<script>` tag in HTML
- Event delegation pattern for buttons → Refactor into class methods

### New Additions
- `neural-theme.css` - Extract all CSS
- Fetch timeout wrapper (5s limit)
- Consecutive failure detection (3-strike offline indicator)

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:**
1. `static/js/neural-core.js` (new file)
2. `static/css/neural-theme.css` (new file)
3. `templates/index.html` (refactor existing)

**Contract Reference:** `docs/contracts/frontend_neural_interface_v2.md` v2.0

---

## Strict Constraints (NON-NEGOTIABLE)

1. **Asset Separation:** Zero inline CSS/JS in HTML (except asset loading `<script src="">`)
2. **API Contract:** POST body MUST be `{"command": "string"}`, not URL parameters
3. **Data Purity:** No `Math.random()` for `battery_voltage`, `motor_connected`, or `mode`
4. **File Size:** `index.html` MUST be ≤150 lines
5. **Browser Support:** ES6+ syntax (async/await, class syntax, Fetch API)

---

## Required Logic

### `neural-core.js` Implementation Steps

1. **Class Structure:**
   ```javascript
   class NeuralInterface {
       constructor(config = {}) {
           this.config = {
               statusEndpoint: config.statusEndpoint || '/api/status',
               controlEndpoint: config.controlEndpoint || '/api/motor/control',
               pollInterval: config.pollInterval || 1000
           };
           this.pollingTimer = null;
           this.failureCount = 0;
           this.init();
       }
   }
   ```

2. **Initialization Logic:**
   - Wait for `DOMContentLoaded`
   - Bind click handlers to all `.control-btn` elements
   - Extract `data-command` attribute
   - Call `this.executeCommand(command)`
   - Start polling with `this.startPolling()`

3. **Command Execution:**
   ```javascript
   async executeCommand(command) {
       // 1. Validate command
       // 2. Construct payload
       // 3. Fetch with timeout
       // 4. Handle response
       // 5. Update UI feedback
   }
   ```

4. **Telemetry Polling:**
   ```javascript
   async fetchTelemetry() {
       // 1. GET /api/status
       // 2. Parse JSON
       // 3. Validate required fields
       // 4. Return data object
   }

   updateUI(telemetry) {
       // 1. Map backend fields to DOM elements
       // 2. Apply transforms (voltage formatting, boolean→text)
       // 3. Handle missing optional fields
   }

   startPolling() {
       // 1. setInterval with this.config.pollInterval
       // 2. Try/catch around fetch+update
       // 3. Increment failureCount on error
       // 4. Show OFFLINE after 3 failures
   }
   ```

5. **Error Handling:**
   - Wrap all fetch calls in try/catch
   - Log errors to console
   - Don't break polling loop on single failure
   - Use fetch timeout helper:
     ```javascript
     async fetchWithTimeout(url, options, timeout = 5000) {
         const controller = new AbortController();
         const id = setTimeout(() => controller.abort(), timeout);
         try {
             const response = await fetch(url, {...options, signal: controller.signal});
             clearTimeout(id);
             return response;
         } catch (error) {
             clearTimeout(id);
             throw error;
         }
     }
     ```

### `neural-theme.css` Implementation Steps

1. Copy all CSS from `index2.html` `<style>` block
2. Organize into sections:
   - CSS Variables (colors, spacing)
   - Layout (grid, flex)
   - Components (buttons, panels, indicators)
   - Animations
   - Responsive breakpoints
3. Remove any unused selectors
4. Verify no `!important` overrides needed

### `index.html` Refactor Steps

1. Remove entire `<style>` block
2. Add `<link rel="stylesheet" href="/static/css/neural-theme.css">`
3. Remove inline `<script>` containing `NeuralInterface`
4. Add `<script src="/static/js/neural-core.js"></script>` before `</body>`
5. Add initialization script:
   ```html
   <script>
       document.addEventListener('DOMContentLoaded', () => {
           window.neuralInterface = new NeuralInterface();
       });
   </script>
   ```
6. Verify all element IDs match contract

---

## Integration Points

**Must Call:**
- `fetch(config.statusEndpoint)` every 1000ms
- `fetch(config.controlEndpoint, {method: 'POST', ...})` on button clicks

**Will Be Called By:**
- HTML instantiation: `new NeuralInterface()` on page load
- DOM events: Button clicks, page unload

**External Dependencies:**
- Chart.js (already loaded via CDN in HTML)
- Browser Fetch API
- Browser DOM API

---

## Success Criteria

✅ All methods match contract signatures exactly  
✅ File structure matches specification (`static/css/`, `static/js/`)  
✅ `index.html` ≤150 lines  
✅ No inline CSS or `<script>` blocks in HTML  
✅ Test Case 1-7 all pass  
✅ No console errors on page load  
✅ Real backend data displayed (not `Math.random()`)  
✅ Network tab shows correct JSON payloads  
✅ Auditor approval required before deployment

---

## Open Questions for Backend Engineer

1. **Missing Telemetry Fields:** Does `/api/status` currently return `cpu_temp` and `uptime`?
   - If NO: Frontend will use fallback visualization for these fields
   - If YES: Confirm field names match contract exactly

2. **Error Response Format:** What does `/api/motor/control` return on failure?
   - Expected: `{"success": false, "message": "Motor not connected"}`
   - Confirm status code (400? 500?)

---

✅ **Contract Created:** `docs/contracts/frontend_neural_interface_v2.md`  
📋 **Work Order Generated** for Frontend Implementer  
🔍 **Next Verification Command:**  
```
/verify-context: frontend_neural_interface_v2.md, API_MAP_lite.md, system_constraints.md
```  
👉 **Next Agent:** Implementer (AGENTS/02_implementer.md)  
🎯 **Estimated Implementation Time:** 3-4 hours  
⚠️ **Risk:** Low (straightforward refactor, no new algorithms)