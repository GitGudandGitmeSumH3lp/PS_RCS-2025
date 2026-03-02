# CONTRACT: Frontend Variable Speed Control
**Version:** 1.0
**Last Updated:** 2026-03-03
**Status:** Draft
**Target File:** `frontend/static/js/dashboard-core.js` + `frontend/templates/service_dashboard.html`
**Spec Source:** `specs/19_frontend_speed_control.md`

---

## 1. PURPOSE

This module formalizes the interface changes required to upgrade the motor speed control system from a raw 0–100 pass-through to a semantically correct 0–100% → 0–255 PWM mapping. It introduces a new `runSpeedRamp()` public method for automated verification of the speed scaling logic, adds a "Run Speed Ramp" button to the motor control modal UI, and updates slider labels to expose percentage units to the operator. All changes are contained to the frontend layer; the backend `/api/motor/control` endpoint remains unchanged.

---

## 2. PUBLIC INTERFACE

---

### Method: `_sendMotorCommand` *(MODIFIED)*
**Location:** `DashboardCore` class, `dashboard-core.js`

**Signature:**
```javascript
/**
 * Sends a directional motor command to the backend with PWM-scaled speed.
 * Reads the speed-slider (0–100) and maps it to 0–255 PWM before transmission.
 *
 * @param {string} direction - One of: 'forward', 'backward', 'left', 'right', 'stop'
 * @returns {void}
 * @private
 */
_sendMotorCommand(direction) { ... }
```

**Behavior Specification:**

- **Input Validation:** `direction` must be a non-empty string. No silent coercion.
- **Processing Logic:**
  1. Read `document.getElementById('speed-slider').value` as integer (fallback: `50`).
  2. Compute `pwmValue = Math.round((sliderVal / 100) * 255)`.
  3. For `direction === 'stop'`: override `pwmValue` to `0` unconditionally.
  4. POST JSON payload `{ command: direction, speed: pwmValue }` to `${this.apiBase}/api/motor/control`.
- **Output Guarantee:** No return value. Side effect is the HTTP POST.
- **Side Effects:** Outbound `fetch()` POST to `/api/motor/control`.

**Error Handling:**

- **Fetch failure:** `.catch(err => ...)` must call `this._showToast('Motor command failed', 'error')` — NOT `console.error` only. *(Constraint: system_constraints.md §5.1 — no silent failures.)*

**Performance Requirements:**

- Time Complexity: O(1)
- Space Complexity: O(1)

---

### Method: `runSpeedRamp` *(NEW)*
**Location:** `DashboardCore` class, `dashboard-core.js`

**Signature:**
```javascript
/**
 * Executes an automated 4-step speed ramp test (25%, 50%, 75%, 100%) to
 * verify PWM scaling logic. Each step runs for a fixed duration, then stops.
 * Disables the trigger button for the duration to prevent re-entry.
 *
 * @returns {Promise<void>}
 */
async runSpeedRamp() { ... }
```

**Behavior Specification:**

- **Input Validation:** None (no parameters). Guard against concurrent invocation via `this._rampInProgress` flag.
- **Processing Logic:**
  1. If `this._rampInProgress === true`, call `this._showToast('Speed ramp already running', 'warning')` and return immediately.
  2. Set `this._rampInProgress = true`.
  3. Disable `#btn-speed-ramp` button (set `disabled = true`).
  4. Show toast: `'⚡ Speed ramp starting…'` (type: `'info'`).
  5. Iterate steps `[25, 50, 75, 100]`:
     a. Compute `pwm = Math.round((pct / 100) * 255)`.
     b. POST `{ command: 'forward', speed: pwm }` to `/api/motor/control`.
     c. Await 800 ms.
  6. POST `{ command: 'stop', speed: 0 }` to `/api/motor/control`.
  7. Show toast: `'✅ Speed ramp complete'` (type: `'success'`).
  8. Re-enable `#btn-speed-ramp`. Set `this._rampInProgress = false`.
- **Output Guarantee:** Motors return to stop state after test unconditionally (use `finally` block).
- **Side Effects:** Multiple sequential outbound POSTs. Temporarily disables UI button. Emits toasts.

**Error Handling:**

- **Any fetch failure during ramp:** Catch in `try/catch`. Call `this._showToast('Speed ramp failed: ' + err.message, 'error')`. Execute stop command in `finally` regardless.
- **Button element missing from DOM:** Log warning via `console.warn()` and continue — do not throw.

**Performance Requirements:**

- Total wall-clock duration: ~3200 ms (4 steps × 800 ms).
- Each individual fetch must complete or fail within the 800 ms window; no serial await-chaining on fetch responses (fire-and-forget per step is acceptable).

---

### Method: `_setupControls` *(MODIFIED)*
**Location:** `DashboardCore` class, `dashboard-core.js`

**Signature:**
```javascript
/**
 * Initialises motor control UI: speed slider gradient, directional buttons,
 * apply button, and the new speed ramp trigger button.
 *
 * @returns {void}
 * @private
 */
_setupControls() { ... }
```

**Behavior Specification:**

- **Existing behavior preserved:** Slider gradient update, `dir-btn` listeners, `apply-controls` button — no changes.
- **New binding (addendum only):**
  1. Query `document.getElementById('btn-speed-ramp')`.
  2. If element exists, attach `addEventListener('click', () => this.runSpeedRamp())`.
  3. If element is missing, log `console.warn('btn-speed-ramp not found — speed ramp feature disabled')` and continue without error.
- **Output Guarantee:** Returns void. All bindings idempotent (called once on init).
- **Side Effects:** DOM event listener registration.

**Error Handling:** Missing DOM elements must never throw. Use guard clauses.

---

## 3. DEPENDENCIES

**This module CALLS:**
- `POST /api/motor/control` — Existing endpoint. No changes required to backend.
- `this._showToast(message: string, type: string)` — Existing toast utility within `DashboardCore` or its host page. *(See Constraint §5 — toast system is mandatory.)*

**This module is CALLED BY:**
- `DashboardCore._setupControls()` → binds `runSpeedRamp` to `#btn-speed-ramp`
- `DashboardCore.handleKeyDown()` / `handleKeyUp()` → calls `_sendMotorCommand` (existing, unchanged calling pattern)
- `DashboardCore.setupModalInteractions()` → calls `_setupControls()` (unchanged)

**No new external libraries required.**

---

## 4. DATA STRUCTURES

### PWM Scaling Formula (Canonical Definition)
```
pwmValue: number = Math.round((sliderPercent / 100) * 255)
```
Where `sliderPercent ∈ [0, 100]` (integer) and `pwmValue ∈ [0, 255]` (integer).

| Slider % | Expected PWM |
|----------|-------------|
| 0        | 0           |
| 25       | 64          |
| 50       | 128 (spec allows ~127–128) |
| 75       | 191         |
| 100      | 255         |

### State Flag
```javascript
this._rampInProgress: boolean  // Added to DashboardCore constructor, default: false
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

- **§4 — Max Function Length:** `runSpeedRamp()` must not exceed 50 lines of executable code. The ramp loop body is simple enough to comply; no refactor needed.
- **§5.1 — No Silent Failures:** Every `fetch()` in `_sendMotorCommand` and `runSpeedRamp` must surface errors via the toast notification system. `console.error` alone is a violation.
- **§5.2 — Toast Container Required:** `service_dashboard.html` must contain `<div id="toast-container" class="toast-container" aria-live="polite"></div>`. Verify before implementation.
- **§5.6 — No Direct Modification Rule Override:** This feature *requires* direct modification of `dashboard-core.js` because it modifies `_sendMotorCommand` (an existing method) and adds `runSpeedRamp` as a `DashboardCore` method. The constraint in §5.6 applies to *new panel features*. This is a core motor command change. **Direct modification of `dashboard-core.js` is therefore explicitly approved for this contract.**
- **§3 — API Protocol:** Payload must remain `{ command: string, speed: number }` with `Content-Type: application/json`. The backend `motor_controller.py` expects integer 0–255 for `speed`.

---

## 6. MEMORY COMPLIANCE

No `_memory_snippet.txt` was provided for this session. No project-memory rules to apply beyond system_constraints.md. Mark as N/A.

**Applied Rules:** N/A (no memory snippet provided)

---

## 7. HTML INTERFACE CONTRACT (`service_dashboard.html`)

The following HTML changes are required inside the Motor Control Modal (`#controlModal`).

### 7.1 Slider Label Update

**Target element:** `<span id="speed-value">`
**Current behavior:** Displays raw number (e.g., `50`)
**Required behavior:** Displays percentage (e.g., `50%`)

The `_setupControls()` method already appends `%` via `speedValue.textContent = \`${val}%\``. Verify the `<span>` initial value in HTML also includes `%`:

```html
<!-- BEFORE -->
<span id="speed-value">50</span>

<!-- AFTER -->
<span id="speed-value">50%</span>
```

### 7.2 Speed Ramp Button

**Location:** Inside `.modal-body` of `#controlModal`, within or adjacent to the existing `.control-group` for the speed slider.

```html
<!-- Speed Ramp Test Control — ADD BELOW SLIDER GROUP -->
<div class="test-controls" style="margin-top: 10px;">
    <button
        id="btn-speed-ramp"
        class="btn-ghost btn-sm"
        type="button"
        aria-label="Run automated speed ramp test"
        style="min-height: 44px; min-width: 44px;">
        ⚡ Run Speed Ramp
    </button>
</div>
```

**Constraints:**
- `type="button"` is mandatory (prevents form submission in older browsers).
- `min-height: 44px` and `min-width: 44px` are mandatory per §5.2 WCAG touch target rules.
- Must use `<button>` element, not `<div>`. (§5.3)
- ID must be kebab-case: `btn-speed-ramp`. (§5.3)

### 7.3 Optional: Stall Zone Visual Hint (CSS)

Per spec Open Question resolution: `min="0"` is kept. A CSS gradient background on the slider may visually indicate the stall zone (0–20%). This is cosmetic and non-blocking for v1.0. Implementer may add it as an enhancement, but it is NOT a contract requirement.

---

## 8. ACCEPTANCE CRITERIA

### Test Case 1: Full-scale PWM mapping
- **Scenario:** User sets slider to 100% and presses a directional key.
- **Input:** `speed-slider.value = 100`, `direction = 'forward'`
- **Expected POST Body:** `{ "command": "forward", "speed": 255 }`
- **Pass Condition:** Backend receives `speed: 255`.

### Test Case 2: Half-scale PWM mapping
- **Scenario:** User sets slider to 50% and clicks a direction button.
- **Input:** `speed-slider.value = 50`, `direction = 'left'`
- **Expected POST Body:** `{ "command": "left", "speed": 128 }`
- **Pass Condition:** `speed` is `127` or `128` (floating point rounding tolerance ±1).

### Test Case 3: Zero speed / full stop
- **Scenario:** Key released → stop command issued.
- **Input:** `direction = 'stop'`
- **Expected POST Body:** `{ "command": "stop", "speed": 0 }`
- **Pass Condition:** `speed` is always `0` regardless of slider position.

### Test Case 4: Speed ramp sequence
- **Scenario:** Operator clicks "⚡ Run Speed Ramp".
- **Expected POST sequence (in order):**
  1. `{ command: 'forward', speed: 64 }` → wait 800 ms
  2. `{ command: 'forward', speed: 128 }` → wait 800 ms
  3. `{ command: 'forward', speed: 191 }` → wait 800 ms
  4. `{ command: 'forward', speed: 255 }` → wait 800 ms
  5. `{ command: 'stop', speed: 0 }`
- **Pass Condition:** All 5 calls made in order. Button disabled during sequence. Toast shown at start and end.

### Test Case 5: Concurrent ramp guard
- **Scenario:** Operator clicks "⚡ Run Speed Ramp" twice rapidly.
- **Input:** Two rapid clicks on `#btn-speed-ramp`
- **Expected Behavior:** Second click is ignored. Toast: `'Speed ramp already running'` (type: `'warning'`).
- **Pass Condition:** Only one ramp sequence runs. Motors stop once after a single complete ramp.

### Test Case 6: Fetch failure during ramp
- **Scenario:** Network error on step 2 of ramp.
- **Expected Behavior:** Error toast fires. `finally` block ensures stop command is attempted. `_rampInProgress` reset to `false`. Button re-enabled.
- **Pass Condition:** UI is not locked after failure.

---

## 9. OUT OF SCOPE

- Backend changes to `motor_controller.py` — already accepts 0–255.
- Slider `min` value change — kept at `0` per Analyst decision.
- PaddleOCR, LiDAR, or camera modules — unrelated.
- Auto mode speed control — separate feature.