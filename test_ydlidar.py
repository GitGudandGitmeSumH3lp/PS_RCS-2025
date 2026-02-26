#!/usr/bin/env python3
# test_ydlidar.py - Standalone test of YDLidar-SDK integration

import sys
sys.path.insert(0, 'src')

from hardware.lidar_adapter import LiDARAdapter
import time
import logging

logging.basicConfig(level=logging.INFO)

def main():
    print("🔍 Testing YDLIDAR X3 Integration")
    print("=" * 50)
    
    # Initialize adapter
    adapter = LiDARAdapter(config={
        "port": "/dev/ttyUSB1",
        "baudrate": 115200,
        "enable_simulation": False
    })
    
    # Connect
    print("\n1. Connecting to LiDAR...")
    if not adapter.connect():
        print("❌ Connection failed!")
        print(f"Error: {adapter.get_status().get('error')}")
        return
    print("✅ Connected")
    
    # Start scanning
    print("\n2. Starting scan...")
    if not adapter.start_scanning():
        print("❌ Failed to start scanning!")
        return
    print("✅ Scanning started")
    
    # Collect data
    print("\n3. Collecting 5 seconds of data...")
    for i in range(10):
        time.sleep(0.5)
        scan = adapter.get_latest_scan()
        status = adapter.get_status()
        print(f"  Iteration {i+1}: {scan['point_count']} points, "
              f"uptime: {status['uptime']:.1f}s")
        
        if scan['obstacles']:
            closest = min(scan['obstacles'], key=lambda x: x['distance'])
            print(f"    ⚠️  Closest obstacle: {closest['distance']:.0f}mm @ "
                  f"{closest['angle']:.1f}°")
    
    # Stop
    print("\n4. Stopping...")
    adapter.stop_scanning()
    adapter.disconnect()
    print("✅ Test complete")

if __name__ == "__main__":
    main()