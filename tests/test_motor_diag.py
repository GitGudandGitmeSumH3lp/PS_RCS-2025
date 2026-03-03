import time
import serial
import sys

# The exact port from your logs
PORT = '/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'
BAUD = 9600

def send_cmd(ser, cmd_char, speed):
    packet = cmd_char.encode('ascii') + bytes([speed])
    ser.write(packet)
    ser.flush()
    print(f"   -> Sent: [{cmd_char}] at PWM {speed}")

try:
    print(f" Connecting to {PORT}...")
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(" Waiting 3 seconds for Arduino to initialize and ESCs to arm...")
    time.sleep(3)
except Exception as e:
    print(f" Connection failed: {e}")
    sys.exit(1)

def run_test():
    while True:
        print("\n=====================================")
        print(" MOTOR DIAGNOSTIC MENU")
        print("1. Test 'Speed Ramp' (0 -> 100% slowly)")
        print("2. Test 'Instant Full' (Instantly 100%)")
        print("3. Test 'UI Heartbeat' (50% sent every 100ms)")
        print("4. Test 'Low Speed Heartbeat' (20% sent every 100ms)")
        print("5. Stop Motors")
        print("Q. Quit")
        
        choice = input("\nSelect a test (1-5, Q): ").strip().upper()
        
        if choice == 'Q':
            send_cmd(ser, 'X', 0)
            ser.close()
            break
            
        elif choice == '1':
            print("\n Running Test 1: Speed Ramp (Wait 800ms between steps)...")
            for speed in [64, 128, 192, 255]:
                send_cmd(ser, 'W', speed)
                time.sleep(0.8)
            send_cmd(ser, 'X', 0)
            
        elif choice == '2':
            print("\n🚀 Running Test 2: Instant Full (Single burst of 255)...")
            send_cmd(ser, 'W', 255)
            time.sleep(2)
            send_cmd(ser, 'X', 0)
            
        elif choice == '3':
            print("\n Running Test 3: UI Heartbeat (Sending 128 every 0.1s for 3 seconds)...")
            for _ in range(30):
                send_cmd(ser, 'W', 128)
                time.sleep(0.1)
            send_cmd(ser, 'X', 0)

        elif choice == '4':
            print("\n Running Test 4: Low Speed Heartbeat (Sending 50 every 0.1s for 3 seconds)...")
            for _ in range(30):
                send_cmd(ser, 'W', 50)
                time.sleep(0.1)
            send_cmd(ser, 'X', 0)
            
        elif choice == '5':
            send_cmd(ser, 'X', 0)
            print(" Motors Stopped.")
        
        else:
            print("Invalid choice.")

if __name__ == '__main__':
    try:
        run_test()
    except KeyboardInterrupt:
        send_cmd(ser, 'X', 0)
        ser.close()
        print("\nExiting.")