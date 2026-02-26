import serial
import time

def send_cmd(ser, cmd, name):
    ser.write(cmd)
    time.sleep(0.1)
    data = ser.read(200)  # read up to 200 bytes
    print(f"\n--- {name} (command {cmd.hex()}) ---")
    print(f"Response ({len(data)} bytes): {data.hex()}")
    if data:
        print(f"First byte: 0x{data[0]:02x}")
    return data

port = '/dev/ttyUSB1'
baud = 115200

try:
    ser = serial.Serial(port, baud, timeout=2)
    print(f"Opened {port} at {baud}")

    # 1. Stop any ongoing scan
    send_cmd(ser, b'\xA5\x25', 'STOP')

    # 2. Reset device
    send_cmd(ser, b'\xA5\x40', 'RESET')
    time.sleep(1)  # give it time to reboot

    # 3. Get device info (should return a descriptor starting with 0xA5)
    info = send_cmd(ser, b'\xA5\x50', 'GET_INFO')

    # 4. Get health status
    health = send_cmd(ser, b'\xA5\x52', 'GET_HEALTH')

    # 5. Start motor (if needed)
    send_cmd(ser, b'\xA5\x60', 'MOTOR_START')
    time.sleep(1)

    # 6. Start scan and read data
    ser.write(b'\xA5\x20')
    time.sleep(0.2)
    scan_data = ser.read(500)  # read up to 500 bytes
    print(f"\n--- SCAN DATA (first 500 bytes) ---")
    print(f"Length: {len(scan_data)} bytes")
    print(f"Hex: {scan_data.hex()}")
    if len(scan_data) >= 5:
        # Try parsing first 5-byte packet
        q = scan_data[0]
        a = scan_data[1] | (scan_data[2] << 8)
        d = scan_data[3] | (scan_data[4] << 8)
        print(f"First 5-byte packet: quality={q}, angle={a/64:.2f}°, distance={d/4:.1f}mm")

    ser.close()
except Exception as e:
    print(f"Error: {e}")