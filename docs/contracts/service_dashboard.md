# CONTRACT: Service Dashboard (Hub Architecture)
**Version:** 1.0
**Last Updated:** 2026-01-23
**Status:** Draft

---

## 1. PURPOSE

The Service Dashboard serves as the central hub interface for the PS_RCS_PROJECT robot control system. It provides a modular, theme-aware layout that displays real-time motor control alongside extensible placeholder modules for future heavy subsystems (Lidar, Camera, OCR). The architecture prioritizes professional aesthetics, accessibility, and seamless integration of future components without requiring structural refactoring.

---

## 2. PUBLIC INTERFACE

### 2.1 HTML Structure Contract (`templates/service_dashboard.html`)

**Template Variables (Jinja2):**
```python
# Passed from Flask route
{
    "initial_status": dict,  # Output from HardwareManager.get_status()
    "app_version": str       # e.g., "4.0"
}
```

**Required Semantic Structure:**

```html
<!-- Theme wrapper with data attribute -->
<body data-theme="dark">
  
  <!-- Top Bar: Global Status -->
  <header id="global-status-bar" class="status-bar">
    <div id="connection-indicator" class="status-badge"></div>
    <div id="battery-display" class="status-metric"></div>
    <button id="theme-toggle" class="icon-button"></button>
  </header>

  <!-- Main Grid: Modular Card Container -->
  <main id="dashboard-grid" class="service-grid">
    
    <!-- Active Module: Motor Control -->
    <section id="motor-control-card" class="service-card active">
      <header class="card-header">
        <h2>Motor Control</h2>
        <span id="motor-status" class="module-status-badge"></span>
      </header>
      <div class="card-body">
        <div id="speed-control" class="control-group"></div>
        <div id="direction-pad" class="d-pad"></div>
      </div>
    </section>

    <!-- Placeholder: Lidar System -->
    <section id="lidar-card" class="service-card placeholder">
      <header class="card-header">
        <h2>Lidar System</h2>
        <span id="lidar-status" class="module-status-badge">Offline</span>
      </header>
      <div class="card-body placeholder-content">
        <p class="placeholder-text">Module Ready for Integration</p>
      </div>
    </section>

    <!-- Placeholder: Camera Feed -->
    <section id="camera-card" class="service-card placeholder">
      <header class="card-header">
        <h2>Camera Feed</h2>
        <span id="camera-status" class="module-status-badge">Offline</span>
      </header>
      <div class="card-body placeholder-content">
        <p class="placeholder-text">Module Ready for Integration</p>
      </div>
    </section>

    <!-- Placeholder: OCR Logs -->
    <section id="ocr-card" class="service-card placeholder">
      <header class="card-header">
        <h2>OCR Logs</h2>
        <span id="ocr-status" class="module-status-badge">Standby</span>
      </header>
      <div class="card-body placeholder-content">
        <p class="placeholder-text">Module Ready for Integration</p>
      </div>
    </section>

  </main>

  <!-- Scripts -->
  <script src="/static/js/dashboard-core.js"></script>
</body>
```

**HTML Element ID Contract:**

| Element ID | Purpose | Required Attributes |
|------------|---------|-------------------|
| `global-status-bar` | Top navigation container | None |
| `connection-indicator` | Hardware connection status | `data-connected="true/false"` |
| `battery-display` | Battery voltage display | `data-voltage="12.4"` |
| `theme-toggle` | Theme switch button | `aria-label="Toggle theme"` |
| `dashboard-grid` | Main card container | None |
| `motor-control-card` | Active motor module | `class="service-card active"` |
| `motor-status` | Motor module status | `data-status="online/offline"` |
| `lidar-status` | Lidar module status | `data-status="offline"` |
| `camera-status` | Camera module status | `data-status="offline"` |
| `ocr-status` | OCR module status | `data-status="standby"` |

**Behavior Specification:**
- **Initial Render:** Template must render with all placeholder cards visible
- **Accessibility:** All interactive elements require ARIA labels
- **Data Attributes:** Status badges use `data-status` for CSS targeting
- **Grid Expansion:** Adding new modules requires only appending new `<section class="service-card">` elements

---

### 2.2 CSS Theming Contract (`static/css/service_theme.css`)

**Required CSS Custom Properties:**

```css
/* Root: Industrial Dark (Default) */
:root[data-theme="dark"] {
  /* Primary Colors */
  --bg-primary: #0f172a;        /* Deep slate */
  --bg-secondary: #1e293b;      /* Card background */
  --bg-tertiary: #334155;       /* Hover states */
  
  /* Text Colors */
  --text-primary: #f8fafc;      /* High contrast white */
  --text-secondary: #cbd5e1;    /* Muted text */
  --text-tertiary: #94a3b8;     /* Disabled text */
  
  /* Accent Colors */
  --accent-primary: #3b82f6;    /* Blue for active states */
  --accent-success: #10b981;    /* Green for online */
  --accent-warning: #f59e0b;    /* Amber for standby */
  --accent-danger: #ef4444;     /* Red for offline */
  
  /* UI Elements */
  --border-color: #475569;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
}

/* Medical Light Theme */
:root[data-theme="light"] {
  --bg-primary: #f8fafc;
  --bg-secondary: #ffffff;
  --bg-tertiary: #e2e8f0;
  
  --text-primary: #1e293b;
  --text-secondary: #475569;
  --text-tertiary: #94a3b8;
  
  --accent-primary: #2563eb;
  --accent-success: #059669;
  --accent-warning: #d97706;
  --accent-danger: #dc2626;
  
  --border-color: #cbd5e1;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
}
```

**Required CSS Classes:**

```css
/* Core Layout */
.status-bar {
  /* Top bar styling */
  display: flex;
  justify-content: space-between;
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.service-grid {
  /* Main grid container */
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  max-width: 1400px;
  margin: 0 auto;
}

.service-card {
  /* Modular card component */
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s ease;
}

.service-card:hover {
  box-shadow: var(--shadow-md);
}

.service-card.active {
  border-color: var(--accent-primary);
}

.service-card.placeholder .card-body {
  opacity: 0.6;
}

/* Status Indicators */
.module-status-badge {
  /* Status badge component */
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.module-status-badge[data-status="online"] {
  background: var(--accent-success);
  color: white;
}

.module-status-badge[data-status="offline"] {
  background: var(--accent-danger);
  color: white;
}

.module-status-badge[data-status="standby"] {
  background: var(--accent-warning);
  color: white;
}
```

**Typography Contract:**
```css
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 16px;
  line-height: 1.5;
  color: var(--text-primary);
  background: var(--bg-primary);
}

h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
}
```

**Spacing System Contract:**
```css
:root {
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

**Error Handling:**
- **Missing Theme Attribute:** Default to `data-theme="dark"`
- **Invalid Status Values:** Default badge to neutral gray

**Performance Requirements:**
- Theme transitions: < 100ms
- CSS file size: < 15KB uncompressed
- No external font dependencies (use system stack)

---

### 2.3 JavaScript Dashboard Core Contract (`static/js/dashboard-core.js`)

**Class: `DashboardCore`**

```javascript
class DashboardCore {
  /**
   * Central dashboard controller managing themes and module states.
   * @class
   */
  constructor() {
    /** @type {string} Current theme ('dark' or 'light') */
    this.currentTheme = 'dark';
    
    /** @type {Object.<string, string>} Module status cache */
    this.moduleStates = {};
    
    /** @type {number|null} Status polling interval ID */
    this.pollIntervalId = null;
  }

  /**
   * Initialize dashboard on page load.
   * @returns {void}
   */
  init(): void

  /**
   * Toggle between dark and light themes.
   * @returns {void}
   * @fires themeChanged - Custom event with {theme: string}
   */
  toggleTheme(): void

  /**
   * Load theme preference from localStorage.
   * @returns {string} Saved theme or 'dark' as default
   */
  loadThemePreference(): string

  /**
   * Save theme preference to localStorage.
   * @param {string} theme - 'dark' or 'light'
   * @returns {void}
   */
  saveThemePreference(theme: string): void

  /**
   * Update a module's status badge.
   * @param {string} moduleName - ID prefix (e.g., 'motor', 'lidar')
   * @param {string} status - 'online' | 'offline' | 'standby'
   * @param {string} [displayText] - Optional custom badge text
   * @returns {boolean} Success status
   * @throws {Error} If moduleName is invalid
   */
  updateModuleStatus(
    moduleName: string, 
    status: string, 
    displayText?: string
  ): boolean

  /**
   * Start polling /api/status endpoint.
   * @param {number} [interval=2000] - Polling interval in ms
   * @returns {void}
   */
  startStatusPolling(interval?: number): void

  /**
   * Stop polling /api/status endpoint.
   * @returns {void}
   */
  stopStatusPolling(): void

  /**
   * Process status response from backend.
   * @param {Object} statusData - Response from /api/status
   * @returns {void}
   * @private
   */
  _processStatusUpdate(statusData: Object): void

  /**
   * Update global connection indicator.
   * @param {Object} connections - {motor: bool, lidar: bool, camera: bool}
   * @returns {void}
   * @private
   */
  _updateConnectionIndicator(connections: Object): void

  /**
   * Update battery display.
   * @param {number} voltage - Battery voltage (V)
   * @returns {void}
   * @private
   */
  _updateBatteryDisplay(voltage: number): void
}
```

**Behavior Specification:**

**Method: `init()`**
- **Input Validation:** None required
- **Processing Logic:**
  1. Load theme preference from localStorage
  2. Apply theme to `<body data-theme>`
  3. Attach event listener to `#theme-toggle`
  4. Initialize module status cache from DOM
  5. Start status polling
- **Output Guarantee:** Dashboard is fully interactive
- **Side Effects:** 
  - Modifies DOM `data-theme` attribute
  - Starts background polling interval
  - Registers global event listeners

**Method: `toggleTheme()`**
- **Input Validation:** None
- **Processing Logic:**
  1. Toggle `currentTheme` between 'dark' and 'light'
  2. Update `<body data-theme>` attribute
  3. Save preference to localStorage
  4. Dispatch custom `themeChanged` event
- **Output Guarantee:** Theme is visually switched
- **Side Effects:**
  - Modifies DOM
  - Writes to localStorage
  - Fires CustomEvent

**Method: `updateModuleStatus(moduleName, status, displayText?)`**
- **Input Validation:**
  - `moduleName` must match pattern: `^(motor|lidar|camera|ocr)$`
  - `status` must be one of: `online`, `offline`, `standby`
  - `displayText` optional, max 20 characters
- **Processing Logic:**
  1. Construct element ID: `${moduleName}-status`
  2. Query element from DOM
  3. Update `data-status` attribute
  4. Update `textContent` with displayText or capitalize(status)
  5. Cache state in `moduleStates`
- **Output Guarantee:** Returns `true` if element found and updated
- **Side Effects:** Modifies DOM element attributes and text

**Error Handling:**
- **Invalid moduleName:** Throw `Error("Invalid module name: ${moduleName}")`
- **Element not found:** Log warning, return `false`
- **Invalid status:** Throw `Error("Invalid status: ${status}. Must be online|offline|standby")`

**Method: `_processStatusUpdate(statusData)`**
- **Input Validation:** Validate against API_MAP_LITE `/api/status` schema
- **Processing Logic:**
  1. Extract `connections` object
  2. Map motor connection to `updateModuleStatus('motor', ...)`
  3. Map lidar connection to `updateModuleStatus('lidar', ...)`
  4. Map camera connection to `updateModuleStatus('camera', ...)`
  5. Call `_updateBatteryDisplay(statusData.battery_voltage)`
  6. Call `_updateConnectionIndicator(statusData.connections)`
- **Output Guarantee:** All UI elements reflect latest backend state
- **Side Effects:** Multiple DOM updates

**Performance Requirements:**
- `toggleTheme()`: < 50ms execution time
- `updateModuleStatus()`: < 10ms per call
- Status polling: 2000ms default interval (configurable)
- Memory: < 1MB JavaScript heap usage

---

## 3. DEPENDENCIES

**This module CALLS:**
- `GET /api/status` (from API_MAP_LITE) - Real-time telemetry polling
- `localStorage.getItem('theme')` - Browser API for theme persistence
- `localStorage.setItem('theme', value)` - Browser API for theme persistence

**This module is CALLED BY:**
- None (Entry point module)

**External Resources:**
- Font: System font stack (Inter preferred if available)
- No external CSS frameworks
- No external JavaScript libraries

---

## 4. DATA STRUCTURES

### Theme Configuration Object
```javascript
const THEME_CONFIG = {
  DARK: 'dark',
  LIGHT: 'light',
  STORAGE_KEY: 'ps_rcs_theme_preference'
};
```

### Module Status Map
```javascript
const MODULE_STATUS_TYPES = {
  ONLINE: 'online',
  OFFLINE: 'offline',
  STANDBY: 'standby'
};
```

### Valid Module Names
```javascript
const VALID_MODULES = ['motor', 'lidar', 'camera', 'ocr'];
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

**From `system_constraints.md`:**

1. **Dual Theme Requirement:** Must implement both Industrial Dark and Medical Light themes with toggle
2. **Professional Aesthetic:** No neon glows, cyberpunk terminology, or Orbitron font
3. **Typography:** Must use Inter, Roboto, or system sans-serif
4. **JSON Protocol:** All API communication must use `application/json`
5. **Non-Blocking:** Status polling must not block UI interactions
6. **Legacy Compatibility:** Must consume API structure from API_MAP_LITE (maintain `success`, `mode`, `battery_voltage` keys)

**Additional Technical Constraints:**

7. **CSS Variables Only:** No hardcoded colors; all theming via custom properties
8. **Semantic HTML:** Use proper HTML5 semantic elements (`<header>`, `<main>`, `<section>`)
9. **Accessibility:** All interactive elements must have ARIA labels
10. **Grid Extensibility:** New modules added by appending `<section>` elements without structural changes

---

## 6. MEMORY COMPLIANCE

**No `_memory_snippet.txt` provided - no historical rules to apply.**

**Future Memory Integration Points:**
- Theme preference persistence behavior
- Module card layout patterns
- Status badge color mappings
- Grid breakpoint definitions

---

## 7. ACCEPTANCE CRITERIA

### Test Case 1: Theme Toggle
- **Input:** User clicks `#theme-toggle` button
- **Expected Output:** 
  - DOM attribute changes to `<body data-theme="light">`
  - All CSS variables update to light theme values
  - localStorage contains `ps_rcs_theme_preference: 'light'`
- **Expected Behavior:** Visual transition completes within 100ms

### Test Case 2: Module Status Update (Online)
- **Input:** `dashboard.updateModuleStatus('lidar', 'online')`
- **Expected Output:** 
  - Element `#lidar-status` has `data-status="online"`
  - Badge displays "ONLINE" text
  - Badge background is `--accent-success` (green)
- **Expected Behavior:** Returns `true`

### Test Case 3: Module Status Update (Invalid Module)
- **Input:** `dashboard.updateModuleStatus('invalid', 'online')`
- **Expected Exception:** `Error`
- **Expected Message:** "Invalid module name: invalid"

### Test Case 4: Theme Persistence
- **Input:** 
  1. User toggles to light theme
  2. Browser page reload
- **Expected Output:**
  - Dashboard loads with `data-theme="light"`
  - Theme toggle button shows dark mode icon
- **Expected Behavior:** Theme persists across sessions

### Test Case 5: Status Polling Integration
- **Input:** Backend `/api/status` returns:
  ```json
  {
    "mode": "manual",
    "battery_voltage": 11.8,
    "connections": {
      "motor": true,
      "lidar": false,
      "camera": false
    }
  }
  ```
- **Expected Output:**
  - Motor status badge: "ONLINE"
  - Lidar status badge: "OFFLINE"
  - Camera status badge: "OFFLINE"
  - Battery display: "11.8V"
  - Connection indicator: Partial (1/3 connected)
- **Expected Behavior:** Updates occur within 100ms of response

### Test Case 6: Grid Responsiveness
- **Input:** Browser viewport resized to 768px width
- **Expected Output:**
  - Grid collapses to single column
  - All cards remain fully visible
  - No horizontal scrolling
- **Expected Behavior:** Layout reflows smoothly

### Test Case 7: Placeholder Card Behavior
- **Input:** User hovers over `#lidar-card.placeholder`
- **Expected Output:**
  - Box shadow increases (--shadow-md)
  - Cursor: pointer
  - No expansion/modal (not implemented yet)
- **Expected Behavior:** Visual feedback only

---

## 8. INTEGRATION NOTES

**Flask Route Requirements:**
```python
@app.route('/')
def dashboard():
    """Render service dashboard."""
    initial_status = hardware_manager.get_status()
    return render_template(
        'service_dashboard.html',
        initial_status=initial_status,
        app_version='4.0'
    )
```

**File Dependencies:**
- Template depends on: `static/css/service_theme.css`
- Template depends on: `static/js/dashboard-core.js`
- JavaScript depends on: `/api/status` endpoint (API_MAP_LITE)

**Future Extension Points:**
1. **Lidar Visualizer:** Replace `.placeholder-content` with canvas element
2. **Camera Feed:** Replace with `<video>` or WebRTC stream
3. **OCR Logs:** Replace with scrollable log table component
4. **Modal System:** Add overlay for expanded module views

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:** 
1. `templates/service_dashboard.html`
2. `static/css/service_theme.css`
3. `static/js/dashboard-core.js`

**Contract Reference:** `docs/contracts/service_dashboard.md` v1.0

---

## Strict Constraints (NON-NEGOTIABLE)

1. **Dual Theme Requirement:** MUST implement both dark and light themes using CSS variables
2. **No External Dependencies:** No Bootstrap, Tailwind, jQuery, or any external libraries
3. **Semantic HTML5:** Use proper semantic tags (`<header>`, `<main>`, `<section>`, `<button>`)
4. **Accessibility:** All interactive elements require `aria-label` or `aria-labelledby`
5. **CSS Variables Only:** Zero hardcoded colors; all theming via custom properties
6. **Grid Flexibility:** Layout must accommodate 1-4 cards per row based on viewport
7. **Professional Aesthetic:** Clean, minimalist, SaaS/industrial look (no neon, no cyberpunk)
8. **API Contract Adherence:** JavaScript must consume exact structure from API_MAP_LITE `/api/status`

---

## Memory Compliance (MANDATORY)

**No historical memory rules provided.** Implementer should create clean-slate implementation following contract specifications.

---

## Required Logic

### HTML Implementation (`service_dashboard.html`)
1. Create `<!DOCTYPE html>` with lang="en"
2. Include `<meta name="viewport">` for responsive design
3. Link `/static/css/service_theme.css` in `<head>`
4. Implement exact HTML structure from Section 2.1 contract
5. Ensure all required IDs are present
6. Add ARIA labels to all buttons
7. Include Flask template variables: `{{ initial_status }}`, `{{ app_version }}`
8. Link `/static/js/dashboard-core.js` at end of `<body>`

### CSS Implementation (`service_theme.css`)
1. Define `:root[data-theme="dark"]` with all required custom properties
2. Define `:root[data-theme="light"]` with all required custom properties
3. Implement `.status-bar` layout (flexbox)
4. Implement `.service-grid` layout (CSS Grid with auto-fit)
5. Implement `.service-card` base styles
6. Implement `.service-card.active` variant
7. Implement `.service-card.placeholder` variant
8. Implement `.module-status-badge` with status attribute selectors
9. Define spacing system (--spacing-* variables)
10. Define typography (system font stack)
11. Add smooth transitions for theme changes
12. Ensure responsive breakpoints (< 768px single column)

### JavaScript Implementation (`dashboard-core.js`)
1. Define `DashboardCore` class with all methods from contract
2. Implement constructor with property initialization
3. Implement `init()` method:
   - Load theme preference
   - Attach theme toggle event listener
   - Start status polling
4. Implement `toggleTheme()`:
   - Toggle state
   - Update DOM `data-theme` attribute
   - Save to localStorage
   - Dispatch `themeChanged` event
5. Implement `updateModuleStatus()`:
   - Validate inputs
   - Query DOM element
   - Update `data-status` attribute
   - Update text content
6. Implement `startStatusPolling()`:
   - Use `setInterval` with default 2000ms
   - Fetch `/api/status`
   - Call `_processStatusUpdate()`
7. Implement `_processStatusUpdate()`:
   - Map connections to module status updates
   - Update battery display
   - Update connection indicator
8. Add error handling for all async operations
9. Instantiate and initialize on `DOMContentLoaded`

---

## Integration Points

**Must integrate with:**
- **Backend Flask Route:** Expects template to receive `initial_status` and `app_version`
- **API Endpoint:** JavaScript polls `GET /api/status` from API_MAP_LITE
- **Browser APIs:** `localStorage` for theme persistence, `fetch` for HTTP requests

**File Structure:**
```
PS_RCS_PROJECT/
├── templates/
│   └── service_dashboard.html
├── static/
│   ├── css/
│   │   └── service_theme.css
│   └── js/
│       └── dashboard-core.js
└── backend/
    └── app.py (calls render_template)
```

---

## Success Criteria

1. ✅ All HTML elements have required IDs from contract
2. ✅ Both themes render correctly with distinct color schemes
3. ✅ Theme toggle persists across page reloads
4. ✅ All 7 acceptance test cases pass
5. ✅ No console errors on page load
6. ✅ Status polling updates UI every 2 seconds
7. ✅ Grid layout responds to viewport changes
8. ✅ Lighthouse accessibility score > 90
9. ✅ CSS file size < 15KB
10. ✅ JavaScript executes without external dependencies
11. ✅ Auditor approval on code review

---

## Post-Implementation Checklist

- [ ] HTML validates with W3C validator
- [ ] CSS has zero hardcoded colors
- [ ] JavaScript passes ESLint with no errors
- [ ] All ARIA labels present
- [ ] Theme transitions are smooth (< 100ms)
- [ ] Module status updates work for all 4 modules
- [ ] Battery display shows voltage with 1 decimal place
- [ ] Connection indicator reflects actual hardware state
- [ ] Placeholder cards show correct "Offline"/"Standby" states
- [ ] No browser console warnings

---

✅ **Contract Created:** `docs/contracts/service_dashboard.md`  
📋 **Work Order Generated** for Implementer  
🔍 **Next Verification Command:** `/verify-context: system_constraints.md, API_MAP_LITE.md, contracts/service_dashboard.md`  
👉 **Next Agent:** Implementer (AGENTS/02_implementer.md)  

**Critical Notes for Implementer:**
- The HTML structure is the foundation - get IDs right first
- CSS variables enable instant theme switching - define them completely
- JavaScript class should be instantiable for future testing
- Placeholder cards are semantic containers for future heavy modules
- Keep it minimal - this is a professional dashboard, not a flashy demo