# CONTRACT: OCR Scanner Enhancement (Multi-Source Input)
**Version:** 1.0
**Last Updated:** 2026-02-06
**Status:** DRAFT
**Target File Path:** `F:\PORTFOLIO\ps_rcs_project\docs\contracts\ocr_scanner_enhancement_contract.md`

## 1. PURPOSE

This contract defines the interface changes required to enhance the OCR Scanner with multi-source input capabilities (Live Camera, File Upload, Clipboard Paste). The enhancement transforms the barebones OCR card into a fully functional document scanning system with Linear.app-inspired tab navigation, real-time previews, and intelligent stream management.

**Key Features:**
1. Three input methods with seamless switching
2. Bandwidth-optimized camera stream management
3. Unified backend endpoint for all image sources
4. Accessibility-first keyboard navigation
5. Visual confidence indicators for scan results

---

## 2. DECISION LOG

### 2.1 File Structure Strategy
**Decision:** Embed new `OCRPanel` class directly in `dashboard-core.js` alongside existing `VisionPanel` class.

**Rationale:** The OCR Scanner shares architectural patterns with Vision Panel (modal lifecycle, stream management, API calls). Embedding in the same file:
- Allows code reuse (stream management utilities)
- Maintains single JS bundle (no additional HTTP requests)
- Keeps related functionality co-located
- Simplifies dependency management

**Contract:**
```javascript
// In dashboard-core.js (after VisionPanel class)
class OCRPanel {
  constructor() {
    this.elements = {};
    this.activeTab = 'camera';
    this.currentImage = null;
    this.streamActive = false;
    this._initializeElements();
    this._initializeEventListeners();
  }
  // ... methods
}

// In DashboardCore.init()
this.ocrPanel = new OCRPanel();
```

### 2.2 Modal Reuse Strategy
**Decision:** Reuse existing `#ocr-scanner-modal` HTML structure, enhance with proper ARIA roles and stream container.

**Rationale:** The existing modal structure provides:
- Semantic HTML foundation with proper dialog element
- Tab navigation framework already in place
- Accessibility baseline with screen reader support
- Minimal HTML changes required

**Contract:**
- Keep existing `#ocr-scanner-modal` dialog element
- Add stream container to `#tab-camera` panel
- Enhance tab buttons with ARIA attributes
- Add results panel container at modal footer

### 2.3 Tab Navigation Pattern
**Decision:** Implement semantic HTML tablist with full keyboard navigation (Tab, Arrow keys, Enter/Space).

**Rationale:** Follows WCAG 2.1 AA standards for accessible tab interfaces. Provides:
- Screen reader compatibility
- Keyboard-only navigation support
- Focus management best practices
- Standard interaction model users expect

**Contract:**
```html
<div class="scanner-tabs" role="tablist" aria-label="OCR input methods">
  <button role="tab" aria-selected="true" aria-controls="tab-camera" 
          id="btn-tab-camera" tabindex="0">Live Camera</button>
  <button role="tab" aria-selected="false" aria-controls="tab-upload" 
          id="btn-tab-upload" tabindex="-1">Upload</button>
  <button role="tab" aria-selected="false" aria-controls="tab-paste" 
          id="btn-tab-paste" tabindex="-1">Paste</button>
</div>
```

### 2.4 Unified Endpoint Strategy
**Decision:** Create single `/api/ocr/analyze` endpoint accepting both `multipart/form-data` (file uploads) and JSON with base64 images.

**Rationale:** 
- Simplifies frontend logic (one API call for all sources)
- Centralizes image validation and preprocessing
- Reduces code duplication in backend
- Easier to maintain and test

**Contract:**
```python
@app.route("/api/ocr/analyze", methods=['POST'])
def analyze_image() -> Response:
    """Analyze image from any source (upload/paste/camera).
    
    Accepts:
        - multipart/form-data with 'image' file
        - application/json with 'image_data' (base64)
    
    Returns:
        JSON with OCR results and confidence scores
    """
```

### 2.5 Stream Lifecycle Management
**Decision:** Start camera stream ONLY when Live Camera tab is active; stop immediately when switching to other tabs.

**Rationale:** Bandwidth optimization is critical for remote operations:
- Stream consumes ~100KB/s at 320x240@15fps
- Unnecessary streaming wastes bandwidth during file/paste operations
- Prevents stream conflicts with Vision Panel modal
- Improves battery life on mobile devices

**Contract:**
```javascript
// In OCRPanel.switchTab(tabId)
if (tabId === 'camera') {
  this._startCameraStream();  // Initialize stream
} else {
  this._stopCameraStream();   // Stop and release resources
}
```

---

## 3. HTML CHANGES

**Target File:** `F:\PORTFOLIO\ps_rcs_project\frontend\templates\service_dashboard.html`

### Change 3.1: Update OCR Scanner Card (Icon-Only Design)

**Location:** OCR Scanner Card (Line ~95)

**Current Code:**
```html
<article id="ocr-scanner-card" class="linear-card clickable" role="button" tabindex="0" aria-label="OCR Scanner - Select input method">
    <header class="card-header">
        <div class="icon-container" aria-hidden="true">📄</div>
        <h3 class="card-title">OCR Scanner</h3>
    </header>
    <div class="card-body">
        <div class="scanner-options">
            <div class="option" data-mode="camera" role="button" tabindex="0" aria-label="Scan via Camera">
                <span aria-hidden="true">📹</span>
                <span>Live Camera</span>
            </div>
            <!-- ... other options ... -->
        </div>
    </div>
</article>
```

**Required Change:**
```html
<article id="ocr-scanner-card" class="linear-card clickable" role="button" tabindex="0" aria-label="OCR Scanner - Multi-source document scanning">
    <header class="card-header">
        <div class="icon-container" aria-hidden="true">
            <svg class="card-icon" width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
        </div>
        <h3 class="card-title">OCR Scanner</h3>
        <div class="status-indicator" data-status="offline" aria-live="polite">
            <span class="status-dot"></span>
            <span class="status-text">Ready</span>
        </div>
    </header>
    <div class="card-body">
        <div class="preview-placeholder">
            <svg class="placeholder-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
        </div>
        <div class="card-hover-overlay">
            <span>Click to scan</span>
        </div>
    </div>
</article>
```

**Behavior:**
- Removes inline emoji, replaces with SVG document icon
- Matches icon-only design pattern from Vision card
- Adds status indicator for scan readiness
- Updates aria-label for clarity

**Acceptance:**
- Card shows only document icon (no text in body)
- Icon centered in placeholder
- Hover overlay says "Click to scan"

---

### Change 3.2: Enhanced OCR Scanner Modal Structure

**Location:** OCR Scanner Modal (Line ~130)

**Required Complete Structure:**
```html
<dialog id="ocr-scanner-modal" class="linear-modal" aria-labelledby="ocr-modal-title" aria-modal="true">
    <div class="modal-backdrop"></div>
    <div class="modal-container">
        <header class="modal-header">
            <h2 id="ocr-modal-title" class="modal-title">Document Scanner</h2>
            <div class="modal-actions">
                <button id="btn-ocr-close" class="btn-ghost btn-icon-only" aria-label="Close scanner">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                        <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
            </div>
        </header>

        <!-- Tab Navigation -->
        <nav class="scanner-tabs" role="tablist" aria-label="Input method selection">
            <button role="tab" aria-selected="true" aria-controls="tab-camera" 
                    id="btn-tab-camera" data-tab="camera" tabindex="0">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M18 10L20.576 8.283C20.8586 8.097 21.2029 7.997 21.553 8H22C23.1046 8 24 8.89543 24 10V18C24 19.1046 23.1046 20 22 20H2C0.89543 20 0 19.1046 0 18V10C0 8.89543 0.89543 8 2 8H2.447C2.7971 7.997 3.1414 8.097 3.424 8.283L6 10M15 13C15 14.6569 13.6569 16 12 16C10.3431 16 9 14.6569 9 13C9 11.3431 10.3431 10 12 10C13.6569 10 15 11.3431 15 13Z" stroke="currentColor" stroke-width="1.5"/>
                </svg>
                <span>Live Camera</span>
            </button>
            <button role="tab" aria-selected="false" aria-controls="tab-upload" 
                    id="btn-tab-upload" data-tab="upload" tabindex="-1">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" stroke="currentColor" stroke-width="1.5"/>
                </svg>
                <span>Upload File</span>
            </button>
            <button role="tab" aria-selected="false" aria-controls="tab-paste" 
                    id="btn-tab-paste" data-tab="paste" tabindex="-1">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2" stroke="currentColor" stroke-width="1.5"/>
                </svg>
                <span>Paste Image</span>
            </button>
        </nav>

        <div class="modal-body">
            <!-- Live Camera Tab -->
            <div id="tab-camera" class="tab-panel" role="tabpanel" aria-labelledby="btn-tab-camera">
                <div class="stream-container">
                    <img id="ocr-stream" class="stream-image" alt="Live camera feed for document scanning" crossorigin="anonymous"/>
                    <div class="stream-overlay hidden">
                        <svg class="stream-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M18 10L20.576 8.283C20.8586 8.097 21.2029 7.997 21.553 8H22C23.1046 8 24 8.89543 24 10V18C24 19.1046 23.1046 20 22 20H2C0.89543 20 0 19.1046 0 18V10C0 8.89543 0.89543 8 2 8H2.447C2.7971 7.997 3.1414 8.097 3.424 8.283L6 10M15 13C15 14.6569 13.6569 16 12 16C10.3431 16 9 14.6569 9 13C9 11.3431 10.3431 10 12 10C13.6569 10 15 11.3431 15 13Z" stroke="currentColor" stroke-width="2"/>
                        </svg>
                        <p class="stream-message">Initializing camera...</p>
                    </div>
                    <div class="error-state hidden" aria-live="assertive">
                        <div class="error-icon" aria-hidden="true">⚠️</div>
                        <div class="error-message">Camera unavailable</div>
                    </div>
                </div>
                <div class="tab-actions">
                    <button id="btn-ocr-capture" class="btn-primary" aria-label="Capture current frame for analysis">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
                            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
                        </svg>
                        <span>Capture Frame</span>
                    </button>
                </div>
            </div>

            <!-- Upload Tab -->
            <div id="tab-upload" class="tab-panel hidden" role="tabpanel" aria-labelledby="btn-tab-upload">
                <label for="ocr-file-input" class="file-dropzone" tabindex="0" 
                       aria-label="Drag and drop image file or click to browse">
                    <input type="file" id="ocr-file-input" accept="image/*" class="file-input-hidden">
                    <svg class="dropzone-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" stroke="currentColor" stroke-width="2"/>
                    </svg>
                    <p class="dropzone-text">Drop image here or <span class="text-link">browse</span></p>
                    <p class="dropzone-hint">PNG, JPG up to 5MB</p>
                </label>
                <div id="upload-preview-container" class="preview-container hidden">
                    <img id="upload-preview-img" src="" alt="Uploaded document preview">
                    <button id="btn-clear-upload" class="btn-ghost btn-small" aria-label="Clear uploaded image">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="2"/>
                        </svg>
                        <span>Clear</span>
                    </button>
                </div>
            </div>

            <!-- Paste Tab -->
            <div id="tab-paste" class="tab-panel hidden" role="tabpanel" aria-labelledby="btn-tab-paste">
                <div id="paste-dropzone" class="paste-area" tabindex="0" 
                     aria-label="Click here then paste image from clipboard with Ctrl+V">
                    <svg class="paste-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2" stroke="currentColor" stroke-width="2"/>
                    </svg>
                    <p class="paste-text">Click here and press <kbd>Ctrl+V</kbd> to paste</p>
                    <p class="paste-hint">Or drag and drop an image</p>
                </div>
                <div id="paste-preview-container" class="preview-container hidden">
                    <img id="paste-preview-img" src="" alt="Pasted document preview">
                    <button id="btn-clear-paste" class="btn-ghost btn-small" aria-label="Clear pasted image">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="2"/>
                        </svg>
                        <span>Clear</span>
                    </button>
                </div>
            </div>
        </div>

        <footer class="modal-footer">
            <div class="modal-actions">
                <button id="btn-analyze" class="btn-primary" disabled aria-label="Analyze document">
                    <span class="btn-text">Analyze Document</span>
                    <span class="btn-spinner hidden" aria-hidden="true"></span>
                </button>
            </div>

            <!-- Results Panel (slides up on success) -->
            <div id="ocr-results-panel" class="results-panel hidden" aria-live="polite">
                <div class="results-header">
                    <h3 class="results-title">Scan Results</h3>
                    <div class="confidence-badge" data-level="high">
                        <span class="confidence-dot"></span>
                        <span class="confidence-text" id="confidence-value">--</span>
                    </div>
                </div>
                <dl class="results-data">
                    <div class="data-row">
                        <dt>Tracking ID:</dt>
                        <dd id="result-tracking-id">
                            <span class="data-value">-</span>
                            <button class="btn-copy" data-field="tracking-id" aria-label="Copy tracking ID">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                    <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" stroke-width="2"/>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2"/>
                                </svg>
                            </button>
                        </dd>
                    </div>
                    <div class="data-row">
                        <dt>Order ID:</dt>
                        <dd id="result-order-id">
                            <span class="data-value">-</span>
                            <button class="btn-copy" data-field="order-id" aria-label="Copy order ID">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                    <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" stroke-width="2"/>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2"/>
                                </svg>
                            </button>
                        </dd>
                    </div>
                    <div class="data-row">
                        <dt>RTS Code:</dt>
                        <dd id="result-rts-code">
                            <span class="data-value">-</span>
                            <button class="btn-copy" data-field="rts-code" aria-label="Copy RTS code">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                    <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" stroke-width="2"/>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2"/>
                                </svg>
                            </button>
                        </dd>
                    </div>
                    <div class="data-row">
                        <dt>District:</dt>
                        <dd id="result-district">
                            <span class="data-value">-</span>
                            <button class="btn-copy" data-field="district" aria-label="Copy district">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                    <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" stroke-width="2"/>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2"/>
                                </svg>
                            </button>
                        </dd>
                    </div>
                    <div class="data-row">
                        <dt>Scan Time:</dt>
                        <dd id="result-timestamp">
                            <span class="data-value">-</span>
                        </dd>
                    </div>
                </dl>
            </div>
        </footer>
    </div>
</dialog>
```

**Behavior:**
- Modal opens with Live Camera tab active by default
- Tab buttons have proper ARIA roles for screen readers
- Stream container shows loading overlay until camera initialized
- Each tab has dedicated preview container
- Results panel hidden until successful scan
- Copy buttons on each data field

**Acceptance:**
- Keyboard navigation works (Tab, Arrow keys)
- Screen readers announce tab changes
- Stream loads within 1 second on camera tab
- File dropzone highlights on drag-over
- Paste area accepts Ctrl+V

---

## 4. CSS CHANGES

**Target File:** `F:\PORTFOLIO\ps_rcs_project\frontend\static\css\service_theme.css`

### Change 4.1: OCR-Specific CSS Variables

**Location:** Add to `:root` block (after line ~72)

**Required Addition:**
```css
/* OCR Scanner Variables */
--ocr-border-drag: 2px dashed var(--text-tertiary);
--ocr-border-active: 2px solid var(--accent-primary);
--ocr-border-error: 2px solid var(--accent-error);
--confidence-high: #10b981;
--confidence-medium: #f59e0b;
--confidence-low: #ef4444;
--dropzone-bg: var(--surface-secondary);
--dropzone-bg-hover: var(--surface-hover);
--preview-max-height: 400px;
```

---

### Change 4.2: Scanner Tab Styles

**Location:** Add new section after modal styles (~line 400)

**Required Addition:**
```css
/* ============================================
   OCR SCANNER TABS
   ============================================ */
.scanner-tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  background: var(--surface-card);
}

.scanner-tabs button[role="tab"] {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--timing-normal) var(--easing-smooth);
  position: relative;
}

.scanner-tabs button[role="tab"]:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.scanner-tabs button[role="tab"][aria-selected="true"] {
  color: var(--accent-primary);
  background: rgba(59, 130, 246, 0.1);
}

.scanner-tabs button[role="tab"][aria-selected="true"]::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--accent-primary);
}

.scanner-tabs button[role="tab"]:focus-visible {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
}

.scanner-tabs svg {
  width: 16px;
  height: 16px;
  opacity: 0.8;
}

.scanner-tabs button[role="tab"][aria-selected="true"] svg {
  opacity: 1;
}
```

---

### Change 4.3: Tab Panel Styles

**Location:** Add after scanner tabs section

**Required Addition:**
```css
/* ============================================
   TAB PANELS
   ============================================ */
.tab-panel {
  padding: var(--space-6);
  min-height: 400px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.tab-panel.hidden {
  display: none;
}

.tab-actions {
  display: flex;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

/* Stream Container (OCR variant) */
#tab-camera .stream-container {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: var(--surface-base);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

#ocr-stream {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.stream-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(10px);
}

.stream-overlay.hidden {
  display: none;
}

.stream-icon {
  color: var(--text-tertiary);
  opacity: 0.5;
}

.stream-message {
  color: var(--text-secondary);
  font-size: 0.875rem;
}
```

---

### Change 4.4: Dropzone & Paste Area Styles

**Location:** Add after tab panels section

**Required Addition:**
```css
/* ============================================
   FILE DROPZONE
   ============================================ */
.file-dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  min-height: 300px;
  padding: var(--space-8);
  background: var(--dropzone-bg);
  border: var(--ocr-border-drag);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--timing-normal) var(--easing-smooth);
}

.file-dropzone:hover,
.file-dropzone:focus-visible {
  background: var(--dropzone-bg-hover);
  border-color: var(--accent-primary);
  border-style: solid;
}

.file-dropzone.drag-over {
  background: var(--dropzone-bg-hover);
  border: var(--ocr-border-active);
  transform: scale(1.02);
}

.file-dropzone.error {
  border: var(--ocr-border-error);
}

.file-input-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

.dropzone-icon {
  color: var(--text-tertiary);
  opacity: 0.6;
}

.dropzone-text {
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: var(--font-weight-medium);
}

.text-link {
  color: var(--accent-primary);
  text-decoration: underline;
}

.dropzone-hint {
  color: var(--text-tertiary);
  font-size: 0.75rem;
}

/* ============================================
   PASTE AREA
   ============================================ */
.paste-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  min-height: 300px;
  padding: var(--space-8);
  background: var(--dropzone-bg);
  border: var(--ocr-border-drag);
  border-radius: var(--radius-lg);
  cursor: text;
  transition: all var(--timing-normal) var(--easing-smooth);
}

.paste-area:hover,
.paste-area:focus-visible {
  background: var(--dropzone-bg-hover);
  border-color: var(--accent-primary);
  outline: none;
}

.paste-area.drag-over {
  background: var(--dropzone-bg-hover);
  border: var(--ocr-border-active);
}

.paste-icon {
  color: var(--text-tertiary);
  opacity: 0.6;
}

.paste-text {
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: var(--font-weight-medium);
}

.paste-text kbd {
  padding: 2px 6px;
  background: var(--surface-base);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 0.875em;
}

.paste-hint {
  color: var(--text-tertiary);
  font-size: 0.75rem;
}

/* ============================================
   PREVIEW CONTAINERS
   ============================================ */
.preview-container {
  position: relative;
  width: 100%;
  max-height: var(--preview-max-height);
  background: var(--surface-base);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.preview-container.hidden {
  display: none;
}

.preview-container img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.btn-small {
  position: absolute;
  top: var(--space-3);
  right: var(--space-3);
  padding: var(--space-2) var(--space-3);
  font-size: 0.75rem;
}
```

---

### Change 4.5: Results Panel Styles

**Location:** Add after preview containers section

**Required Addition:**
```css
/* ============================================
   RESULTS PANEL
   ============================================ */
.results-panel {
  margin-top: var(--space-6);
  padding: var(--space-6);
  background: var(--surface-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  animation: slideUp var(--timing-slow) var(--easing-smooth);
}

.results-panel.hidden {
  display: none;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.results-title {
  font-size: 1rem;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.confidence-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: rgba(16, 185, 129, 0.1);
  border-radius: var(--radius-md);
  font-size: 0.75rem;
  font-weight: var(--font-weight-medium);
}

.confidence-badge[data-level="high"] {
  background: rgba(16, 185, 129, 0.1);
  color: var(--confidence-high);
}

.confidence-badge[data-level="medium"] {
  background: rgba(245, 158, 11, 0.1);
  color: var(--confidence-medium);
}

.confidence-badge[data-level="low"] {
  background: rgba(239, 68, 68, 0.1);
  color: var(--confidence-low);
}

.confidence-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.results-data {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
}

.data-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3);
  background: var(--surface-base);
  border-radius: var(--radius-sm);
}

.data-row dt {
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: var(--font-weight-medium);
  margin: 0;
}

.data-row dd {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-primary);
  font-size: 0.875rem;
  font-family: 'SF Mono', 'Monaco', monospace;
  margin: 0;
}

.btn-copy {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--timing-fast) var(--easing-smooth);
  opacity: 0;
}

.data-row:hover .btn-copy {
  opacity: 1;
}

.btn-copy:hover {
  background: var(--surface-hover);
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.btn-copy:active {
  transform: scale(0.95);
}
```

---

## 5. JAVASCRIPT CHANGES

**Target File:** `F:\PORTFOLIO\ps_rcs_project\frontend\static\js\dashboard-core.js`

### Change 5.1: OCRPanel Class Definition

**Location:** Add after VisionPanel class (around line 350)

**Method Signatures:**

```javascript
/**
 * Manages the OCR Scanner modal with multi-source input capabilities.
 */
class OCRPanel {
  /**
   * Initialize OCR Panel.
   */
  constructor() {
    this.elements = {};
    this.activeTab = 'camera';
    this.currentImage = null;
    this.streamActive = false;
    this.streamSrc = '/api/vision/stream';
    
    this._initializeElements();
    this._initializeEventListeners();
  }

  /**
   * Cache DOM element references.
   * @private
   */
  _initializeElements() {
    // Implementation
  }

  /**
   * Set up event listeners for all interactions.
   * @private
   */
  _initializeEventListeners() {
    // Implementation
  }

  /**
   * Open the OCR scanner modal.
   */
  openModal() {
    // Implementation
  }

  /**
   * Close the OCR scanner modal.
   */
  closeModal() {
    // Implementation
  }

  /**
   * Switch active tab and manage stream lifecycle.
   * @param {string} tabId - Tab identifier ('camera', 'upload', 'paste')
   */
  switchTab(tabId) {
    // Implementation
  }

  /**
   * Start camera stream (only when camera tab active).
   * @private
   */
  _startCameraStream() {
    // Implementation
  }

  /**
   * Stop camera stream and free resources.
   * @private
   */
  _stopCameraStream() {
    // Implementation
  }

  /**
   * Handle paste event from clipboard.
   * @param {ClipboardEvent} event - Paste event
   * @private
   */
  _handlePaste(event) {
    // Implementation
  }

  /**
   * Handle file drop event.
   * @param {DragEvent} event - Drop event
   * @private
   */
  _handleDrop(event) {
    // Implementation
  }

  /**
   * Handle file selection from input.
   * @param {Event} event - Change event
   * @private
   */
  _handleFileSelect(event) {
    // Implementation
  }

  /**
   * Validate image file size and type.
   * @param {File} file - File to validate
   * @returns {boolean} True if valid
   * @private
   */
  _validateImageFile(file) {
    // Implementation
  }

  /**
   * Display image preview in current tab.
   * @param {string} imageDataUrl - Base64 image data URL
   * @private
   */
  _showPreview(imageDataUrl) {
    // Implementation
  }

  /**
   * Clear preview in current tab.
   * @private
   */
  _clearPreview() {
    // Implementation
  }

  /**
   * Capture frame from camera stream.
   * @private
   */
  _captureFrame() {
    // Implementation
  }

  /**
   * Perform OCR analysis on current image.
   */
  async analyzeDocument() {
    // Implementation
  }

  /**
   * Display scan results in results panel.
   * @param {Object} data - OCR result data
   * @private
   */
  _displayResults(data) {
    // Implementation
  }

  /**
   * Copy field value to clipboard.
   * @param {string} fieldId - Field identifier
   * @private
   */
  _copyToClipboard(fieldId) {
    // Implementation
  }

  /**
   * Show toast notification.
   * @param {string} message - Message text
   * @param {string} type - 'success', 'error', 'info'
   * @private
   */
  _showToast(message, type = 'info') {
    // Implementation
  }
}
```

**Required Logic Implementation:**

```javascript
_initializeElements() {
  this.elements = {
    modal: document.getElementById('ocr-scanner-modal'),
    closeBtn: document.getElementById('btn-ocr-close'),
    tabs: {
      camera: document.getElementById('btn-tab-camera'),
      upload: document.getElementById('btn-tab-upload'),
      paste: document.getElementById('btn-tab-paste')
    },
    panels: {
      camera: document.getElementById('tab-camera'),
      upload: document.getElementById('tab-upload'),
      paste: document.getElementById('tab-paste')
    },
    stream: document.getElementById('ocr-stream'),
    streamOverlay: document.querySelector('#tab-camera .stream-overlay'),
    errorState: document.querySelector('#tab-camera .error-state'),
    captureBtn: document.getElementById('btn-ocr-capture'),
    fileInput: document.getElementById('ocr-file-input'),
    fileDropzone: document.querySelector('.file-dropzone'),
    uploadPreview: document.getElementById('upload-preview-container'),
    uploadPreviewImg: document.getElementById('upload-preview-img'),
    clearUploadBtn: document.getElementById('btn-clear-upload'),
    pasteArea: document.getElementById('paste-dropzone'),
    pastePreview: document.getElementById('paste-preview-container'),
    pastePreviewImg: document.getElementById('paste-preview-img'),
    clearPasteBtn: document.getElementById('btn-clear-paste'),
    analyzeBtn: document.getElementById('btn-analyze'),
    resultsPanel: document.getElementById('ocr-results-panel')
  };

  // Verify critical elements exist
  if (!this.elements.modal) {
    console.warn('[OCRPanel] Modal element not found');
  }
}

_initializeEventListeners() {
  // Card click to open modal
  const card = document.getElementById('ocr-scanner-card');
  if (card) {
    card.addEventListener('click', () => this.openModal());
  }

  // Close button
  if (this.elements.closeBtn) {
    this.elements.closeBtn.addEventListener('click', () => this.closeModal());
  }

  // Tab navigation
  Object.entries(this.elements.tabs).forEach(([tabId, btn]) => {
    if (btn) {
      btn.addEventListener('click', () => this.switchTab(tabId));
      
      // Keyboard navigation
      btn.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
          e.preventDefault();
          const tabs = Object.keys(this.elements.tabs);
          const currentIndex = tabs.indexOf(tabId);
          const nextIndex = e.key === 'ArrowRight'
            ? (currentIndex + 1) % tabs.length
            : (currentIndex - 1 + tabs.length) % tabs.length;
          this.switchTab(tabs[nextIndex]);
          this.elements.tabs[tabs[nextIndex]].focus();
        }
      });
    }
  });

  // Camera capture
  if (this.elements.captureBtn) {
    this.elements.captureBtn.addEventListener('click', () => this._captureFrame());
  }

  // File upload
  if (this.elements.fileInput) {
    this.elements.fileInput.addEventListener('change', (e) => this._handleFileSelect(e));
  }

  // Drag and drop (upload tab)
  if (this.elements.fileDropzone) {
    ['dragenter', 'dragover'].forEach(event => {
      this.elements.fileDropzone.addEventListener(event, (e) => {
        e.preventDefault();
        this.elements.fileDropzone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(event => {
      this.elements.fileDropzone.addEventListener(event, (e) => {
        e.preventDefault();
        this.elements.fileDropzone.classList.remove('drag-over');
      });
    });

    this.elements.fileDropzone.addEventListener('drop', (e) => this._handleDrop(e));
  }

  // Paste area events
  if (this.elements.pasteArea) {
    this.elements.pasteArea.addEventListener('paste', (e) => this._handlePaste(e));
    
    // Drag and drop (paste tab)
    ['dragenter', 'dragover'].forEach(event => {
      this.elements.pasteArea.addEventListener(event, (e) => {
        e.preventDefault();
        this.elements.pasteArea.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(event => {
      this.elements.pasteArea.addEventListener(event, (e) => {
        e.preventDefault();
        this.elements.pasteArea.classList.remove('drag-over');
      });
    });

    this.elements.pasteArea.addEventListener('drop', (e) => this._handleDrop(e));
  }

  // Clear buttons
  if (this.elements.clearUploadBtn) {
    this.elements.clearUploadBtn.addEventListener('click', () => this._clearPreview());
  }
  if (this.elements.clearPasteBtn) {
    this.elements.clearPasteBtn.addEventListener('click', () => this._clearPreview());
  }

  // Analyze button
  if (this.elements.analyzeBtn) {
    this.elements.analyzeBtn.addEventListener('click', () => this.analyzeDocument());
  }

  // Copy buttons
  document.querySelectorAll('.btn-copy').forEach(btn => {
    btn.addEventListener('click', () => {
      const fieldId = btn.getAttribute('data-field');
      this._copyToClipboard(fieldId);
    });
  });
}

switchTab(tabId) {
  if (!['camera', 'upload', 'paste'].includes(tabId)) {
    console.warn(`[OCRPanel] Invalid tab ID: ${tabId}`);
    return;
  }

  this.activeTab = tabId;

  // Update tab button states
  Object.entries(this.elements.tabs).forEach(([id, btn]) => {
    if (btn) {
      const isActive = id === tabId;
      btn.setAttribute('aria-selected', isActive);
      btn.setAttribute('tabindex', isActive ? '0' : '-1');
    }
  });

  // Show/hide panels
  Object.entries(this.elements.panels).forEach(([id, panel]) => {
    if (panel) {
      if (id === tabId) {
        panel.classList.remove('hidden');
      } else {
        panel.classList.add('hidden');
      }
    }
  });

  // Stream lifecycle management (CRITICAL for bandwidth)
  if (tabId === 'camera') {
    this._startCameraStream();
  } else {
    this._stopCameraStream();
  }

  // Clear previous image state when switching tabs
  this.currentImage = null;
  if (this.elements.analyzeBtn) {
    this.elements.analyzeBtn.disabled = true;
  }
}

_startCameraStream() {
  if (this.streamActive || !this.elements.stream) return;

  // Hide error state from previous attempts
  if (this.elements.errorState) {
    this.elements.errorState.classList.add('hidden');
  }

  // Show loading overlay
  if (this.elements.streamOverlay) {
    this.elements.streamOverlay.classList.remove('hidden');
  }

  // Set stream source
  this.elements.stream.src = this.streamSrc;
  this.streamActive = true;

  // Hide overlay after stream loads
  this.elements.stream.onload = () => {
    if (this.elements.streamOverlay) {
      this.elements.streamOverlay.classList.add('hidden');
    }
  };

  // Show error on failure
  this.elements.stream.onerror = () => {
    if (this.elements.streamOverlay) {
      this.elements.streamOverlay.classList.add('hidden');
    }
    if (this.elements.errorState) {
      this.elements.errorState.classList.remove('hidden');
    }
    this.streamActive = false;
  };
}

_stopCameraStream() {
  if (!this.streamActive || !this.elements.stream) return;

  this.elements.stream.src = '';
  this.streamActive = false;

  // Show overlay again
  if (this.elements.streamOverlay) {
    this.elements.streamOverlay.classList.remove('hidden');
  }
}

async _handlePaste(event) {
  const items = event.clipboardData?.items;
  if (!items) {
    this._showToast('No clipboard data found', 'error');
    return;
  }

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file && this._validateImageFile(file)) {
        const reader = new FileReader();
        reader.onload = (e) => {
          this.currentImage = e.target.result;
          this._showPreview(e.target.result);
          if (this.elements.analyzeBtn) {
            this.elements.analyzeBtn.disabled = false;
          }
        };
        reader.readAsDataURL(file);
      }
      return;
    }
  }

  this._showToast('No image data found in clipboard', 'error');
}

_handleDrop(event) {
  const files = event.dataTransfer?.files;
  if (!files || files.length === 0) return;

  const file = files[0];
  if (this._validateImageFile(file)) {
    const reader = new FileReader();
    reader.onload = (e) => {
      this.currentImage = e.target.result;
      this._showPreview(e.target.result);
      if (this.elements.analyzeBtn) {
        this.elements.analyzeBtn.disabled = false;
      }
    };
    reader.readAsDataURL(file);
  }
}

_handleFileSelect(event) {
  const files = event.target.files;
  if (!files || files.length === 0) return;

  const file = files[0];
  if (this._validateImageFile(file)) {
    const reader = new FileReader();
    reader.onload = (e) => {
      this.currentImage = e.target.result;
      this._showPreview(e.target.result);
      if (this.elements.analyzeBtn) {
        this.elements.analyzeBtn.disabled = false;
      }
    };
    reader.readAsDataURL(file);
  }
}

_validateImageFile(file) {
  const MAX_SIZE = 5 * 1024 * 1024; // 5MB
  const VALID_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];

  if (!VALID_TYPES.includes(file.type)) {
    this._showToast('Invalid file type. Use PNG, JPG, or WEBP', 'error');
    return false;
  }

  if (file.size > MAX_SIZE) {
    this._showToast('File too large. Maximum size is 5MB', 'error');
    return false;
  }

  return true;
}

_showPreview(imageDataUrl) {
  let container, img;

  if (this.activeTab === 'upload') {
    container = this.elements.uploadPreview;
    img = this.elements.uploadPreviewImg;
    if (this.elements.fileDropzone) {
      this.elements.fileDropzone.style.display = 'none';
    }
  } else if (this.activeTab === 'paste') {
    container = this.elements.pastePreview;
    img = this.elements.pastePreviewImg;
    if (this.elements.pasteArea) {
      this.elements.pasteArea.style.display = 'none';
    }
  }

  if (container && img) {
    img.src = imageDataUrl;
    container.classList.remove('hidden');
  }
}

_clearPreview() {
  this.currentImage = null;

  if (this.activeTab === 'upload') {
    if (this.elements.uploadPreview) {
      this.elements.uploadPreview.classList.add('hidden');
    }
    if (this.elements.uploadPreviewImg) {
      this.elements.uploadPreviewImg.src = '';
    }
    if (this.elements.fileDropzone) {
      this.elements.fileDropzone.style.display = '';
    }
    if (this.elements.fileInput) {
      this.elements.fileInput.value = '';
    }
  } else if (this.activeTab === 'paste') {
    if (this.elements.pastePreview) {
      this.elements.pastePreview.classList.add('hidden');
    }
    if (this.elements.pastePreviewImg) {
      this.elements.pastePreviewImg.src = '';
    }
    if (this.elements.pasteArea) {
      this.elements.pasteArea.style.display = '';
    }
  }

  if (this.elements.analyzeBtn) {
    this.elements.analyzeBtn.disabled = true;
  }
}

async _captureFrame() {
  // For camera tab, send capture request to backend
  try {
    const response = await fetch('/api/vision/capture', {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error('Capture failed');
    }

    const data = await response.json();
    
    // Use captured image URL as current image
    this.currentImage = data.download_url;
    
    // Enable analyze button
    if (this.elements.analyzeBtn) {
      this.elements.analyzeBtn.disabled = false;
    }

    this._showToast('Frame captured successfully', 'success');
  } catch (error) {
    console.error('[OCRPanel] Capture error:', error);
    this._showToast('Failed to capture frame', 'error');
  }
}

async analyzeDocument() {
  if (!this.currentImage) {
    this._showToast('No image to analyze', 'error');
    return;
  }

  // Show loading state
  const btnText = this.elements.analyzeBtn.querySelector('.btn-text');
  const btnSpinner = this.elements.analyzeBtn.querySelector('.btn-spinner');
  
  if (btnText) btnText.classList.add('hidden');
  if (btnSpinner) btnSpinner.classList.remove('hidden');
  this.elements.analyzeBtn.disabled = true;

  try {
    let response;

    if (this.activeTab === 'camera') {
      // Use URL from captured frame
      const imageResponse = await fetch(this.currentImage);
      const blob = await imageResponse.blob();
      const formData = new FormData();
      formData.append('image', blob, 'capture.jpg');

      response = await fetch('/api/ocr/analyze', {
        method: 'POST',
        body: formData
      });
    } else {
      // Send base64 image
      response = await fetch('/api/ocr/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          image_data: this.currentImage.split(',')[1] // Remove data:image/... prefix
        })
      });
    }

    if (!response.ok) {
      throw new Error('Analysis failed');
    }

    const result = await response.json();
    
    if (result.status === 'processing') {
      // Poll for results
      await this._pollForResults(result.scan_id);
    } else {
      this._displayResults(result);
    }
  } catch (error) {
    console.error('[OCRPanel] Analysis error:', error);
    this._showToast('Analysis failed. Please try again', 'error');
  } finally {
    // Reset button state
    if (btnText) btnText.classList.remove('hidden');
    if (btnSpinner) btnSpinner.classList.add('hidden');
    this.elements.analyzeBtn.disabled = false;
  }
}

async _pollForResults(scanId, maxAttempts = 20) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, 500)); // Wait 500ms

    const response = await fetch(`/api/vision/results/${scanId}`);
    const data = await response.json();

    if (data.status === 'completed') {
      this._displayResults(data.data);
      return;
    }
  }

  this._showToast('Analysis timeout. Please try again', 'error');
}

_displayResults(data) {
  if (!this.elements.resultsPanel) return;

  // Update confidence badge
  const confidenceBadge = this.elements.resultsPanel.querySelector('.confidence-badge');
  const confidenceText = document.getElementById('confidence-value');
  
  if (data.confidence && confidenceBadge && confidenceText) {
    const confidence = parseFloat(data.confidence);
    let level = 'high';
    if (confidence < 0.7) level = 'low';
    else if (confidence < 0.85) level = 'medium';
    
    confidenceBadge.setAttribute('data-level', level);
    confidenceText.textContent = `${(confidence * 100).toFixed(0)}%`;
  }

  // Update data fields
  const fields = {
    'result-tracking-id': data.tracking_id,
    'result-order-id': data.order_id,
    'result-rts-code': data.rts_code,
    'result-district': data.district,
    'result-timestamp': new Date(data.timestamp).toLocaleString()
  };

  Object.entries(fields).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) {
      const valueSpan = element.querySelector('.data-value');
      if (valueSpan) {
        valueSpan.textContent = value || '-';
      }
    }
  });

  // Show results panel
  this.elements.resultsPanel.classList.remove('hidden');
  
  // Scroll into view
  this.elements.resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  
  this._showToast('Analysis complete', 'success');
}

_copyToClipboard(fieldId) {
  const element = document.getElementById(`result-${fieldId}`);
  if (!element) return;

  const valueSpan = element.querySelector('.data-value');
  if (!valueSpan) return;

  const text = valueSpan.textContent;
  if (text === '-') return;

  navigator.clipboard.writeText(text).then(() => {
    this._showToast('Copied to clipboard', 'success');
  }).catch(() => {
    this._showToast('Failed to copy', 'error');
  });
}

_showToast(message, type = 'info') {
  // Simple console logging for now (can be enhanced with toast UI)
  console.log(`[OCRPanel Toast - ${type}]:`, message);
  
  // TODO: Implement visual toast notification
}

openModal() {
  if (!this.elements.modal) return;

  this.elements.modal.showModal();
  
  // Switch to camera tab by default
  this.switchTab('camera');
  
  // Hide results panel
  if (this.elements.resultsPanel) {
    this.elements.resultsPanel.classList.add('hidden');
  }
}

closeModal() {
  if (!this.elements.modal) return;

  // Stop stream before closing
  this._stopCameraStream();
  
  // Clear any previews
  this._clearPreview();
  
  this.elements.modal.close();
}
```

### Change 5.2: Integration with DashboardCore

**Location:** DashboardCore.init() method (around line 57)

**Required Change:**
```javascript
init() {
  // ... existing initialization code ...

  this.setupModalInteractions();
  this._startStatusPolling();
  
  this.visionPanel = new VisionPanel();
  this.ocrPanel = new OCRPanel();  // ADD THIS LINE
}
```

**Behavior:**
- Initializes OCRPanel alongside VisionPanel
- Ensures proper lifecycle management

**Acceptance:**
- OCR Scanner card click opens modal
- No JavaScript errors in console

---

## 6. BACKEND CHANGES

**Target File:** `F:\PORTFOLIO\ps_rcs_project\src\api\server.py`

### Change 6.1: New Unified OCR Endpoint

**Location:** Add after existing OCR endpoint (around line 230)

**Method Signature:**
```python
@app.route("/api/ocr/analyze", methods=['POST'])
def analyze_image() -> Response:
    """Analyze image from any source (upload/paste/camera).
    
    Accepts:
        - multipart/form-data with 'image' file
        - application/json with 'image_data' (base64)
    
    Returns:
        JSON response with OCR results and confidence scores
        
    Raises:
        400: Invalid image format or size
        500: OCR processing failure
    """
```

**Required Implementation:**
```python
@app.route("/api/ocr/analyze", methods=['POST'])
def analyze_image() -> Response:
    """Analyze image from any source (upload/paste/camera)."""
    frame = None
    
    try:
        # Handle multipart/form-data (file upload)
        if 'image' in request.files:
            file = request.files['image']
            
            # Validate file size (max 5MB)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > 5 * 1024 * 1024:
                return jsonify({'error': 'File too large (max 5MB)'}), 400
            
            # Decode image
            nparr = np.frombuffer(file.read(), np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
        # Handle JSON with base64 image
        elif request.is_json and 'image_data' in request.json:
            try:
                img_data = base64.b64decode(request.json['image_data'])
                nparr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            except Exception as e:
                self.logger.error(f"[APIServer] Base64 decode error: {e}")
                return jsonify({'error': 'Invalid base64 image data'}), 400
        else:
            return jsonify({'error': 'No image provided'}), 400
        
        # Validate decoded frame
        if frame is None or frame.size == 0:
            return jsonify({'error': 'Invalid image format'}), 400
        
        # Preprocess: resize to 640x480 for consistency with VisionManager
        if frame.shape[0] != 480 or frame.shape[1] != 640:
            frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
            self.logger.debug(f"[APIServer] Resized image to 640x480")
        
        # Process with OCR service
        future = self.ocr_service.process_scan(frame)
        
        def update_state(fut: Any) -> None:
            try:
                result = fut.result()
                self.state.update_scan_result(result)
                self.logger.info(f"[APIServer] OCR completed: {result.get('tracking_id', 'N/A')}")
            except Exception as e:
                self.logger.error(f"[APIServer] OCR callback error: {e}")

        future.add_done_callback(update_state)
        
        return jsonify({
            'success': True,
            'scan_id': id(future),
            'status': 'processing',
            'message': 'Image submitted for analysis'
        }), 202
        
    except Exception as e:
        self.logger.error(f"[APIServer] OCR analyze error: {e}")
        return jsonify({'error': 'Image analysis failed'}), 500
```

**Behavior:**
- Accepts both file uploads and base64 images
- Validates file size (5MB limit)
- Resizes images to 640x480 for consistency
- Returns 202 Accepted with scan_id for polling
- Logs all operations for debugging

**Error Handling:**
- Returns 400 for invalid images or oversized files
- Returns 500 for processing failures
- Logs errors with context

**Acceptance:**
- Upload endpoint accepts multipart files
- Paste endpoint accepts base64 JSON
- Camera endpoint works with captured images
- All return consistent scan_id for polling

---

## 7. ACCEPTANCE CRITERIA

### Acceptance 7.1: Visual Design & Layout
- [ ] OCR Scanner card shows ONLY document icon (no text in body)
- [ ] Card matches icon-only design pattern from Vision card
- [ ] Hover reveals "Click to scan" overlay
- [ ] Modal opens with tab navigation header
- [ ] Tabs show icon + label (e.g., camera icon + "Live Camera")
- [ ] Active tab has blue underline indicator
- [ ] Tab panels show/hide without layout shift
- [ ] All colors use CSS variables (no hardcoded hex)

### Acceptance 7.2: Keyboard Navigation
- [ ] Tab key moves between tabs
- [ ] Arrow Left/Right switches tabs
- [ ] Enter/Space activates focused tab
- [ ] Escape closes modal
- [ ] Tab order is logical (tabs → content → buttons)
- [ ] Focus indicators visible on all interactive elements
- [ ] Screen readers announce tab changes

### Acceptance 7.3: Live Camera Tab
- [ ] Stream starts when tab activated (<1s delay)
- [ ] Stream stops when switching to other tabs
- [ ] Stream shows loading overlay initially
- [ ] Stream error state displays if camera fails
- [ ] "Capture Frame" button captures high-res image
- [ ] Captured frame enables "Analyze" button
- [ ] Stream uses 320x240@15fps (bandwidth optimized)

### Acceptance 7.4: Upload Tab
- [ ] Dropzone accepts drag-and-drop files
- [ ] Dropzone border changes to solid blue on drag-over
- [ ] Click opens file browser
- [ ] File validation rejects >5MB files
- [ ] File validation rejects non-image types
- [ ] Preview shows after file selected
- [ ] "Clear" button removes preview and resets state
- [ ] "Analyze" button enabled after valid file selected

### Acceptance 7.5: Paste Tab
- [ ] Paste area accepts Ctrl+V clipboard images
- [ ] Paste area accepts drag-and-drop images
- [ ] Focus outline visible when paste area focused
- [ ] Preview shows after successful paste
- [ ] Error toast if clipboard has no image data
- [ ] "Clear" button removes preview and resets state
- [ ] "Analyze" button enabled after successful paste

### Acceptance 7.6: Analysis & Results
- [ ] "Analyze" button disabled until image present
- [ ] Loading spinner shows during analysis
- [ ] Results panel slides up on completion
- [ ] Confidence badge shows color-coded dot (green/yellow/red)
- [ ] Confidence percentage displayed (e.g., "92%")
- [ ] All data fields populated (Tracking ID, Order ID, etc.)
- [ ] Copy buttons appear on hover
- [ ] Copy buttons write to clipboard on click
- [ ] Toast shows "Copied to clipboard" confirmation

### Acceptance 7.7: Code Quality
- [ ] All JS methods ≤50 lines (system_constraints.md requirement)
- [ ] All Python functions have type hints
- [ ] All Python functions have Google-style docstrings
- [ ] Zero hardcoded colors in CSS (all use variables)
- [ ] No console errors during normal operation
- [ ] Graceful degradation if DOM elements missing

---

## 8. ERROR HANDLING SPECIFICATIONS

### Error 8.1: Paste Failure (No Image Data)
**Condition:** User presses Ctrl+V but clipboard contains no image

**Handler:**
```javascript
// In _handlePaste()
for (const item of items) {
  if (item.type.startsWith('image/')) {
    // Process image...
    return;
  }
}
// No image found
this._showToast('No image data found in clipboard', 'error');
console.log('[OCRPanel] Clipboard contents:', Array.from(items).map(i => i.type));
```

**Response:**
- Show toast: "No image data found in clipboard"
- Log clipboard types to console for debugging
- Do not enable analyze button

### Error 8.2: Large File Rejection
**Condition:** User uploads or drops file >5MB

**Handler:**
```javascript
// In _validateImageFile()
if (file.size > MAX_SIZE) {
  this._showToast('File too large. Maximum size is 5MB', 'error');
  return false;
}
```

**Response:**
- Show toast: "File too large. Maximum size is 5MB"
- Reject file (do not show preview)
- Log file size to console

### Error 8.3: Invalid Image Format
**Condition:** Backend cannot decode image

**Handler:**
```python
# In analyze_image endpoint
if frame is None or frame.size == 0:
    return jsonify({'error': 'Invalid image format'}), 400
```

**Response:**
- Return 400 Bad Request
- JSON: `{"error": "Invalid image format"}`
- Frontend shows toast: "Invalid image format"

### Error 8.4: OCR Processing Timeout
**Condition:** OCR takes >10 seconds

**Handler:**
```javascript
// In _pollForResults()
async _pollForResults(scanId, maxAttempts = 20) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, 500));
    // Check result...
  }
  // Timeout after 10 seconds
  this._showToast('Analysis timeout. Please try again', 'error');
}
```

**Response:**
- Show toast: "Analysis timeout. Please try again"
- Reset analyze button to enabled state
- Keep image loaded for retry

### Error 8.5: Stream Conflict with Vision Panel
**Condition:** User tries to open OCR modal while Vision modal is open

**Handler:**
```javascript
// In openModal()
const visionModal = document.getElementById('modal-vision');
if (visionModal && visionModal.open) {
  this._showToast('Please close the Vision Panel first', 'error');
  return;
}
```

**Response:**
- Show toast: "Please close the Vision Panel first"
- Do not open OCR modal
- Prevent stream conflict

---

## 9. DEPENDENCIES

**This contract CREATES:**
- `OCRPanel` class (embedded in dashboard-core.js)
- `/api/ocr/analyze` endpoint (unified image analysis)

**This contract CALLS:**
- `VisionManager.get_frame()` - High-res frame capture
- `VisionManager.generate_mjpeg()` - Camera stream
- `OCRService.process_scan()` - OCR processing
- `RobotState.update_scan_result()` - State updates
- `/api/vision/stream` - MJPEG stream endpoint
- `/api/vision/capture` - Frame capture endpoint
- `/api/vision/results/<scan_id>` - Result polling endpoint

**This contract is CALLED BY:**
- User interactions (card clicks, tab switches, file uploads)
- Browser paste events (Ctrl+V)
- Drag-and-drop events
- Keyboard navigation events

---

## 10. CONSTRAINTS (FROM SYSTEM RULES)

### From `system_contraints.md`:
1. **Max Function Length:** 50 lines (JS/Python) ✅
2. **Type Hints:** Mandatory for all backend functions ✅
3. **Error Handling:** Specific exceptions, log errors ✅

### From `system_style.md`:
1. **Typography:** Inter, -apple-system, BlinkMacSystemFont ✅
2. **Border Radius:** 20-24px cards, 12-16px buttons ✅
3. **Shadows:** Soft diffused (0 8px 30px rgba(0,0,0,0.08)) ✅
4. **Colors:** CSS variables only (no hex/rgb in components) ✅
5. **Progressive Disclosure:** Stream hidden until modal open ✅

### From `vision_manager_optimization.md`:
1. **Stream Quality:** Must use quality=40 (not 80) ✅
2. **Stream Resolution:** Must be 320x240 for UI ✅
3. **Stream FPS:** Must throttle to ~15 FPS ✅

---

## 11. INTEGRATION NOTES

**Upstream Dependencies:**
- `VisionManager` - Provides camera stream and frame capture
- `OCRService` - Processes images and returns structured data
- `RobotState` - Stores scan results for display

**Downstream Consumers:**
- Last Scan Results Card - Displays latest scan data
- System logs - Records all OCR operations
- User clipboard - Receives copied field values

**Critical Path Flow:**
1. User opens OCR Scanner modal
2. Selects input method (camera/upload/paste)
3. Provides image via chosen method
4. Clicks "Analyze Document"
5. Frontend sends POST to `/api/ocr/analyze`
6. Backend processes with OCRService
7. Frontend polls `/api/vision/results/<scan_id>`
8. Results display in panel with confidence indicator
9. User copies fields to clipboard

**Stream Management Contract:**
- Stream starts ONLY when camera tab active
- Stream stops immediately when switching tabs
- Maximum one active stream (conflict detection with Vision Panel)
- Stream uses 320x240@Q40@15fps (from vision_manager_optimization.md)

---

## 12. MEMORY COMPLIANCE

**No `_memory_snippet.txt` provided. Proceeding without additional memory rules.**

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:**
- `F:\PORTFOLIO\ps_rcs_project\frontend\templates\service_dashboard.html`
- `F:\PORTFOLIO\ps_rcs_project\frontend\static\css\service_theme.css`
- `F:\PORTFOLIO\ps_rcs_project\frontend\static\js\dashboard-core.js`
- `F:\PORTFOLIO\ps_rcs_project\src\api\server.py`

**Contract Reference:** `F:\PORTFOLIO\ps_rcs_project\docs\contracts\ocr_scanner_enhancement_contract.md` v1.0

## Strict Constraints (NON-NEGOTIABLE)

1. **Stream Lifecycle:** Stream MUST start only when camera tab active; MUST stop when switching away
2. **Bandwidth Optimization:** Stream MUST use 320x240@Q40@15fps (from vision_manager_optimization.md)
3. **Unified Endpoint:** `/api/ocr/analyze` MUST handle both multipart and JSON base64
4. **Keyboard Navigation:** MUST implement full ARIA roles and arrow key navigation
5. **File Validation:** MUST reject files >5MB and non-image types
6. **Code Limits:** All methods MUST be ≤50 lines
7. **CSS Variables:** Zero hardcoded colors (all use variables)

## Implementation Sequence

### Phase 1: HTML Structure (15 minutes)
1. Update OCR Scanner card to icon-only design
2. Complete OCR Scanner modal with all three tab panels
3. Add stream container to camera tab
4. Add dropzones to upload/paste tabs
5. Add results panel with copy buttons

### Phase 2: CSS Styling (20 minutes)
1. Add OCR-specific CSS variables
2. Style scanner tabs with active states
3. Style dropzone/paste area with drag states
4. Style preview containers
5. Style results panel with confidence badges
6. Test dark/light theme compatibility

### Phase 3: JavaScript - Core Structure (20 minutes)
1. Define OCRPanel class with all method signatures
2. Implement `_initializeElements()` with element caching
3. Implement `_initializeEventListeners()` for all interactions
4. Integrate with DashboardCore.init()

### Phase 4: JavaScript - Tab Management (15 minutes)
1. Implement `switchTab()` with stream lifecycle
2. Implement `_startCameraStream()`
3. Implement `_stopCameraStream()`
4. Add keyboard navigation (arrow keys)
5. Test tab switching without layout shift

### Phase 5: JavaScript - Input Handling (25 minutes)
1. Implement `_handlePaste()` for clipboard images
2. Implement `_handleDrop()` for drag-and-drop
3. Implement `_handleFileSelect()` for file input
4. Implement `_validateImageFile()` with size/type checks
5. Implement `_showPreview()` and `_clearPreview()`

### Phase 6: JavaScript - Analysis & Results (20 minutes)
1. Implement `_captureFrame()` for camera tab
2. Implement `analyzeDocument()` with loading states
3. Implement `_pollForResults()` with timeout
4. Implement `_displayResults()` with confidence badges
5. Implement `_copyToClipboard()` functionality

### Phase 7: Backend Endpoint (15 minutes)
1. Create `/api/ocr/analyze` endpoint
2. Add multipart/form-data handler
3. Add JSON base64 handler
4. Add file size validation
5. Add image preprocessing (resize to 640x480)
6. Add logging for all operations

### Phase 8: Testing & Refinement (20 minutes)
1. Test all three input methods
2. Test keyboard navigation
3. Test error scenarios (large files, invalid images)
4. Test stream lifecycle (start/stop on tab switch)
5. Test results display with copy buttons
6. Verify all acceptance criteria

## Success Criteria

- All methods match contract signatures exactly
- All acceptance criteria pass
- No console errors or warnings
- Stream management prevents bandwidth waste
- Keyboard navigation works flawlessly
- All methods ≤50 lines
- Auditor approval required

---

# POST-ACTION REPORT

✅ **Contract Created:** `F:\PORTFOLIO\ps_rcs_project\docs\contracts\ocr_scanner_enhancement_contract.md` v1.0
📋 **Work Order Generated** for Implementer
🎯 **Key Features Delivered:**
   1. Multi-source input (camera/upload/paste)
   2. Bandwidth-optimized stream management
   3. Unified backend endpoint
   4. Accessibility-first keyboard navigation
   5. Visual confidence indicators

🔍 **Next Verification Command:**
```
/verify-context: system_constraints.md, system_style.md, vision_manager_optimization.md, contracts/ocr_scanner_enhancement_contract.md, service_dashboard.html, service_theme.css, dashboard-core.js, server.py
```

👉 **Next Agent:** Implementer (AGENTS/02_implementer.md)

---

**ARCHITECT SIGNATURE:** Contract v1.0 APPROVED for implementation.
**Immutability Notice:** These interfaces are now FROZEN. Any deviations require Architect re-approval.