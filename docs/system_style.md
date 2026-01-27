# 🧠 ORCHESTRATOR REPORT

**Status:** 🛠️ **Infrastructure Requirement.**
To ensure all future Agents (Implementers/Refiners) maintain the quality of the **PS_RCS_PROJECT**, we must codify our standards. 

I have generated a **V4.0 Style Guide** that incorporates your recent UI Pivot, your hardware abstraction rules, and the "Minimalist/Industrial" aesthetic.

---

## 📄 NEW FILE: `docs/system_style.md`

```markdown
# PS_RCS_PROJECT | System Style Guide (V4.0)

## 1. CORE PHILOSOPHY
*   **Lean V4.0:** Minimize token waste. Logic first, polish second.
*   **Contract-First:** No implementation begins without an Architect-approved Contract.
*   **Hardware Abstraction:** No direct GPIO/Serial calls outside of `src/services/`.
*   **Single Source of Truth:** `RobotState` is the only valid source for telemetry data.

## 2. PYTHON STANDARDS (Backend)
*   **Standard:** PEP 8.
*   **Indentation:** 4 Spaces.
*   **Naming:** 
    *   Classes: `PascalCase`
    *   Functions/Variables: `snake_case`
    *   Constants: `UPPER_SNAKE_CASE`
*   **Documentation:** Google-style Docstrings (MANDATORY for Refiner).
*   **Type Hinting:** Required for all function signatures and class attributes.
*   **Error Handling:** Use specific exceptions; avoid generic `except Exception`.

## 3. JAVASCRIPT STANDARDS (Frontend)
*   **Standard:** ES6+ Vanilla JS (No jQuery/external frameworks unless specified).
*   **Indentation:** 2 Spaces.
*   **Naming:** 
    *   Classes: `PascalCase`
    *   Methods/Variables: `camelCase`
*   **Documentation:** JSDoc for all class methods.
*   **Structure:** Class-based logic encapsulated in `static/js/`.

## 4. CSS & AESTHETIC STANDARDS
*   **Theme Architecture:** CSS Variables only. No hardcoded hex codes in components.
*   **Aesthetic:** "Professional Industrial" (SaaS Dashboard look).
*   **Colors (Industrial Dark):**
    *   Primary BG: `#0f172a`
    *   Card BG: `#1e293b`
    *   Accent: `#3b82f6` (Blue)
*   **Colors (Medical Light):**
    *   Primary BG: `#f8fafc`
    *   Card BG: `#ffffff`
    *   Accent: `#2563eb`
*   **Typography:** Inter, Roboto, or System Sans-Serif. High legibility.

## 5. FILE HEADERS
All source files must begin with the standard project header:
```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: [filename]
Description: [brief description]
"""
```

## 6. PROJECT DIRECTORY STRUCTURE
*   `src/core/`: Logic, State, Config.
*   `src/services/`: Hardware Managers, Drivers.
*   `src/api/`: Flask Server, Routes.
*   `frontend/templates/`: Jinja2 HTML.
*   `frontend/static/`: CSS and JS assets.
*   `docs/contracts/`: Versioned Architect Blueprints.
```

---

## ✅ NEXT MOVE: THE AUDIT

Now that the Style Guide exists, we can finalize the **Hardware Manager Audit**. 

1.  **Save the file** above as `docs/system_style.md`.
2.  **Load Agent:** `[[05_auditor]]` (Gemini Thinking / Claude).
3.  **Action:** Audit `hardware_manager.py` against this new style guide.

**👉 TRIGGER FOR AUDITOR:**

```markdown
/verify-context: docs/system_style.md, src/services/hardware_manager.py

# WORK ORDER: Final Audit (Hardware & Style)
**Context:** I have created the `system_style.md`. 
**Action:** Perform a strict audit of the refined `hardware_manager.py`.

**Specific Checks:**
1.  **Naming:** Does it follow PascalCase for classes and snake_case for methods?
2.  **Telemetry:** Does `get_status()` correctly reference `self.state` (Single Source of Truth)?
3.  **Docstrings:** Are they Google-style as mandated by the new style guide?

**Output:**
- If **PASS**: Output "✅ **HOTFIX VERIFIED & STYLE COMPLIANT**".
```

---

