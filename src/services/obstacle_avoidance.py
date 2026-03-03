# src/services/obstacle_avoidance.py

import logging
import threading
import time
from typing import Dict, List, Optional, Any, TypedDict

logger = logging.getLogger(__name__)

# Distance thresholds for speed scaling (millimeters)
STOP_DIST_MM = 200      # If obstacle closer than this, speed = 0
SAFE_DIST_MM = 500      # If obstacle farther than this, use base speed


class BodyMaskSector(TypedDict):
    name: str
    angle_min: float
    angle_max: float
    min_distance_mm: float


DEFAULT_BODY_MASK: List[BodyMaskSector] = [
    {"name": "front_chassis", "angle_min": -30.0, "angle_max":  30.0, "min_distance_mm": 280.0},
    {"name": "rear_chassis",  "angle_min": 150.0, "angle_max": 210.0, "min_distance_mm": 180.0},
]


class SimpleObstacleAvoidance:
    def __init__(self, hardware_manager, safety_distance_mm: int = 500) -> None:
        self.hw = hardware_manager
        self.safety_distance = safety_distance_mm
        self._running = False
        self._last_decision = "stop"
        self._lock = threading.Lock()
        self._speed: int = 80  # Internal default, will be overridden by start_continuous caller.
        self._loop_counter = 0

    def evaluate_sectors(self, points: List[Dict]) -> Dict[str, float]:
        sectors = {
            'front': [],      # -30 to 30
            'front_left': [], # 30 to 90
            'left': [],       # 90 to 150
            'rear': [],       # abs > 150
            'right': [],      # -150 to -90
            'front_right': [] # -90 to -30
        }
        for p in points:
            angle = p.get('angle', 0.0)
            # Normalize to -180..180
            while angle > 180:
                angle -= 360
            while angle < -180:
                angle += 360
            dist = p.get('distance', 0.0)
            if dist <= 0 or dist > 8000:
                continue
            if -30 <= angle <= 30:
                sectors['front'].append(dist)
            elif 30 < angle <= 90:
                sectors['front_left'].append(dist)
            elif 90 < angle <= 150:
                sectors['left'].append(dist)
            elif abs(angle) > 150:
                sectors['rear'].append(dist)
            elif -150 <= angle < -90:
                sectors['right'].append(dist)
            elif -90 <= angle < -30:
                sectors['front_right'].append(dist)
        return {
            name: (min(dists) if dists else float('inf'))
            for name, dists in sectors.items()
        }

    def make_decision(self, sectors: Dict[str, float]) -> str:
        front_clear = sectors['front'] > self.safety_distance
        if front_clear:
            return 'forward'
        left_space = min(sectors['front_left'], sectors['left'])
        right_space = min(sectors['front_right'], sectors['right'])
        if left_space > self.safety_distance and left_space > right_space:
            return 'left'
        elif right_space > self.safety_distance:
            return 'right'
        elif sectors['rear'] > self.safety_distance:
            return 'backward'
        else:
            return 'stop'

    def execute(self, command: str, speed: int = 80) -> bool:
        cmd_map = {
            'forward': 'forward',
            'backward': 'backward',
            'left': 'left',
            'right': 'right',
            'stop': 'stop'
        }
        motor_cmd = cmd_map.get(command, 'stop')
        # Pass source="auto" to respect operation mode
        success = self.hw.send_motor_command(motor_cmd, speed, source="auto")
        with self._lock:
            if success and command != self._last_decision:
                logger.info(f"Obstacle avoidance: {self._last_decision} -> {command}")
                self._last_decision = command
        return success

    def set_speed(self, speed: int) -> None:
        """Updates the speed used by the avoidance loop on its next iteration.

        Thread-safe for CPython due to GIL-protected integer assignment.

        Args:
            speed: New speed in PWM units. Range: [0, 255].

        Raises:
            ValueError: If speed is outside [0, 255].
        """
        if not (0 <= speed <= 255):
            raise ValueError("speed must be 0–255")
        self._speed = speed

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
        if not isinstance(points, list):
            raise TypeError(f"apply_body_mask: 'points' must be a list, got {type(points).__name__}")
        if not isinstance(mask, list):
            raise TypeError(f"apply_body_mask: 'mask' must be a list, got {type(mask).__name__}")

        if not mask:
            return points

        filtered = []
        for p in points:
            # Skip malformed points
            if not isinstance(p, dict) or 'angle' not in p or 'distance' not in p:
                logger.debug("apply_body_mask: skipping point with missing keys")
                continue
            distance = p['distance']
            if distance <= 0:
                continue  # invalid reading

            # Normalize angle to [-180, 180]
            angle = p['angle']
            while angle > 180:
                angle -= 360
            while angle < -180:
                angle += 360

            # Check against mask sectors
            keep = True
            for sector in mask:
                if (sector['angle_min'] <= angle <= sector['angle_max'] and
                        distance < sector['min_distance_mm']):
                    keep = False
                    break
            if keep:
                filtered.append(p)

        return filtered

    def run_once(self, speed: int = None) -> str:
        """Executes one obstacle-avoidance cycle.

        Args:
            speed: PWM speed override. If None, uses self._speed.
        """
        if speed is None:
            speed = self._speed   # base speed from slider

        if not hasattr(self.hw, 'lidar') or not self.hw.lidar:
            logger.error("No LiDAR available")
            return 'stop'

        scan_data = self.hw.lidar.get_latest_scan()
        points = scan_data.get('points', []) if isinstance(scan_data, dict) else []

        # --- Body Mask Filtering ---
        mask = []
        if hasattr(self.hw, 'state') and self.hw.state is not None:
            mask = self.hw.state.lidar_body_mask
        points = self.apply_body_mask(points, mask)
        # --- End Body Mask Filtering ---

        if not points:
            logger.warning("No LiDAR points available after body mask")
            return self._last_decision

        # --- Distance‑based speed scaling ---
        # Compute minimum distance in front sector (-30° to 30°)
        front_dists = [
            p['distance'] for p in points
            if -30 <= p.get('angle', 0) <= 30 and p.get('distance', 0) > 0
        ]
        if front_dists:
            min_front = min(front_dists)
        else:
            min_front = float('inf')

        # Determine effective speed
        if min_front <= STOP_DIST_MM:
            effective_speed = 0
        elif min_front >= SAFE_DIST_MM:
            effective_speed = speed
        else:
            # Linear interpolation between STOP_DIST and SAFE_DIST
            factor = (min_front - STOP_DIST_MM) / (SAFE_DIST_MM - STOP_DIST_MM)
            effective_speed = int(speed * factor)

        self._loop_counter += 1
        if self._loop_counter % 10 == 0:
            logger.info(f"Distance‑based speed: min_front={min_front:.0f}mm, "
                        f"base={speed}, effective={effective_speed}")
        # --- End scaling ---

        sectors = self.evaluate_sectors(points)

        # --- NEW LOGGING ---
        logger.info(
            f"Sector distances (mm): front={sectors['front']:.1f}, "
            f"front_left={sectors['front_left']:.1f}, front_right={sectors['front_right']:.1f}, "
            f"left={sectors['left']:.1f}, right={sectors['right']:.1f}, rear={sectors['rear']:.1f}"
        )

        # Optional: log a few raw points near the front
        front_points = [p for p in points if -30 <= p['angle'] <= 30]
        if front_points:
            # log the three closest points
            front_points.sort(key=lambda p: p['distance'])
            for idx, p in enumerate(front_points[:3]):
                logger.debug(f"Front point {idx}: angle={p['angle']:.1f}, dist={p['distance']:.0f}")

        decision = self.make_decision(sectors)
        logger.info(f"Decision: {decision} (front_clear={sectors['front'] > self.safety_distance})")
        # --- END NEW LOGGING ---

        self.execute(decision, effective_speed)
        return decision

    def start_continuous(self, interval_ms: int = 100, speed: int = None):
        """
        Start background obstacle avoidance thread.
        If speed is provided, sets self._speed before starting.
        Returns the thread object (daemon).
        """
        if speed is not None:
            self._speed = speed

        with self._lock:
            if self._running:
                logger.warning("Obstacle avoidance already running")
                return None
            self._running = True

        def loop():
            loop_counter = 0
            while self._running:
                try:
                    self.run_once()   # now uses self._speed
                    loop_counter += 1
                    if loop_counter % 10 == 0:
                        logger.info(f"Avoidance loop alive, last decision: {self._last_decision}")
                except Exception as e:
                    logger.error(f"Obstacle avoidance loop error: {e}", exc_info=True)
                time.sleep(interval_ms / 1000.0)
            logger.info("Obstacle avoidance loop ended")

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logger.info(f"Obstacle avoidance started: {interval_ms}ms interval, speed={self._speed}")
        return thread

    def stop(self) -> None:
        with self._lock:
            self._running = False
        self.hw.stop_motors()
        logger.info("Obstacle avoidance stopped")