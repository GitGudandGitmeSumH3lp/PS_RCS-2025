# tests/test_body_masking.py
import pytest
from src.services.obstacle_avoidance import SimpleObstacleAvoidance, BodyMaskSector

def test_apply_body_mask_angle_wrapping():
    """Verify that angles outside [-180,180] are normalized and mask matches correctly."""
    avoid = SimpleObstacleAvoidance(None)  # hardware_manager not needed for this test
    points = [
        {"angle": -170.0, "distance": 100.0},  # should be masked by rear sector
        {"angle": 190.0, "distance": 100.0},   # also rear after normalization
        {"angle": 10.0, "distance": 100.0},    # front sector, not rear
    ]
    mask: List[BodyMaskSector] = [
        {"name": "rear_chassis", "angle_min": 150.0, "angle_max": 210.0, "min_distance_mm": 180.0}
    ]
    filtered = avoid.apply_body_mask(points, mask)
    # Points with angle -170 (normalized -170) and 190 (normalized -170) should be dropped.
    # Point at 10 should be kept.
    assert len(filtered) == 1
    assert filtered[0]["angle"] == 10.0