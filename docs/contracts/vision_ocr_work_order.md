# WORK ORDER FOR IMPLEMENTER

**Contract Reference:** `docs/contracts/vision_ocr_system.md` v1.0  
**Target Files:** 
- `src/services/vision_manager.py`
- `src/services/ocr_service.py`
- `src/services/ocr_patterns.py`
- `src/core/state_manager.py` (UPDATE ONLY)
- `src/api/api_routes.py` (UPDATE ONLY)
- `frontend/templates/service_dashboard.html` (UPDATE ONLY)
- `frontend/static/js/dashboard-core.js` (UPDATE ONLY)
- `frontend/static/css/service_theme.css` (UPDATE ONLY)

---

## STRICT CONSTRAINTS (NON-NEGOTIABLE)

### From `docs/system_style.md`:
1. **Threading Model:** Camera I/O MUST use `threading.Thread()`, OCR MUST use `concurrent.futures.ThreadPoolExecutor`.
2. **Non-Blocking Requirement:** OCR processing CANNOT block the main event loop or motor control.
3. **Hardware Abstraction:** NO direct `cv2` or `pytesseract` calls outside of service layer (`src/services/`).
4. **Single Source of Truth:** All vision data flows through `RobotState.vision`.
5. **Code Standards:**
   - PEP 8 compliance
   - Google-style docstrings (MANDATORY)
   - Type hints on all signatures
   - Class names: `PascalCase`
   - Method names: `snake_case`
   - Constants: `UPPER_SNAKE_CASE`

### From `specs/vision_ocr_integration.md`:
1. **Performance Targets:**
   - MJPEG stream latency < 500ms
   - OCR scan completion < 3 seconds
   - Camera resolution locked at 640x480 for streaming
2. **Error Handling:** Service degradation (return False/None) instead of crashes.
3. **Camera Discovery:** Loop indices 0-9, first working camera wins.

---

## MEMORY COMPLIANCE (MANDATORY)

No `_memory_snippet.txt` was provided, but these architectural rules apply:

1. **Contract Immutability:** Do NOT modify any method signatures from the contract.
2. **State Updates:** Use `state_manager.update_vision_status()` and `state_manager.update_scan_result()` exclusively.
3. **Legacy Code Ports:** Preserve MSER and regex logic from legacy modules exactly as specified.

---

## IMPLEMENTATION ROADMAP

### Phase 1: Core Services (Priority 1)

#### Task 1.1: Create `src/services/ocr_patterns.py`
```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: ocr_patterns.py
Description: Flash Express label validation patterns and constants
"""

import re
from typing import List, Dict

# Regex patterns for Flash Express labels
TRACKING_PATTERN: re.Pattern = re.compile(r'TH[0-9]{10,12}')
RTS_PATTERN: re.Pattern = re.compile(r'RTS-[0-9]{2}')
ORDER_PATTERN: re.Pattern = re.compile(r'ORD[0-9]{6,8}')

# Validation lookup
VALID_RTS_CODES: Dict[str, str] = {
    'RTS-01': 'Return to Sender - Address Not Found',
    'RTS-02': 'Return to Sender - Refused',
    'RTS-03': 'Return to Sender - Damaged',
    # Add remaining codes from legacy knowledge_base_optimized.py
}

# Bangkok districts for fuzzy matching
BANGKOK_DISTRICTS: List[str] = [
    'Bang Khen', 'Bang Kapi', 'Pathum Wan', 
    # ... Complete list from legacy
]

# Fuzzy match threshold (Levenshtein distance)
FUZZY_MATCH_THRESHOLD: float = 0.8
```

**Success Criteria:**
- File exists with all constants defined
- No logic, pure data definitions
- Passes `flake8` linting

---

#### Task 1.2: Implement `src/services/vision_manager.py`
**Critical Requirements:**
1. Implement ALL methods from contract Section 2
2. Use `threading.Lock()` for `self.current_frame` access
3. Camera loop MUST be daemon thread
4. JPEG quality parameter in `generate_mjpeg()` defaults to 80
5. Handle camera disconnect gracefully in `_capture_loop()`

**Pseudocode for `_capture_loop()`:**
```python
def _capture_loop(self):
    consecutive_failures = 0
    while not self.stopped:
        ret, frame = self.stream.read()
        if ret:
            with self.frame_lock:
                self.current_frame = frame
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures > 10:
                logger.error("Camera disconnected")
                break
        time.sleep(0.001)  # Prevent CPU thrashing
```

**Verification Checklist:**
- [ ] All method signatures match contract exactly
- [ ] Type hints present on all methods
- [ ] Google-style docstrings on all public methods
- [ ] Thread cleanup in `stop_capture()` with timeout
- [ ] `generate_mjpeg()` yields proper multipart boundaries

---

#### Task 1.3: Implement `src/services/ocr_service.py`
**Critical Requirements:**
1. Import `ocr_patterns.py` for constants
2. ThreadPoolExecutor initialized in `__init__`
3. `process_scan()` returns `Future` immediately (non-blocking)
4. `_run_scan()` NEVER raises exceptions (catches all, returns error dict)
5. Port preprocessing logic from legacy `image_preprocessor.py`:
   - Grayscale conversion
   - Gaussian blur (5x5 kernel)
   - Adaptive threshold
   - Contour detection → Perspective transform

**Preprocessing Template:**
```python
def _preprocess_legacy(self, image: np.ndarray) -> np.ndarray:
    """Apply legacy MSER preprocessing pipeline."""
    # Step 1: Grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Step 2: Denoise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Step 3: Adaptive threshold
    thresh = cv2.adaptiveThreshold(
        blurred, 255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Step 4: Find contours for perspective correction
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Step 5: Apply perspective transform if valid quad found
    # (Port exact logic from legacy image_preprocessor.py)
    
    return thresh  # or warped image if transform applied
```

**Fuzzy Matching Implementation:**
```python
def _fuzzy_match_district(self, text: str) -> Optional[str]:
    """Match district name using Levenshtein distance."""
    from difflib import SequenceMatcher
    
    best_match = None
    best_ratio = 0.0
    
    for district in BANGKOK_DISTRICTS:
        ratio = SequenceMatcher(None, text.lower(), district.lower()).ratio()
        if ratio > best_ratio and ratio >= FUZZY_MATCH_THRESHOLD:
            best_ratio = ratio
            best_match = district
    
    return best_match
```

**Verification Checklist:**
- [ ] ThreadPoolExecutor created with max_workers=2
- [ ] `shutdown()` method implemented
- [ ] All regex patterns use `ocr_patterns.py` constants
- [ ] Confidence score calculated (0.0-1.0)
- [ ] Timestamp in ISO 8601 format
- [ ] Never raises exceptions in `_run_scan()`

---

### Phase 2: State Integration (Priority 2)

#### Task 2.1: Update `src/core/state_manager.py`
**Required Changes:**
1. Add `VisionState` dataclass (as per contract Section 7)
2. Add `vision: VisionState` field to `RobotState`
3. Implement `update_vision_status()` method
4. Implement `update_scan_result()` method

**Template:**
```python
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

@dataclass
class VisionState:
    """Vision subsystem state."""
    camera_connected: bool = False
    camera_index: Optional[int] = None
    stream_active: bool = False
    last_scan: Optional[Dict[str, Any]] = None

class RobotState:
    # ... existing fields ...
    vision: VisionState = field(default_factory=VisionState)
    
    def update_vision_status(self, connected: bool, index: Optional[int] = None) -> None:
        """Update camera connection status."""
        self.vision.camera_connected = connected
        self.vision.camera_index = index
        self.vision.stream_active = connected
        self._notify_observers()
    
    def update_scan_result(self, result: Dict[str, Any]) -> None:
        """Update last OCR scan result."""
        self.vision.last_scan = result
        self._notify_observers()
```

**Verification:**
- [ ] `VisionState` matches contract structure
- [ ] Methods update state atomically
- [ ] Observers notified on updates

---

### Phase 3: API Integration (Priority 3)

#### Task 3.1: Update `src/api/api_routes.py`
**Required Routes:**
1. `GET /api/vision/stream` → MJPEG stream
2. `POST /api/vision/scan` → Trigger OCR
3. `GET /api/vision/last-scan` → Retrieve result

**Implementation Template:**
```python
from flask import Response, jsonify
from src.services.vision_manager import VisionManager
from src.services.ocr_service import OCRService

# Singleton instances (initialize at module level)
vision_manager = VisionManager()
ocr_service = OCRService(max_workers=2)

@app.route('/api/vision/stream')
def vision_stream():
    """Stream MJPEG video feed."""
    if not vision_manager.stream:
        return jsonify({'error': 'Camera not connected'}), 503
    
    return Response(
        vision_manager.generate_mjpeg(quality=80),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/vision/scan', methods=['POST'])
def trigger_scan():
    """Trigger OCR scan (non-blocking)."""
    frame = vision_manager.get_frame()
    if frame is None:
        return jsonify({'error': 'No frame available'}), 503
    
    # Submit to thread pool
    future = ocr_service.process_scan(frame)
    
    # Register callback to update state
    def on_complete(future):
        try:
            result = future.result()
            state_manager.update_scan_result(result)
        except Exception as e:
            logger.error(f"OCR callback error: {e}")
    
    future.add_done_callback(on_complete)
    
    return jsonify({
        'status': 'processing',
        'message': 'Scan started'
    }), 202

@app.route('/api/vision/last-scan')
def get_last_scan():
    """Retrieve last scan result."""
    state = state_manager.get_state()
    return jsonify(state.vision.last_scan)
```

**Startup Code (in `main.py` or `api_routes.py`):**
```python
# Initialize vision on server start
if vision_manager.start_capture():
    state_manager.update_vision_status(True, vision_manager.camera_index)
    logger.info(f"Camera initialized at index {vision_manager.camera_index}")
else:
    logger.warning("No camera detected")
```

**Shutdown Code:**
```python
# In cleanup/shutdown handler
vision_manager.stop_capture()
ocr_service.shutdown(wait=True)
```

**Verification:**
- [ ] Routes return correct HTTP status codes
- [ ] Error responses include descriptive messages
- [ ] Async callback updates state correctly
- [ ] No blocking operations in request handlers

---

### Phase 4: Frontend Integration (Priority 4)

#### Task 4.1: Update `frontend/templates/service_dashboard.html`
**Add to grid layout:**
```html
<!-- Insert after existing cards -->
<div class="dashboard-card" id="vision-card">
    <div class="card-header">
        <h3>📹 Live Camera Feed</h3>
        <span class="status-indicator" id="camera-status">●</span>
    </div>
    <div class="card-body">
        <img id="video-stream" 
             src="/api/vision/stream" 
             alt="Camera feed"
             onerror="this.src='/static/img/no-camera.png'"
             style="width: 100%; height: auto; border-radius: 8px;">
        <button id="scan-btn" class="action-btn">Scan Label</button>
    </div>
</div>

<div class="dashboard-card" id="scan-results-card">
    <div class="card-header">
        <h3>📄 Last Scan Result</h3>
    </div>
    <div class="card-body">
        <div id="scan-data">
            <p><strong>Tracking ID:</strong> <span id="tracking-id">-</span></p>
            <p><strong>Order ID:</strong> <span id="order-id">-</span></p>
            <p><strong>RTS Code:</strong> <span id="rts-code">-</span></p>
            <p><strong>District:</strong> <span id="district">-</span></p>
            <p><strong>Confidence:</strong> <span id="confidence">-</span></p>
            <p><strong>Time:</strong> <span id="scan-time">-</span></p>
        </div>
    </div>
</div>
```

---

#### Task 4.2: Update `frontend/static/js/dashboard-core.js`
**Add VisionPanel class:**
```javascript
class VisionPanel {
    constructor() {
        this.scanBtn = document.getElementById('scan-btn');
        this.cameraStatus = document.getElementById('camera-status');
        this.videoStream = document.getElementById('video-stream');
        this.setupEventListeners();
        this.startPolling();
    }
    
    setupEventListeners() {
        this.scanBtn.addEventListener('click', () => this.triggerScan());
        
        // Handle stream errors
        this.videoStream.addEventListener('error', () => {
            this.updateCameraStatus(false);
        });
        
        this.videoStream.addEventListener('load', () => {
            this.updateCameraStatus(true);
        });
    }
    
    async triggerScan() {
        this.scanBtn.disabled = true;
        this.scanBtn.textContent = 'Scanning...';
        
        try {
            const response = await fetch('/api/vision/scan', {
                method: 'POST'
            });
            
            if (response.ok) {
                // Poll for result after 2 seconds
                setTimeout(() => this.fetchLastScan(), 2000);
            } else {
                const error = await response.json();
                console.error('Scan failed:', error);
            }
        } catch (error) {
            console.error('Network error:', error);
        } finally {
            setTimeout(() => {
                this.scanBtn.disabled = false;
                this.scanBtn.textContent = 'Scan Label';
            }, 3000);
        }
    }
    
    async fetchLastScan() {
        try {
            const response = await fetch('/api/vision/last-scan');
            const data = await response.json();
            
            if (data && data.success) {
                this.updateScanDisplay(data);
            } else if (data && data.error) {
                this.showScanError(data.error);
            }
        } catch (error) {
            console.error('Failed to fetch scan result:', error);
        }
    }
    
    updateScanDisplay(data) {
        document.getElementById('tracking-id').textContent = data.tracking_id || '-';
        document.getElementById('order-id').textContent = data.order_id || '-';
        document.getElementById('rts-code').textContent = data.rts_code || '-';
        document.getElementById('district').textContent = data.district || '-';
        document.getElementById('confidence').textContent = 
            data.confidence ? (data.confidence * 100).toFixed(1) + '%' : '-';
        document.getElementById('scan-time').textContent = 
            data.timestamp ? new Date(data.timestamp).toLocaleString() : '-';
    }
    
    updateCameraStatus(connected) {
        this.cameraStatus.style.color = connected ? 
            'var(--success-color)' : 'var(--error-color)';
    }
    
    startPolling() {
        // Poll last scan every 5 seconds
        setInterval(() => this.fetchLastScan(), 5000);
    }
}

// Initialize in DashboardCore
document.addEventListener('DOMContentLoaded', () => {
    const visionPanel = new VisionPanel();
});
```

---

#### Task 4.3: Update `frontend/static/css/service_theme.css`
**Add styles:**
```css
/* Vision Panel Styles */
#video-stream {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    max-height: 400px;
    object-fit: contain;
}

#scan-btn {
    width: 100%;
    margin-top: 1rem;
    padding: 0.75rem;
    background: var(--primary-color);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.2s;
}

#scan-btn:hover {
    background: var(--primary-color-dark);
}

#scan-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

#scan-data p {
    margin: 0.5rem 0;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.9rem;
}

#scan-data strong {
    color: var(--text-secondary);
}

.status-indicator {
    font-size: 1.2rem;
    transition: color 0.3s;
}
```

---

## INTEGRATION SEQUENCE

Execute in this order:

1. **Install Dependencies:**
   ```bash
   pip install opencv-python-headless pytesseract numpy
   sudo apt-get install tesseract-ocr tesseract-ocr-eng
   ```

2. **Implement Services:**
   - Create `ocr_patterns.py`
   - Create `vision_manager.py`
   - Create `ocr_service.py`

3. **Update State:**
   - Modify `state_manager.py`

4. **Update API:**
   - Modify `api_routes.py`
   - Add initialization code

5. **Update Frontend:**
   - Modify `service_dashboard.html`
   - Modify `dashboard-core.js`
   - Modify `service_theme.css`

6. **Test:**
   - Camera auto-detection
   - Stream rendering
   - Scan trigger
   - Result display

---

## SUCCESS CRITERIA

### Code Quality
- [ ] All files pass `flake8` linting
- [ ] All methods have Google-style docstrings
- [ ] Type hints on all signatures
- [ ] No `# type: ignore` comments

### Functionality
- [ ] Camera connects automatically on server start
- [ ] MJPEG stream displays in browser with < 500ms latency
- [ ] Scan button triggers OCR without blocking UI
- [ ] Results appear in dashboard within 3 seconds
- [ ] Camera disconnect handled gracefully

### Testing
- [ ] All 7 test cases from contract Section 10 pass
- [ ] No exceptions in logs during normal operation
- [ ] Memory usage stable over 10 scans

---

## AUDITOR HANDOFF

After implementation, provide to Auditor:

**Files for Review:**
- `src/services/vision_manager.py`
- `src/services/ocr_service.py`
- `src/services/ocr_patterns.py`
- `src/core/state_manager.py` (updated sections only)
- `src/api/api_routes.py` (new routes only)

**Verification Command:**
```
/verify-context: docs/contracts/vision_ocr_system.md, docs/system_style.md, src/services/vision_manager.py, src/services/ocr_service.py
```

**Audit Checklist:**
- [ ] All contract signatures match exactly
- [ ] Threading model correct (threading for camera, ThreadPoolExecutor for OCR)
- [ ] No blocking operations in API handlers
- [ ] Error handling follows contract specifications
- [ ] State updates use proper methods
- [ ] Frontend integration complete

---

## NOTES

- **Legacy Code:** Preserve exact MSER/perspective logic from `image_preprocessor.py`
- **Performance:** If OCR takes > 3s, consider reducing Tesseract PSM mode or image resolution
- **Thai Support:** If needed later, add `tesseract-ocr-tha` and change `tesseract_lang='eng+tha'`
- **Barcode Fallback:** Future enhancement - add `pyzbar` for barcode scanning if OCR fails