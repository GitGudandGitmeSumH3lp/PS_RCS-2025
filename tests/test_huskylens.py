#!/usr/bin/env python3
"""
HuskyLens Object Recognition Test for Headless Raspberry Pi
Tests both USB and I2C connections
"""

import time
import sys

# Try both possible library imports
try:
    from huskylib import HuskyLensLibrary
    print("✓ Using huskylib library")
except ImportError:
    try:
        from pyhuskylens import HuskyLens, ALGORITHM_OBJECT_RECOGNITION
        USING_PYHUSKYLENS = True
        print("✓ Using pyhuskylens library")
    except ImportError:
        print("✗ No HuskyLens library found. Install with:")
        print("  pip install pyhuskylens[serial]")
        print("  or download huskylib.py from GitHub")
        sys.exit(1)

def test_usb_connection():
    """Test HuskyLens via USB serial connection"""
    print("\n🔌 Testing USB Connection...")
    try:
        # Common serial ports - adjust if yours is different
        ports = ['/dev/ttyUSB0', '/dev/ttyACM0']
        
        for port in ports:
            try:
                if USING_PYHUSKYLENS:
                    hl = HuskyLens(port)
                else:
                    hl = HuskyLensLibrary("SERIAL", port)
                
                result = hl.knock()
                print(f"  ✓ Connected on {port}")
                print(f"  ✓ Knock result: {result}")
                return hl
            except:
                continue
        
        print("  ✗ Could not connect on any serial port")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None

def test_i2c_connection():
    """Test HuskyLens via I2C"""
    print("\n🔌 Testing I2C Connection...")
    try:
        if USING_PYHUSKYLENS:
            hl = HuskyLens(1)  # I2C bus 1
        else:
            hl = HuskyLensLibrary("I2C", "", address=0x32)
        
        result = hl.knock()
        print(f"  ✓ Connected via I2C")
        print(f"  ✓ Knock result: {result}")
        return hl
    except Exception as e:
        print(f"  ✗ I2C connection failed: {e}")
        return None

def read_object_data(hl):
    """Main loop to read and display object recognition data"""
    print("\n🎯 Setting up Object Recognition...")
    
    # Set algorithm to object recognition/classification
    try:
        if USING_PYHUSKYLENS:
            hl.set_alg(ALGORITHM_OBJECT_RECOGNITION)
        else:
            hl.algorthim("ALGORITHM_OBJECT_RECOGNITION")
        print("  ✓ Algorithm set to Object Recognition")
    except Exception as e:
        print(f"  ✗ Failed to set algorithm: {e}")
        return
    
    print("\n📡 Reading object data (press Ctrl+C to stop)...")
    print("-" * 50)
    
    try:
        while True:
            # Get all detected objects
            if USING_PYHUSKYLENS:
                # For pyhuskylens library
                objects = hl.get_blocks()
                learned_objects = hl.get_blocks(learned=True)
            else:
                # For huskylib library
                objects = hl.requestAll()
                learned_objects = hl.learnedBlocks()
            
            # Display results
            if objects and len(objects) > 0:
                print(f"\n⏱️  Scan at {time.strftime('%H:%M:%S')}")
                print(f"   Total objects: {len(objects)}")
                print(f"   Learned objects: {len(learned_objects) if learned_objects else 0}")
                
                for i, obj in enumerate(objects[:3]):  # Show first 3 objects
                    # Object properties vary by library, but common ones:
                    obj_id = getattr(obj, 'ID', getattr(obj, 'id', 'N/A'))
                    obj_x = getattr(obj, 'x', getattr(obj, 'xCenter', 'N/A'))
                    obj_y = getattr(obj, 'y', getattr(obj, 'yCenter', 'N/A'))
                    obj_w = getattr(obj, 'width', 'N/A')
                    obj_h = getattr(obj, 'height', 'N/A')
                    obj_learned = getattr(obj, 'learned', False)
                    
                    status = "✓" if obj_learned else "○"
                    print(f"   {status} Object {i+1}: ID={obj_id}, "
                          f"Pos=({obj_x},{obj_y}), Size={obj_w}x{obj_h}")
            else:
                print(".", end="", flush=True)  # No objects found
            
            time.sleep(1)  # Update every second
            
    except KeyboardInterrupt:
        print("\n\n✓ Test complete. Object data successfully read.")
    except Exception as e:
        print(f"\n✗ Error reading data: {e}")

def main():
    """Main test function"""
    print("=" * 50)
    print("HUSKYLENS OBJECT RECOGNITION TEST")
    print("=" * 50)
    
    # Try USB first, then I2C
    hl = test_usb_connection()
    if not hl:
        hl = test_i2c_connection()
    
    if not hl:
        print("\n✗ Could not establish any connection to HuskyLens")
        print("\nTroubleshooting tips:")
        print("1. Check USB: ls /dev/ttyUSB*")
        print("2. Check I2C: sudo i2cdetect -y 1")
        print("3. Verify HuskyLens is powered (LED should be on)")
        print("4. Try different USB cable/port")
        return
    
    # Read and display object data
    read_object_data(hl)

if __name__ == "__main__":
    main()