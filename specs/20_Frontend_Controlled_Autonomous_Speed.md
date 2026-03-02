# 📄 FEATURE SPEC: Frontend‑Controlled Autonomous Speed

**Date:** 2026‑03‑03  
**Status:** Draft  
**Target Version:** v4.2  
**Author:** Master Orchestrator (from session logs)

---

## 1. PURPOSE

Currently, the autonomous (obstacle‑avoidance) mode uses a fixed speed, hardcoded as `30` in the `start_continuous` call (roughly 12% of max PWM). The operator cannot adjust this speed from the frontend, making it impossible to slow down the robot for delicate obstacle testing or speed up for open‑space traversal.

This feature adds a dedicated **Auto Speed slider** in the UI, allowing real‑time adjustment of the autonomous movement speed. The slider range will be 0–100% (mapped to 0–255 PWM, same as manual mode), with a default safe value (e.g., 30%). Changes will be persisted on the backend and take effect immediately for the obstacle‑avoidance loop.

---

## 2. FEASIBILITY CHECK

- **System Constraints:** ✅ Passed. The backend already supports variable speed via the same motor‑control API. No new hardware dependencies.
- **New Libraries Needed:** None.
- **Risk Level:** Low. The change is isolated to the `HardwareManager` and `ObstacleAvoidance` classes, plus frontend additions. The manual speed control remains untouched.
- **Backward Compatibility:** The existing hardcoded speed will be replaced by a configurable value; old deployments will need to set a default.

---

## 3. ARCHITECTURE CHANGES

### Backend

- **`HardwareManager`**  
  - Add an instance variable `self.auto_speed` (int, 0–255).  
  - Initialize with a sensible default (e.g., `30`).  
  - Modify `enable_auto_mode()` (or wherever `obstacle_avoidance.start_continuous` is called) to pass `self.auto_speed` instead of a hardcoded value.  
  - Add a method `set_auto_speed(speed: int)` that updates `self.auto_speed` and, if avoidance is running, updates the loop’s speed dynamically (or restarts it with the new speed).  

- **`ObstacleAvoidance`**  
  - Currently `run_once(speed)` and `start_continuous(speed)` accept a speed parameter. This design already supports variable speed.  
  - No change needed, except to ensure that if the speed is changed while the loop is running, the new value is used on the next iteration. The loop currently reads the `speed` argument at each iteration (because `run_once(speed)` is called inside the loop with the same `speed` that was passed to `start_continuous`). If we want the speed to be changeable without restarting the loop, we need to modify `ObstacleAvoidance` to store a reference to the speed (e.g., via a property that can be updated).  

  **Option A (simpler):** Restart the avoidance loop with the new speed whenever the auto speed is changed. This is easy but may cause a brief stop.  
  **Option B (more elegant):** Modify `ObstacleAvoidance` to have a `current_speed` attribute that can be updated safely while the loop runs. Then `run_once` uses `self.current_speed`.  

  I recommend **Option B** for a smooth experience.  

- **API Endpoints** (new)  
  - `GET /api/auto/speed` – returns current auto speed as `{ "speed": int }` (0‑255).  
  - `POST /api/auto/speed` – accepts `{ "speed": int }` (0‑255), updates backend, returns success.

### Frontend

- **`dashboard-core.js`**  
  - Add a new slider in the motor control modal (or in a separate “Auto Settings” section near the mode buttons).  
  - Slider range: 0–100% (visual percentage), mapped to 0–255 PWM on the backend (same mapping as manual speed).  
  - When slider changes, POST the new speed to `/api/auto/speed`.  
  - On page load, fetch current auto speed and set slider position.  
  - Display current value as a percentage (e.g., “Auto Speed: 30%”).

- **`service_dashboard.html`**  
  - Add HTML for the auto speed slider inside the motor control modal or in the global status bar area (next to mode buttons).  
  - Keep the existing manual speed slider unchanged.  
  - Use similar styling and accessibility attributes as the manual slider.

- **Optional** – Add a “Test Auto Ramp” button that runs a short sequence at the current auto speed (like the manual speed ramp) to verify behaviour.

---

## 4. API SPECIFICATION

### GET /api/auto/speed

**Response:**
```json
{
  "success": true,
  "speed": 30   // integer 0‑255
}
```

### POST /api/auto/speed

**Request Body:**
```json
{
  "speed": 50   // integer 0‑255
}
```

**Response:**
```json
{
  "success": true,
  "speed": 50
}
```
If the speed is out of range, return `400` with an error message.

---

## 5. FRONTEND UI CHANGES (Detailed)

**Location:** Inside the Motor Control Modal (`#controlModal`), below the manual speed slider or in a new “Autonomous Settings” section.

**HTML Addition (example):**

```html
<div class="control-group auto-speed">
  <label for="auto-speed-slider">Auto Speed</label>
  <input type="range" id="auto-speed-slider" min="0" max="100" value="30" class="slider"
         aria-valuemin="0" aria-valuemax="100" aria-valuenow="30">
  <span id="auto-speed-value" aria-hidden="true">30%</span>
</div>
```

**JavaScript additions (`dashboard-core.js`):**

- In `init()` or `_setupControls()`, fetch the current auto speed via `GET /api/auto/speed` and set the slider value.
- Add an event listener to the auto speed slider to send changes to the backend (debounced, e.g., 200ms after last change).
- Define a method `_updateAutoSpeed(speed)` that sends the POST request and updates the displayed percentage.
- Update the displayed percentage in real time as the slider moves (same as manual slider).

**Example implementation snippet:**

```javascript
_setupAutoSpeedControl() {
  const slider = document.getElementById('auto-speed-slider');
  const valueSpan = document.getElementById('auto-speed-value');
  if (!slider || !valueSpan) return;

  // Fetch current value
  fetch(`${this.apiBase}/api/auto/speed`)
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        const pct = Math.round((data.speed / 255) * 100);
        slider.value = pct;
        valueSpan.textContent = pct + '%';
      }
    })
    .catch(console.warn);

  // Update on input
  slider.addEventListener('input', () => {
    const pct = parseInt(slider.value);
    valueSpan.textContent = pct + '%';
    // Debounced update
    clearTimeout(this.autoSpeedTimeout);
    this.autoSpeedTimeout = setTimeout(() => {
      const speed = Math.round((pct / 100) * 255);
      fetch(`${this.apiBase}/api/auto/speed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speed })
      }).catch(err => this._showToast('Failed to set auto speed', 'error'));
    }, 300);
  });
}
```

Call `_setupAutoSpeedControl()` from `_setupControls()` or `init()`.

---

## 6. BACKEND IMPLEMENTATION DETAILS

### HardwareManager modifications

Add to `HardwareManager.__init__`:

```python
self.auto_speed = 30  # default, can be loaded from config later
```

Add methods:

```python
def get_auto_speed(self):
    return self.auto_speed

def set_auto_speed(self, speed: int):
    if not 0 <= speed <= 255:
        raise ValueError("Speed must be 0‑255")
    self.auto_speed = speed
    if self.mode == 'auto' and self.avoidance_thread and self.avoidance_thread.is_alive():
        # Update the avoidance loop's speed
        self.avoidance.set_speed(speed)   # see below
```

Modify `enable_auto_mode()` to pass `self.auto_speed`:

```python
def enable_auto_mode(self):
    # ... existing code ...
    self.avoidance_thread = self.avoidance.start_continuous(
        interval_ms=100,
        speed=self.auto_speed   # use current auto_speed
    )
    # ...
```

### ObstacleAvoidance modifications

Add an instance variable `self._speed` and a setter:

```python
def __init__(self, hardware_manager, safety_distance_mm=500):
    # ... existing ...
    self._speed = 80   # default, will be overridden by caller

def set_speed(self, speed):
    self._speed = speed

def run_once(self, speed=None):
    # If speed is not provided, use self._speed
    if speed is None:
        speed = self._speed
    # ... rest unchanged ...

def start_continuous(self, interval_ms=100, speed=None):
    # Store the initial speed
    if speed is not None:
        self._speed = speed
    # ... rest unchanged, but inside loop call run_once() with no arg (so it uses self._speed)
```

Inside the loop in `start_continuous`, replace:

```python
self.run_once(speed)   # with
self.run_once()        # uses self._speed
```

This way, calling `set_speed()` updates the speed for subsequent iterations without restarting the thread.

### API route in `server.py`

Add two new routes (or one combined) in `src/api/server.py`:

```python
@app.route('/api/auto/speed', methods=['GET'])
def get_auto_speed():
    speed = hardware_manager.get_auto_speed()
    return jsonify(success=True, speed=speed)

@app.route('/api/auto/speed', methods=['POST'])
def set_auto_speed():
    data = request.get_json()
    if not data or 'speed' not in data:
        return jsonify(success=False, error="Missing speed"), 400
    try:
        speed = int(data['speed'])
        hardware_manager.set_auto_speed(speed)
        return jsonify(success=True, speed=speed)
    except ValueError as e:
        return jsonify(success=False, error=str(e)), 400
```

---

## 7. ATOMIC TASKS (Checklist)

### Backend
- [ ] Modify `HardwareManager`: add `auto_speed` attribute, getter, setter.
- [ ] Modify `HardwareManager.enable_auto_mode()` to use `self.auto_speed`.
- [ ] Modify `ObstacleAvoidance` to store and use `self._speed`; add `set_speed()` method.
- [ ] Update `ObstacleAvoidance.start_continuous` to accept optional speed and store it.
- [ ] Update the loop inside `start_continuous` to call `run_once()` without argument.
- [ ] Add API routes in `server.py` for GET/POST `/api/auto/speed`.
- [ ] Add error handling (range checks, JSON validation).

### Frontend
- [ ] Add HTML for auto speed slider in `service_dashboard.html` (inside motor modal or near mode buttons).
- [ ] Add CSS styling for the new slider (reuse existing `.control-group` styles).
- [ ] In `dashboard-core.js`, add method `_setupAutoSpeedControl()`.
- [ ] Call it from `init()` or `_setupControls()`.
- [ ] Implement fetch of current auto speed on load.
- [ ] Add input event listener with debounced POST.
- [ ] Update displayed percentage in real time.
- [ ] Handle fetch errors with toast notifications.

### Testing & Validation
- [ ] Manual mode unchanged – verify manual slider still works.
- [ ] Switch to auto mode, change auto speed slider, verify robot speed changes (with wheels elevated).
- [ ] Test edge cases: speed 0 (should stop), speed 255 (full speed).
- [ ] Verify that changing auto speed while auto mode is active takes effect without restarting.
- [ ] Check that auto speed persists across mode switches (it should stay at last set value).
- [ ] Verify API error handling (invalid JSON, out‑of‑range values).

---

## 8. SUCCESS CRITERIA

- [ ] A dedicated auto speed slider exists in the UI.
- [ ] Slider range is 0–100%, displayed as percentage.
- [ ] Changing the slider updates the robot’s autonomous speed immediately (within ~100ms).
- [ ] Manual speed slider remains unaffected.
- [ ] Auto speed defaults to a safe value (e.g., 30%) on first start.
- [ ] No regressions in obstacle‑avoidance logic.
- [ ] All new code passes an auditor review (95+ score).

---

## 9. OPEN QUESTIONS / FUTURE ENHANCEMENTS

- Should the auto speed be persisted across server restarts? (Could be added later via config file or database.)
- Should we add a “Test Auto Speed” button that runs a short forward/backward sequence at the current auto speed?
- Should the auto speed slider be placed in the motor modal or in the global header? (I’d suggest motor modal for consistency.)

---

## 10. ESTIMATED EFFORT

- Backend changes: ~1 hour  
- Frontend changes: ~1 hour  
- Testing & integration: ~30 minutes  
- **Total:** 2.5–3 hours

---

**Next Step:** If you approve this plan, I will generate a formal contract for the Architect, then a work order for the Implementer. Or you can start implementing directly following this spec.