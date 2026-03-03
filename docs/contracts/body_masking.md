# CONTRACT: LiDAR Body Masking
**Version:** 1.0
**Last Updated:** 2026-03-03
**Status:** Draft

---

## 1. PURPOSE

This module provides configurable angular-distance filtering of raw LiDAR point data to prevent the robot's own physical chassis from being interpreted as obstacles by the `SimpleObstacleAvoidance` algorithm. A list of named "body mask sectors" — each defined by an angle range and a minimum distance threshold — is stored in `RobotState` and applied to every scan before sector evaluation. Operators may configure these sectors at runtime via a dedicated REST API without restarting the server, and the configuration persists across reboots via a JSON config file.

---

## 2. PUBLIC INTERFACE

---

### 2.1 Data Structure: `BodyMaskSector`

```python
# Defined as a TypedDict for annotation purposes. No new class required.
from typing import TypedDict

class BodyMaskSector(TypedDict):
    name: str             # Human-readable label, e.g. "front_chassis"
    angle_min: float      # Degrees. Range: [-180.0, 180.0]. Must be <= angle_max.
    angle_max: float      # Degrees. Range: [-180.0, 180.0]. Must be >= angle_min.
    min_distance_mm: float  # Points closer than this (within angle range) are dropped.
                            # Range: [0.0, 500.0].
```

**Default Mask (applied when no persisted config exists):**

```python
DEFAULT_BODY_MASK: List[BodyMaskSector] = [
    {"name": "front_chassis", "angle_min": -30.0, "angle_max": 30.0,  "min_distance_mm": 280.0},
    {"name": "rear_chassis",  "angle_min": 150.0, "angle_max": 210.0, "min_distance_mm": 180.0},
]
```

> **Note on rear sector:** `angle_max: 210.0` exceeds the nominal [-180, 180] range. `apply_body_mask()` MUST normalize all angles to [-180, 180] before comparison, making this equivalent to [-180, -150] after wrapping. The validation logic in the API must accept values in [-180, 360] to support such wrap-around definitions, but normalize them internally. See Section 2.3 for validation rules.

---

### 2.2 Method: `apply_body_mask` (in `SimpleObstacleAvoidance`)

**Signature:**

```python
def apply_body_mask(
    self,
    points: List[Dict[str, Any]],
    mask: List[BodyMaskSector]
) -> List[Dict[str, Any]]:
    """Filter raw LiDAR points using the configured body mask sectors.

    Args:
        points: Raw point list from LiDARAdapter.get_latest_scan()['points'].
                Each point dict must contain 'angle' (float, degrees) and
                'distance' (float, millimeters).
        mask:   List of BodyMaskSector dicts defining chassis blind spots.

    Returns:
        Filtered list of point dicts. Points matching a mask sector are dropped.
        Points with distance <= 0 are always dropped (invalid).
        If mask is empty, returns the input list unmodified.

    Raises:
        TypeError: If points or mask are not lists.
    """
```

**Behavior Specification:**

- **Input Validation:** Assert `points` is a `list`. Assert `mask` is a `list`. Raise `TypeError` on violation. Do NOT raise on empty lists — return `[]` or the input unchanged respectively.
- **Processing Logic:**
  1. If `mask` is empty, return `points` unchanged.
  2. For each point in `points`:
     a. Extract `angle` (float) and `distance` (float). Skip point if either key is missing.
     b. Drop point if `distance <= 0` (invalid reading).
     c. Normalize angle to [-180.0, 180.0] using the same modular arithmetic already present in `evaluate_sectors()`.
     d. For each sector in `mask`: if `angle_min <= normalized_angle <= angle_max` AND `distance < sector['min_distance_mm']`, drop the point. Break on first matching sector.
     e. If no sector matches, keep the point.
  3. Return the filtered list.
- **Output Guarantee:** Returns a new list (does not mutate the input). All returned points are guaranteed to have `distance > 0`.
- **Side Effects:** None. This is a pure function with no I/O or state changes.

**Error Handling:**

- `points` is not a `list` → Raise `TypeError` with message `"apply_body_mask: 'points' must be a list, got {type(points).__name__}"`
- `mask` is not a `list` → Raise `TypeError` with message `"apply_body_mask: 'mask' must be a list, got {type(mask).__name__}"`
- Individual malformed point dicts (missing keys) → Log a `DEBUG`-level warning and skip that point. Do NOT raise.

**Performance Requirements:**

- Time Complexity: O(P × M) where P = number of points, M = number of mask sectors. Acceptable given P ≤ 360, M ≤ 10.
- Space Complexity: O(P) for the output list.
- **MUST NOT** block the avoidance loop. No I/O, no locking inside this method.

---

### 2.3 Integration point: `run_once` modification (in `SimpleObstacleAvoidance`)

**Modification Specification** (not a new method — describes required change to existing method):

After extracting `points` from `scan_data` and before the distance-based speed scaling block, insert exactly one call:

```python
# --- Body Mask Filtering ---
mask = []
if hasattr(self.hw, 'robot_state') and self.hw.robot_state is not None:
    mask = self.hw.robot_state.lidar_body_mask
points = self.apply_body_mask(points, mask)
# --- End Body Mask Filtering ---
```

- The mask is fetched fresh on every cycle. No caching. This ensures runtime updates are applied immediately.
- If `robot_state` is unavailable, mask defaults to `[]` (no filtering). System degrades gracefully.

---

### 2.4 `RobotState` Property: `lidar_body_mask`

**Signature:**

```python
@property
def lidar_body_mask(self) -> List[BodyMaskSector]:
    """Return the current body mask configuration.

    Returns:
        List of BodyMaskSector dicts. Returns DEFAULT_BODY_MASK if not yet set.
    """

@lidar_body_mask.setter
def lidar_body_mask(self, mask: List[BodyMaskSector]) -> None:
    """Set and persist a new body mask configuration.

    Args:
        mask: Validated list of BodyMaskSector dicts. Caller is responsible
              for pre-validating via validate_body_mask() before assignment.

    Side Effects:
        Persists the new mask to config file (see Section 2.6).
    """
```

**Behavior Specification:**

- **Getter:** Returns `self._lidar_body_mask`. If `_lidar_body_mask` is `None` (not yet loaded), loads from the persisted config file. If file does not exist, returns `DEFAULT_BODY_MASK` and initializes `_lidar_body_mask` with it.
- **Setter:** Assigns to `self._lidar_body_mask`, then calls `self._persist_body_mask()` to write to disk.
- **Thread Safety:** Access to `_lidar_body_mask` MUST be guarded by `self._lidar_mask_lock` (`threading.Lock`). The getter acquires the lock for read. The setter acquires the lock for write + persist.

---

### 2.5 Validation Function: `validate_body_mask`

**Location:** `src/api/routes_config.py` (or wherever the POST route is defined)

**Signature:**

```python
def validate_body_mask(mask_data: Any) -> List[BodyMaskSector]:
    """Validate and normalize a raw body mask payload from an API request.

    Args:
        mask_data: The parsed JSON value of the 'mask' key from the request body.

    Returns:
        Validated and normalized list of BodyMaskSector dicts.

    Raises:
        ValueError: If any validation rule is violated. Message indicates the
                    offending sector index and field.
    """
```

**Validation Rules (all MANDATORY):**

| Field | Rule | Error Message Pattern |
|---|---|---|
| `mask_data` | Must be a `list` | `"'mask' must be a list"` |
| `mask_data` length | 1 ≤ len ≤ 10 | `"'mask' must contain 1–10 sectors"` |
| `name` | str, non-empty, max 64 chars | `"sector[{i}].name: must be a non-empty string (max 64 chars)"` |
| `angle_min` | float/int, in [-180, 360] | `"sector[{i}].angle_min: must be a number in [-180, 360]"` |
| `angle_max` | float/int, in [-180, 360] | `"sector[{i}].angle_max: must be a number in [-180, 360]"` |
| `angle_min` vs `angle_max` | `angle_min <= angle_max` | `"sector[{i}]: angle_min must be <= angle_max"` |
| `min_distance_mm` | float/int, in [0, 500] | `"sector[{i}].min_distance_mm: must be a number in [0, 500]"` |

**Post-validation normalization:** Cast all numeric fields to `float`. Do not modify `name`.

---

### 2.6 Persistence: `_persist_body_mask` (on `RobotState`)

**Signature:**

```python
def _persist_body_mask(self) -> None:
    """Write current body mask to the config file.

    File: config/body_mask.json (relative to project root, resolved via pathlib).
    Format: {"mask": [<BodyMaskSector>, ...]}
    Side Effects: Creates file and parent directories if they do not exist.
    Errors: Logs ERROR and does NOT raise. Persistence failure must not crash the avoidance loop.
    """
```

**Load Counterpart:** `_load_body_mask() -> List[BodyMaskSector]` — called from the getter on first access. Returns `DEFAULT_BODY_MASK` if the file is missing or malformed (logs WARNING in the latter case).

**File Path:** `config/body_mask.json` — resolved using `pathlib.Path(__file__).resolve().parent.parent / "config" / "body_mask.json"` (adjust depth as appropriate for `robot_state.py` location). No hardcoded paths per system constraints.

---

## 3. API ENDPOINTS

### `GET /api/lidar/body_mask`

**Route:** `GET /api/lidar/body_mask`
**Handler file:** `src/api/routes_config.py` (or applicable routes file)

**Response (200 OK):**
```json
{
  "success": true,
  "mask": [
    {"name": "front_chassis", "angle_min": -30.0, "angle_max": 30.0, "min_distance_mm": 280.0},
    {"name": "rear_chassis",  "angle_min": 150.0, "angle_max": 210.0, "min_distance_mm": 180.0}
  ]
}
```

**Behavior:** Reads `hardware_manager.robot_state.lidar_body_mask`. Non-blocking. No side effects.

**Error Response (500):**
```json
{"success": false, "error": "Failed to retrieve body mask: {reason}"}
```

---

### `POST /api/lidar/body_mask`

**Route:** `POST /api/lidar/body_mask`
**Content-Type:** `application/json`

**Request Body:**
```json
{
  "mask": [
    {"name": "front_chassis", "angle_min": -35.0, "angle_max": 35.0, "min_distance_mm": 300.0}
  ]
}
```

**Processing Steps:**
1. Parse JSON body. Return 400 if not valid JSON or `mask` key is absent.
2. Call `validate_body_mask(request.json['mask'])`. Return 400 with error detail on `ValueError`.
3. Assign `hardware_manager.robot_state.lidar_body_mask = validated_mask` (triggers persistence).
4. Return 200.

**Response (200 OK):**
```json
{"success": true, "message": "Body mask updated. {N} sector(s) active."}
```

**Error Responses:**

| Condition | Status | Body |
|---|---|---|
| Missing `mask` key | 400 | `{"success": false, "error": "Request body must contain 'mask' key"}` |
| Validation failure | 400 | `{"success": false, "error": "{ValueError message}"}` |
| `robot_state` unavailable | 503 | `{"success": false, "error": "RobotState not available"}` |
| Unexpected exception | 500 | `{"success": false, "error": "Internal error: {reason}"}` |

**Thread Safety:** The setter on `RobotState` uses `_lidar_mask_lock`. The route itself does not need additional locking.

---

## 4. DATA STRUCTURES

```python
# src/services/obstacle_avoidance.py (add to top of file)
from typing import TypedDict  # Python 3.8+

class BodyMaskSector(TypedDict):
    name: str
    angle_min: float
    angle_max: float
    min_distance_mm: float

DEFAULT_BODY_MASK: List[BodyMaskSector] = [
    {"name": "front_chassis", "angle_min": -30.0, "angle_max":  30.0, "min_distance_mm": 280.0},
    {"name": "rear_chassis",  "angle_min": 150.0, "angle_max": 210.0, "min_distance_mm": 180.0},
]
```

---

## 5. DEPENDENCIES

**`SimpleObstacleAvoidance` now READS:**
- `self.hw.robot_state.lidar_body_mask` — on every `run_once()` call

**`POST /api/lidar/body_mask` WRITES:**
- `hardware_manager.robot_state.lidar_body_mask`

**`RobotState` READS/WRITES:**
- `config/body_mask.json` — via `pathlib` (no hardcoded paths)

**This contract does NOT modify:**
- `LiDARAdapter` (untouched)
- `YDLidarReader` (Phase B — diagnostic only, no contract required now)
- `evaluate_sectors()` (untouched — mask is applied upstream)

---

## 6. CONSTRAINTS (FROM SYSTEM CONSTRAINTS)

- **No Global State:** `lidar_body_mask` lives exclusively in `RobotState`. No module-level variables. *(Section 1 — Architectural Rules)*
- **Concurrency — `threading` only:** `_lidar_mask_lock` is a `threading.Lock()`. No `asyncio`. *(Section 1 — Concurrency)*
- **Non-Blocking Routes:** Both API routes return immediately. No scanning or file I/O on the main Flask thread beyond a single JSON read/write (acceptable). *(Section 1 — Non-Blocking)*
- **No Hardcoded Paths:** Config file path resolved via `pathlib`. *(Section 4 — Forbidden Patterns)*
- **Max Function Length 50 lines:** `apply_body_mask`, `validate_body_mask`, both route handlers, and `_persist_body_mask` must each stay under 50 lines. Refactor if needed. *(Section 4 — Code Quality)*
- **Type Hints Mandatory:** All new Python functions must be fully annotated. *(Section 4 — Code Quality)*
- **Google-style Docstrings:** Required on all new public methods and classes. *(Section 4 — Code Quality)*
- **snake_case JSON fields:** All API request/response fields use `snake_case`. *(Section 4 — Field Naming)*
- **`min_distance_mm` hard cap: 500mm.** Safety limit from spec. Applied in `validate_body_mask`. *(Feature Spec Section 4)*

---

## 7. MEMORY COMPLIANCE

No `_memory_snippet.txt` was provided. No project memory rules to apply beyond what is captured in `system_constraints.md` above.

---

## 8. ACCEPTANCE CRITERIA

**Test Case 1 — Happy Path: Mask filters chassis return**
- Input points: `[{"angle": 0.0, "distance": 150.0, ...}, {"angle": 0.0, "distance": 400.0, ...}]`
- Mask: `[{"name": "front_chassis", "angle_min": -30.0, "angle_max": 30.0, "min_distance_mm": 280.0}]`
- Expected Output: `[{"angle": 0.0, "distance": 400.0, ...}]` (150mm point dropped; 400mm point kept)

**Test Case 2 — Empty mask: passthrough**
- Input: any list of valid points
- Mask: `[]`
- Expected Output: identical to input (no filtering)

**Test Case 3 — Angle wrapping (rear sector)**
- Input: `[{"angle": -170.0, "distance": 100.0, ...}]`
- Mask: `[{"name": "rear_chassis", "angle_min": 150.0, "angle_max": 210.0, "min_distance_mm": 180.0}]`
- Expected Output: `[]` (angle -170° normalizes to -170°, which is within [150°–210°] after wrap-around interpretation — implementer must handle this correctly)
- *Note to Implementer: verify exact normalization behavior for this edge case and add a unit test.*

**Test Case 4 — POST API validation: angle out of range**
- Request body: `{"mask": [{"name": "x", "angle_min": -999, "angle_max": 30, "min_distance_mm": 100}]}`
- Expected: HTTP 400, `{"success": false, "error": "sector[0].angle_min: must be a number in [-180, 360]"}`

**Test Case 5 — POST API validation: min_distance_mm exceeds safety cap**
- Request body: `{"mask": [{"name": "x", "angle_min": -30, "angle_max": 30, "min_distance_mm": 600}]}`
- Expected: HTTP 400, `{"success": false, "error": "sector[0].min_distance_mm: must be a number in [0, 500]"}`

**Test Case 6 — GET returns default mask on first boot**
- State: `config/body_mask.json` does not exist
- Expected: HTTP 200 with `DEFAULT_BODY_MASK` in response

**Test Case 7 — Persistence round-trip**
- Action: POST a custom mask → restart server → GET mask
- Expected: GET returns the same custom mask (loaded from `config/body_mask.json`)

**Test Case 8 — Thread safety: concurrent POST and avoidance loop**
- Action: POST new mask while avoidance loop is running at 100ms interval
- Expected: No deadlock, no crash. Avoidance loop picks up new mask within one cycle.

**Test Case 9 — Invalid point dict (missing keys)**
- Input: `[{"angle": 0.0}]` (missing `distance`)
- Expected: Point is silently skipped. No exception raised. DEBUG log emitted.

---

## 9. OPEN QUESTIONS (Resolved for Contract)

**Q: Does `RobotState` persist across reboots?**
**A (Contract Decision):** YES. This contract mandates persistence via `config/body_mask.json`. The implementer MUST implement `_persist_body_mask()` and `_load_body_mask()` on `RobotState`. The avoidance algorithm relies on the mask being correct on startup.

**Q: What about the rear sector exceeding 180°?**
**A (Contract Decision):** The API validation accepts `angle_min`/`angle_max` in [-180, 360] to support wrap-around sector definitions. `apply_body_mask()` normalizes all point angles to [-180, 180] using the existing modular arithmetic pattern. The implementer must document how they handle sectors that span the ±180° boundary.

---

```
✅ Contract Created: docs/contracts/body_masking.md v1.0
📋 Work Order: (below)
```

---

---

# WORK ORDER FOR IMPLEMENTER

**Target Files:**
- `src/services/obstacle_avoidance.py` — Add `apply_body_mask()`, modify `run_once()`
- `src/hardware/robot_state.py` — Add `lidar_body_mask` property + persistence
- `src/api/routes_config.py` — Add GET + POST routes

**Contract Reference:** `docs/contracts/body_masking.md` v1.0

---

## Strict Constraints (NON-NEGOTIABLE)

1. No global state. All mask data lives in `RobotState`.
2. `threading.Lock` only. No asyncio.
3. No hardcoded paths. Use `pathlib`.
4. Max 50 lines per function. Refactor if needed.
5. Full type hints on all new functions.
6. Google-style docstrings on all new public methods.
7. All JSON fields snake_case.
8. `min_distance_mm` hard cap: 500. Enforced in `validate_body_mask`.

---

## Required Logic

### Step 1 — `src/services/obstacle_avoidance.py`

1. Add `BodyMaskSector` TypedDict and `DEFAULT_BODY_MASK` constant at top of file.
2. Implement `apply_body_mask(self, points, mask) -> List[Dict]` as a method on `SimpleObstacleAvoidance`. See contract Section 2.2. Max 50 lines.
3. In `run_once()`, immediately after `points = scan_data.get('points', [])`, insert the body mask fetch + `apply_body_mask()` call block (Section 2.3).

### Step 2 — `src/hardware/robot_state.py`

1. Add `self._lidar_body_mask: Optional[List[BodyMaskSector]] = None` and `self._lidar_mask_lock = threading.Lock()` to `__init__`.
2. Implement `lidar_body_mask` property (getter + setter) per Section 2.4.
3. Implement `_load_body_mask()` and `_persist_body_mask()` per Section 2.6. Use `pathlib`. Wrap file I/O in try/except — never raise from persist.

### Step 3 — `src/api/routes_config.py`

1. Implement `validate_body_mask(mask_data)` per Section 2.5. All validation rules enforced. Max 50 lines.
2. Implement `GET /api/lidar/body_mask` route per Section 3.
3. Implement `POST /api/lidar/body_mask` route per Section 3. Call `validate_body_mask` before assignment.

---

## Integration Points

- `run_once()` READS `self.hw.robot_state.lidar_body_mask` each cycle.
- `POST` route WRITES `hardware_manager.robot_state.lidar_body_mask`.
- `RobotState` setter triggers `_persist_body_mask()` automatically.
- `apply_body_mask()` is called before `evaluate_sectors()` and before distance-based speed scaling.

---

## Success Criteria

- All 9 acceptance test cases pass.
- No function exceeds 50 lines.
- Server does not crash if `config/body_mask.json` is absent on first boot.
- Avoidance loop continues to function if `robot_state` is unavailable (degrades gracefully to no masking).
- Auditor approval required before merge.

---

## 📋 APPENDIX: API MAP UPDATE

**⚠️ MANUAL ACTION REQUIRED:** Paste into `docs/API_MAP_lite.md`:

```markdown
### Module: `lidar_body_mask`
**Location:** `src/api/routes_config.py` (routes) + `src/hardware/robot_state.py` (state) + `src/services/obstacle_avoidance.py` (filter)
**Status:** Designed (not yet implemented)
**Contract:** `docs/contracts/body_masking.md` v1.0

**Public Interface:**
- `GET /api/lidar/body_mask` → `{"success": bool, "mask": List[BodyMaskSector]}`
  - Purpose: Retrieve current body mask configuration
- `POST /api/lidar/body_mask` → `{"success": bool, "message": str}`
  - Purpose: Update and persist body mask configuration
- `SimpleObstacleAvoidance.apply_body_mask(points: List[Dict], mask: List[BodyMaskSector]) -> List[Dict]`
  - Purpose: Filter raw LiDAR points before sector evaluation
- `RobotState.lidar_body_mask` (property, get/set)
  - Purpose: Thread-safe storage + persistence of mask config

**Dependencies:**
- Imports: `threading`, `pathlib`, `json`, `typing`
- Called by: `run_once()` (avoidance loop), `POST /api/lidar/body_mask` (API)
- Reads from: `config/body_mask.json`
```

---

## ⏭️ HUMAN WORKFLOW CHECKPOINT

**Files you should now have:**
- ✅ `docs/contracts/body_masking.md` v1.0
- ✅ `work_order.md`
- ✅ API Map snippet (above) — ready to paste

**Before moving to Implementer:**
1. Review Test Case 3 (rear sector angle wrapping) — confirm your expected behavior with the implementer.
2. Confirm the path depth of `robot_state.py` so the implementer resolves `config/body_mask.json` correctly.
3. Update `API_MAP_lite.md`.

**Next Agent:** `02_implementer.md`

**Verification Command (paste to Implementer):**
```
/verify-context: contracts/body_masking.md, work_order.md, API_MAP_lite.md, system_constraints.md
```