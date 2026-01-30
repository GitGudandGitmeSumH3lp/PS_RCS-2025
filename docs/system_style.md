
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

## 4. CSS & AESTHETIC STANDARDS (Apple / Bento)
*   **Theme Architecture:** CSS Variables only. No hardcoded hex codes in components.
*   **Layout:** **Bento Grid** (Responsive Grid of Cards).
*   **Visual Language:** "Modern Consumer" / "Control Center".
    *   **Shapes:** Large Border Radius (`20px` - `24px`).
    *   **Depth:** Soft, diffused shadows (`0 8px 30px rgba(0,0,0,0.08)`).
    *   **Materials:** "Frosted Glass" (Backdrop blur) for modals and overlays.
*   **Color Palette (Light/Clean):**
    *   **Background:** `#F5F5F7` (Light Grey).
    *   **Surface (Cards):** `#FFFFFF` (White).
    *   **Primary Action:** `#007AFF` (San Francisco Blue).
    *   **Success:** `#34C759` (Green).
    *   **Text:** `#1D1D1F` (Near Black).
*   **Interaction Model:**
    *   **Video Feeds:** Hidden or blurred static preview by default. Click card to expand/wake stream.
    *   **Controls:** Hidden until card interaction (Hover/Click).
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