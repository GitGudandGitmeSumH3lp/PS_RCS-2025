# PS_RCS_PROJECT | System Style Guide (V4.2)

## 1. CORE PHILOSOPHY
*   **Lean V4.2:** Minimize token waste. Logic first, polish second.
*   **Contract-First:** No implementation begins without an Architect-approved Contract.
*   **Hardware Abstraction:** No direct GPIO/Serial calls outside of `src/services/`.
*   **Single Source of Truth:** `RobotState` is the only valid source for telemetry data.
*   **Progressive Disclosure:** UI Complexity is hidden by default. Information is revealed on demand (Hover/Click).
*   **Design System:** Adopt **shadcn/ui Neutral** as the foundational design language, mapped to custom CSS variables for vanilla JS compatibility. Ensure zero blue accents.

---

## 2. DESIGN TOKENS (shadcn/ui Neutral Mapping)

All visual styles MUST use the following CSS custom properties. No hardcoded hex values allowed.

```css
:root {
  /* shadcn/ui Neutral mapping (dark mode default) */
  --background: 0 0% 6%;           /* #0f0f0f */
  --foreground: 0 0% 98%;          /* #fafafa */
  --card: 0 0% 9%;                 /* #171717 */
  --card-foreground: 0 0% 98%;
  --popover: 0 0% 9%;
  --popover-foreground: 0 0% 98%;
  --primary: 0 0% 53%;             /* #888888 */
  --primary-foreground: 0 0% 98%;
  --secondary: 0 0% 15%;
  --secondary-foreground: 0 0% 98%;
  --muted: 0 0% 15%;
  --muted-foreground: 0 0% 64%;    /* #a3a3a3 */
  --accent: 0 0% 15%;
  --accent-foreground: 0 0% 98%;
  --destructive: 0 63% 31%;
  --destructive-foreground: 0 0% 98%;
  --border: 0 0% 15%;
  --input: 0 0% 15%;
  --ring: 0 0% 83%;
  
  /* Hardware status tokens */
  --status-online: 142 71% 45%;    /* #10b981 */
  --status-offline: 0 0% 45%;
  --status-standby: 38 92% 50%;
  
  /* Radius */
  --radius: 1.25rem;                /* 20px (cards) */
  --radius-lg: 1.5rem;              /* 24px (modals) */
  --radius-sm: 0.75rem;             /* 12px (buttons) */
  
  /* Effects (Pi 4B optimized) */
  --shadow-card: 0 8px 30px rgba(0,0,0,0.08);
  --blur-modal: blur(20px);
  
  /* Performance flag – set to 0 if backdrop blur causes lag */
  --enable-backdrop-blur: 1;
}

[data-theme="light"] {
  --background: 0 0% 100%;
  --foreground: 0 0% 9%;
  --card: 0 0% 98%;
  --card-foreground: 0 0% 9%;
  --primary: 0 0% 32%;
  --primary-foreground: 0 0% 98%;
  /* ... other light mappings ... */
}
```

**Critical Rule:** **NO BLUE ACCENTS** in any UI element. Use neutral grays and green for success only.

---

## 3. LAYOUT & COMPONENTS

### 3.1 Bento Grid
- Use CSS Grid with `grid-template-columns: repeat(auto-fit, minmax(300px, 1fr))` or similar.
- Grid gap: `1rem` (16px) – slightly larger than Linear but acceptable.
- Cards should occupy available space, not fixed heights.

### 3.2 Cards
- Apply `background: hsl(var(--card))`, `border: 1px solid hsl(var(--border))`, `border-radius: var(--radius)`.
- Box shadow: `var(--shadow-card)`.
- Header with icon + title + status indicator.
- Hover overlay with `Click to open` text (opacity 0 on idle, 1 on hover).

### 3.3 Modals
- Use `<dialog>` element with `::backdrop` for overlay.
- Modal container: `background: hsl(var(--background) / 0.8)` with `backdrop-filter: var(--blur-modal)` if performance allows.
- Border radius: `var(--radius-lg)`.
- Close button: `btn-ghost` style.

### 3.4 Buttons
- Primary: `background: hsl(var(--primary))`, `color: hsl(var(--primary-foreground))`, `border-radius: var(--radius-sm)`.
- Secondary: `background: transparent`, `border: 1px solid hsl(var(--border))`.
- Ghost: `background: transparent`, `border: none`.
- All buttons must have `min-height: 44px`, `min-width: 44px` for touch targets.

### 3.5 Status Indicators
- Dot + text combo.
- Dot colors: `online: hsl(var(--status-online))`, `offline: hsl(var(--status-offline))`, `standby: hsl(var(--status-standby))`.
- Use `aria-live="polite"` for dynamic updates.

---

## 4. PYTHON STANDARDS (Backend)

*   **Standard:** PEP 8.
*   **Indentation:** 4 Spaces.
*   **Naming:** 
    *   Classes: `PascalCase`
    *   Functions/Variables: `snake_case`
    *   Constants: `UPPER_SNAKE_CASE`
*   **Documentation:** Google-style Docstrings (MANDATORY for Refiner).
*   **Type Hinting:** Required for all function signatures and class attributes.
*   **Error Handling:** Use specific exceptions; avoid generic `except Exception`.
*   **Concurrency:** `threading` ONLY. No `asyncio` (compatibility with legacy serial/SMBus libraries).

---

## 5. JAVASCRIPT STANDARDS (Frontend)

*   **Standard:** ES6+ Vanilla JS (No jQuery/external frameworks unless specified).
*   **Indentation:** 2 Spaces.
*   **Naming:** 
    *   Classes: `PascalCase`
    *   Methods/Variables: `camelCase`
*   **Documentation:** JSDoc for all class methods.
*   **Structure:** Class-based logic encapsulated in `static/js/`.
*   **Component Pattern:** Each UI module (e.g., VisionPanel, LiDARPanel) should be a separate class in its own file.

---

## 6. FILE HEADERS

All source files must begin with the standard project header:

```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: [filename]
Description: [brief description]
"""
```

For JavaScript files, use `/* ... */` style comments.

---

## 7. PROJECT DIRECTORY STRUCTURE

```
src/
├── core/         # Logic, State, Config
├── services/     # Hardware Managers, Drivers
├── api/          # Flask Server, Routes
├── hardware/     # Hardware adapters (camera, lidar, motor)
└── database/     # SQLAlchemy models, repositories

frontend/
├── templates/    # Jinja2 HTML (service_dashboard.html)
├── static/
│   ├── css/
│   │   ├── tokens.css            # Design tokens (HSL variables)
│   │   ├── base.css               # Global resets
│   │   ├── components/            # Component-specific CSS
│   │   │   ├── card.css
│   │   │   ├── button.css
│   │   │   └── dialog.css
│   │   └── utilities.css          # Tailwind-like utilities
│   └── js/
│       ├── dashboard-core.js      # Main orchestrator
│       ├── vision-panel.js        # Camera panel
│       ├── ocr-panel.js           # OCR scanner
│       ├── lidar-panel.js         # LiDAR visualization (NEW)
│       └── components/             # Reusable vanilla JS components
└── themes/
    └── neutral.json                # shadcn theme export (reference)
```

---

## 8. FORBIDDEN PATTERNS (Global)

### 🔴 Security & Safety
- No `os.system`: Use `subprocess.run` with list arguments.
- No `eval()` / `exec()`: Absolute ban.
- No Hardcoded Secrets: API keys/Passwords must use Environment Variables or Config files.
- No Hardcoded Paths: Use `os.path.join` or `pathlib`.

### 🔴 Code Quality
- **Max Function Length (Python & JavaScript):** 50 lines. Refactor if longer.
- **Type Hints:** Mandatory for all Python Backend functions.
- **Docstrings:** Google-style docstrings required for all public classes/methods.
- **No Async in Backend:** `threading` only. If async is unavoidable, use Quart instead of Flask (requires full migration).

### 🔴 Design Violations
- **NO BLUE ACCENTS** – any shade of blue is forbidden in UI.
- **No hardcoded colors** – all colors must come from CSS variables.
- **No neon glows** – maintain industrial/minimalist aesthetic.

---

## 9. ACCESSIBILITY & PERFORMANCE

### 9.1 Accessibility (WCAG AA)
- Color contrast ≥ 4.5:1 for text.
- Touch targets ≥ 44x44 pixels.
- All interactive elements keyboard navigable.
- ARIA labels where needed (`aria-label`, `aria-live` for dynamic updates).

### 9.2 Performance (Raspberry Pi 4B)
- UI response to user input: <100 ms.
- Camera overlay frame latency: <16 ms (60 fps capable).
- History load time: <500 ms for 50 records.
- Backdrop blur enabled only if `--enable-backdrop-blur: 1` and performance allows.
- Use `performance.mark()` and `performance.measure()` to monitor critical paths (PerfMonitor in `ocr-panel.js`).

---

## 10. VERSION HISTORY

- **v4.2 (2026-02-24):** Adopted shadcn/ui Neutral design tokens. Updated style guide with token mappings, layout rules, and performance guidelines. Integrated findings from Comprehensive Orchestration Report.

*(Previous versions omitted for brevity)*

---

*This document is the single source of truth for all frontend styling and backend code conventions. Violations trigger automatic audit failure.*