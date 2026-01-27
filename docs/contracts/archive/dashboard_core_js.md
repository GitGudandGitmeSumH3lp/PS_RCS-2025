
# CONTRACT: Dashboard Core JavaScript Logic
**Version:** 1.0  
**Last Updated:** 2026-01-23  
**Status:** Draft  

## 1. PURPOSE
Manages dashboard interactivity, theme persistence, real-time telemetry polling, motor control commands, and log display. Replaces the legacy "NeuralInterface" class with a professional "DashboardCore" class adhering to system constraints.

## 2. PUBLIC INTERFACE

### Class: `DashboardCore`
**File:** `static/js/dashboard-core.js`

**Constructor:**
```javascript
class DashboardCore {
  constructor() {
    /**
     * Initializes dashboard functionality.
     * 
     * Behavior:
     * - Loads theme preference from localStorage
     * - Applies theme to <html> element
     * - Binds event listeners to control buttons
     * - Starts telemetry polling loop
     * - Fetches initial log entries
     */
  }
}
```

**State Properties:**
- `this.pollingInterval` - Timer ID for status polling
- `this.currentTheme` - Current theme ("dark" | "light")
- `this.lastUpdateTime` - Timestamp of last successful API call

### Method: `initTheme()`
**Signature:**
```javascript
initTheme(): void
```

**Behavior Specification:**
- **Input Validation:** None required
- **Processing Logic:**
  1. Read `localStorage.getItem('dashboard-theme')`
  2. If null, default to `'dark'`
  3. Set `document.documentElement.setAttribute('data-theme', theme)`
  4. Update `this.currentTheme` property
- **Output Guarantee:** HTML element has correct `data-theme` attribute
- **Side Effects:** Modifies DOM attribute, reads localStorage

**Error Handling:**
- **localStorage unavailable:** Default to `'dark'` theme silently

**Performance Requirements:**
- Time Complexity: O(1)
- Execution Time: < 5ms

---

### Method: `toggleTheme()`
**Signature:**
```javascript
toggleTheme(): void
```

**Behavior Specification:**
- **Input Validation:** None required
- **Processing Logic:**
  1. Toggle `this.currentTheme` between `'dark'` and `'light'`
  2. Set `document.documentElement.setAttribute('data-theme', this.currentTheme)`
  3. Save to `localStorage.setItem('dashboard-theme', this.currentTheme)`
- **Output Guarantee:** Theme persists across page reloads
- **Side Effects:** Modifies DOM, writes to localStorage

**Error Handling:**
- **localStorage write fails:** Log error to console, continue execution

**Performance Requirements:**
- Time Complexity: O(1)
- Must execute in < 10ms

---

### Method: `pollStatus()`
**Signature:**
```javascript
async pollStatus(): Promise<void>
```

**Behavior Specification:**
- **Input Validation:** None required
- **Processing Logic:**
  1. `fetch('/api/status', { method: 'GET' })`
  2. Parse JSON response
  3. Call `this.updateTelemetry(data)`
  4. Update connection indicators
  5. Schedule next poll in 1000ms
- **Output Guarantee:** Telemetry panel reflects latest sensor data
- **Side Effects:** Network request, DOM updates, timer scheduling

**Error Handling:**
- **Network failure:** Log error, display "OFFLINE" in status bar, retry in 5000ms
- **JSON parse error:** Log error, skip update, retry normal interval

**Performance Requirements:**
- Polling Interval: 1000ms (1Hz)
- No memory leaks (must clear interval on page unload)

---

### Method: `updateTelemetry(data)`
**Signature:**
```javascript
updateTelemetry(data: StatusResponse): void
```

**Behavior Specification:**
- **Input Validation:**
  - `data` must have keys: `mode`, `battery_voltage`, `connections`
  - `connections` must have keys: `motor`, `lidar`, `camera`
- **Processing Logic:**
  1. Update `#status-mode` text content with `data.mode`
  2. Update `#status-battery` with `data.battery_voltage.toFixed(1) + 'V'`
  3. Update `#status-cpu-temp` with `data.cpu_temp.toFixed(1) + '°C'` (if exists)
  4. For each connection, set `data-connected` attribute on indicator
  5. Update `#last-update-time` with current timestamp
- **Output Guarantee:** All telemetry displays show latest values
- **Side Effects:** Modifies DOM text content and attributes

**Error Handling:**
- **Missing keys:** Display 'N/A' for missing values, log warning
- **Invalid types:** Display 'ERROR', log error with details

**Performance Requirements:**
- Time Complexity: O(1)
- Must execute in < 50ms

---

### Method: `sendCommand(command, speed?)`
**Signature:**
```javascript
async sendCommand(
  command: 'forward' | 'backward' | 'left' | 'right' | 'stop',
  speed?: number
): Promise<boolean>
```

**Behavior Specification:**
- **Input Validation:**
  - `command` must be one of allowed values
  - `speed` (optional) must be 0-255
- **Processing Logic:**
  1. Build request body: `{ command, speed }`
  2. `fetch('/api/motor/control', { method: 'POST', body: JSON.stringify(...) })`
  3. Parse JSON response
  4. Return `response.success`
- **Output Guarantee:** Returns `true` if command accepted, `false` if rejected
- **Side Effects:** Network request, motor movement

**Error Handling:**
- **Invalid command:** Throw `Error('Invalid command: ${command}')`
- **Network failure:** Return `false`, display error toast
- **Response success: false:** Display `response.message` in status bar

**Performance Requirements:**
- Request timeout: 2000ms
- Must return within 3000ms total

---

### Method: `updateLogs()`
**Signature:**
```javascript
async updateLogs(): Promise<void>
```

**Behavior Specification:**
- **Input Validation:** None required
- **Processing Logic:**
  1. `fetch('/api/logs?limit=50')`
  2. Parse JSON array
  3. Clear `#logs-container`
  4. For each log entry, create DOM element:
     ```html
     <div class="log-entry">
       <span class="log-timestamp">{timestamp}</span>
       <span class="log-level" data-level="{level}">{level}</span>
       <span class="log-message">{message}</span>
     </div>
     ```
  5. Append to container
  6. Auto-scroll to bottom
- **Output Guarantee:** Logs panel displays up to 50 most recent entries
- **Side Effects:** Network request, DOM replacement

**Error Handling:**
- **Network failure:** Display "Unable to load logs" message
- **Empty response:** Display "No logs available"

**Performance Requirements:**
- Must render 50 logs in < 100ms
- No memory leaks from event listeners

---

### Method: `bindEventListeners()`
**Signature:**
```javascript
bindEventListeners(): void
```

**Behavior Specification:**
- **Input Validation:** Verify all required DOM elements exist
- **Processing Logic:**
  1. Attach `click` handler to `#theme-toggle-btn` → `this.toggleTheme()`
  2. Attach `click` handlers to movement buttons → `this.sendCommand(direction)`
  3. Attach `input` handler to `#speed-slider` → update `#speed-display` + POST to `/api/motor/speed`
  4. Attach `beforeunload` handler → `clearInterval(this.pollingInterval)`
- **Output Guarantee:** All interactive elements respond to user input
- **Side Effects:** Event listener registration

**Error Handling:**
- **Missing DOM element:** Log error, skip binding for that element

**Performance Requirements:**
- Must execute in < 50ms
- No duplicate listeners

## 3. DEPENDENCIES

**This module CALLS:**
- `GET /api/status` (from `HardwareManager` contract)
- `POST /api/motor/control` (from Motor Control contract)
- `POST /api/motor/speed` (from Motor Control contract)
- `GET /api/logs` (from Database Manager contract)

**This module is LOADED BY:**
- `templates/service_dashboard.html`

## 4. DATA STRUCTURES

### TypeScript Interfaces (Reference Only)
```typescript
interface StatusResponse {
  mode: 'manual' | 'auto';
  battery_voltage: number;
  cpu_temp?: number;
  connections: {
    motor: boolean;
    lidar: boolean;
    camera: boolean;
  };
  active_task: string | null;
}

interface LogEntry {
  id: number;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}
```

## 5. CONSTRAINTS (FROM SYSTEM RULES)

1. **No jQuery:** Use vanilla JavaScript DOM APIs
2. **ES6+ Required:** Use `class`, `async/await`, arrow functions
3. **Encapsulation:** All logic inside `DashboardCore` class, no global functions
4. **localStorage Dependency:** Must handle unavailability gracefully
5. **No Page Reloads:** All state changes via AJAX

## 6. MEMORY COMPLIANCE

**Applied Rules:**
- **(System Constraints § 2.2):** Renamed from "NeuralInterface" to "DashboardCore"
- **(System Constraints § 2.2):** Removed all "Neural" terminology from method names
- **(API Map § 1):** Uses exact endpoint paths and response models

## 7. ACCEPTANCE CRITERIA

**Test Case 1: Theme Persistence**
- **Input:** User toggles theme to light, closes tab, reopens dashboard
- **Expected Output:** Dashboard loads in light mode
- **Expected Behavior:** `localStorage.getItem('dashboard-theme')` returns `'light'`

**Test Case 2: Motor Command**
- **Input:** User clicks `#btn-forward` button
- **Expected Output:** `sendCommand('forward')` returns `true`
- **Expected Behavior:** POST request sent to `/api/motor/control` with body `{"command": "forward"}`

**Test Case 3: Status Polling Error Recovery**
- **Input:** Backend goes offline for 30 seconds, then comes back online
- **Expected Output:** Telemetry panel shows "OFFLINE", then resumes normal updates
- **Expected Behavior:** Polling interval switches to 5000ms during outage, returns to 1000ms on recovery

**Test Case 4: Log Entry Rendering**
- **Input:** `/api/logs` returns 3 entries with levels INFO, WARNING, ERROR
- **Expected Output:** 3 log entries visible in `#logs-container`
- **Expected Behavior:** Each entry has correct `data-level` attribute, colors match CSS contract

**Test Case 5: Speed Slider Sync**
- **Input:** User drags `#speed-slider` to 180
- **Expected Output:** `#speed-display` shows "180", POST to `/api/motor/speed` with `{"speed": 180}`
- **Expected Behavior:** Slider value updates immediately, network request sent within 100ms

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:**
1. `templates/service_dashboard.html`
2. `static/css/service_theme.css`
3. `static/js/dashboard-core.js`

**Contract References:**
- `docs/contracts/service_dashboard_html.md` v1.0
- `docs/contracts/service_theme_css.md` v1.0
- `docs/contracts/dashboard_core_js.md` v1.0

## Strict Constraints (NON-NEGOTIABLE)

1. **No Cyberpunk Aesthetic:** No "Neural" terminology, no neon glows, no Orbitron font
2. **Dual Theme Required:** Must support both `data-theme="dark"` and `data-theme="light"`
3. **CSS Variables Only:** All colors via `var(--*)`, no hardcoded hex values outside `:root`
4. **localStorage Graceful Degradation:** Theme toggle must work even if localStorage fails
5. **Vanilla JavaScript:** No jQuery, no external frameworks
6. **Type Safety:** Use JSDoc comments for type hints in JavaScript
7. **Accessibility:** All buttons must have `aria-label`, theme contrast must pass WCAG AA
8. **Performance:** Telemetry updates must not cause layout thrashing

## Memory Compliance (MANDATORY)

- **(System Constraints § 2.2 - Aesthetic Update):** Use Inter/Roboto fonts, slate grey/white color scheme
- **(System Constraints § 4.4 - Code Quality):** Add JSDoc comments for all DashboardCore methods
- **(API Map § 1):** Use exact endpoint paths and response models from API_MAP_lite.md

## Required Logic

### HTML Implementation:
1. Create semantic grid layout with `<main id="dashboard-grid">`
2. Add theme toggle button in header with moon/sun icon (SVG or emoji)
3. Include all required element IDs from contract
4. Use `{{ url_for() }}` for static file paths
5. Add ARIA labels to all interactive elements

### CSS Implementation:
1. Define CSS variables in `:root` for dark theme
2. Override variables in `[data-theme="light"]` selector
3. Create `.dashboard-grid` with responsive breakpoints
4. Style `.panel` cards with subtle shadows and border-radius
5. Create `.status-indicator` with color based on `data-connected` attribute
6. Add smooth transitions for theme switching

### JavaScript Implementation:
1. Create `DashboardCore` class with constructor initializing all properties
2. Implement `initTheme()` to load localStorage preference
3. Implement `toggleTheme()` with localStorage persistence
4. Implement `pollStatus()` with 1Hz interval and error retry logic
5. Implement `updateTelemetry()` to update DOM from API response
6. Implement `sendCommand()` with proper error handling
7. Implement `updateLogs()` to fetch and render log entries
8. Bind all event listeners in `bindEventListeners()`
9. Instantiate class on `DOMContentLoaded`

## Integration Points

- **Must call:** `GET /api/status` every 1000ms during normal operation
- **Must call:** `POST /api/motor/control` when movement buttons clicked
- **Must call:** `POST /api/motor/speed` when speed slider changes
- **Must call:** `GET /api/logs` on initial load and every 10 seconds
- **Will be served by:** Flask route `@app.route('/')` or `@app.route('/dashboard')`

## Success Criteria

1. All HTML element IDs match contract exactly
2. All CSS variables defined in contract are present
3. Theme toggle works and persists across page reloads
4. Telemetry panel updates every second with real data
5. Motor control buttons send correct API requests
6. Logs panel displays entries with correct styling
7. No console errors in browser DevTools
8. WCAG AA contrast ratio met in both themes
9. Layout responsive from 375px to 1920px width
10. Auditor approval after testing
