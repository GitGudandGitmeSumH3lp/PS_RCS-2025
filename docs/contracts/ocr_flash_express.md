✅ **Context verified. Proceeding with Contract Design.**

---

# CONTRACT: Flash Express OCR Integration
**Version:** 1.0  
**Last Updated:** 2026-02-09  
**Status:** Draft  
**Architecture Phase:** 5.1 - Production OCR Enhancement

---

## 1. PURPOSE

Implement production-grade OCR processing for Flash Express parcel receipts, extending the existing VisionManager architecture with specialized receipt field extraction. This module enables automated parsing of thermal-printed receipts into structured data for downstream sorting operations, targeting <4 second processing time on Raspberry Pi 4B hardware.

**Key Capabilities:**
- Flash Express receipt field extraction (tracking ID, order ID, RTS code, buyer info, weight, quantity)
- Thermal print preprocessing pipeline optimized for Pi Camera Module 3
- Integration with existing VisionManager camera HAL
- Fallback OCR engine support (Tesseract primary, PaddleOCR secondary)
- Thread-safe processing compatible with Flask request handlers

---

## 2. PUBLIC INTERFACE

### Class: `FlashExpressOCR`

**Location:** `src/services/ocr_processor.py`

#### Method: `__init__`

**Signature:**
```python
def __init__(
    self,
    use_paddle_fallback: bool = False,
    confidence_threshold: float = 0.85,
    tesseract_config: str = '--oem 1 --psm 6 -l eng'
) -> None:
    """
    Initialize Flash Express OCR processor.
    
    Args:
        use_paddle_fallback: Enable PaddleOCR when Tesseract confidence < threshold
        confidence_threshold: Minimum confidence to accept Tesseract results (0.0-1.0)
        tesseract_config: Tesseract CLI configuration string
    
    Raises:
        ImportError: If PaddleOCR requested but not installed
        ValueError: If confidence_threshold not in [0.0, 1.0]
    """
```

**Behavior Specification:**
- **Input Validation:** 
  - `confidence_threshold` must be in range [0.0, 1.0]
  - If `use_paddle_fallback=True`, verify PaddleOCR import succeeds
- **Processing Logic:**
  - Initialize Tesseract configuration constants
  - Compile regex patterns for field extraction (tracking ID, order ID, RTS code, etc.)
  - If fallback enabled, lazy-load PaddleOCR instance (defer GPU allocation)
- **Output Guarantee:** Instance ready to process frames
- **Side Effects:** 
  - PaddleOCR instantiation (~2-3 seconds on first call if enabled)
  - No file I/O or network calls

**Error Handling:**
- **Invalid threshold:** Raise `ValueError` with message "confidence_threshold must be between 0.0 and 1.0, got {value}"
- **Missing PaddleOCR:** Raise `ImportError` with message "PaddleOCR requested but not installed. Run: pip install paddleocr --break-system-packages"

**Performance Requirements:**
- Time Complexity: O(1) - initialization only
- Space Complexity: O(1) - config storage only (~500MB if PaddleOCR loaded)

---

#### Method: `process_frame`

**Signature:**
```python
def process_frame(
    self,
    bgr_frame: np.ndarray,
    scan_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Process camera frame for Flash Express receipt extraction.
    
    Args:
        bgr_frame: (H, W, 3) BGR uint8 array from VisionManager.get_frame()
        scan_id: Optional scan identifier for result tracking
    
    Returns:
        Dictionary with structure:
        {
            'success': bool,
            'scan_id': int,
            'fields': {
                'tracking_id': Optional[str],      # FE1234567890
                'order_id': Optional[str],         # FE12345678J12345
                'rts_code': Optional[str],         # FEX-BUL-SJDM-TKO1-GY22
                'rider_id': Optional[str],         # GY22
                'buyer_name': Optional[str],       # James Flores
                'buyer_address': Optional[str],    # Full Philippine address
                'weight_g': Optional[int],         # Weight in grams
                'quantity': Optional[int],         # Package quantity
                'payment_type': Optional[str],     # COD/Paid/Prepaid
                'confidence': float,               # 0.0-1.0
                'timestamp': str                   # ISO 8601
            },
            'raw_text': str,                       # Full OCR output
            'engine': str,                         # 'tesseract' or 'paddle'
            'processing_time_ms': int
        }
    
    Raises:
        ValueError: If bgr_frame is not 3-channel BGR uint8 array
        RuntimeError: If both OCR engines fail
    """
```

**Behavior Specification:**
- **Input Validation:**
  - Verify `bgr_frame.ndim == 3` and `bgr_frame.shape[2] == 3`
  - Verify `bgr_frame.dtype == np.uint8`
  - Generate `scan_id` if not provided (use `id(bgr_frame)`)
- **Processing Logic:**
  1. Start performance timer
  2. Call `_preprocess_thermal_receipt(bgr_frame)` → grayscale binary image
  3. Call `_ocr_tesseract(preprocessed)` → (text, confidence)
  4. If confidence < threshold AND fallback enabled: Call `_ocr_paddle(preprocessed)`
  5. Call `_extract_fields(text)` → ReceiptFields dataclass
  6. Normalize field names to snake_case
  7. Inject timestamp (ISO 8601 format)
  8. Stop timer, calculate processing_time_ms
- **Output Guarantee:**
  - Always returns dict with `success` and `scan_id` keys
  - `fields` dict always present (values may be None)
  - `confidence` always in [0.0, 1.0] range
  - `timestamp` always ISO 8601 string
- **Side Effects:**
  - Logging to console (DEBUG level) with processing time
  - No database writes (caller's responsibility)

**Error Handling:**
- **Invalid frame shape:** Raise `ValueError` with message "Expected BGR frame with shape (H, W, 3), got {shape}"
- **Invalid dtype:** Raise `ValueError` with message "Expected uint8 array, got {dtype}"
- **OCR engine failure:** Raise `RuntimeError` with message "All OCR engines failed. Last error: {error}"

**Performance Requirements:**
- Time Complexity: O(n) where n = frame pixel count
- Space Complexity: O(n) for preprocessing buffers
- Target: < 4000ms total on Pi 4B @ 640x480 input

---

#### Method: `_preprocess_thermal_receipt` (Private)

**Signature:**
```python
def _preprocess_thermal_receipt(
    self,
    bgr_frame: np.ndarray
) -> np.ndarray:
    """
    Apply Flash Express thermal receipt preprocessing pipeline.
    
    Args:
        bgr_frame: (H, W, 3) BGR uint8 array
    
    Returns:
        (H', W') binary uint8 array (grayscale thresholded)
        where H' = 800 * (H / W) for optimal OCR performance
    
    Raises:
        cv2.error: If OpenCV operations fail
    """
```

**Behavior Specification:**
- **Processing Steps:**
  1. Convert BGR → Grayscale
  2. Resize to 800px width (maintain aspect ratio, LANCZOS4 interpolation)
  3. Color-based orange banner removal (HSV masking for Flash Express footer)
  4. Noise reduction (fastNlMeansDenoising with h=10)
  5. Adaptive thresholding (GAUSSIAN_C, block=11, C=2)
  6. QR code region masking (bottom center 40% × 30% set to white)
- **Output Guarantee:** Binary image optimized for Tesseract PSM 6 (uniform text block)
- **Side Effects:** None (pure function)

**Error Handling:**
- **OpenCV failure:** Propagate `cv2.error` to caller with original stack trace

**Performance Requirements:**
- Time Complexity: O(n) where n = pixel count
- Space Complexity: O(n) for intermediate buffers
- Target: < 500ms on Pi 4B

---

#### Method: `_extract_fields` (Private)

**Signature:**
```python
def _extract_fields(
    self,
    ocr_text: str
) -> Dict[str, Any]:
    """
    Extract structured fields from OCR text using regex patterns.
    
    Args:
        ocr_text: Raw OCR output string
    
    Returns:
        Dictionary with extracted fields (snake_case keys)
    """
```

**Behavior Specification:**
- **Field Extraction Patterns:**
  - `tracking_id`: `r'FE\d{10}'` → First match
  - `order_id`: `r'FE\d{8}J\d{5}'` → First match
  - `rts_code`: `r'FEX-[A-Z]{3,4}-[A-Z]{2,4}-[A-Z0-9]{3,5}-[A-Z]{1,2}\d{2}'` → First match
  - `rider_id`: `r'Rider:\s*([A-Z]{1,2}\d{1,2})'` → Capture group
  - `weight_g`: `r'(\d{3,5})g'` → Convert to int
  - `quantity`: `r'Quantity:\s*(\d{1,3})'` → Convert to int
  - `payment_type`: `r'\b(COD|Paid|Prepaid)\b'` → First match (case-insensitive)
  - `buyer_name`: Custom parser for "BUYER" section (2 capitalized words)
  - `buyer_address`: Philippine address parser (street, barangay, city, province, ZIP)
- **Output Guarantee:** All fields default to None if not found
- **Side Effects:** None (pure function)

**Performance Requirements:**
- Time Complexity: O(m) where m = text length
- Space Complexity: O(1)
- Target: < 50ms

---

### Class: `ReceiptDatabase`

**Location:** `src/services/receipt_database.py`

#### Method: `store_scan`

**Signature:**
```python
def store_scan(
    self,
    scan_id: int,
    fields: Dict[str, Any],
    raw_text: str,
    confidence: float,
    engine: str
) -> bool:
    """
    Persist OCR scan results to SQLite database.
    
    Args:
        scan_id: Unique scan identifier
        fields: Extracted receipt fields (from FlashExpressOCR.process_frame)
        raw_text: Full OCR text output
        confidence: OCR confidence score (0.0-1.0)
        engine: OCR engine used ('tesseract' or 'paddle')
    
    Returns:
        True on success, False on failure
    
    Raises:
        sqlite3.Error: On database constraint violations
    """
```

**Behavior Specification:**
- **Input Validation:**
  - Verify `scan_id` is positive integer
  - Verify `confidence` in [0.0, 1.0]
  - Verify `engine` in ['tesseract', 'paddle']
- **Processing Logic:**
  1. Acquire database connection from `DatabaseManager`
  2. Insert into `receipt_scans` table with all fields
  3. Commit transaction
  4. Release connection
- **Output Guarantee:** Returns True if INSERT succeeds
- **Side Effects:** 
  - Database write to `data/database.db`
  - Auto-increment of scan history

**Error Handling:**
- **Duplicate scan_id:** Raise `sqlite3.IntegrityError` with message "Scan ID {scan_id} already exists"
- **Database locked:** Retry up to 3 times with 100ms delay, then raise

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)
- Target: < 100ms per insert

---

## 3. DEPENDENCIES

### This module CALLS:
- `cv2.cvtColor()` - Color space conversion (BGR→Gray, HSV)
- `cv2.resize()` - Image scaling with LANCZOS4 interpolation
- `cv2.fastNlMeansDenoising()` - Noise reduction
- `cv2.adaptiveThreshold()` - Binary thresholding
- `cv2.inpaint()` - Orange banner removal
- `pytesseract.image_to_data()` - Tesseract OCR with confidence data
- `pytesseract.image_to_string()` - Tesseract OCR text extraction
- `PaddleOCR()` (optional) - Fallback OCR engine
- `DatabaseManager.get_connection()` - Database access (via ReceiptDatabase)
- `VisionManager.get_frame()` - Camera frame acquisition (caller provides)

### This module is CALLED BY:
- `src/api/server.py::vision_scan_route()` - POST /api/vision/scan endpoint
- `src/api/server.py::ocr_analyze_route()` - POST /api/ocr/analyze endpoint
- `src/api/server.py::vision_results_route()` - GET /api/vision/results/<scan_id> (indirectly via RobotState)

---

## 4. DATA STRUCTURES

### ReceiptFields (Dataclass)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ReceiptFields:
    """Structured representation of Flash Express receipt data."""
    tracking_id: Optional[str] = None       # FE1234567890
    order_id: Optional[str] = None          # FE12345678J12345
    rts_code: Optional[str] = None          # FEX-BUL-SJDM-TKO1-GY22
    rider_id: Optional[str] = None          # GY22
    buyer_name: Optional[str] = None        # James Flores
    buyer_address: Optional[str] = None     # Full address string
    weight_g: Optional[int] = None          # Weight in grams
    quantity: Optional[int] = None          # Package count
    payment_type: Optional[str] = None      # COD/Paid/Prepaid
    confidence: float = 0.0                 # OCR confidence (0.0-1.0)
    timestamp: str = ""                     # ISO 8601 string
```

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS receipt_scans (
    scan_id INTEGER PRIMARY KEY,
    tracking_id TEXT,
    order_id TEXT,
    rts_code TEXT,
    rider_id TEXT,
    buyer_name TEXT,
    buyer_address TEXT,
    weight_g INTEGER,
    quantity INTEGER,
    payment_type TEXT,
    confidence REAL NOT NULL,
    raw_text TEXT NOT NULL,
    engine TEXT NOT NULL,  -- 'tesseract' or 'paddle'
    timestamp TEXT NOT NULL,  -- ISO 8601
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tracking_id ON receipt_scans(tracking_id);
CREATE INDEX IF NOT EXISTS idx_rts_code ON receipt_scans(rts_code);
CREATE INDEX IF NOT EXISTS idx_timestamp ON receipt_scans(timestamp);
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

### From `system_constraints.md`:
1. **Concurrency:** Use `threading` ONLY. No `asyncio` (legacy Serial/SMBus compatibility)
2. **Hardware Abstraction:** No direct OpenCV VideoCapture in OCR code - use VisionManager.get_frame()
3. **Non-Blocking:** OCR processing must run in background thread (Flask route returns immediately)
4. **Manager Pattern:** Use DatabaseManager for all SQLite operations
5. **Type Hints:** Mandatory for all public methods
6. **Docstrings:** Google-style required for all public classes/methods
7. **Max Function Length:** 50 lines (refactor if exceeded)
8. **Field Naming:** Backend uses `snake_case` for all JSON keys

### From `_STATE.MD`:
1. **Platform:** Raspberry Pi 4B (ARM64, 4GB RAM recommended)
2. **Camera:** Pi Camera Module 3 (IMX708) via CSI interface
3. **Performance Target:** < 4 seconds total processing time
4. **Storage:** Auto-cleanup after 50 high-res captures in `data/captures/`
5. **GPU Memory:** 256MB minimum allocation (shared with camera ISP)

---

## 6. MEMORY COMPLIANCE

**No `_memory_snippet.txt` provided** - no historical decisions to enforce.

**Applied Design Decisions:**
- Follow existing VisionManager threading pattern (background capture loop)
- Reuse existing `/api/ocr/analyze` endpoint structure (v4.2 compatibility)
- Maintain snake_case field naming in backend (frontend has dual-lookup)
- Use existing `_validate_ocr_result()` pattern for field normalization

---

## 7. ACCEPTANCE CRITERIA

### Test Case 1: Successful Flash Express Receipt Scan

**Scenario:** Clean thermal receipt with all fields present

**Setup:**
```python
vision_mgr = VisionManager()
vision_mgr.start_camera(640, 480, 15)
ocr = FlashExpressOCR()

# Capture frame with receipt5.jpg equivalent
frame = vision_mgr.get_frame()
```

**Input:**
```python
result = ocr.process_frame(frame, scan_id=12345)
```

**Expected Output:**
```python
{
    'success': True,
    'scan_id': 12345,
    'fields': {
        'tracking_id': 'FE2315392337',
        'order_id': 'FE083001J62947',
        'rts_code': 'FEX-BUL-SJDM-TKO1-GY22',
        'rider_id': 'GY22',
        'buyer_name': 'James Flores',
        'buyer_address': '115 Carriedo St, Brgy. Tungko Main, San Jose del Monte, Bulacan 3024',
        'weight_g': 6872,
        'quantity': 13,
        'payment_type': 'COD',
        'confidence': 0.92,  # >= 0.85
        'timestamp': '2026-02-09T14:30:45Z'
    },
    'raw_text': 'FE2315392337\nFE083001J62947\n...',
    'engine': 'tesseract',
    'processing_time_ms': 3650  # < 4000ms
}
```

**Expected Behavior:**
- Processing completes in < 4 seconds
- All critical fields extracted (tracking_id, order_id, rts_code, buyer_address)
- Confidence > 0.85 (no fallback to PaddleOCR)
- Timestamp is valid ISO 8601 string

---

### Test Case 2: Low Confidence Fallback to PaddleOCR

**Scenario:** Faded thermal receipt, Tesseract confidence < 0.85

**Setup:**
```python
ocr = FlashExpressOCR(use_paddle_fallback=True, confidence_threshold=0.85)
```

**Input:**
```python
# Frame with low-quality print
result = ocr.process_frame(faded_frame, scan_id=67890)
```

**Expected Output:**
```python
{
    'success': True,
    'scan_id': 67890,
    'fields': {
        'tracking_id': 'FE9876543210',
        # ... other fields ...
        'confidence': 0.96,  # Improved from 0.72 (Tesseract)
    },
    'engine': 'paddle',  # Fallback triggered
    'processing_time_ms': 6500  # < 10000ms (PaddleOCR is slower)
}
```

**Expected Behavior:**
- Tesseract runs first, returns confidence=0.72
- PaddleOCR fallback triggered automatically
- Final confidence > 0.85
- `engine` field correctly reports 'paddle'

---

### Test Case 3: Missing Fields Handling

**Scenario:** Partial receipt (cropped image missing buyer section)

**Input:**
```python
result = ocr.process_frame(cropped_frame, scan_id=11111)
```

**Expected Output:**
```python
{
    'success': True,
    'scan_id': 11111,
    'fields': {
        'tracking_id': 'FE1234567890',
        'order_id': None,  # Missing from cropped area
        'rts_code': 'FEX-BUL-SJDM-TKO1-GY22',
        'rider_id': None,
        'buyer_name': None,  # Missing from cropped area
        'buyer_address': None,
        'weight_g': 5000,
        'quantity': 1,
        'payment_type': 'COD',
        'confidence': 0.88,
        'timestamp': '2026-02-09T14:35:00Z'
    },
    'raw_text': 'FE1234567890\nFEX-BUL-SJDM-TKO1-GY22\n5000g\nQuantity: 1\nCOD',
    'engine': 'tesseract',
    'processing_time_ms': 3200
}
```

**Expected Behavior:**
- No exceptions raised for missing fields
- Fields default to None (not empty string)
- Success=True even with partial extraction
- Confidence reflects quality of extracted text (not field completeness)

---

### Test Case 4: Invalid Input Rejection

**Scenario:** Invalid frame format (grayscale instead of BGR)

**Input:**
```python
gray_frame = np.zeros((480, 640), dtype=np.uint8)  # 2D array
result = ocr.process_frame(gray_frame)
```

**Expected Exception:**
```python
ValueError: Expected BGR frame with shape (H, W, 3), got (480, 640)
```

**Expected Message Pattern:** Contains "Expected BGR frame"

---

### Test Case 5: Database Persistence

**Scenario:** Store successful scan result

**Setup:**
```python
db = ReceiptDatabase()
fields = {
    'tracking_id': 'FE2315392337',
    'order_id': 'FE083001J62947',
    # ... all fields ...
}
```

**Input:**
```python
success = db.store_scan(
    scan_id=12345,
    fields=fields,
    raw_text='FE2315392337\n...',
    confidence=0.92,
    engine='tesseract'
)
```

**Expected Output:**
```python
success == True
```

**Expected Database State:**
```sql
SELECT * FROM receipt_scans WHERE scan_id = 12345;
-- Returns 1 row with all fields populated
```

**Expected Behavior:**
- Transaction commits successfully
- Data retrievable via SELECT query
- Timestamp auto-populated with current datetime

---

## 8. INTEGRATION POINTS

### API Route Integration

```python
# src/api/server.py

@app.route('/api/vision/scan', methods=['POST'])
def vision_scan_route():
    """Enhanced to use FlashExpressOCR processor."""
    try:
        # Existing code gets frame from VisionManager
        frame = vision_manager.get_frame()
        
        # NEW: Use Flash Express processor
        ocr = FlashExpressOCR()
        result = ocr.process_frame(frame, scan_id=generate_scan_id())
        
        # Store in database
        receipt_db.store_scan(
            scan_id=result['scan_id'],
            fields=result['fields'],
            raw_text=result['raw_text'],
            confidence=result['fields']['confidence'],
            engine=result['engine']
        )
        
        # Store in RobotState for polling
        robot_state.set_last_scan(result)
        
        return jsonify({
            'success': True,
            'scan_id': result['scan_id'],
            'status': 'completed',
            'processing_time_ms': result['processing_time_ms']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

### Frontend Integration (OCR Results Panel)

```javascript
// static/js/ocr-panel.js

async function displayScanResults(scanId) {
    const response = await fetch(`/api/vision/results/${scanId}`);
    const data = await response.json();
    
    if (data.status === 'completed') {
        const fields = data.data.fields;
        
        // Display Flash Express specific fields
        document.getElementById('tracking-id').textContent = fields.tracking_id || 'N/A';
        document.getElementById('order-id').textContent = fields.order_id || 'N/A';
        document.getElementById('rts-code').textContent = fields.rts_code || 'N/A';
        document.getElementById('buyer-name').textContent = fields.buyer_name || 'N/A';
        document.getElementById('buyer-address').textContent = fields.buyer_address || 'N/A';
        document.getElementById('weight').textContent = fields.weight_g ? `${fields.weight_g}g` : 'N/A';
        document.getElementById('quantity').textContent = fields.quantity || 'N/A';
        document.getElementById('payment-type').textContent = fields.payment_type || 'N/A';
        
        // Confidence indicator
        updateConfidenceBadge(fields.confidence);
    }
}
```

---

## 9. PERFORMANCE BENCHMARKS

**Target Hardware:** Raspberry Pi 4B (4GB RAM, 256MB GPU)

| Operation | Target | Maximum |
|-----------|--------|---------|
| Preprocessing | < 500ms | 800ms |
| Tesseract OCR | < 3200ms | 4000ms |
| Field Extraction | < 50ms | 100ms |
| Database Insert | < 100ms | 200ms |
| **Total End-to-End** | **< 4000ms** | **5000ms** |

**Memory Footprint:**
- Tesseract only: ~150MB
- PaddleOCR loaded: ~500MB
- Peak working set: ~650MB (with fallback enabled)

---

## 10. DEPLOYMENT CHECKLIST

### Prerequisites
- [ ] Tesseract 5.x installed: `sudo apt-get install tesseract-ocr`
- [ ] Python dependencies: `pip install pytesseract opencv-python-headless numpy --break-system-packages`
- [ ] Optional: `pip install paddleocr --break-system-packages` (for fallback)
- [ ] GPU memory allocated: `vcgencmd get_mem gpu` shows >= 256MB
- [ ] `data/captures/` directory exists with write permissions

### Configuration
- [ ] Set `CAMERA_INTERFACE=csi` in `.env` file
- [ ] Verify camera detected: `libcamera-hello` shows preview
- [ ] Database schema created: Run `python -m src.database.init_db`

### Testing
- [ ] Unit tests pass: `pytest tests/test_ocr_processor.py`
- [ ] Integration test with sample receipt: Accuracy >= 90%
- [ ] Performance test: Processing time < 4 seconds
- [ ] Database persistence: Scans retrievable from SQLite

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:**
- `src/services/ocr_processor.py` (PRIMARY)
- `src/services/receipt_database.py` (SECONDARY)
- `src/database/schema.sql` (DATABASE SCHEMA)

**Contract Reference:** `docs/contracts/ocr_flash_express.md` v1.0

---

## STRICT CONSTRAINTS (NON-NEGOTIABLE)

1. **Threading Only:** Use `threading.Thread` for background processing. NO `asyncio`.
2. **Hardware Abstraction:** NEVER call `cv2.VideoCapture()` directly. Use `VisionManager.get_frame()`.
3. **Manager Pattern:** ALL database access via `DatabaseManager.get_connection()`.
4. **Type Hints:** EVERY function signature must have complete type annotations.
5. **Docstrings:** Google-style docstrings required for all public methods.
6. **Max Function Length:** 50 lines. Refactor `process_frame()` into helper methods if needed.
7. **Field Naming:** Backend JSON uses `snake_case` (tracking_id, buyer_name, etc.).
8. **Performance:** Total processing < 4000ms on Pi 4B @ 640x480 input.

---

## REQUIRED LOGIC

### Class: `FlashExpressOCR`

#### Step 1: Initialization
```python
def __init__(self, use_paddle_fallback=False, confidence_threshold=0.85):
    # 1. Validate confidence_threshold in [0.0, 1.0]
    # 2. Store Tesseract config: '--oem 1 --psm 6 -l eng'
    # 3. Compile regex patterns for ALL fields (see contract section 2)
    # 4. If use_paddle_fallback: Try import PaddleOCR, lazy-load instance
```

#### Step 2: Frame Processing
```python
def process_frame(self, bgr_frame, scan_id=None):
    # 1. Validate bgr_frame shape (H, W, 3) and dtype (uint8)
    # 2. Generate scan_id if None: use id(bgr_frame)
    # 3. Start timer
    # 4. preprocessed = self._preprocess_thermal_receipt(bgr_frame)
    # 5. text, confidence = self._ocr_tesseract(preprocessed)
    # 6. If confidence < threshold AND fallback: text, confidence = self._ocr_paddle(preprocessed)
    # 7. fields = self._extract_fields(text)
    # 8. Inject timestamp (datetime.now(timezone.utc).isoformat())
    # 9. Stop timer, calculate processing_time_ms
    # 10. Return dict with all required keys (see contract section 2)
```

#### Step 3: Preprocessing Pipeline
```python
def _preprocess_thermal_receipt(self, bgr_frame):
    # 1. cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
    # 2. Resize to 800px width: scale = 800 / width, cv2.resize(..., INTER_LANCZOS4)
    # 3. Orange banner removal:
    #    - Convert to HSV
    #    - Mask orange range [10-25, 100-255, 100-255]
    #    - cv2.inpaint() on masked regions
    # 4. cv2.fastNlMeansDenoising(h=10, templateWindowSize=7, searchWindowSize=21)
    # 5. cv2.adaptiveThreshold(ADAPTIVE_THRESH_GAUSSIAN_C, blockSize=11, C=2)
    # 6. Mask QR code region: bottom 40% height × center 30% width → set to 255 (white)
    # 7. Return binary uint8 array
```

#### Step 4: Field Extraction
```python
def _extract_fields(self, ocr_text):
    # 1. Apply regex patterns for simple fields (tracking_id, order_id, rts_code, etc.)
    # 2. Extract buyer_name: Look for "BUYER\n[Name]" pattern
    # 3. Extract buyer_address: Philippine address parser
    #    - Pattern: "Street, Brgy. [Name], City, Province ZIP"
    #    - Must handle compound city names ("San Jose del Monte")
    # 4. Type conversions: weight_g (int), quantity (int)
    # 5. Return dict with snake_case keys, None for missing fields
```

### Class: `ReceiptDatabase`

#### Step 1: Database Schema
```sql
-- src/database/schema.sql
CREATE TABLE IF NOT EXISTS receipt_scans (
    scan_id INTEGER PRIMARY KEY,
    tracking_id TEXT,
    order_id TEXT,
    rts_code TEXT,
    rider_id TEXT,
    buyer_name TEXT,
    buyer_address TEXT,
    weight_g INTEGER,
    quantity INTEGER,
    payment_type TEXT,
    confidence REAL NOT NULL,
    raw_text TEXT NOT NULL,
    engine TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tracking_id ON receipt_scans(tracking_id);
CREATE INDEX IF NOT EXISTS idx_rts_code ON receipt_scans(rts_code);
```

#### Step 2: Store Scan Method
```python
def store_scan(self, scan_id, fields, raw_text, confidence, engine):
    # 1. Validate inputs (scan_id > 0, confidence in [0.0, 1.0], engine in ['tesseract', 'paddle'])
    # 2. conn = DatabaseManager.get_connection()
    # 3. cursor = conn.cursor()
    # 4. INSERT INTO receipt_scans with all fields
    # 5. conn.commit()
    # 6. Return True on success
    # 7. Handle sqlite3.IntegrityError for duplicate scan_id
    # 8. Retry 3 times on sqlite3.OperationalError (database locked)
```

---

## INTEGRATION POINTS

### Must Call (Dependencies):
- `cv2.cvtColor()` - Color conversions
- `cv2.resize()` - Image scaling
- `cv2.fastNlMeansDenoising()` - Noise reduction
- `cv2.adaptiveThreshold()` - Binarization
- `cv2.inpaint()` - Banner removal
- `pytesseract.image_to_data()` - OCR with confidence
- `pytesseract.image_to_string()` - OCR text extraction
- `DatabaseManager.get_connection()` - Database access (via ReceiptDatabase)

### Will Be Called By:
- `src/api/server.py::vision_scan_route()` - POST /api/vision/scan
- `src/api/server.py::ocr_analyze_route()` - POST /api/ocr/analyze

---

## SUCCESS CRITERIA

### Code Quality
- [ ] All methods match contract signatures exactly
- [ ] Type hints present on all function signatures
- [ ] Google-style docstrings on all public methods
- [ ] No function exceeds 50 lines
- [ ] No `asyncio` usage (threading only)

### Functional Requirements
- [ ] All 11 Flash Express fields extracted correctly (when present)
- [ ] Preprocessing completes in < 500ms
- [ ] Tesseract OCR completes in < 3200ms
- [ ] Total processing < 4000ms on Pi 4B
- [ ] Confidence calculation accurate (matches Tesseract confidence data)
- [ ] Database persistence works (INSERT succeeds)

### Test Coverage
- [ ] Unit test: Valid frame processing (Test Case 1)
- [ ] Unit test: PaddleOCR fallback (Test Case 2)
- [ ] Unit test: Missing fields handling (Test Case 3)
- [ ] Unit test: Invalid input rejection (Test Case 4)
- [ ] Integration test: Database persistence (Test Case 5)
- [ ] Integration test: End-to-end with sample receipt (accuracy >= 90%)

### Auditor Requirements
- [ ] No violations of system_constraints.md
- [ ] Follows existing VisionManager threading pattern
- [ ] Maintains snake_case field naming in JSON
- [ ] Uses DatabaseManager (no direct sqlite3.connect())
- [ ] Proper error handling with descriptive messages

---

**Auditor approval required before deployment.**

---

✅ **Contract Created:** `docs/contracts/ocr_flash_express.md` v1.0  
📋 **Work Order Generated:** (embedded above)

---

### 📋 APPENDIX: API MAP UPDATE

**⚠️ MANUAL ACTION REQUIRED:** Before proceeding to implementation, copy this snippet into `docs/API_MAP_LITE.md` under the "SERVICES LAYER" section:

```markdown
#### Module: `FlashExpressOCR`
**Location:** `src/services/ocr_processor.py`
**Status:** Designed (not yet implemented)
**Contract:** `docs/contracts/ocr_flash_express.md` v1.0

**Public Interface:**
- `__init__(use_paddle_fallback: bool = False, confidence_threshold: float = 0.85) -> None`
  - Purpose: Initialize Flash Express OCR processor with optional PaddleOCR fallback
  - Raises: ImportError (PaddleOCR missing), ValueError (invalid threshold)
  
- `process_frame(bgr_frame: np.ndarray, scan_id: Optional[int] = None) -> Dict[str, Any]`
  - Purpose: Process camera frame for Flash Express receipt field extraction
  - Returns: Dict with success, scan_id, fields (11 receipt fields), raw_text, engine, processing_time_ms
  - Target: < 4000ms total processing time on Pi 4B
  - See contract for full specification

**Dependencies:**
- Imports: cv2, pytesseract, numpy, re, datetime, typing, dataclasses
- Optional: paddleocr (fallback engine)
- Called by: vision_scan_route(), ocr_analyze_route()

**Enables:**
- Flash Express receipt parsing (tracking ID, order ID, RTS code, buyer info, weight, quantity)
- Thermal print preprocessing optimized for Pi Camera Module 3
- Dual-engine OCR (Tesseract primary, PaddleOCR fallback)

#### Module: `ReceiptDatabase`
**Location:** `src/services/receipt_database.py`
**Status:** Designed (not yet implemented)
**Contract:** `docs/contracts/ocr_flash_express.md` v1.0

**Public Interface:**
- `store_scan(scan_id: int, fields: Dict, raw_text: str, confidence: float, engine: str) -> bool`
  - Purpose: Persist OCR scan results to SQLite database
  - Returns: True on success
  - See contract for full specification

**Database Schema:**
- Table: `receipt_scans` (15 columns including all Flash Express fields)
- Indexes: tracking_id, rts_code, timestamp

**Dependencies:**
- Imports: sqlite3, typing
- Uses: DatabaseManager.get_connection()
- Called by: vision_scan_route(), ocr_analyze_route()
```

---

### ⏭️ HUMAN WORKFLOW CHECKPOINT

**Status:** Contract design complete. Ready for implementation phase.

**Files You Should Have:**
- ✅ `docs/contracts/ocr_flash_express.md` v1.0 - The formal contract (embedded in this response)
- ✅ Work order - Instructions for implementer (embedded above)
- ✅ API Map snippet (above) - Ready to paste into `API_MAP_LITE.md`

**Before Moving to Next Agent:**

1. **Save the contract** - Copy the entire "CONTRACT: Flash Express OCR Integration" section to `docs/contracts/ocr_flash_express.md`
2. **Update API_MAP_LITE.md** - Paste the snippet above into the SERVICES LAYER section
3. **Verify completeness** - All 11 receipt fields specified? Preprocessing pipeline detailed? Database schema defined?
4. **Review constraints** - Pi 4B performance targets met? Threading-only enforced? Manager pattern required?

**Next Agent to Invoke:** `02_implementer.md`

**Required Files for Implementer:**
- `docs/contracts/ocr_flash_express.md` v1.0
- Work order (embedded in contract)
- `docs/API_MAP_LITE.md` (updated with new contract snippet)
- `docs/system_constraints.md`
- OCR research document (for preprocessing pipeline reference)

**Verification Command (copy-paste to Implementer):**

```
/verify-context: contracts/ocr_flash_express.md, API_MAP_LITE.md, system_constraints.md, ocr_research.md
```

**Ready to proceed?** If yes, provide the contract file and invoke the Implementer agent with the files listed above.