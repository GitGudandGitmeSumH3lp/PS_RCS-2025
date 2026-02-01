```markdown
# FEATURE SPEC: UI Overhaul & Vision Integration (Linear Style)
**Date:** 2025-01-24
**Status:** Feasible
**Target File:** `docs/specs/ui_overhaul_linear_spec.md`

## 1. DESIGN PRINCIPLES (Linear.app Translation)

### Typography System
*   **Font Family:** `Inter`, system-ui, sans-serif.
*   **Hierarchy:**
    *   *Headings:* Weight 600, tight tracking (-0.02em).
    *   *Body:* Weight 400, normal tracking.
    *   *Labels/Metadata:* Weight 500, slightly loose tracking, uppercase option for tiny labels.
*   **Text Colors (CSS Variables):**
    *   `--text-primary`: High contrast (e.g., #F7F8F8 or #1A1C1E).
    *   `--text-secondary`: Medium contrast (e.g., #8A8F98).
    *   `--text-tertiary`: Low contrast for placeholders (e.g., #5F656F).

### Color Palette & Depth
*   **Concept:** "Matte Surfaces & Subtle Borders."
*   **Surfaces:**
    *   `--surface-base`: Main background.
    *   `--surface-card`: Slightly elevated (lighter in dark mode).
    *   `--surface-overlay`: Modal background.
*   **Borders:**
    *   `--border-subtle`: 1px solid opacity 10%.
    *   `--border-focus`: 1px solid opacity 40% (Active state).
*   **Shadows:**
    *   `--shadow-card`: `0 2px 8px rgba(0,0,0,0.04)`.
    *   `--shadow-modal`: `0 24px 48px rgba(0,0,0,0.2)`.

### Motion & Interaction
*   **Timing:** 200ms `cubic-bezier(0.4, 0, 0.2, 1)` (Linear's snappy feel).
*   **Micro-interactions:** Buttons scale down (0.98) on click. Links have hover underlines.

## 2. COMPONENT INVENTORY

### A. The Dashboard Grid (Layout)
*   **Replacement:** Replace the bubbly Bento Grid with a **Structured Signal Grid**.
*   **Style:** Cards have 20px radius (Constraint compliant) but use a 1px border (`--border-subtle`) instead of heavy shadows.
*   **Spacing:** Gap 16px or 24px (multiples of 4).

### B. Camera Preview Card (The Entry Point)
*   **ID:** `#card-vision-preview`
*   **Appearance:**
    *   Top: Header with "Vision System" + Status Pulse (Green/Grey).
    *   Body: Static blurred snapshot of the camera (looks like a file preview).
    *   Overlay: "Click to view live" (Visible only on hover).
*   **Behavior:** Click triggers `#modal-vision`.

### C. Vision Modal (The Workspace)
*   **ID:** `#modal-vision`
*   **Style:** Centered, 80% width, max-width 800px. Backdrop blur (`backdrop-filter: blur(4px)`).
*   **Content:**
    *   Header: "Live Feed" (Left), "Scan Action" (Right).
    *   Body: `img#vision-stream` (Aspect ratio maintained).
    *   Footer: Recent scan results (Inline text).

## 3. USER JOURNEY MAP

### Phase 1: Idle (Dashboard)
1.  **User** views Dashboard.
2.  **System** renders `#card-vision-preview` with a cached image (or placeholder).
3.  **Indicator** shows current hardware status (online/offline) fetched from `api/status`.

### Phase 2: Engagement (Preview)
1.  **User** hovers over card -> Card border darkens (Focus state).
2.  **User** clicks card -> Modal scales up (`transform: scale(0.95) -> scale(1)`).
3.  **System** sets `img.src = /api/vision/stream`.
4.  **System** stream loads (< 1s).

### Phase 3: Action (Scanning)
1.  **User** clicks "Scan Label" (in Modal Header).
2.  **System** (Frontend) disables button, shows spinner.
3.  **System** (Backend) calls `OCRService.scan()`.
4.  **System** (Frontend) polls `/api/vision/last-scan`.
5.  **UI Update:** Result appears in Modal Footer *and* syncs to Dashboard "Last Scan" card instantly.

## 4. TECHNICAL REQUIREMENTS

### HTML Structure (`service_dashboard.html`)
```html
<!-- Semantic & Accessible -->
<section class="grid-layout">
    <article id="card-vision-preview" class="linear-card" role="button" tabindex="0">
        <header>
            <span class="icon">📷</span>
            <h4>Vision Feed</h4>
            <div class="status-indicator" data-status="online"></div>
        </header>
        <div class="card-body">
            <!-- Lazy loaded placeholder -->
            <div class="preview-placeholder"></div>
        </div>
    </article>
</section>

<dialog id="modal-vision" class="linear-modal">
    <!-- Stream injected here only when open -->
</dialog>
```

### CSS Architecture (`dashboard.css`)
*   **Variables:** Define `--font-inter`, `--space-4`, `--space-8`, etc.
*   **Utility Classes:** `.text-sm`, `.text-muted`, `.flex-center`.
*   **Z-Index Strategy:** Modal (1000), Overlay (999), Dashboard (1).

### JavaScript Behavior (`VisionPanel.js`)
*   **Initialization:**
    *   Verify `#card-vision-preview` and `#modal-vision` exist.
    *   Bind `click` on Card -> `openModal()`.
    *   Bind `keydown(Escape)` -> `closeModal()`.
*   **Stream Handling:**
    *   `openModal()`: `videoEl.src = "/api/vision/stream?q=40"`
    *   `closeModal()`: `videoEl.src = ""` (Bandwidth saver).
*   **Data Sync:**
    *   Use `EventBus` or custom events to notify other cards when a scan completes.

## 5. ACCEPTANCE CRITERIA
*   [ ] **Visual:** Dashboard typography is Inter. No system serif fonts.
*   [ ] **Visual:** Colors use defined CSS variables (check for hardcoded hex).
*   [ ] **Functional:** Clicking `#card-vision-preview` opens `#modal-vision`.
*   [ ] **Functional:** Stream starts *only* when modal opens.
*   [ ] **Functional:** Stream stops when modal closes.
*   [ ] **Functional:** "Scan" button sends POST request and updates UI without reload.
*   [ ] **Performance:** Modal animation is smooth (60fps) on Desktop (GPU transform).
*   [ ] **Constraint:** JS methods are < 50 lines.

## 6. RISK MITIGATION
*   **Risk:** Stream latency on Pi.
    *   *Mitigation:* Force `320x240` and `quality=40` in the image tag attributes or query params.
*   **Risk:** Missing DOM elements cause JS crash.
    *   *Mitigation:* Wrap `constructor` logic in `if (element) { ... }` blocks. Log warnings, don't throw errors.
*   **Risk:** Styles break on mobile.
    *   *Mitigation:* Use CSS Grid `minmax` for dashboard layout. Modal becomes full-screen on mobile viewports.

---
