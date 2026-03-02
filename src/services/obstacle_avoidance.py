# src/services/obstacle_avoidance.py

import logging
import threading
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SimpleObstacleAvoidance:
    def __init__(self, hardware_manager, safety_distance_mm: int = 500) -> None:
        self.hw = hardware_manager
        self.safety_distance = safety_distance_mm
        self._running = False
        self._last_decision = "stop"
        self._lock = threading.Lock()

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
        
        # ---> THIS IS THE NEW CHANGE: Tell the hardware manager this is an "auto" command
        success = self.hw.send_motor_command(motor_cmd, speed, source="auto")
        
        with self._lock:
            if success and command != self._last_decision:
                logger.info(f"Obstacle avoidance: {self._last_decision} -> {command}")
                self._last_decision = command
        return success

    def run_once(self, speed: int = 80) -> str:
        if not hasattr(self.hw, 'lidar') or not self.hw.lidar:
            logger.error("No LiDAR available")
            return 'stop'
        scan_data = self.hw.lidar.get_latest_scan()
        points = scan_data.get('points', []) if isinstance(scan_data, dict) else []
        if not points:
            logger.warning("No LiDAR points available")
            return self._last_decision
        sectors = self.evaluate_sectors(points)
        decision = self.make_decision(sectors)
        self.execute(decision, speed)
        return decision

    def start_continuous(self, interval_ms: int = 100, speed: int = 80) -> threading.Thread:
        with self._lock:
            if self._running:
                logger.warning("Obstacle avoidance already running")
                return None
            self._running = True

        def loop():
            while self._running:
                try:
                    self.run_once(speed)
                except Exception as e:
                    logger.error(f"Obstacle avoidance loop error: {e}", exc_info=True)
                time.sleep(interval_ms / 1000.0)

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logger.info(f"Obstacle avoidance started: interval={interval_ms}ms, speed={speed}")
        return thread

    def stop(self) -> None:
        with self._lock:
            self._running = False
        self.hw.stop_motors()
        logger.info("Obstacle avoidance stopped")