```markdown
# FEATURE SPEC: UI Refinement & Icon Navigation
**Date:** 2025-01-24
**Status:** Feasible
**Target File:** `docs/specs/ui_refinement_spec.md`

## 1. DESIGN PRINCIPLES (Icon-First)
*   **Philosophy:** "Content over Chrome." Remove text labels where symbols suffice.
*   **Typography:** `Inter` (Variable). Minimal text usage.
    *   *Tooltips:* 12px Medium (tracking +0.02em).
    *   *Data:* 14px Monospace (for logs/stats).
*   **Color Palette (Monochromatic Dark):**
    *   `--bg-app`: `#0F0F0F` (Deep matte black).
    *   `--bg-card`: `#1A1A1A` (Slightly lighter).
    *   `--bg-hover`: `#262626` (Interactive state).
    *   `--text-primary`: `#EDEDED`.
    *   `--text-dim`: `#6E6E6E`.
    *   `--border-subtle`: `#333333`.
*   **Spacing:** Strict 8px grid. Cards have `p-24` (24px padding). Gap `24px`.
*   **Depth:**
    *   *Idle:* No shadow, 1px subtle border.
    *   *Hover:* `0 8px 32px rgba(0,0,0,0.4)`, border color lightens.

## 2. COMPONENT INVENTORY

### A. Global Navigation (The Grid)
*   **Refinement:** Convert text-heavy cards to **Icon Cards**.
*   **Interaction:** Hovering a card reveals its label via a custom tooltip or subtle slide-up text.

### B. Theme Toggle (Repair)
*   **Current State:** Broken/Unsynced.
*   **Target:** Simple Sun/Moon icon toggle.
*   **Logic:** Defaults to `dark`. Checks `localStorage`. Toggles `data-theme` on `<html>`.

### C. Vision Modal (Enhanced)
*   **New Feature:** **High-Res Capture**.
*   **Controls:**
    *   [ 📸 ] Capture (Left)
    *   [ 🔍 ] Scan (Right)
*   **Feedback:** Capture flashes screen white (CSS animation) -> Shows preview overlay.

## 3. ICON SYSTEM SPECIFICATION
*   *Style:* 2px stroke, rounded caps/joins, hollow centers (Linear style).
*   *Size:* 48x48px (Card Centers), 24x24px (Buttons).
*   *Mapping:*
    *   **Vision Card:** `video-camera` (📹)
    *   **Control/Movement:** `adjustments-horizontal` (🎚️)
    *   **System Health:** `cpu-chip` or `shield-check` (🛡️)
    *   **Action - Capture:** `camera-shutter` (📸)
    *   **Action - Scan:** `viewfinder-circle` (🎯)

## 4. USER JOURNEY MAP

### Phase 1: Dashboard (Idle)
*   User sees a clean grid of icons on a matte black background.
*   User hovers over the **Camera Icon**.
*   Card background lightens (`#262626`), Tooltip "Vision System" appears.

### Phase 2: Interaction (Vision)
*   User clicks **Camera Icon**.
*   Modal fades in (`opacity: 0 -> 1`, `scale: 0.95 -> 1`).
*   Live stream (320x240) loads.

### Phase 3: High-Res Capture
*   User clicks **Shutter Icon** (📸).
*   **Frontend:** Disables button, adds "processing" state.
*   **Backend:** Attempts to grab high-res frame (see Risks). Saves to `data/captures/`.
*   **Frontend:** Receives URL, displays "Photo Saved" toast, and shows a thumbnail preview.

### Phase 4: Theme Switching
*   User clicks **Moon/Sun Icon** in top-right.
*   Application instantly inverts colors (CSS Variables swap).
*   Preference saved to disk.

## 5. TECHNICAL REQUIREMENTS

### HTML Structure (`service_dashboard.html`)
```html
<!-- Example Icon Card -->
<div class="icon-card" data-tooltip="Vision System" onclick="visionPanel.open()">
    <svg class="hero-icon">...</svg> <!-- 48px SVG -->
</div>
```

### CSS Architecture (`dashboard.css`)
*   **Tooltips:** CSS-only implementation using `[data-tooltip]:hover::after`.
*   **Flash Animation:** `@keyframes flash { 0% { opacity: 0.8; background: white; } 100% { opacity: 0; } }`.

### JavaScript Logic
*   **Module:** `ThemeController.js` (New atomic module).
    *   `toggle()`: Swaps class, writes to localStorage.
    *   `init()`: Reads localStorage, applies class.
*   **Module:** `VisionPanel.js` (Update).
    *   `captureHighRes()`: POST `/api/vision/capture`.
    *   `handleCaptureSuccess(url)`: Show preview image in modal.

### Backend Endpoints (`routes/vision_routes.py`)
*   `POST /api/vision/capture`:
    *   Triggers `VisionManager.capture_snapshot(high_res=True)`.
    *   Returns: `{ "status": "ok", "url": "/captures/snapshot_123.jpg" }`.
*   `GET /captures/<filename>`:
    *   Serves static files from `data/captures/`.

## 6. ACCEPTANCE CRITERIA
*   [ ] **Aesthetic:** Dashboard uses `#0F0F0F` background and defined grayscale palette.
*   [ ] **Navigation:** Cards display large icons, no persistent text labels.
*   [ ] **Theme:** Toggle switches CSS variables and persists after refresh.
*   [ ] **Vision:** Modal includes a "Capture" button (Camera Icon).
*   [ ] **Feature:** Clicking Capture saves an image and returns a valid URL.
*   [ ] **Constraint:** `VisionPanel.js` functions remain < 50 lines.
*   [ ] **Accessibility:** Icons have `aria-label` or `title` attributes.

## 7. RISK MITIGATION
*   **Hardware Limitation:** If Camera cannot switch to 1920x1080 without restart, the Backend should silently fallback to 640x480 (System constraint: Don't crash).
*   **Storage:** Infinite captures will fill the disk.
    *   *Mitigation:* Add a basic cleanup check in Backend (keep last 50 images only).
*   **Browser Caching:** Images might cache aggressively.
    *   *Mitigation:* Append timestamp to image URLs (`?t=1234`).

---
```

✅ **Spec Created:** `docs/specs/ui_refinement_spec.md`
📋 **Next Step:** Review Spec, then pass to Architect.
👉 **Next Agent:** Architect (AGENTS/01_architect.md)