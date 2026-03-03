### Updated `API_MAP_LITE.md`

```markdown
# API MAP (LITE)
Last Updated: 2026-03-03
Source: `src/api/server.py`
Version: 4.3.1 (Mode Switching & Camera Focus Endpoints)

### CORE ENDPOINTS

#### GET /api/status
- **Purpose:** System health check and hardware status polling
- **Method:** GET
- **Polling:** DashboardCore polls every 2 seconds
- **Response:**
  ```json
  {
      "mode": "idle",
      "battery_voltage": 12.3,
      "last_error": null,
      "motor_connected": false,
      "lidar_connected": false,
      "camera_connected": true,
      "timestamp": "2026-02-07T14:30:00Z"
  }
  ```
- **Field Descriptions:**
  - `camera_connected`: Boolean indicating camera hardware status (NEW v4.0)
  - `lidar_connected`: Boolean indicating LiDAR hardware status (NEW v4.3)
  - `motor_connected`: Boolean indicating motor controller status

---

#### GET /api/vision/stream
- **Purpose:** MJPEG video stream for live camera feed
- **Method:** GET
- **Constraints:**
  - Quality: 40 (server-enforced optimization)
  - Resolution: 320x240
  - FPS: ~15
  - Bandwidth: ~50-70 KB/s

---

#### POST /api/vision/scan
- **Purpose:** Trigger OCR scan on current camera frame
- **Method:** POST
- **Response (Success):**
  ```json
  {
      "success": true,
      "scan_id": 140285763291232,
      "status": "processing"
  }
  ```
- **Critical Change (v4.2.1):**
  - Callback now injects `scan_id` into result AND validates field names:
    ```python
    result['scan_id'] = scan_id
    result = self._validate_ocr_result(result)  # Normalizes to snake_case
    ```

---

#### GET /api/vision/last-scan
- **Purpose:** Retrieve most recent OCR scan results
- **Method:** GET

---

#### POST /api/vision/capture (v4.1)
- **Purpose:** Capture high-resolution photo for archival/OCR
- **Method:** POST
- **Response (Success):**
  ```json
  {
      "success": true,
      "filename": "capture_20260207_143045.jpg",
      "download_url": "/captures/capture_20260207_143045.jpg",
      "resolution": "1920x1080",
      "timestamp": "2026-02-07T14:30:45Z"
  }
  ```
- **Constraints:**
  - Resolution: 1920x1080 (attempted), fallback to 640x480
  - Quality: 95 (high fidelity for OCR)
  - Storage: Auto-cleanup after 50 images
  - Location: `data/captures/`

---

#### GET /captures/ (v4.1)
- **Purpose:** Serve captured high-resolution images
- **Method:** GET
- **Security:**
  - Filename sanitized (no path traversal)
  - Restricted to `.jpg`/`.jpeg` only
  - Absolute path resolution (prevents 404 errors)

---

#### POST /api/ocr/analyze (NEW v4.2)
- **Purpose:** Analyze image from ANY source (camera/upload/paste)
- **Method:** POST
- **Accepts:**
  - `multipart/form-data` with `image` file (upload)
  - JSON with `image_data` base64 string (paste)
  - URL from captured frame (camera)
- **Response (Success):**
  ```json
  {
      "success": true,
      "scan_id": 548275392208,
      "status": "processing",
      "message": "Image submitted for analysis"
  }
  ```
- **Critical Changes (v4.2.1):**
  - Field Validation: Callback normalizes all field names to snake_case
  - Confidence Clamping: Values clamped to [0.0, 1.0] range
  - Timestamp Validation: Ensures ISO 8601 string format
  - Empty Field Handling: Missing fields set to `None` (not empty string)
- **Constraints:**
  - File size: Max 5MB
  - Valid types: PNG, JPG, WEBP
  - Preprocessing: Resized to 640x480 before OCR
  - Polling: Results available via `/api/vision/results/<scan_id>`

---

#### POST /api/ocr/analyze_batch (NEW v4.2.3)
- **Purpose:** Process multiple uploaded receipt images in one request
- **Method:** POST
- **Request:** `multipart/form-data` with field `images` containing one or more image files
- **Limits:** Maximum 10 files, each ≤5MB
- **Response:** JSON array. Each element corresponds to a file (same order) and has the same structure as the single-file endpoint (`/api/ocr/analyze`). Failed files contain `{"success": false, "error": "reason"}`.
- **Processing:** Sequential (one at a time) to prevent memory exhaustion on Raspberry Pi
- **Example:**
  ```json
  [
    {
      "success": true,
      "scan_id": 123456789,
      "fields": { "trackingNumber": "FE123...", ... },
      "raw_text": "...",
      "engine": "tesseract",
      "processing_time_ms": 1250
    },
    {
      "success": false,
      "error": "Invalid image format"
    }
  ]
  ```

---

#### GET /api/vision/results/<scan_id> (v4.2.1)
- **Purpose:** Poll OCR results with robust ID handling
- **Method:** GET
- **Response (Completed):**
  ```json
  {
      "status": "completed",
      "data": {
          "scan_id": 548275392208,
          "tracking_id": "RTS-12345",
          "order_id": "ORD-67890",
          "rts_code": "BKK-01",
          "district": "Bangrak",
          "confidence": 0.92,
          "timestamp": "2026-02-07T14:30:45Z"
      }
  }
  ```
- **Critical Fix (v4.2.1):**
  - Handles both string and integer `scan_id` comparisons:
    ```python
    state_scan_id = str(scan_data['scan_id'])
    requested_scan_id = str(scan_id)
    if state_scan_id == requested_scan_id:  # Prevents timeout
        return jsonify({'status': 'completed', 'data': scan_data})
    ```

---

### MODE SWITCHING ENDPOINTS (NEW v4.3.1)

#### GET /api/mode
- **Purpose:** Get current operation mode
- **Method:** GET
- **Response:**
  ```json
  {
      "mode": "manual" | "auto"
  }
  ```

---

#### POST /api/mode
- **Purpose:** Set operation mode
- **Method:** POST
- **Request Body:**
  ```json
  {
      "mode": "manual" | "auto"
  }
  ```
- **Response:**
  ```json
  {
      "success": true,
      "mode": "manual" | "auto"
  }
  ```
- **Note:** Switching to `auto` enables obstacle avoidance; switching to `manual` disables it and stops motors.

---

### CAMERA FOCUS ENDPOINTS (NEW v4.3.1)

#### POST /api/camera/focus
- **Purpose:** Adjust lens position for manual focus tuning
- **Method:** POST
- **Request Body:**
  ```json
  {
      "lens_position": float
  }
  ```
  - Range: 0.0–10.0 (where 0.0 = infinity, 10.0 = ~10 cm)
- **Response:**
  ```json
  {
      "success": true,
      "lens_position": float,
      "distance_cm": int
  }
  ```

---

#### GET /api/camera/focus-status
- **Purpose:** Retrieve live focus metadata (FocusFoM, lens position, exposure)
- **Method:** GET
- **Response:**
  ```json
  {
      "status": "ok",
      "focus_fom": int,
      "lens_position": float,
      "exposure_time": int
  }
  ```

---

### MOTOR CONTROL ENDPOINTS

#### POST /api/motor/control
- **Purpose:** Control motor movement with optional speed parameter
- **Method:** POST
- **Request Body:**
  ```json
  {
      "command": "forward" | "backward" | "left" | "right" | "stop",
      "speed": int (optional, 0-255)
  }
  ```
- **Response:**
  ```json
  {
      "success": true,
      "command": "forward",
      "speed": 128
  }
  ```
- **Note:** Speed control is now functional via the `speed` parameter. No new endpoint needed.

---

### LIDAR ENDPOINTS (NEW v4.3)

#### GET /api/lidar/status
- **Purpose:** Returns LiDAR connection and scanning status
- **Method:** GET
- **Response:**
  ```json
  {
      "connected": true,
      "scanning": false,
      "port": "/dev/ttyUSB0",
      "error": null,
      "uptime": 1234
  }
  ```

---

#### POST /api/lidar/start
- **Purpose:** Starts LiDAR scanning
- **Method:** POST
- **Response (Success):**
  ```json
  {
      "success": true
  }
  ```

---

#### POST /api/lidar/stop
- **Purpose:** Stops LiDAR scanning
- **Method:** POST
- **Response (Success):**
  ```json
  {
      "success": true
  }
  ```

---

#### GET /api/lidar/scan
- **Purpose:** Returns current scan data as array of points
- **Method:** GET
- **Response (Success):**
  ```json
  [
      {"angle": 0.0, "distance": 1500},
      {"angle": 1.0, "distance": 1520},
      {"angle": 2.0, "distance": 1480}
  ]
  ```
- **Note:** Returns a **plain array**, not an object with a `points` key. Frontend computes `x` and `y` coordinates for canvas rendering using trigonometry.

---

### LIDAR BODY MASK ENDPOINTS (NEW v4.3.1)

#### GET /api/lidar/body_mask
- **Purpose:** Retrieve current body mask configuration
- **Method:** GET
- **Response:**
  ```json
  {
      "success": true,
      "mask": [
          {"start_angle": 45.0, "end_angle": 135.0, "enabled": true},
          {"start_angle": 225.0, "end_angle": 315.0, "enabled": true}
      ]
  }
  ```

---

#### POST /api/lidar/body_mask
- **Purpose:** Update and persist body mask configuration
- **Method:** POST
- **Request Body:**
  ```json
  {
      "mask": [
          {"start_angle": 45.0, "end_angle": 135.0, "enabled": true},
          {"start_angle": 225.0, "end_angle": 315.0, "enabled": true}
      ]
  }
  ```
- **Response:**
  ```json
  {
      "success": true,
      "message": "Body mask updated successfully"
  }
  ```
- **Note:** Mask configuration is persisted to `config/body_mask.json` and applied to all LiDAR points before obstacle evaluation.

---

## CAMERA HAL LAYER (`src/hardware/camera/`)

### Module: `CameraProvider` (Abstract Base Class)
- **Location:** `src/hardware/camera/base.py`
- **Status:** Implemented
- **Type:** Abstract Base Class (ABC)
- **Purpose:** Defines hardware-agnostic camera interface contract for VisionManager

**Public Interface:**
- `start(width: int, height: int, fps: int) -> bool`
  - Purpose: Initialize camera with specified parameters
  - Contract: Must be called from main thread (picamera2 requirement)
  - Returns: True on success, False on failure
  - Raises: `ValueError` (invalid params), `RuntimeError` (already running)
- `read() -> Tuple[bool, Optional[np.ndarray]]`
  - Purpose: Acquire next available frame
  - Contract: MUST return BGR format for OpenCV compatibility
  - Thread-safe: Safe to call from background threads
  - Returns: (success, frame) tuple
- `stop() -> None`
  - Purpose: Release hardware resources
  - Contract: Idempotent and thread-safe

**Exception Hierarchy:**
- `CameraError` - Base exception
- `CameraInitializationError` - Hardware initialization failures
- `CameraConfigurationError` - Invalid configuration parameters

---

### Module: `UsbCameraProvider`
- **Location:** `src/hardware/camera/usb_provider.py`
- **Status:** Implemented
- **Hardware:** USB webcams (V4L2 backend)

**Implementation Details:**
- Uses OpenCV `cv2.VideoCapture()` with V4L2 backend
- MJPG codec negotiation for bandwidth efficiency
- Auto-fallback to YUYV if MJPG unavailable
- Single-stream configuration (no high-res capture)

**Integration:**
- Primary use: USB webcam fallback when CSI camera unavailable
- Called by: `factory.get_camera_provider(interface="usb")`

---

### Module: `CsiCameraProvider` (UPDATED v4.2.2 - YUV420 Fix)
- **Location:** `src/hardware/camera/csi_provider.py`
- **Status:** Implemented
- **Contract:** `docs/contracts/csi_provider_yuv420_fix.md` v1.0
- **Hardware:** Raspberry Pi Camera Module 3 (IMX708 sensor)
- **Dependencies:** picamera2, cv2, numpy, threading

**Critical Fix (v4.2.2):** Resolved `RuntimeError: lores stream must be YUV` by implementing hardware-compliant YUV420→BGR conversion pipeline.

**Public Interface:**
- `start(width: int, height: int, fps: int) -> bool`
  - Purpose: Initialize CSI camera with dual-stream configuration
  - Streams:
    - `main`: 1920x1080 RGB888 (high-resolution capture)
    - `lores`: WxH YUV420 (live feed - hardware compliant)
  - Validation: Width [320-1920], Height [240-1080], FPS [1-30]
  - Configuration: Uses `picamera2.create_preview_configuration()`
  - Buffer count: 2 (double-buffering for thread safety)
- `read() -> Tuple[bool, Optional[np.ndarray]]`
  - Purpose: Acquire BGR frame from YUV420 stream with CPU conversion
  - Processing Pipeline:
    - Capture YUV420 planar frame from `lores` stream
    - Validate shape: `(height * 1.5, width, 1)`
    - Convert to BGR: `cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)`
    - Return: `(height, width, 3)` uint8 BGR array
  - Thread-safe: Protected by `threading.Lock`
  - Performance: ~8.5ms @ 640x480 on Pi 4B
  - Error Recovery: Graceful failure on shape mismatch or conversion errors
- `stop() -> None`
  - Purpose: Release picamera2 hardware resources
  - Contract: Idempotent and thread-safe

**Internal Capabilities:**
- High-Resolution Capture: Direct access to `main` stream via `picam2.capture_array("main")`
- Resolution: 1920x1080 RGB888
- No conversion overhead (ISP outputs RGB directly)
- Concurrent with `lores` stream (no interruption)

**Dual-Stream Architecture:**
- Simultaneous operation of both streams
- Independent resolution/format per stream
- Thread-safe buffer management

**Performance Characteristics:**
- Conversion Overhead: ~8.5ms per frame @ 640x480
- CPU impact: ~15% of 66.7ms frame budget @ 15fps
- Thermal: +0.5W (acceptable for Pi 4B)
- Memory Footprint: ~6.7MB total
  - ISP DMA buffers: ~4MB
  - YUV420 buffer: ~450KB
  - BGR buffer: ~900KB
  - Double-buffering overhead: 2× per buffer type

**Hardware Context:**
- Platform: Raspberry Pi 4B (VideoCore VI ISP)
- Sensor: Sony IMX708 (11.9MP stacked CMOS)
- ISP Constraint: Low-res output node MUST output YUV420 (hardware limitation)
- Driver: libcamera backend via picamera2 library

**Integration Points:**
- Called by:
  - `VisionManager.start_camera()` - Initialization
  - `VisionManager._frame_capture_loop()` - Background frame acquisition (15fps)
  - `VisionManager.capture_highres()` - High-res still capture
- Enables Endpoints:
  - `/api/vision/stream` - 15fps MJPEG stream (uses `lores` → BGR)
  - `/api/vision/capture` - 1920x1080 stills (uses `main` RGB888)

**Error Handling:**
- Configuration errors: Raise `CameraConfigurationError` with diagnostic info
- Runtime conversion errors: Return `(False, None)` for graceful degradation
- Shape validation: Log warning and reject malformed frames
- Thread safety: Lock prevents concurrent `capture_array()` calls

**YUV420 Technical Details:**
- Format: Planar (I420)
- Y plane: Full resolution luminance
- U/V planes: Quarter resolution chrominance (2x2 subsampling)
- Buffer Layout: Monolithic array with `height = original_height * 1.5`
- Example @ 640x480: Shape is (720, 640, 1)
  - Y: [0:480, :, 0]
  - U: [480:600, :, 0]
  - V: [600:720, :, 0]
- Conversion: OpenCV `COLOR_YUV2BGR_I420` flag (specific to planar YUV420)

**See Also:**
- Base class: `CameraProvider` (src/hardware/camera/base.py)
- Alternative: `UsbCameraProvider` (USB webcam fallback)
- Factory: `get_camera_provider()` (src/hardware/camera/factory.py)
- Contract: `docs/contracts/csi_provider_yuv420_fix.md` v1.0

---

### Module: `CameraFactory`
- **Location:** `src/hardware/camera/factory.py`
- **Status:** Implemented

**Public Interface:**
- `get_camera_provider(interface: Optional[str] = None) -> CameraProvider`
  - Purpose: Factory function for camera instantiation
  - Logic:
    - If `interface="usb"`: Return `UsbCameraProvider()`
    - If `interface="csi"`: Return `CsiCameraProvider()` (requires picamera2)
    - If `interface=None`: Auto-detect (CSI preferred, USB fallback)
  - Returns: Concrete `CameraProvider` implementation
  - Raises: `ImportError` if CSI requested but picamera2 unavailable

---

### Module: `camera.__init__`
- **Location:** `src/hardware/camera/__init__.py`
- **Status:** Implemented

**Exports:**
- `CameraProvider` (ABC)
- `CameraError`, `CameraInitializationError`, `CameraConfigurationError`
- `UsbCameraProvider`
- `CsiCameraProvider` (conditional - only if picamera2 available)
- `get_camera_provider` (factory function)

---

## SERVICES LAYER (`src/services/`)

### Module: `VisionManager`
- **Location:** `src/services/vision_manager.py`
- **Status:** Implemented
- **Dependencies:** Camera HAL (factory pattern)

**Camera Integration:**
- Uses `get_camera_provider()` for hardware abstraction
- Maintains backward compatibility with existing API routes
- Manages camera lifecycle (start/stop/capture)
- Handles background frame capture thread (15fps)
- Generates MJPEG stream for `/api/vision/stream`

**Public Methods (Camera-Related):**
- `start_camera(width, height, fps)` - Initialize camera via factory
- `stop_camera()` - Release camera resources
- `capture_highres()` - Capture 1920x1080 still (CSI only)
- `get_frame()` - Get latest BGR frame for processing

---

### Module: `FlashExpressOCR`
- **Location:** `src/services/ocr_processor.py`
- **Status:** Implemented
- **Contract:** `docs/contracts/ocr_flash_express.md` v1.0

**Public Interface:**
- `__init__(use_paddle_fallback: bool = False, confidence_threshold: float = 0.85, tesseract_config: str = '--oem 1 --psm 6 -l eng', debug_align: bool = False, enable_correction: bool = False, correction_dict_path: Optional[str] = None, use_anchor_extraction: bool = True) -> None`
  - Purpose: Initialize Flash Express OCR processor
  - New:
    - `enable_correction` – toggles post-processing correction using dictionary
    - `correction_dict_path` – path to `ground_truth_parcel_gen.json`
    - `use_anchor_extraction` – (v4.2.3) If True, uses anchor-phrase extraction; if False, reverts to zone-based
  - Raises: `ImportError` (PaddleOCR missing), `ValueError` (invalid threshold)
- `process_frame(bgr_frame: np.ndarray, scan_id: Optional[int] = None) -> Dict[str, Any]`
  - Purpose: Process camera frame for Flash Express receipt field extraction
  - Returns: Dict with success, scan_id, fields (11 receipt fields), raw_text, engine, processing_time_ms
  - When correction enabled: Fields are passed through `FlashExpressCorrector`
  - Target: < 4000ms total processing time on Pi 4B

**Dependencies:**
- Imports: cv2, pytesseract, numpy, re, datetime, typing, dataclasses, threading, logging
- Optional: paddleocr (fallback engine)
- New: `FlashExpressCorrector` (if correction enabled)
- Optional: `pyzbar` (for barcode decoding)

---

### Module: `ReceiptDatabase`
- **Location:** `src/services/receipt_database.py`
- **Status:** Implemented
- **Contract:** `docs/contracts/ocr_flash_express.md` v1.0

**Public Interface:**
- `store_scan(scan_id: int, fields: Dict, raw_text: str, confidence: float, engine: str) -> bool`
  - Purpose: Persist OCR scan results to SQLite database
  - Returns: True on success

**Dependencies:**
- Imports: sqlite3, typing
- Uses: `DatabaseManager.get_connection()`
- Called by: `vision_scan_route()`, `ocr_analyze_route()`

**Database Schema:**
- Table: `receipt_scans` (15 columns including all Flash Express fields)
- Indexes: tracking_id, rts_code, timestamp

---

### Module: `FlashExpressCorrector` (NEW)
- **Location:** `src/services/ocr_correction.py`
- **Status:** Implemented
- **Purpose:** Post-processing correction layer for Flash Express OCR fields using a ground-truth dictionary and fuzzy matching

**Public Interface:**
- `__init__(dictionary_path: str, fuzzy_threshold: float = 80.0) -> None`
  - Loads the Flash Express dictionary from `ground_truth_parcel_gen.json`
- `correct_barangay(text: str) -> str`
  - Fuzzy-match against known barangays
- `correct_district(barangay: str, text: str) -> str`
  - Given a barangay, match against its valid districts
- `validate_tracking_number(text: str) -> Tuple[bool, str]`
  - Validate against regex `^FE\d{10}$`; attempt OCR character correction
- `validate_phone(text: str) -> Tuple[bool, str]`
  - Validate against regex `^\d{12}$`; attempt OCR character correction
- `correct_rider_code(text: str) -> str`
  - Match against enumerated `riderCodes` list
- `correct_sort_code(text: str) -> str`
  - Match against enumerated `sortCode` list
- `derive_quantity_from_weight(weight: int) -> int`
  - Compute quantity using `max(1, weight // 500)`
- `clean_address(text: str) -> str`
  - Remove trailing garbage characters (e.g., `) 1, iy`)

**Dependencies:**
- Imports: json, re, typing, rapidfuzz (or fuzzywuzzy)
- Dictionary file: `data/dictionaries/ground_truth_parcel_gen.json`
- Called internally by `FlashExpressOCR` when correction is enabled

---

### Module: `SimpleObstacleAvoidance`
- **Location:** `src/services/obstacle_avoidance.py`
- **Status:** Implemented
- **Purpose:** LiDAR-based obstacle avoidance with body mask filtering

**Public Interface:**
- `apply_body_mask(points: List[Dict], mask: List[BodyMaskSector]) -> List[Dict]`
  - Purpose: Filter raw LiDAR points before sector evaluation
  - Returns: Filtered point list with masked sectors removed
- `run_once() -> AvoidanceDecision`
  - Purpose: Execute single avoidance cycle
  - Called by: Avoidance loop in hardware manager

**Dependencies:**
- Imports: threading, pathlib, json, typing
- Called by: `run_once()` (avoidance loop), `POST /api/lidar/body_mask` (API)
- Reads from: `config/body_mask.json`

---

### Module: `RobotState`
- **Location:** `src/core/state.py`
- **Status:** Implemented
- **Purpose:** Thread-safe state storage including LiDAR body mask configuration

**Public Interface:**
- `lidar_body_mask` (property, get/set)
  - Purpose: Thread-safe storage + persistence of mask config
  - Returns: List[BodyMaskSector]
  - Sets: Validates and persists mask configuration to `config/body_mask.json`

**Dependencies:**
- Imports: threading, pathlib, json, typing
- Called by: `GET /api/lidar/body_mask`, `POST /api/lidar/body_mask`, `SimpleObstacleAvoidance`

---

### Module: `FlashExpressOCRPanel`
- **Location:** `frontend/static/js/ocr-panel.js`
- **Status:** Implemented

**Public Interface:**
- `constructor()`
  - Purpose: Initialize OCR panel with necessary elements and event listeners
- `openModal()`
  - Purpose: Open the OCR modal and initialize the camera stream
- `closeModal()`
  - Purpose: Close the OCR modal and stop the camera stream
- `switchTab(tabId: string)`
  - Purpose: Switch between camera, upload, and paste tabs
- `analyzeDocument()`
  - Purpose: Trigger OCR analysis on the selected image

**Event Handlers:**
- `closeBtn` - Close modal on click
- `tabs` - Switch tabs on click and keydown
- `captureBtn` - Capture frame from camera on click
- `fileInput` - Handle file selection for upload
- `fileDropzone` - Handle drag and drop for file upload
- `clearUploadBtn` - Clear uploaded image
- `clearPasteBtn` - Clear pasted image
- `analyzeBtn` - Trigger OCR analysis on click
- `clearAllBtn` - Clear all images and results
- `saveScanBtn` - Save scan results to database
- `exportJsonBtn` - Export scan results to JSON
- `btn-copy` - Copy individual fields to clipboard
- `modal` - Handle modal close events

**Dependencies:**
- Imports: None (pure JavaScript)
- Called by: `dashboard-core.js` for modal integration

**Enables:**
- Real-time camera stream for OCR
- Image upload for OCR
- Clipboard paste for OCR
- Result polling and display
- Confidence indicators
- Scan history management

---

## INTEGRATION NOTES

### Theme Persistence
- **Storage key:** `ps-rcs-theme` (localStorage)
- **Values:** `'dark'` or `'light'`
- **Default:** `'dark'`
- **DOM attribute:** `<html data-theme="dark">`

### OCR Scanner Workflow
1. User selects input method (camera/upload/paste tab)
2. Provides image (stream capture / file drop / Ctrl+V paste)
3. Clicks "Analyze Document" → POST to `/api/ocr/analyze`
4. Frontend polls `/api/vision/results/<scan_id>` (500ms intervals)
5. Results appear in panel with confidence indicator
6. User copies fields via hover buttons

### Mode Switching Workflow
1. GET `/api/mode` to check current mode
2. POST `/api/mode` with `{"mode": "auto"}` to enable obstacle avoidance
3. POST `/api/mode` with `{"mode": "manual"}` to disable and stop motors

### Camera Focus Tuning Workflow
1. GET `/api/camera/focus-status` to check current FocusFoM
2. POST `/api/camera/focus` with `{"lens_position": 5.0}` to adjust
3. Repeat until FocusFoM is maximized

### LiDAR Body Mask Workflow
1. GET `/api/lidar/body_mask` to retrieve current mask configuration
2. POST `/api/lidar/body_mask` with updated mask sectors to configure
3. Mask is persisted to `config/body_mask.json` and applied to all LiDAR points

### Error Handling Strategy
- **503 Service Unavailable:** Hardware not connected
- **507 Insufficient Storage:** Disk full during capture
- **400 Bad Request:** Invalid filename/path traversal attempt
- **Graceful Degradation:** Missing DOM elements log warning but don't crash

---

## ENDPOINT SUMMARY

| Endpoint | Method | Purpose | New in |
|----------|--------|---------|--------|
| /api/status | GET | System health & hardware status | ✅ |
| /api/vision/stream | GET | Live MJPEG stream | ✅ |
| /api/vision/scan | POST | Trigger OCR scan | ✅ Field validation |
| /api/vision/last-scan | GET | Retrieve OCR results | ✅ |
| /api/vision/capture | POST | High-res capture | ⭐ v4.1 |
| /captures/ | GET | Serve captures | ⭐ v4.1 |
| /api/ocr/analyze | POST | Multi-source OCR | ⭐ NEW v4.2 |
| /api/ocr/analyze_batch | POST | Batch OCR | ⭐ NEW v4.2.3 |
| /api/vision/results/<scan_id> | GET | Poll results | ✅ ID comparison fix |
| /api/mode | GET/POST | Get/Set operation mode | ⭐ NEW v4.3.1 |
| /api/camera/focus | POST | Adjust lens position | ⭐ NEW v4.3.1 |
| /api/camera/focus-status | GET | Retrieve focus metadata | ⭐ NEW v4.3.1 |
| /api/motor/control | POST | Motor control with speed | ✅ Speed parameter |
| /api/lidar/status | GET | LiDAR connection status | ⭐ NEW v4.3 |
| /api/lidar/start | POST | Start LiDAR scanning | ⭐ NEW v4.3 |
| /api/lidar/stop | POST | Stop LiDAR scanning | ⭐ NEW v4.3 |
| /api/lidar/scan | GET | Get scan point array | ⭐ NEW v4.3 |
| /api/lidar/body_mask | GET/POST | Get/Set body mask config | ⭐ NEW v4.3.1 |

---

## VERSION HISTORY

### v4.3.1 (2026-03-03) - Mode Switching & Camera Focus Endpoints
- **NEW:** Added `/api/mode` GET/POST endpoints for operation mode switching
- **NEW:** Added `/api/camera/focus` POST endpoint for manual focus tuning
- **NEW:** Added `/api/camera/focus-status` GET endpoint for focus metadata
- **NEW:** Added `/api/lidar/body_mask` GET/POST endpoints for body mask configuration
- **NEW:** Motor speed control via `speed` parameter in `/api/motor/control`
- **NEW:** `SimpleObstacleAvoidance.apply_body_mask()` for LiDAR point filtering
- **NEW:** `RobotState.lidar_body_mask` property for thread-safe mask storage
- **FIX:** Obstacle avoidance now properly enabled/disabled via mode switching

### v4.3.0 (2026-02-25) - LiDAR Frontend Integration
- **NEW:** Added LiDAR endpoints (`/api/lidar/status`, `/api/lidar/start`, `/api/lidar/stop`, `/api/lidar/scan`)
- **NEW:** LiDAR panel frontend module (`frontend/static/js/lidar-panel.js`)
- **FIX:** LiDAR API returns plain array (not object with `points` key)
- **FIX:** Frontend computes x,y coordinates from angle/distance using trigonometry
- **FIX:** Canvas scaling to 500×500 with max 8000mm distance

### v4.2.3 (2026-02-20) - VisionManager Stream Property Fix & Batch OCR
- **CRITICAL FIX:** Corrected `stream` property to check `capture_thread.is_alive()` instead of non-existent `provider.is_alive()`
- **NEW:** Added `/api/ocr/analyze_batch` for sequential multi-image processing
- **NEW:** Added `ExtractionGuide` module for dictionary-aware OCR helpers
- **NEW:** Added `use_anchor_extraction` flag to `FlashExpressOCR`

### v4.2.2 (2026-02-15) - YUV420 Fix
- **CRITICAL FIX:** Resolved `RuntimeError: lores stream must be YUV` by implementing hardware-compliant YUV420→BGR conversion pipeline
- **NEW:** Dual-stream architecture (main: 1920x1080 RGB888, lores: YUV420)
- **NEW:** High-resolution capture via `picam2.capture_array("main")`

### v4.2.1 (2026-02-12) - Field Validation and ID Comparison Fix
- **CRITICAL FIX:** Added field validation and ID comparison fix in `vision_manager.py` and `api/server.py`
- **NEW:** Field normalization to snake_case
- **NEW:** Confidence clamping to [0.0, 1.0]
- **NEW:** Timestamp validation (ISO 8601)

### v4.2.0 (2026-02-09) - OCR Backend Integration
- **NEW:** Added OCR endpoints and backend logic
- **NEW:** `FlashExpressOCR` and `ReceiptDatabase` modules
- **NEW:** `FlashExpressCorrector` for post-processing correction

### v4.1.0 (2026-02-07) - High-Res Capture and Serve
- **NEW:** Added high-resolution capture and serve endpoints
- **NEW:** Auto-cleanup after 50 images

### v4.0.0 (2026-02-06) - Initial OCR Integration
- **NEW:** Initial OCR integration with basic endpoints

---

**End of API_MAP_LITE.md**
```

### Summary of Changes:
1. **Added LiDAR Body Mask Endpoints:** GET/POST `/api/lidar/body_mask` for body mask configuration
2. **Added `SimpleObstacleAvoidance` Module:** Documented `apply_body_mask()` method for LiDAR point filtering
3. **Added `RobotState` Module:** Documented `lidar_body_mask` property for thread-safe mask storage
4. **Added Integration Notes:** LiDAR Body Mask Workflow section
5. **Updated Endpoint Summary Table:** Added `/api/lidar/body_mask` endpoint
6. **Updated Version History:** Added v4.3.1 entry with body mask features
7. **Updated Last Updated Date:** 2026-03-03
8. **Updated Version:** 4.3.1 (Mode Switching, Camera Focus & LiDAR Body Mask Endpoints)

This updated `API_MAP_LITE.md` file is now ready for use.

Please confirm by replying with:
> `API_MAP_LITE.md updated to 2026-03-03`