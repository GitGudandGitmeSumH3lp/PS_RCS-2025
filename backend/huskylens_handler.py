# huskylens_handler.py
# Communicates with HuskyLens via USB serial

import time
import logging

# Import HuskyLens library
try:
    from pyhuskylens import HuskyLensLibrary
except ImportError:
    print("pyhuskylens not found. Install with: pip install git+https://github.com/huskylenz/pyhuskylens.git")

# ----------------------------
# CONFIGURATION
# ----------------------------
SERIAL_PORT = "/dev/ttyUSB2"  # Change if HuskyLens appears as /dev/ttyACM0
BAUDRATE = 9600

# Map of known HuskyLens algorithms and their readable names
ALGO_MAP = {
    "ALGORITHM_FACE_RECOGNITION": "Face Recognition",
    "ALGORITHM_OBJECT_TRACKING": "Object Tracking",
    "ALGORITHM_OBJECT_RECOGNITION": "Object Recognition",
    "ALGORITHM_LINE_TRACKING": "Line Tracking",
    "ALGORITHM_COLOR_RECOGNITION": "Color Recognition",
    "ALGORITHM_TAG_RECOGNITION": "Tag Recognition",
    "ALGORITHM_OBJECT_CLASSIFICATION": "Object Classification"
}

class HuskyLensHandler:
    def __init__(self, port=SERIAL_PORT, baudrate=BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.huskylens = None
        self.current_mode = None
        self.logger = logging.getLogger(__name__)

    def connect(self):
        """Initialize connection to HuskyLens."""
        try:
            self.logger.info(f"Connecting to HuskyLens on {self.port}...")
            self.huskylens = HuskyLensLibrary("SERIAL", self.port, baudrate=self.baudrate)
            time.sleep(2)
            self.current_mode = self.huskylens.known_algorithms[self.huskylens.currentAlgorithm]
            self.logger.info(f"HuskyLens connected in mode: {self.current_mode}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            return False

    def get_object_label(self, block):
        """
        Generate a label based on current algorithm.
        """
        algo = self.current_mode

        if algo == "ALGORITHM_FACE_RECOGNITION":
            return f"Face #{block.ID}"
        elif algo == "ALGORITHM_OBJECT_CLASSIFICATION":
            return block.name if hasattr(block, 'name') and block.name else f"Learned Object #{block.ID}"
        elif algo == "ALGORITHM_COLOR_RECOGNITION":
            colors = {1: "Red", 2: "Yellow", 3: "Green", 4: "Blue"}
            return colors.get(block.ID, f"Color ID {block.ID}")
        elif algo in ["ALGORITHM_OBJECT_TRACKING", "ALGORITHM_OBJECT_RECOGNITION"]:
            return f"Tracked Object #{block.ID}"
        else:
            return f"Detected Object #{block.ID}"

    def get_detections(self):
        """Get current object detections from HuskyLens."""
        if not self.huskylens:
            self.logger.error("HuskyLens not connected")
            return []

        try:
            blocks = self.huskylens.blocks()
            detections = []
            
            for block in blocks:
                label = self.get_object_label(block)
                detections.append({
                    "label": label,
                    "id": block.ID,
                    "x": block.x,
                    "y": block.y,
                    "width": block.width,
                    "height": block.height,
                    "algorithm": self.current_mode
                })
                
            return detections
        except Exception as e:
            self.logger.error(f"Error reading blocks: {e}")
            return []

    def disconnect(self):
        """Disconnect from HuskyLens."""
        # HuskyLens library doesn't have explicit disconnect method
        self.logger.info("Disconnected from HuskyLens")

# Example usage
if __name__ == "__main__":
    handler = HuskyLensHandler()
    if handler.connect():
        try:
            while True:
                detections = handler.get_detections()
                if detections:
                    for obj in detections:
                        print(f"Detected: {obj['label']} at ({obj['x']}, {obj['y']})")
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            handler.disconnect()