import serial
import time

def test_baud(port, baud):
    print(f"\n--- Testing {port} at {baud} baud ---")
    try:
        ser = serial.Serial(port, baud, timeout=2)
        # Try to reset / stop any ongoing scan
        ser.write(b'\xA5\x25')   # stop scan
        time.sleep(0.2)
        ser.write(b'\xA5\x40')   # reset (optional)
        time.sleep(0.5)
        ser.write(b'\xA5\x20')   # request scan
        data = ser.read(100)
        print(f"Response (hex): {data.hex()}")
        if data:
            print(f"First byte: {data[0]:02x} (should be a5)")
        ser.close()
    except Exception as e:
        print(f"Error: {e}")

# Test both common baud rates
test_baud('/dev/ttyUSB1', 115200)
test_baud('/dev/ttyUSB1', 256000)

# Also test with DTR high (motor enable for some models)
print("\n--- Testing with DTR high ---")
try:
    ser = serial.Serial('/dev/ttyUSB1', 115200, timeout=2)
    ser.dtr = True   # try True or False
    time.sleep(1)
    ser.write(b'\xA5\x20')
    data = ser.read(100)
    print(f"Response (hex): {data.hex()}")
    ser.close()
except Exception as e:
    print(f"Error: {e}")