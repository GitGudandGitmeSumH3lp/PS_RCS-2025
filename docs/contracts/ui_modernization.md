# CONTRACT: UI MODERNIZATION SYSTEM
**Version:** 1.0
**Last Updated:** January 23, 2026
**Status:** Draft

## 1. PURPOSE

This contract defines the interface between the legacy "Neural Network" sci-fi themed UI and the new "Project Aether" enterprise-grade professional interface. The modernization preserves all functional DOM structure and JavaScript integration points while completely replacing visual presentation from cyberpunk aesthetics to modern SaaS design patterns.

---

## 2. PUBLIC INTERFACE

### 2.1 CSS Variable Contract

**Signature:**
```css
:root {
    /* Typography System */
    --font-main: string;
    --font-mono: string;
    
    /* Brand Color Palette */
    --primary-brand: hex-color;
    --primary-hover: hex-color;
    --accent-teal: hex-color;
    
    /* Functional Status Colors */
    --success-green: hex-color;
    --warning-amber: hex-color;
    --danger-red: hex-color;
    --neutral-gray: hex-color;
    
    /* Surface & Background System */
    --bg-body: hex-color;
    --bg-surface: hex-color;
    --bg-sidebar: hex-color;
    --border-light: hex-color;
    
    /* Text Hierarchy */
    --text-primary: hex-color;
    --text-secondary: hex-color;
    --text-muted: hex-color;
    
    /* Elevation System (Material Design Inspired) */
    --shadow-sm: box-shadow-value;
    --shadow-md: box-shadow-value;
    --shadow-lg: box-shadow-value;
    
    /* Layout Constants */
    --radius-md: pixel-value;
    --radius-lg: pixel-value;
}
```

**Behavior Specification:**
- **Input Validation:** All color values MUST be valid hex codes (#RRGGBB format)
- **Processing Logic:** CSS variables cascade through entire document; changes affect all dependent components
- **Output Guarantee:** Variable references (e.g., `var(--primary-brand)`) resolve to defined values
- **Side Effects:** Global theme changes; affects all styled elements

**Error Handling:**
- **Invalid hex color:** Browser ignores declaration → Fallback to browser defaults
- **Missing variable reference:** Browser treats as invalid → Property ignored

**Performance Requirements:**
- Time Complexity: O(1) variable lookup
- Space Complexity: O(1) per variable definition

---

### 2.2 Class Migration Map

**Signature:**
```typescript
interface ClassMigration {
    legacy: string;           // Old sci-fi class name
    modern: string;           // New enterprise class name
    purpose: string;          // Semantic description
    visualChange: string;     // Key visual transformation
    jsDependent: boolean;     // Whether JS selectors rely on this class
}

const MIGRATION_MAP: ClassMigration[] = [...]
```

**Behavior Specification:**
- **Input Validation:** All legacy class names MUST exist in current `index.html`
- **Processing Logic:** One-to-one mapping; no class should map to multiple targets
- **Output Guarantee:** Complete coverage of all styled elements in HTML
- **Side Effects:** HTML class attributes change; CSS selectors must update accordingly

**Error Handling:**
- **Unmapped legacy class:** Visual regression → Element loses styling
- **Duplicate modern class:** CSS specificity conflicts → Unpredictable rendering
- **JS selector breakage:** Runtime errors → Feature failure

**Performance Requirements:**
- Time Complexity: O(n) where n = number of class attributes in HTML
- Space Complexity: O(m) where m = number of unique class names

---

### 2.3 Component Refactoring Contract

#### Method: `refactor_card_component`

**Signature:**
```css
.card {
    background: var(--bg-surface);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    padding: length-value;
    transition: box-shadow duration ease;
}

.card:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(negative-pixel-value);
}
```

**Behavior Specification:**
- **Input Validation:** Padding MUST be in rem units; transform MUST use negative Y values
- **Processing Logic:** Hover state creates "lift" effect via shadow increase + Y-axis translation
- **Output Guarantee:** Consistent card appearance across all instances
- **Side Effects:** Replaces `.holo-panel`, `.quantum-chart`, `.neural-stats` styling

**Error Handling:**
- **Missing CSS variables:** Fallback to browser defaults → Broken visual hierarchy
- **Invalid transition duration:** Animation disabled → No smooth state changes

---

#### Method: `refactor_button_component`

**Signature:**
```css
.btn-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: length-value length-value;
    background-color: var(--primary-brand);
    color: color-value;
    font-weight: numeric-value;
    border-radius: var(--radius-md);
    border: none;
    cursor: pointer;
    transition: background-color duration;
}

.btn-primary:hover {
    background-color: var(--primary-hover);
}

.btn-primary:focus {
    outline: pixel-value solid var(--primary-brand);
    outline-offset: pixel-value;
}
```

**Behavior Specification:**
- **Input Validation:** Font-weight MUST be 400-700 range; padding MUST use rem units
- **Processing Logic:** Flexbox centering ensures icon+text alignment; focus state ensures accessibility
- **Output Guarantee:** WCAG 2.1 AA compliant focus indicators
- **Side Effects:** Replaces `.neural-button` styling; JS selectors remain functional via attribute selectors

**Error Handling:**
- **Missing focus state:** Accessibility violation → Keyboard navigation broken
- **Invalid color contrast:** WCAG failure → Readability issues

---

### 2.4 JavaScript Integration Preservation Contract

**Signature:**
```typescript
interface JSIntegrationPoint {
    selector: string;              // CSS selector used in neural-core.js
    currentClass: string;          // Legacy class name
    newClass: string;              // Modern class name
    selectorType: 'class' | 'attribute' | 'id';
    mustPreserve: boolean;         // Whether selector MUST remain unchanged
}

const JS_DEPENDENCIES: JSIntegrationPoint[] = [
    {
        selector: '.neural-button[data-command]',
        currentClass: 'neural-button',
        newClass: 'btn-primary',
        selectorType: 'attribute',
        mustPreserve: true  // Attribute selector still works after class rename
    },
    {
        selector: '#camera-feed',
        currentClass: 'quantum-camera',
        newClass: 'media-frame',
        selectorType: 'id',
        mustPreserve: true  // ID selector unaffected by class change
    },
    {
        selector: '.control-matrix',
        currentClass: 'control-matrix',
        newClass: 'control-pad',
        selectorType: 'class',
        mustPreserve: false  // Must update JS if this selector is used
    }
]
```

**Behavior Specification:**
- **Input Validation:** All `mustPreserve: true` items MUST have selector types that survive class changes
- **Processing Logic:** Identify all JS selectors; determine which are safe to modify
- **Output Guarantee:** Zero JavaScript runtime errors after CSS migration
- **Side Effects:** May require `neural-core.js` updates if class selectors are used

**Error Handling:**
- **Breaking selector change:** `querySelector` returns null → Event listeners not attached → Feature fails
- **Ambiguous selector:** Multiple elements match → Unexpected behavior

---

## 3. DEPENDENCIES

**This module CALLS:**
- None (Pure CSS transformation)

**This module is CALLED BY:**
- `index.html` - Consumes CSS classes and variables
- `neural-core.js` - Queries DOM elements via class/ID selectors
- Chart.js configuration - Uses CSS variables for theming

**External Dependencies:**
- Google Fonts API (if loading Inter font externally)
- Browser CSS engine

---

## 4. DATA STRUCTURES

### ClassMigrationTable
```typescript
type ClassMigrationTable = {
    legacy: string;
    modern: string;
    purpose: string;
    visualChange: string;
    jsImpact: 'SAFE' | 'VERIFY' | 'BREAKING';
}[];
```

### CSSVariableSet
```typescript
interface CSSVariableSet {
    typography: {
        fontMain: string;
        fontMono: string;
    };
    colors: {
        brand: { primary: string; hover: string; };
        functional: { success: string; warning: string; danger: string; };
        surfaces: { body: string; surface: string; border: string; };
        text: { primary: string; secondary: string; muted: string; };
    };
    elevation: {
        shadowSm: string;
        shadowMd: string;
        shadowLg: string;
    };
    layout: {
        radiusMd: string;
        radiusLg: string;
    };
}
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

1. **DOM Structure Preservation:** Grid layout (3 columns: 1fr) MUST remain intact
2. **Control Matrix Layout:** D-Pad structure MUST be preserved for JS event handling
3. **No Breaking Changes:** All `data-command` attributes MUST remain functional
4. **Accessibility Mandate:** Focus states MUST be visible and pass WCAG 2.1 AA
5. **Performance:** No CSS animations consuming >5% CPU (removes particle background)
6. **Browser Support:** CSS MUST work in Chrome 90+, Firefox 88+, Safari 14+

---

## 6. MEMORY COMPLIANCE

**Applied Rules:**
- N/A (No `_memory_snippet.txt` provided in this engagement)

---

## 7. ACCEPTANCE CRITERIA

### Test Case 1: CSS Variable Resolution
- **Input:** Browser loads new `enterprise-theme.css`
- **Expected Output:** All `var(--*)` references resolve to defined values
- **Expected Behavior:** No console warnings about invalid CSS properties

### Test Case 2: Visual Regression (Cards)
- **Input:** Elements with old `.holo-panel` class renamed to `.card`
- **Expected Output:** White background, subtle shadow, 12px border radius
- **Expected Behavior:** Hover state shows increased shadow + 2px Y-axis lift

### Test Case 3: Button Functionality
- **Input:** Click `.btn-primary[data-command="capture"]`
- **Expected Output:** JS event handler fires correctly
- **Expected Behavior:** Camera capture initiates (no errors in console)

### Test Case 4: Focus Accessibility
- **Input:** Tab through interactive elements
- **Expected Output:** 2px blue outline visible on focused elements
- **Expected Behavior:** Outline offset = 2px; no browser default outline

### Test Case 5: Chart.js Theme Integration
- **Input:** Chart renders after CSS update
- **Expected Output:** Transparent background, `#E5E7EB` grid lines, `#111827` text
- **Expected Behavior:** No visual artifacts; text is readable

### Test Case 6: JavaScript Selector Integrity
- **Input:** Run `document.querySelectorAll('.neural-button[data-command]')`
- **Expected Output:** Returns NodeList of all control buttons
- **Expected Behavior:** Event listeners attach successfully (even after class rename to `.btn-primary`)

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:** 
- `static/css/enterprise-theme.css` (NEW - replaces `neural-theme.css`)
- `index.html` (CLASS NAME UPDATES ONLY)
- `static/js/neural-core.js` (VERIFY Chart.js config - may need updates)

**Contract Reference:** `docs/contracts/ui_modernization.md` v1.0

---

## Strict Constraints (NON-NEGOTIABLE)

1. **Zero Breaking Changes to JS:** All `data-command` selectors MUST remain functional
2. **DOM Structure Immutable:** Do NOT change grid layout or control matrix HTML structure
3. **Delete Legacy Animations:** Remove `@keyframes scan`, `@keyframes float`, `@keyframes pulse-brain`, `body::before` particle layer
4. **WCAG 2.1 AA Compliance:** All interactive elements MUST have visible focus states
5. **No External Font CDN (Optional):** If Inter font unavailable, fallback to system font stack works
6. **Backup First:** Rename `neural-theme.css` to `neural-theme.css.backup` before deploying new file

---

## Memory Compliance (MANDATORY)
- N/A (No memory rules provided)

---

## Required Logic

### Step 1: Create New CSS File
1. Create `static/css/enterprise-theme.css`
2. Copy the entire CSS Variable Set from Spec Section 2 into `:root` block
3. Add global resets for typography smoothing
4. Implement `.card` component class (Section 4C of spec)
5. Implement `.btn-primary` component class (Section 4D of spec)
6. Add focus state styles for accessibility

### Step 2: Update HTML Class Names
Perform find/replace in `index.html` using this exact mapping:

| **Find (Old Class)** | **Replace (New Class)** | **JS Impact** |
|:---|:---|:---|
| `neural-header` | `app-header` | ✅ SAFE (no JS references) |
| `system-title` | `brand-title` | ✅ SAFE |
| `brain-indicator` | `system-status-badge` | ⚠️ VERIFY (check if JS updates this) |
| `nav-node` | `nav-link` | ✅ SAFE |
| `holo-panel` | `card` | ✅ SAFE |
| `quantum-camera` | `media-frame` | ✅ SAFE (ID selector used) |
| `neural-stats` | `kpi-grid` | ✅ SAFE |
| `stat-node` | `kpi-card` | ✅ SAFE |
| `control-matrix` | `control-pad` | ⚠️ VERIFY (check JS for class selector) |
| `neural-button` | `btn-primary` | ✅ SAFE (attribute selector `[data-command]` used) |
| `quantum-chart` | `chart-container` | ✅ SAFE |

### Step 3: Update Chart.js Configuration (IF APPLICABLE)
In `neural-core.js`, locate Chart.js options object and update:

```javascript
// OLD (Dark Theme)
options: {
    plugins: {
        legend: {
            labels: { color: '#00ffff' }
        }
    },
    scales: {
        y: {
            grid: { color: 'rgba(0, 255, 255, 0.1)' },
            ticks: { color: '#00ffff' }
        }
    }
}

// NEW (Light Theme)
options: {
    plugins: {
        legend: {
            labels: { color: '#111827' }  // var(--text-primary)
        }
    },
    scales: {
        y: {
            grid: { color: '#E5E7EB' },   // var(--border-light)
            ticks: { color: '#111827' }
        }
    }
}
```

### Step 4: Remove Legacy Code
Delete the following from new CSS file:
- All `@keyframes` definitions (scan, float, pulse-brain)
- `body::before` pseudo-element (particle background)
- Any CSS rules containing `text-shadow: 0 0 10px cyan` patterns
- Any `background: linear-gradient(...)` with neon colors
- Any `border: 1px solid rgba(0, 255, 255, ...)` patterns

### Step 5: Update Link Tag in HTML
In `index.html` `<head>`:
```html
<!-- OLD -->
<link rel="stylesheet" href="/static/css/neural-theme.css">

<!-- NEW -->
<link rel="stylesheet" href="/static/css/enterprise-theme.css">
```

---

## Integration Points

**Must call:** None (pure CSS transformation)

**Will be called by:**
- Browser CSS engine on page load
- JavaScript `querySelector()` calls for DOM manipulation
- Chart.js for style inheritance

**Critical Verification:**
After deployment, test these JavaScript interactions:
1. Click any `.btn-primary[data-command]` button → Verify event fires
2. Check browser console for "Cannot read property of null" errors
3. Verify Chart renders with light theme colors
4. Tab through UI → Verify focus outlines appear

---

## Success Criteria

✅ All class names in `index.html` updated per migration table  
✅ New `enterprise-theme.css` file contains all 24 CSS variables from spec  
✅ Zero JavaScript console errors after page load  
✅ All interactive elements show 2px blue focus outline on tab navigation  
✅ Charts render with light backgrounds and dark text  
✅ `.card` elements have white background with subtle shadow  
✅ `.btn-primary` elements have blue background with hover state  
✅ Legacy animations (`@keyframes`, particles) completely removed  
✅ Page load time improved (no CPU-intensive animations)  
✅ Visual comparison matches "modern SaaS" aesthetic reference  

---

## Post-Implementation Verification Checklist

```bash
# File Existence Check
[ ] static/css/enterprise-theme.css exists
[ ] static/css/neural-theme.css.backup exists (safety copy)

# HTML Validation
[ ] All 11 class names updated in index.html
[ ] Link tag points to enterprise-theme.css
[ ] No orphaned sci-fi class names remain

# CSS Validation
[ ] :root block contains exactly 24 variables
[ ] No @keyframes blocks remain
[ ] .card and .btn-primary classes defined
[ ] Focus states defined for button:focus and a:focus

# JavaScript Validation
[ ] No console errors on page load
[ ] querySelectorAll('.btn-primary[data-command]') returns expected elements
[ ] Chart renders without errors
[ ] Click handlers on control buttons still fire

# Accessibility Validation
[ ] Tab navigation shows visible focus indicators
[ ] Color contrast passes WCAG AA (use browser DevTools checker)
```

---

## Auditor Review Points

1. **Contract Compliance:** Verify all 11 class migrations match specification
2. **No Scope Creep:** Confirm NO changes to grid layout or control matrix structure
3. **JavaScript Safety:** Run automated test suite for event handler attachment
4. **Accessibility Audit:** Use axe DevTools to verify WCAG 2.1 AA compliance
5. **Performance Check:** Verify CPU usage <5% during idle (no particle animations)

---

# POST-ACTION REPORT

✅ **Contract Created:** `docs/contracts/ui_modernization.md`  
📋 **Work Order Generated** for Implementer  
🔍 **Next Verification Command:** `/verify-context: ui_modernization.md, enterprise-theme.css, index.html, neural-core.js`  
👉 **Next Agent:** Implementer (AGENTS/02_implementer.md)  

**Critical Handoff Notes:**
- Class migration is **ONE-TO-ONE** mapping - do not merge or split classes
- JavaScript uses **attribute selectors** `[data-command]` - safe from class renames
- Chart.js config update is **OPTIONAL** if charts not yet implemented
- Focus on **visual transformation** only - no functional changes to JS logic