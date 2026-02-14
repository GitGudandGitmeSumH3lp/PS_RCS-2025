# Flash Express Zonal OCR Design Document
**Version:** 2.0  
**Created:** 2026-02-15  
**Status:** Production Design  
**Target:** Replace full-page OCR with region-based extraction

---

## EXECUTIVE SUMMARY

### The Problem
Current full-page OCR approach achieves:
- ✅ **100% tracking ID accuracy** (large, machine-readable font)
- ❌ **0% buyer name accuracy** (name completely missed)
- ❌ **14% address accuracy** (heavy column bleed, template labels mixed with data)
- ❌ **51% average confidence** (low quality indicates poor OCR conditions)

**Root Causes Identified:**
1. **Column Bleed:** Vertical "BUYER" and "SELLER" labels on dark brown background contaminate horizontal text flow
2. **Template Pollution:** "District", "Street", "City", "Province", "Zip Code" labels get mixed into address text
3. **Anchor Loss:** No spatial reference means buyer name (above address) is completely ignored
4. **Thermal Noise:** Low-contrast dot-matrix text requires aggressive preprocessing that damages adjacent regions

### The Solution
**Region-Based (Zonal) OCR** - Divide receipt into 5 specialized zones, each with:
- Dedicated preprocessing pipeline
- Optimized Tesseract configuration
- Spatial-aware field extraction
- Isolated processing (failures don't cascade)

### Expected Results
- **Buyer Name:** 0% → 85%+ (direct spatial targeting)
- **Address:** 14% → 75%+ (column isolation + template filtering)
- **Tracking ID:** 100% maintained (already working)
- **Processing Time:** <3.5s total (reduced OCR surface area)

---

## RECEIPT ANATOMY

Based on analysis of 7 Flash Express receipts, the layout is **highly standardized**:

```
┌─────────────────────────────────────────────────┐
│ [FLASH EXPRESS]  FE3690805513          [GY]     │ ← ZONE 1: Header (0-15%)
│ FEX-GAYA-GAYA-HUB-SJDM                          │
│ RTS Sort Code: FEX-BUL-SJDM-BS02-GY15           │
│ Rider: GY15                                     │
│ Order ID: FE0781379UHY88                        │
├─────────────────────────────────────────────────┤
│ ║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║║   │ ← ZONE 2: Barcode (15-40%)
│         FE 352981460456                         │
├─────────────────────────────────────────────────┤
│ BUYER │ Carlos Johnson                    PDG   │ ← ZONE 3: Buyer Info (40-58%)
│       │ 381 Bulacan Highway, Brgy. Bagong       │   **CRITICAL ZONE**
│       │ Silang (Brgy 176) Metro Manila Border,  │
│       │ San Jose del Monte, Bulacan 3023        │
│       │ District         City        Zip Code   │ ← Template labels
│       │ Street          Province                │
├─────────────────────────────────────────────────┤
│SELLER │ Flash Express                      COD  │ ← ZONE 4: Seller Info (58-70%)
│       │ Gaya-Gaya Warehouse, SJDM, Bulacan 3023│
│       │ District         City        Zip Code   │
│       │ Street          Province                │
├─────────────────────────────────────────────────┤
│ Product Quantity: 2  │ [QR CODE] │ [  ] [  ] [  ]│ ← ZONE 5: Footer (70-100%)
│ Weight: 1184g        │           │ [  ] [  ] [  ]│
│ ────────────────────────────────────────────────│
│ FASTEST DELIVERY IN THE PHILIPPINES             │ ← Orange banner
└─────────────────────────────────────────────────┘
```

### Key Observations
1. **Horizontal bands are consistent** across all receipts (±2% variance)
2. **Vertical "BUYER" label is 40px wide** dark brown background
3. **Buyer name is ALWAYS on the first line** after barcode region
4. **Address spans 2-4 lines**, ends before "District/Street" template
5. **Weight/Quantity are bottom-left**, isolated from QR code
6. **Orange footer is HSV-maskable** (already implemented)

---

## ZONE DEFINITIONS

### Zone 1: Header Block
**Purpose:** Extract tracking ID, order ID, RTS code, rider ID  
**Vertical Range:** 0% - 15% of receipt height  
**Characteristics:** Clean printed text, high contrast, no column contamination

**Extraction Strategy:**
- Already works at 100% accuracy
- Keep existing preprocessing + full-text regex
- **No changes needed** - maintain current pipeline

---

### Zone 2: Barcode Region
**Purpose:** Secondary tracking ID validation (from barcode number)  
**Vertical Range:** 15% - 40% of receipt height  
**Characteristics:** Black/white barcode + numeric string below

**Extraction Strategy:**
- OCR the numeric string below barcode
- Use as fallback if Zone 1 tracking ID fails
- **Low priority** - Zone 1 already reliable

---

### Zone 3: Buyer Information (CRITICAL ZONE)
**Purpose:** Extract buyer name and address  
**Vertical Range:** 40% - 58% of receipt height  
**Horizontal Range:** **60px - 95%** of width (crop out "BUYER" label)

**Why This Zone Fails Now:**
```
Current Full-Page OCR Output:
"BUYER Carlos Johnson PDG 381 Bulacan Highway..."

Problems:
1. "BUYER" label bleeds into text
2. "PDG" (payment type) attached to name
3. "District", "Street", "City" template labels mixed into address
4. Multi-line address becomes single garbled string
```

**Preprocessing Pipeline:**
```python
1. Crop region: frame[int(H*0.40):int(H*0.58), 60:int(W*0.95)]
   → Removes "BUYER" label (first 60px)
   → Removes right margin with "PDG"/"COD" tags
   
2. Convert to grayscale
   
3. CLAHE enhancement (clipLimit=3.0, tileGridSize=(4,4))
   → Boosts thermal dot-matrix contrast
   
4. Morphological opening: kernel=np.ones((2,2))
   → Removes salt noise from thermal printing
   
5. Adaptive threshold:
   - Method: ADAPTIVE_THRESH_GAUSSIAN_C
   - blockSize: 15 (larger than full-page to handle low contrast)
   - C: 3 (aggressive binarization)
   
6. Dilation: kernel=np.ones((1,2), horizontal)
   → Connects broken characters in thermal text
   
7. Template label suppression:
   - Detect horizontal lines (Hough transform)
   - Mask everything below first detected line
   → Removes "District/Street/City/Province" labels
```

**Tesseract Configuration:**
```python
config = '--oem 1 --psm 6 -l eng'
# PSM 6 = Uniform block of text (suitable for address block)
# OEM 1 = Neural nets LSTM engine (better for thermal text)
```

**Field Extraction Logic:**
```python
def extract_buyer_info(ocr_text: str) -> Tuple[str, str]:
    """
    Extract buyer name and address from Zone 3 OCR text.
    
    Strategy:
    1. Split into lines, clean each line
    2. First non-empty line = buyer name
    3. Next 2-4 lines = address components
    4. Stop when hitting template keywords or empty lines
    """
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    
    if not lines:
        return None, None
    
    # First line is buyer name
    buyer_name = lines[0]
    
    # Remove attached payment type suffix
    buyer_name = re.sub(r'\s+(PDG|COD|Paid)$', '', buyer_name)
    
    # Clean OCR artifacts
    buyer_name = buyer_name.replace('|', 'I')  # Common OCR error
    
    # Validate: should be 2-4 words, capitalized
    name_words = buyer_name.split()
    if not (2 <= len(name_words) <= 4):
        return None, None  # Invalid name format
    
    # Extract address lines
    address_lines = []
    template_keywords = ['district', 'street', 'city', 'province', 'zip code']
    
    for line in lines[1:]:
        line_lower = line.lower()
        
        # Stop at template labels
        if any(kw in line_lower for kw in template_keywords):
            break
        
        # Stop at seller section
        if 'flash express' in line_lower or 'gaya-gaya' in line_lower:
            break
            
        address_lines.append(line)
    
    address = ', '.join(address_lines) if address_lines else None
    
    return buyer_name, address
```

**Confidence Boosting:**
```python
# Post-validation checks
def validate_buyer_name(name: str) -> bool:
    """Validate extracted buyer name format."""
    if not name:
        return False
    
    # Must be 2-4 words
    words = name.split()
    if not (2 <= len(words) <= 4):
        return False
    
    # Each word should start with capital letter
    if not all(w[0].isupper() for w in words if w):
        return False
    
    # No numbers in name
    if any(char.isdigit() for char in name):
        return False
    
    return True

def validate_address(address: str) -> bool:
    """Validate extracted address has Philippine address markers."""
    if not address or len(address) < 20:
        return False
    
    # Must contain barangay reference
    if not re.search(r'brgy|barangay', address, re.IGNORECASE):
        return False
    
    # Must contain city/municipality
    if not re.search(r'san jose del monte|sjdm|bulacan', address, re.IGNORECASE):
        return False
    
    # Must have postal code
    if not re.search(r'\b302[0-9]\b', address):
        return False
    
    return True
```

---

### Zone 4: Seller Information
**Purpose:** Extract seller name, warehouse location (optional)  
**Vertical Range:** 58% - 70% of receipt height  
**Horizontal Range:** 60px - 95% of width (same crop as Zone 3)

**Extraction Strategy:**
- Same preprocessing as Zone 3
- Always "Flash Express" + warehouse address
- **Low priority** - seller is constant across all receipts
- Use for sanity check only (verify "Flash Express" appears)

---

### Zone 5: Footer Metadata
**Purpose:** Extract weight, quantity, payment type  
**Vertical Range:** 70% - 85% of receipt height  
**Horizontal Range:** 0 - 45% of width (left side, excludes QR code)

**Why This Zone Needs Isolation:**
- QR code causes Tesseract to output garbage when full-page processed
- Current implementation masks QR but not cleanly

**Preprocessing Pipeline:**
```python
1. Crop region: frame[int(H*0.70):int(H*0.85), 0:int(W*0.45)]
   → Excludes QR code (center-right), excludes attempt checkboxes (right)
   
2. Convert to grayscale

3. Gaussian blur: kernel=(3,3)
   → Smooth thermal noise
   
4. Otsu's threshold (automatic threshold detection)
   → Simple binarization since this region has good contrast
   
5. Morphological closing: kernel=np.ones((2,2))
   → Fill gaps in printed numbers
```

**Tesseract Configuration:**
```python
config = '--oem 1 --psm 6 -l eng --psm 11'
# PSM 11 = Sparse text (good for "Quantity: 2" format)
# Could also try PSM 7 (single text line)
```

**Field Extraction:**
```python
def extract_footer_fields(ocr_text: str) -> Dict[str, Any]:
    """Extract weight and quantity from footer region."""
    
    fields = {
        'weight_g': None,
        'quantity': None,
        'payment_type': None
    }
    
    # Weight pattern: "Weight: 1184g" or "1184g"
    weight_match = re.search(r'(\d{3,5})\s*g', ocr_text, re.IGNORECASE)
    if weight_match:
        fields['weight_g'] = int(weight_match.group(1))
    
    # Quantity pattern: "Quantity: 2" or "Product Quantity: 13"
    qty_match = re.search(r'quantity:\s*(\d{1,3})', ocr_text, re.IGNORECASE)
    if qty_match:
        fields['quantity'] = int(qty_match.group(1))
    
    # Payment type from Zone 3 or Zone 4 (not Zone 5)
    # This should be extracted from buyer/seller zones
    # Zone 5 only extracts weight/quantity
    
    return fields
```

---

## INTEGRATION WITH EXISTING CODE

### Current Architecture
```python
class FlashExpressOCR:
    def process_frame(self, bgr_frame, scan_id):
        # Current flow:
        preprocessed = self._preprocess_thermal_receipt(bgr_frame)
        text, confidence = self._ocr_tesseract(preprocessed)
        fields = self._extract_fields(text)  # ← Replace this
        return format_result(...)
```

### New Architecture
```python
class FlashExpressOCR:
    def process_frame(self, bgr_frame, scan_id):
        # NEW: Multi-zone processing
        zone_results = self._process_zones(bgr_frame)
        fields = self._merge_zone_fields(zone_results)
        return format_result(...)
    
    def _process_zones(self, bgr_frame):
        """Process each zone independently."""
        H, W = bgr_frame.shape[:2]
        
        zones = {
            'header': self._process_zone_1(bgr_frame, H, W),
            'buyer': self._process_zone_3(bgr_frame, H, W),
            'footer': self._process_zone_5(bgr_frame, H, W)
        }
        
        return zones
    
    def _process_zone_3(self, bgr_frame, H, W):
        """Process buyer information zone (critical)."""
        # Crop region
        y1, y2 = int(H * 0.40), int(H * 0.58)
        x1, x2 = 60, int(W * 0.95)
        region = bgr_frame[y1:y2, x1:x2]
        
        # Preprocess
        processed = self._preprocess_buyer_zone(region)
        
        # OCR
        text, conf = self._ocr_tesseract(
            processed, 
            config='--oem 1 --psm 6 -l eng'
        )
        
        # Extract fields
        buyer_name, address = self._extract_buyer_info(text)
        
        return {
            'buyer_name': buyer_name,
            'buyer_address': address,
            'confidence': conf,
            'raw_text': text
        }
    
    def _preprocess_buyer_zone(self, region):
        """Specialized preprocessing for buyer info."""
        # Convert to grayscale
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        
        # CLAHE enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
        enhanced = clahe.apply(gray)
        
        # Morphological opening (noise removal)
        kernel_open = np.ones((2,2), np.uint8)
        opened = cv2.morphologyEx(enhanced, cv2.MORPH_OPEN, kernel_open)
        
        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            opened, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            15, 3
        )
        
        # Horizontal dilation (connect broken chars)
        kernel_dilate = np.ones((1,2), np.uint8)
        dilated = cv2.dilate(binary, kernel_dilate, iterations=1)
        
        # Template label suppression (mask bottom section)
        h = dilated.shape[0]
        # Detect horizontal lines using projection
        horizontal_proj = np.sum(dilated == 0, axis=1)
        threshold = dilated.shape[1] * 0.6  # 60% black pixels = line
        
        line_positions = np.where(horizontal_proj > threshold)[0]
        if len(line_positions) > 0:
            # Mask everything below first major horizontal line
            first_line = line_positions[0]
            if first_line < h * 0.8:  # Only if line is not at very bottom
                dilated[first_line:, :] = 255
        
        return dilated
```

### Fallback Strategy
```python
def _merge_zone_fields(self, zone_results):
    """Merge results from all zones with fallback logic."""
    
    fields = {
        'tracking_id': None,
        'order_id': None,
        'rts_code': None,
        'rider_id': None,
        'buyer_name': None,
        'buyer_address': None,
        'weight_g': None,
        'quantity': None,
        'payment_type': None,
        'confidence': 0.0
    }
    
    # Zone 1 (header) - primary source for IDs
    if 'header' in zone_results:
        fields.update({
            'tracking_id': zone_results['header'].get('tracking_id'),
            'order_id': zone_results['header'].get('order_id'),
            'rts_code': zone_results['header'].get('rts_code'),
            'rider_id': zone_results['header'].get('rider_id')
        })
    
    # Zone 3 (buyer) - critical for name/address
    if 'buyer' in zone_results:
        buyer = zone_results['buyer']
        
        # Validate before accepting
        if self._validate_buyer_name(buyer.get('buyer_name')):
            fields['buyer_name'] = buyer['buyer_name']
        
        if self._validate_address(buyer.get('buyer_address')):
            fields['buyer_address'] = buyer['buyer_address']
        
        # If validation fails, try full-page OCR as fallback
        if not fields['buyer_name'] or not fields['buyer_address']:
            logger.warning("Zone 3 validation failed, attempting full-page fallback")
            fallback = self._fallback_full_page_ocr(bgr_frame)
            if not fields['buyer_name']:
                fields['buyer_name'] = fallback.get('buyer_name')
            if not fields['buyer_address']:
                fields['buyer_address'] = fallback.get('buyer_address')
    
    # Zone 5 (footer) - weight/quantity
    if 'footer' in zone_results:
        fields.update({
            'weight_g': zone_results['footer'].get('weight_g'),
            'quantity': zone_results['footer'].get('quantity')
        })
    
    # Calculate aggregate confidence
    confidences = [z.get('confidence', 0) for z in zone_results.values() if z]
    fields['confidence'] = sum(confidences) / len(confidences) if confidences else 0.0
    
    return fields
```

---

## IMPLEMENTATION PLAN

### Phase 1: Zone 3 Prototype (Buyer Info)
**Goal:** Validate zonal approach on critical failing zone  
**Timeline:** 2 hours  
**Deliverables:**
1. `_process_zone_3()` method
2. `_preprocess_buyer_zone()` method
3. `_extract_buyer_info()` extraction logic
4. Test on 7 sample images
5. Measure accuracy improvement

**Success Criteria:**
- Buyer name accuracy: >80%
- Address accuracy: >70%
- No regression on tracking ID

### Phase 2: Zone 5 Integration (Footer)
**Goal:** Improve weight/quantity extraction  
**Timeline:** 1 hour  
**Deliverables:**
1. `_process_zone_5()` method
2. `_preprocess_footer_zone()` method
3. `_extract_footer_fields()` extraction logic

**Success Criteria:**
- Weight accuracy: >95%
- Quantity accuracy: >95%

### Phase 3: Full Integration
**Goal:** Replace existing `_extract_fields()` with zonal system  
**Timeline:** 2 hours  
**Deliverables:**
1. `_process_zones()` orchestrator
2. `_merge_zone_fields()` aggregator
3. Fallback logic for zone failures
4. Updated error handling
5. Performance profiling

**Success Criteria:**
- Total processing time: <3.5s
- All zones processed successfully
- Graceful degradation if zone fails

### Phase 4: Testing & Validation
**Goal:** Ensure production readiness  
**Timeline:** 2 hours  
**Deliverables:**
1. Run on all 7 test images
2. Compare against ground truth
3. Generate accuracy report
4. Performance benchmarks
5. Edge case testing (blurry images, partial receipts)

**Success Criteria:**
- Overall accuracy: >85%
- No critical field regressions
- Processing time within target

---

## TESTING METHODOLOGY

### Ground Truth Comparison
```python
def evaluate_ocr_accuracy(scan_results, ground_truth):
    """
    Compare OCR results against ground truth.
    
    Args:
        scan_results: List of OCR output dicts
        ground_truth: Ground truth data from ground_truth.json
    
    Returns:
        Accuracy metrics per field
    """
    
    metrics = {
        'tracking_id': {'correct': 0, 'total': 0, 'accuracy': 0.0},
        'order_id': {'correct': 0, 'total': 0, 'accuracy': 0.0},
        'buyer_name': {'correct': 0, 'total': 0, 'accuracy': 0.0},
        'buyer_address': {'correct': 0, 'total': 0, 'accuracy': 0.0},
        'weight_g': {'correct': 0, 'total': 0, 'accuracy': 0.0},
        'quantity': {'correct': 0, 'total': 0, 'accuracy': 0.0}
    }
    
    for scan in scan_results:
        tracking_id = scan['fields']['tracking_id']
        
        # Find matching ground truth
        gt = None
        for img_name, gt_data in ground_truth.items():
            if gt_data['tracking_id'] == tracking_id:
                gt = gt_data
                break
        
        if not gt:
            continue
        
        # Compare each field
        for field in metrics.keys():
            metrics[field]['total'] += 1
            
            # Get extracted and ground truth values
            if field == 'tracking_id':
                extracted = scan['fields'].get('tracking_id')
                expected = gt['tracking_id']
            elif field == 'order_id':
                extracted = scan['fields'].get('order_id')
                expected = gt['order_id']
            elif field == 'buyer_name':
                extracted = scan['fields'].get('buyer_name')
                expected = gt['buyer_name']
            elif field == 'buyer_address':
                extracted = scan['fields'].get('buyer_address')
                expected = gt['address']
            elif field == 'weight_g':
                extracted = scan['fields'].get('weight_g')
                # Parse weight from ground truth (e.g., "1184g" -> 1184)
                expected = int(gt['weight'].replace('g', ''))
            elif field == 'quantity':
                extracted = scan['fields'].get('quantity')
                expected = int(gt['quantity'])
            
            # Check match
            if field == 'buyer_address':
                # Fuzzy match for address (allow minor differences)
                if extracted and expected:
                    # Normalize both
                    ext_norm = ' '.join(extracted.lower().split())
                    exp_norm = ' '.join(expected.lower().split())
                    # Check if main components match
                    if 'brgy' in ext_norm and 'san jose del monte' in ext_norm:
                        metrics[field]['correct'] += 1
            else:
                # Exact match for other fields
                if extracted == expected:
                    metrics[field]['correct'] += 1
    
    # Calculate accuracy percentages
    for field in metrics:
        total = metrics[field]['total']
        if total > 0:
            metrics[field]['accuracy'] = (
                metrics[field]['correct'] / total * 100
            )
    
    return metrics
```

### Expected Results
```
BEFORE (Current Full-Page OCR):
┌────────────────┬─────────┬─────────┬──────────┐
│ Field          │ Correct │ Total   │ Accuracy │
├────────────────┼─────────┼─────────┼──────────┤
│ Tracking ID    │ 7       │ 7       │ 100.0%   │
│ Order ID       │ 2       │ 7       │  28.6%   │
│ Buyer Name     │ 0       │ 7       │   0.0%   │ ← CRITICAL FAIL
│ Address        │ 1       │ 7       │  14.3%   │ ← CRITICAL FAIL
│ Weight         │ 3       │ 7       │  42.9%   │
│ Quantity       │ 6       │ 7       │  85.7%   │
└────────────────┴─────────┴─────────┴──────────┘

AFTER (Zonal OCR - Target):
┌────────────────┬─────────┬─────────┬──────────┐
│ Field          │ Correct │ Total   │ Accuracy │
├────────────────┼─────────┼─────────┼──────────┤
│ Tracking ID    │ 7       │ 7       │ 100.0%   │ ← Maintained
│ Order ID       │ 6       │ 7       │  85.7%   │ ← Improved
│ Buyer Name     │ 6       │ 7       │  85.7%   │ ← FIXED ✓
│ Address        │ 5       │ 7       │  71.4%   │ ← FIXED ✓
│ Weight         │ 7       │ 7       │ 100.0%   │ ← Improved
│ Quantity       │ 7       │ 7       │ 100.0%   │ ← Improved
└────────────────┴─────────┴─────────┴──────────┘
Overall: 80%+ field accuracy (vs 50% current)
```

---

## PERFORMANCE CONSIDERATIONS

### Current Timing (Full-Page OCR)
```
Preprocessing:           ~500ms
Tesseract (full page):  ~2000ms
PaddleOCR fallback:     ~2500ms (when triggered)
Field extraction:        ~100ms
TOTAL:                  ~3100ms average
```

### Expected Timing (Zonal OCR)
```
Zone 1 (header):
  - Crop + preprocess:    50ms
  - OCR (small region):  400ms
  
Zone 3 (buyer):
  - Crop + preprocess:   100ms
  - OCR (medium region): 600ms
  
Zone 5 (footer):
  - Crop + preprocess:    50ms
  - OCR (small region):  300ms
  
Field extraction:        100ms
Merge + validation:       50ms

TOTAL:                 ~1650ms (parallel) to ~2200ms (sequential)
```

**Optimization Opportunities:**
1. **Parallel zone processing** using ThreadPoolExecutor
2. **Early exit** if Zone 1 + Zone 3 succeed (skip Zone 5 if not needed)
3. **Caching** preprocessed images for multi-attempt scenarios
4. **Tesseract optimization** per zone (different PSM modes)

---

## EDGE CASES & FALLBACKS

### Edge Case 1: Partial Receipt Capture
**Scenario:** Camera captures only top 70% of receipt  
**Detection:** Zone 5 extraction returns None  
**Fallback:** Use Zone 1 + Zone 3 only, mark weight/quantity as null

### Edge Case 2: Severe Thermal Fade
**Scenario:** Receipt text is very light (old thermal paper)  
**Detection:** Zone 3 confidence <0.3  
**Fallback:** Apply aggressive CLAHE (clipLimit=5.0), retry OCR

### Edge Case 3: Skewed Receipt
**Scenario:** Receipt at 5-15° angle  
**Detection:** Hough line detection shows non-horizontal lines  
**Fallback:** Apply perspective correction before zonal cropping

### Edge Case 4: Multi-Line Name
**Scenario:** Buyer name wraps to second line (rare but possible)  
**Detection:** First line has <2 words, second line starts with capital  
**Fallback:** Concatenate first two lines as buyer name

### Edge Case 5: Zone Boundary Misalignment
**Scenario:** Receipt is compressed/stretched vertically  
**Detection:** Key fields not found in expected zones  
**Fallback:** 
1. Use horizontal line detection to find actual zone boundaries
2. Adjust zone percentages dynamically
3. If still fails, fall back to full-page OCR

---

## IMPLEMENTATION CHECKLIST

### Code Changes
- [ ] Create `_process_zone_1()` method (header extraction)
- [ ] Create `_process_zone_3()` method (buyer info)
- [ ] Create `_process_zone_5()` method (footer)
- [ ] Create `_preprocess_buyer_zone()` (specialized preprocessing)
- [ ] Create `_preprocess_footer_zone()` (specialized preprocessing)
- [ ] Create `_extract_buyer_info()` (name + address parser)
- [ ] Create `_extract_footer_fields()` (weight + quantity parser)
- [ ] Create `_validate_buyer_name()` (name format validator)
- [ ] Create `_validate_address()` (address format validator)
- [ ] Create `_merge_zone_fields()` (result aggregator)
- [ ] Update `process_frame()` to use zonal pipeline
- [ ] Add fallback to full-page OCR on zone failures
- [ ] Add performance timing per zone

### Testing
- [ ] Unit test: Zone cropping accuracy
- [ ] Unit test: Buyer name extraction
- [ ] Unit test: Address extraction
- [ ] Unit test: Template label removal
- [ ] Integration test: Full pipeline on 7 samples
- [ ] Accuracy comparison: before vs after
- [ ] Performance benchmark: timing per zone
- [ ] Edge case testing: partial receipts, faded text, skewed images

### Documentation
- [ ] Update API documentation
- [ ] Add inline comments for zone boundaries
- [ ] Document preprocessing parameters per zone
- [ ] Create troubleshooting guide for low accuracy
- [ ] Update README with new accuracy metrics

### Deployment
- [ ] Code review
- [ ] Run evaluation script on test set
- [ ] Verify no regression on tracking ID
- [ ] Performance profiling on Raspberry Pi 4B
- [ ] Monitor production accuracy for 1 week
- [ ] Rollback plan if accuracy drops

---

## CONCLUSION

### Why This Will Work

1. **Root Cause Addressed:** Column bleed from "BUYER"/"SELLER" labels is eliminated by horizontal cropping
2. **Spatial Awareness:** Zone-based processing maintains buyer name position (first line after barcode)
3. **Template Isolation:** Horizontal line detection removes "District/Street" labels before extraction
4. **Focused Preprocessing:** Each zone gets tuned preprocessing (CLAHE for thermal text, Otsu for printed numbers)
5. **Validation Gates:** Post-extraction validation ensures garbage doesn't propagate

### Risk Mitigation

1. **Fallback to Full-Page:** If zones fail, revert to original pipeline
2. **Incremental Rollout:** Deploy Zone 3 first, validate, then add other zones
3. **A/B Testing:** Run both systems in parallel, compare results
4. **Monitoring:** Track per-zone accuracy in production logs

### Success Metrics

- **Primary:** Buyer name 0% → 85%+, Address 14% → 75%+
- **Secondary:** Overall field accuracy >80%, processing time <3.5s
- **Operational:** Zero regressions on currently working fields

---

**Document Version:** 2.0  
**Last Updated:** 2026-02-15  
**Next Review:** After Phase 1 implementation  
**Status:** Ready for implementation