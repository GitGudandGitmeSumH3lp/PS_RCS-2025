# WORK ORDER FOR IMPLEMENTER

**Target File:** `src/services/vision_manager.py`  
**Contract Reference:** `docs/contracts/vision_manager_stream_fix.md` v1.0  
**Estimated Effort:** 5 minutes (single 3-line change)  
**Risk Level:** MINIMAL (backward-compatible property fix)

---

## STRICT CONSTRAINTS (NON-NEGOTIABLE)

1. **Single File Modification:** ONLY modify `src/services/vision_manager.py` - no other files
2. **Line-Specific Change:** Modify ONLY lines 29-35 (the `stream` property)
3. **No New Dependencies:** Do NOT add any imports
4. **No Signature Changes:** Do NOT modify property decorator or return type
5. **Preserve Docstring:** Do NOT alter the docstring text
6. **Thread Safety:** Do NOT add locks (property is read-only and thread-safe by design)

---

## MEMORY COMPLIANCE (MANDATORY)

### [2026-02-08] Camera HAL Integration
**Rule:** Preserve VisionManager's public API during HAL refactoring  
**Application:** The `stream` property is part of backward-compatibility interface - maintain signature exactly

### [2026-02-08] Backward Compatibility
**Rule:** Zero-breaking changes to API server interface  
**Application:** Property must still return provider/None (no new return types or exceptions)

---

## REQUIRED LOGIC

### Step 1: Locate the Broken Property (Lines 29-35)

Find this code block:
```python
@property
def stream(self) -> Any:
    """Backward compatibility property for API server checks.
    
    Returns:
        The provider if running (truthy), else None.
    """
    if self.provider and getattr(self.provider, 'is_running', False):  # ❌ REMOVE THIS LINE
        return self.provider
    return None
```

### Step 2: Replace the Conditional Check

**DELETE:**
```python
    if self.provider and getattr(self.provider, 'is_running', False):
```

**INSERT:**
```python
    if self.provider and self.capture_thread and self.capture_thread.is_alive():
```

### Step 3: Verify Complete Property After Change

The final property should look EXACTLY like this:
```python
@property
def stream(self) -> Any:
    """Backward compatibility property for API server checks.
    
    Returns:
        The provider if running (truthy), else None.
    """
    if self.provider and self.capture_thread and self.capture_thread.is_alive():
        return self.provider
    return None
```

---

## INTEGRATION POINTS

### Must NOT Break:
- **File:** `src/api/server.py` - Line 231
  - **Current Code:** `if self.vision_manager.stream is None:`
  - **Expected:** Continues working without modification

- **File:** `src/api/server.py` - Line 13
  - **Current Code:** `camera_online = bool(self.vision_manager.stream)`
  - **Expected:** Now returns `True` when camera operational (was always `False`)

### Depends On (DO NOT MODIFY):
- `VisionManager.provider` - Initialized in `start_capture()` line 63
- `VisionManager.capture_thread` - Created in `start_capture()` line 72
- Thread lifecycle managed by existing `start_capture()` / `stop_capture()` methods

---

## SUCCESS CRITERIA

### Pre-Implementation Verification

1. **Confirm Bug Exists:**
   ```bash
   # Start server and check camera status
   curl http://localhost:5000/api/status | jq '.camera_connected'
   # Should output: false (BUG - camera is actually online)
   
   curl -I http://localhost:5000/api/vision/stream
   # Should output: 503 Service Unavailable (BUG)
   ```

2. **Document Current State:**
   - Take screenshot of dashboard showing "Camera offline" message
   - Save curl output showing `camera_connected: false`

### Post-Implementation Verification

1. **Syntax Check:**
   ```bash
   python -m py_compile src/services/vision_manager.py
   echo $?  # Must be 0
   ```

2. **Functionality Test:**
   ```bash
   # Restart server
   python src/main.py
   
   # Verify status endpoint shows camera online
   curl http://localhost:5000/api/status | jq '.camera_connected'
   # Must output: true ✅
   
   # Verify stream endpoint returns 200 OK
   curl -I http://localhost:5000/api/vision/stream
   # Must output: HTTP/1.1 200 OK ✅
   # Must output: Content-Type: multipart/x-mixed-replace; boundary=frame ✅
   ```

3. **Manual Dashboard Test:**
   - Open browser to `http://localhost:5000`
   - Click "Vision" tab
   - **Expected:** Live camera feed visible (not "Camera offline")
   - Click "OCR Scanner" button
   - **Expected:** Live Camera tab shows active stream

4. **Regression Test (Python REPL):**
   ```python
   from src.services.vision_manager import VisionManager
   import time
   
   vm = VisionManager()
   
   # Test 1: Before start
   assert vm.stream is None, "FAIL: stream should be None before start"
   
   # Test 2: After start
   vm.start_capture(640, 480, 30)
   time.sleep(0.5)
   assert vm.stream is not None, "FAIL: stream should be provider when running"
   
   # Test 3: After stop
   vm.stop_capture()
   time.sleep(0.1)
   assert vm.stream is None, "FAIL: stream should be None after stop"
   
   print("✅ All regression tests passed!")
   ```

---

## TESTING REQUIREMENTS

### Minimum Tests to Pass Before Deployment

| Test Case | Description | Pass Criteria |
|-----------|-------------|---------------|
| TC-1 | Stream property when camera running | Returns provider instance (truthy) |
| TC-2 | Stream property before start_capture() | Returns None |
| TC-3 | Stream property after stop_capture() | Returns None |
| TC-4 | API /api/vision/stream endpoint | Returns 200 OK with MJPEG stream |
| TC-5 | API /api/status endpoint | Returns `camera_connected: true` |

**All 5 tests MUST pass before marking work order complete.**

---

## ROLLBACK PROCEDURE

If ANY regression detected:

1. **Immediate Revert:**
   ```bash
   git checkout HEAD -- src/services/vision_manager.py
   sudo systemctl restart ps-rcs-api
   ```

2. **Document Failure:**
   - Exact error message
   - Python version: `python --version`
   - Thread state: Provide `vm.capture_thread.is_alive()` output
   - Provider type: Provide `type(vm.provider).__name__` output

3. **Notify Architect:**
   - Include all documentation from step 2
   - Attach server logs showing failure
   - Reference this work order and contract v1.0

---

## COMMON PITFALLS TO AVOID

### ❌ DO NOT Do This:
```python
# WRONG: Adding unnecessary complexity
if self.provider:
    if self.capture_thread:
        if self.capture_thread.is_alive():
            return self.provider
return None

# WRONG: Checking provider internals
if self.provider and self.provider.camera is not None:
    return self.provider

# WRONG: Adding new attributes
if self.provider and self._is_running:  # Don't create new flags
    return self.provider

# WRONG: Calling methods in property
if self.provider and self.get_frame() is not None:  # Too slow
    return self.provider
```

### ✅ DO This (Correct):
```python
# CORRECT: Simple AND chain with thread check
if self.provider and self.capture_thread and self.capture_thread.is_alive():
    return self.provider
return None
```

---

## DELIVERABLES

### Files to Modify
- [x] `src/services/vision_manager.py` (lines 29-35 only)

### Files to Create
- [ ] None (fix-only work order)

### Documentation Updates
After successful implementation:
- [ ] Update `docs/API_MAP_lite.md` - Add v4.2.3 entry (see contract Appendix A)
- [ ] Update `_STATE.MD` - Mark fix complete under Phase 4.4
- [ ] Mark contract status: `docs/contracts/vision_manager_stream_fix.md` → "Status: Implemented"

### Git Commit Message Template
```
fix(vision): correct stream property camera detection

- Replace non-existent provider.is_running check with capture_thread.is_alive()
- Fixes 503 errors on /api/vision/stream endpoint
- Resolves camera_connected reporting false negatives
- Contract: docs/contracts/vision_manager_stream_fix.md v1.0

Closes: PS-RCS-ISSUE-001 (CSI Camera Stream 503 Error)
```

---

## ESTIMATED TIMELINE

| Phase | Duration | Notes |
|-------|----------|-------|
| Pre-verification | 5 min | Confirm bug exists, take screenshots |
| Code change | 2 min | Single 3-line modification |
| Syntax check | 1 min | `py_compile` verification |
| Restart server | 1 min | Apply changes |
| Post-verification | 10 min | Run all 5 test cases |
| Regression tests | 5 min | Python REPL lifecycle tests |
| Documentation | 10 min | Update API_MAP and _STATE.MD |
| **TOTAL** | **34 min** | Includes buffer for manual testing |

---

## APPROVAL CHECKLIST

### Before Submitting to Auditor

- [ ] Syntax validation passed (`py_compile`)
- [ ] All 5 test cases passed (see table above)
- [ ] Regression tests passed (3 lifecycle cycles)
- [ ] Pre/post verification documented (screenshots + curl outputs)
- [ ] No other files modified (only `vision_manager.py`)
- [ ] Git commit message follows template
- [ ] Documentation updated (`API_MAP_lite.md`, `_STATE.MD`)
- [ ] Contract marked "Status: Implemented"

### Auditor Approval Required For:
- Deployment to production
- Closing related issue/ticket
- Archiving contract as "Approved"

---

**END OF WORK ORDER**