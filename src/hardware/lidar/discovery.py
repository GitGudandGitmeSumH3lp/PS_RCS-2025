import serial
import serial.tools.list_ports

def find_lidar():
    ports = list(serial.tools.list_ports.comports())
    print("Scanning all serial devices...")
    
    for port in ports:
        print(f"Checking {port.device} - {port.description}")
        try:
            # Attempt to open the port with common LiDAR settings
            ser = serial.Serial(port.device, baudrate=115200, timeout=1)
            ser.write(b'\xA5\x00')  # Example: sending a ping/command if needed
            response = ser.read(2)
            ser.close()
            
            if response:  # If we get a response, likely our LiDAR
                print(f"LiDAR detected on {port.device}")
                return port.device
        except Exception as e:
            # Skip if can't open or invalid response
            pass

    print("LiDAR not found!")
    return None

if __name__ == "__main__":
    lidar_port = find_lidar()
    if lidar_port:
        print(f"Connect your LiDAR using port: {lidar_port}")
    else:
        print("Please check your LiDAR connection.")
