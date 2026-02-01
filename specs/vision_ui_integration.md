```markdown
# FEATURE SPEC: Vision UI Integration
**Date:** 2025-01-24
**Status:** Feasible
**Target File:** `docs/specs/vision_ui_integration_spec.md`

## 1. THE VISION
*   **User Story:** As a Service Technician, I need to view the robot's camera feed and trigger label scans from the Service Dashboard so that I can verify package sorting without physically inspecting the robot.
*   **Success Metrics:**
    *   Clicking the Camera Bento Card opens the modal < 200ms.
    *   MJPEG Stream loads in Modal < 1s.
    *   Stream stops (bandwidth drops) when Modal closes.
    *   OCR Scan populates the "Last Scan Results" card within 3s.

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed (Uses existing API, adheres to Bento grid).
*   **New Libraries Needed:** None (Vanilla JS/CSS).
*   **Risk Level:** Medium (DOM manipulation on Pi requires strict performance throttling).
*   **Constraint Compliance:**
    *   *Progressive Disclosure:* Stream hidden behind modal click.
    *   *Bandwidth:* Stream active only when viewing.
    *   *Code Style:* JS methods to be kept small (<50 lines).

## 3. ATOMIC TASKS (The Roadmap)

### Frontend Structure (HTML)
*   [ ] **Update `templates/service_dashboard.html`**:
    *   Add `div.bento-card` (id: `card-camera-preview`) to the grid.
    *   Add `div.modal` (id: `modal-vision`) containing the full-size video element and controls.

### Frontend Style (CSS)
*   [ ] **Update `static/css/dashboard.css`**:
    *   Define `.camera-preview` styles (blurred background, centered status icon).
    *   Define `.modal-vision` layout (80% width, responsive video container).
    *   Ensure all colors use CSS variables (`--glass-bg`, `--text-primary`).

### Frontend Logic (JS)
*   [ ] **Refactor `static/js/panels/VisionPanel.js`**:
    *   Implement `constructor` with null checks.
    *   Implement `openVisionModal()` (sets stream src).
    *   Implement `closeVisionModal()` (clears stream src).
    *   Implement `handleScanTrigger()` (async fetch).
    *   Implement `updateResultCard()` (DOM updates).

---

## 4. INTERFACE SKETCHES (For Architect)

### A. HTML Structure
**File:** `service_dashboard.html`

```html
<!-- 1. The Bento Card (Idle State) -->
<div class="bento-card" id="card-camera-preview">
    <div class="card-header">
        <h3>Vision System</h3>
        <span class="status-dot" id="cam-status-dot"></span>
    </div>
    <div class="preview-container">
        <!-- Placeholder image, NOT live stream -->
        <img src="/static/assets/cam_placeholder.png" class="camera-blur">
        <button class="btn-overlay">View Feed</button>
    </div>
</div>

<!-- 2. The Modal (Active State) -->
<dialog id="modal-vision" class="glass-modal">
    <div class="modal-header">
        <h2>Live Feed</h2>
        <button class="btn-close">×</button>
    </div>
    <div class="video-wrapper">
        <!-- SRC is empty by default to save bandwidth -->
        <img id="video-stream-modal" alt="Live Feed" width="320" height="240">
    </div>
    <div class="modal-controls">
        <button id="btn-scan-trigger" class="btn-primary">Scan Label</button>
    </div>
</dialog>
```

### B. JavaScript Logic
**Module:** `VisionPanel.js`

*   `constructor()`
    *   *Logic:* Look for `card-camera-preview`, `modal-vision`, `btn-scan-trigger`. If missing, log warning and return. Else, call `initListeners`.
*   `openModal()`
    *   *Logic:* Add `.active` class to modal. Set `img.src = "/api/vision/stream?t=" + Date.now()`.
*   `closeModal()`
    *   *Logic:* Remove `.active` class. Set `img.src = ""`. (Crucial for bandwidth).
*   `triggerScan()`
    *   *Logic:* specific endpoint `POST /api/vision/scan`. Disable button. Show spinner.
*   `pollResults()`
    *   *Logic:* Wait 1s, then `GET /api/vision/last-scan`. Pass data to `renderResults`.

## 5. INTEGRATION POINTS
*   **Touches:** `templates/service_dashboard.html` (DOM injection).
*   **Touches:** `static/js/dashboard_core.js` (Status LED synchronization).
*   **Data Flow:**
    *   User Click -> JS `src` injection -> Browser requests `/api/vision/stream` -> `VisionManager` (Backend).
    *   User Scan -> POST `/api/vision/scan` -> `OCRService` -> Database.

## 6. OPEN QUESTIONS
*   Does `DashboardCore` currently expose a global method to trigger "Toast" notifications for scan success/fail?
*   Should the static preview card update its snapshot periodically (e.g., every 10s), or remain strictly static until clicked? *Assumption: Strictly static for now to minimize traffic.*

## 7. RISK MITIGATION
*   **Missing Camera:** If `video-stream-modal` triggers `onerror`, replace with "Camera Offline" placeholder graphic instantly.
*   **Stuck Modal:** Ensure `Esc` key and "Backdrop Click" both map to `closeModal()` to prevent UI traps.

```

✅ **Spec Created:** `docs/specs/vision_ui_integration_spec.md`
📋 **Next Step:** Review Spec, then pass to Architect.
👉 **Next Agent:** Architect (AGENTS/01_architect.md)