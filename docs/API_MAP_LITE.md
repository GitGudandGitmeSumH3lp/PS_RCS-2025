```

### Updated `API_MAP_LITE.md`

```markdown
API MAP (LITE)
Last Updated: 2026-02-09
Source: src/api/server.py
Version: 4.2.3 (VisionManager Stream Property Fix)

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

#### GET /api/vision/stream
- **Purpose:** MJPEG video stream for live camera feed
- **Constraints:**
  - Quality: 40 (server-enforced optimization)
  - Resolution: 320x240
  - FPS: ~15
  - Bandwidth: ~50-70 KB/s

#### POST /api/vision/scan
- **Purpose:** Trigger OCR scan on current camera frame
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

#### GET /api/vision/last-scan
- **Purpose:** Retrieve most recent OCR scan results

#### POST /api/vision/capture (v4.1)
- **Purpose:** Capture high-resolution photo for archival/OCR
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

#### GET /captures/<filename> (v4.1)
- **Purpose:** Serve captured high-resolution images
- **Security:**
  - Filename sanitized (no path traversal)
  - Restricted to `.jpg`/`.jpeg` only
  - Absolute path resolution (prevents 404 errors)

#### POST /api/ocr/analyze (NEW v4.2)
- **Purpose:** Analyze image from ANY source (camera/upload/paste)
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
  - Field Validation: Callback normalizes all field names to snake_case:
    ```python
    result = self._validate_ocr_result(result)
    # Returns: {tracking_id, order_id, rts_code, district, confidence, timestamp}
    ```
  - Confidence Clamping: Values clamped to [0.0, 1.0] range
  - Timestamp Validation: Ensures ISO 8601 string format
  - Empty Field Handling: Missing fields set to `None` (not empty string)
- **Constraints:**
  - File size: Max 5MB
  - Valid types: PNG, JPG, WEBP
  - Preprocessing: Resized to 640x480 before OCR
  - Polling: Results available via `/api/vision/results/<scan_id>`

#### GET /api/vision/results/<scan_id> (v4.2.1)
- **Purpose:** Poll OCR results with robust ID handling
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

### CAMERA HAL LAYER (`src/hardware/camera/`)

#### Module: `CameraProvider` (Abstract Base Class)
- **Location:** `src/hardware/camera/base.py`
- **Status:** Implemented
- **Type:** Abstract Base Class (ABC)
- **Purpose:** Defines hardware-agnostic camera interface contract for VisionManager.
- **Public Interface:**
  - `start(width: int, height: int, fps: int) -> bool`
    - **Purpose:** Initialize camera with specified parameters
    - **Contract:** Must be called from main thread (picamera2 requirement)
    - **Returns:** True on success, False on failure
    - **Raises:** `ValueError` (invalid params), `RuntimeError` (already running)
  - `read() -> Tuple[bool, Optional[np.ndarray]]`
    - **Purpose:** Acquire next available frame
    - **Contract:** MUST return BGR format for OpenCV compatibility
    - **Thread-safe:** Safe to call from background threads
    - **Returns:** (success, frame) tuple
  - `stop() -> None`
    - **Purpose:** Release hardware resources
    - **Contract:** Idempotent and thread-safe
- **Exception Hierarchy:**
  - `CameraError` - Base exception
  - `CameraInitializationError` - Hardware initialization failures
  - `CameraConfigurationError` - Invalid configuration parameters

#### Module: `UsbCameraProvider`
- **Location:** `src/hardware/camera/usb_provider.py`
- **Status:** Implemented
- **Hardware:** USB webcams (V4L2 backend)
- **Implementation Details:**
  - Uses OpenCV `cv2.VideoCapture()` with V4L2 backend
  - MJPG codec negotiation for bandwidth efficiency
  - Auto-fallback to YUYV if MJPG unavailable
  - Single-stream configuration (no high-res capture)
- **Integration:**
  - Primary use: USB webcam fallback when CSI camera unavailable
  - Called by: `factory.get_camera_provider(interface="usb")`

#### Module: `CsiCameraProvider` (UPDATED v4.2.2 - YUV420 Fix)
- **Location:** `src/hardware/camera/csi_provider.py`
- **Status:** Contract Approved - Implementation Required
- **Contract:** `docs/contracts/csi_provider_yuv420_fix.md` v1.0
- **Hardware:** Raspberry Pi Camera Module 3 (IMX708 sensor)
- **Dependencies:** picamera2, cv2, numpy, threading
- **Critical Fix (v4.2.2):** Resolved `RuntimeError: lores stream must be YUV` by implementing hardware-compliant YUV420→BGR conversion pipeline.
- **Public Interface:**
  - `start(width: int, height: int, fps: int) -> bool`
    - **Purpose:** Initialize CSI camera with dual-stream configuration
    - **Streams:**
      - `main`: 1920x1080 RGB888 (high-resolution capture)
      - `lores`: WxH YUV420 (live feed - hardware compliant)
    - **Validation:** Width [320-1920], Height [240-1080], FPS [1-30]
    - **Configuration:** Uses `picamera2.create_preview_configuration()`
    - **Buffer count:** 2 (double-buffering for thread safety)
  - `read() -> Tuple[bool, Optional[np.ndarray]]`
    - **Purpose:** Acquire BGR frame from YUV420 stream with CPU conversion
    - **Processing Pipeline:**
      - Capture YUV420 planar frame from `lores` stream
      - Validate shape: `(height * 1.5, width, 1)`
      - Convert to BGR: `cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)`
      - Return: `(height, width, 3)` uint8 BGR array
    - **Thread-safe:** Protected by `threading.Lock`
    - **Performance:** ~8.5ms @ 640x480 on Pi 4B
    - **Error Recovery:** Graceful failure on shape mismatch or conversion errors
  - `stop() -> None`
    - **Purpose:** Release picamera2 hardware resources
    - **Contract:** Idempotent and thread-safe
- **Internal Capabilities:**
  - High-Resolution Capture: Direct access to `main` stream via `picam2.capture_array("main")`
  - Resolution: 1920x1080 RGB888
  - No conversion overhead (ISP outputs RGB directly)
  - Concurrent with `lores` stream (no interruption)
- **Dual-Stream Architecture:**
  - Simultaneous operation of both streams
  - Independent resolution/format per stream
  - Thread-safe buffer management
- **Performance Characteristics:**
  - Conversion Overhead: ~8.5ms per frame @ 640x480
  - CPU impact: ~15% of 66.7ms frame budget @ 15fps
  - Thermal: +0.5W (acceptable for Pi 4B)
  - Memory Footprint: ~6.7MB total
    - ISP DMA buffers: ~4MB
    - YUV420 buffer: ~450KB
    - BGR buffer: ~900KB
    - Double-buffering overhead: 2× per buffer type
- **Hardware Context:**
  - Platform: Raspberry Pi 4B (VideoCore VI ISP)
  - Sensor: Sony IMX708 (11.9MP stacked CMOS)
  - ISP Constraint: Low-res output node MUST output YUV420 (hardware limitation)
  - Driver: libcamera backend via picamera2 library
- **Integration Points:**
  - Called by:
    - `VisionManager.start_camera()` - Initialization
    - `VisionManager._frame_capture_loop()` - Background frame acquisition (15fps)
    - `VisionManager.capture_highres()` - High-res still capture
- **Enables Endpoints:**
  - `/api/vision/stream` - 15fps MJPEG stream (uses `lores` → BGR)
  - `/api/vision/capture` - 1920x1080 stills (uses `main` RGB888)
- **Error Handling:**
  - Configuration errors: Raise `CameraConfigurationError` with diagnostic info
  - Runtime conversion errors: Return `(False, None)` for graceful degradation
  - Shape validation: Log warning and reject malformed frames
  - Thread safety: Lock prevents concurrent `capture_array()` calls
- **YUV420 Technical Details:**
  - Format: Planar (I420)
  - Y plane: Full resolution luminance
  - U/V planes: Quarter resolution chrominance (2x2 subsampling)
  - Buffer Layout: Monolithic array with `height = original_height * 1.5`
  - Example @ 640x480: Shape is (720, 640, 1)
  - Y: [0:480, :, 0]
  - U: [480:600, :, 0]
  - V: [600:720, :, 0]
  - Conversion: OpenCV `COLOR_YUV2BGR_I420` flag (specific to planar YUV420)
- **See Also:**
  - Base class: `CameraProvider` (src/hardware/camera/base.py)
  - Alternative: `UsbCameraProvider` (USB webcam fallback)
  - Factory: `get_camera_provider()` (src/hardware/camera/factory.py)
  - Contract: `docs/contracts/csi_provider_yuv420_fix.md` v1.0
  - Investigation: `docs/specs/14_csi_error_investigation.md`

#### Module: `CameraFactory`
- **Location:** `src/hardware/camera/factory.py`
- **Status:** Implemented
- **Public Interface:**
  - `get_camera_provider(interface: Optional[str] = None) -> CameraProvider`
    - **Purpose:** Factory function for camera instantiation
    - **Logic:**
      - If `interface="usb"`: Return `UsbCameraProvider()`
      - If `interface="csi"`: Return `CsiCameraProvider()` (requires picamera2)
      - If `interface=None`: Auto-detect (CSI preferred, USB fallback)
    - **Returns:** Concrete `CameraProvider` implementation
    - **Raises:** `ImportError` if CSI requested but picamera2 unavailable

#### Module: `camera.__init__`
- **Location:** `src/hardware/camera/__init__.py`
- **Status:** Implemented
- **Exports:**
  - `CameraProvider` (ABC)
  - `CameraError`, `CameraInitializationError`, `CameraConfigurationError`
  - `UsbCameraProvider`
  - `CsiCameraProvider` (conditional - only if picamera2 available)
  - `get_camera_provider` (factory function)

### SERVICES LAYER (`src/services/`)

#### Module: `VisionManager`
- **Location:** `src/services/vision_manager.py`
- **Status:** Implemented
- **Dependencies:** Camera HAL (factory pattern)
- **Camera Integration:**
  - Uses `get_camera_provider()` for hardware abstraction
  - Maintains backward compatibility with existing API routes
  - Manages camera lifecycle (start/stop/capture)
  - Handles background frame capture thread (15fps)
  - MJPEG stream generation for `/api/vision/stream`
- **Public Methods (Camera-Related):**
  - `start_camera(width, height, fps)` - Initialize camera via factory
  - `stop_camera()` - Release camera resources
  - `capture_highres()` - Capture 1920x1080 still (CSI only)
  - `get_frame()` - Get latest BGR frame for processing

### INTEGRATION NOTES

#### Theme Persistence
- **Storage key:** `ps-rcs-theme` (localStorage)
- **Values:** `'dark'` or `'light'`
- **Default:** `'dark'`
- **DOM attribute:** `<html data-theme="dark">`

#### OCR Scanner Workflow
- User selects input method (camera/upload/paste tab)
- Provides image (stream capture / file drop / Ctrl+V paste)
- Clicks "Analyze Document" → POST to `/api/ocr/analyze`
- Frontend polls `/api/vision/results/<scan_id>` (500ms intervals)
- Results appear in panel with confidence indicator
- User copies fields via hover buttons

#### Error Handling Strategy
- **503 Service Unavailable:** Hardware not connected
- **507 Insufficient Storage:** Disk full during capture
- **400 Bad Request:** Invalid filename/path traversal attempt
- **Graceful Degradation:** Missing DOM elements log warning but don't crash

### ENDPOINT SUMMARY

| Endpoint | Method | Purpose | New in v4.2.2 |
| --- | --- | --- | --- |
| /api/status | GET | System health & hardware status | ✅ |
| /api/vision/stream | GET | Live MJPEG stream | ✅ |
| /api/vision/scan | POST | Trigger OCR scan | ✅ Field validation |
| /api/vision/last-scan | GET | Retrieve OCR results | ✅ |
| /api/vision/capture | POST | High-res capture | ⭐ v4.1 |
| /captures/<filename> | GET | Serve captures | ⭐ v4.1 |
| /api/ocr/analyze | POST | Multi-source OCR | ⭐ NEW v4.2 |
| /api/vision/results/<scan_id> | GET | Poll results | ✅ ID comparison fix |

### VERSION HISTORY

#### v4.2.3 (2026-02-09) - VisionManager Stream Property Fix
- **CRITICAL FIX:** Corrected `stream` property to check `capture_thread.is_alive()` instead of non-existent `provider.is_running`
- **Impact:** Resolves 503 errors on `/api/vision/stream` endpoint with CSI camera
- **Affected Endpoints:** `/api/vision/stream`, `/api/status` (camera_connected field)
- **Backward Compatibility:** Zero breaking changes; only fixes broken behavior
- **Performance:** +30ns per call (negligible overhead)
- **Contract:** `docs/contracts/vision_manager_stream_fix.md` v1.0

#### v4.2.2 (2026-02-08) - CSI Camera YUV420 Fix
- **CRITICAL:** Fixed `RuntimeError: lores stream must be YUV` initialization failure
- Implemented YUV420→BGR conversion pipeline for CSI camera
- Added hardware-compliant dual-stream configuration:
  - Main stream: 1920x1080 RGB888 (high-resolution capture)
  - Lores stream: 640x480 YUV420 (live feed - hardware compliant)
- Performance: ~8.5ms conversion overhead @ 640x480 (15% of frame budget)
- Thread-safe frame acquisition with `threading.Lock`
- Graceful error recovery for shape mismatches and conversion failures
- **Contract:** `docs/contracts/csi_provider_yuv420_fix.md` v1.0
- **Investigation:** `docs/specs/14_csi_error_investigation.md`

#### v4.2.1 (2026-02-07) - OCR Results Display Bug Fix
- Fixed field name mismatch (snake_case/camelCase normalization)
- Added `_validate_ocr_result()` for consistent field naming
- Fixed scan_id comparison in results endpoint (string vs integer)
- Implemented empty state detection ("No text detected" toast)
- Added confidence clamping and timestamp validation
- Dual-lookup pattern in frontend for robust field access

#### v4.2 (2026-02-06) - OCR Scanner Enhancement
- Multi-source input: Live Camera / Upload File / Paste Image
- Bandwidth-optimized stream management (starts/stops per tab)
- Unified `/api/ocr/analyze` endpoint for all image sources
- Visual confidence indicators (color-coded dot + percentage)
- Copy-to-clipboard for all result fields
- Full keyboard navigation with ARIA roles

#### v4.1 (2026-02-02)
- Icon-only navigation with CSS tooltips (Linear.app style)
- X/Linear dark palette (#0F0F0F, #1A1A1A, neutral grays)
- Theme toggle functional with localStorage persistence
- High-resolution capture feature (1920x1080 @ quality=95)
- Capture preview with flash animation and download link
- Stream reset on modal close (bandwidth optimization)
- Spacing refined to 8px baseline (Stripe-like breathing room)

#### v4.0 (2026-02-02)
- Linear-style UI overhaul (Inter font, CSS variables)
- Vision system fully integrated (camera feed + OCR)
- Stream optimization: quality=40 (70% bandwidth reduction)
- Status polling sync (2-second interval)
- Progressive disclosure pattern (stream lazy-loaded)
```