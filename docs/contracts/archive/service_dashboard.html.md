✅ **Context verified. Proceeding.**

---

# CONTRACT: Service Dashboard HTML Structure
**Version:** 1.0  
**Last Updated:** 2026-01-23  
**Status:** Draft  

## 1. PURPOSE
Defines the semantic HTML structure for the professional service dashboard interface. This template provides a grid-based layout with clear separation between telemetry, controls, and system logs, supporting dual-theme switching without breaking layout integrity.

## 2. PUBLIC INTERFACE

### Document Structure
**File:** `templates/service_dashboard.html`

**Required Elements:**

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PS-RCS Service Dashboard</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/service_theme.css') }}">
</head>
<body>
    <!-- Theme toggle must be in header -->
    <header id="dashboard-header"></header>
    
    <!-- Main grid container -->
    <main id="dashboard-grid"></main>
    
    <!-- Footer with status -->
    <footer id="dashboard-footer"></footer>
    
    <script src="{{ url_for('static', filename='js/dashboard-core.js') }}"></script>
</body>
</html>
```

### Element ID Contract

**Header Section:**
- `#dashboard-header` - Top navigation bar
- `#theme-toggle-btn` - Theme switcher button (must have `aria-label`)
- `#system-title` - Application title display

**Main Grid Sections:**
- `#dashboard-grid` - Primary CSS Grid container
- `#telemetry-panel` - Real-time sensor display card
- `#control-panel` - Motor control interface card
- `#logs-panel` - System event history card

**Telemetry Panel Elements:**
- `#status-mode` - Current operation mode display
- `#status-battery` - Battery voltage display
- `#status-cpu-temp` - CPU temperature display
- `#connection-motor` - Motor connection indicator
- `#connection-lidar` - Lidar connection indicator
- `#connection-camera` - Camera connection indicator

**Control Panel Elements:**
- `#speed-slider` - Speed control input (`<input type="range">`)
- `#speed-display` - Current speed value display
- `#btn-forward` - Forward movement button
- `#btn-backward` - Backward movement button
- `#btn-left` - Left turn button
- `#btn-right` - Right turn button
- `#btn-stop` - Emergency stop button

**Logs Panel Elements:**
- `#logs-container` - Scrollable log entries container
- `.log-entry` - Individual log item class
- `.log-timestamp` - Timestamp span class
- `.log-level` - Log level badge class
- `.log-message` - Log message text class

**Footer Elements:**
- `#dashboard-footer` - Status bar
- `#last-update-time` - Last telemetry update timestamp

### Data Attribute Contract

**Theme Switching:**
- `<html data-theme="dark">` - Default state
- `<html data-theme="light">` - Light mode state

**Connection States:**
- `<span class="status-indicator" data-connected="true">` - Active connection
- `<span class="status-indicator" data-connected="false">` - Disconnected

**Log Levels:**
- `<span class="log-level" data-level="info">` - Info messages
- `<span class="log-level" data-level="warning">` - Warning messages
- `<span class="log-level" data-level="error">` - Error messages

## 3. DEPENDENCIES

**This template REQUIRES:**
- `static/css/service_theme.css` - Styling contract
- `static/js/dashboard-core.js` - Logic contract
- Flask template context: No variables required (static dashboard)

**This template is LOADED BY:**
- Flask route `GET /` or `GET /dashboard`

## 4. LAYOUT SPECIFICATION

**Grid Structure:**
```
+----------------------------------+
|         HEADER (Theme Toggle)    |
+----------------------------------+
| TELEMETRY  | CONTROL  |  LOGS    |
|   PANEL    |  PANEL   |  PANEL   |
|            |          |          |
+----------------------------------+
|         FOOTER (Status Bar)      |
+----------------------------------+
```

**Responsive Behavior:**
- **Desktop (>1024px):** 3-column grid
- **Tablet (768-1024px):** 2-column grid (logs move below)
- **Mobile (<768px):** Single column stack

## 5. CONSTRAINTS (FROM SYSTEM RULES)

1. **No Inline Styles:** All styling via CSS classes
2. **Semantic HTML:** Use `<main>`, `<section>`, `<header>`, `<footer>` appropriately
3. **Accessibility:** All interactive elements must have ARIA labels
4. **Flask Template Syntax:** Use `{{ url_for() }}` for static file paths
5. **No "Cyberpunk" Terminology:** No "Neural", "Neon", "Orbitron" references

## 6. ACCEPTANCE CRITERIA

**Test Case 1: Theme Persistence**
- **Scenario:** User toggles theme to light mode and refreshes page
- **Expected:** Dashboard loads in light mode (reads `localStorage`)
- **Validation:** `<html data-theme="light">` attribute present on load

**Test Case 2: Grid Responsiveness**
- **Scenario:** Resize viewport from 1920px to 375px
- **Expected:** Layout shifts from 3-col → 2-col → 1-col without horizontal scroll
- **Validation:** All panels remain visible and accessible

**Test Case 3: Connection Indicators**
- **Scenario:** `/api/status` returns `{"connections": {"motor": false}}`
- **Expected:** `#connection-motor` shows red/inactive state
- **Validation:** `data-connected="false"` attribute set correctly

**Test Case 4: Accessibility**
- **Scenario:** Navigate dashboard using keyboard only
- **Expected:** All buttons reachable via Tab, theme toggle activates with Enter/Space
- **Validation:** WAVE/axe DevTools report 0 critical errors

---

