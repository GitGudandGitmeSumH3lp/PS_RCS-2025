
---

### UPDATED API_MAP_LITE.md

```markdown
# API MAP (LITE)
Last Updated: 2026-02-20
Source: `src/api/server.py`
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

#### GET /captures/ (v4.1)
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
  - Field Validation: Callback normalizes all field names to snake_case
  - Confidence Clamping: Values clamped to [0.0, 1.0] range
  - Timestamp Validation: Ensures ISO 8601 string format
  - Empty Field Handling: Missing fields set to `None` (not empty string)
- **Constraints:**
  - File size: Max 5MB
  - Valid types: PNG, JPG, WEBP
  - Preprocessing: Resized to 640x480 before OCR
  - Polling: Results available via `/api/vision/results/<scan_id>`

#### POST /api/ocr/analyze_batch (NEW v4.2.3)
- **Purpose:** Process multiple uploaded receipt images in one request.
- **Request:** `multipart/form-data` with field `images` containing one or more image files.
- **Limits:** Maximum 10 files, each ≤5MB.
- **Response:** JSON array. Each element corresponds to a file (same order) and has the same structure as the single‑file endpoint (`/api/ocr/analyze`). Failed files contain `{"success": false, "error": "reason"}`.
- **Processing:** **Sequential (one at a time)** to prevent memory exhaustion on Raspberry Pi.
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

### SERVICES LAYER (`src/services/`)

#### Module: `VisionManager`
**Location:** `src/services/vision_manager.py`
**Status:** Implemented
**Dependencies:** Camera HAL (factory pattern)
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

#### Module: `FlashExpressOCR`
**Location:** `src/services/ocr_processor.py`
**Status:** Implemented
**Contract:** `docs/contracts/ocr_flash_express.md` v1.0
**Public Interface:**
- `__init__(use_paddle_fallback: bool = False, confidence_threshold: float = 0.85, tesseract_config: str = '--oem 1 --psm 6 -l eng', debug_align: bool = False, enable_correction: bool = False, correction_dict_path: Optional[str] = None, use_anchor_extraction: bool = True) -> None`
  - **Purpose:** Initialize Flash Express OCR processor.
  - **New:**
    - `enable_correction` – toggles post-processing correction using dictionary.
    - `correction_dict_path` – path to `ground_truth_parcel_gen.json`.
    - `use_anchor_extraction` – (v4.2.3) If True, uses anchor-phrase extraction; if False, reverts to zone-based.
  - **Raises:** `ImportError` (PaddleOCR missing), `ValueError` (invalid threshold)
- `process_frame(bgr_frame: np.ndarray, scan_id: Optional[int] = None) -> Dict[str, Any]`
  - **Purpose:** Process camera frame for Flash Express receipt field extraction.
  - **Returns:** Dict with success, scan_id, fields (11 receipt fields), raw_text, engine, processing_time_ms.
  - **When correction enabled:** Fields are passed through `FlashExpressCorrector`.
  - **Target:** < 4000ms total processing time on Pi 4B.
**Dependencies:**
- Imports: cv2, pytesseract, numpy, re, datetime, typing, dataclasses, threading, logging
- Optional: paddleocr (fallback engine)
- New: `FlashExpressCorrector` (if correction enabled)
- Optional: `pyzbar` (for barcode decoding)

#### Module: `ReceiptDatabase`
**Location:** `src/services/receipt_database.py`
**Status:** Designed (pending implementation)
**Contract:** `docs/contracts/ocr_flash_express.md` v1.0
**Public Interface:**
- `store_scan(scan_id: int, fields: Dict, raw_text: str, confidence: float, engine: str) -> bool`
  - **Purpose:** Persist OCR scan results to SQLite database.
  - **Returns:** True on success.
**Dependencies:**
- Imports: sqlite3, typing
- Uses: `DatabaseManager.get_connection()`
- Called by: `vision_scan_route()`, `ocr_analyze_route()`

#### Module: `FlashExpressCorrector` (NEW)
**Location:** `src/services/ocr_correction.py`
**Status:** Implemented
**Purpose:** Post-processing correction layer for Flash Express OCR fields using a ground-truth dictionary and fuzzy matching.
**Public Interface:**
- `__init__(dictionary_path: str, fuzzy_threshold: float = 80.0) -> None`
  - **Loads the Flash Express dictionary from `ground_truth_parcel_gen.json`.**
- `correct_barangay(text: str) -> str`
  - **Fuzzy-match against known barangays.**
- `correct_district(barangay: str, text: str) -> str`
  - **Given a barangay, match against its valid districts.**
- `validate_tracking_number(text: str) -> Tuple[bool, str]`
  - **Validate against regex `^FE\d{10}$`; attempt OCR character correction.**
- `validate_phone(text: str) -> Tuple[bool, str]`
  - **Validate against regex `^\d{12}$`; attempt OCR character correction.**
- `correct_rider_code(text: str) -> str`
  - **Match against enumerated `riderCodes` list.**
- `correct_sort_code(text: str) -> str`
  - **Match against enumerated `sortCode` list.**
- `derive_quantity_from_weight(weight: int) -> int`
  - **Compute quantity using `max(1, weight // 500)`.**
- `clean_address(text: str) -> str`
  - **Remove trailing garbage characters (e.g., `) 1, iy`).**
**Dependencies:**
- Imports: json, re, typing, rapidfuzz (or fuzzywuzzy)
- Dictionary file: `data/dictionaries/ground_truth_parcel_gen.json`
- Called internally by `FlashExpressOCR` when correction is enabled.

#### Module: `ExtractionGuide` (NEW)
**Location:** `src/services/extraction_guide.py`
**Status:** Designed
**Purpose:** Provides dictionary‑aware helper functions for OCR extraction.
**Public Functions:**
- `fix_ocr_digits(text: str) -> str`
  - **Purpose:** Applies common OCR digit/letter substitutions.
- `validate_and_fix_field(candidate: str, field_type: str) -> Tuple[Optional[str], bool]`
  - **Purpose:** Validates a field against its regex pattern, fixes characters, returns corrected value.
- `validate_code(candidate: str, code_type: str, threshold: float = 80.0) -> Optional[str]`
  - **Purpose:** Matches a candidate rider/sort code against enumerated list.
- `score_address_line(line: str, barangay_threshold: float = 75.0, place_threshold: float = 85.0) -> float`
  - **Purpose:** Returns a score [0,1] indicating how likely the line is part of an address.
- `cross_validate_weight_quantity(weight: Optional[int], quantity: Optional[int]) -> Tuple[Optional[int], bool]`
  - **Purpose:** Checks consistency using weight/500 formula.
- `score_name_line(line: str, threshold: float = 85.0) -> float`
  - **Purpose:** Scores a line against known first/last names.

#### Module: `FlashExpressOCRPanel`
**Location:** `frontend/static/js/ocr-panel.js`
**Status:** Designed (not yet implemented)
**Public Interface:**
- `constructor()`
  - **Purpose:** Initialize OCR panel with necessary elements and event listeners
- `openModal()`
  - **Purpose:** Open the OCR modal and initialize the camera stream
- `closeModal()`
  - **Purpose:** Close the OCR modal and stop the camera stream
- `switchTab(tabId: string)`
  - **Purpose:** Switch between camera, upload, and paste tabs
- `analyzeDocument()`
  - **Purpose:** Trigger OCR analysis on the selected image
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
- **Enables:**
  - Real-time camera stream for OCR
  - Image upload for OCR
  - Clipboard paste for OCR
  - Result polling and display
  - Confidence indicators
  - Scan history management

#### Module: `Batch Results Display`
**Location:** `frontend/static/js/ocr-panel.js`
**Status:** Designed (not yet implemented)
**Contract:** `docs/contracts/batch-results-theme-integration.md` v1.0
**Public Interface:**
- `_displayBatchResults(results: Array<Object>) -> void`
  - Purpose: Displays batch OCR results in theme-compliant card grid
  - See contract for full specification
- `_createBatchResultCard(result: Object, index: number) -> HTMLElement`
  - Purpose: Generates single batch result card with field extraction
  - Uses `_extractFieldsFromData()` for field mapping
**Dependencies:**
- Requires: `_extractFieldsFromData()`, `_showToast()`, `navigator.clipboard`
- Theme Variables: All CSS custom properties from `system_style.md`
- Called by: Batch upload polling completion handler
**Theme Compliance:**
- Uses CSS variables exclusively (no hardcoded colors)
- Respects `data-theme` attribute changes
- Implements bento grid layout with glass effect

### Multi-Courier Parcel Generator

#### Module: `core/courier-registry`
**Location:** `parcel_generator/core/courier-registry.js`
**Status:** Designed (not yet implemented)
**Contract:** `CONTRACT_MULTI_COURIER_GENERATOR.md` v1.0 - Section 3.4

**Public Interface:**
- `registerCourier(courierConfig: CourierConfig) -> void`
  - **Purpose:** Register a new courier configuration in the system
  - **Validates config structure before registration**
- `getCourier(courierId: string) -> CourierConfig`
  - **Purpose:** Retrieve courier configuration by ID
  - **Throws error if courier not found**
- `getAllCourierIds() -> string[]`
  - **Purpose:** Get array of all registered courier IDs
- `getAllCouriers() -> CourierConfig[]`
  - **Purpose:** Get all registered courier configurations
- `hasCourier(courierId: string) -> boolean`
  - **Purpose:** Check if courier is registered
- `validateCourierConfig(courierConfig: CourierConfig) -> ValidationResult`
  - **Purpose:** Validate courier configuration structure

**Dependencies:**
- No external dependencies
- Called by: `label-engine`, `label-renderer`, `app.js`

---

#### Module: `core/label-engine`
**Location:** `parcel_generator/core/label-engine.js`
**Status:** Designed (not yet implemented)
**Contract:** `CONTRACT_MULTI_COURIER_GENERATOR.md` v1.0 - Section 3.2

**Public Interface:**
- `setActiveCourier(courierId: string) -> void`
  - **Purpose:** Set the active courier for label generation
- `generateSingleLabel(overrides?: Object) -> LabelData`
  - **Purpose:** Generate a single label with optional field overrides
  - **Returns complete label data with ground truth**
- `generateBatch(count: number, options?: Object) -> LabelData[]`
  - **Purpose:** Generate multiple labels in batch
  - **Supports random courier selection per label**
- `getActiveCourier() -> CourierConfig`
  - **Purpose:** Get current active courier configuration
- `validateLabel(labelData: LabelData) -> ValidationResult`
  - **Purpose:** Validate label data against courier rules

**Dependencies:**
- Imports: `CourierRegistry`
- Called by: `app.js`, UI event handlers

---

#### Module: `core/label-renderer`
**Location:** `parcel_generator/core/label-renderer.js`
**Status:** Designed (not yet implemented)
**Contract:** `CONTRACT_MULTI_COURIER_GENERATOR.md` v1.0 - Section 3.3

**Public Interface:**
- `renderLabel(labelData: LabelData, courierConfig: CourierConfig) -> Promise<string>`
  - **Purpose:** Render label to DOM, returns element ID
- `renderBatch(labelDataArray: LabelData[], courierRegistry: CourierRegistry) -> Promise<string[]>`
  - **Purpose:** Render multiple labels, returns array of element IDs
- `captureAsImage(labelElementId: string, options?: Object) -> Promise<Blob>`
  - **Purpose:** Capture label as PNG/JPG image blob
- `downloadAsImage(labelElementId: string, filename?: string, format?: string) -> Promise<void>`
  - **Purpose:** Trigger browser download of label as image
- `downloadAsPDF(labelElementId: string, filename?: string) -> Promise<void>`
  - **Purpose:** Trigger browser download of label as PDF
- `clearAll() -> void`
  - **Purpose:** Remove all rendered labels from DOM
- `removeLabel(labelElementId: string) -> void`
  - **Purpose:** Remove specific label from DOM

**Dependencies:**
- Imports: `html2canvas`, `JsBarcode`, `QRCode`, `jsPDF`
- Called by: `ground-truth-exporter`, UI event handlers

---

#### Module: `core/ground-truth-exporter`
**Location:** `parcel_generator/core/ground-truth-exporter.js`
**Status:** Designed (not yet implemented)
**Contract:** `CONTRACT_MULTI_COURIER_GENERATOR.md` v1.0 - Section 3.5

**Public Interface:**
- `generateGroundTruth(labelData: LabelData, options?: Object) -> GroundTruthData`
  - **Purpose:** Generate ground truth JSON for a single label
- `exportAsJSON(groundTruth: GroundTruthData, filename?: string) -> Promise<void>`
  - **Purpose:** Export ground truth as JSON file download
- `bundleAndDownload(labelDataArray: LabelData[], options?: Object) -> Promise<void>`
  - **Purpose:** Bundle multiple labels with ground truth into ZIP
  - **Includes images, JSON files, and manifest**
- `generateManifest(labelDataArray: LabelData[]) -> BatchManifest`
  - **Purpose:** Generate batch manifest with statistics

**Dependencies:**
- Imports: `LabelRenderer`, `JSZip`
- Called by: UI event handlers (batch download)

---

#### Module: `couriers/flash-express`
**Location:** `parcel_generator/couriers/flash-express.js`
**Status:** Designed (not yet implemented)
**Contract:** `CONTRACT_MULTI_COURIER_GENERATOR.md` v1.0 - Section 4.1

**Public Interface:**
- `FLASH_EXPRESS_CONFIG: CourierConfig`
  - **Complete Flash Express courier configuration**
  - **Includes branding, generators, layout, validation rules**

**Dependencies:**
- Imports: `CourierRegistry` (for registration)
- Called by: `app.js` (on initialization)

---

#### Module: `couriers/shopee-spx`
**Location:** `parcel_generator/couriers/shopee-spx.js`
**Status:** Designed (not yet implemented)
**Contract:** `CONTRACT_MULTI_COURIER_GENERATOR.md` v1.0 - Section 4.2

**Public Interface:**
- `SHOPEE_SPX_CONFIG: CourierConfig`
  - **Complete Shopee SPX courier configuration**
  - **Includes branding, generators, layout, validation rules**

**Dependencies:**
- Imports: `CourierRegistry` (for registration)
- Called by: `app.js` (on initialization)

---

#### Module: `utils/data-generators`
**Location:** `parcel_generator/utils/data-generators.js`
**Status:** Designed (not yet implemented)
**Contract:** Referenced in Section 5

**Public Interface:**
- `generateRandomName() -> string`
  - **Purpose:** Generate random Filipino/international name
- `generateRandomAddress(city?: string, barangay?: string) -> AddressData`
  - **Purpose:** Generate random address from dictionaries
- `generateRandomWeight(min?: number, max?: number) -> number`
  - **Purpose:** Generate random weight in grams
- `generateRandomQuantity(weight: number) -> number`
  - **Purpose:** Calculate quantity based on weight

**Dependencies:**
- Imports: Address data from `data/*.json`
- Called by: Courier generators, `label-engine`

---

#### Module: `utils/dictionary-extractor`
**Location:** `parcel_generator/utils/dictionary-extractor.js`
**Status:** Designed (not yet implemented)
**Contract:** `CONTRACT_MULTI_COURIER_GENERATOR.md` v1.0 - Section 3.6

**Public Interface:**
- `extractDictionaries(labelDataArray: LabelData[], fieldNames: string[]) -> ExtractedDictionaries`
  - **Purpose:** Extract unique values for specified fields
- `exportDictionariesAsJSON(dictionaries: ExtractedDictionaries, filename?: string) -> Promise<void>`
  - **Purpose:** Export dictionaries as JSON file
- `generatePythonDict(dictionaries: ExtractedDictionaries) -> string`
  - **Purpose:** Generate Python dict literal for backend integration

**Dependencies:**
- No external dependencies
- Called by: UI event handlers (after batch generation)

---

#### Module: `utils/barcode-utils`
**Location:** `parcel_generator/utils/barcode-utils.js`
**Status:** Designed (not yet implemented)
**Contract:** Referenced in Section 3.3

**Public Interface:**
- `generateBarcode(elementId: string, value: string, options?: Object) -> void`
  - **Purpose:** Generate Code 128 barcode in specified DOM element
- `generateQRCode(elementId: string, value: string, options?: Object) -> void`
  - **Purpose:** Generate QR code in specified DOM element

**Dependencies:**
- Imports: `JsBarcode`, `QRCode` (from CDN)
- Called by: `label-renderer`, courier templates

### CAMERA HAL LAYER (`src/hardware/camera/`)

#### Module: `CameraProvider` (Abstract Base Class)
**Location:** `src/hardware/camera/base.py`
**Status:** Implemented
**Type:** Abstract Base Class (ABC)
**Purpose:** Defines hardware-agnostic camera interface contract for VisionManager.
**Public Interface:**
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

#### Module: `UsbCameraProvider`
**Location:** `src/hardware/camera/usb_provider.py`
**Status:** Implemented
**Hardware:** USB webcams (V4L2 backend)
**Implementation Details:**
- Uses OpenCV `cv2.VideoCapture()` with V4L2 backend
- MJPG codec negotiation for bandwidth efficiency
- Auto-fallback to YUYV if MJPG unavailable
- Single-stream configuration (no high-res capture)
**Integration:**
- Primary use: USB webcam fallback when CSI camera unavailable
- Called by: `factory.get_camera_provider(interface="usb")`

#### Module: `CsiCameraProvider` (UPDATED v4.2.2 - YUV420 Fix)
**Location:** `src/hardware/camera/csi_provider.py`
**Status:** Contract Approved - Implementation Required
**Contract:** `docs/contracts/csi_provider_yuv420_fix.md` v1.0
**Hardware:** Raspberry Pi Camera Module 3 (IMX708 sensor)
**Dependencies:** picamera2, cv2, numpy, threading
**Critical Fix (v4.2.2):** Resolved `RuntimeError: lores stream must be YUV` by implementing hardware-compliant YUV420→BGR conversion pipeline.
**Public Interface:**
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

**Internal Capabilities:**
- **High-Resolution Capture:** Direct access to `main` stream via `picam2.capture_array("main")`
- **Resolution:** 1920x1080 RGB888
- **No conversion overhead (ISP outputs RGB directly)**
- **Concurrent with `lores` stream (no interruption)**
- **Dual-Stream Architecture:**
  - Simultaneous operation of both streams
  - Independent resolution/format per stream
  - Thread-safe buffer management

**Performance Characteristics:**
- **Conversion Overhead:** ~8.5ms per frame @ 640x480
- **CPU impact:** ~15% of 66.7ms frame budget @ 15fps
- **Thermal:** +0.5W (acceptable for Pi 4B)
- **Memory Footprint:** ~6.7MB total
  - **ISP DMA buffers:** ~4MB
  - **YUV420 buffer:** ~450KB
  - **BGR buffer:** ~900KB
  - **Double-buffering overhead:** 2× per buffer type

**Hardware Context:**
- **Platform:** Raspberry Pi 4B (VideoCore VI ISP)
- **Sensor:** Sony IMX708 (11.9MP stacked CMOS)
- **ISP Constraint:** Low-res output node MUST output YUV420 (hardware limitation)
- **Driver:** libcamera backend via picamera2 library

**Integration Points:**
- **Called by:**
  - `VisionManager.start_camera()` - Initialization
  - `VisionManager._frame_capture_loop()` - Background frame acquisition (15fps)
  - `VisionManager.capture_highres()` - High-res still capture
- **Enables Endpoints:**
  - `/api/vision/stream` - 15fps MJPEG stream (uses `lores` → BGR)
  - `/api/vision/capture` - 1920x1080 stills (uses `main` RGB880)

**Error Handling:**
- **Configuration errors:** Raise `CameraConfigurationError` with diagnostic info
- **Runtime conversion errors:** Return `(False, None)` for graceful degradation
- **Shape validation:** Log warning and reject malformed frames
- **Thread safety:** Lock prevents concurrent `capture_array()` calls

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
| /captures/ | GET | Serve captures | ⭐ v4.1 |
| /api/ocr/analyze | POST | Multi-source OCR | ⭐ NEW v4.2 |
| /api/ocr/analyze_batch | POST | Batch OCR | ⭐ NEW v4.2.3 |
| /api/vision/results/<scan_id> | GET | Poll results | ✅ ID comparison fix |

### 📑 VERSION HISTORY

- **v4.2.3 (2026-02-09) - VisionManager Stream Property Fix & Batch OCR**
  - CRITICAL FIX: Corrected `stream` property to check `capture_thread.is_alive()` instead of non-existent `provider.is_alive()`
  - NEW: Added `/api/ocr/analyze_batch` for sequential multi-image processing.
- **v4.2.2 (2026-02-15) - YUV420 Fix**
  - CRITICAL FIX: Resolved `RuntimeError: lores stream must be YUV` by implementing hardware-compliant YUV420→BGR conversion pipeline.
- **v4.2.1 (2026-02-12) - Field Validation and ID Comparison Fix**
  - CRITICAL FIX: Added field validation and ID comparison fix in `vision_manager.py` and `api/server.py`.
- **v4.2.0 (2026-02-09) - OCR Backend Integration**
  - Added OCR endpoints and backend logic.
- **v4.1.0 (2026-02-07) - High-Res Capture and Serve**
  - Added high-resolution capture and serve endpoints.
- **v4.0.0 (2026-02-06) - Initial OCR Integration**
  - Initial OCR integration with basic endpoints.
```

---