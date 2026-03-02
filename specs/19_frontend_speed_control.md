# FEATURE SPEC: Frontend Variable Speed Control
**Date:** 2026-03-03  
**Status:** Feasible  
**Target Version:** v4.1

## 1. THE VISION
*   **User Story:** As a Remote Operator, I want to adjust the robot's movement speed using a percentage slider (0-100%) so that I can perform precise maneuvers at low speed and cover ground quickly at high speed.
*   **Success Metrics:**
    *   Setting slider to 100% results in `255` PWM sent to backend.
    *   Setting slider to 50% results in `~127` PWM sent to backend.
    *   "Test Speed" sequence confirms audible/visible motor speed changes.

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed. Uses existing HTTP API (`/api/motor/control`).
*   **New Libraries Needed:** None (Standard HTML5/Vanilla JS).
*   **Risk Level:** Low. Client-side calculation change only.

## 3. ATOMIC TASKS (The Roadmap)

### Frontend (HTML - `service_dashboard.html`)
*   [ ] Update `speed-slider` visual labels to explicitly show "%".
*   [ ] Add a "Test Ramp" button to the Motor Control Modal footer or control panel.
*   [ ] (Optional) Add visual markers for "Stall Zone" (0-20%) where motors might hum but not move.

### Frontend (Logic - `dashboard-core.js`)
*   [ ] Update `_setupControls` to handle 0-100 visual range.
*   [ ] Modify `_sendMotorCommand` to map 0-100 input -> 0-255 output.
*   [ ] Implement `runSpeedTest()` function for the new test button.

## 4. INTERFACE SKETCHES

### A. Speed Scaling Logic
*Current Issue:* Slider 100 -> sends 100 (39% power).
*New Logic:*
```javascript
// Inside _sendMotorCommand(direction)
const sliderVal = parseInt(document.getElementById('speed-slider').value);
// Map 0-100 to 0-255
const pwmValue = Math.round((sliderVal / 100) * 255);

// Send payload
const payload = { 
    command: direction, 
    speed: pwmValue 
};
```

### B. The "Speed Ramp" Test
*Automated sequence to verify PWM logic without holding keys.*

```javascript
async function runSpeedTest() {
    const steps = [25, 50, 75, 100];
    const duration = 800; // ms

    for (const pct of steps) {
        // Send forward command at specific % (converted to PWM)
        const pwm = Math.round((pct / 100) * 255);
        console.log(`Testing ${pct}% (PWM: ${pwm})`);
        
        await fetch('/api/motor/control', { 
            method: 'POST', 
            body: JSON.stringify({ command: 'forward', speed: pwm }) 
        });
        
        await new Promise(r => setTimeout(r, duration));
    }
    
    // Stop
    await fetch('/api/motor/control', { 
        method: 'POST', 
        body: JSON.stringify({ command: 'stop', speed: 0 }) 
    });
}
```

### C. UI Changes (`service_dashboard.html`)
```html
<!-- Inside modal-body .control-group -->
<label for="speed-slider">Motor Power</label>
<div class="slider-container">
    <input type="range" id="speed-slider" min="0" max="100" value="50" ...>
    <span id="speed-value">50%</span>
</div>
<div class="test-controls" style="margin-top:10px;">
    <button id="btn-speed-ramp" class="btn-ghost btn-sm">⚡ Run Speed Ramp</button>
</div>
```

## 5. INTEGRATION POINTS
*   **Touches:** `dashboard-core.js` (Method: `_sendMotorCommand`)
*   **Data Flow:** 
    1.  User drags slider (0-100).
    2.  JS converts to 0-255.
    3.  JS POSTs to `/api/motor/control`.
    4.  Python `motor_controller.py` receives 0-255.
    5.  Arduino receives Byte (0-255).

## 6. OPEN QUESTIONS
*   **Stall Threshold:** Most DC motors won't move below ~40-50 PWM (~20%). Should we set the slider `min="20"`?
    *   *Analyst Decision:* Keep `min="0"` to allow complete stops/fine humming if needed, but visually color the slider (via CSS gradient) to indicate low power.
*   **Default Speed:** Currently 50 (which becomes ~127 PWM). This is a safe starting point.

---

## POST-ACTION REPORT
✅ **Spec Created:** `specs/frontend_speed_control.md`
👉 **Next Agent:** Architect / Implementer (to apply changes to `service_dashboard.html` and `dashboard-core.js`)