import sys
sys.path.insert(0, '.')  # Adjust to your project root
from src.services.vision_manager import VisionManager

vm = VisionManager()
print("Calling start_capture...")
success = vm.start_capture(640, 480, 15)
print(f"start_capture returned: {success}")
print(f"Provider: {vm.provider}")
print(f"Capture thread alive: {vm.capture_thread and vm.capture_thread.is_alive()}")
if success:
    import time
    time.sleep(2)
    frame = vm.get_frame()
    print(f"Got frame: {frame.shape if frame is not None else 'None'}")
vm.stop_capture()