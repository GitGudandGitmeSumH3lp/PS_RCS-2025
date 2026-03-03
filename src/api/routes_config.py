# src/api/routes_config.py
"""
PS_RCS_PROJECT - Configuration API routes
Handles retrieval and update of system configuration parameters,
including LiDAR body mask.
"""

import logging
from typing import Any, Dict, List

from flask import Blueprint, request, jsonify, current_app

from src.services.obstacle_avoidance import BodyMaskSector, DEFAULT_BODY_MASK

logger = logging.getLogger(__name__)

# This blueprint will be registered with the Flask app.
# The hardware_manager is expected to be stored in app.config['HARDWARE_MANAGER'].
config_bp = Blueprint('config', __name__, url_prefix='/api')


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
    if not isinstance(mask_data, list):
        raise ValueError("'mask' must be a list")

    if len(mask_data) < 1 or len(mask_data) > 10:
        raise ValueError("'mask' must contain 1–10 sectors")

    validated = []
    for i, sector in enumerate(mask_data):
        if not isinstance(sector, dict):
            raise ValueError(f"sector[{i}]: must be an object")

        # name
        name = sector.get('name')
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"sector[{i}].name: must be a non-empty string (max 64 chars)")
        if len(name) > 64:
            raise ValueError(f"sector[{i}].name: must be a non-empty string (max 64 chars)")

        # angle_min
        try:
            angle_min = float(sector['angle_min'])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"sector[{i}].angle_min: must be a number in [-180, 360]")
        if not (-180 <= angle_min <= 360):
            raise ValueError(f"sector[{i}].angle_min: must be a number in [-180, 360]")

        # angle_max
        try:
            angle_max = float(sector['angle_max'])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"sector[{i}].angle_max: must be a number in [-180, 360]")
        if not (-180 <= angle_max <= 360):
            raise ValueError(f"sector[{i}].angle_max: must be a number in [-180, 360]")

        if angle_min > angle_max:
            raise ValueError(f"sector[{i}]: angle_min must be <= angle_max")

        # min_distance_mm
        try:
            min_dist = float(sector['min_distance_mm'])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"sector[{i}].min_distance_mm: must be a number in [0, 500]")
        if not (0 <= min_dist <= 500):
            raise ValueError(f"sector[{i}].min_distance_mm: must be a number in [0, 500]")

        validated.append({
            "name": name.strip(),
            "angle_min": angle_min,
            "angle_max": angle_max,
            "min_distance_mm": min_dist,
        })

    return validated


@config_bp.route('/lidar/body_mask', methods=['GET'])
def get_body_mask():
    """Retrieve current body mask configuration."""
    try:
        hw = current_app.config.get('HARDWARE_MANAGER')
        if hw is None or not hasattr(hw, 'state') or hw.state is None:
            return jsonify({"success": False, "error": "RobotState not available"}), 503

        mask = hw.state.lidar_body_mask
        return jsonify({"success": True, "mask": mask}), 200
    except Exception as e:
        logger.exception("Error in GET /api/lidar/body_mask")
        return jsonify({"success": False, "error": f"Failed to retrieve body mask: {str(e)}"}), 500


@config_bp.route('/lidar/body_mask', methods=['POST'])
def set_body_mask():
    """Update and persist body mask configuration."""
    data = request.get_json()
    if data is None or 'mask' not in data:
        return jsonify({"success": False, "error": "Request body must contain 'mask' key"}), 400

    try:
        validated_mask = validate_body_mask(data['mask'])
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        hw = current_app.config.get('HARDWARE_MANAGER')
        if hw is None or not hasattr(hw, 'state') or hw.state is None:
            return jsonify({"success": False, "error": "RobotState not available"}), 503

        hw.state.lidar_body_mask = validated_mask
        return jsonify({
            "success": True,
            "message": f"Body mask updated. {len(validated_mask)} sector(s) active."
        }), 200
    except Exception as e:
        logger.exception("Error in POST /api/lidar/body_mask")
        return jsonify({"success": False, "error": f"Internal error: {str(e)}"}), 500