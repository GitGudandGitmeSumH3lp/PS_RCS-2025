#!/usr/bin/env python3
from pyhuskylens import HuskyLens, ALGORITHM_OBJECT_CLASSIFICATION
import time

hl = HuskyLens('/dev/ttyUSB0')
hl.knock()
hl.set_alg(ALGORITHM_OBJECT_CLASSIFICATION)
print("📡 Reading classifications (Ctrl+C to stop)...")

while True:
    blocks = hl.get_blocks()
    if blocks:
        print(f"\n[{time.strftime('%H:%M:%S')}] Found {len(blocks)} classified objects:")
        for i, block in enumerate(blocks):
            class_name = hl.get_name_for_id(block.ID) or "Unknown"
            confidence = getattr(block, 'confidence', 'N/A')
            print(f"  Class {block.ID}: '{class_name}' at ({block.x},{block.y}) [conf: {confidence}]")
    else:
        print(".", end="", flush=True)
    time.sleep(1)