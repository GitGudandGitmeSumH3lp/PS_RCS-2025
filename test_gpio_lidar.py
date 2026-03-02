import serial
import time

port = '/dev/ttyAMA0'  # or /dev/serial0
baud = 115200

try:
    ser = serial.Serial(port, baud, timeout=2)
    print(f"Opened {port}")
    # Send a simple command to request info (adjust to your LiDAR)
    ser.write(b'\xA5\x50')  # get_info command for RPLIDAR, but YDLIDAR may differ
    time.sleep(0.1)
    resp = ser.read(100)
    print(f"Response: {resp.hex()}")
    ser.close()
except Exception as e:
    print(f"Error: {e}")