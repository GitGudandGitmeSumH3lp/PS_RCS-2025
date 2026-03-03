```markdown
# FEATURE SPEC: Configurable LiDAR Body Masking & Point Count Diagnostics
**Date:** 2026-03-03
**Status:** Feasible

## 1. THE VISION
*   **User Story:** As an operator, I want the LiDAR to explicitly ignore returns corresponding to the robot's physical chassis, preventing false obstacle detections and erratic behavior in the `SimpleObstacleAvoidance` algorithm. Concurrently, I need a diagnostic toolset to understand why the LiDAR is returning significantly fewer points than expected (20-50 instead of ~360 per scan).
*   **Success Metrics:**
    *   Obstacle avoidance ceases to trigger on the robot's own chassis (e.g., front/rear limits).
    *   Sectors defined as the 'body mask' are correctly ignored prior to avoidance evaluation.
    *   Operator is provided with an API to configure these blind spots dynamically.
    *   Implementation of targeted logging enabling root-cause analysis of the low point count anomaly without crashing or locking the server thread.

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed (Will use purely algorithmic filtering within python; API routes will be non-blocking; state stored in `RobotState`; memory-safe lists used for mask).
*   **New Libraries Needed:** None.
*   **Risk Level:** Medium (Altering the core point processing pipeline before obstacle avoidance could cause missed real obstacles if configured poorly. Therefore, strict bounds validation is required).

## 3. ATOMIC TASKS (The Roadmap)

### Phase A: Body Masking Implementation
*   [ ] **Update `RobotState`**:
    *   Add `lidar_body_mask` property containing a list of sector dictionaries.
    *   *Default mask*: Front: `-30` to `30`, `min_distance`: `280`; Rear: `150` to `210`, `min_distance`: `180`.
*   [ ] **Update API Map / Create Endpoints (`src/api/routes_config.py` or similar)**:
    *   `GET /api/lidar/body_mask`: Returns the current `lidar_body_mask`.
    *   `POST /api/lidar/body_mask`: Validates and updates `lidar_body_mask` in `RobotState`.
*   [ ] **Update `src/services/obstacle_avoidance.py`**:
    *   Retrieve the mask from `RobotState` (passed in or accessed via a manager).
    *   Implement an `apply_body_mask(points: List[Dict], mask: List[Dict]) -> List[Dict]` method.
    *   Call `apply_body_mask` immediately after extracting points in `run_once()`, *before* distance-based speed scaling and sector evaluation.
*   [ ] **Frontend Update (`lidar-panel.js` or new settings modal)**:
    *   Build a UI to view and edit the body mask sectors.
    *   Use sliders for `min_distance` (Max 500mm limit).
    *   *Note: Detailed UI implementation is handled by the Frontend dev, but API contract is defined here.*

### Phase B: Point Count Diagnostics
*   [ ] **Update `src/hardware/lidar_adapter.py`**:
    *   Implement an internal performance counter to log the point count distribution over N cycles.
*   [ ] **Update `src/hardware/ydlidar_reader.py`**:
    *   Add trace logging (configurable via environment variable or specific endpoint) around the `doProcessSimple()` call to expose execution times and raw point counts before they hit the adapter queue.
    *   Examine the `max_points` variable.

## 4. INTERFACE SKETCHES (For Architect)

**Data Structure: Body Mask Sector**
```python
{
    "name": "front_chassis",
    "angle_min": -35.0,
    "angle_max": 35.0,
    "min_distance_mm": 280
}
```

**Module:** `src/services/obstacle_avoidance.py`
*   `apply_body_mask(points: List[Dict], mask: List[Dict]) -> List[Dict]`
    *   *Idea:* Iterate through points. If a point's angle falls within a mask sector's `angle_min` and `angle_max`, AND its `distance` is LESS than `min_distance_mm`, it is dropped. Otherwise, keep it. Handles angle wrapping (-180 to 180).

**API Contract (`POST /api/lidar/body_mask`)**
*   *Input:* `{"mask": [{"name": "front", "angle_min": -30, "angle_max": 30, "min_distance_mm": 280}, ...]}`
*   *Validation Rules:*
    *   `min_distance_mm` must be `>= 0` and `<= 500` (Safety limit).
    *   `angle_min` and `angle_max` must be between `-180` and `180`.

## 5. DIAGNOSTIC PLAN: LOW POINT COUNT

Based on the evidence (~20-50 points returned vs ~360 expected), the following steps must be executed to diagnose the bottleneck:

1.  **Check Hardware Scan Frequency vs Adapter Polling:**
    *   *Hypothesis:* The `get_latest_scan()` is being polled too quickly by the frontend or avoidance loop, grabbing incomplete rotations.
    *   *Action:* In `lidar_adapter.py`, log the delta time between calls to `get_latest_scan()`. If it's very short (<100ms), we are likely draining the buffer faster than it fills (YDLidar S2 spins at ~8Hz, so a full scan takes ~125ms).
2.  **Verify `ydlidar_reader.py` Internal Buffer:**
    *   *Hypothesis:* `max_points=360` in `get_latest_data()` is fine, but the internal `_latest_scan` list is being overwritten completely on partial scans.
    *   *Action:* Review the `_scan_loop()` in `ydlidar_reader.py`. Ensure that `doProcessSimple()` is actually accumulating a full 360-degree sweep before returning `True`. If it returns partial sweeps, we need an accumulator logic in the reader.
3.  **Investigate Quality/Intensity Filtering:**
    *   *Hypothesis:* The LiDAR is physically dropping points due to low reflectivity of the room, or a software filter is active.
    *   *Action:* Log the number of raw points received from `doProcessSimple` vs the number of points after any internal filtering. Note: Current code in `ydlidar_reader.py` does not appear to filter by quality, but the `ydlidar` SDK might be configured to drop zero-intensity points.
4.  **Operator Physical Test:**
    *   *Action:* Place the robot in a perfectly square, highly reflective room (or use cardboard walls). Does the point count increase? If yes, it's an environmental/intensity issue. If no, it's a software timing/buffer issue.

## 6. INTEGRATION POINTS
*   **Touches:** `src/services/obstacle_avoidance.py` (Applying the mask), `src/hardware/RobotState` (Storing the mask config), `src/api/...` (Exposing the config).
*   **Data Flow:** Mask API -> `RobotState` -> `ObstacleAvoidance` -> Point Filter -> Collision Logic.

## 7. OPEN QUESTIONS
*   Does `RobotState` currently persist across reboots (e.g., via a JSON config file), or will the operator need to set the body mask on every startup? (Architect should ensure persistence).
*   For the diagnostic: Is `ydlidar.LaserScan()` guaranteed to represent exactly one full rotation in the python wrapper, or does it return partial buffers?

---
## POST-ACTION REPORT TEMPLATE

✅ **Spec Created:** `docs/specs/body_masking.md`
✅ **Plan Created:** `docs/diagnostics/low_point_count_plan.md`
📋 **Next Step:** Review Spec, then pass to Architect for structural design.
👉 **Next Agent:** Architect (AGENTS/01_architect.md)
```