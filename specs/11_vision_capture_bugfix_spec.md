```markdown
# FEATURE SPEC: Vision Capture UI Bug Fixes
**Date:** 2025-01-24
**Status:** High Priority
**Target File:** `docs/specs/vision_capture_bugfix_spec.md`

## 1. ISSUE DIAGNOSIS

| Symptom | Root Cause | Technical Fix |
| :--- | :--- | :--- |
| **Camera Card Clutter** | `.preview-text` "Camera preview" exists in DOM, violating icon-only design. | **HTML:** Remove text node. **CSS:** Center the placeholder icon. |
| **Capture Preview 404** | `server.py` may be resolving `data/captures` relative to the wrong root, or `VisionPanel` constructs invalid URLs. | **Python:** Use `os.getcwd()` for absolute paths. **JS:** Verify URL construction. |
| **Download Broken** | `<a>` tag lacks `download` attribute filename, causing browser to open link instead of saving. | **JS:** Set `download` attribute dynamically when updating `href`. |
| **Stream Stuck Error** | `_startStream()` sets the image source but fails to hide the `.error-state` overlay if it was previously triggered. | **JS:** Explicitly add `.hidden` to error overlay in `_startStream()`. |
| **Button Overflow** | `.btn-ghost` has fixed `width: 32px` in CSS, truncating "↓ Download". | **CSS:** Change `width` to `auto` and add horizontal padding. |

## 2. FILE-SPECIFIC FIXES

### A. Backend Logic (`src/api/server.py`)
**Problem:** Path resolution for static files relies on relative paths that may differ based on execution context.
**Fix:** Enforce absolute paths for the data directory.

```python
# In __init__
self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
self.captures_dir = os.path.join(self.root_dir, "data", "captures")

# Update capture_photo endpoint
@app.route("/api/vision/capture", methods=['POST'])
def capture_photo() -> Response:
    # ...
    # Ensure directory exists using absolute path
    os.makedirs(self.captures_dir, exist_ok=True)
    filepath = os.path.join(self.captures_dir, filename)
    # ...

# Update serve_capture endpoint
@app.route('/captures/<filename>')
def serve_capture(filename: str) -> Any:
    """Serve captured image files."""
    return send_from_directory(self.captures_dir, filename)
```

### B. Dashboard Structure (`frontend/templates/service_dashboard.html`)
**Problem:** Text clutter in Vision Card.
**Fix:** Remove text, use Icon.

```html
<!-- OLD -->
<div class="preview-placeholder">
  <div class="preview-text">Camera preview</div>
</div>

<!-- NEW -->
<div class="preview-placeholder">
  <svg class="text-muted" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
    <path d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
</div>
```

### C. Styling (`frontend/static/css/service_theme.css`)
**Problem:** Button width constraint.
**Fix:** Allow auto width for buttons containing text.

```css
/* Update .btn-ghost */
.btn-ghost {
  /* ... existing styles ... */
  /* Remove fixed width/height constraints for text buttons */
  width: auto; 
  min-width: 32px;
  height: 32px; 
  padding: 0 var(--space-2); /* Add horizontal breathing room */
}

/* Ensure icons inside ghost buttons still look good */
.btn-ghost svg {
  flex-shrink: 0;
}
```

### D. Frontend Logic (`frontend/static/js/dashboard-core.js`)
**Problem:** Stream error state persistence and Download link behavior.
**Fix:** Update `VisionPanel` class.

```javascript
// In VisionPanel class

_startStream() {
    const stream = this.elements['vision-stream'];
    const errorState = document.querySelector('.error-state');
    
    // FIX 1: Reset UI state before starting
    if (errorState) errorState.classList.add('hidden');
    if (stream) stream.classList.remove('hidden');

    if (!stream || this.streamActive) return;

    const src = stream.getAttribute('data-src');
    if (src) {
        stream.src = `${src}?t=${Date.now()}`;
        this.streamActive = true;
        // Re-attach error handler just in case
        stream.onerror = () => this._handleStreamError();
    }
}

_showCapturePreview(url) {
    const preview = this.elements['capture-preview'];
    const thumb = this.elements['capture-thumbnail'];
    const link = this.elements['download-link'];
    
    if (preview && thumb && link) {
        thumb.src = `${url}?t=${Date.now()}`;
        
        // FIX 2: Set download attribute to filename
        link.href = url;
        const filename = url.split('/').pop().split('?')[0];
        link.setAttribute('download', filename);
        
        preview.classList.remove('hidden');
    }
}
```

## 3. ACCEPTANCE CRITERIA

1.  **Vision Card:**
    *   [ ] Contains NO text inside the preview area.
    *   [ ] Displays a centered camera icon in the placeholder.
2.  **Stream Recovery:**
    *   [ ] Disconnect Camera -> Open Modal -> Shows "Camera stream unavailable".
    *   [ ] Reconnect Camera -> Close & Reopen Modal -> **Stream plays immediately** (Error overlay hidden).
3.  **Capture Download:**
    *   [ ] Click "Save Photo" -> Preview appears with image (No 404).
    *   [ ] Click "↓ Download" -> Browser prompts to save file `capture_YYYYMMDD_...jpg`.
    *   [ ] Download button text is fully visible (no overflow).

## 4. RISK MITIGATION

*   **Regression - CSS layout:** Changing `.btn-ghost` width might affect the "X" close buttons.
    *   *Check:* Ensure the close buttons in modal headers still look square. If not, create a specific `.btn-icon-only` class or apply `aspect-ratio: 1`.
*   **Pathing on Pi:** `os.getcwd()` assumes the script is run from the project root.
    *   *Mitigation:* Use `os.path.dirname(os.path.abspath(__file__))` to anchor paths relative to the source code, regardless of where the command is run.
```