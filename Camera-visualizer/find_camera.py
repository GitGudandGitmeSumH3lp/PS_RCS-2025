import cv2

def find_available_cameras(max_cameras_to_check=10):
    """
    Checks for available cameras by trying to open them by index.
    Returns a list of valid camera indices.
    """
    available_cameras = []
    print("Searching for available cameras...")
    for i in range(max_cameras_to_check):
        cap = cv2.VideoCapture(i)
        if cap is not None and cap.isOpened():
            print(f"  [SUCCESS] Camera found at index: {i}")
            available_cameras.append(i)
            cap.release() # Important to release the camera
        else:
            print(f"  [FAILURE] No camera at index: {i}")
    
    if not available_cameras:
        print("\nNo cameras found. Please check your connections and permissions.")
    else:
        print(f"\nFound valid camera(s) at index/indices: {available_cameras}")
        print(f"Use the first one ({available_cameras[0]}) in your application.")
    
    return available_cameras

if __name__ == '__main__':
    find_available_cameras()