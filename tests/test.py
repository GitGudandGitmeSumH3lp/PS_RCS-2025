import cv2
print("Opening camera 0 with V4L2...")
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
if not cap.isOpened():
    print("FAILED to open index 0")
else:
    print("SUCCESS! Camera opened.")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    ret, frame = cap.read()
    print(f"Read frame: {ret}")
    cap.release()