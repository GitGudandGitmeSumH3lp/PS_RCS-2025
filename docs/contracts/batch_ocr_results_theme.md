✅ **Context verified. Proceeding.**

**Verified files:**
- `system_constraints.md` (v2026-02-11) ✅
- `system_style.md` (V4.1) ✅
- `service_dashboard.html` ✅
- `ocr-panel.js` ✅

---

# CONTRACT: Batch OCR Results Theme Integration

**Version:** 1.0  
**Last Updated:** 2026-02-17  
**Status:** Draft

## 1. PURPOSE

This contract defines the complete redesign of the batch OCR results display to achieve full theme compatibility and reliable data presentation. The module transforms the current hard-coded, table-based batch results into a theme-aware, card-based interface that respects the X/Linear aesthetic and properly displays extracted OCR fields.

**Problems Addressed:**
1. Theme incompatibility (hard-coded colors ignore dark/light mode)
2. Missing extracted field data (field mapping issues)
3. UI inconsistency with established design system

## 2. PUBLIC INTERFACE

### 2.1 HTML Structure Specification

**Location:** `service_dashboard.html` - Batch Results Container

```html
<!-- Inside OCR Modal, after existing content -->
<div id="batch-results-container" class="batch-results-container" role="region" aria-label="Batch OCR Results">
  <div class="batch-results-header">
    <h3 class="batch-results-title">Batch Results</h3>
    <button id="btn-close-batch" class="btn-icon" aria-label="Close batch results">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
        <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"/>
      </svg>
    </button>
  </div>
  
  <div id="batch-results-grid" class="batch-results-grid">
    <!-- Dynamic cards generated here -->
  </div>
</div>
```

**Card Template Structure (JavaScript-generated):**

```html
<article class="batch-result-card" data-batch-index="{index}" role="article">
  <div class="batch-card-header">
    <span class="batch-card-number">#{index + 1}</span>
    <span class="batch-card-status batch-status-{success|error}" 
          role="status" 
          aria-label="{Success|Failed}">
      {✓ Success | ✗ Failed}
    </span>
  </div>
  
  <div class="batch-card-body">
    <!-- For successful OCR -->
    <div class="batch-field-group">
      <div class="batch-field" data-field="tracking_id">
        <label class="batch-field-label">Tracking ID</label>
        <div class="batch-field-value-wrapper">
          <span class="batch-field-value">{value}</span>
          <button class="btn-copy-field" 
                  data-field-id="tracking_id" 
                  data-batch-index="{index}"
                  aria-label="Copy Tracking ID">
            <svg width="16" height="16"><!-- copy icon --></svg>
          </button>
        </div>
      </div>
      <!-- Repeat for: order_id, buyer_name, receiver_name, delivery_address -->
    </div>
    
    <!-- For failed OCR -->
    <div class="batch-error-message" role="alert">
      <svg class="batch-error-icon" width="20" height="20"><!-- error icon --></svg>
      <span>{error_message}</span>
    </div>
  </div>
</article>
```

### 2.2 CSS Specifications

**Location:** `service_dashboard.html` - `<style>` block or separate CSS file

**Theme Variables (MUST be used exclusively):**

```css
:root[data-theme="dark"] {
  --bg-primary: #0F0F0F;
  --bg-surface: #1A1A1A;
  --text-primary: #F0F0F0;
  --text-secondary: #B0B0B0;
  --border-color: rgba(255, 255, 255, 0.1);
  --success: #10B981;
  --danger: #EF4444;
  --action-primary: #888888;
  --shadow-soft: 0 8px 30px rgba(0, 0, 0, 0.08);
}

:root[data-theme="light"] {
  --bg-primary: #F8FAFC;
  --bg-surface: #FFFFFF;
  --text-primary: #1E293B;
  --text-secondary: #64748B;
  --border-color: rgba(0, 0, 0, 0.1);
  --success: #10B981;
  --danger: #EF4444;
  --action-primary: #1E293B;
  --shadow-soft: 0 8px 30px rgba(0, 0, 0, 0.05);
}
```

**Container Styles:**

```css
.batch-results-container {
  display: none; /* Hidden by default */
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 90vw;
  max-width: 1200px;
  height: 85vh;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 24px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--shadow-soft);
  z-index: 2000;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.batch-results-container.active {
  display: flex;
}

.batch-results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid var(--border-color);
}

.batch-results-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn-icon {
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 12px;
  transition: background-color 0.2s ease;
}

.btn-icon:hover {
  background: var(--border-color);
  color: var(--text-primary);
}
```

**Grid Layout (Bento Grid):**

```css
.batch-results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

@media (max-width: 768px) {
  .batch-results-grid {
    grid-template-columns: 1fr;
  }
}
```

**Card Styles:**

```css
.batch-result-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 20px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.batch-result-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-soft);
}

.batch-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.batch-card-number {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.batch-card-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.batch-status-success {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
}

.batch-status-error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--danger);
}

.batch-field-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.batch-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.batch-field-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.batch-field-value-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 44px; /* Touch target compliance */
}

.batch-field-value {
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-word;
  flex: 1;
}

.btn-copy-field {
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.btn-copy-field:hover {
  background: var(--border-color);
  color: var(--text-primary);
  border-color: var(--text-secondary);
}

.btn-copy-field:active {
  transform: scale(0.95);
}
```

**Error State:**

```css
.batch-error-message {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--danger);
  border-radius: 12px;
  color: var(--danger);
  font-size: 14px;
}

.batch-error-icon {
  flex-shrink: 0;
  fill: currentColor;
}
```

### 2.3 JavaScript Modifications

**File:** `ocr-panel.js`

#### Method: `_displayBatchResults(results)`

**Signature:**
```javascript
/**
 * Displays batch OCR results in theme-compliant card layout
 * @param {Array<Object>} results - Array of OCR result objects
 * @private
 */
_displayBatchResults(results) {
  // Implementation details below
}
```

**Behavior Specification:**

**Input Validation:**
- Verify `results` is an array
- Handle empty array gracefully
- Validate each result object has required structure

**Processing Logic:**
1. Show batch results container
2. Clear existing cards from grid
3. For each result in array:
   - Extract fields using `_extractFieldsFromData()` (reuse existing method)
   - Generate card HTML based on success/error state
   - Attach event listeners for copy buttons
4. Ensure container has proper ARIA attributes
5. Set focus to close button for accessibility

**Output Guarantee:**
- Returns void
- Updates DOM with card elements
- All cards respect current theme

**Side Effects:**
- Modifies `#batch-results-grid` innerHTML
- Adds event listeners to dynamically created buttons
- Shows `#batch-results-container`

**Error Handling:**
- **Empty results array:** Display message "No results to display"
- **Invalid result structure:** Log warning and skip item
- **DOM element missing:** Throw error with message "Batch results container not found in DOM"

**Implementation Template:**

```javascript
_displayBatchResults(results) {
  if (!Array.isArray(results)) {
    console.error('Invalid results format');
    return;
  }

  const container = document.getElementById('batch-results-container');
  const grid = document.getElementById('batch-results-grid');
  
  if (!container || !grid) {
    throw new Error('Batch results container not found in DOM');
  }

  // Clear existing content
  grid.innerHTML = '';

  // Handle empty results
  if (results.length === 0) {
    grid.innerHTML = '<p class="batch-empty-message">No results to display</p>';
    container.classList.add('active');
    return;
  }

  // Generate cards
  results.forEach((result, index) => {
    const card = this._createBatchResultCard(result, index);
    grid.appendChild(card);
  });

  // Show container
  container.classList.add('active');
  
  // Set focus to close button
  const closeBtn = document.getElementById('btn-close-batch');
  if (closeBtn) {
    closeBtn.focus();
  }
}
```

#### Method: `_createBatchResultCard(result, index)`

**Signature:**
```javascript
/**
 * Creates a single batch result card element
 * @param {Object} result - OCR result object
 * @param {number} index - Card index in batch
 * @returns {HTMLElement} Card element
 * @private
 */
_createBatchResultCard(result, index) {
  // Implementation details below
}
```

**Behavior Specification:**

**Input Validation:**
- Verify `result` is an object
- Verify `index` is a number

**Processing Logic:**
1. Create article element with proper attributes
2. Check if OCR was successful
3. If successful:
   - Extract fields using `_extractFieldsFromData(result.data)` or `_extractFieldsFromData(result)`
   - Create field rows for: tracking_id, order_id, buyer_name, receiver_name, delivery_address
   - Add copy buttons with proper event listeners
4. If failed:
   - Display error message from `result.error` or generic message
5. Add status indicator
6. Return complete card element

**Field Mapping (CRITICAL):**
```javascript
const fieldMap = {
  tracking_id: 'Tracking ID',
  order_id: 'Order ID',
  buyer_name: 'Buyer Name',
  receiver_name: 'Receiver Name',
  delivery_address: 'Delivery Address'
};
```

**Implementation Template:**

```javascript
_createBatchResultCard(result, index) {
  const card = document.createElement('article');
  card.className = 'batch-result-card';
  card.setAttribute('data-batch-index', index);
  card.setAttribute('role', 'article');

  const isSuccess = result.success === true;
  
  // Header
  const header = `
    <div class="batch-card-header">
      <span class="batch-card-number">#${index + 1}</span>
      <span class="batch-card-status batch-status-${isSuccess ? 'success' : 'error'}" 
            role="status" 
            aria-label="${isSuccess ? 'Success' : 'Failed'}">
        ${isSuccess ? '✓ Success' : '✗ Failed'}
      </span>
    </div>
  `;

  let body = '';
  
  if (isSuccess) {
    // Extract fields using existing method
    const fields = this._extractFieldsFromData(result.data || result);
    
    const fieldMap = {
      tracking_id: 'Tracking ID',
      order_id: 'Order ID',
      buyer_name: 'Buyer Name',
      receiver_name: 'Receiver Name',
      delivery_address: 'Delivery Address'
    };

    const fieldRows = Object.entries(fieldMap).map(([key, label]) => {
      const value = fields[key] || 'N/A';
      return `
        <div class="batch-field" data-field="${key}">
          <label class="batch-field-label">${label}</label>
          <div class="batch-field-value-wrapper">
            <span class="batch-field-value">${this._escapeHtml(value)}</span>
            <button class="btn-copy-field" 
                    data-field-id="${key}" 
                    data-batch-index="${index}"
                    data-value="${this._escapeHtml(value)}"
                    aria-label="Copy ${label}">
              <svg width="16" height="16" fill="currentColor">
                <path d="M8 2a1 1 0 0 1 1 1v5h5a1 1 0 1 1 0 2H9v5a1 1 0 1 1-2 0V10H2a1 1 0 1 1 0-2h5V3a1 1 0 0 1 1-1z"/>
              </svg>
            </button>
          </div>
        </div>
      `;
    }).join('');

    body = `<div class="batch-card-body"><div class="batch-field-group">${fieldRows}</div></div>`;
  } else {
    // Error state
    const errorMessage = result.error || 'OCR processing failed';
    body = `
      <div class="batch-card-body">
        <div class="batch-error-message" role="alert">
          <svg class="batch-error-icon" width="20" height="20" fill="currentColor">
            <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9 9a1 1 0 112 0v4a1 1 0 11-2 0V9zm1-4a1 1 0 100 2 1 1 0 000-2z"/>
          </svg>
          <span>${this._escapeHtml(errorMessage)}</span>
        </div>
      </div>
    `;
  }

  card.innerHTML = header + body;

  // Attach copy button event listeners
  if (isSuccess) {
    card.querySelectorAll('.btn-copy-field').forEach(btn => {
      btn.addEventListener('click', (e) => this._handleBatchCopyField(e));
    });
  }

  return card;
}
```

#### Method: `_handleBatchCopyField(event)`

**Signature:**
```javascript
/**
 * Handles copy button click for batch result fields
 * @param {Event} event - Click event
 * @private
 */
_handleBatchCopyField(event) {
  // Implementation
}
```

**Behavior Specification:**

**Processing Logic:**
1. Extract value from `data-value` attribute
2. Copy to clipboard using Clipboard API
3. Show toast notification with success/error message
4. Provide visual feedback (button animation)

**Implementation Template:**

```javascript
async _handleBatchCopyField(event) {
  const button = event.currentTarget;
  const value = button.getAttribute('data-value');
  const fieldId = button.getAttribute('data-field-id');

  try {
    await navigator.clipboard.writeText(value);
    this._showToast(`${fieldId.replace('_', ' ')} copied`, 'success');
    
    // Visual feedback
    button.style.transform = 'scale(0.9)';
    setTimeout(() => {
      button.style.transform = 'scale(1)';
    }, 150);
  } catch (error) {
    console.error('Copy failed:', error);
    this._showToast('Failed to copy', 'error');
  }
}
```

#### Helper Method: `_escapeHtml(unsafe)`

**Signature:**
```javascript
/**
 * Escapes HTML special characters
 * @param {string} unsafe - Unsafe string
 * @returns {string} Escaped string
 * @private
 */
_escapeHtml(unsafe) {
  // Implementation
}
```

**Implementation:**
```javascript
_escapeHtml(unsafe) {
  if (typeof unsafe !== 'string') return '';
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
```

## 3. DEPENDENCIES

**This module CALLS:**
- `_extractFieldsFromData()` (existing method in `ocr-panel.js`) - Dual-lookup field extraction
- `_showToast()` (existing method) - User feedback notifications
- `navigator.clipboard.writeText()` (Browser API) - Copy to clipboard

**This module is CALLED BY:**
- Batch upload completion handler in `ocr-panel.js`
- Poll completion callback for batch operations

## 4. DATA STRUCTURES

### OCR Result Object (Expected Format)

```typescript
interface BatchOCRResult {
  success: boolean;
  data?: {
    tracking_id: string;
    order_id: string;
    buyer_name: string;
    receiver_name: string;
    delivery_address: string;
    [key: string]: any; // Other fields
  };
  error?: string;
}
```

## 5. CONSTRAINTS (FROM SYSTEM RULES)

**From `system_constraints.md`:**
- **Function Length:** No JavaScript method may exceed 50 lines of executable code ✓
- **Touch Targets:** All interactive elements must have `min-height: 44px` and `min-width: 44px` ✓
- **Toast Notifications:** All user feedback via toast container, no `alert()` ✓
- **Accessibility:** Modal dialogs must have `role="dialog"`, `aria-labelledby`, `aria-modal="true"` ✓
- **Field Naming:** Backend uses `snake_case`, frontend implements dual-lookup ✓

**From `system_style.md`:**
- **Theme Variables:** CSS custom properties only, no hardcoded hex codes ✓
- **Border Radius:** Large radius (20px-24px for cards, 12px-16px for buttons) ✓
- **Glass Effect:** Backdrop blur (20px) for modals ✓
- **No Blue Accents:** Prohibited in UI elements ✓
- **Bento Grid:** Responsive grid layout ✓
- **Progressive Disclosure:** Content hidden by default, revealed on interaction ✓

## 6. MEMORY COMPLIANCE

**No memory snippet provided** - No specific historical rules to apply.

## 7. ACCEPTANCE CRITERIA

### Test Case 1: Successful Batch Display (Dark Theme)

**Scenario:** User uploads 3 images, all OCR successful

**Input:**
```javascript
[
  {
    success: true,
    data: {
      tracking_id: "ABC123",
      order_id: "ORD-001",
      buyer_name: "John Doe",
      receiver_name: "Jane Smith",
      delivery_address: "123 Main St"
    }
  },
  {
    success: true,
    data: {
      tracking_id: "XYZ789",
      order_id: "ORD-002",
      buyer_name: "Alice Johnson",
      receiver_name: "Bob Wilson",
      delivery_address: "456 Oak Ave"
    }
  },
  {
    success: true,
    data: {
      tracking_id: "DEF456",
      order_id: "ORD-003",
      buyer_name: "Carol White",
      receiver_name: "David Brown",
      delivery_address: "789 Pine Rd"
    }
  }
]
```

**Expected Output:**
- Batch results container displays with glass effect
- 3 cards in bento grid layout
- All cards show green "✓ Success" status
- All 5 fields displayed per card with correct values
- Copy buttons present and functional (44x44px minimum)
- Dark theme colors applied (no hard-coded colors visible)

**Expected Behavior:**
- Container slides in smoothly
- Cards are hoverable (subtle lift effect)
- Copy buttons show hover state
- Toast appears on successful copy

### Test Case 2: Mixed Success/Error Results

**Scenario:** Batch with 2 successful, 1 failed OCR

**Input:**
```javascript
[
  { success: true, data: { tracking_id: "ABC123", /* ... */ } },
  { success: false, error: "Image quality too low" },
  { success: true, data: { tracking_id: "DEF456", /* ... */ } }
]
```

**Expected Output:**
- 3 cards displayed
- Card #1 and #3 show success state with fields
- Card #2 shows error state with message
- Error card has red "✗ Failed" status
- Error message displayed in danger color

**Expected Behavior:**
- Error cards do not have copy buttons
- Error icon visible
- No N/A values in error cards (error message only)

### Test Case 3: Light Theme Toggle

**Scenario:** User switches from dark to light theme while viewing results

**Input:**
- Theme toggle button clicked
- `data-theme` attribute changes to "light"

**Expected Output:**
- All cards immediately update colors
- Background changes from #1A1A1A to #FFFFFF
- Text changes from #F0F0F0 to #1E293B
- Borders adjust to light theme color
- No visual glitches or layout shifts

**Expected Behavior:**
- Transition is smooth (CSS variables respond instantly)
- No JavaScript required for theme update
- All nested elements respect new theme

### Test Case 4: Copy Button Functionality

**Scenario:** User clicks copy button for tracking_id

**Input:**
- Click on copy button with `data-value="ABC123"`

**Expected Output:**
- Clipboard contains "ABC123"
- Toast notification: "tracking id copied" (success)
- Button scales down briefly (visual feedback)

**Expected Behavior:**
- Async operation completes in <200ms
- Error handling if clipboard API unavailable
- Focus remains on button after copy

### Test Case 5: Empty Results Array

**Scenario:** Batch upload completes with no results

**Input:**
```javascript
[]
```

**Expected Output:**
- Container displays
- Message: "No results to display"
- No cards rendered

**Expected Behavior:**
- No errors in console
- Close button still functional

### Test Case 6: Accessibility Compliance

**Scenario:** Keyboard-only navigation

**Input:**
- User presses Tab key repeatedly
- User presses Enter on copy button

**Expected Output:**
- Focus outline visible on all interactive elements
- Tab order: Close button → Card 1 copy buttons → Card 2 copy buttons → ...
- Enter key activates copy functionality

**Expected Behavior:**
- Focus trap within modal
- Escape key closes modal (if implemented)
- Screen reader announces card status and field labels

### Test Case 7: Touch Target Compliance

**Scenario:** Mobile device interaction

**Input:**
- User taps copy button on mobile

**Expected Output:**
- Button responds to touch
- No mis-taps due to small target

**Expected Behavior:**
- All buttons meet 44x44px minimum
- Adequate spacing between touch targets (8px minimum)

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:**
- `frontend/templates/service_dashboard.html`
- `frontend/static/js/ocr-panel.js`

**Contract Reference:** `docs/contracts/batch-results-theme-integration.md` v1.0

## Strict Constraints (NON-NEGOTIABLE)

1. **CSS Variables Only:** No hardcoded hex colors anywhere in the implementation. All color references must use CSS custom properties from theme variables.
2. **50-Line Method Limit:** All JavaScript methods must be ≤50 executable lines. If a method exceeds this, refactor into smaller methods.
3. **Touch Target Compliance:** All interactive elements (buttons, clickable areas) MUST have `min-height: 44px` and `min-width: 44px`.
4. **No `alert()` Usage:** All user feedback via toast notification system only.
5. **Field Name Consistency:** Backend returns `snake_case`. Use `_extractFieldsFromData()` for dual-lookup to handle both `snake_case` and `camelCase`.

## Memory Compliance (MANDATORY)

**No memory snippet provided** - Standard project rules apply.

## Required Logic

### HTML Changes (`service_dashboard.html`)

1. Locate the OCR modal structure (search for `id="ocr-modal"`)
2. After the existing modal content, add the batch results container HTML (Section 2.1)
3. Add the CSS styles inside the `<style>` block or in a separate linked CSS file (Section 2.2)
4. Ensure toast container exists: `<div id="toast-container" class="toast-container" aria-live="polite"></div>`

### JavaScript Changes (`ocr-panel.js`)

1. **Refactor `_displayBatchResults` method:**
   - Replace existing implementation with contract-specified version
   - Use `_createBatchResultCard()` helper for card generation
   - Ensure container visibility management
   
2. **Add `_createBatchResultCard` method:**
   - Implement field mapping using `_extractFieldsFromData()`
   - Generate HTML with proper ARIA attributes
   - Handle success/error states
   - Attach copy button event listeners
   
3. **Add `_handleBatchCopyField` method:**
   - Implement clipboard copy with async/await
   - Show toast notifications for success/error
   - Add visual feedback animation
   
4. **Add `_escapeHtml` helper method:**
   - Prevent XSS by escaping HTML special characters
   
5. **Add close button handler:**
   - Implement `_closeBatchResults()` to hide container
   - Attach to `#btn-close-batch` click event

### Integration Points

- **Must call:** `_extractFieldsFromData()` for each successful OCR result
- **Must call:** `_showToast()` for copy success/error notifications
- **Will be called by:** Batch upload completion handler (existing polling mechanism)

## Success Criteria

- All methods match contract signatures exactly
- All test cases pass (Section 7)
- Theme toggle works without JavaScript intervention (pure CSS)
- No console errors during batch display
- Auditor approval required before merge

## Files You Should Create

1. Updated `service_dashboard.html` with new HTML structure and CSS
2. Updated `ocr-panel.js` with new/modified methods
3. Test file demonstrating all 7 acceptance criteria

---

## POST-ACTION REPORT

```
✅ **Contract Created:** `docs/contracts/batch-results-theme-integration.md` v1.0
📋 **Work Order Generated:** (above)
```

### ⏭️ HUMAN WORKFLOW CHECKPOINT

**Status:** Contract design complete. Ready for implementation phase.

**Files You Should Have:**

- ✅ `docs/contracts/batch-results-theme-integration.md` v1.0 - The formal contract
- ✅ Work order (above) - Instructions for implementer
- ✅ API Map snippet (above) - Ready to paste

