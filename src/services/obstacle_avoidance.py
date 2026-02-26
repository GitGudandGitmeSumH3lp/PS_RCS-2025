# src/services/obstacle_avoidance.py

import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SimpleObstacleAvoidance:
    """
    Reactive obstacle avoidance using YDLIDAR data.
    Implements: Stop if blocked, turn toward clearest path.
    """
    
    def __init__(self, hardware_manager, safety_distance_mm: int = 500):
        """
        Args:
            hardware_manager: Instance with motor_controller and lidar
            safety_distance_mm: Stop if obstacle closer than this (default 50cm)
        """
        self.hw = hardware_manager
        self.safety_distance = safety_distance_mm
        self._running = False
        self._last_decision = "stop"
        
    def evaluate_sectors(self, points: List[Dict]) -> Dict[str, float]:
        """
        Divide 360° into sectors and find minimum distance in each.
        
        Returns:
            Dict mapping sector name to minimum distance (mm).
        """
        sectors = {
            'front': [],      # -30° to +30°
            'front_left': [], # +30° to +90°
            'left': [],       # +90° to +150°
            'rear': [],       # +150° to +210° (and -150° to -210°)
            'right': [],      # -150° to -90°
            'front_right': [] # -90° to -30°
        }
        
        for p in points:
            angle = p['angle']
            # Normalize to -180 to +180
            while angle > 180:
                angle -= 360
            while angle < -180:
                angle += 360
                
            dist = p['distance']
            if dist <= 0 or dist > 8000:  # Filter invalid readings
                continue
                
            # Categorize by angle
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
        
        # Return minimum distance per sector (infinity if empty)
        return {
            name: (min(dists) if dists else float('inf'))
            for name, dists in sectors.items()
        }
    
    def make_decision(self, sectors: Dict[str, float]) -> str:
        """
        Decide action based on sector distances.
        
        Returns:
            Command string: 'forward', 'left', 'right', 'backward', 'stop'
        """
        front_clear = sectors['front'] > self.safety_distance
        
        if front_clear:
            return 'forward'
        
        # Front blocked - find best turn
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
        """Send command to motor controller."""
        cmd_map = {
            'forward': 'forward',
            'backward': 'backward',
            'left': 'left',
            'right': 'right',
            'stop': 'stop'
        }
        
        motor_cmd = cmd_map.get(command, 'stop')
        success = self.hw.send_motor_command(motor_cmd, speed)
        
        if success and command != self._last_decision:
            logger.info(f"Obstacle avoidance: {self._last_decision} -> {command}")
            self._last_decision = command
            
        return success
    
    def run_once(self, speed: int = 80) -> str:
        """
        Single evaluation cycle: get scan, decide, execute.
        
        Returns:
            Decision made (for logging/debugging).
        """
        if not self.hw.lidar:
            logger.error("No LiDAR available")
            return 'stop'
            
        # Get latest scan
        scan_data = self.hw.lidar.get_latest_scan()
        points = scan_data.get('points', [])
        
        if not points:
            logger.warning("No LiDAR points available")
            return self._last_decision
        
        # Evaluate and decide
        sectors = self.evaluate_sectors(points)
        decision = self.make_decision(sectors)
        
        # Execute
        self.execute(decision, speed)
        
        return decision
    
    def start_continuous(self, interval_ms: int = 100, speed: int = 80):
        """
        Start background obstacle avoidance thread.
        
        Args:
            interval_ms: Evaluation interval in milliseconds.
            speed: Motor speed (0-255).
        """
        import threading
        
        self._running = True
        
        def loop():
            while self._running:
                self.run_once(speed)
                time.sleep(interval_ms / 1000.0)
        
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logger.info(f"Obstacle avoidance started: {interval_ms}ms interval")
        return thread
    
    def stop(self):
        """Stop avoidance and halt motors."""
        self._running = False
        self.hw.stop_motors()
        logger.info("Obstacle avoidance stopped")