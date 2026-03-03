# tests/test_body_masking.py
import pytest
from src.core.lidar_types import BodyMaskSector, DEFAULT_BODY_MASK
from src.services.obstacle_avoidance import SimpleObstacleAvoidance, _normalize_angle

def test_front_sector_mask_applied():
    """Front points within min_distance must be dropped after mask fix."""
    avoidance = SimpleObstacleAvoidance(None)  # hardware_manager not needed
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
    avoidance = SimpleObstacleAvoidance(None)
    mask = DEFAULT_BODY_MASK  # uses split rear sectors
    points = [
        {"angle": 160.0, "distance": 100.0},   # rear_pos sector → DROP
        {"angle":-160.0, "distance": 100.0},   # rear_neg sector → DROP
        {"angle": 160.0, "distance": 300.0},   # rear_pos, far   → KEEP
        {"angle": 10.0,  "distance": 100.0},   # front sector, not rear → KEEP
    ]
    result = avoidance.apply_body_mask(points, mask)
    assert len(result) == 2
    assert result[0]["angle"] == 160.0 and result[0]["distance"] == 300.0
    assert result[1]["angle"] == 10.0