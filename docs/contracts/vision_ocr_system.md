# CONTRACT: Vision & OCR Subsystem
**Version:** 1.0
**Last Updated:** 2026-01-27
**Status:** Draft

## 1. PURPOSE
This subsystem provides real-time camera streaming and on-demand OCR capabilities for Flash Express shipping label extraction. It consists of two core services: `VisionManager` (camera I/O and MJPEG streaming) and `OCRService` (text extraction and validation). The system operates in a non-blocking manner using threading for camera capture and thread pools for CPU-intensive OCR processing, ensuring the main event loop and motor control remain responsive.

---

## 2. PUBLIC INTERFACE

### Module: `src/services/vision_manager.py`

#### Class: `VisionManager`

**Purpose:** Manages USB camera connection, frame buffering, and MJPEG stream generation.

---

##### Method: `__init__`
**Signature:**
```python
def __init__(self) -> None:
    """Initialize VisionManager with empty state."""
```

**Behavior Specification:**
- **Input Validation:** None required.
- **Processing Logic:** 
  - Initialize `self.stream` to `None`
  - Create `threading.Lock()` for `self.frame_lock`
  - Set `self.current_frame` to `None`
  - Set `self.stopped` to `False`
  - Set `self.camera_index` to `None`
  - Set `self.capture_thread` to `None`
- **Output Guarantee:** Instance ready for `start_capture()` call.
- **Side Effects:** None.

**Error Handling:**
- None expected during initialization.

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

##### Method: `start_capture`
**Signature:**
```python
def start_capture(
    self,
    width: int = 640,
    height: int = 480,
    fps: int = 30
) -> bool:
    """Auto-discover camera and start threaded capture loop.
    
    Args:
        width: Frame width in pixels
        height: Frame height in pixels
        fps: Target frames per second
        
    Returns:
        True if camera successfully connected, False otherwise
    """
```

**Behavior Specification:**
- **Input Validation:** 
  - `width` must be > 0 and <= 1920
  - `height` must be > 0 and <= 1080
  - `fps` must be > 0 and <= 60
- **Processing Logic:**
  - Loop through camera indices 0-9
  - Attempt `cv2.VideoCapture(index)` for each
  - Test `.isOpened()` and `.read()` to verify functional camera
  - On success: set stream properties (width, height, fps)
  - Store working index in `self.camera_index`
  - Create daemon thread calling `self._capture_loop()`
  - Start thread and store reference in `self.capture_thread`
- **Output Guarantee:** Returns `True` if camera connected, `False` if no camera found in range 0-9.
- **Side Effects:** 
  - Starts background thread
  - Opens hardware camera device
  - Continuously writes to `self.current_frame`

**Error Handling:**
- **No camera found:** Return `False` (do not raise exception)
- **Invalid parameters:** Raise `ValueError` with message "Invalid camera parameters: width, height, fps must be positive"
- **Thread already running:** Raise `RuntimeError` with message "Capture already started. Call stop_capture() first."

**Performance Requirements:**
- Time Complexity: O(n) where n=10 (max camera indices)
- Space Complexity: O(1)

---

##### Method: `get_frame`
**Signature:**
```python
def get_frame(self) -> Optional[np.ndarray]:
    """Thread-safe access to latest captured frame.
    
    Returns:
        numpy array (BGR format) or None if no frame available
    """
```

**Behavior Specification:**
- **Input Validation:** None.
- **Processing Logic:**
  - Acquire `self.frame_lock`
  - Copy `self.current_frame` (deep copy to prevent race conditions)
  - Release lock
  - Return copied frame
- **Output Guarantee:** Returns copy of latest frame or `None` if capture not started.
- **Side Effects:** None.

**Error Handling:**
- None (returns `None` gracefully if no frame exists).

**Performance Requirements:**
- Time Complexity: O(1) for lock acquisition + O(w*h) for frame copy
- Space Complexity: O(w*h) for frame copy

---

##### Method: `generate_mjpeg`
**Signature:**
```python
def generate_mjpeg(
    self,
    quality: int = 80
) -> Generator[bytes, None, None]:
    """Generator yielding MJPEG stream bytes for HTTP response.
    
    Args:
        quality: JPEG compression quality (1-100)
        
    Yields:
        Multipart JPEG chunks with HTTP headers
    """
```

**Behavior Specification:**
- **Input Validation:** 
  - `quality` must be 1-100
- **Processing Logic:**
  - Infinite loop:
    - Call `self.get_frame()`
    - If frame is `None`, yield placeholder frame or continue
    - Encode frame to JPEG using `cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])`
    - Wrap in multipart/x-mixed-replace boundary format
    - Yield bytes: `b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n'`
    - Sleep 0.033s (30 FPS target)
- **Output Guarantee:** Continuous stream of JPEG frames formatted for HTTP streaming.
- **Side Effects:** Blocks thread while generating (intended for Flask response).

**Error Handling:**
- **Invalid quality:** Raise `ValueError` with message "JPEG quality must be between 1 and 100"
- **Encoding failure:** Log warning, yield previous frame or placeholder

**Performance Requirements:**
- Time Complexity: O(w*h) per frame for JPEG encoding
- Space Complexity: O(w*h) per encoded frame

---

##### Method: `stop_capture`
**Signature:**
```python
def stop_capture(self) -> None:
    """Stop capture thread and release camera."""
```

**Behavior Specification:**
- **Input Validation:** None.
- **Processing Logic:**
  - Set `self.stopped = True`
  - Wait for `self.capture_thread.join(timeout=2.0)`
  - Release `self.stream` via `self.stream.release()`
  - Set `self.stream = None`
  - Set `self.current_frame = None`
- **Output Guarantee:** Camera released, thread stopped.
- **Side Effects:** Closes hardware device.

**Error Handling:**
- **Thread timeout:** Log warning but continue cleanup
- **No active capture:** No-op (safe to call multiple times)

**Performance Requirements:**
- Time Complexity: O(1) + thread join time
- Space Complexity: O(1)

---

##### Method: `_capture_loop` (PRIVATE)
**Signature:**
```python
def _capture_loop(self) -> None:
    """Internal thread loop for continuous frame capture."""
```

**Behavior Specification:**
- **Processing Logic:**
  - While not `self.stopped`:
    - Read frame from `self.stream.read()`
    - If successful, acquire `self.frame_lock`
    - Update `self.current_frame` with new frame
    - Release lock
    - If read fails 10 consecutive times, break loop

**Error Handling:**
- **Camera disconnect:** Exit loop gracefully, log error

---

### Module: `src/services/ocr_service.py`

#### Class: `OCRService`

**Purpose:** Performs OCR on captured frames with Flash Express-specific parsing and validation.

---

##### Method: `__init__`
**Signature:**
```python
def __init__(
    self,
    max_workers: int = 2,
    tesseract_lang: str = 'eng'
) -> None:
    """Initialize OCR service with thread pool.
    
    Args:
        max_workers: Number of ThreadPoolExecutor workers
        tesseract_lang: Tesseract language code ('eng', 'tha', or 'eng+tha')
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `max_workers` must be >= 1 and <= 4
  - `tesseract_lang` must be in `['eng', 'tha', 'eng+tha']`
- **Processing Logic:**
  - Create `ThreadPoolExecutor(max_workers=max_workers)`
  - Store in `self.executor`
  - Load `ENHANCED_LABEL_MODEL` patterns
  - Set `self.tesseract_config` to f'--oem 3 --psm 6 -l {tesseract_lang}'
- **Output Guarantee:** Service ready for `process_scan()` calls.
- **Side Effects:** Creates thread pool (background threads).

**Error Handling:**
- **Invalid max_workers:** Raise `ValueError` with message "max_workers must be between 1 and 4"
- **Invalid language:** Raise `ValueError` with message "tesseract_lang must be 'eng', 'tha', or 'eng+tha'"

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(max_workers)

---

##### Method: `process_scan`
**Signature:**
```python
def process_scan(
    self,
    frame: np.ndarray
) -> concurrent.futures.Future:
    """Submit OCR task to thread pool (non-blocking).
    
    Args:
        frame: BGR image from camera (numpy array)
        
    Returns:
        Future object that resolves to dict with scan results
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `frame` must be a valid numpy array
  - `frame.shape` must have 3 dimensions (H, W, C)
- **Processing Logic:**
  - Submit `self._run_scan(frame)` to `self.executor`
  - Return Future immediately
- **Output Guarantee:** Returns `Future` that will contain `ScanResult` dict.
- **Side Effects:** Spawns background task.

**Error Handling:**
- **Invalid frame:** Raise `ValueError` with message "Frame must be a valid numpy array with shape (H, W, 3)"
- **Executor shutdown:** Raise `RuntimeError` with message "OCR service has been shut down"

**Performance Requirements:**
- Time Complexity: O(1) (submission only)
- Space Complexity: O(1)

---

##### Method: `_run_scan` (PRIVATE)
**Signature:**
```python
def _run_scan(self, frame: np.ndarray) -> Dict[str, Any]:
    """Execute full OCR pipeline (runs in thread pool).
    
    Returns:
        {
            'success': bool,
            'timestamp': str (ISO 8601),
            'tracking_id': Optional[str],
            'order_id': Optional[str],
            'rts_code': Optional[str],
            'district': Optional[str],
            'confidence': float,
            'raw_text': str,
            'error': Optional[str]
        }
    """
```

**Behavior Specification:**
- **Processing Logic:**
  1. Call `self._preprocess_legacy(frame)` → preprocessed image
  2. Call `pytesseract.image_to_string(preprocessed, config=self.tesseract_config)` → raw_text
  3. Call `self._parse_flash_express(raw_text)` → structured data dict
  4. Calculate confidence score based on field matches
  5. Return complete result dict with timestamp
- **Output Guarantee:** Always returns dict (even on failure, with `success=False`).
- **Side Effects:** CPU-intensive processing.

**Error Handling:**
- **Preprocessing failure:** Return `{'success': False, 'error': 'Preprocessing failed: {details}'}`
- **OCR failure:** Return `{'success': False, 'error': 'OCR extraction failed: {details}'}`
- **All exceptions caught:** Never raises, always returns dict

**Performance Requirements:**
- Time Complexity: O(w*h) for preprocessing + O(text_length) for parsing
- Space Complexity: O(w*h) for temporary images
- **Time Limit:** Must complete within 3 seconds (spec requirement)

---

##### Method: `_preprocess_legacy`
**Signature:**
```python
def _preprocess_legacy(self, image: np.ndarray) -> np.ndarray:
    """Apply MSER and perspective correction from legacy image_preprocessor.
    
    Args:
        image: BGR image
        
    Returns:
        Preprocessed grayscale image optimized for OCR
    """
```

**Behavior Specification:**
- **Processing Logic:**
  1. Convert to grayscale via `cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)`
  2. Apply Gaussian Blur: `cv2.GaussianBlur(gray, (5, 5), 0)`
  3. Apply Adaptive Threshold: `cv2.adaptiveThreshold(..., ADAPTIVE_THRESH_GAUSSIAN_C)`
  4. Detect contours for perspective transform
  5. If valid quadrilateral found: apply `cv2.getPerspectiveTransform()` and `cv2.warpPerspective()`
  6. Apply MSER region detection for text area isolation
  7. Return processed image
- **Output Guarantee:** Returns grayscale image ready for Tesseract.
- **Side Effects:** None.

**Error Handling:**
- **No contours found:** Skip perspective transform, continue with threshold image
- **Invalid transform:** Log warning, return non-transformed image

**Performance Requirements:**
- Time Complexity: O(w*h)
- Space Complexity: O(w*h) for intermediate images

---

##### Method: `_parse_flash_express`
**Signature:**
```python
def _parse_flash_express(self, text: str) -> Dict[str, Optional[str]]:
    """Extract Flash Express fields using regex and fuzzy matching.
    
    Args:
        text: Raw OCR output
        
    Returns:
        {
            'tracking_id': Optional[str],  # Pattern: TH[0-9]{10,12}
            'order_id': Optional[str],
            'rts_code': Optional[str],     # Pattern: RTS-[0-9]{2}
            'district': Optional[str]
        }
    """
```

**Behavior Specification:**
- **Processing Logic:**
  1. Clean text: remove whitespace, normalize case
  2. Apply regex patterns from `ENHANCED_LABEL_MODEL`:
     - `TRACKING_PATTERN = r'TH[0-9]{10,12}'`
     - `RTS_PATTERN = r'RTS-[0-9]{2}'`
     - `ORDER_PATTERN = r'ORD[0-9]{6,8}'`
  3. Use Levenshtein distance for fuzzy district matching against known district list
  4. Return dict with extracted fields (None if not found)
- **Output Guarantee:** Always returns dict with all keys present.
- **Side Effects:** None.

**Error Handling:**
- **No matches found:** Return dict with all values as `None` (not an error)

**Performance Requirements:**
- Time Complexity: O(text_length) for regex + O(n*m) for fuzzy matching
- Space Complexity: O(text_length)

---

##### Method: `shutdown`
**Signature:**
```python
def shutdown(self, wait: bool = True) -> None:
    """Gracefully shutdown thread pool.
    
    Args:
        wait: If True, block until all pending tasks complete
    """
```

**Behavior Specification:**
- **Processing Logic:**
  - Call `self.executor.shutdown(wait=wait)`
- **Output Guarantee:** Thread pool stopped.
- **Side Effects:** Blocks if `wait=True`.

**Error Handling:**
- None (shutdown is safe to call multiple times).

---

### Constants Module: `src/services/ocr_patterns.py`

**Purpose:** Centralized regex patterns and validation rules (ported from legacy knowledge_base_optimized.py).

```python
# Flash Express Label Patterns
TRACKING_PATTERN = r'TH[0-9]{10,12}'
RTS_PATTERN = r'RTS-[0-9]{2}'
ORDER_PATTERN = r'ORD[0-9]{6,8}'

# Known RTS Codes (for validation)
VALID_RTS_CODES = {
    'RTS-01': 'Return to Sender - Address Not Found',
    'RTS-02': 'Return to Sender - Refused',
    'RTS-03': 'Return to Sender - Damaged'
}

# Bangkok Districts (for fuzzy matching)
BANGKOK_DISTRICTS = [
    'Bang Khen', 'Bang Kapi', 'Pathum Wan', 'Pom Prap Sattru Phai',
    'Phra Nakhon', 'Min Buri', 'Lat Krabang', 'Yan Nawa',
    'Samphanthawong', 'Phaya Thai', 'Thon Buri', 'Bang Khun Thian'
    # ... (complete list from legacy knowledge base)
]

# Levenshtein threshold for fuzzy matching
FUZZY_MATCH_THRESHOLD = 0.8
```

---

## 3. DEPENDENCIES

### VisionManager Dependencies

**This module CALLS:**
- `cv2.VideoCapture()` - OpenCV camera interface
- `threading.Thread()` - Background capture loop
- `threading.Lock()` - Frame buffer synchronization

**This module is CALLED BY:**
- `src/api/api_routes.py` → `GET /api/vision/stream` → `vision_manager.generate_mjpeg()`
- `src/api/api_routes.py` → `POST /api/vision/scan` → `vision_manager.get_frame()`

### OCRService Dependencies

**This module CALLS:**
- `pytesseract.image_to_string()` - OCR engine
- `cv2` preprocessing functions - Image manipulation
- `concurrent.futures.ThreadPoolExecutor` - Non-blocking execution
- `src/services/ocr_patterns.py` - Validation patterns

**This module is CALLED BY:**
- `src/api/api_routes.py` → `POST /api/vision/scan` → `ocr_service.process_scan()`

---

## 4. DATA STRUCTURES

### ScanResult (TypedDict)
```python
from typing import TypedDict, Optional

class ScanResult(TypedDict):
    success: bool
    timestamp: str  # ISO 8601 format
    tracking_id: Optional[str]
    order_id: Optional[str]
    rts_code: Optional[str]
    district: Optional[str]
    confidence: float  # 0.0 - 1.0
    raw_text: str
    error: Optional[str]
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

**From `docs/system_style.md`:**
1. **Non-Blocking Logic:** OCR processing MUST run in separate thread pool to prevent UI/Motor lag.
2. **Hardware Abstraction:** Camera access encapsulated in service layer (no direct `cv2` calls in API routes).
3. **Single Source of Truth:** Scan results stored in `RobotState.vision.last_scan`.

**From `specs/vision_ocr_integration.md`:**
1. **Performance:** MJPEG stream latency < 500ms.
2. **Performance:** OCR scan completion < 3 seconds.
3. **Camera Resolution:** Force 640x480 for streaming; allow higher resolution for single-frame OCR if needed.
4. **Threading:** Camera I/O must use `threading`, OCR must use `ThreadPoolExecutor`.

---

## 6. MEMORY COMPLIANCE

**Applied Rules:**
- None applicable (no `_memory_snippet.txt` provided in context).

---

## 7. STATE INTEGRATION CONTRACT

### RobotState Schema Extension

**File:** `src/core/state_manager.py`

**Required Addition:**
```python
@dataclass
class VisionState:
    camera_connected: bool = False
    camera_index: Optional[int] = None
    stream_active: bool = False
    last_scan: Optional[ScanResult] = None
    
class RobotState:
    # ... existing fields ...
    vision: VisionState = field(default_factory=VisionState)
```

**Update Methods Required:**
```python
def update_vision_status(self, connected: bool, index: Optional[int] = None) -> None:
    """Called by VisionManager after start_capture()."""
    
def update_scan_result(self, result: ScanResult) -> None:
    """Called after OCR processing completes."""
```

---

## 8. API INTEGRATION CONTRACT

### Required Routes (in `src/api/api_routes.py`)

#### Route 1: Stream Endpoint
```python
@app.route('/api/vision/stream')
def vision_stream():
    """
    Returns: MJPEG stream (Content-Type: multipart/x-mixed-replace)
    Error Codes:
        503: Camera not connected
    """
    if not vision_manager.stream:
        return jsonify({'error': 'Camera not connected'}), 503
    
    return Response(
        vision_manager.generate_mjpeg(quality=80),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
```

#### Route 2: Scan Trigger
```python
@app.route('/api/vision/scan', methods=['POST'])
def trigger_scan():
    """
    Returns: 
        {
            'status': 'processing',
            'message': 'Scan started'
        }
    Error Codes:
        503: Camera not connected
        500: OCR service unavailable
    Side Effects:
        Submits background task that updates RobotState.vision.last_scan
    """
    frame = vision_manager.get_frame()
    if frame is None:
        return jsonify({'error': 'No frame available'}), 503
    
    future = ocr_service.process_scan(frame)
    
    # Non-blocking: result will be in state when ready
    def update_state(future):
        result = future.result()
        state_manager.update_scan_result(result)
    
    future.add_done_callback(update_state)
    
    return jsonify({
        'status': 'processing',
        'message': 'Scan started'
    }), 202
```

#### Route 3: Get Last Scan Result
```python
@app.route('/api/vision/last-scan')
def get_last_scan():
    """
    Returns: ScanResult dict or null
    """
    state = state_manager.get_state()
    return jsonify(state.vision.last_scan)
```

---

## 9. FRONTEND INTEGRATION CONTRACT

### Dashboard HTML Update

**File:** `frontend/templates/service_dashboard.html`

**Required Addition:**
```html
<!-- Vision Feed Card (Add to grid) -->
<div class="dashboard-card" id="vision-card">
    <div class="card-header">
        <h3>📹 Live Camera Feed</h3>
        <span class="status-indicator" id="camera-status">●</span>
    </div>
    <div class="card-body">
        <img id="video-stream" 
             src="/api/vision/stream" 
             alt="Camera feed"
             style="width: 100%; height: auto; border-radius: 8px;">
        <button id="scan-btn" class="action-btn">Scan Label</button>
    </div>
</div>

<!-- Scan Results Card -->
<div class="dashboard-card" id="scan-results-card">
    <div class="card-header">
        <h3>📄 Last Scan Result</h3>
    </div>
    <div class="card-body">
        <div id="scan-data">
            <p><strong>Tracking:</strong> <span id="tracking-id">-</span></p>
            <p><strong>RTS Code:</strong> <span id="rts-code">-</span></p>
            <p><strong>District:</strong> <span id="district">-</span></p>
            <p><strong>Confidence:</strong> <span id="confidence">-</span></p>
        </div>
    </div>
</div>
```

### Dashboard JavaScript Update

**File:** `frontend/static/js/dashboard-core.js`

**Required Addition:**
```javascript
class VisionPanel {
    constructor() {
        this.scanBtn = document.getElementById('scan-btn');
        this.cameraStatus = document.getElementById('camera-status');
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        this.scanBtn.addEventListener('click', () => this.triggerScan());
    }
    
    async triggerScan() {
        this.scanBtn.disabled = true;
        this.scanBtn.textContent = 'Scanning...';
        
        try {
            const response = await fetch('/api/vision/scan', {
                method: 'POST'
            });
            
            if (response.ok) {
                // Poll for result
                setTimeout(() => this.fetchLastScan(), 1000);
            }
        } catch (error) {
            console.error('Scan failed:', error);
        } finally {
            this.scanBtn.disabled = false;
            this.scanBtn.textContent = 'Scan Label';
        }
    }
    
    async fetchLastScan() {
        const response = await fetch('/api/vision/last-scan');
        const data = await response.json();
        
        if (data && data.success) {
            document.getElementById('tracking-id').textContent = data.tracking_id || '-';
            document.getElementById('rts-code').textContent = data.rts_code || '-';
            document.getElementById('district').textContent = data.district || '-';
            document.getElementById('confidence').textContent = 
                (data.confidence * 100).toFixed(1) + '%';
        }
    }
    
    updateCameraStatus(connected) {
        this.cameraStatus.style.color = connected ? 'var(--success-color)' : 'var(--error-color)';
    }
}

// Add to DashboardCore initialization
const visionPanel = new VisionPanel();
```

### CSS Additions

**File:** `frontend/static/css/service_theme.css`

**Required Styles:**
```css
#video-stream {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
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
}

#scan-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

#scan-data p {
    margin: 0.5rem 0;
    font-family: 'Roboto Mono', monospace;
}
```

---

## 10. ACCEPTANCE CRITERIA

### Test Case 1: Camera Auto-Discovery
- **Input:** System with USB camera at index 2
- **Expected Output:** `vision_manager.start_capture()` returns `True`
- **Expected Behavior:** 
  - `vision_manager.camera_index == 2`
  - `state.vision.camera_connected == True`
  - Stream immediately available at `/api/vision/stream`

### Test Case 2: MJPEG Streaming
- **Input:** Browser navigates to `/api/vision/stream`
- **Expected Output:** Live video feed displays
- **Expected Behavior:**
  - HTTP 200 response
  - Content-Type: `multipart/x-mixed-replace; boundary=frame`
  - Latency < 500ms (spec requirement)

### Test Case 3: Successful OCR Scan
- **Input:** Frame containing valid Flash Express label with tracking "TH0123456789"
- **Expected Output:** 
```json
{
  "success": true,
  "tracking_id": "TH0123456789",
  "rts_code": "RTS-01",
  "confidence": 0.95,
  "error": null
}
```
- **Expected Behavior:**
  - Scan completes within 3 seconds
  - Result stored in `RobotState.vision.last_scan`
  - `/api/vision/last-scan` returns same data

### Test Case 4: OCR with Invalid Label
- **Input:** Frame with no recognizable text
- **Expected Output:**
```json
{
  "success": false,
  "tracking_id": null,
  "confidence": 0.0,
  "error": null
}
```
- **Expected Behavior:** No exception raised, graceful degradation

### Test Case 5: No Camera Available
- **Input:** System with no USB cameras
- **Expected Output:** `vision_manager.start_capture()` returns `False`
- **Expected Behavior:**
  - `/api/vision/stream` returns 503
  - `/api/vision/scan` returns 503
  - No background threads started

### Test Case 6: Concurrent Scans
- **Input:** Two scan requests sent 100ms apart
- **Expected Output:** Both complete successfully
- **Expected Behavior:**
  - ThreadPoolExecutor queues second request
  - No race conditions on `state.vision.last_scan`
  - Both return 202 Accepted

### Test Case 7: Camera Disconnect During Operation
- **Input:** USB camera unplugged while streaming
- **Expected Output:** Stream stops gracefully
- **Expected Behavior:**
  - Capture loop exits cleanly
  - `state.vision.camera_connected` updates to `False`
  - Frontend displays error state

---

## 11. INSTALLATION REQUIREMENTS

### System Dependencies
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-eng
# Optional: Thai language support
sudo apt-get install tesseract-ocr-tha

# Verify installation
tesseract --version
```

### Python Dependencies
```txt
opencv-python-headless==4.8.1.78
pytesseract==0.3.10
numpy==1.24.3
```

### Permissions (Linux)
```bash
# Add user to video group for camera access
sudo usermod -a -G video $USER
```

---

## 12. PERFORMANCE BENCHMARKS

| Operation | Target | Maximum |
|-----------|--------|---------|
| Camera initialization | < 1s | 2s |
| Frame capture rate | 30 FPS | 15 FPS min |
| MJPEG stream latency | 300ms | 500ms |
| OCR processing time | 2s | 3s |
| Memory per frame | 1MB | 2MB |
| Thread pool workers | 2 | 4 |

---

## 13. MIGRATION NOTES FROM LEGACY CODE

### From `image_preprocessor.py`
- **Port:** MSER region detection → `VisionManager._preprocess_legacy()`
- **Port:** Perspective correction → `VisionManager._preprocess_legacy()`
- **Change:** Remove GUI dependencies (cv2.imshow)
- **Change:** Adapt for numpy array input instead of file paths

### From `knowledge_base_optimized.py`
- **Port:** Regex patterns → `ocr_patterns.py`
- **Port:** Levenshtein fuzzy matching → `OCRService._parse_flash_express()`
- **Port:** District validation list → `ocr_patterns.py`
- **Change:** Return structured dict instead of printing results

---