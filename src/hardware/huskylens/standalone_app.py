import serial, time

ser = serial.Serial('/dev/serial0', 9600, timeout=0.5)

print("Listening on /dev/serial0...")
while True:
    data = ser.read(32)  # read up to 32 bytes
    if data:
        print("Raw data:", data.hex())
    time.sleep(0.1)
