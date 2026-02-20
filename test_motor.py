# test_motor.py
import serial
import time

ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=2)
time.sleep(2)          # give Arduino time to reset and arm
ser.write(b'W')        # forward command
ser.flush()
print("Sent 'W' – motors should run forward for a moment")
time.sleep(2)
ser.write(b'X')        # stop
ser.close()