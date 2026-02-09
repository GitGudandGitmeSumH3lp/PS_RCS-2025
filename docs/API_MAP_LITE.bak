

```markdown:docs/API_MAP_LITE.md
# API MAP (LITE)
*Last Updated: 2026-02-07*
*Source: src/api/server.py*
*Version: 4.2.1 (Bug Fix)*


## CORE ENDPOINTS

### GET /api/status
**Purpose:** System health check and hardware status polling  
**Method:** GET  
**Polling:** DashboardCore polls every 2 seconds

**Response:**
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

**Field Descriptions:**
- `camera_connected`: Boolean indicating camera hardware status (NEW v4.0)

---

### GET /api/vision/stream
**Purpose:** MJPEG video stream for live camera feed  
**Constraints:**
- Quality: 40 (server-enforced optimization)
- Resolution: 320x240
- FPS: ~15
- Bandwidth: ~50-70 KB/s

---

### POST /api/vision/scan
**Purpose:** Trigger OCR scan on current camera frame  
**Response (Success):**
```json
{
  "success": true,
  "scan_id": 140285763291232,
  "status": "processing"
}
```

**Critical Change (v4.2.1):**  
Callback now injects `scan_id` into result AND validates field names:
```python
result['scan_id'] = scan_id
result = self._validate_ocr_result(result)  # Normalizes to snake_case
```

---

### GET /api/vision/last-scan
**Purpose:** Retrieve most recent OCR scan results

---

### POST /api/vision/capture (v4.1)
**Purpose:** Capture high-resolution photo for archival/OCR  
**Response (Success):**
```json
{
  "success": true,
  "filename": "capture_20260207_143045.jpg",
  "download_url": "/captures/capture_20260207_143045.jpg",
  "resolution": "1920x1080",
  "timestamp": "2026-02-07T14:30:45Z"
}
```
**Constraints:**
- Resolution: 1920x1080 (attempted), fallback to 640x480
- Quality: 95 (high fidelity for OCR)
- Storage: Auto-cleanup after 50 images
- Location: `data/captures/`

---

### GET /captures/<filename> (v4.1)
**Purpose:** Serve captured high-resolution images  
**Security:**
- Filename sanitized (no path traversal)
- Restricted to `.jpg`/`.jpeg` only
- Absolute path resolution (prevents 404 errors)

---

### POST /api/ocr/analyze (NEW v4.2)
**Purpose:** Analyze image from ANY source (camera/upload/paste)  
**Accepts:**
- `multipart/form-data` with `image` file (upload)
- JSON with `image_data` base64 string (paste)
- URL from captured frame (camera)

**Response (Success):**
```json
{
  "success": true,
  "scan_id": 548275392208,
  "status": "processing",
  "message": "Image submitted for analysis"
}
```

**Critical Changes (v4.2.1):**
1. **Field Validation:** Callback normalizes all field names to snake_case:
   ```python
   result = self._validate_ocr_result(result)
   # Returns: {tracking_id, order_id, rts_code, district, confidence, timestamp}
   ```
2. **Confidence Clamping:** Values clamped to [0.0, 1.0] range
3. **Timestamp Validation:** Ensures ISO 8601 string format
4. **Empty Field Handling:** Missing fields set to `None` (not empty string)

**Constraints:**
- File size: Max 5MB
- Valid types: PNG, JPG, WEBP
- Preprocessing: Resized to 640x480 before OCR
- Polling: Results available via `/api/vision/results/<scan_id>`

---

### GET /api/vision/results/<scan_id> (v4.2.1)
**Purpose:** Poll OCR results with robust ID handling  
**Response (Completed):**
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

**Critical Fix (v4.2.1):**  
Handles both string and integer `scan_id` comparisons:
```python
state_scan_id = str(scan_data['scan_id'])
requested_scan_id = str(scan_id)
if state_scan_id == requested_scan_id:  # Prevents timeout
    return jsonify({'status': 'completed', 'data': scan_data})
```
---

### 5. CAMERA HAL LAYER (`src/hardware/camera/`)
*   `src/hardware/camera/base.py`
    - CameraProvider (ABC) - Abstract base class for camera hardware
    - CameraError, CameraInitializationError, CameraConfigurationError - Exception hierarchy
*   `src/hardware/camera/usb_provider.py`
    - UsbCameraProvider - USB webcam provider (OpenCV V4L2) with MJPG negotiation
*   `src/hardware/camera/csi_provider.py`
    - CsiCameraProvider - Raspberry Pi Camera Module 3 provider (picamera2) [Optional import]
*   `src/hardware/camera/factory.py`
    - get_camera_provider(interface: Optional[str] = None) → CameraProvider - Factory function
*   `src/hardware/camera/__init__.py`
    - Package exports with conditional CsiCameraProvider

### 6. SERVICES LAYER (`src/services/`)
*   `src/services/vision_manager.py` - VisionManager with Camera HAL integration
    - Uses factory pattern for USB/CSI camera selection
    - Maintains backward compatibility with existing API
---

## INTEGRATION NOTES

### Theme Persistence
- Storage key: `ps-rcs-theme` (localStorage)
- Values: `'dark'` or `'light'`
- Default: `'dark'`
- DOM attribute: `<html data-theme="dark">`

### OCR Scanner Workflow
1. **User selects input method** (camera/upload/paste tab)
2. **Provides image** (stream capture / file drop / Ctrl+V paste)
3. **Clicks "Analyze Document"** → POST to `/api/ocr/analyze`
4. **Frontend polls** `/api/vision/results/<scan_id>` (500ms intervals)
5. **Results appear** in panel with confidence indicator
6. **User copies fields** via hover buttons

### Error Handling Strategy
- **503 Service Unavailable:** Hardware not connected
- **507 Insufficient Storage:** Disk full during capture
- **400 Bad Request:** Invalid filename/path traversal attempt
- **Graceful Degradation:** Missing DOM elements log warning but don't crash

---

## ENDPOINT SUMMARY

| Endpoint | Method | Purpose | New in v4.2.1 |
|----------|--------|---------|---------------|
| `/api/status` | GET | System health & hardware status | ✅ |
| `/api/vision/stream` | GET | Live MJPEG stream | ✅ |
| `/api/vision/scan` | POST | Trigger OCR scan | ✅ Field validation |
| `/api/vision/last-scan` | GET | Retrieve OCR results | ✅ |
| `/api/vision/capture` | POST | **High-res capture** | ⭐ v4.1 |
| `/captures/<filename>` | GET | **Serve captures** | ⭐ v4.1 |
| `/api/ocr/analyze` | POST | **Multi-source OCR** | ⭐ NEW v4.2 |
| `/api/vision/results/<scan_id>` | GET | **Poll results** | ✅ ID comparison fix |

---

## VERSION HISTORY

### v4.2.1 (2026-02-07) - OCR Results Display Bug Fix
- Fixed field name mismatch (snake_case/camelCase normalization)
- Added `_validate_ocr_result()` for consistent field naming
- Fixed scan_id comparison in results endpoint (string vs int)
- Implemented empty state detection ("No text detected" toast)
- Added confidence clamping and timestamp validation
- Dual-lookup pattern in frontend for field access

### v4.2 (2026-02-06) - OCR Scanner Enhancement
- Multi-source input (Live Camera / Upload File / Paste Image)
- Bandwidth-optimized stream management (starts/stops per tab)
- Unified `/api/ocr/analyze` endpoint for all image sources
- Visual confidence indicators (color-coded dot + percentage)
- Copy-to-clipboard for all result fields
- Full keyboard navigation with ARIA roles

### v4.1 (2026-02-02)
- Icon-only navigation with CSS tooltips (Linear.app style)
- X/Linear dark palette (#0F0F0F, #1A1A1A, neutral grays)
- Theme toggle functional with localStorage persistence
- High-resolution capture feature (1920x1080 @ quality=95)
- Capture preview with flash animation and download link
- Stream reset on modal close (bandwidth optimization)
- Spacing refined to 8px baseline (Stripe-like breathing room)

### v4.0 (2026-02-02)
- Linear-style UI overhaul (Inter font, CSS variables)
- Vision system fully integrated (camera feed + OCR)
- Stream optimization: quality=40 (70% bandwidth reduction)
- Status polling sync (2-second interval)
- Progressive disclosure pattern (stream lazy-loaded)
```
