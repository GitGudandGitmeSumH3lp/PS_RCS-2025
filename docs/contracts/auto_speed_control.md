# CONTRACT: Frontend‑Controlled Autonomous Speed
**Version:** 1.0
**Last Updated:** 2026‑03‑03
**Status:** Draft
**Spec Source:** `specs/20_Frontend_Controlled_Autonomous_Speed.md`

---

## 1. PURPOSE

This contract formalizes the interface changes required to expose the autonomous obstacle‑avoidance speed to the frontend operator. Currently the avoidance loop runs at a hardcoded speed of `30` PWM (~12% of max). This feature replaces that constant with a configurable `auto_speed` attribute on `HardwareManager`, surfaced via two new API endpoints (`GET/POST /api/auto/speed`), and controlled through a dedicated slider added to the Motor Control Modal in the dashboard UI. Manual mode speed control is explicitly **out of scope** and must remain untouched.

---

## 2. PUBLIC INTERFACE — BACKEND

---

### Class: `HardwareManager` *(MODIFIED)*
**Location:** `src/hardware/hardware_manager.py`

#### 2.1 New Attribute: `auto_speed`

```python
# Added inside __init__
self.auto_speed: int = 30  # Default: 30 PWM (~12% of max). Range: 0–255.
```

**Invariant:** `0 <= self.auto_speed <= 255` at all times. No code path may set this attribute directly outside `set_auto_speed()`.

---

#### 2.2 New Method: `get_auto_speed`

**Signature:**
```python
def get_auto_speed(self) -> int:
    """Returns the current autonomous speed setting.

    Returns:
        int: Current auto speed in PWM units (0–255).
    """
```

**Behavior Specification:**
- **Input Validation:** None (no parameters).
- **Processing Logic:** Return `self.auto_speed` directly.
- **Output Guarantee:** Always returns an integer in `[0, 255]`.
- **Side Effects:** None.
- **Thread Safety:** Read of a single integer — atomic in CPython; no lock required.

**Error Handling:** None applicable.

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

#### 2.3 New Method: `set_auto_speed`

**Signature:**
```python
def set_auto_speed(self, speed: int) -> None:
    """Updates the autonomous movement speed.

    If the obstacle-avoidance loop is currently running, the new speed
    takes effect on the next iteration without restarting the thread.

    Args:
        speed: New speed in PWM units. Must be in range [0, 255].

    Raises:
        ValueError: If speed is outside [0, 255].
    """
```

**Behavior Specification:**
- **Input Validation:** `if not isinstance(speed, int) or not (0 <= speed <= 255)` → raise `ValueError`.
- **Processing Logic:**
  1. Validate range. Raise on failure.
  2. Set `self.auto_speed = speed`.
  3. Check if avoidance is actively running: `self.mode == 'auto'` AND `self.avoidance_thread is not None` AND `self.avoidance_thread.is_alive()`.
  4. If running: call `self.avoidance.set_speed(speed)` to propagate immediately.
- **Output Guarantee:** Returns `None`. After return, `self.auto_speed == speed`.
- **Side Effects:** May call `ObstacleAvoidance.set_speed()`. No thread restart.

**Error Handling:**
- **Out-of-range:** `not (0 <= speed <= 255)` → raise `ValueError("auto_speed must be 0–255, got {speed}")`
- **Wrong type (float, string, None):** → raise `ValueError("auto_speed must be an integer")`

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

#### 2.4 Modified Method: `enable_auto_mode` *(MODIFIED)*

**Signature (unchanged):**
```python
def enable_auto_mode(self) -> None:
    """Enables autonomous obstacle-avoidance mode using current auto_speed."""
```

**Change:** Replace any hardcoded speed literal (currently `30`) in the `start_continuous()` call with `self.auto_speed`:

```python
# BEFORE (current):
self.avoidance_thread = self.avoidance.start_continuous(interval_ms=100, speed=30)

# AFTER (contract):
self.avoidance_thread = self.avoidance.start_continuous(interval_ms=100, speed=self.auto_speed)
```

**No other changes to this method.** The rest of its logic is untouched.

---

### Class: `ObstacleAvoidance` *(MODIFIED)*
**Location:** `src/hardware/obstacle_avoidance.py` *(or equivalent)*

#### 2.5 New Attribute: `_speed`

```python
# Added inside __init__
self._speed: int = 80  # Internal default. Will be overridden by start_continuous caller.
```

---

#### 2.6 New Method: `set_speed`

**Signature:**
```python
def set_speed(self, speed: int) -> None:
    """Updates the speed used by the avoidance loop on its next iteration.

    Thread-safe for CPython due to GIL-protected integer assignment.

    Args:
        speed: New speed in PWM units. Range: [0, 255].

    Raises:
        ValueError: If speed is outside [0, 255].
    """
```

**Behavior Specification:**
- **Input Validation:** `if not (0 <= speed <= 255)` → raise `ValueError`.
- **Processing Logic:** `self._speed = speed`.
- **Output Guarantee:** Returns `None`.
- **Side Effects:** The running loop will use the new value on its next call to `run_once()`.
- **Thread Safety:** Single integer assignment. Safe under CPython GIL. No `threading.Lock` required for this attribute alone.

**Error Handling:**
- **Out-of-range:** → raise `ValueError("speed must be 0–255")`

---

#### 2.7 Modified Method: `run_once` *(MODIFIED)*

**Signature:**
```python
def run_once(self, speed: int = None) -> None:
    """Executes one obstacle-avoidance cycle.

    Args:
        speed: PWM speed override. If None, uses self._speed.
    """
```

**Change:** Make `speed` parameter optional. If `None`, fall back to `self._speed`:

```python
# At top of method body, add:
if speed is None:
    speed = self._speed
# Rest of method unchanged.
```

**No other changes to this method.**

---

#### 2.8 Modified Method: `start_continuous` *(MODIFIED)*

**Signature:**
```python
def start_continuous(self, interval_ms: int = 100, speed: int = None) -> threading.Thread:
    """Starts the continuous obstacle-avoidance loop in a background thread.

    Args:
        interval_ms: Delay between avoidance cycles in milliseconds.
        speed: Initial PWM speed. If provided, sets self._speed before starting.

    Returns:
        threading.Thread: The running background thread.
    """
```

**Changes:**
1. If `speed is not None`: set `self._speed = speed` before starting the thread.
2. Inside the loop, replace `self.run_once(speed)` with `self.run_once()` (no argument), so the loop always reads the current `self._speed`.

```python
# BEFORE (current):
def start_continuous(self, interval_ms=100, speed=80):
    def loop():
        while self._running:
            self.run_once(speed)   # ← hardcoded to original arg
            time.sleep(interval_ms / 1000)
    ...

# AFTER (contract):
def start_continuous(self, interval_ms=100, speed=None):
    if speed is not None:
        self._speed = speed
    def loop():
        while self._running:
            self.run_once()        # ← reads self._speed, picks up live updates
            time.sleep(interval_ms / 1000)
    ...
```

**No other changes to this method.**

---

## 3. PUBLIC INTERFACE — API ROUTES

**Location:** `src/api/server.py`

---

### Endpoint: `GET /api/auto/speed`

**Signature:**
```python
@app.route('/api/auto/speed', methods=['GET'])
def get_auto_speed_route() -> Response:
    """Returns the current autonomous movement speed.

    Returns:
        JSON: { "success": true, "speed": int }
        HTTP 200 on success.
        HTTP 500 if hardware_manager is unavailable.
    """
```

**Behavior Specification:**
- **Input Validation:** None (GET, no body).
- **Processing Logic:** Call `hardware_manager.get_auto_speed()`. Return as JSON.
- **Output Guarantee:** `speed` field is always integer `[0, 255]`.
- **Side Effects:** None.

**Response Schema:**
```json
{
  "success": true,
  "speed": 30
}
```

**Error Handling:**
- **`hardware_manager` not initialized / `None`:** → return `jsonify(success=False, error="Hardware manager unavailable")`, HTTP `503`.

---

### Endpoint: `POST /api/auto/speed`

**Signature:**
```python
@app.route('/api/auto/speed', methods=['POST'])
def set_auto_speed_route() -> Response:
    """Updates the autonomous movement speed.

    Request Body (JSON):
        { "speed": int }  # 0–255

    Returns:
        JSON: { "success": true, "speed": int }  on success.
        HTTP 400 on missing/invalid payload.
        HTTP 503 if hardware unavailable.
    """
```

**Behavior Specification:**
- **Input Validation (in order):**
  1. `request.get_json()` returns `None` or non-dict → HTTP `400`.
  2. `'speed'` key missing from body → HTTP `400`.
  3. `int(data['speed'])` raises `(ValueError, TypeError)` → HTTP `400`.
  4. Converted value outside `[0, 255]` → caught by `hardware_manager.set_auto_speed()` raising `ValueError` → HTTP `400`.
- **Processing Logic:**
  1. Parse body.
  2. Cast `speed = int(data['speed'])`.
  3. Call `hardware_manager.set_auto_speed(speed)`.
  4. Return success JSON.
- **Output Guarantee:** On success, `speed` in response matches the value now active on the backend.
- **Side Effects:** Calls `hardware_manager.set_auto_speed()`, which may call `ObstacleAvoidance.set_speed()`.

**Response Schema (success):**
```json
{
  "success": true,
  "speed": 50
}
```

**Error Response Schema:**
```json
{
  "success": false,
  "error": "Speed must be 0–255, got 300"
}
```

**Error Handling:**

| Condition | HTTP Code | Error Message |
|---|---|---|
| Body is not JSON / missing | 400 | `"Request body must be JSON with 'speed' field"` |
| `speed` key absent | 400 | `"Missing required field: speed"` |
| `speed` not castable to int | 400 | `"'speed' must be an integer"` |
| `speed` outside [0, 255] | 400 | Forwarded from `ValueError` raised by `set_auto_speed` |
| `hardware_manager` unavailable | 503 | `"Hardware manager unavailable"` |

**Constraint:** Route must return immediately (non-blocking). `set_auto_speed` is O(1); no long-running work occurs in this route. *(system_constraints.md §1 — Non-Blocking routes.)*

---

## 4. PUBLIC INTERFACE — FRONTEND

---

### Method: `_setupAutoSpeedControl` *(NEW)*
**Location:** `DashboardCore` class, `dashboard-core.js`

**Signature:**
```javascript
/**
 * Initialises the autonomous speed slider: fetches the current backend value,
 * sets the slider position, and attaches a debounced input listener that
 * POSTs updates to /api/auto/speed.
 *
 * @returns {void}
 * @private
 */
_setupAutoSpeedControl() { ... }
```

**Behavior Specification:**
- **Input Validation:** If `#auto-speed-slider` or `#auto-speed-value` are absent from the DOM, log `console.warn('auto-speed-slider not found — auto speed control disabled')` and return. No throw.
- **Processing Logic:**
  1. Query `#auto-speed-slider` and `#auto-speed-value`.
  2. Guard — return if either is missing.
  3. `fetch GET /api/auto/speed` to load current backend value:
     - On success: convert `data.speed` (0–255) to percent `Math.round((data.speed / 255) * 100)`, set `slider.value` and `valueSpan.textContent = pct + '%'`.
     - On failure: call `this._showToast('Could not load auto speed', 'warning')`.
  4. Attach `'input'` event listener to slider:
     - Update `valueSpan.textContent = pct + '%'` immediately (real‑time).
     - Update gradient via same `updateGradient` pattern as manual slider.
     - Set `clearTimeout(this._autoSpeedTimeout)`.
     - Set `this._autoSpeedTimeout = setTimeout(() => this._updateAutoSpeed(pct), 300)`.
- **Output Guarantee:** Returns void. Slider position reflects backend state after initialization.
- **Side Effects:** One outbound `fetch GET`. DOM mutations. Timer registration.

**Error Handling:**
- All `fetch` calls wrapped in `try/catch`. Failures surface via `this._showToast(...)`. *(§5.1)*

**Performance Requirements:**
- Debounce delay: 300 ms (prevents burst POSTs while dragging slider).
- Time Complexity: O(1) per event.

---

### Method: `_updateAutoSpeed` *(NEW)*
**Location:** `DashboardCore` class, `dashboard-core.js`

**Signature:**
```javascript
/**
 * Converts a percentage (0–100) to PWM (0–255) and POSTs to /api/auto/speed.
 *
 * @param {number} pct - Slider percentage value (0–100 integer).
 * @returns {Promise<void>}
 * @private
 */
async _updateAutoSpeed(pct) { ... }
```

**Behavior Specification:**
- **Input Validation:** `pct` must be an integer `[0, 100]`. No runtime check required (caller controls the value from a range input).
- **Processing Logic:**
  1. Compute `speed = Math.round((pct / 100) * 255)`.
  2. POST `{ speed }` to `${this.apiBase}/api/auto/speed` with `Content-Type: application/json`.
  3. On non-OK response: throw to trigger catch.
- **Output Guarantee:** Returns resolved Promise on success.
- **Side Effects:** One outbound `fetch POST`.

**Error Handling:**
- Wrap in `try/catch`. On failure: `this._showToast('Failed to set auto speed: ' + err.message, 'error')`. *(§5.1 — no silent failures.)*

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

### Method: `_setupControls` *(MODIFIED)*
**Location:** `DashboardCore` class, `dashboard-core.js`

**Change:** Add one call at the end of the existing `_setupControls()` body:

```javascript
this._setupAutoSpeedControl();
```

**No other changes to `_setupControls()`.** All existing bindings (manual slider, direction buttons, apply button, speed ramp button) remain untouched.

---

### Constructor Additions *(MODIFIED)*
**Location:** `DashboardCore` constructor

Add two new instance variables:
```javascript
this._autoSpeedTimeout = null;  // Debounce timer for auto speed slider
```
*(Note: `_rampInProgress` was already added by contract v1.0 for Feature 19. Do not duplicate.)*

---

## 5. HTML INTERFACE CONTRACT (`service_dashboard.html`)

### 5.1 Auto Speed Slider Block

**Location:** Inside `#controlModal` `.modal-body`, below the existing manual speed `.control-group` and below the `#btn-speed-ramp` test controls block (added by Feature 19 contract).

```html
<!-- Auto Speed Control — Feature 20 -->
<div class="control-group auto-speed-group" style="margin-top: 16px; border-top: 1px solid var(--border-light); padding-top: 12px;">
    <label for="auto-speed-slider">Auto Speed</label>
    <div class="slider-container">
        <input
            type="range"
            id="auto-speed-slider"
            class="speed-slider"
            min="0"
            max="100"
            value="30"
            aria-label="Autonomous mode speed"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow="30"
            style="min-height: 44px;">
        <span id="auto-speed-value" aria-hidden="true">30%</span>
    </div>
</div>
```

**Constraints:**
- `type="range"` — not a custom widget.
- `min-height: 44px` on the `<input>` — WCAG touch target compliance. *(§5.2)*
- IDs must be kebab-case: `auto-speed-slider`, `auto-speed-value`. *(§5.3)*
- `value="30"` — matches backend default of `30 PWM`. The JS init will override this after fetching actual backend value on page load.
- `aria-valuenow` must be updated by JS whenever the value changes (for screen reader live region accuracy). The implementer must add `slider.setAttribute('aria-valuenow', pct)` inside the `input` event handler.

---

## 6. DEPENDENCIES

**Backend — This module CALLS:**
- `ObstacleAvoidance.set_speed(speed)` — Called by `HardwareManager.set_auto_speed()` when avoidance loop is live.
- `ObstacleAvoidance.run_once()` — Called internally by the avoidance loop (no args, reads `self._speed`).

**Backend — This module is CALLED BY:**
- `GET /api/auto/speed` route → `hardware_manager.get_auto_speed()`
- `POST /api/auto/speed` route → `hardware_manager.set_auto_speed()`
- `HardwareManager.enable_auto_mode()` → `self.avoidance.start_continuous(speed=self.auto_speed)`

**Frontend — This module CALLS:**
- `GET /api/auto/speed` — on init, to hydrate slider
- `POST /api/auto/speed` — on debounced slider change
- `this._showToast(message, type)` — error/warning feedback

**Frontend — This module is CALLED BY:**
- `DashboardCore._setupControls()` → `this._setupAutoSpeedControl()`

**No new external libraries required on either frontend or backend.**

---

## 7. DATA STRUCTURES

### PWM ↔ Percent Mapping (Canonical, both layers must use this)
```
pwm   = Math.round((pct / 100) * 255)    // frontend → backend
pct   = Math.round((pwm / 255) * 100)    // backend  → frontend (display only)
```

| Slider % | Sent PWM |
|----------|---------|
| 0        | 0       |
| 30       | 77 (default) |
| 50       | 128     |
| 75       | 191     |
| 100      | 255     |

### Backend Default
```python
DEFAULT_AUTO_SPEED: int = 30  # PWM units. ~11.8% of max. Safe for close-quarters avoidance.
```

---

## 8. CONSTRAINTS (FROM SYSTEM RULES)

- **§1 — Non-Blocking Routes:** `POST /api/auto/speed` must return immediately. `set_auto_speed()` is O(1) and non-blocking by design. ✅
- **§1 — No Global State:** `auto_speed` lives on `HardwareManager` instance, not as a module-level variable. ✅
- **§1 — HardwareManager pattern:** Route does NOT call hardware directly. It calls `hardware_manager.set_auto_speed()`. ✅
- **§1 — Type Hints:** `get_auto_speed` and `set_auto_speed` must have full Python type hints.
- **§4 — Max 50 lines:** `set_auto_speed`, `get_auto_speed`, `ObstacleAvoidance.set_speed` are all trivially short. `_setupAutoSpeedControl()` must be verified ≤50 lines; if the fetch + event listener exceeds this, split the fetch into a private `_fetchAutoSpeed()` helper.
- **§5.1 — No Silent Failures:** Every `fetch()` in `_setupAutoSpeedControl` and `_updateAutoSpeed` must be wrapped in `try/catch` with a toast call.
- **§5.2 — Toast Container:** Verify `<div id="toast-container">` exists in `service_dashboard.html` before implementation.
- **§5.2 — Touch Target:** `min-height: 44px` on `#auto-speed-slider`. ✅ (specified in HTML contract §5.1)
- **§5.6 — Legacy Integration Override:** As with Feature 19, direct modification of `dashboard-core.js` is approved for this contract because we are adding a method to `DashboardCore` itself, not building a new panel. **Explicit approval granted.**
- **§3 — API Protocol:** All endpoints use `application/json`. ✅

---

## 9. MEMORY COMPLIANCE

No `_memory_snippet.txt` was provided. **N/A.**

---

## 10. ACCEPTANCE CRITERIA

### Test Case 1: Default load
- **Scenario:** Page loads. Auto speed slider should reflect the backend default.
- **Action:** Open dashboard, open Motor Control Modal.
- **Expected:** `#auto-speed-slider.value` is `12` (i.e., `Math.round((30/255)*100) = 12`). `#auto-speed-value` shows `"12%"`.
- **Pass Condition:** Slider position matches backend state fetched via `GET /api/auto/speed`.

### Test Case 2: Slider change → backend update
- **Scenario:** Operator drags auto speed slider to 50%.
- **Action:** Drag `#auto-speed-slider` to `50`.
- **Expected (after 300ms debounce):** POST `{ speed: 128 }` sent to `/api/auto/speed`. Backend `hardware_manager.auto_speed == 128`.
- **Pass Condition:** `GET /api/auto/speed` returns `{ success: true, speed: 128 }`.

### Test Case 3: Live update during auto mode
- **Scenario:** Robot is in auto mode, avoidance loop is running at default speed.
- **Action:** POST `{ speed: 191 }` to `/api/auto/speed`.
- **Expected:** `hardware_manager.auto_speed == 191`. `obstacle_avoidance._speed == 191`. Next `run_once()` iteration uses `191`.
- **Pass Condition:** No thread restart. Loop continues. Speed changes within one iteration cycle.

### Test Case 4: Out-of-range rejection
- **Scenario:** Invalid POST sent directly to API.
- **Input:** POST `{ speed: 300 }` to `/api/auto/speed`.
- **Expected Response:** HTTP `400`. Body: `{ success: false, error: "..." }`.
- **Pass Condition:** Backend raises `ValueError`, route catches it, returns 400.

### Test Case 5: Missing speed field
- **Input:** POST `{}` to `/api/auto/speed`.
- **Expected Response:** HTTP `400`. Body: `{ success: false, error: "Missing required field: speed" }`.

### Test Case 6: Manual slider unaffected
- **Scenario:** Manual speed slider operates normally.
- **Action:** Move `#speed-slider` to 75%.
- **Expected:** POST `{ command: 'forward', speed: 191 }` to `/api/motor/control`. `auto_speed` unchanged.
- **Pass Condition:** Auto and manual speed are fully independent. No cross-contamination.

### Test Case 7: Frontend fetch failure (backend offline)
- **Scenario:** Backend is unreachable when modal opens.
- **Expected:** Toast appears: `"Could not load auto speed"` (type: `warning`). Slider remains at HTML default (`30`). No crash.

### Test Case 8: Slider aria update
- **Action:** Move `#auto-speed-slider` to any value.
- **Expected:** `aria-valuenow` attribute on the input element is updated to the new percentage integer.
- **Pass Condition:** Screen reader can announce current value.

---

## 11. OUT OF SCOPE

- Persisting `auto_speed` across server restarts (config file / database) — future enhancement.
- "Test Auto Speed" button — deferred to future spec.
- Manual speed slider changes — Feature 19, already contracted separately.
- Any changes to `ObstacleAvoidance` collision logic — untouched.
- Auto speed slider placement outside the motor modal — operator feedback deferred.