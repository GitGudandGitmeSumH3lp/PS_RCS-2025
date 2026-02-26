# test_simple.py
import ydlidar
import time

laser = ydlidar.CYdLidar()
laser.setSerialPort('/dev/ttyUSB1')
laser.setSerialBaudrate(115200)

if laser.initialize():
    print("Initialized")
    if laser.turnOn():
        print("Motor on, scanning...")
        scan = ydlidar.LaserScan()
        for i in range(10):
            if laser.doProcessSimple(scan):
                print(f"Scan {i}: {scan.points.size()} points")
            time.sleep(1)
        laser.turnOff()
    else:
        print("Motor start failed")
else:
    print("Init failed")
laser.disconnecting()