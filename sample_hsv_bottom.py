import cv2
import numpy as np
import sys

if len(sys.argv) < 2:
    print("Usage: python sample_hsv_bottom.py <image_path>")
    sys.exit(1)

img = cv2.imread(sys.argv[1])
if img is None:
    print("Failed to load image")
    sys.exit(1)

h, w = img.shape[:2]
# Sample bottom 10% of the image (where footer usually is)
bottom_region = img[int(h*0.9):, :]
hsv_region = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2HSV)

# Compute average HSV of the region (or you can print min/max)
avg_hue = np.mean(hsv_region[:,:,0])
avg_sat = np.mean(hsv_region[:,:,1])
avg_val = np.mean(hsv_region[:,:,2])

print(f"Average HSV in bottom 10%: H={avg_hue:.1f}, S={avg_sat:.1f}, V={avg_val:.1f}")

# Also print min/max for each channel to get a range
min_hue = np.min(hsv_region[:,:,0])
max_hue = np.max(hsv_region[:,:,0])
min_sat = np.min(hsv_region[:,:,1])
max_sat = np.max(hsv_region[:,:,1])
min_val = np.min(hsv_region[:,:,2])
max_val = np.max(hsv_region[:,:,2])

print(f"Hue range: {min_hue} – {max_hue}")
print(f"Saturation range: {min_sat} – {max_sat}")
print(f"Value range: {min_val} – {max_val}")