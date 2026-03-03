Good enough — I have all 7 source files and the full researcher findings from the orchestration report embedded in context. Running verification now.

---

✅ **Context verified. Proceeding.**

All required files present:
- `system_constraints.md` ✅
- `src/hardware/lidar_adapter.py` ✅
- `src/hardware/hardware_manager.py` ✅
- `src/services/obstacle_avoidance.py` ✅
- `src/core/state.py` ✅
- `config/settings.json` ✅
- `docs/research/lidar_front_sector_diagnosis.md` ✅ (via orchestration report)

---

Now generating all four contract documents.The bash environment isn't available in this session. I'll deliver all contracts directly in the response — fully formatted and ready to save.

---

✅ **Context verified. Proceeding.**

---

# CONTRACT: LiDAR Angle Offset Correction
**Version:** 1.0
**Last Updated:** 2026-03-03
**Status:** Draft

## 1. PURPOSE

This module adds a configurable angular offset to the LiDAR hardware pipeline to compensate for physical sensor mounting misalignment. The offset is applied inside `LiDARAdapter.get_latest_scan()` — the single point of data ingestion — so all downstream consumers (body mask, sector evaluation, obstacle avoidance) automatically receive corrected angles with no changes required in those modules. The value is persisted in `settings.json` and read once at adapter construction.

> ⚠️ **OPERATOR PREREQUISITE (Recommendation 1 — must complete before implementation):**
> Place a flat obstacle ~600 mm directly in front of the robot. Enable DEBUG logging in `ydlidar_reader.py`. Start the server and observe raw angle clusters. If the cluster appears at e.g. 135° instead of 0°, the correction is **−135.0**. Record this as `LIDAR_ANGLE_OFFSET_DEG` in `settings.json`. Until calibration is done, leave the value at **0.0** — behaviour is unchanged.

---

## 2. PUBLIC INTERFACE

### 2.1 `settings.json` — new key
```json
"LIDAR_ANGLE_OFFSET_DEG": 0.0
```
- **Type:** `float` | **Range:** `[-180.0, 180.0]` | **Default:** `0.0`
- **Semantics:** `corrected = (raw + offset + 180) % 360 − 180`

---

### 2.2 `Settings` dataclass — new field
```python
LIDAR_ANGLE_OFFSET_DEG: float = 0.0
```
**Validation** (in loader/`__post_init__`):
```python
if not (-180.0 <= self.LIDAR_ANGLE_OFFSET_DEG <= 180.0):
    raise ValueError(
        f"LIDAR_ANGLE_OFFSET_DEG must be in [-180, 180], got {self.LIDAR_ANGLE_OFFSET_DEG}"
    )
```

---

### 2.3 `LiDARAdapter.__init__` — new config key
```python
def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
    """
    Initialize LiDARAdapter with optional configuration.

    Args:
        config: Optional dict. New key added to existing set:
            - angle_offset_deg (float): Mounting offset in degrees.
              Valid range [-180, 180]. Default 0.0.
              Applied as: corrected = (raw + offset + 180) % 360 - 180

    Raises:
        ValueError: If angle_offset_deg is outside [-180, 180].
    """
```
New internal attribute: `self._angle_offset_deg: float = 0.0`

Config-loop addition:
```python
elif key == "angle_offset_deg":
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"'angle_offset_deg' expects float, got {type(value).__name__}"
        )
    if not (-180.0 <= float(value) <= 180.0):
        raise ValueError(
            f"'angle_offset_deg' must be in [-180, 180], got {value}"
        )
    self._angle_offset_deg = float(value)
```

---

### 2.4 `LiDARAdapter.get_latest_scan` — apply offset
**Signature:** *(unchanged)*
```python
def get_latest_scan(self) -> Dict[str, Any]:
    """
    Retrieve the most recent scan data in frontend-compatible format.
    All 'angle' values in returned points are corrected by self._angle_offset_deg.
    x/y coordinates are recalculated from the corrected angle.
    """
```
**Offset application** (per point, before appending to `points_data`):
```python
import math
corrected_angle = (p['angle'] + self._angle_offset_deg + 180) % 360 - 180
rad = math.radians(corrected_angle)
point_dict = {
    'angle':    corrected_angle,
    'distance': p['distance'],
    'quality':  p['quality'],
    'x':        round(p['distance'] * math.cos(rad), 2),
    'y':        round(p['distance'] * math.sin(rad), 2),
}
```
- **Processing order:** Offset applied *before* obstacle classification (`distance < 1000` check unchanged).
- **Performance:** O(n), no I/O.
- **Side Effects:** None beyond existing logging.

---

### 2.5 `HardwareManager.__init__` — pass offset from settings
```python
self.lidar = LiDARAdapter(config={
    "port":               settings.LIDAR_PORT,
    "baudrate":           settings.LIDAR_BAUD_RATE,
    "max_queue_size":     1000,
    "enable_simulation":  False,
    "angle_offset_deg":   settings.LIDAR_ANGLE_OFFSET_DEG,   # ← NEW
})
```

---

## 3. DEPENDENCIES
- **Calls:** `settings.json` via `Settings` (read once at init)
- **Called by:** `HardwareManager.__init__`; downstream consumers untouched

## 4. DATA STRUCTURES
No new types. `angle_offset_deg` is a plain `float`.

## 5. CONSTRAINTS
- §1: threading only, Python 3.9+
- §4: no hardcoded offset value in source; must come from `settings.json`
- §4: full type hints, Google docstrings, ≤50 lines per function

## 6. MEMORY COMPLIANCE
No `_memory_snippet.txt` provided.

## 7. ACCEPTANCE CRITERIA

| Test | Input | Expected |
|---|---|---|
| A-1 Zero offset | `offset=0.0`, raw angle `45.0°` | corrected `45.0°` |
| A-2 Positive offset | `offset=90.0`, raw `45.0°` | corrected `135.0°` |
| A-3 Mounting correction | `offset=−135.0`, raw `135.0°` | corrected `0.0°` ✓ front |
| A-4 Wraparound | `offset=90.0`, raw `150.0°` | corrected `60.0°` |
| A-5 Invalid rejected | `offset=181.0` | `ValueError` at `__init__` |
| A-6 Missing key default | no key in `settings.json` | `Settings` defaults to `0.0` |

---
---

# CONTRACT: Body Mask Angle Space Fix
**Version:** 1.0
**Last Updated:** 2026-03-03
**Status:** Draft

## 1. PURPOSE

`apply_body_mask()` currently converts angles to the 0–360° range before comparing against mask sectors, but `DEFAULT_BODY_MASK` defines sectors in [−180, 180] (e.g., `front_chassis: −30°..30°`). This mismatch means the front sector never matches any points — the root cause of the front-sector blindness bug. This contract redesigns `apply_body_mask()` to perform all comparisons exclusively in the [−180, 180] range and updates `DEFAULT_BODY_MASK` to correctly represent the rear sector (which wraps at ±180°) as two split sectors.

---

## 2. PUBLIC INTERFACE

### 2.1 `_normalize_angle` — already exists, contract confirms signature
```python
def _normalize_angle(angle: float) -> float:
    """Normalize angle to [-180, 180] using modular arithmetic.

    Args:
        angle: Raw angle in degrees, any range.

    Returns:
        float: Equivalent angle in [-180.0, 180.0].
    """
```
Implementation may use the modular form `(angle + 180) % 360 - 180` instead of the while-loop to ensure O(1) rather than O(n-wraps) behaviour.

---

### 2.2 `apply_body_mask` — redesigned
```python
def apply_body_mask(
    self,
    points: List[Dict[str, Any]],
    mask: List[BodyMaskSector]
) -> List[Dict[str, Any]]:
    """Filter raw LiDAR points using the configured body mask sectors.

    All angle comparisons are performed in the normalized [-180, 180] range.
    Mask sector angle_min and angle_max MUST be defined in [-180, 180].
    Sectors that wrap around ±180° (e.g., the rear) must be split into two
    sectors by the mask author; this function does NOT split automatically.

    Args:
        points: Raw point list from LiDARAdapter.get_latest_scan()['points'].
                Each point dict must contain 'angle' (float, degrees) and
                'distance' (float, millimeters).
        mask:   List of BodyMaskSector dicts. Each sector angle_min/max must
                be in [-180, 180] with angle_min <= angle_max.

    Returns:
        Filtered list of point dicts. A point is DROPPED if ALL of:
            - Its normalized angle satisfies angle_min <= angle <= angle_max
            - Its distance < sector['min_distance_mm']
        Points with distance <= 0 are always dropped (invalid reading).
        If mask is empty, returns input list unmodified.

    Raises:
        TypeError: If points or mask are not lists.
    """
```

**Behaviour — key change from current implementation:**

*Current (buggy):*
```python
angle_0_360 = angle if angle >= 0 else angle + 360   # converts to 0-360
# then compares against sectors defined in [-180, 180]  ← mismatch
```

*New (correct):*
```python
norm_angle = _normalize_angle(p['angle'])   # stays in [-180, 180]
# compare directly against sector angle_min / angle_max in [-180, 180]
if sector['angle_min'] <= norm_angle <= sector['angle_max'] and \
        distance < sector['min_distance_mm']:
    keep = False
```
**No 0-360 conversion. The `angle_0_360` line is removed entirely.**

---

### 2.3 `DEFAULT_BODY_MASK` — updated constant
```python
DEFAULT_BODY_MASK: List[BodyMaskSector] = [
    {
        "name":             "front_chassis",
        "angle_min":        -30.0,
        "angle_max":         30.0,
        "min_distance_mm":  280.0,
    },
    {
        "name":             "rear_chassis_pos",   # 150° to 180°
        "angle_min":        150.0,
        "angle_max":        180.0,
        "min_distance_mm":  180.0,
    },
    {
        "name":             "rear_chassis_neg",   # -180° to -150°
        "angle_min":       -180.0,
        "angle_max":       -150.0,
        "min_distance_mm":  180.0,
    },
]
```

**Rationale:** The old `rear_chassis` sector `(150°, 210°)` was defined with `210°` — impossible in [−180, 180]. Splitting into `[150, 180]` and `[−180, −150]` covers the same physical rear region correctly.

**Convention note (MANDATORY — must be documented in code comment above constant):**
```
# CONVENTION: All BodyMaskSector angles MUST be in [-180, 180].
# Sectors crossing the ±180° boundary MUST be split into two entries.
```

---

### 2.4 Unit test requirement
A unit test must be added to the test suite verifying the front-sector fix:

```python
def test_front_sector_mask_applied():
    """Front points within min_distance must be dropped after mask fix."""
    avoidance = SimpleObstacleAvoidance(mock_hw)
    mask = [{"name": "front_chassis", "angle_min": -30.0,
              "angle_max": 30.0, "min_distance_mm": 280.0}]
    points = [
        {"angle":   0.0, "distance": 200.0},   # inside front sector, close → DROP
        {"angle":  10.0, "distance": 150.0},   # inside front sector, close → DROP
        {"angle":   0.0, "distance": 350.0},   # inside front sector, far  → KEEP
        {"angle":  90.0, "distance": 200.0},   # outside front sector      → KEEP
    ]
    result = avoidance.apply_body_mask(points, mask)
    assert len(result) == 2
    assert all(p["distance"] > 280 or abs(p["angle"]) > 30 for p in result)

def test_rear_sector_wraparound():
    """Rear sector split correctly covers both ±180° sides."""
    avoidance = SimpleObstacleAvoidance(mock_hw)
    mask = DEFAULT_BODY_MASK  # uses split rear sectors
    points = [
        {"angle": 160.0, "distance": 100.0},   # rear_pos sector → DROP
        {"angle":-160.0, "distance": 100.0},   # rear_neg sector → DROP
        {"angle": 160.0, "distance": 300.0},   # rear_pos, far   → KEEP
    ]
    result = avoidance.apply_body_mask(points, mask)
    assert len(result) == 1
```

---

## 3. DEPENDENCIES
- **Calls:** `_normalize_angle()` (module-level helper, same file)
- **Called by:** `run_once()` in `SimpleObstacleAvoidance`; `state.py` body-mask property

## 4. DATA STRUCTURES
`BodyMaskSector` TypedDict is unchanged. The **convention** that `angle_min <= angle_max` and both are in `[-180, 180]` is now a documented and enforced precondition.

## 5. CONSTRAINTS
- §4: ≤50 lines for `apply_body_mask`; the redesigned version is shorter than current
- §4: type hints, Google docstrings

## 6. MEMORY COMPLIANCE
No `_memory_snippet.txt` provided.

## 7. ACCEPTANCE CRITERIA

| Test | Input | Expected |
|---|---|---|
| B-1 Front drop | angle=`0°`, dist=`200mm`, mask front `±30°/280mm` | Point dropped |
| B-2 Front keep (far) | angle=`0°`, dist=`350mm`, same mask | Point kept |
| B-3 Front keep (outside) | angle=`90°`, dist=`200mm`, same mask | Point kept |
| B-4 Rear drop pos | angle=`160°`, dist=`100mm`, split rear mask | Point dropped |
| B-5 Rear drop neg | angle=`−160°`, dist=`100mm`, split rear mask | Point dropped |
| B-6 Empty mask | any points, `mask=[]` | Returns input unchanged |
| B-7 TypeError | `points` is not a list | `TypeError` raised |

---
---

# CONTRACT: Decouple State and Service — `lidar_types.py`
**Version:** 1.0
**Last Updated:** 2026-03-03
**Status:** Draft

## 1. PURPOSE

`state.py` currently imports `BodyMaskSector` and `DEFAULT_BODY_MASK` from `obstacle_avoidance.py`. This is an architectural inversion: a core state module must not depend on a service module. This contract creates a new shared types module `src/core/lidar_types.py` and redirects both `state.py` and `obstacle_avoidance.py` to import from it. This is a **pure refactor** — zero functional change.

---

## 2. PUBLIC INTERFACE

### 2.1 New file: `src/core/lidar_types.py`
```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/core/lidar_types.py
Description: Shared type definitions for LiDAR processing.
             This module has NO imports from other project modules
             to prevent circular dependencies.
"""
from typing import List
from typing import TypedDict


class BodyMaskSector(TypedDict):
    """Defines a single angular sector of the robot chassis to mask.

    Attributes:
        name: Human-readable identifier (e.g., 'front_chassis').
        angle_min: Sector start angle in degrees. Must be in [-180, 180].
        angle_max: Sector end angle in degrees. Must be in [-180, 180].
                   Must satisfy angle_min <= angle_max.
                   Sectors crossing ±180° must be split into two entries.
        min_distance_mm: Points closer than this within the sector are masked.
    """
    name: str
    angle_min: float
    angle_max: float
    min_distance_mm: float


# CONVENTION: All angles in [-180, 180]. Wrap-around sectors must be split.
DEFAULT_BODY_MASK: List[BodyMaskSector] = [
    {
        "name":             "front_chassis",
        "angle_min":        -30.0,
        "angle_max":         30.0,
        "min_distance_mm":  280.0,
    },
    {
        "name":             "rear_chassis_pos",
        "angle_min":        150.0,
        "angle_max":        180.0,
        "min_distance_mm":  180.0,
    },
    {
        "name":             "rear_chassis_neg",
        "angle_min":       -180.0,
        "angle_max":       -150.0,
        "min_distance_mm":  180.0,
    },
]
```

> Note: `DEFAULT_BODY_MASK` here already incorporates the Module B fix (split rear sectors). Modules B and C are delivered together; Module C's source of truth for `DEFAULT_BODY_MASK` is Module B's specification.

---

### 2.2 `src/services/obstacle_avoidance.py` — import change
```python
# REMOVE:
class BodyMaskSector(TypedDict): ...      # local definition — DELETE
DEFAULT_BODY_MASK: List[BodyMaskSector] = [...]   # local definition — DELETE

# ADD at top of imports:
from src.core.lidar_types import BodyMaskSector, DEFAULT_BODY_MASK
```
No other changes to `obstacle_avoidance.py` from this module.

---

### 2.3 `src/core/state.py` — import change
```python
# REMOVE:
from src.services.obstacle_avoidance import BodyMaskSector, DEFAULT_BODY_MASK

# ADD:
from src.core.lidar_types import BodyMaskSector, DEFAULT_BODY_MASK
```
No other changes to `state.py` from this module.

---

## 3. DEPENDENCIES
- **`lidar_types.py` imports:** stdlib only (`typing`). No project imports.
- **`state.py` imports from:** `src.core.lidar_types` (replaces service import)
- **`obstacle_avoidance.py` imports from:** `src.core.lidar_types` (replaces local definition)
- **All other files:** No changes required

## 4. DATA STRUCTURES
`BodyMaskSector` and `DEFAULT_BODY_MASK` — definitions moved, not altered (except rear-sector split from Module B, which is applied in the same pass).

## 5. CONSTRAINTS
- §1 Architectural Rule: "No Global State" — `lidar_types.py` contains only type definitions and a constant. Compliant.
- §1 Architectural Rule: Eliminates the inverted dependency `state → obstacle_avoidance`. Resolves Defect #4.
- §4: Full type hints and Google docstrings in `lidar_types.py`.

## 6. MEMORY COMPLIANCE
No `_memory_snippet.txt` provided.

## 7. ACCEPTANCE CRITERIA

| Test | Verification |
|---|---|
| C-1 Import resolves | `from src.core.lidar_types import BodyMaskSector, DEFAULT_BODY_MASK` succeeds |
| C-2 No circular import | `python -c "from src.core.state import RobotState"` exits 0 |
| C-3 No circular import | `python -c "from src.services.obstacle_avoidance import SimpleObstacleAvoidance"` exits 0 |
| C-4 Functional parity | All existing body-mask tests pass without modification |
| C-5 No duplicate definition | `BodyMaskSector` defined in exactly one place (`lidar_types.py`) |

---
---

# CONTRACT: Safety Distance & Logging Tweaks
**Version:** 1.0
**Last Updated:** 2026-03-03
**Status:** Draft

## 1. PURPOSE

Three small but operationally significant fixes that do not warrant separate modules:

1. **Safety distance scaling zone** — `hardware_manager.py` currently calls `enable_obstacle_avoidance(safety_distance_mm=300)`, which equals `STOP_DIST_MM`. This eliminates the speed-scaling zone defined in `obstacle_avoidance.py` (linear ramp between `STOP_DIST_MM=300` and `SAFE_DIST_MM=700`). Changing to 500 mm restores the intended two-zone behaviour: robot decelerates between 500–700 mm and stops at 300 mm.

2. **Missing body-mask config elevated to WARNING** — `state.py._load_body_mask()` logs at INFO when `body_mask.json` is absent. In production this is a silent misconfiguration. Elevating to WARNING ensures operator visibility.

3. **Diagnostic raw-point logging in `run_once()`** — After fetching points and before body-mask filtering, log the first 5 raw points to aid future calibration and debugging.

---

## 2. PUBLIC INTERFACE

### 2.1 `HardwareManager.set_mode` — safety distance change

**Location:** `hardware_manager.py` line ~277

```python
# CURRENT (buggy):
self.enable_obstacle_avoidance(safety_distance_mm=300, speed=self.auto_speed)

# NEW:
self.enable_obstacle_avoidance(safety_distance_mm=500, speed=self.auto_speed)
```

**Behaviour Specification:**
- `SimpleObstacleAvoidance.__init__` receives `safety_distance_mm=500`.
- `self.safety_distance = 500` in the avoidance instance.
- In `run_once()`, `make_decision()` now uses `sectors['front'] > 500` as the "clear" threshold — matching the midpoint of the scaling ramp.
- Speed scaling zone is thereby active: robot decelerates from full speed at 700 mm down to 0 at 300 mm, with 500 mm as the "considered blocked" decision threshold.
- **No signature change** to `enable_obstacle_avoidance` or `set_mode`.

---

### 2.2 `RobotState._load_body_mask` — log level change

**Location:** `state.py`, inside `_load_body_mask()`

```python
# CURRENT:
logger.info("No body mask config file found, using default mask")

# NEW:
logger.warning(
    "No body_mask.json found at %s — using DEFAULT_BODY_MASK. "
    "Run calibration and POST /api/lidar/body-mask to persist a validated config.",
    config_path
)
```

**Behaviour Specification:**
- Level changed from `INFO` to `WARNING`.
- Message includes the expected file path and actionable guidance.
- No functional change; still returns `DEFAULT_BODY_MASK`.

---

### 2.3 `SimpleObstacleAvoidance.run_once` — diagnostic log

**Location:** `obstacle_avoidance.py`, in `run_once()`, after `scan_data` is fetched and before `apply_body_mask()` is called.

```python
def run_once(self, speed: int = None) -> str:
    """Executes one obstacle-avoidance cycle.

    Args:
        speed: PWM speed override. If None, uses self._speed.

    Returns:
        str: The motion decision taken ('forward', 'left', 'right',
             'backward', or 'stop').
    """
    ...
    points = scan_data.get('points', []) if isinstance(scan_data, dict) else []

    # Diagnostic: log first 5 raw points before masking (DEBUG level)
    if points:
        sample = points[:5]
        logger.debug(
            "run_once raw sample (pre-mask): %s",
            [(round(p.get('angle', 0), 1), round(p.get('distance', 0), 0))
             for p in sample]
        )
    else:
        logger.debug("run_once: no raw points received from adapter")

    # --- Body Mask Filtering (existing) ---
    ...
```

**Behaviour Specification:**
- Log level: `DEBUG` (not INFO — avoids flooding production logs).
- Logged before `apply_body_mask()` to capture pre-filter state.
- Format: list of `(angle, distance)` tuples for the first 5 points.
- If `points` is empty, logs a distinct "no raw points" message.
- **No change to return type or control flow.**

---

## 3. DEPENDENCIES
- **2.1** touches only `hardware_manager.py` (one integer literal change)
- **2.2** touches only `state.py` (one log call change)
- **2.3** touches only `obstacle_avoidance.py` (one log block inserted)
- No new imports required in any file

## 4. DATA STRUCTURES
No new types.

## 5. CONSTRAINTS
- §4: ≤50 lines per function — all three touch sites are small additions inside existing functions; no function exceeds 50 lines after changes.
- §4: Type hints unchanged (no new params).
- §1: threading-safe — all changes are read-only logging or a single int literal; no new shared state.

## 6. MEMORY COMPLIANCE
No `_memory_snippet.txt` provided.

## 7. ACCEPTANCE CRITERIA

| Test | Verification |
|---|---|
| D-1 Safety distance | `avoidance.safety_distance == 500` after `set_mode('auto')` |
| D-2 Scaling zone active | Front obstacle at 600 mm → effective speed is between 0 and base speed (not full speed) |
| D-3 Stop still works | Front obstacle at 250 mm → decision is `stop`, effective speed = 0 |
| D-4 Warning logged | Delete `config/body_mask.json`, restart server → log shows WARNING with file path |
| D-5 Diagnostic appears | Set log level to DEBUG, run avoidance cycle → `run_once raw sample` line appears before mask |
| D-6 No INFO flood | Log level set to INFO → diagnostic line is absent (DEBUG suppressed) |

---
---

# WORK ORDER FOR IMPLEMENTER

**Contract References:**
- `CONTRACT_A_lidar_angle_offset.md` v1.0
- `CONTRACT_B_body_mask_angle_fix.md` v1.0
- `CONTRACT_C_decouple_state_service.md` v1.0
- `CONTRACT_D_safety_distance_logging.md` v1.0

---

## Recommended Implementation Order

```
C → A → B → D
```

**Rationale:**
- **C first** — creates `lidar_types.py` and removes the circular import. No functional change; lowest risk. Unblocks B and enables clean imports throughout.
- **A second** — adds offset to adapter. Self-contained. Can be deployed with `offset=0.0` before calibration with zero behaviour change.
- **B third** — fixes the body mask logic. Depends on C (shared types) and benefits from A (points are already corrected before masking).
- **D last** — three small tweaks that depend on B being correct (safety distance interacts with the now-working mask) and have the lowest complexity.

---

## Strict Constraints (NON-NEGOTIABLE)
1. Max 50 lines per Python function (`system_constraints.md §4`)
2. Full type hints on all modified/new functions (`system_constraints.md §4`)
3. Google-style docstrings on all public methods (`system_constraints.md §4`)
4. No direct hardware libraries outside Adapters (`system_constraints.md §1`)
5. No hardcoded paths — use `pathlib` (`system_constraints.md §4`)
6. `lidar_types.py` must have **zero** project-level imports (stdlib only)

---

## Module C — Required Logic
1. Create `src/core/lidar_types.py` with `BodyMaskSector` TypedDict and `DEFAULT_BODY_MASK` (split rear sectors per Module B spec)
2. In `obstacle_avoidance.py`: delete local `BodyMaskSector` class and `DEFAULT_BODY_MASK` list; add `from src.core.lidar_types import BodyMaskSector, DEFAULT_BODY_MASK`
3. In `state.py`: replace `from src.services.obstacle_avoidance import ...` with `from src.core.lidar_types import ...`
4. Run circular-import check: `python -c "from src.core.state import RobotState"` must exit 0

## Module A — Required Logic
1. Add `"LIDAR_ANGLE_OFFSET_DEG": 0.0` to `settings.json`
2. Add `LIDAR_ANGLE_OFFSET_DEG: float = 0.0` to `Settings` with validation in loader
3. Add `angle_offset_deg` handling to `LiDARAdapter.__init__` config loop
4. In `get_latest_scan()`: apply `corrected = (raw + offset + 180) % 360 - 180` and recalculate x/y
5. Pass `"angle_offset_deg": settings.LIDAR_ANGLE_OFFSET_DEG` in `HardwareManager.__init__`

## Module B — Required Logic
1. Replace `angle_0_360` conversion block in `apply_body_mask()` with direct `_normalize_angle()` call
2. Remove the `angle_0_360 = angle if angle >= 0 else angle + 360` line
3. Update `DEFAULT_BODY_MASK` in `lidar_types.py` — rear sector split (already done in C)
4. Add unit tests `test_front_sector_mask_applied` and `test_rear_sector_wraparound`

## Module D — Required Logic
1. `hardware_manager.py` line ~277: change `300` → `500` in `enable_obstacle_avoidance` call
2. `state.py._load_body_mask`: change `logger.info` → `logger.warning` with updated message
3. `obstacle_avoidance.py.run_once`: insert DEBUG log of `points[:5]` before `apply_body_mask` call

---

## Integration Points
- `lidar_types.py` → imported by `state.py` AND `obstacle_avoidance.py`
- `Settings.LIDAR_ANGLE_OFFSET_DEG` → consumed by `HardwareManager.__init__` → passed to `LiDARAdapter`
- `LiDARAdapter.get_latest_scan()` → all downstream consumers receive corrected angles automatically

---

## Success Criteria
- All contract acceptance criteria pass
- `python -c "from src.core.state import RobotState"` exits 0 (no circular import)
- Front obstacles at 0° are visible in sector evaluation after offset calibration
- Body mask unit tests pass
- No function exceeds 50 lines
- Auditor approval required before merge

---

## 📋 API MAP UPDATE SNIPPET

Copy into `docs/API_MAP_lite.md`:

```markdown
### Module: `lidar_types`
**Location:** `src/core/lidar_types.py`
**Status:** Designed (not yet implemented)
**Contract:** `CONTRACT_C_decouple_state_service.md` v1.0

**Public Interface:**
- `BodyMaskSector` — TypedDict for chassis mask sector definitions
- `DEFAULT_BODY_MASK: List[BodyMaskSector]` — three-entry default (front + split rear)

**Dependencies:**
- Imports: stdlib `typing` only
- Imported by: `src.core.state`, `src.services.obstacle_avoidance`

---

### Module: `LiDARAdapter` (amended)
**Location:** `src/hardware/lidar_adapter.py`
**Status:** Amending existing — Contract A
**Contract:** `CONTRACT_A_lidar_angle_offset.md` v1.0

**New config key:**
- `angle_offset_deg (float)` — mounting correction, applied in `get_latest_scan()`

**New settings.json key:**
- `LIDAR_ANGLE_OFFSET_DEG: float = 0.0` — operator fills after calibration
```

---

## ⏭️ HUMAN WORKFLOW CHECKPOINT

**Files produced:** 4 contracts + 1 work order (this document)

**Before invoking Implementer:**
1. Complete physical calibration (see Contract A §1 operator note) — or confirm `0.0` as placeholder
2. Review `DEFAULT_BODY_MASK` split-rear sectors (Contracts B/C) — do angles match your robot geometry?
3. Update `docs/API_MAP_lite.md` with snippet above
4. Save all contract files

**Verification command for Implementer:**
```
/verify-context: CONTRACT_A_lidar_angle_offset.md, CONTRACT_B_body_mask_angle_fix.md, CONTRACT_C_decouple_state_service.md, CONTRACT_D_safety_distance_logging.md, work_order.md, API_MAP_lite.md, system_constraints.md
```

**Next Agent:** `02_implementer.md` — implement in order C → A → B → D

---

```
✅ Contract Created: CONTRACT_A_lidar_angle_offset.md v1.0
✅ Contract Created: CONTRACT_B_body_mask_angle_fix.md v1.0
✅ Contract Created: CONTRACT_C_decouple_state_service.md v1.0
✅ Contract Created: CONTRACT_D_safety_distance_logging.md v1.0
📋 Work Order Generated: work_order.md
```