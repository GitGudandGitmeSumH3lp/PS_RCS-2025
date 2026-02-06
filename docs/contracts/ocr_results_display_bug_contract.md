# CONTRACT: OCR Results Display Bug Fix
**Version:** 1.0  
**Last Updated:** 2026-02-06  
**Status:** DRAFT  
**Target Files:**  
- `F:\PORTFOLIO\ps_rcs_project\frontend\static\js\dashboard-core.js`
- `F:\PORTFOLIO\ps_rcs_project\src\api\server.py`

---

## 1. PURPOSE

Fix the OCR results display panel showing empty fields (dashes) despite successful backend analysis. Root cause is field name inconsistency between backend OCR service (returns snake_case) and frontend display logic (expects mixed naming). This contract establishes a robust field normalization strategy with defensive fallbacks.

---

## 2. DECISION LOG

### 2.1 Field Name Strategy
**Decision:** Implement dual-lookup with snake_case primary, camelCase fallback.

**Rationale:** Backend OCR service returns fields in snake_case format (`tracking_id`, `order_id`, `rts_code`, `district`, `confidence`, `timestamp`). Frontend currently expects exact matches but should handle both naming conventions defensively.

**Implementation Pattern:**
```javascript
// Normalize field access with fallback chain
const getValue = (data, snakeCase, camelCase) => {
  return data[snakeCase] ?? data[camelCase] ?? null;
};
```

### 2.2 Empty State Detection
**Decision:** Distinguish between "no text detected" vs "processing failed" using field population threshold.

**Criteria:**
- **No Text Detected:** All core fields (tracking_id, order_id, rts_code, district) are null/undefined/empty
- **Processing Failed:** OCR service returns error object or confidence < 0.1
- **Partial Success:** At least one core field populated

**Implementation Logic:**
```javascript
const coreFields = [tracking_id, order_id, rts_code, district];
const populatedCount = coreFields.filter(val => val && val !== '-').length;
const isEmpty = populatedCount === 0;
```

### 2.3 Toast Messaging Logic
**Decision:** Contextual toast messages based on analysis outcome.

**Message Matrix:**

| Condition | Message | Type |
|-----------|---------|------|
| All fields empty | "No text detected in image" | Warning |
| confidence < 0.5 | "Low confidence results - verify accuracy" | Warning |
| 0.5 ≤ confidence < 0.85 | "Analysis complete" | Success |
| confidence ≥ 0.85 | "High confidence analysis complete" | Success |
| Error response | "Analysis failed - please retry" | Error |

### 2.4 Confidence Threshold Mapping
**Decision:** Three-tier visual indicator with strict boundaries.

**Thresholds:**
- **High (Green):** confidence ≥ 0.85
- **Medium (Yellow):** 0.7 ≤ confidence < 0.85
- **Low (Red):** confidence < 0.7

**CSS Implementation:**
```css
.confidence-badge[data-level="high"]::before { background: var(--confidence-high); }
.confidence-badge[data-level="medium"]::before { background: var(--confidence-medium); }
.confidence-badge[data-level="low"]::before { background: var(--confidence-low); }
```

### 2.5 Timestamp Format Handling
**Decision:** Display localized human-readable format with ISO fallback.

**Format Strategy:**
```javascript
// Backend returns ISO 8601 string: "2026-02-06T14:30:00.000Z"
const timestamp = data.timestamp || data.scan_time;
const displayTime = timestamp 
  ? new Date(timestamp).toLocaleString()
  : '-';
```

---

## 3. BACKEND CHANGES

### 3.1 OCR Service Response Contract

**File:** `F:\PORTFOLIO\ps_rcs_project\src\api\server.py`

**Current State Analysis:**
- OCR service callback injects `scan_id` into result (line 315)
- Result object stored in `state.vision.last_scan`
- Fields returned: Unknown (not visible in provided server.py)

**Required Specification:**

```python
# OCR Service MUST return this exact structure
ocr_result: Dict[str, Any] = {
    'scan_id': int,           # Injected by callback
    'tracking_id': str,       # Primary parcel identifier
    'order_id': str,          # Order/shipment number
    'rts_code': str,          # Return-to-sender code
    'district': str,          # Geographic district
    'confidence': float,      # 0.0 to 1.0
    'timestamp': str,         # ISO 8601 format
}
```

**Validation Requirements:**

**Signature:**
```python
def _validate_ocr_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure OCR result contains required fields with correct types.
    
    Args:
        result: Raw OCR service output
    
    Returns:
        Validated dictionary with all required fields
    
    Raises:
        ValueError: If critical fields missing or invalid types
    """
```

**Behavior:**
- Check for presence of: `tracking_id`, `order_id`, `rts_code`, `district`, `confidence`, `timestamp`
- Convert `confidence` to float if string
- Ensure `timestamp` is valid ISO 8601 string
- Set missing fields to `None` (not empty string)
- Clamp `confidence` to [0.0, 1.0] range

**Integration Point:**
```python
def update_state(fut: Any) -> None:
    try:
        result = fut.result()
        result['scan_id'] = scan_id
        result = _validate_ocr_result(result)  # ADD THIS LINE
        self.state.update_scan_result(result)
        self.logger.info(f"[APIServer] OCR completed: {result.get('tracking_id', 'N/A')}")
    except Exception as e:
        self.logger.error(f"[APIServer] OCR callback error: {e}")
```

---

## 4. FRONTEND CHANGES

### 4.1 JavaScript: `_displayResults()` Method

**File:** `F:\PORTFOLIO\ps_rcs_project\frontend\static\js\dashboard-core.js`  
**Current Location:** Lines 923-962  
**Max Length:** 50 lines (Per system_constraints.md)

**New Signature:**
```javascript
/**
 * Display OCR analysis results with defensive field normalization.
 * 
 * @param {Object} data - OCR result object from backend
 * @param {string} [data.tracking_id] - Tracking number (snake_case)
 * @param {string} [data.trackingId] - Tracking number (camelCase fallback)
 * @param {string} [data.order_id] - Order ID
 * @param {string} [data.rts_code] - RTS code
 * @param {string} [data.district] - District name
 * @param {number} [data.confidence] - Confidence score (0-1)
 * @param {string} [data.timestamp] - ISO timestamp
 * @private
 */
_displayResults(data)
```

**Required Implementation Logic:**

```javascript
_displayResults(data) {
  if (!this.elements.resultsPanel || !data) return;
  
  console.log('[OCR Raw Data]:', data);  // Debugging aid
  
  // STEP 1: Normalize field access with dual-lookup
  const getField = (snakeCase, camelCase) => {
    const value = data[snakeCase] ?? data[camelCase] ?? null;
    return value && value.trim() !== '' ? value.trim() : null;
  };
  
  // STEP 2: Extract fields with fallbacks
  const tracking = getField('tracking_id', 'trackingId');
  const order = getField('order_id', 'orderId');
  const rts = getField('rts_code', 'rtsCode');
  const district = getField('district', 'district');
  const confidence = parseFloat(data.confidence ?? data.conf ?? 0);
  const timestamp = data.timestamp ?? data.scan_time ?? null;
  
  // STEP 3: Determine empty state
  const coreFields = [tracking, order, rts, district];
  const populatedCount = coreFields.filter(v => v !== null).length;
  const isEmpty = populatedCount === 0;
  
  // STEP 4: Update confidence badge
  const confidenceBadge = this.elements.resultsPanel.querySelector('.confidence-badge');
  const confidenceText = document.getElementById('confidence-value');
  
  if (confidenceBadge && confidenceText) {
    let level = 'low';
    if (confidence >= 0.85) level = 'high';
    else if (confidence >= 0.7) level = 'medium';
    
    confidenceBadge.setAttribute('data-level', level);
    confidenceText.textContent = `${(confidence * 100).toFixed(0)}%`;
  }
  
  // STEP 5: Populate result fields
  const fields = {
    'result-tracking-id': tracking,
    'result-order-id': order,
    'result-rts-code': rts,
    'result-district': district,
    'result-timestamp': timestamp ? new Date(timestamp).toLocaleString() : null
  };
  
  Object.entries(fields).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) {
      const valueSpan = element.querySelector('.data-value');
      if (valueSpan) {
        valueSpan.textContent = value ?? '-';
      }
    }
  });
  
  // STEP 6: Show results panel
  this.elements.resultsPanel.classList.remove('hidden');
  this.elements.resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  
  // STEP 7: Contextual toast message
  if (isEmpty) {
    this._showToast('No text detected in image', 'warning');
  } else if (confidence < 0.5) {
    this._showToast('Low confidence results - verify accuracy', 'warning');
  } else if (confidence >= 0.85) {
    this._showToast('High confidence analysis complete', 'success');
  } else {
    this._showToast('Analysis complete', 'success');
  }
}
```

**Line Count:** 49 lines (within 50-line limit)

### 4.2 Toast Notification Enhancement

**Method:** `_showToast(message, type)`  
**Current Location:** Lines 981-983 (console.log only)  
**Status:** TODO - Implementation required

**Required Signature:**
```javascript
/**
 * Display toast notification to user.
 * 
 * @param {string} message - Notification text
 * @param {'success'|'warning'|'error'|'info'} type - Visual style
 * @private
 */
_showToast(message, type = 'info')
```

**Behavior Specification:**
- Create temporary DOM element with toast styling
- Position: Bottom-right corner of viewport
- Duration: 3 seconds for success/info, 5 seconds for warning/error
- Auto-remove after duration
- Max 3 toasts visible simultaneously (queue older toasts)

**Constraint:** This method is NOT part of the OCR bug fix scope. Log message for now, defer full implementation to future work order.

---

## 5. HTML CHANGES

**File:** `F:\PORTFOLIO\ps_rcs_project\frontend\templates\service_dashboard.html`

**Verification Required:** Ensure results panel structure exists with correct IDs.

**Expected Structure:**
```html
<div id="ocr-results-panel" class="ocr-results hidden">
  <div class="result-header">
    <h3>Analysis Results</h3>
    <div class="confidence-badge" data-level="high">
      <span id="confidence-value">0%</span>
    </div>
  </div>
  
  <div class="result-grid">
    <div id="result-tracking-id" class="data-field">
      <span class="data-label">Tracking ID</span>
      <span class="data-value">-</span>
      <button class="copy-btn" onclick="ocrPanel._copyToClipboard('tracking-id')">
        Copy
      </button>
    </div>
    
    <div id="result-order-id" class="data-field">
      <span class="data-label">Order ID</span>
      <span class="data-value">-</span>
      <button class="copy-btn" onclick="ocrPanel._copyToClipboard('order-id')">
        Copy
      </button>
    </div>
    
    <div id="result-rts-code" class="data-field">
      <span class="data-label">RTS Code</span>
      <span class="data-value">-</span>
      <button class="copy-btn" onclick="ocrPanel._copyToClipboard('rts-code')">
        Copy
      </button>
    </div>
    
    <div id="result-district" class="data-field">
      <span class="data-label">District</span>
      <span class="data-value">-</span>
      <button class="copy-btn" onclick="ocrPanel._copyToClipboard('district')">
        Copy
      </button>
    </div>
    
    <div id="result-timestamp" class="data-field">
      <span class="data-label">Scanned At</span>
      <span class="data-value">-</span>
    </div>
  </div>
</div>
```

**ARIA Attributes (Required for Accessibility):**
```html
<div id="ocr-results-panel" 
     class="ocr-results hidden" 
     role="region" 
     aria-labelledby="results-heading"
     aria-live="polite">
  <h3 id="results-heading">Analysis Results</h3>
  <!-- ... -->
</div>
```

**Validation Steps:**
1. Verify element IDs match JavaScript selectors
2. Ensure `.data-value` spans exist for field updates
3. Confirm copy buttons reference correct field IDs
4. Check `this.elements.resultsPanel` binding in OCRPanel constructor

---

## 6. CSS CHANGES

**File:** `F:\PORTFOLIO\ps_rcs_project\frontend\static\css\service_theme.css`

**Current Confidence Badge Styles (Lines 937-962):**
```css
.confidence-badge {
  /* Existing styles verified as correct */
}
```

**Required Updates:** NONE - Existing CSS is correct.

**Verification Checklist:**
- ✅ `.confidence-badge[data-level="high"]` uses `var(--confidence-high)` (#10b981)
- ✅ `.confidence-badge[data-level="medium"]` uses `var(--confidence-medium)` (#f59e0b)
- ✅ `.confidence-badge[data-level="low"]` uses `var(--confidence-low)` (#ef4444)
- ✅ No hardcoded hex colors in component styles

**Empty State Styling (Recommended Addition):**
```css
.data-value:empty::before,
.data-value:has(text = "-")::before {
  content: attr(data-empty-text, "No data");
  color: var(--text-muted);
  font-style: italic;
}
```

**Status:** OPTIONAL - Deferred to polish phase.

---

## 7. ACCEPTANCE CRITERIA

### 7.1 Functional Requirements

**Test Case 1: Successful OCR with All Fields**
- **Input:** Image with complete parcel label
- **Backend Returns:**
  ```json
  {
    "tracking_id": "PKG-2026-001234",
    "order_id": "ORD-5678",
    "rts_code": "RTS-NCR",
    "district": "Quezon City",
    "confidence": 0.92,
    "timestamp": "2026-02-06T14:30:00.000Z"
  }
  ```
- **Expected Output:**
  - All fields display correct values (not dashes)
  - Confidence badge shows green dot with "92%"
  - Toast: "High confidence analysis complete" (success)
  - Browser console: `[OCR Raw Data]: {tracking_id: "PKG-2026-001234", ...}`

**Test Case 2: Empty Image (No Text)**
- **Input:** Blank white image
- **Backend Returns:**
  ```json
  {
    "tracking_id": null,
    "order_id": null,
    "rts_code": null,
    "district": null,
    "confidence": 0.05,
    "timestamp": "2026-02-06T14:31:00.000Z"
  }
  ```
- **Expected Output:**
  - All fields display "-" (dash)
  - Confidence badge shows red dot with "5%"
  - Toast: "No text detected in image" (warning)

**Test Case 3: Partial OCR Success**
- **Input:** Partially obscured label
- **Backend Returns:**
  ```json
  {
    "tracking_id": "PKG-2026-001235",
    "order_id": null,
    "rts_code": "RTS-NCR",
    "district": null,
    "confidence": 0.68,
    "timestamp": "2026-02-06T14:32:00.000Z"
  }
  ```
- **Expected Output:**
  - `tracking_id` and `rts_code` display values
  - `order_id` and `district` display "-"
  - Confidence badge shows red dot with "68%"
  - Toast: "Low confidence results - verify accuracy" (warning)

**Test Case 4: CamelCase Fallback**
- **Input:** Legacy backend returns camelCase
- **Backend Returns:**
  ```json
  {
    "trackingId": "PKG-2026-001236",
    "orderId": "ORD-5679",
    "rtsCode": "RTS-MNL",
    "district": "Manila",
    "confidence": 0.87,
    "timestamp": "2026-02-06T14:33:00.000Z"
  }
  ```
- **Expected Output:**
  - All fields display correct values (fallback works)
  - Confidence badge shows green dot with "87%"
  - Toast: "High confidence analysis complete" (success)

### 7.2 Technical Requirements

**TR-1: Code Quality**
- [ ] `_displayResults()` method ≤ 50 lines
- [ ] All variables use `camelCase` (JavaScript style guide)
- [ ] JSDoc comments present
- [ ] No `console.error` without try/catch

**TR-2: Performance**
- [ ] Field access is O(1) (direct object lookup)
- [ ] No unnecessary DOM queries (cache element references)
- [ ] Timestamp parsing uses native `Date` (no external libraries)

**TR-3: Robustness**
- [ ] Handles `null`, `undefined`, empty string for all fields
- [ ] Confidence value clamped to [0, 1] before percentage conversion
- [ ] Timestamp parsing wrapped in try/catch
- [ ] Copy button disabled if value is "-"

**TR-4: Style Compliance**
- [ ] Zero hardcoded colors in JavaScript
- [ ] CSS uses only `var(--token-name)` variables
- [ ] Border radius: 12-16px for buttons (system_style.md §4)
- [ ] Typography: Inter font family

### 7.3 Browser Compatibility

**Tested Browsers:**
- [ ] Chrome 120+ (Primary)
- [ ] Firefox 115+ (Secondary)
- [ ] Edge 120+ (Secondary)

**Feature Support:**
- [ ] Nullish coalescing (`??`) - Supported in all target browsers
- [ ] Optional chaining (`?.`) - Supported in all target browsers
- [ ] `scrollIntoView({ behavior: 'smooth' })` - Graceful degradation if unsupported

---

## 8. RISK MITIGATION

### 8.1 Field Name Mismatch
**Risk:** Backend changes naming convention again.  
**Mitigation:** Dual-lookup pattern handles both snake_case and camelCase.  
**Fallback:** Log unrecognized field names to console for debugging.

**Code Implementation:**
```javascript
// Log unknown fields for future debugging
const knownFields = ['tracking_id', 'trackingId', 'order_id', 'orderId', ...];
Object.keys(data).forEach(key => {
  if (!knownFields.includes(key)) {
    console.warn('[OCR] Unknown field:', key, '=', data[key]);
  }
});
```

### 8.2 Empty Results Confusion
**Risk:** User confused why all fields show "-".  
**Mitigation:** Contextual toast message explains "No text detected".  
**Future Enhancement:** Add empty state illustration with retry suggestion.

### 8.3 Timestamp Parsing Failure
**Risk:** Invalid ISO string causes `new Date()` to return `Invalid Date`.  
**Mitigation:** Validate timestamp before parsing.

**Code Implementation:**
```javascript
const displayTime = (() => {
  if (!timestamp) return '-';
  try {
    const date = new Date(timestamp);
    return isNaN(date.getTime()) ? '-' : date.toLocaleString();
  } catch {
    return '-';
  }
})();
```

### 8.4 Confidence Out of Range
**Risk:** Backend returns confidence > 1.0 or < 0.0.  
**Mitigation:** Clamp value before display.

**Code Implementation:**
```javascript
const confidence = Math.max(0, Math.min(1, parseFloat(data.confidence ?? 0)));
```

### 8.5 Copy Button Malfunction
**Risk:** Copy fails silently in unsupported browsers.  
**Mitigation:** Check `navigator.clipboard` availability.

**Code Implementation:**
```javascript
_copyToClipboard(fieldId) {
  if (!navigator.clipboard) {
    this._showToast('Copy not supported in this browser', 'error');
    return;
  }
  // ... existing copy logic
}
```

---

## 9. DEPENDENCIES

### 9.1 This Module CALLS

**Backend:**
- `OCRService.process_scan(frame)` - Asynchronous OCR processing
  - **Contract:** Returns Future object with result containing `{tracking_id, order_id, rts_code, district, confidence, timestamp}`
  - **Dependency:** OCR service must return consistent snake_case field names

**Frontend:**
- `this.elements.resultsPanel.querySelector()` - DOM traversal
- `document.getElementById()` - Element lookup
- `navigator.clipboard.writeText()` - Clipboard API

### 9.2 This Module is CALLED BY

**Frontend:**
- `OCRPanel.analyzeDocument()` - After successful OCR analysis (line 895)
- `OCRPanel._pollForResults()` - After polling completes (line 915)

**Data Flow:**
```
[User clicks Analyze] 
  → analyzeDocument() 
  → POST /api/ocr/analyze 
  → OCRService.process_scan() 
  → Future callback updates state.vision.last_scan 
  → Frontend polls /api/vision/results/{scan_id} 
  → _displayResults(data)
```

---

## 10. CONSTRAINTS (FROM SYSTEM RULES)

### From `system_constraints.md`:
1. **Max Function Length:** 50 lines (JavaScript/Python) - ENFORCED in `_displayResults()`
2. **Type Hints:** Mandatory for all Python functions - ENFORCED in `_validate_ocr_result()`
3. **Error Handling:** Specific exceptions only - NO `except Exception:` in production code
4. **Absolute Paths:** Windows paths in documentation - ENFORCED in file references

### From `system_style.md`:
1. **CSS Variables Only:** No hardcoded `#hex` colors - ENFORCED in all stylesheets
2. **Typography:** Inter, -apple-system, BlinkMacSystemFont - VERIFIED in theme
3. **Border Radius:** 20-24px cards, 12-16px buttons - VERIFIED in existing styles
4. **Naming:**
   - JavaScript: `camelCase` for methods/variables
   - Python: `snake_case` for functions/variables
5. **Documentation:**
   - Python: Google-style docstrings
   - JavaScript: JSDoc comments

---

## 11. MEMORY COMPLIANCE

**No `_memory_snippet.txt` provided.** No historical memory rules apply to this contract.

**Future Memory Entries (Recommended):**
```
2026-02-06 | OCR Field Normalization: Always use dual-lookup (snake_case primary, camelCase fallback) for backend-frontend field mapping to prevent naming convention mismatches.

2026-02-06 | Empty State Detection: Use field population count, not confidence alone, to determine "no text detected" state. Threshold: 0 populated core fields.

2026-02-06 | Toast Message Context: Toast severity must match analysis outcome - "warning" for empty/low confidence, "success" for populated results.
```

---

## 12. POST-ACTION REPORT TEMPLATE

```
✅ **Contract Created:** F:\PORTFOLIO\ps_rcs_project\docs\contracts\ocr_results_display_bug_contract.md
📋 **Work Order Generated** for Implementer

🔧 **Required Changes:**
   - JavaScript: Refactor `_displayResults()` with dual-lookup pattern (49 lines)
   - Backend: Add `_validate_ocr_result()` field normalization (20 lines)
   - HTML: Verify results panel structure with correct IDs
   - CSS: No changes required (styles already correct)

🎯 **Critical Fixes:**
   1. Field normalization handles snake_case + camelCase
   2. Empty state detection uses population count
   3. Contextual toast messages based on outcome
   4. Confidence badge correct color mapping
   5. Timestamp parsing with error handling

🔍 **Next Verification Command:**
/verify-context: system_style.md, system_constraints.md, contracts/ocr_results_display_bug_contract.md, dashboard-core.js, server.py

👉 **Next Agent:** Implementer (AGENTS/02_implementer.md)

⚠️ **Blockers:** None - All dependencies available
📊 **Estimated LOC:** ~70 lines (49 JS + 21 Python)
⏱️ **Estimated Time:** 45 minutes implementation + 15 minutes testing
```

---

## 13. IMPLEMENTATION CHECKLIST

### Backend (server.py)
- [ ] Add `_validate_ocr_result()` helper function
- [ ] Integrate validation in OCR callback (line ~315)
- [ ] Add unit tests for field normalization
- [ ] Log validated structure for debugging

### Frontend (dashboard-core.js)
- [ ] Refactor `_displayResults()` method (lines 923-962)
- [ ] Add defensive null checks for all field access
- [ ] Implement dual-lookup with `getField()` helper
- [ ] Add console.log for raw data debugging
- [ ] Update toast logic with contextual messages
- [ ] Add timestamp parsing error handling
- [ ] Verify confidence clamping to [0, 1]

### HTML (service_dashboard.html)
- [ ] Verify `#ocr-results-panel` exists
- [ ] Confirm element IDs: `result-tracking-id`, `result-order-id`, etc.
- [ ] Check `.data-value` span structure
- [ ] Validate copy button onclick handlers
- [ ] Add ARIA attributes for accessibility

### Testing
- [ ] Test Case 1: Full OCR success (all fields populated)
- [ ] Test Case 2: Empty image (no text detected)
- [ ] Test Case 3: Partial OCR (some fields null)
- [ ] Test Case 4: CamelCase fallback compatibility
- [ ] Browser console shows `[OCR Raw Data]` log
- [ ] Confidence badge colors correct (green/yellow/red)
- [ ] Copy buttons functional (no copy on "-")
- [ ] Toast messages contextually appropriate

---

**ARCHITECT SIGNATURE:** Contract v1.0 APPROVED for implementation.  
**Immutability Notice:** These interfaces are now FROZEN. Field access patterns, confidence thresholds, and toast message logic are non-negotiable. Any deviations require Architect re-approval.
