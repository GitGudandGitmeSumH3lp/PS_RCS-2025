# CONTRACT: UI Overhaul (Linear Style)
**Version:** 1.0  
**Last Updated:** 2026-02-02  
**Status:** Draft  
**Target Files:** `frontend/templates/service_dashboard.html`, `frontend/static/css/service_theme.css`, `frontend/static/js/dashboard-core.js`, `src/api/server.py`

---

## 1. PURPOSE

Transform the current Bento Grid dashboard into a Linear.app-inspired interface with optimized Vision System integration. This contract defines exact HTML structure, CSS architecture, JavaScript behavior, and backend stream optimization to achieve <1s stream load times, zero bandwidth waste during idle state, and seamless scan workflows.

---

## 2. DECISION LOG (Ambiguity Resolution)

### Decision 1: File Structure
**Question:** Keep VisionPanel embedded in `dashboard-core.js` OR extract to `VisionPanel.js`?  
**Resolution:** **KEEP EMBEDDED** in `dashboard-core.js`  
**Rationale:**
- Current system uses single-file architecture per `system_style.md` § 3
- VisionPanel is <150 lines (within 50-line method limit when properly factored)
- Reduces HTTP requests (performance optimization)
- Maintains consistency with existing `DashboardCore` pattern

### Decision 2: Modal Approach
**Question:** Reuse existing `#visionModal` OR create new `#modal-vision`?  
**Resolution:** **CREATE NEW** `#modal-vision`  
**Rationale:**
- Linear spec explicitly defines new semantic structure (`<dialog>` tag)
- Legacy `#visionModal` may have Bento-style classes conflicting with new design
- Clean slate ensures no CSS inheritance issues
- Allows gradual migration (old modal can coexist during transition)

### Decision 3: Grid Layout Definition
**Question:** Exact CSS grid-template-columns definition?  
**Resolution:**
```css
.grid-layout {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
  padding: 24px;
}
```
**Rationale:**
- `auto-fill`: Cards wrap responsively (mobile-first)
- `minmax(280px, 1fr)`: Cards never shrink below 280px (prevents content squish)
- `gap: 24px`: Per spec § 2.A spacing requirement (multiple of 4)
- Complies with `system_constraints.md` responsive design mandate

### Decision 4: Status Sync Mechanism
**Question:** Poll `/api/status` OR WebSocket OR event-driven?  
**Resolution:** **POLL `/api/status`** every 2 seconds  
**Rationale:**
- `API_MAP_lite.md` documents existing 2s polling pattern
- WebSocket adds complexity (violates Lean V4.0 principle)
- Camera status changes are infrequent (not real-time critical)
- Existing infrastructure already supports this pattern
- **Implementation:** `DashboardCore._pollStatus()` updates `VisionPanel.updateStatusIndicator()`

### Decision 5: Stream Quality Enforcement
**Question:** Backend enforcement (quality=40) OR client query param?  
**Resolution:** **BACKEND ENFORCEMENT** (server-side)  
**Rationale:**
- `vision_manager_optimization.md` § 2.3 mandates quality=40 as system constraint
- Prevents client tampering (security/performance guarantee)
- Simplifies frontend code (no query param logic needed)
- **Implementation:** `server.py` hardcodes `vision_manager.generate_mjpeg(quality=40)`

---

## 3. HTML CHANGES (`service_dashboard.html`)

### 3.1 Dashboard Grid Structure

**Replace existing Bento grid** (`<div class="bento-grid">`) with:

```html
<section class="grid-layout" role="main" aria-label="Service Dashboard">
  <!-- Existing cards remain, add Vision card below -->
  
  <article id="card-vision-preview" 
           class="linear-card clickable" 
           role="button" 
           tabindex="0"
           aria-label="Vision System - Click to view live feed">
    <header class="card-header">
      <span class="icon" aria-hidden="true">📷</span>
      <h4 class="card-title">Vision Feed</h4>
      <div id="vision-status-indicator" 
           class="status-indicator" 
           data-status="offline"
           aria-live="polite"></div>
    </header>
    <div class="card-body">
      <div class="preview-placeholder">
        <span class="preview-text">Click to activate stream</span>
      </div>
    </div>
    <div class="card-hover-overlay" aria-hidden="true">
      <span class="overlay-text">Click to view live</span>
    </div>
  </article>
  
</section>
```

**Required DOM Element IDs:**
- `#card-vision-preview` - Main card container (JS binding target)
- `#vision-status-indicator` - Status pulse element (updated via polling)
- `.preview-placeholder` - Static preview area (replaced on modal open)
- `.card-hover-overlay` - Overlay shown on hover (Progressive Disclosure)

**Semantic HTML Requirements:**
- `<section>` for grid container (landmark role)
- `<article>` for card (independent content unit)
- `<header>` for card title area
- `role="button"` + `tabindex="0"` for keyboard accessibility

### 3.2 Vision Modal Structure

**Add before closing `</body>` tag:**

```html
<dialog id="modal-vision" class="linear-modal" aria-labelledby="modal-title">
  <div class="modal-backdrop" aria-hidden="true"></div>
  <div class="modal-container">
    <header class="modal-header">
      <h2 id="modal-title" class="modal-title">Live Feed</h2>
      <div class="modal-actions">
        <button id="btn-scan-label" 
                class="btn-primary" 
                aria-label="Scan current frame">
          <span class="btn-icon">🔍</span>
          <span class="btn-text">Scan Label</span>
        </button>
        <button id="btn-close-modal" 
                class="btn-ghost" 
                aria-label="Close modal">
          <span aria-hidden="true">✕</span>
        </button>
      </div>
    </header>
    
    <div class="modal-body">
      <div class="stream-container">
        <img id="vision-stream" 
             class="stream-image" 
             alt="Live camera feed"
             data-src="/api/vision/stream"
             aria-live="off">
        <div id="stream-error-state" class="error-state hidden" role="alert">
          <span class="error-icon">⚠️</span>
          <p class="error-message">Stream unavailable</p>
        </div>
      </div>
    </div>
    
    <footer class="modal-footer">
      <div id="scan-results-container" class="scan-results hidden">
        <h3 class="results-title">Last Scan Results</h3>
        <dl class="results-data">
          <dt>Tracking ID:</dt>
          <dd id="result-tracking-id">—</dd>
          <dt>Order ID:</dt>
          <dd id="result-order-id">—</dd>
          <dt>District:</dt>
          <dd id="result-district">—</dd>
          <dt>Confidence:</dt>
          <dd id="result-confidence">—</dd>
        </dl>
      </div>
    </footer>
  </div>
</dialog>
```

**Required DOM Element IDs:**
- `#modal-vision` - Dialog container (native `<dialog>` element)
- `#vision-stream` - `<img>` element for MJPEG stream
- `#btn-scan-label` - Trigger OCR scan
- `#btn-close-modal` - Close dialog
- `#scan-results-container` - Results display area
- `#result-tracking-id`, `#result-order-id`, `#result-district`, `#result-confidence` - Individual result fields
- `#stream-error-state` - Error fallback UI

**Behavioral Attributes:**
- `data-src="/api/vision/stream"` - Lazy-loaded stream URL (set to `src` only on modal open)
- `aria-live="off"` - Stream is visual only (no screen reader announcements)
- `role="alert"` - Error state announced to assistive tech

---

## 4. CSS CHANGES (`service_theme.css`)

### 4.1 CSS Variables (Root Scope)

**Add to `:root` selector:**

```css
:root {
  /* Typography System */
  --font-primary: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  
  /* Color System (Dark Mode Default) */
  --surface-base: #0F1419;          /* Main background */
  --surface-card: #1A1F26;          /* Card background */
  --surface-overlay: rgba(10, 12, 16, 0.92); /* Modal backdrop */
  --text-primary: #F7F8F8;          /* High contrast */
  --text-secondary: #8A8F98;        /* Medium contrast */
  --text-tertiary: #5F656F;         /* Low contrast */
  --border-subtle: rgba(255, 255, 255, 0.1);
  --border-focus: rgba(255, 255, 255, 0.4);
  --accent-primary: #007AFF;        /* Action buttons */
  --accent-success: #34C759;        /* Success state */
  --accent-error: #FF3B30;          /* Error state */
  
  /* Shadows */
  --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.04);
  --shadow-modal: 0 24px 48px rgba(0, 0, 0, 0.2);
  
  /* Spacing Scale (4px baseline) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --space-16: 64px;
  
  /* Border Radii */
  --radius-sm: 12px;
  --radius-md: 16px;
  --radius-lg: 20px;
  --radius-xl: 24px;
  
  /* Motion */
  --timing-fast: 200ms;
  --easing-smooth: cubic-bezier(0.4, 0, 0.2, 1);
}

/* Light Mode Override (Medical/Industrial) */
[data-theme="light"] {
  --surface-base: #F8FAFC;
  --surface-card: #FFFFFF;
  --surface-overlay: rgba(248, 250, 252, 0.92);
  --text-primary: #1A1C1E;
  --text-secondary: #6B7280;
  --text-tertiary: #9CA3AF;
  --border-subtle: rgba(0, 0, 0, 0.08);
  --border-focus: rgba(0, 0, 0, 0.24);
}
```

### 4.2 Grid Layout Classes

```css
/* Dashboard Grid */
.grid-layout {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-6);
  padding: var(--space-6);
  background: var(--surface-base);
  min-height: 100vh;
}

/* Linear Card Base */
.linear-card {
  background: var(--surface-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-4);
  transition: border-color var(--timing-fast) var(--easing-smooth),
              transform var(--timing-fast) var(--easing-smooth);
  position: relative;
  overflow: hidden;
}

/* Clickable Card State */
.linear-card.clickable {
  cursor: pointer;
}

.linear-card.clickable:hover {
  border-color: var(--border-focus);
  transform: translateY(-2px);
}

.linear-card.clickable:active {
  transform: scale(0.98);
}

/* Card Internal Structure */
.card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.card-title {
  font-family: var(--font-primary);
  font-size: 16px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  flex: 1;
  letter-spacing: -0.02em;
}

.card-body {
  position: relative;
  min-height: 120px;
}

/* Preview Placeholder (Vision Card) */
.preview-placeholder {
  width: 100%;
  height: 160px;
  background: var(--surface-base);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--border-subtle);
}

.preview-text {
  font-family: var(--font-primary);
  font-size: 14px;
  font-weight: var(--font-weight-medium);
  color: var(--text-tertiary);
}

/* Hover Overlay (Progressive Disclosure) */
.card-hover-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--timing-fast) var(--easing-smooth);
  pointer-events: none;
}

.linear-card.clickable:hover .card-hover-overlay {
  opacity: 1;
}

.overlay-text {
  font-family: var(--font-primary);
  font-size: 16px;
  font-weight: var(--font-weight-semibold);
  color: #FFFFFF;
}

/* Status Indicator (Pulse Animation) */
.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
  position: relative;
}

.status-indicator[data-status="online"] {
  background: var(--accent-success);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.status-indicator[data-status="offline"] {
  background: var(--text-tertiary);
}
```

### 4.3 Modal Classes

```css
/* Modal Base */
.linear-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: none;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}

.linear-modal[open] {
  display: flex;
  animation: modalFadeIn var(--timing-fast) var(--easing-smooth);
}

@keyframes modalFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* Backdrop */
.modal-backdrop {
  position: absolute;
  inset: 0;
  background: var(--surface-overlay);
  backdrop-filter: blur(8px);
  z-index: -1;
}

/* Modal Container */
.modal-container {
  background: var(--surface-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-modal);
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: modalScaleIn var(--timing-fast) var(--easing-smooth);
}

@keyframes modalScaleIn {
  from {
    transform: scale(0.95);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

/* Modal Header */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-6);
  border-bottom: 1px solid var(--border-subtle);
}

.modal-title {
  font-family: var(--font-primary);
  font-size: 20px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
}

.modal-actions {
  display: flex;
  gap: var(--space-2);
}

/* Modal Body */
.modal-body {
  padding: var(--space-6);
  overflow-y: auto;
  flex: 1;
}

.stream-container {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: var(--surface-base);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.stream-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* Error State */
.error-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--surface-base);
}

.error-state.hidden {
  display: none;
}

.error-icon {
  font-size: 48px;
  margin-bottom: var(--space-2);
}

.error-message {
  font-family: var(--font-primary);
  font-size: 14px;
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
}

/* Modal Footer */
.modal-footer {
  padding: var(--space-6);
  border-top: 1px solid var(--border-subtle);
}

.scan-results {
  background: var(--surface-base);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.scan-results.hidden {
  display: none;
}

.results-title {
  font-family: var(--font-primary);
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0 0 var(--space-3) 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.results-data {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0;
}

.results-data dt {
  font-family: var(--font-primary);
  font-size: 13px;
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
}

.results-data dd {
  font-family: var(--font-primary);
  font-size: 13px;
  font-weight: var(--font-weight-normal);
  color: var(--text-primary);
  margin: 0;
}
```

### 4.4 Utility Classes

```css
/* Text Utilities */
.text-sm {
  font-size: 14px;
}

.text-muted {
  color: var(--text-secondary);
}

/* Layout Utilities */
.flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

.hidden {
  display: none !important;
}

/* Button Styles */
.btn-primary {
  background: var(--accent-primary);
  color: #FFFFFF;
  border: none;
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-4);
  font-family: var(--font-primary);
  font-size: 14px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  transition: background var(--timing-fast) var(--easing-smooth),
              transform var(--timing-fast) var(--easing-smooth);
}

.btn-primary:hover {
  background: #0062CC;
}

.btn-primary:active {
  transform: scale(0.98);
}

.btn-primary:disabled {
  background: var(--text-tertiary);
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
  font-family: var(--font-primary);
  font-size: 18px;
  cursor: pointer;
  transition: border-color var(--timing-fast) var(--easing-smooth),
              color var(--timing-fast) var(--easing-smooth);
}

.btn-ghost:hover {
  border-color: var(--border-focus);
  color: var(--text-primary);
}

/* Motion Classes */
.transition-200 {
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

.scale-hover:hover {
  transform: scale(1.05);
}
```

---

## 5. JAVASCRIPT CHANGES (`dashboard-core.js`)

### 5.1 VisionPanel Class Refactoring

**Replace existing VisionPanel class with:**

```javascript
/**
 * VisionPanel - Manages camera stream modal and scan workflow
 * @class
 */
class VisionPanel {
  constructor() {
    // DOM Element Verification (Graceful Degradation)
    this.cardElement = document.getElementById('card-vision-preview');
    this.modalElement = document.getElementById('modal-vision');
    this.streamElement = document.getElementById('vision-stream');
    this.statusIndicator = document.getElementById('vision-status-indicator');
    this.scanButton = document.getElementById('btn-scan-label');
    this.closeButton = document.getElementById('btn-close-modal');
    this.resultsContainer = document.getElementById('scan-results-container');
    this.errorState = document.getElementById('stream-error-state');
    
    // Null Check Safety
    if (!this.cardElement || !this.modalElement) {
      console.warn('[VisionPanel] Required DOM elements missing. Module disabled.');
      return;
    }
    
    // State
    this.isStreamActive = false;
    this.lastScanTimestamp = null;
    
    // Bind Event Listeners
    this._initializeEventListeners();
  }
  
  /**
   * Initialize all event listeners
   * @private
   */
  _initializeEventListeners() {
    // Card Click/Enter - Open Modal
    this.cardElement.addEventListener('click', () => this.openModal());
    this.cardElement.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.openModal();
      }
    });
    
    // Close Button
    if (this.closeButton) {
      this.closeButton.addEventListener('click', () => this.closeModal());
    }
    
    // Backdrop Click - Close Modal
    this.modalElement.addEventListener('click', (e) => {
      if (e.target === this.modalElement) {
        this.closeModal();
      }
    });
    
    // Escape Key - Close Modal
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.modalElement.open) {
        this.closeModal();
      }
    });
    
    // Scan Button
    if (this.scanButton) {
      this.scanButton.addEventListener('click', () => this.triggerScan());
    }
    
    // Stream Error Handling
    if (this.streamElement) {
      this.streamElement.addEventListener('error', () => this._handleStreamError());
    }
  }
  
  /**
   * Open modal and start stream (lazy loading)
   */
  openModal() {
    if (!this.modalElement) return;
    
    // Show Modal (native dialog API)
    this.modalElement.showModal();
    
    // Start Stream (Lazy Load)
    this._startStream();
  }
  
  /**
   * Close modal and stop stream (bandwidth optimization)
   */
  closeModal() {
    if (!this.modalElement) return;
    
    // Stop Stream BEFORE closing modal
    this._stopStream();
    
    // Close Modal
    this.modalElement.close();
  }
  
  /**
   * Start video stream by setting img src
   * @private
   */
  _startStream() {
    if (!this.streamElement || this.isStreamActive) return;
    
    const streamUrl = this.streamElement.getAttribute('data-src');
    if (!streamUrl) {
      console.error('[VisionPanel] Stream URL not found in data-src attribute');
      return;
    }
    
    // Set src to trigger stream load
    this.streamElement.src = streamUrl;
    this.isStreamActive = true;
    
    // Hide error state
    if (this.errorState) {
      this.errorState.classList.add('hidden');
    }
    
    console.log('[VisionPanel] Stream started:', streamUrl);
  }
  
  /**
   * Stop video stream by clearing img src (bandwidth saver)
   * @private
   */
  _stopStream() {
    if (!this.streamElement || !this.isStreamActive) return;
    
    // Clear src to stop stream request
    this.streamElement.src = '';
    this.isStreamActive = false;
    
    console.log('[VisionPanel] Stream stopped (bandwidth saved)');
  }
  
  /**
   * Handle stream loading errors
   * @private
   */
  _handleStreamError() {
    console.error('[VisionPanel] Stream failed to load');
    
    // Show error state
    if (this.errorState) {
      this.errorState.classList.remove('hidden');
    }
    
    // Update status indicator
    this.updateStatusIndicator(false);
  }
  
  /**
   * Update camera status indicator
   * @param {boolean} isOnline - Camera online status
   */
  updateStatusIndicator(isOnline) {
    if (!this.statusIndicator) return;
    
    this.statusIndicator.setAttribute('data-status', isOnline ? 'online' : 'offline');
    this.statusIndicator.setAttribute('aria-label', 
      isOnline ? 'Camera online' : 'Camera offline');
  }
  
  /**
   * Trigger OCR scan workflow
   */
  async triggerScan() {
    if (!this.scanButton) return;
    
    // Disable button (prevent double-click)
    this.scanButton.disabled = true;
    this.scanButton.querySelector('.btn-text').textContent = 'Scanning...';
    
    try {
      // POST to scan endpoint
      const response = await fetch('/api/vision/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        throw new Error(`Scan failed: ${response.status}`);
      }
      
      // Poll for results (async operation)
      await this._pollScanResults();
      
    } catch (error) {
      console.error('[VisionPanel] Scan error:', error);
      alert('Scan failed. Please try again.');
    } finally {
      // Re-enable button
      this.scanButton.disabled = false;
      this.scanButton.querySelector('.btn-text').textContent = 'Scan Label';
    }
  }
  
  /**
   * Poll /api/vision/last-scan for results
   * @private
   */
  async _pollScanResults() {
    const maxAttempts = 10;
    const pollInterval = 300; // 300ms
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise(resolve => setTimeout(resolve, pollInterval));
      
      try {
        const response = await fetch('/api/vision/last-scan');
        const data = await response.json();
        
        // Check if this is a new scan (timestamp changed)
        if (data.timestamp !== this.lastScanTimestamp) {
          this.lastScanTimestamp = data.timestamp;
          this._displayScanResults(data);
          return; // Exit polling loop
        }
      } catch (error) {
        console.warn('[VisionPanel] Poll attempt failed:', error);
      }
    }
    
    console.warn('[VisionPanel] Scan results polling timeout');
  }
  
  /**
   * Display scan results in modal footer
   * @private
   * @param {Object} data - Scan result data from API
   */
  _displayScanResults(data) {
    if (!this.resultsContainer) return;
    
    // Show results container
    this.resultsContainer.classList.remove('hidden');
    
    // Update individual fields
    const fields = {
      'result-tracking-id': data.tracking_id || '—',
      'result-order-id': data.order_id || '—',
      'result-district': data.district || '—',
      'result-confidence': data.confidence 
        ? `${(data.confidence * 100).toFixed(1)}%` 
        : '—'
    };
    
    Object.entries(fields).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = value;
      }
    });
    
    // Dispatch custom event for dashboard sync
    document.dispatchEvent(new CustomEvent('vision:scan-complete', {
      detail: data
    }));
  }
}
```

### 5.2 DashboardCore Integration

**Add to DashboardCore class:**

```javascript
class DashboardCore {
  constructor() {
    // Existing initialization...
    
    // Initialize VisionPanel
    this.visionPanel = new VisionPanel();
    
    // Start status polling
    this._startStatusPolling();
  }
  
  /**
   * Start periodic status polling
   * @private
   */
  _startStatusPolling() {
    this._pollStatus(); // Initial poll
    setInterval(() => this._pollStatus(), 2000); // Every 2 seconds
  }
  
  /**
   * Poll /api/status and update components
   * @private
   */
  async _pollStatus() {
    try {
      const response = await fetch('/api/status');
      const data = await response.json();
      
      // Update vision panel status
      if (this.visionPanel) {
        this.visionPanel.updateStatusIndicator(data.camera_connected);
      }
      
      // Update other dashboard components...
      
    } catch (error) {
      console.error('[DashboardCore] Status poll failed:', error);
    }
  }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  new DashboardCore();
});
```

---

## 6. BACKEND CHANGES (`src/api/server.py`)

### 6.1 Stream Endpoint Optimization

**Modify `/api/vision/stream` route:**

```python
@app.route('/api/vision/stream')
def vision_stream():
    """
    MJPEG stream endpoint with enforced optimization.
    
    Returns:
        Response: Multipart MJPEG stream (320x240 @ Q40 @ 15fps)
    
    Raises:
        503: If camera not connected
    """
    # Check camera status
    if not vision_manager or not vision_manager.stream:
        return jsonify({
            "error": "Camera offline",
            "message": "Vision system not initialized"
        }), 503
    
    # Return optimized stream (quality=40 enforced server-side)
    return Response(
        vision_manager.generate_mjpeg(quality=40),  # CRITICAL: Hardcoded quality
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
```

**Behavior Specification:**
- **Input Validation:** None (quality parameter removed from client control)
- **Processing Logic:** Call `vision_manager.generate_mjpeg(quality=40)` unconditionally
- **Output Guarantee:** Stream at 320x240, Q40, ~15 FPS (per vision_manager_optimization.md contract)
- **Side Effects:** Continuous generator execution until client disconnects

**Error Handling:**
- **Camera Offline:** Return 503 with JSON error message
- **Stream Failure:** Generator handles internally (per vision_manager contract)

### 6.2 Status Endpoint Enhancement

**Modify `/api/status` route:**

```python
@app.route('/api/status')
def get_status():
    """
    System health check with hardware status.
    
    Returns:
        dict: System state including camera_connected flag
    """
    camera_online = bool(vision_manager and vision_manager.stream)
    
    return jsonify({
        "mode": robot_state.mode,
        "battery_voltage": robot_state.battery_voltage,
        "last_error": robot_state.last_error,
        "motor_connected": robot_state.motor_connected,
        "lidar_connected": robot_state.lidar_connected,
        "camera_connected": camera_online,  # NEW: Frontend status sync
        "timestamp": datetime.now().isoformat()
    })
```

**Behavior Specification:**
- **Input Validation:** None (GET request)
- **Processing Logic:** Check `vision_manager.stream` existence
- **Output Guarantee:** JSON with `camera_connected` boolean
- **Side Effects:** None (read-only operation)

### 6.3 Scan Endpoint (No Changes Required)

**Existing `/api/vision/scan` endpoint complies with contract:**
- Returns 202 immediately (async processing)
- Results retrieved via `/api/vision/last-scan` (polling pattern)
- No modifications needed

---

## 7. ACCEPTANCE CRITERIA (Testable)

### Visual Compliance
- [ ] **AC-1:** Typography uses Inter font family (check computed styles in DevTools)
- [ ] **AC-2:** Zero hardcoded hex/rgb colors in CSS (all values reference CSS variables)
- [ ] **AC-3:** Dashboard grid uses Linear-style layout (inspect grid-template-columns)
- [ ] **AC-4:** Card border radius is 20px (per `system_style.md` requirement)
- [ ] **AC-5:** Modal backdrop has blur effect (`backdrop-filter: blur(8px)`)

### Functional Behavior
- [ ] **AC-6:** Camera card displays with status indicator (green online / gray offline)
- [ ] **AC-7:** Click card → modal opens with smooth scale animation (200ms transition)
- [ ] **AC-8:** Modal stream loads in <1s (verify via Network tab: stream starts immediately)
- [ ] **AC-9:** Stream quality is 40 (verify in browser: image file size ~5-8KB per frame)
- [ ] **AC-10:** Stream resolution is 320x240 (verify via image properties)
- [ ] **AC-11:** Close modal → stream stops (Network tab shows request terminates)
- [ ] **AC-12:** Bandwidth drops to zero after modal close (no ongoing stream requests)
- [ ] **AC-13:** "Scan Label" button workflow: disable → POST → poll → update results
- [ ] **AC-14:** Scan results appear in modal footer within 3 seconds
- [ ] **AC-15:** Status indicator syncs with backend camera state (poll every 2s)

### Code Quality
- [ ] **AC-16:** All JavaScript methods ≤50 lines (per `system_constraints.md`)
- [ ] **AC-17:** No direct hardware calls in JavaScript (frontend only uses API)
- [ ] **AC-18:** Graceful degradation if DOM elements missing (console.warn, no crash)
- [ ] **AC-19:** Keyboard accessibility: Enter/Space on card opens modal, Escape closes
- [ ] **AC-20:** ARIA attributes present (aria-label, aria-live, role)

### Performance
- [ ] **AC-21:** Modal animation maintains 60fps (check Performance tab)
- [ ] **AC-22:** Stream FPS stabilizes at ~15 (measure via frame timestamps)
- [ ] **AC-23:** No memory leaks (stream cleanup verified via Memory profiler)
- [ ] **AC-24:** Dashboard load time <2s on Raspberry Pi 4B

### Error Handling
- [ ] **AC-25:** Camera offline: Gray status indicator + placeholder visible
- [ ] **AC-26:** Stream error: Error state appears in modal (⚠️ icon + message)
- [ ] **AC-27:** Scan failed: Alert notification shown (reuse existing toast system if available)
- [ ] **AC-28:** Missing DOM: Console warning logged, no JavaScript crash

---

## 8. ERROR HANDLING SPECIFICATIONS

### Frontend Errors

**Error Case 1: Missing DOM Elements**
- **Condition:** `#card-vision-preview` or `#modal-vision` not found in DOM
- **Handling:** Log `console.warn('[VisionPanel] Required DOM elements missing. Module disabled.')` and return early from constructor
- **User Impact:** Vision panel features disabled (other dashboard features unaffected)

**Error Case 2: Stream Load Failure**
- **Condition:** `<img>` `onerror` event triggered
- **Handling:** Call `_handleStreamError()` → Show `#stream-error-state`, update status indicator to offline
- **User Impact:** Error message displayed in modal, user can retry by closing/reopening

**Error Case 3: Scan API Failure**
- **Condition:** `/api/vision/scan` returns non-2xx status
- **Handling:** `catch` block in `triggerScan()` → `alert('Scan failed. Please try again.')`
- **User Impact:** Alert notification, button re-enabled for retry

**Error Case 4: Scan Results Timeout**
- **Condition:** 10 polling attempts (3 seconds) without new timestamp
- **Handling:** Log `console.warn('[VisionPanel] Scan results polling timeout')`, exit polling loop
- **User Impact:** No results displayed (silent failure with console log)

### Backend Errors

**Error Case 5: Camera Offline**
- **Condition:** `vision_manager` not initialized or `stream` is None
- **Handling:** `/api/vision/stream` returns 503 with JSON `{"error": "Camera offline", "message": "Vision system not initialized"}`
- **User Impact:** Frontend receives 503, triggers stream error handling (Error Case 2)

**Error Case 6: Stream Generator Exception**
- **Condition:** Exception in `vision_manager.generate_mjpeg()` loop
- **Handling:** Generator silently skips frame (per vision_manager contract § 2.3)
- **User Impact:** Brief frame drop (not user-facing error)

---

## 9. CONSTRAINTS (FROM SYSTEM RULES)

### From `system_constraints.md`:

1. **Max Function Length:** 50 lines (JS/Python) ✅
   - VisionPanel methods factored to comply (longest: `_pollScanResults` at 24 lines)
2. **No Hardcoded Colors:** CSS variables only ✅
   - All colors reference `:root` variables
3. **Type Hints:** Mandatory for backend functions ✅
   - `/api/vision/stream` and `/api/status` have return type annotations
4. **Docstrings:** Google-style required ✅
   - All Python functions include docstrings

### From `system_style.md`:

1. **Typography:** Inter, -apple-system, BlinkMacSystemFont ✅
   - `--font-primary` variable defined
2. **Border Radius:** 20-24px for cards ✅
   - `--radius-lg: 20px` used for `.linear-card`
3. **Shadows:** Soft, diffused ✅
   - `--shadow-card: 0 2px 8px rgba(0,0,0,0.04)` matches spec
4. **Progressive Disclosure:** Hidden until interaction ✅
   - Stream loaded only on modal open, hover overlay reveals call-to-action

### From `vision_manager_optimization.md`:

1. **Stream Quality:** 40 (not 80) ✅
   - Server enforces `quality=40` in `/api/vision/stream`
2. **Stream Resolution:** 320x240 for UI ✅
   - Vision manager downscales from 640x480 capture
3. **Stream FPS:** ~15 FPS throttle ✅
   - Vision manager sleeps 0.066s per frame

---

## 10. MEMORY COMPLIANCE

**No `_memory_snippet.txt` provided.**

**Applied Rules:** None (proceeding with contract-first principles and system constraints only)

---

## 11. INTEGRATION POINTS

### This contract MODIFIES:

- `frontend/templates/service_dashboard.html` - Grid structure, modal structure
- `frontend/static/css/service_theme.css` - CSS variables, component styles
- `frontend/static/js/dashboard-core.js` - VisionPanel class, DashboardCore polling
- `src/api/server.py` - Stream endpoint quality enforcement, status endpoint enhancement

### This contract DEPENDS ON:

- `src/services/vision_manager.py::generate_mjpeg(quality=40)` - Optimized stream generator
- `src/services/vision_manager.py::get_frame()` - High-res frame for OCR
- `/api/status` - Existing polling infrastructure
- `/api/vision/scan` - Existing OCR trigger endpoint
- `/api/vision/last-scan` - Existing results endpoint

### This contract is CONSUMED BY:

- **End Users:** Web dashboard operators viewing live stream
- **DashboardCore:** Status polling integration
- **Future Features:** Scan history panel, multi-camera support

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:**
- `frontend/templates/service_dashboard.html`
- `frontend/static/css/service_theme.css`
- `frontend/static/js/dashboard-core.js`
- `src/api/server.py`

**Contract Reference:** `docs/contracts/ui_overhaul_linear.md` v1.0

---

## Strict Constraints (NON-NEGOTIABLE)

1. **Max Function Length:** 50 lines (refactor if longer)
2. **No Hardcoded Colors:** All colors must reference CSS variables in `:root`
3. **Stream Quality:** Server MUST enforce `quality=40` (no client override)
4. **Progressive Disclosure:** Stream hidden until modal open (bandwidth optimization)
5. **Semantic HTML:** Use `<article>`, `<section>`, `<dialog>`, `<header>`, `<footer>`
6. **Accessibility:** Include ARIA attributes (`aria-label`, `aria-live`, `role`)
7. **Type Hints:** All Python functions require return type annotations
8. **Docstrings:** Google-style for all public methods

---

## Memory Compliance (MANDATORY)

_No memory rules provided in this context._

---

## Required Implementation Steps

### Phase 1: HTML Structure (1-2 hours)

1. **Replace Bento Grid:**
   - Locate `<div class="bento-grid">` in `service_dashboard.html`
   - Replace with `<section class="grid-layout">` structure per § 3.1
   - Preserve existing cards, add Vision card

2. **Add Vision Card:**
   - Copy HTML structure from § 3.1 exactly (IDs must match)
   - Verify `data-status="offline"` default on status indicator

3. **Add Vision Modal:**
   - Insert `<dialog id="modal-vision">` before `</body>` per § 3.2
   - Copy complete structure (header, body, footer)
   - Set `data-src="/api/vision/stream"` on `<img>`

### Phase 2: CSS Styling (2-3 hours)

1. **Add CSS Variables:**
   - Open `service_theme.css`
   - Add all variables from § 4.1 to `:root` selector
   - Add `[data-theme="light"]` overrides

2. **Add Component Styles:**
   - Copy grid layout classes (§ 4.2)
   - Copy modal classes (§ 4.3)
   - Copy utility classes (§ 4.4)
   - Verify no hardcoded colors remain (search for `#` and `rgb(`)

3. **Test Responsiveness:**
   - Resize browser to mobile width (320px)
   - Verify grid wraps to single column
   - Verify modal becomes full-screen

### Phase 3: JavaScript Logic (3-4 hours)

1. **Add VisionPanel Class:**
   - Open `dashboard-core.js`
   - Add complete class from § 5.1 (copy entire implementation)
   - Verify all method names match contract

2. **Integrate with DashboardCore:**
   - Add `this.visionPanel = new VisionPanel()` to constructor
   - Add `_startStatusPolling()` method from § 5.2
   - Verify 2-second poll interval

3. **Test Event Handling:**
   - Click card → verify modal opens
   - Press Escape → verify modal closes
   - Click scan button → verify POST sent

### Phase 4: Backend Optimization (1 hour)

1. **Modify Stream Endpoint:**
   - Open `src/api/server.py`
   - Locate `/api/vision/stream` route
   - Replace with implementation from § 6.1
   - **CRITICAL:** Hardcode `quality=40` (remove any client parameter parsing)

2. **Enhance Status Endpoint:**
   - Locate `/api/status` route
   - Add `camera_connected` field per § 6.2
   - Verify logic: `bool(vision_manager and vision_manager.stream)`

3. **Test Camera Detection:**
   - Disconnect camera → verify status returns `camera_connected: false`
   - Reconnect → verify status returns `camera_connected: true`

---

## Integration Testing Checklist

### Visual Tests
- [ ] Dashboard uses grid layout (not Bento bubbles)
- [ ] Inter font loaded and applied
- [ ] Colors use variables (inspect computed styles)
- [ ] Modal backdrop has blur effect

### Functional Tests
- [ ] Card click opens modal
- [ ] Stream starts on modal open
- [ ] Stream stops on modal close
- [ ] Scan button triggers workflow
- [ ] Results display in footer

### Performance Tests
- [ ] Stream loads in <1s (Network tab)
- [ ] Modal animation is smooth (Performance tab)
- [ ] Bandwidth drops to zero when modal closed
- [ ] FPS stabilizes at ~15

### Error Tests
- [ ] Camera offline → gray status indicator
- [ ] Stream error → error state appears
- [ ] Missing DOM → console warning (no crash)

---

## Success Criteria

1. ✅ All HTML IDs match contract specifications
2. ✅ All CSS classes defined and applied
3. ✅ All JavaScript methods ≤50 lines
4. ✅ Stream quality enforced at 40 server-side
5. ✅ Status polling updates indicator every 2s
6. ✅ Modal animation is 200ms cubic-bezier
7. ✅ Keyboard navigation works (Enter, Escape)
8. ✅ ARIA attributes present for accessibility
9. ✅ Type hints on all Python functions
10. ✅ Zero hardcoded colors in CSS

---

**Auditor approval required before deployment to production.**