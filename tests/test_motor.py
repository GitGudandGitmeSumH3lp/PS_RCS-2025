import serial
import time

ser = serial.Serial('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0', 9600, timeout=1)
time.sleep(2)  # let Arduino reset

# Send forward at speed 128
ser.write(bytes([256]) + b'W')
ser.flush()
print("Sent forward 256")
time.sleep(3)

# Send stop
ser.write(bytes([0]) + b'X')
ser.flush()
print("Sent stop")
ser.close()