#!/usr/bin/env python3
"""
HuskyLens Object Classification Test
Detects parcels trained as classes.
"""

import time
from pyhuskylens import HuskyLens, ALGORITHM_OBJECT_CLASSIFICATION

# Initialize on USB port
hl = HuskyLens('/dev/ttyUSB0')

# Knock to verify connection
hl.knock()
print("✓ HuskyLens connected")

# Set algorithm to CLASSIFICATION (critical!)
hl.set_alg(ALGORITHM_OBJECT_CLASSIFICATION)
print("✓ Algorithm set to OBJECT CLASSIFICATION")

print("\n Reading classifications (Ctrl+C to stop)...")
print("Place trained parcels in view.\n")

try:
    while True:
        blocks = hl.get_blocks()
        if blocks:
            print(f"\n[{time.strftime('%H:%M:%S')}] Found {len(blocks)} objects:")
            for i, block in enumerate(blocks):
                # Get the name you assigned during training (e.g., "PARCEL")
                name = hl.get_name_for_id(block.ID) or f"ID{block.ID}"
                confidence = getattr(block, 'confidence', 'N/A')
                learned = "✓" if block.learned else "○"
                print(f"  {learned} {name}: ID={block.ID}, pos=({block.x},{block.y}), "
                      f"size={block.width}x{block.height}, conf={confidence}")
        else:
            print(".", end="", flush=True)
        time.sleep(1)
except KeyboardInterrupt:
    print("\n Done.")