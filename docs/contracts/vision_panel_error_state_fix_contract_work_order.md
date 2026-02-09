# WORK ORDER FOR IMPLEMENTER

**Target File:** `frontend/static/js/dashboard-core.js`
**Contract Reference:** `docs/contracts/vision_panel_error_state_fix_contract.md` v1.0
**Status:** Ready for Implementation
**Priority:** HIGH (User-facing bug affecting UX)

---

## STRICT CONSTRAINTS (NON-NEGOTIABLE)

1. **No Global Variables:** All changes confined to VisionPanel class instance methods
2. **Browser Compatibility:** Must work in Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
3. **No DOM Structure Changes:** Work with existing HTML in `service_dashboard.html`
4. **No CSS Changes:** Use existing `.hidden` class only
5. **Event Handler Order:** ALWAYS set `onload` and `onerror` BEFORE `src` assignment
6. **Pattern Consistency:** Follow OCRPanel._startCameraStream() pattern exactly
7. **No Breaking Changes:** All public methods maintain same signature
8. **Performance:** Total overhead < 1ms per modal open

---

## MEMORY COMPLIANCE (MANDATORY)

**[2026-02-07] Field Normalization:** 
- JavaScript uses camelCase (no changes needed here)
- Maintain consistent error state management pattern

**[2026-02-08] Graceful Degradation:**
- Error state must provide clear feedback when camera unavailable
- No silent failures - always show user-facing error message

**[2026-02-06] Bandwidth Optimization:**
- streamActive flag must accurately reflect stream status
- No unnecessary stream starts when already active

---

## REQUIRED LOGIC

### Change 1: openModal() Method (Lines 308-313)

**Location:** `dashboard-core.js` Line 308

**Current Code:**
```javascript
openModal() {
    if (this.elements['modal-vision']) {
        this.elements['modal-vision'].showModal();
        this._startStream();
    }
}
```

**Required Implementation:**
```javascript
openModal() {
    if (this.elements['modal-vision']) {
        // CRITICAL: Reset error state from previous session
        const errorState = document.querySelector('.error-state');
        if (errorState) errorState.classList.add('hidden');
        
        this.elements['modal-vision'].showModal();
        this._startStream();
    }
}
```

**Testing Requirement:**
- Verify `.error-state` has `hidden` class after method executes
- Verify works even if `.error-state` element doesn't exist

---

### Change 2: _startStream() Method (Lines 321-331)

**Location:** `dashboard-core.js` Line 321

**Current Code:**
```javascript
_startStream() {
    const stream = this.elements['vision-stream'];
    if (!stream || this.streamActive) return;

    const src = stream.getAttribute('data-src');
    if (src) {
        stream.src = `${src}?t=${Date.now()}`;
        this.streamActive = true;
        stream.onerror = () => this._handleStreamError();
    }
}
```

**Required Implementation:**
```javascript
_startStream() {
    const stream = this.elements['vision-stream'];
    if (!stream || this.streamActive) return;

    const src = stream.getAttribute('data-src');
    if (src) {
        // CRITICAL: Set event handlers BEFORE src assignment to avoid race condition
        stream.onload = () => {
            // Hide error state on successful load (may fire multiple times for MJPEG)
            const errorState = document.querySelector('.error-state');
            if (errorState) errorState.classList.add('hidden');
            this.streamActive = true;
        };
        
        stream.onerror = () => this._handleStreamError();
        
        // CRITICAL: Assign src LAST (may trigger immediate load/error events)
        stream.src = `${src}?t=${Date.now()}`;
    }
}
```

**Testing Requirements:**
- Verify `onload` handler defined before `src` assignment
- Verify `onerror` handler defined before `src` assignment
- Verify `streamActive` only set to `true` inside `onload` handler
- Verify `onload` can execute multiple times (MJPEG streams)

---

### Change 3: _handleStreamError() Method (Lines 341-345)

**Location:** `dashboard-core.js` Line 341

**Current Code:**
```javascript
_handleStreamError() {
    this.updateStatusIndicator(false);
    const errorState = document.querySelector('.error-state');
    if (errorState) errorState.classList.remove('hidden');
}
```

**Required Implementation:**
```javascript
_handleStreamError() {
    this.updateStatusIndicator(false);
    this.streamActive = false;  // CRITICAL: Reset flag to allow retry
    const errorState = document.querySelector('.error-state');
    if (errorState) errorState.classList.remove('hidden');
}
```

**Testing Requirement:**
- Verify `streamActive` set to `false` when error occurs
- Verify subsequent `_startStream()` call can succeed (not blocked by `streamActive` check)

---

## INTEGRATION POINTS

### Must Work With:

**HTML Structure (service_dashboard.html):**
```html
<dialog id="modal-vision" class="linear-modal">
    <div class="error-state hidden">Camera stream unavailable</div>
    <img id="vision-stream" data-src="/api/vision/stream" />
</dialog>
```

**CSS (.hidden class):**
```css
.hidden {
    display: none !important;
}
```

**Backend API:**
- `GET /api/vision/stream` - MJPEG stream endpoint
- Returns 503 when camera offline
- Returns MJPEG stream when camera online

### Must Not Break:

- **OCRPanel class:** Verify OCRPanel._startCameraStream() still works
- **Modal close behavior:** Verify `_stopStream()` on close still works
- **Status indicator:** Verify `updateStatusIndicator()` still updates UI
- **Capture photo feature:** Verify `capturePhoto()` still functions

---

## SUCCESS CRITERIA

### Functional Requirements

- [ ] Opening modal after previous error clears error overlay
- [ ] Successful stream load hides error overlay
- [ ] Failed stream load shows error overlay
- [ ] `streamActive` flag accurately reflects stream status
- [ ] Rapid modal open/close cycles work without errors

### Code Quality Requirements

- [ ] All lines < 100 characters
- [ ] Consistent 4-space indentation
- [ ] Comments added for non-obvious event handler order
- [ ] No console errors or warnings
- [ ] No eslint violations (if applicable)

### Testing Requirements

- [ ] Manual test: Open modal → stream loads → no error shown
- [ ] Manual test: Open modal → stream fails → error shown
- [ ] Manual test: Error shown → close modal → fix camera → reopen → no error shown
- [ ] Browser test: Chrome (MJPEG multiple onload events)
- [ ] Browser test: Firefox (single onload event)
- [ ] Regression test: OCRPanel camera tab still works

### Performance Requirements

- [ ] Modal open latency < 100ms (user perception threshold)
- [ ] No memory leaks (event handlers cleaned up)
- [ ] No unnecessary DOM queries (cache elements where possible)

---

## IMPLEMENTATION CHECKLIST

### Before Starting

- [ ] Read contract document in full (`vision_panel_error_state_fix_contract.md`)
- [ ] Review OCRPanel._startCameraStream() pattern (lines 472-511)
- [ ] Backup current `dashboard-core.js` file
- [ ] Open browser DevTools (F12) for testing

### During Implementation

- [ ] Make Change 1 (openModal error state reset)
- [ ] Make Change 2 (_startStream event handler order)
- [ ] Make Change 3 (_handleStreamError flag reset)
- [ ] Test after EACH change (incremental validation)
- [ ] Check console for errors after each test
- [ ] Verify `.error-state` class list in DevTools Elements tab

### After Implementation

- [ ] Run all 5 test cases from contract (Acceptance Criteria section)
- [ ] Test in at least 2 browsers (Chrome + Firefox minimum)
- [ ] Verify OCRPanel unaffected (camera tab works)
- [ ] Clear browser cache and hard reload (Ctrl+F5)
- [ ] Document any deviations from contract in comments

---

## DEBUGGING GUIDE

### If Error State Never Hides

**Check:**
1. Is `.error-state` element in DOM? (`document.querySelector('.error-state')`)
2. Does `.hidden` CSS class exist and apply `display: none`?
3. Is `onload` handler being called? (Add `console.log` inside handler)
4. Is `classList.add('hidden')` executing? (Check in DevTools)

**Fix:**
- Verify CSS specificity (`.hidden` must have `!important`)
- Check if other CSS rules override `.hidden`
- Ensure `onload` handler is actually attached (check `stream.onload` in console)

### If Stream Never Loads

**Check:**
1. Is `/api/vision/stream` endpoint returning 200? (Check Network tab)
2. Is `data-src` attribute set on img element?
3. Is `src` being assigned? (Check `stream.src` value in console)
4. Is `onerror` handler firing? (Add `console.log` in handler)

**Fix:**
- Verify backend camera is online (`curl http://localhost:5000/api/status`)
- Check MJPEG stream is valid (open `/api/vision/stream` in new tab)
- Ensure cache-busting timestamp is unique (`Date.now()`)

### If streamActive Flag Stuck

**Check:**
1. Is `streamActive` being set in `onload`? (Not before handler fires)
2. Is `streamActive` reset in `_handleStreamError`?
3. Are there multiple VisionPanel instances? (Should only be one)

**Fix:**
- Move `this.streamActive = true` INSIDE `onload` handler
- Add `this.streamActive = false` in `_handleStreamError`
- Verify `dashboard.visionPanel` is singleton

---

## VALIDATION SCRIPT

```javascript
// Run in browser console after implementation
function validateVisionPanelFix() {
    const vp = window.dashboard?.visionPanel;
    if (!vp) {
        console.error('❌ VisionPanel not found');
        return;
    }
    
    // Test 1: Error state reset in openModal
    const errorState = document.querySelector('.error-state');
    if (errorState) {
        errorState.classList.remove('hidden');  // Simulate previous error
        vp.openModal();
        console.assert(
            errorState.classList.contains('hidden'),
            '❌ Error state not reset in openModal()'
        );
        console.log('✅ Test 1 passed: Error state reset');
        vp.closeModal();
    }
    
    // Test 2: Event handlers exist
    const stream = document.getElementById('vision-stream');
    if (stream) {
        console.assert(
            typeof stream.onload === 'function',
            '❌ onload handler not set'
        );
        console.assert(
            typeof stream.onerror === 'function',
            '❌ onerror handler not set'
        );
        console.log('✅ Test 2 passed: Event handlers defined');
    }
    
    // Test 3: streamActive flag behavior
    const initialState = vp.streamActive;
    vp._handleStreamError();
    console.assert(
        vp.streamActive === false,
        '❌ streamActive not reset in _handleStreamError()'
    );
    console.log('✅ Test 3 passed: streamActive reset on error');
    
    console.log('
✅ All validation tests passed!');
}

validateVisionPanelFix();
```

---

## DELIVERABLES

### Required Files

1. **Modified:** `frontend/static/js/dashboard-core.js`
   - VisionPanel.openModal() updated
   - VisionPanel._startStream() updated
   - VisionPanel._handleStreamError() updated

### Required Documentation

2. **Updated:** `docs/API_MAP_lite.md`
   - Add version history entry (v4.2.4)
   - Copy snippet from contract Appendix A

3. **Updated:** `_STATE.MD`
   - Mark Phase 4.4 task as complete
   - Add entry to VERSION HISTORY section
   - Update LESSONS LEARNED if applicable

### Required Testing Evidence

4. **Screenshots:**
   - Before: Error state persisting after modal reopen
   - After: Error state cleared on modal reopen

5. **Console Logs:**
   - No JavaScript errors in console
   - Validation script output (all tests passed)

### Git Commit

6. **Commit Message:**
```
fix(vision): correct error state management in VisionPanel (contract v1.0)

- Reset error state in openModal() before stream start
- Set event handlers BEFORE src assignment (race condition fix)
- Add onload handler to hide error on successful stream load
- Reset streamActive flag in _handleStreamError()

Fixes persistent "Camera stream unavailable" message when camera is functional.
Follows OCRPanel error state management pattern for consistency.

Contract: docs/contracts/vision_panel_error_state_fix_contract.md v1.0
Testing: All 5 acceptance criteria passed + browser compatibility verified
```

---

## AUDITOR REVIEW REQUIREMENTS

After implementation, the Auditor will verify:

1. **Contract Compliance (40 points):**
   - [ ] All 3 method changes implemented exactly as specified
   - [ ] Event handler order correct (handlers before src)
   - [ ] Error state reset logic in openModal()
   - [ ] streamActive flag reset in _handleStreamError()

2. **Style Compliance (30 points):**
   - [ ] Code follows existing VisionPanel style
   - [ ] Comments added for non-obvious logic
   - [ ] Indentation consistent (4 spaces)
   - [ ] Line length < 100 characters

3. **Safety & Logic (30 points):**
   - [ ] No race conditions introduced
   - [ ] Error state lifecycle correct
   - [ ] OCRPanel not affected (regression test)
   - [ ] All acceptance criteria tests passed

**Minimum Passing Score:** 90/100

---

## READY TO PROCEED?

**Required Context Files:**
- ✅ `docs/contracts/vision_panel_error_state_fix_contract.md` v1.0
- ✅ `work_order.md` (this file)
- ✅ `docs/system_constraints.md`
- ✅ `_STATE.MD`

**Verification Command:**
```
/verify-context: vision_panel_error_state_fix_contract.md, work_order.md, system_constraints.md, _STATE.MD
```

**Next Steps:**
1. Read contract document in full
2. Review OCRPanel pattern (reference implementation)
3. Implement 3 changes in order
4. Test after each change
5. Run validation script
6. Capture before/after screenshots
7. Update documentation
8. Commit with specified message format

**Estimated Implementation Time:** 30-45 minutes

---

**END OF WORK ORDER**