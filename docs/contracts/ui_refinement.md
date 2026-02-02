# CONTRACT: UI Refinement (Icon Navigation + High-Res Capture)
**Version:** 1.0
**Last Updated:** 2024-02-02
**Status:** DRAFT
**Target Files:** `service_dashboard.html`, `service_theme.css`, `dashboard-core.js`, `server.py`

---

## 1. PURPOSE

Transform the service dashboard from text-based navigation to icon-only cards with CSS-based tooltips, repair theme persistence mechanism, and add high-resolution image capture capability to the vision system. This contract ensures visual consistency with modern SaaS/industrial design systems while maintaining accessibility and strict performance constraints.

---

## 2. DECISION LOG (Architectural Resolutions)

### 2.1 File Structure
**Decision:** Keep `ThemeController` embedded in `dashboard-core.js`
**Rationale:** 
- Single responsibility class estimated at ~35 lines (under 50-line limit)
- Avoids circular dependency between theme and dashboard initialization
- No complex state management requiring separate module
- Follows existing pattern in `dashboard-core.js` structure

### 2.2 Modal Approach
**Decision:** Reuse existing `#visionModal` DOM structure
**Rationale:**
- Avoid DOM duplication and state synchronization issues
- Add capture button to existing modal footer alongside scan button
- Maintains progressive disclosure pattern (stream hidden until modal open)
- Reduces complexity for implementer

### 2.3 Grid Layout
**Decision:** `grid-template-columns: repeat(auto-fill, minmax(160px, 1fr))`
**Rationale:**
- 160px = 20 × 8px (baseline compliance)
- Auto-fill enables responsive wrapping across viewport sizes
- Minimum width ensures 48px icon + 24px padding + tooltip space
- Gap: 24px (3 × 8px baseline)

### 2.4 Status Synchronization
**Decision:** Continue polling `/api/status` at 2000ms interval
**Rationale:**
- WebSocket adds dependency complexity without measurable benefit at 2s intervals
- Existing polling mechanism already implemented in current system
- Aligns with "Non-Blocking" constraint (status reads are fast)
- Simpler error handling (HTTP retries vs WebSocket reconnection)

### 2.5 Capture Resolution
**Decision:** Attempt 1920×1080 @ quality=95, fallback to 640×480 @ quality=95
**Rationale:**
- Stream uses 320×240@40 (constraint from vision_manager_optimization.md)
- Capture requires high-quality for OCR preprocessing
- Quality=95 avoids JPEG artifacts that interfere with text recognition
- Graceful degradation if camera cannot switch modes (see Risk Mitigation)
- Storage: ~200KB per image at 1080p/95, manageable with cleanup

### 2.6 Theme Persistence
**Decision:** `localStorage.setItem('ps-rcs-theme', 'dark'|'light')`, fallback to `'dark'`
**Rationale:**
- Key prefix `ps-rcs-` avoids collision with other localhost apps
- Simple string value (no JSON overhead)
- Default `'dark'` aligns with system_constraints.md (Industrial Dark default)
- Single source of truth (no CSS class + localStorage sync issues)

---

## 3. PUBLIC INTERFACES

### 3.1 HTML Changes (`service_dashboard.html`)

#### 3.1.1 Service Card Structure (Icon-Only)

**Method:** `renderServiceCard`
**Signature:**
```html
<article class="service-card" 
         data-service="{service_id}"
         data-tooltip="{service_name}"
         role="button"
         aria-label="Open {service_name}"
         tabindex="0">
  <div class="card-icon" aria-hidden="true">{emoji_icon}</div>
  <span class="status-indicator" data-status="{active|inactive|error}"></span>
</article>
```

**Behavior Specification:**
- **Input Validation:** `data-service` must match API endpoint names (vision, motor, lidar)
- **Processing Logic:** 
  - Remove all `<h3>` and text content from existing cards
  - Replace with single icon element (48×48px effective size)
  - Add status indicator dot (8px, positioned top-right)
- **Output Guarantee:** Each card contains exactly 2 children: `.card-icon` and `.status-indicator`
- **Side Effects:** Existing click handlers remain functional (unchanged)

**Required DOM Element IDs:**
- `.service-card[data-service="vision"]` - Vision card (📹)
- `.service-card[data-service="motor"]` - Motor control card (🎚️)
- `.service-card[data-service="lidar"]` - Lidar card (🛡️)
- `#themeToggle` - Theme switch button (☀️/🌙)

#### 3.1.2 Vision Modal Enhancement

**Location:** Inside `#visionModal .modal-footer`

**ADD Before Existing `#scanBtn`:**
```html
<button id="captureBtn" 
        class="btn btn-primary" 
        aria-label="Capture high-resolution image"
        disabled>
  <span class="icon" aria-hidden="true">📸</span>
  <span class="label">Capture</span>
</button>
```

**Behavior Specification:**
- **Initial State:** `disabled` until stream is confirmed active
- **Click Handler:** Calls `VisionPanel.captureHighRes()`
- **Loading State:** Adds `.processing` class during capture (button shows spinner)

#### 3.1.3 Capture Preview Overlay

**Location:** After `#visionStream` inside `#visionModal .modal-body`

**ADD:**
```html
<div id="capturePreview" class="capture-preview" hidden>
  <img id="captureImage" 
       src="" 
       alt="Captured image preview" 
       loading="lazy" />
  <button id="closePreview" 
          class="btn-icon" 
          aria-label="Close preview"
          type="button">×</button>
</div>
```

**Behavior Specification:**
- **Initial State:** `hidden` attribute present
- **Reveal:** Remove `hidden` when capture succeeds, add `.flash` animation class
- **Dismiss:** Click `#closePreview` or press Escape to re-add `hidden` attribute

**Semantic HTML Requirements:**
- Use `<article>` for service cards (self-contained interactive components)
- Use `<section>` for modal body groupings
- Maintain existing `<dialog>` or modal patterns (no change to modal structure)

---

### 3.2 CSS Changes (`service_theme.css`)

#### 3.2.1 Color System Variables

**Method:** `defineColorVariables`
**Signature:**
```css
:root {
  /* Backgrounds */
  --bg-app: #0F0F0F;
  --bg-card: #1A1A1A;
  --bg-card-hover: #262626;
  --bg-modal: #1E1E1E;
  --bg-overlay: rgba(0, 0, 0, 0.85);
  
  /* Text */
  --text-primary: #EDEDED;
  --text-secondary: #A0A0A0;
  --text-muted: #6E6E6E;
  
  /* Accents */
  --accent-primary: #3B82F6;
  --accent-success: #10B981;
  --accent-warning: #F59E0B;
  --accent-error: #EF4444;
  
  /* Borders */
  --border-subtle: #333333;
  --border-focus: #3B82F6;
  
  /* Status Colors */
  --status-active: #10B981;
  --status-inactive: #6E6E6E;
  --status-error: #EF4444;
}

[data-theme="light"] {
  --bg-app: #f8fafc;
  --bg-card: #ffffff;
  --bg-card-hover: #f1f5f9;
  --bg-modal: #ffffff;
  --bg-overlay: rgba(15, 23, 42, 0.75);
  
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  
  --border-subtle: #e2e8f0;
  --border-focus: #3B82F6;
}
```

**Behavior Specification:**
- **Input Validation:** No hardcoded hex/rgb values allowed outside `:root` and `[data-theme]`
- **Processing Logic:** All component styles must reference CSS variables only
- **Output Guarantee:** Theme switch requires only `data-theme` attribute change
- **Side Effects:** None (declarative CSS)

**Performance Requirements:**
- Time Complexity: O(1) (CSS variable lookup)
- Space Complexity: O(1) (no runtime computation)

#### 3.2.2 Spacing Scale (8px Baseline)

**Method:** `defineSpacingScale`
**Signature:**
```css
:root {
  --space-1: 8px;   /* 1 unit */
  --space-2: 16px;  /* 2 units */
  --space-3: 24px;  /* 3 units */
  --space-4: 32px;  /* 4 units */
  --space-5: 40px;  /* 5 units */
  --space-6: 48px;  /* 6 units */
  --space-7: 56px;  /* 7 units */
  --space-8: 64px;  /* 8 units */
}
```

**Usage Contract:**
- All padding, margin, gap values MUST use these variables
- Direct pixel values (e.g., `padding: 20px`) are FORBIDDEN
- Exception: 1px borders allowed (not subject to baseline)

#### 3.2.3 Icon Card Styles

**Method:** `styleIconCard`
**Signature:**
```css
.service-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 160px; /* 20 × 8px */
  padding: var(--space-3); /* 24px */
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 20px; /* Per system_style.md */
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.service-card:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-primary);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08); /* Per system_style.md */
  transform: translateY(-2px);
}

.service-card:focus-visible {
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}

.card-icon {
  font-size: 48px; /* Hero icon size */
  line-height: 1;
  margin-bottom: var(--space-2); /* 16px */
}

.status-indicator {
  position: absolute;
  top: var(--space-2); /* 16px */
  right: var(--space-2); /* 16px */
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--status-inactive);
}

.status-indicator[data-status="active"] {
  background: var(--status-active);
  box-shadow: 0 0 8px var(--status-active);
}

.status-indicator[data-status="error"] {
  background: var(--status-error);
  box-shadow: 0 0 8px var(--status-error);
}
```

**Behavior Specification:**
- **Hover State:** Must trigger within 16ms (1 frame @ 60fps)
- **Focus State:** Keyboard navigation must show visible outline
- **Status Sync:** `data-status` attribute updated by JS polling

#### 3.2.4 Tooltip System (CSS-Only)

**Method:** `renderTooltip`
**Signature:**
```css
[data-tooltip] {
  position: relative;
}

[data-tooltip]::before {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(-8px);
  padding: var(--space-1) var(--space-2); /* 8px 16px */
  background: var(--bg-modal);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.02em;
  white-space: nowrap;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease;
  z-index: 1000;
}

[data-tooltip]::after {
  content: '';
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: var(--bg-modal);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  z-index: 1000;
}

[data-tooltip]:hover::before,
[data-tooltip]:hover::after {
  opacity: 1;
  transform: translateX(-50%) translateY(-4px);
}

[data-tooltip]:hover::after {
  transform: translateX(-50%);
}
```

**Behavior Specification:**
- **Input Validation:** `data-tooltip` attribute must contain non-empty string
- **Processing Logic:** Pure CSS pseudo-elements, no JS required
- **Output Guarantee:** Tooltip appears 200ms after hover start
- **Side Effects:** None (declarative CSS)

**Accessibility Requirements:**
- Tooltip text MUST also exist in `aria-label` for screen readers
- Tooltips are visual enhancement only, not primary content

#### 3.2.5 Flash Animation (Capture Feedback)

**Method:** `animateCapture`
**Signature:**
```css
@keyframes flash {
  0% { 
    opacity: 0.9; 
    background: rgba(255, 255, 255, 0.9); 
  }
  100% { 
    opacity: 0; 
    background: rgba(255, 255, 255, 0); 
  }
}

.flash-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 9999;
  animation: flash 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
```

**Behavior Specification:**
- **Trigger:** JS adds `.flash-overlay` div to `<body>` on capture
- **Duration:** 400ms total (matches camera shutter feel)
- **Cleanup:** JS removes element after animation ends
- **Side Effects:** Briefly obscures entire viewport (intentional feedback)

**Performance Requirements:**
- GPU-accelerated properties only (opacity, transform)
- No layout thrashing (fixed positioning)

#### 3.2.6 Capture Preview Styles

**Method:** `stylePreviewOverlay`
**Signature:**
```css
.capture-preview {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.capture-preview:not([hidden]) {
  opacity: 1;
}

.capture-preview img {
  max-width: 90%;
  max-height: 90%;
  border-radius: 12px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
}

.btn-icon {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-icon:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.1);
}
```

**Behavior Specification:**
- **Initial State:** `hidden` attribute prevents display
- **Reveal:** Remove `hidden`, opacity transitions to 1
- **Image Loading:** `loading="lazy"` prevents blocking
- **Dismiss:** Click button or Escape key re-adds `hidden`

---

### 3.3 JavaScript Changes (`dashboard-core.js`)

#### 3.3.1 ThemeController Class

**Class:** `ThemeController`
**Location:** Embedded in `dashboard-core.js`

**Method:** `constructor`
**Signature:**
```javascript
constructor() {
  this.storageKey = 'ps-rcs-theme';
  this.toggleButton = null;
  this.currentTheme = null;
}
```

**Method:** `init`
**Signature:**
```javascript
/**
 * Initialize theme system from localStorage
 * @returns {void}
 */
init(): void
```

**Behavior Specification:**
- **Input Validation:** None (reads localStorage)
- **Processing Logic:**
  1. Read `localStorage.getItem(this.storageKey)`
  2. If null/undefined, default to `'dark'`
  3. Apply theme via `this.applyTheme(theme)`
  4. Bind toggle button click handler
- **Output Guarantee:** `<html>` has `data-theme` attribute set
- **Side Effects:** Modifies DOM attribute, reads localStorage

**Error Handling:**
- **localStorage disabled:** Catch exception, use `'dark'` default, log warning
- **Toggle button missing:** Log warning, continue (graceful degradation)

**Method:** `toggle`
**Signature:**
```javascript
/**
 * Toggle between light and dark themes
 * @returns {void}
 */
toggle(): void
```

**Behavior Specification:**
- **Processing Logic:**
  1. Read current theme from `<html data-theme>`
  2. Compute opposite: `'dark'` ↔ `'light'`
  3. Call `this.applyTheme(newTheme)`
- **Output Guarantee:** Theme persists to localStorage
- **Side Effects:** Writes localStorage, modifies DOM

**Method:** `applyTheme` (Private)
**Signature:**
```javascript
/**
 * Apply theme to DOM and persist to storage
 * @param {string} theme - 'dark' or 'light'
 * @returns {void}
 * @private
 */
applyTheme(theme: string): void
```

**Behavior Specification:**
- **Input Validation:** `theme` must be `'dark'` or `'light'`
- **Processing Logic:**
  1. Set `document.documentElement.setAttribute('data-theme', theme)`
  2. Write `localStorage.setItem(this.storageKey, theme)`
  3. Update toggle button icon (☀️ for dark mode, 🌙 for light mode)
- **Output Guarantee:** DOM and storage are synchronized
- **Side Effects:** Modifies DOM, writes localStorage

**Error Handling:**
- **Invalid theme:** Log error, fallback to `'dark'`
- **localStorage write failure:** Log warning, continue (theme still applied to DOM)

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)
- Max Lines: 35 (estimate)

---

#### 3.3.2 VisionPanel Class Extension

**Class:** `VisionPanel`
**Location:** Existing class in `dashboard-core.js`

**Method:** `captureHighRes`
**Signature:**
```javascript
/**
 * Capture high-resolution image from camera
 * @returns {Promise<void>}
 * @throws {Error} If capture fails or camera offline
 */
async captureHighRes(): Promise<void>
```

**Behavior Specification:**
- **Input Validation:** Check camera status before attempting capture
- **Processing Logic:**
  1. Disable `#captureBtn`, add `.processing` class
  2. POST to `/api/vision/capture` (no body required)
  3. Await response with timeout (5000ms)
  4. If success: Call `this.showCapturePreview(response.url)`
  5. If failure: Call `this.showToast('Capture failed', 'error')`
  6. Re-enable button, remove `.processing` class
- **Output Guarantee:** Either preview shown OR error toast displayed
- **Side Effects:** HTTP request, DOM manipulation, possible flash animation

**Error Handling:**
- **Camera offline:** Show toast "Camera not available", don't attempt request
- **Network timeout:** Show toast "Capture timed out", re-enable button
- **Server error (500):** Show toast "Capture failed", log error
- **Invalid response:** Show toast "Unexpected response", log payload

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)
- Network Timeout: 5000ms
- Max Lines: 45 (estimate)

**Method:** `showCapturePreview` (Private)
**Signature:**
```javascript
/**
 * Display captured image in overlay
 * @param {string} imageUrl - URL to captured image
 * @returns {void}
 * @private
 */
showCapturePreview(imageUrl: string): void
```

**Behavior Specification:**
- **Input Validation:** `imageUrl` must be non-empty string
- **Processing Logic:**
  1. Set `#captureImage.src = imageUrl + '?t=' + Date.now()` (cache bust)
  2. Remove `hidden` attribute from `#capturePreview`
  3. Trigger flash animation: Add `.flash-overlay` to body, auto-remove after 400ms
- **Output Guarantee:** Preview overlay visible with loaded image
- **Side Effects:** Modifies DOM, triggers animation

**Error Handling:**
- **Image load failure:** Listen for `img.onerror`, show toast "Preview failed"
- **Missing DOM elements:** Log warning, skip preview (graceful degradation)

**Performance Requirements:**
- Time Complexity: O(1)
- Max Lines: 25 (estimate)

**Method:** `hideCapture Preview` (Private)
**Signature:**
```javascript
/**
 * Dismiss capture preview overlay
 * @returns {void}
 * @private
 */
hideCapturePreview(): void
```

**Behavior Specification:**
- **Processing Logic:**
  1. Add `hidden` attribute to `#capturePreview`
  2. Clear `#captureImage.src` (free memory)
- **Output Guarantee:** Preview hidden, image unloaded
- **Side Effects:** Modifies DOM

**Performance Requirements:**
- Time Complexity: O(1)
- Max Lines: 10 (estimate)

---

#### 3.3.3 Tooltip System (Optional JS Enhancement)

**Note:** Tooltips are pure CSS by default. JS enhancement is OPTIONAL for advanced features (delay, positioning).

**Method:** `enhanceTooltips` (Optional)
**Signature:**
```javascript
/**
 * Add programmatic tooltip enhancements
 * @returns {void}
 */
enhanceTooltips(): void
```

**Behavior Specification:**
- **Processing Logic:**
  1. Find all `[data-tooltip]` elements
  2. Add `mouseenter` delay (200ms) before adding `.tooltip-visible` class
  3. Add `mouseleave` to remove class
- **Output Guarantee:** Tooltips appear with slight delay (prevents flickering)
- **Side Effects:** Adds event listeners to DOM elements

**Performance Requirements:**
- Time Complexity: O(n) where n = number of tooltip elements
- Max Lines: 30 (estimate)

**Note:** Implementer may SKIP this method if CSS-only tooltips are sufficient.

---

#### 3.3.4 Icon Card Interactions

**Method:** `bindCardClicks`
**Signature:**
```javascript
/**
 * Attach click handlers to service cards
 * @returns {void}
 */
bindCardClicks(): void
```

**Behavior Specification:**
- **Input Validation:** None (queries DOM)
- **Processing Logic:**
  1. Query all `.service-card` elements
  2. For each card, read `data-service` attribute
  3. Attach click handler that opens corresponding panel:
     - `vision` → `visionPanel.open()`
     - `motor` → `motorPanel.open()`
     - `lidar` → `lidarPanel.open()`
- **Output Guarantee:** All cards are clickable
- **Side Effects:** Adds event listeners

**Error Handling:**
- **Unknown service:** Log warning, ignore card
- **Missing panel instance:** Log error, show toast "Service unavailable"

**Performance Requirements:**
- Time Complexity: O(n) where n = number of cards
- Max Lines: 20 (estimate)

---

### 3.4 Backend Changes (`server.py`)

#### 3.4.1 New Endpoint: Capture High-Res Image

**Method:** `capture_image`
**Route:** `POST /api/vision/capture`
**Signature:**
```python
@app.route('/api/vision/capture', methods=['POST'])
def capture_image() -> tuple[Response, int]:
    """
    Capture high-resolution image from camera.
    
    Returns:
        tuple: (JSON response, HTTP status code)
            Success: {"status": "ok", "url": "/captures/snapshot_123.jpg"}
            Failure: {"status": "error", "message": "Error description"}
    
    Raises:
        None (all exceptions caught and returned as JSON)
    """
```

**Behavior Specification:**
- **Input Validation:** No body required (POST to trigger action)
- **Processing Logic:**
  1. Check if `VisionManager` instance is initialized
  2. Call `vision_manager.capture_snapshot(high_res=True)`
  3. Generate unique filename: `snapshot_{timestamp}.jpg`
  4. Save to `data/captures/` directory
  5. Trigger cleanup if directory > 50 images
  6. Return URL to captured image
- **Output Guarantee:** Either image URL or error message
- **Side Effects:** File I/O, possible cleanup of old images

**Error Handling:**
- **VisionManager not initialized:** Return `{"status": "error", "message": "Camera not available"}`, 503
- **Capture fails (hardware):** Return `{"status": "error", "message": "Capture failed"}`, 500
- **Disk full:** Return `{"status": "error", "message": "Storage full"}`, 507
- **Permission denied:** Return `{"status": "error", "message": "Cannot write to captures"}`, 500

**Performance Requirements:**
- Time Complexity: O(1) for capture + O(n) for cleanup (where n = image count)
- Space Complexity: O(1)
- Max Response Time: 2000ms
- Max Lines: 40

**Dependencies:**
- **Calls:** `VisionManager.capture_snapshot(high_res=True)`
- **Called By:** Frontend `VisionPanel.captureHighRes()`

---

#### 3.4.2 Serve Captured Images

**Method:** `serve_capture`
**Route:** `GET /captures/<filename>`
**Signature:**
```python
@app.route('/captures/<filename>')
def serve_capture(filename: str) -> Response:
    """
    Serve static captured image files.
    
    Args:
        filename: Name of image file (e.g., "snapshot_123.jpg")
    
    Returns:
        Response: Image file or 404 error
    
    Raises:
        None (Flask handles file serving errors)
    """
```

**Behavior Specification:**
- **Input Validation:** 
  - `filename` must end with `.jpg` or `.jpeg`
  - `filename` must not contain path traversal (`..`)
- **Processing Logic:**
  1. Sanitize filename (remove path separators)
  2. Construct safe path: `data/captures/{filename}`
  3. Check file exists
  4. Serve with `send_from_directory`
- **Output Guarantee:** Image file or 404 response
- **Side Effects:** File read

**Error Handling:**
- **Invalid extension:** Return 400 "Invalid file type"
- **Path traversal attempt:** Return 400 "Invalid filename"
- **File not found:** Return 404 (Flask default)

**Performance Requirements:**
- Time Complexity: O(1)
- Max Lines: 15

**Security Requirements:**
- MUST sanitize filename (no `../`, no absolute paths)
- MUST restrict to `.jpg`/`.jpeg` only
- MUST serve from `data/captures/` only (no arbitrary file access)

---

#### 3.4.3 Storage Cleanup Utility

**Method:** `cleanup_old_captures`
**Signature:**
```python
def cleanup_old_captures(max_files: int = 50) -> int:
    """
    Remove oldest capture images when limit exceeded.
    
    Args:
        max_files: Maximum number of images to retain (default: 50)
    
    Returns:
        int: Number of files deleted
    
    Raises:
        OSError: If file deletion fails (logged, not raised)
    """
```

**Behavior Specification:**
- **Input Validation:** `max_files` must be positive integer
- **Processing Logic:**
  1. List all `.jpg` files in `data/captures/`
  2. Sort by modification time (oldest first)
  3. If count > `max_files`, delete oldest (count - max_files) images
  4. Return count of deleted files
- **Output Guarantee:** Directory contains ≤ max_files images
- **Side Effects:** File deletion

**Error Handling:**
- **Permission denied:** Log error, skip file, continue
- **File not found:** Log warning, continue (race condition handled)
- **Directory not exists:** Create directory, return 0

**Performance Requirements:**
- Time Complexity: O(n log n) where n = file count (sorting)
- Space Complexity: O(n) (file list in memory)
- Max Lines: 35

**Dependencies:**
- **Calls:** `os.listdir`, `os.path.getmtime`, `os.remove`
- **Called By:** `capture_image()` after successful capture

---

#### 3.4.4 VisionManager Enhancement (External Contract)

**Note:** This is a contract for the `VisionManager` class (not in `server.py`).

**Method:** `capture_snapshot`
**Signature:**
```python
def capture_snapshot(self, high_res: bool = False) -> np.ndarray:
    """
    Capture single frame from camera.
    
    Args:
        high_res: If True, attempt 1920x1080. If False, use stream resolution.
    
    Returns:
        np.ndarray: Captured frame (BGR format)
    
    Raises:
        RuntimeError: If camera is not initialized
        cv2.error: If capture fails
    """
```

**Behavior Specification:**
- **Input Validation:** `high_res` must be boolean
- **Processing Logic:**
  1. If `high_res=True`:
     - Attempt to set camera resolution to 1920×1080
     - Capture frame
     - Restore original resolution (320×240)
  2. If `high_res=False`:
     - Capture frame at current resolution
  3. Validate frame is not empty
- **Output Guarantee:** Valid numpy array or exception
- **Side Effects:** Temporarily changes camera settings if high_res=True

**Error Handling:**
- **Camera not initialized:** Raise `RuntimeError("Camera not available")`
- **Resolution change fails:** Log warning, capture at current resolution (graceful fallback)
- **Frame empty:** Raise `cv2.error("Capture failed")`

**Performance Requirements:**
- Time Complexity: O(1)
- Max Response Time: 1000ms (camera hardware dependent)
- Max Lines: 45

---

## 4. DEPENDENCIES

### 4.1 This Module CALLS

**Frontend (`dashboard-core.js`):**
- `POST /api/vision/capture` - Trigger image capture
- `GET /captures/<filename>` - Retrieve captured image
- `GET /api/status` - Poll system status (existing)

**Backend (`server.py`):**
- `VisionManager.capture_snapshot(high_res=True)` - Hardware capture
- `cleanup_old_captures(50)` - Storage management
- `os.path.join('data', 'captures', filename)` - Path construction
- `flask.send_from_directory()` - File serving

### 4.2 This Module is CALLED BY

**Frontend:**
- User click on `#captureBtn` → `VisionPanel.captureHighRes()`
- User click on `#themeToggle` → `ThemeController.toggle()`
- User hover on `.service-card` → CSS tooltip reveal (no JS call)

**Backend:**
- Frontend HTTP requests → Flask route handlers

---

## 5. DATA STRUCTURES

### 5.1 Capture Response Object

```typescript
interface CaptureResponse {
  status: 'ok' | 'error';
  url?: string;        // Present if status='ok'
  message?: string;    // Present if status='error'
  timestamp?: number;  // Optional: Unix timestamp of capture
}
```

### 5.2 Theme State

```typescript
type Theme = 'dark' | 'light';

interface ThemeConfig {
  storageKey: string;  // 'ps-rcs-theme'
  defaultTheme: Theme; // 'dark'
}
```

### 5.3 Capture Metadata (Backend)

```python
@dataclass
class CaptureMetadata:
    """Metadata for captured image."""
    filename: str
    timestamp: float
    resolution: tuple[int, int]  # (width, height)
    quality: int                 # JPEG quality (0-100)
    size_bytes: int
```

---

## 6. CONSTRAINTS (FROM SYSTEM RULES)

### 6.1 From `system_constraints.md`

1. **Max Function Length:** 50 lines (JS/Python)
   - `ThemeController.*`: ~35 lines total (compliant)
   - `VisionPanel.captureHighRes()`: ~45 lines (compliant)
   - `capture_image()`: ~40 lines (compliant)

2. **No Hardcoded Colors:** CSS variables only
   - All colors defined in `:root` and `[data-theme]`
   - Zero hex/rgb values in component styles

3. **Progressive Disclosure:** Stream hidden until modal open
   - Maintained (no change to existing behavior)

4. **Type Hints Mandatory:** All backend functions
   - All route handlers have return type annotations
   - All utility functions have full type hints

5. **Docstrings:** Google-style required
   - All public methods include docstrings
   - Parameters, returns, raises documented

6. **No Global State:** All state in classes
   - Theme state in `ThemeController` instance
   - Vision state in `VisionPanel` instance

7. **Non-Blocking Routes:** HTTP returns immediately
   - Capture endpoint runs synchronously but completes in <2s
   - No long-running operations (cleanup is O(n) but fast)

### 6.2 From `system_style.md` (Embedded in Mission Brief)

1. **Typography:** Inter, -apple-system, BlinkMacSystemFont
   - Applied in CSS root font-family

2. **Border Radius:** 20-24px for cards, 12-16px for buttons
   - Service cards: 20px
   - Buttons: 12px
   - Preview image: 12px

3. **Shadows:** Soft, diffused `0 8px 30px rgba(0,0,0,0.08)`
   - Card hover: `0 8px 30px rgba(0,0,0,0.08)`
   - Preview image: `0 16px 48px rgba(0,0,0,0.5)`

4. **Spacing:** 8px baseline grid
   - All spacing uses `--space-*` variables (8, 16, 24, 32, etc.)

### 6.3 From `vision_manager_optimization.md` (Embedded in Mission Brief)

1. **Stream MUST use quality=40** (not 80)
   - No change (stream settings unchanged)

2. **Stream MUST be 320×240 resolution for UI**
   - No change (maintained)

3. **Stream MUST throttle to ~15 FPS**
   - No change (maintained)

4. **Capture uses DIFFERENT settings:**
   - Capture: 1920×1080 @ quality=95 (new)
   - Stream: 320×240 @ quality=40 (existing)

---

## 7. ACCEPTANCE CRITERIA

### 7.1 Visual Design

**Test Case 1:** Dark Theme Verification
- **Input:** Load dashboard with no localStorage
- **Expected Output:** 
  - `<html data-theme="dark">`
  - Background color: `#0F0F0F`
  - Card background: `#1A1A1A`
  - Text color: `#EDEDED`
- **Expected Behavior:** All colors sourced from CSS variables

**Test Case 2:** Icon-Only Cards
- **Input:** View service grid
- **Expected Output:**
  - Vision card shows 📹 icon (48px)
  - No text labels visible (except in tooltips)
  - Status indicator dot present (8px, top-right)
- **Expected Behavior:** Hover reveals tooltip with service name

**Test Case 3:** Tooltip Display
- **Input:** Hover over vision card for 200ms
- **Expected Output:** Tooltip appears with "Vision Service" text
- **Expected Behavior:** Tooltip positioned above card, centered

### 7.2 Theme Persistence

**Test Case 4:** Theme Toggle
- **Input:** Click theme toggle button
- **Expected Output:**
  - `<html data-theme>` changes from `dark` to `light`
  - Colors invert immediately
  - `localStorage['ps-rcs-theme']` = `'light'`
- **Expected Behavior:** No page flash, instant transition

**Test Case 5:** Theme Persistence
- **Input:** 
  1. Toggle to light theme
  2. Refresh page
- **Expected Output:** Page loads with light theme
- **Expected Behavior:** Theme persists across sessions

**Test Case 6:** Theme Toggle Icon
- **Input:** View theme button in dark mode
- **Expected Output:** Button shows ☀️ icon
- **Expected Behavior:** Icon updates to 🌙 when in light mode

### 7.3 High-Res Capture

**Test Case 7:** Successful Capture
- **Input:** 
  1. Open vision modal
  2. Click "Capture" button (📸)
- **Expected Output:**
  - Button disabled during capture
  - Flash animation plays (white overlay, 400ms)
  - Preview overlay appears with captured image
  - Image saved to `data/captures/snapshot_{timestamp}.jpg`
- **Expected Behavior:** Capture completes in <2s

**Test Case 8:** Capture Preview
- **Input:** After successful capture
- **Expected Output:**
  - Image displayed at 90% modal size
  - Close button (×) visible in top-right
  - Image URL includes cache-bust parameter (`?t=`)
- **Expected Behavior:** Click close button hides preview

**Test Case 9:** Camera Offline
- **Input:** 
  1. Stop camera service
  2. Click "Capture" button
- **Expected Output:**
  - Toast notification: "Camera not available"
  - Button remains enabled
  - No HTTP request sent
- **Expected Behavior:** Graceful error handling

**Test Case 10:** Storage Cleanup
- **Input:** 
  1. Populate `data/captures/` with 55 images
  2. Capture new image
- **Expected Output:**
  - Oldest 6 images deleted
  - Directory contains 50 images total
- **Expected Behavior:** Cleanup runs automatically, no user notification

### 7.4 Code Quality

**Test Case 11:** Function Length Compliance
- **Input:** Review all modified functions
- **Expected Output:** 
  - `ThemeController`: All methods ≤35 lines
  - `VisionPanel.captureHighRes()`: ≤45 lines
  - `capture_image()`: ≤40 lines
- **Expected Behavior:** All functions pass auditor review

**Test Case 12:** CSS Variable Usage
- **Input:** Inspect compiled CSS
- **Expected Output:** Zero hardcoded hex/rgb values outside `:root` definitions
- **Expected Behavior:** All component styles reference CSS variables

**Test Case 13:** Accessibility
- **Input:** Navigate with keyboard only
- **Expected Output:**
  - Service cards focusable with Tab key
  - Focus outlines visible (2px blue)
  - All icons have `aria-label` attributes
  - Tooltips do not interfere with screen readers
- **Expected Behavior:** Full keyboard navigation support

---

## 8. ERROR HANDLING SPECIFICATIONS

### 8.1 Frontend Errors

**Error Case 1:** Camera Offline During Capture
- **Condition:** `VisionManager` not initialized OR camera disconnected
- **Action:** 
  1. Check status before capture attempt
  2. If offline: Show toast "Camera not available"
  3. Don't send HTTP request
  4. Keep button enabled for retry
- **User Feedback:** Toast notification (error style)

**Error Case 2:** Network Timeout
- **Condition:** `/api/vision/capture` takes >5000ms
- **Action:**
  1. Abort fetch request
  2. Show toast "Capture timed out. Please try again."
  3. Re-enable capture button
- **User Feedback:** Toast notification (warning style)

**Error Case 3:** Invalid Server Response
- **Condition:** Response status ≠ 200 OR missing `url` field
- **Action:**
  1. Log full response to console
  2. Show toast "Capture failed"
  3. Re-enable button
- **User Feedback:** Toast notification (error style)

**Error Case 4:** Image Load Failure
- **Condition:** Preview image fails to load (404, corrupt file)
- **Action:**
  1. Listen for `img.onerror` event
  2. Show toast "Preview unavailable"
  3. Hide preview overlay
  4. Log error to console
- **User Feedback:** Toast notification (warning style)

**Error Case 5:** Missing DOM Elements
- **Condition:** `#captureBtn` or `#capturePreview` not found
- **Action:**
  1. Log warning: "Capture UI not found, skipping initialization"
  2. Continue dashboard initialization
  3. Don't crash
- **User Feedback:** None (graceful degradation)

**Error Case 6:** localStorage Disabled
- **Condition:** Browser blocks localStorage access
- **Action:**
  1. Catch exception in `ThemeController.init()`
  2. Use `'dark'` default theme
  3. Log warning to console
  4. Theme toggle still works (DOM-only, no persistence)
- **User Feedback:** None (theme still functional)

### 8.2 Backend Errors

**Error Case 7:** VisionManager Not Initialized
- **Condition:** `vision_manager` instance is None
- **Action:** 
  1. Return `{"status": "error", "message": "Camera not available"}`
  2. HTTP status: 503 Service Unavailable
- **Logging:** `logger.warning("Capture attempt with uninitialized camera")`

**Error Case 8:** Hardware Capture Failure
- **Condition:** `VisionManager.capture_snapshot()` raises exception
- **Action:**
  1. Catch exception
  2. Log full traceback
  3. Return `{"status": "error", "message": "Capture failed"}`
  4. HTTP status: 500 Internal Server Error
- **Logging:** `logger.error(f"Capture failed: {str(e)}", exc_info=True)`

**Error Case 9:** Disk Full
- **Condition:** `OSError` during file write with errno 28 (No space)
- **Action:**
  1. Attempt cleanup immediately
  2. Retry save once
  3. If still fails: Return `{"status": "error", "message": "Storage full"}`
  4. HTTP status: 507 Insufficient Storage
- **Logging:** `logger.critical("Disk full during capture")`

**Error Case 10:** Permission Denied
- **Condition:** Cannot write to `data/captures/` directory
- **Action:**
  1. Check directory permissions
  2. Attempt to create directory if missing
  3. If still fails: Return `{"status": "error", "message": "Cannot write to captures"}`
  4. HTTP status: 500 Internal Server Error
- **Logging:** `logger.error("Permission denied: data/captures/")`

**Error Case 11:** Invalid Filename (Security)
- **Condition:** GET `/captures/../../../etc/passwd`
- **Action:**
  1. Sanitize filename (remove `../`, absolute paths)
  2. If still invalid: Return 400 Bad Request
  3. Log attempted path traversal
- **Logging:** `logger.warning(f"Path traversal attempt: {filename}")`

**Error Case 12:** Cleanup Failure
- **Condition:** `cleanup_old_captures()` cannot delete file
- **Action:**
  1. Log error for each failed deletion
  2. Continue with remaining files
  3. Return count of successful deletions
  4. Don't block capture process
- **Logging:** `logger.error(f"Failed to delete {filename}: {str(e)}")`

---

## 9. IMPLEMENTATION NOTES

### 9.1 File Structure Decision

The `ThemeController` is embedded in `dashboard-core.js` because:
1. Small scope (~35 lines)
2. No dependencies outside dashboard
3. Tight coupling with dashboard initialization
4. Avoids module loading complexity

If future requirements expand theme logic beyond 50 lines, extract to `ThemeController.js`.

### 9.2 Resolution Switching Fallback

The `VisionManager.capture_snapshot(high_res=True)` method must implement graceful fallback:

```python
try:
    # Attempt to set 1920x1080
    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
except Exception as e:
    logger.warning(f"Could not set high-res: {e}, using current resolution")
```

This ensures the system never crashes due to hardware limitations.

### 9.3 Tooltip Accessibility

While tooltips provide visual enhancement, they are NOT accessible to screen readers (CSS pseudo-elements are not exposed to accessibility tree). Therefore:

1. ALL icons MUST have `aria-label` attributes
2. Tooltip text should match `aria-label` content
3. Tooltips are supplementary, not primary UI

Example:
```html
<article class="service-card" 
         data-tooltip="Vision Service"
         aria-label="Open Vision Service">
  <!-- Icon here -->
</article>
```

### 9.4 Performance Optimization

**Image Caching:**
Captured images are served with cache-busting timestamps:
```javascript
const imageUrl = response.url + '?t=' + Date.now();
```

This prevents stale previews when captures are taken in quick succession.

**CSS Transitions:**
All animations use GPU-accelerated properties only:
- ✅ `opacity`, `transform`
- ❌ `width`, `height`, `background-color` (except for variables)

This ensures 60fps animations even on Raspberry Pi 4B.

---

## 10. TESTING STRATEGY

### 10.1 Unit Tests (Backend)

**File:** `tests/test_capture_endpoint.py`

```python
def test_capture_success():
    """Test successful high-res capture."""
    # Mock VisionManager.capture_snapshot()
    # POST /api/vision/capture
    # Assert 200 response with valid URL

def test_capture_camera_offline():
    """Test capture when camera unavailable."""
    # Set vision_manager = None
    # POST /api/vision/capture
    # Assert 503 response

def test_cleanup_trigger():
    """Test automatic cleanup at 51 images."""
    # Populate captures/ with 51 images
    # POST /api/vision/capture
    # Assert directory contains exactly 50 images
```

### 10.2 Integration Tests (Frontend)

**File:** `tests/integration/test_ui_refinement.js`

```javascript
test('Theme toggle persists', () => {
  // Click theme toggle
  // Refresh page
  // Assert theme matches localStorage
});

test('Capture flow end-to-end', () => {
  // Mock camera available
  // Click capture button
  // Assert flash animation plays
  // Assert preview overlay appears
});

test('Tooltip appears on hover', () => {
  // Hover over service card
  // Wait 200ms
  // Assert tooltip is visible
});
```

### 10.3 Accessibility Tests

**Tool:** axe-core automated scanner

```javascript
test('Dashboard meets WCAG 2.1 AA', async () => {
  const results = await axe.run(document);
  expect(results.violations).toHaveLength(0);
});
```

**Manual Tests:**
1. Keyboard navigation (Tab, Enter, Escape)
2. Screen reader testing (NVDA/JAWS)
3. Focus management (visible outlines)

---

## 11. DEPLOYMENT CHECKLIST

- [ ] `data/captures/` directory exists with write permissions
- [ ] CSS variables defined in both `:root` and `[data-theme="light"]`
- [ ] All icons have `aria-label` attributes
- [ ] Theme toggle button has unique ID (`#themeToggle`)
- [ ] Capture button starts disabled, enabled after stream confirms active
- [ ] Flash animation cleanup (remove div after animation ends)
- [ ] localStorage fallback handles disabled storage
- [ ] Image URLs include cache-bust timestamps
- [ ] Cleanup threshold set to 50 images
- [ ] Error toasts styled consistently (error/warning/success)
- [ ] All functions ≤50 lines (auditor verification)
- [ ] Type hints present on all backend functions
- [ ] Docstrings present on all public methods
- [ ] No hardcoded colors outside `:root` definitions

---

## 12. FUTURE ENHANCEMENTS (Out of Scope)

The following features are deliberately excluded from this contract:

1. **Capture History UI:** Browse/delete past captures
2. **Image Annotations:** Draw on captured images before saving
3. **Batch Capture:** Take multiple shots in sequence
4. **Export Formats:** PNG, WebP, or RAW support
5. **Metadata Display:** Resolution, timestamp overlay on preview
6. **Keyboard Shortcuts:** Spacebar to capture, Esc to close

These may be addressed in future iterations if requirements evolve.

---

**End of Contract**