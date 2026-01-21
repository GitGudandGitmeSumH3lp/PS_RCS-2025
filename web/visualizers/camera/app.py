from flask import Flask, render_template, Response
import cv2
import sys

app = Flask(__name__)

def find_camera_index():
    """
    Automatically finds the first available camera index.
    Returns the index number or -1 if no camera is found.
    """
    print("Searching for the first available camera...")
    # Check indices 0 through 9
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"Success! Camera found at index: {i}")
            cap.release() # Release it so the main app can use it
            return i
    return -1

# --- CAMERA SETUP ---
# Automatically find the camera index when the app starts
camera_index = find_camera_index()

if camera_index == -1:
    print("FATAL ERROR: No camera detected.")
    print("Please ensure the camera is connected properly and you have run 'sudo usermod -a -G video $USER' and rebooted.")
    sys.exit() # Exit the script if no camera is found

# Open the camera with the automatically found index
print(f"Attempting to use camera at index {camera_index}...")
camera = cv2.VideoCapture(camera_index)
if not camera.isOpened():
    print(f"FATAL ERROR: Could not open camera at index {camera_index}, even though it was detected.")
    sys.exit()

print("Camera opened successfully. Starting video stream...")

def generate_frames():
    """Generates frames from the webcam to be displayed in the browser."""
    while True:
        # Read the camera frame
        success, frame = camera.read()
        if not success:
            print("Warning: Failed to grab frame from camera.")
            break
        else:
            # Encode the frame in JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                print("Warning: Failed to encode frame.")
                continue
            frame = buffer.tobytes()
            # Yield the frame in the response
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    """Video streaming home page."""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("Starting Flask web server...")
    # Running on port 8080 to avoid conflicts
    app.run(host='0.0.0.0', port=8080, debug=False) # debug=False for cleaner output