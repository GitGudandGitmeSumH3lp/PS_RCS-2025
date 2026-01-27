# FEATURE SPEC: Vision & OCR Subsystem (V4.0)
**Date:** 2025-05-15
**Status:** Feasible
**Target:** `specs/vision_ocr_integration.md`

## 1. THE VISION
*   **User Story:** As a Warehouse Operator, I want to see a live video feed of the sorting area and trigger a "Scan" action that automatically extracts Flash Express shipping details (Tracking, Order ID, RTS Codes) so I don't have to manually enter data.
*   **Success Metrics:**
    *   Camera auto-connects to index 0-9 without manual config.
    *   MJPEG stream renders in Dashboard `<img src="...">` with < 500ms latency.
    *   OCR triggered scan returns structured JSON within 3 seconds.
    *   Validates data against `ENHANCED_LABEL_MODEL` (from legacy `knowledge_base_optimized.py`).

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed.
    *   Uses `threading` for Camera I/O to prevent blocking the Main Event Loop.
    *   Uses `concurrent.futures.ThreadPoolExecutor` for CPU-heavy OCR tasks.
    *   Avoids continuous OCR (CPU killer) in favor of Triggered Action (`/api/vision/scan`).
*   **New Libraries Needed:**
    *   `opencv-python-headless` (or standard `opencv-python`)
    *   `pytesseract` (Requires Tesseract-OCR binary installed on host OS)
    *   `numpy`
*   **Risk Level:** **Medium**.
    *   *Risk:* USB Camera bandwidth issues on Raspberry Pi/Single Board Computers.
    *   *Mitigation:* Force resolution to 640x480 for streaming; capture high-res only for OCR frames if supported.

## 3. ATOMIC TASKS (The Roadmap)

### Phase 1: The Eye (VisionManager)
*   [ ] Create `src/core/vision_manager.py`.
*   [ ] Implement Camera Auto-Discovery (Loop indices 0-9).
*   [ ] Implement threaded `update()` loop to read frames into a shared buffer.
*   [ ] Create `generate_mjpeg()` generator for API streaming.

### Phase 2: The Brain (OCRService)
*   [ ] Create `src/services/ocr_service.py`.
*   [ ] Port `MSER` and `Perspective Correction` logic from legacy `image_preprocessor.py`.
*   [ ] Port `Levenshtein` and `ENHANCED_LABEL_MODEL` from legacy `knowledge_base_optimized.py`.
*   [ ] Implement `extract_data(frame)` using `pytesseract`.

### Phase 3: Integration & API
*   [ ] Update `src/core/state_manager.py` (RobotState) to include `last_scan_result`.
*   [ ] Create API route `GET /api/vision/stream`.
*   [ ] Create API route `POST /api/vision/scan`.
*   [ ] Connect `OCRService` output to `RobotState`.

## 4. INTERFACE SKETCHES

### Module: `src/core/vision_manager.py`

```python
class VisionManager:
    def __init__(self):
        self.stream = None
        self.frame_lock = threading.Lock()
        self.current_frame = None # Stores the latest cv2 image
        self.stopped = False

    def start(self):
        """Auto-discovers camera index (0-9) and starts the capture thread."""
        # Logic: Try cv2.VideoCapture(i) until .isOpened() is true.

    def read(self):
        """Thread-safe access to the latest frame."""
        # returns self.current_frame with lock

    def get_jpeg_stream(self):
        """Generator that yields bytes for MJPEG streaming."""
        # Encodes frame to .jpg and yields as multipart response
```

### Module: `src/services/ocr_service.py`

```python
class OCRService:
    def __init__(self):
        # Load legacy patterns
        self.label_patterns = ENHANCED_LABEL_MODEL 

    def run_scan(self, image):
        """Main entry point. Runs in ThreadPool."""
        # 1. Preprocess
        processed_img = self._legacy_preprocess(image)
        # 2. OCR
        raw_text = pytesseract.image_to_string(processed_img)
        # 3. Parse & Validate
        return self._parse_flash_express_data(raw_text)

    def _legacy_preprocess(self, image):
        """Re-implementation of MSER/Contrast logic from image_preprocessor.py"""
        # Grayscale -> GaussianBlur -> AdaptiveThreshold
        # Optional: PerspectiveTransform if contours found

    def _parse_flash_express_data(self, text):
        """Regex + Fuzzy match against self.label_patterns"""
        # Logic: Look for "TH..." (Tracking) and "RTS" codes.
        # Returns: { "tracking": "TH123...", "order": "...", "district": "..." }
```

## 5. INTEGRATION POINTS

*   **API Layer:**
    *   `api_routes.py` will import `VisionManager` (singleton).
    *   `/api/vision/stream` -> calls `vision_manager.get_jpeg_stream()`.
    *   `/api/vision/scan` -> calls `background_tasks.add_task(ocr_service.run_scan, frame)`.

*   **State Layer:**
    *   `RobotState` schema update:
        ```json
        {
          "vision": {
            "camera_connected": true,
            "last_scan": {
              "timestamp": "ISO8601",
              "tracking_id": "TH012345678",
              "status": "RTS-01"
            }
          }
        }
        ```

## 6. OPEN QUESTIONS
1.  **Tesseract Language:** Do we need Thai language support (`-l tha`) for the destination district, or is English (`-l eng`) sufficient for Tracking IDs and Codes? *Assumption: Start with English for performance.*
2.  **Lighting:** Does the robot have an integrated LED? Image preprocessing (MSER) is sensitive to lighting.
3.  **Barcode Fallback:** Should we add `pyzbar` to decode the barcode if OCR fails? (Highly recommended for Flash Express labels).

---

## POST-ACTION REPORT
✅ **Spec Created:** `specs/vision_ocr_integration.md`
📋 **Next Step:** Review Spec, then Architect will define the Class Contracts.
👉 **Next Agent:** Architect