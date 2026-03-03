"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/core/lidar_types.py
Description: Shared type definitions for LiDAR processing.
             This module has NO imports from other project modules
             to prevent circular dependencies.
"""
from typing import List, TypedDict


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