# WORK ORDER: Frontend Variable Speed Control
**Contract Reference:** `docs/contracts/frontend_speed_control.md` v1.0
**Date:** 2026-03-03
**Target Files:**
- `frontend/static/js/dashboard-core.js`
- `frontend/templates/service_dashboard.html`

---

## Strict Constraints (NON-NEGOTIABLE)

1. **Max 50 lines per function** — `runSpeedRamp()` must stay under 50 lines of executable code. (system_constraints.md §4)
2. **No silent fetch failures** — Both `_sendMotorCommand` and `runSpeedRamp` must call `this._showToast(...)` on error, not just `console.error`. (§5.1)
3. **Toast container must exist** — Verify `<div id="toast-container" ...>` is present in `service_dashboard.html` before implementation. (§5.2)
4. **Button must be `<button type="button">`** — Not a `<div>`. Min touch target: `min-height: 44px`. (§5.2, §5.3)
5. **PWM formula is canonical** — `Math.round((sliderVal / 100) * 255)`. Do not deviate. `stop` commands always send `speed: 0`.

---

## Memory Compliance (MANDATORY)

No `_memory_snippet.txt` provided. Apply system_constraints.md only.

---

## Required Logic

### File 1: `dashboard-core.js`

**Change 1 — Constructor:** Add `this._rampInProgress = false;` to `DashboardCore` constructor.

**Change 2 — `_sendMotorCommand(direction)` (MODIFY EXISTING):**
1. Read slider: `const sliderVal = parseInt(document.getElementById('speed-slider')?.value ?? 50);`
2. Compute PWM: `const pwmValue = direction === 'stop' ? 0 : Math.round((sliderVal / 100) * 255);`
3. POST `{ command: direction, speed: pwmValue }` with `Content-Type: application/json`.
4. `.catch(err => this._showToast('Motor command failed: ' + err.message, 'error'))`.

**Change 3 — `runSpeedRamp()` (NEW METHOD — add to DashboardCore class):**
1. Guard: if `this._rampInProgress`, show warning toast and return.
2. Set flag, disable button, show info toast.
3. `try` block: loop `[25, 50, 75, 100]`, POST each step, `await` 800ms delay.
4. POST stop.
5. Show success toast.
6. `finally`: re-enable button, clear flag.

**Change 4 — `_setupControls()` (MODIFY EXISTING — append only):**
After existing code, add:
```javascript
const rampBtn = document.getElementById('btn-speed-ramp');
if (rampBtn) {
    rampBtn.addEventListener('click', () => this.runSpeedRamp());
} else {
    console.warn('btn-speed-ramp not found — speed ramp feature disabled');
}
```

### File 2: `service_dashboard.html`

**Change 1 — Slider label:** Update `<span id="speed-value">50</span>` to `<span id="speed-value">50%</span>`.

**Change 2 — Speed Ramp Button:** Insert below the speed slider `.control-group`:
```html
<div class="test-controls" style="margin-top: 10px;">
    <button id="btn-speed-ramp" class="btn-ghost btn-sm" type="button"
            aria-label="Run automated speed ramp test"
            style="min-height: 44px; min-width: 44px;">
        ⚡ Run Speed Ramp
    </button>
</div>
```

---

## Integration Points

- **Must call:** `POST /api/motor/control` — existing endpoint, no backend changes needed.
- **Must call:** `this._showToast(message, type)` — verify this method exists on `DashboardCore` or the host page. If absent, escalate to Architect before proceeding.
- **Will be called by:** `_setupControls()` → `runSpeedRamp` binding; `handleKeyDown/Up` → `_sendMotorCommand` (unchanged call sites).

---

## Success Criteria

- [ ] `speed-slider` at 100 sends `speed: 255` in POST body
- [ ] `speed-slider` at 50 sends `speed: 127` or `128` (±1 tolerance)
- [ ] `stop` command always sends `speed: 0` regardless of slider
- [ ] "⚡ Run Speed Ramp" button visible in motor modal, min 44×44px
- [ ] Ramp sequence fires 5 POSTs in correct order (25%→50%→75%→100%→stop)
- [ ] Button disabled during ramp, re-enabled after (success or failure)
- [ ] No silent failures — all fetch errors surface as toasts
- [ ] All methods under 50 lines executable code
- [ ] Auditor approval required before merge