from rplidar import RPLidar
lidar = RPLidar('/dev/ttyUSB1')
print("Info:", lidar.get_info())
print("Health:", lidar.get_health())
for i, scan in enumerate(lidar.iter_scans()):
    print(f"Scan {i}: {len(scan)} points")
    if i > 3:
        break
lidar.stop()
lidar.disconnect()