# WORK ORDER: Frontend‑Controlled Autonomous Speed
**Contract Reference:** `docs/contracts/auto_speed_control.md` v1.0
**Date:** 2026‑03‑03
**Target Files:**
- `src/hardware/hardware_manager.py`
- `src/hardware/obstacle_avoidance.py`
- `src/api/server.py`
- `frontend/static/js/dashboard-core.js`
- `frontend/templates/service_dashboard.html`

---

## Strict Constraints (NON-NEGOTIABLE)

1. **No global state** — `auto_speed` lives on the `HardwareManager` instance only. Never as a module-level variable. (§1)
2. **Non-blocking routes** — `POST /api/auto/speed` must return in O(1). Never call blocking hardware inside a route. (§1)
3. **Type hints mandatory** — `get_auto_speed() -> int` and `set_auto_speed(speed: int) -> None` must have full annotations. (§4)
4. **Max 50 lines per function** — If `_setupAutoSpeedControl()` grows beyond 50 executable lines, split the fetch logic into `_fetchAutoSpeed()`. (§5.1)
5. **No silent fetch failures** — `try/catch` + `this._showToast(...)` on every async call. (§5.1)
6. **Touch target** — `#auto-speed-slider` must have `min-height: 44px`. (§5.2)
7. **PWM formula is canonical** — `Math.round((pct / 100) * 255)` frontend→backend. `Math.round((pwm / 255) * 100)` backend→display. No deviations.

---

## Memory Compliance (MANDATORY)

No memory snippet provided. Apply `system_constraints.md` only.

---

## Required Logic

### File 1: `src/hardware/hardware_manager.py`

**Change 1 — `__init__`:** Add `self.auto_speed: int = 30` after existing state initialization.

**Change 2 — Add `get_auto_speed()`:**
```python
def get_auto_speed(self) -> int:
    return self.auto_speed
```

**Change 3 — Add `set_auto_speed()`:**
```python
def set_auto_speed(self, speed: int) -> None:
    if not isinstance(speed, int) or not (0 <= speed <= 255):
        raise ValueError(f"auto_speed must be 0–255, got {speed}")
    self.auto_speed = speed
    if (self.mode == 'auto'
            and self.avoidance_thread is not None
            and self.avoidance_thread.is_alive()):
        self.avoidance.set_speed(speed)
```

**Change 4 — `enable_auto_mode()`:** Replace hardcoded `speed=30` with `speed=self.auto_speed` in the `start_continuous()` call. One line change only.

---

### File 2: `src/hardware/obstacle_avoidance.py`

**Change 1 — `__init__`:** Add `self._speed: int = 80` to instance variables.

**Change 2 — Add `set_speed()`:**
```python
def set_speed(self, speed: int) -> None:
    if not (0 <= speed <= 255):
        raise ValueError("speed must be 0–255")
    self._speed = speed
```

**Change 3 — `run_once()`:** Change signature to `def run_once(self, speed: int = None)`. Add at top of body:
```python
if speed is None:
    speed = self._speed
```

**Change 4 — `start_continuous()`:** Change signature to `def start_continuous(self, interval_ms=100, speed=None)`. Add at top of body (before thread creation):
```python
if speed is not None:
    self._speed = speed
```
Inside the loop, change `self.run_once(speed)` → `self.run_once()`.

---

### File 3: `src/api/server.py`

**Add two new routes (add them together in the motor/auto section):**

```python
@app.route('/api/auto/speed', methods=['GET'])
def get_auto_speed_route():
    """Returns current autonomous speed setting."""
    try:
        speed = hardware_manager.get_auto_speed()
        return jsonify(success=True, speed=speed)
    except Exception:
        return jsonify(success=False, error="Hardware manager unavailable"), 503


@app.route('/api/auto/speed', methods=['POST'])
def set_auto_speed_route():
    """Updates autonomous speed setting."""
    data = request.get_json()
    if not data or 'speed' not in data:
        return jsonify(success=False, error="Missing required field: speed"), 400
    try:
        speed = int(data['speed'])
        hardware_manager.set_auto_speed(speed)
        return jsonify(success=True, speed=speed)
    except (ValueError, TypeError) as e:
        return jsonify(success=False, error=str(e)), 400
    except Exception:
        return jsonify(success=False, error="Hardware manager unavailable"), 503
```

---

### File 4: `frontend/static/js/dashboard-core.js`

**Change 1 — Constructor:** Add `this._autoSpeedTimeout = null;`

**Change 2 — `_setupControls()`:** Add at the very end of the method body:
```javascript
this._setupAutoSpeedControl();
```

**Change 3 — Add `_setupAutoSpeedControl()`:**
```javascript
_setupAutoSpeedControl() {
    const slider = document.getElementById('auto-speed-slider');
    const valueSpan = document.getElementById('auto-speed-value');
    if (!slider || !valueSpan) {
        console.warn('auto-speed-slider not found — auto speed control disabled');
        return;
    }

    // Load current backend value
    fetch(`${this.apiBase}/api/auto/speed`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const pct = Math.round((data.speed / 255) * 100);
                slider.value = pct;
                slider.setAttribute('aria-valuenow', pct);
                valueSpan.textContent = `${pct}%`;
            }
        })
        .catch(() => this._showToast('Could not load auto speed', 'warning'));

    slider.addEventListener('input', () => {
        const pct = parseInt(slider.value);
        valueSpan.textContent = `${pct}%`;
        slider.setAttribute('aria-valuenow', pct);
        clearTimeout(this._autoSpeedTimeout);
        this._autoSpeedTimeout = setTimeout(() => this._updateAutoSpeed(pct), 300);
    });
}
```

**Change 4 — Add `_updateAutoSpeed()`:**
```javascript
async _updateAutoSpeed(pct) {
    try {
        const speed = Math.round((pct / 100) * 255);
        const res = await fetch(`${this.apiBase}/api/auto/speed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ speed })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (err) {
        this._showToast('Failed to set auto speed: ' + err.message, 'error');
    }
}
```

---

### File 5: `frontend/templates/service_dashboard.html`

**Add below the `#btn-speed-ramp` test controls block (Feature 19) inside `#controlModal`:**

```html
<!-- Auto Speed Control -->
<div class="control-group auto-speed-group"
     style="margin-top: 16px; border-top: 1px solid var(--border-light); padding-top: 12px;">
    <label for="auto-speed-slider">Auto Speed</label>
    <div class="slider-container">
        <input type="range"
               id="auto-speed-slider"
               class="speed-slider"
               min="0" max="100" value="30"
               aria-label="Autonomous mode speed"
               aria-valuemin="0" aria-valuemax="100" aria-valuenow="30"
               style="min-height: 44px;">
        <span id="auto-speed-value" aria-hidden="true">30%</span>
    </div>
</div>
```

---

## Integration Points

- **Must call:** `GET /api/auto/speed` on modal open (via `_setupAutoSpeedControl` init fetch).
- **Must call:** `POST /api/auto/speed` on debounced slider change.
- **Must call:** `this._showToast(message, type)` — verify this exists. If missing, escalate to Architect.
- **Will be called by:** `DashboardCore._setupControls()` → `_setupAutoSpeedControl()`.
- **Backend chain:** `set_auto_speed_route` → `HardwareManager.set_auto_speed()` → `ObstacleAvoidance.set_speed()` (if auto mode active).

---

## Success Criteria

- [ ] `GET /api/auto/speed` returns `{ success: true, speed: 30 }` on fresh start
- [ ] `POST /api/auto/speed` with `{ speed: 128 }` returns 200 and updates backend
- [ ] `POST /api/auto/speed` with `{ speed: 300 }` returns HTTP 400
- [ ] Slider at 50% sends `speed: 128` to backend (±1 tolerance)
- [ ] Slider position reflects backend value after page load
- [ ] `aria-valuenow` updated on every slider move
- [ ] `ObstacleAvoidance._speed` updated live without thread restart (when mode is 'auto')
- [ ] Manual `#speed-slider` behavior completely unchanged
- [ ] All fetch errors surface as toasts, no silent failures
- [ ] All new Python functions have type hints and docstrings
- [ ] All new JS methods have JSDoc comments
- [ ] All functions under 50 lines executable code
- [ ] Auditor approval required before merge
```