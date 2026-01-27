
# CONTRACT: Service Dashboard CSS Theme System
**Version:** 1.0  
**Last Updated:** 2026-01-23  
**Status:** Draft  

## 1. PURPOSE
Provides a dual-theme styling system using CSS custom properties. Defines visual appearance for Industrial Dark (default) and Medical Light themes while maintaining professional aesthetics and ensuring smooth theme transitions.

## 2. PUBLIC INTERFACE

### CSS Variables Declaration
**File:** `static/css/service_theme.css`

**Root Theme (Industrial Dark):**
```css
:root {
  /* Color Palette */
  --bg-primary: #1e293b;        /* Slate grey background */
  --bg-secondary: #334155;      /* Card backgrounds */
  --bg-tertiary: #475569;       /* Hover states */
  
  --text-primary: #f8fafc;      /* White text */
  --text-secondary: #cbd5e1;    /* Muted text */
  --text-tertiary: #94a3b8;     /* Placeholder text */
  
  --accent-primary: #3b82f6;    /* Blue accent (buttons) */
  --accent-success: #10b981;    /* Green (connected) */
  --accent-warning: #f59e0b;    /* Orange (warning) */
  --accent-error: #ef4444;      /* Red (error/disconnected) */
  
  --border-color: #475569;      /* Subtle borders */
  --shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  
  /* Typography */
  --font-family: 'Inter', 'Roboto', -apple-system, sans-serif;
  --font-size-base: 16px;
  --font-size-lg: 18px;
  --font-size-sm: 14px;
  
  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  
  /* Layout */
  --border-radius: 8px;
  --transition-speed: 0.3s;
}
```

**Light Theme Override:**
```css
[data-theme="light"] {
  --bg-primary: #f8fafc;        /* Off-white background */
  --bg-secondary: #ffffff;      /* Pure white cards */
  --bg-tertiary: #e2e8f0;       /* Hover states */
  
  --text-primary: #1e293b;      /* Dark grey text */
  --text-secondary: #475569;    /* Medium grey */
  --text-tertiary: #64748b;     /* Light grey */
  
  --border-color: #cbd5e1;      /* Visible borders */
  --shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
  
  /* Accent colors remain same for consistency */
}
```

### Required CSS Classes

**Layout Classes:**
- `.dashboard-grid` - CSS Grid container for main panels
- `.panel` - Base card styling (shadow, padding, border-radius)
- `.panel-header` - Panel title section
- `.panel-body` - Panel content area

**Component Classes:**
- `.btn-primary` - Primary action buttons (blue accent)
- `.btn-danger` - Stop/emergency button (red)
- `.status-indicator` - Connection status dot (uses `data-connected` attribute)
- `.theme-toggle` - Theme switcher button styling

**Typography Classes:**
- `.text-primary` - Primary text color
- `.text-secondary` - Muted text color
- `.text-mono` - Monospace font (for sensor values)

**State Classes:**
- `.connected` - Active connection state (green)
- `.disconnected` - Inactive connection state (red)
- `.log-level--info` - Info log styling
- `.log-level--warning` - Warning log styling
- `.log-level--error` - Error log styling

### Responsive Breakpoints

**Specification:**
```css
/* Mobile First */
@media (min-width: 768px) {
  /* Tablet layout */
  .dashboard-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  /* Desktop layout */
  .dashboard-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
```

## 3. DEPENDENCIES

**This stylesheet USES:**
- Google Fonts CDN (optional) for Inter or Roboto
- No external CSS frameworks (Bootstrap, Tailwind forbidden)

**This stylesheet is LOADED BY:**
- `templates/service_dashboard.html`

## 4. BEHAVIOR SPECIFICATION

**Theme Switching:**
- When `<html data-theme="light">` is set, all `var(--*)` references automatically use light theme values
- Transition time: `0.3s ease` for background and color changes
- No JavaScript required for color switching (pure CSS)

**Performance Requirements:**
- CSS file size: < 15KB uncompressed
- No `@import` statements (all CSS in one file)
- Critical CSS should be inline in `<head>` (optional optimization)

## 5. CONSTRAINTS (FROM SYSTEM RULES)

1. **Forbidden Fonts:** No "Orbitron", no decorative/script fonts
2. **Forbidden Colors:** No neon cyan (#00fff0), no "cyberpunk" palette
3. **Forbidden Effects:** No text-shadow glows, no pulsing animations
4. **Required:** Inter or Roboto font family
5. **Accessibility:** Text contrast ratio must meet WCAG AA (4.5:1 minimum)

## 6. ACCEPTANCE CRITERIA

**Test Case 1: Theme Variables**
- **Scenario:** Inspect `--bg-primary` in DevTools while in dark mode
- **Expected:** Value is `#1e293b`
- **Validation:** Switch to light mode → value becomes `#f8fafc`

**Test Case 2: Contrast Compliance**
- **Scenario:** Run WAVE contrast checker on dark theme
- **Expected:** All text passes WCAG AA (4.5:1)
- **Validation:** Light theme also passes

**Test Case 3: Transition Smoothness**
- **Scenario:** Toggle theme switch rapidly 5 times
- **Expected:** No color flashing, smooth 0.3s transitions
- **Validation:** No layout shift or jank

**Test Case 4: CSS Isolation**
- **Scenario:** Load dashboard in browser with existing stylesheets
- **Expected:** No style conflicts (all classes are scoped)
- **Validation:** No `!important` flags needed

---