
# PS_RCS_PROJECT | System Style Guide (V4.1)

## 1. CORE PHILOSOPHY
*   **Lean V4.0:** Minimize token waste. Logic first, polish second.
*   **Contract-First:** No implementation begins without an Architect-approved Contract.
*   **Hardware Abstraction:** No direct GPIO/Serial calls outside of `src/services/`.
*   **Single Source of Truth:** `RobotState` is the only valid source for telemetry data.
*   **Progressive Disclosure:** UI Complexity is hidden by default. Information is revealed on demand (Hover/Click).

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

## 4. CSS & AESTHETIC STANDARDS (X/Linear Dark)
*   **Theme Architecture:** CSS Variables only. No hardcoded hex codes in components.
*   **Layout:** **Bento Grid** (Responsive Grid of Cards).
*   **Visual Language:** "X/Linear Professional" / "Control Center".
    *   **Shapes:** Large Border Radius (`20px` - `24px` for cards, `12px` - `16px` for buttons).
    *   **Depth:** Soft, diffused shadows (`0 8px 30px rgba(0,0,0,0.08)`).
    *   **Materials:** "Frosted Glass" (Backdrop blur `blur(20px)`) for modals and overlays.
*   **Color Palette (Dark-First):**
    *   **Background (Dark):** `#0F0F0F` (Near Black).
    *   **Surface (Cards):** `#1A1A1A` (Dark Gray).
    *   **Primary Action:** `#888888` (Neutral Silver/White).
    *   **Success:** `#10B981` (Green).
    *   **Text (Primary):** `#F0F0F0` (Off-White).
    *   **Text (Secondary):** `#B0B0B0` (Medium Gray).
    *   **Critical Rule:** **NO BLUE ACCENTS** in any UI element (violates X/Linear aesthetic).
*   **Theme Toggle Requirement:**
    *   Dark mode is default (`data-theme="dark"` on `<html>`).
    *   Light mode must be toggleable via persistent localStorage (`ps-rcs-theme` key).
    *   All color tokens MUST use CSS variables (never hardcoded hex).
*   **Interaction Model:**
    *   **Video Feeds:** Hidden until modal open (Progressive Disclosure).
    *   **Stream Lifecycle:** MUST stop when modal/tab inactive (bandwidth optimization).
    *   **Controls:** Hidden until interaction (Hover/Click).
*   **Typography:** System Fonts (Inter, -apple-system, BlinkMacSystemFont).

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