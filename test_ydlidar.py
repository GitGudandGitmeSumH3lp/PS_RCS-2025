#!/usr/bin/env python3
# test_ydlidar.py - Test the YDLidarReader wrapper

import sys
import time
import logging

# Add project root to Python path so we can import from hardware
sys.path.insert(0, '.')

from src.hardware.ydlidar_reader import YDLidarReader

# Set up logging to see debug messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    print(" Testing YDLidarReader with corrected API")
    print("=" * 50)

    # Adjust port if necessary; default is /dev/ttyUSB1
    port = '/dev/ttyUSB1'
    baud = 115200

    print(f"1. Initializing reader on {port} @ {baud}...")
    reader = YDLidarReader(port=port, baudrate=baud)

    print("2. Connecting...")
    if not reader.connect():
        print(" Connection failed!")
        return
    print(" Connected")

    print("3. Starting scan...")
    if not reader.start_scan():
        print(" Failed to start scan!")
        return
    print(" Scanning started")

    print("4. Collecting data for 5 seconds...")
    for i in range(10):   # 10 * 0.5s = 5 seconds
        time.sleep(0.5)
        data = reader.get_latest_data()
        print(f"   Scan {i+1}: {len(data)} points")
        if data:
            # Show a sample point
            sample = data[0]
            print(f"      sample: angle={sample['angle']:.1f}°, "
                  f"dist={sample['distance']:.0f}mm, "
                  f"quality={sample['quality']}")

    print("5. Stopping scan...")
    reader.stop_scan()
    print(" Done")

if __name__ == "__main__":
    main()