#!/usr/bin/env python3
"""
Simple HuskyLens Object Recognition Test
Uses pyhuskylens library over USB
"""

import time
from pyhuskylens import HuskyLens, ALGORITHM_OBJECT_RECOGNITION

# Initialize on USB port
hl = HuskyLens('/dev/ttyUSB0')

# Check communication (knock)
print("🔍 Knocking...")
try:
    hl.knock()
    print("✓ HuskyLens responded!")
except Exception as e:
    print(f"✗ No response: {e}")
    exit(1)

# Set algorithm to object recognition
print("🎯 Setting algorithm...")
hl.set_alg(ALGORITHM_OBJECT_RECOGNITION)
print("✓ Algorithm set to Object Recognition")

print("\n📡 Reading objects (press Ctrl+C to stop)...")
print("Make sure objects are in front of the camera.\n")

try:
    while True:
        # Get all blocks (detected objects)
        blocks = hl.get_blocks()
        if blocks:
            print(f"\n[{time.strftime('%H:%M:%S')}] Found {len(blocks)} object(s):")
            for i, block in enumerate(blocks):
                # block attributes: ID, x, y, width, height, learned, etc.
                learned = "✓" if block.learned else "○"
                print(f"  {learned} Object {i+1}: ID={block.ID}, "
                      f"pos=({block.x},{block.y}), size={block.width}x{block.height}")
        else:
            # Print a dot to show it's alive
            print(".", end="", flush=True)

        time.sleep(1)

except KeyboardInterrupt:
    print("\n\n✅ Test finished.")