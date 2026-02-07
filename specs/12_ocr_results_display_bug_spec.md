```markdown
# FEATURE SPEC: OCR Results Display Bug Fix
**Date:** 2026-02-06
**Status:** Urgent / Bugfix
**Target File:** `docs/specs/ocr_results_display_bug_spec.md`

## 1. DIAGNOSIS

### Symptom Analysis
*   **Observation:** User sees "Analysis complete" (Success) toast, but results panel fields are empty (dashes `-`).
*   **Contradiction:** A "Success" toast implies the system detected valid data, but the visual display shows none.
*   **Root Cause:**
    1.  **Field Name Mismatch:** The backend (`server.py`) strictly enforces `snake_case` (e.g., `tracking_id`), while the legacy frontend code likely attempts to access `camelCase` properties (e.g., `data.trackingId`), resulting in `undefined` values.
    2.  **Missing Empty State Logic:** The current frontend likely defaults to a "Success" toast if the API call succeeds (HTTP 200), ignoring the semantic content of the result (i.e., whether text was actually found).
    3.  **Log Discrepancy:** The absence of `[OCR Raw Data]` in the provided logs confirms the running code is an older version lacking the defensive logging and validation present in the `dashboard-core.js` reference file.

## 2. REQUIRED FIXES

### A. Frontend: Robust Field Mapping (`dashboard-core.js`)
*   **Action:** Update `OCRPanel._displayResults` to use a **Dual-Lookup Pattern**.
*   **Logic:**
    *   Check `snake_case` key first (Backend Standard).
    *   Fallback to `camelCase` key (Legacy/Frontend Standard).
    *   Treat `null`, `undefined`, and `""` (empty string) as invalid.

```javascript
// Pattern Specification
const getField = (snakeCase, camelCase) => {
    const value = data[snakeCase] ?? data[camelCase] ?? null;
    return value && value.trim() !== '' ? value.trim() : null;
};
```

### B. Frontend: Empty State Detection
*   **Action:** Calculate `isEmpty` derived state before updating UI.
*   **Logic:**
    *   Define core fields: `tracking`, `order`, `rts`, `district`.
    *   Check if **all** core fields are null/empty.
    *   **Crucial:** Prioritize `isEmpty` check in the Toast Logic chain to prevent false "Success" messages.

```javascript
// Logic Specification
const coreFields = [tracking, order, rts, district];
const isEmpty = coreFields.every(field => !field);

if (isEmpty) {
    this._showToast('No text detected in image', 'warning');
} else {
    // ... proceed to confidence checks ...
}
```

### C. Backend: Data integrity (`server.py`)
*   **Validation:** Verify `_validate_ocr_result` ensures `confidence` is a float (0.0-1.0) and `timestamp` is a valid ISO string. (Current `server.py` implementation appears correct, focus is on Frontend consumption).

## 3. ACCEPTANCE CRITERIA
*   [ ] **Diagnostic:** Browser console outputs `[OCR Raw Data]: { ... }` with `snake_case` keys.
*   [ ] **Visual:** If OCR finds text, fields display values (e.g., "TRK-123").
*   [ ] **Visual:** If OCR finds nothing, fields display `-` and Toast is "No text detected in image" (Warning Color).
*   [ ] **Legacy Support:** System handles both `tracking_id` and `trackingId` keys without error.
*   [ ] **Confidence:** Badge correctly reflects confidence level (High > 85%, Medium > 70%, Low < 70%).

## 4. RISK MITIGATION
*   **Regression:** Ensure `document.getElementById` calls reference the correct IDs (`result-tracking-id` for Panel, `tracking-id` for Card).
*   **Type Safety:** `parseFloat(data.confidence)` must handle `null` or `undefined` (defaults to 0).
*   **Date Parsing:** Wrap `new Date(timestamp)` in a try-catch block to prevent UI crashes on invalid date strings.
```