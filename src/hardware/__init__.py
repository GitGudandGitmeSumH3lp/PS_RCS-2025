from .lidar_adapter import LiDARAdapter

class HardwareManager:
    def __init__(self):
        # ... existing init ...
        self.lidar = LiDARAdapter(config={
            "port": None,               # auto-detect or set from env
            "baudrate": 115200,
            "max_queue_size": 1000,
            "enable_simulation": False
        })