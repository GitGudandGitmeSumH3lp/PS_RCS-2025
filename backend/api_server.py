# api_server.py
# Unified API server for Parcel Robot System with Integrated LiDAR WEB VISUALIZATION
import matplotlib
matplotlib.use('Agg')

import threading
import time
import json
import logging
from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit
from datetime import datetime
import traceback
import sys
import os
import atexit
import cv2

# --- START: LIDAR VISUALIZATION IMPORTS ---
import ydlidar
import numpy as np
import matplotlib.pyplot as plt
import base64
from io import BytesIO
# --- END: LIDAR VISUALIZATION IMPORTS ---

# Ensure correct path imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Module Imports ---
try:
    from motor_controller import MotorController
    motor_controller = MotorController(port='/dev/ttyUSB0')
except Exception as e:
    print(f"  MotorController not loaded: {e}")
    motor_controller = None

try:
    from backend.lidar_handler2 import LiDARHandler
    lidar_handler = LiDARHandler()
except Exception as e:
    print(f"  LiDARHandler not loaded: {e}")
    lidar_handler = None

try:
    from huskylens_handler import HuskyLensHandler
    huskylens_handler = HuskyLensHandler()
except Exception as e:
    print(f"  HuskyLensHandler not loaded: {e}")
    huskylens_handler = None

try:
    from ocr_handler import OCRHandler
    ocr_handler = OCRHandler()
except Exception as e:
    print(f"  OCRHandler not loaded: {e}")
    ocr_handler = None

try:
    from database import Database
    db = Database()
except Exception as e:
    print(f"  Database not loaded: {e}")
    db = None

# ---------------------------------
# --- START: CAMERA INTEGRATION ---
# ---------------------------------

def find_camera_index():
    """
    Automatically finds the first available camera index.
    """
    print("Searching for the first available camera...")
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"Success! Camera found at index: {i}")
            cap.release()
            return i
    return -1
camera_index = find_camera_index()
camera = None
if camera_index == -1:
    print("FATAL ERROR: No camera detected.")
    print("Please ensure the camera is connected properly.")
else:
    print(f"Attempting to use camera at index {camera_index}...")
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        print(f"FATAL ERROR: Could not open camera at index {camera_index}.")
        camera = None # Ensure camera object is None if it fails
    else:
        print("Camera opened successfully.")
lock = threading.Lock()        

def generate_frames():
    """
    Generates frames from the webcam. This function is now the REAL one.
    """
    global camera, lock
    if not camera:
        print("Camera is not available to generate frames.")
        return # Exit the generator if no camera

    while True:
        with lock:
            if not camera.isOpened():
                print("Warning: Camera is no longer open.")
                break
            # Read the camera frame
            success, frame = camera.read()
        
        if not success:
            print("Warning: Failed to grab frame from camera.")
            # Optional: attempt to reconnect or simply break
            break
        else:
            # Encode the frame in JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                print("Warning: Failed to encode frame.")
                continue
            
            frame_bytes = buffer.tobytes()
            # Yield the frame in the response
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        socketio.sleep(0.04) # Limit to ~25 FPS to reduce CPU load
# -------------------------------
# --- END: CAMERA INTEGRATION ---
# -------------------------------
#         
# ----------------------------
# GLOBAL CONFIG
# ----------------------------
app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static')
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ----------------------------------------------
# --- START: LIDAR VISUALIZATION INTEGRATION ---
# ----------------------------------------------

# --- LiDAR Configuration and Initialization ---
RMAX = 12.0  # YDLidar S2 PRO range
lidar_port = "/dev/ttyUSB1" # IMPORTANT: Make sure this is the correct port for your LiDAR

# Initialize laser object
laser = ydlidar.CYdLidar()
laser.setlidaropt(ydlidar.LidarPropSerialPort, lidar_port)
laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, 115200)
laser.setlidaropt(ydlidar.LidarPropLidarType, 0) # TYPE_TOF
laser.setlidaropt(ydlidar.LidarPropDeviceType, 0) # DEVICE_TYPE_SERIAL
laser.setlidaropt(ydlidar.LidarPropScanFrequency, 5.0)
laser.setlidaropt(ydlidar.LidarPropSingleChannel, True)
laser.setlidaropt(ydlidar.LidarPropMaxRange, RMAX)
laser.setlidaropt(ydlidar.LidarPropMinRange, 0.1)
laser.setlidaropt(ydlidar.LidarPropMaxAngle, 180.0)
laser.setlidaropt(ydlidar.LidarPropMinAngle, -180.0)
scan = ydlidar.LaserScan()
print("LiDAR visualizer configured.")

def run_lidar_visualization():
    """
    Background thread that gets data from LiDAR, generates a plot,
    and broadcasts it as an image over Socket.IO.
    """
    print("INFO: Starting LiDAR visualization thread...")
    frame_count = 0
    
    try:
        if not laser.initialize():
            print("ERROR: Failed to initialize LiDAR visualizer.")
            return

        print("INFO: LiDAR visualizer initialized successfully.")
        time.sleep(1) # Give it a moment
        
        if not laser.turnOn():
            print("ERROR: Failed to turn on LiDAR for visualizer.")
            laser.disconnecting()
            return
            
        print("INFO: LiDAR for visualizer turned on successfully!")
        while True:
            r = laser.doProcessSimple(scan)
            if r and len(scan.points) > 0:
                frame_count += 1
                
                # --- Extract Data for Plotting ---
                angle = [p.angle for p in scan.points]
                ran = [p.range for p in scan.points]
                intensity = [p.intensity for p in scan.points]

                # --- Create Plot in Memory (this does NOT open a window) ---
                fig = plt.figure(figsize=(8, 8))
                ax = fig.add_subplot(111, polar=True)
                ax.set_rmax(RMAX)
                ax.grid(True)
                ax.set_theta_zero_location('N')
                ax.set_theta_direction(-1)
                ax.set_title(f'Real-time LiDAR Scan | Points: {len(scan.points)}', pad=20)
                ax.scatter(angle, ran, c=intensity, cmap='plasma', alpha=0.9, s=10)
                
                # --- Convert Plot to a Base64 Encoded Image ---
                buf = BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                plt.close(fig) # CRITICAL: Close figure to free up memory
                
                # --- Emit the Image to the Client ---
                # We use a specific namespace to keep this separate
                socketio.emit('lidar_update', {'image': image_base64}, namespace='/lidar-vis')
                
            socketio.sleep(0.1) # Control update rate to ~10 FPS

    except Exception as e:
        print(f"ERROR in LiDAR visualization thread: {e}")
        traceback.print_exc()
    finally:
        print("INFO: Shutting down LiDAR for visualizer...")
        laser.turnOff()
        laser.disconnecting()
        print("INFO: LiDAR visualization thread finished.")

# --------------------------------------------
# --- END: LIDAR VISUALIZATION INTEGRATION ---
# --------------------------------------------

# Shared data storage (thread-safe)
shared_data = {
    "lidar_points": [],
    "huskylens_objects": [],
    "latest_ocr": {},
    "status": "initializing"
}
data_lock = threading.Lock()

# ----------------------------
# BACKGROUND TASKS
# ----------------------------

def run_lidar():
    """Background thread for LiDAR scanning and WebSocket broadcasting."""
    global shared_data
    if not lidar_handler:
        print("LiDAR handler not available.")
        with data_lock:
            shared_data["status"] = "lidar_error"
        return

    try:
        # The start_scan() method now correctly starts the background reading thread
        if not lidar_handler.start_scan():
            print("Failed to start LiDAR scanning.")
            with data_lock:
                shared_data["status"] = "lidar_error"
            return

        print("LiDAR scanning has started. Now streaming data...")
        
        # Loop indefinitely to get the latest data from the queue and broadcast it
        while True:
            # Get the latest points from the handler's queue
            # The handler already calculates x and y coordinates
            latest_points = lidar_handler.get_latest_data(max_points=360)
            
            if latest_points:
                # Store a copy for the REST API endpoint
                with data_lock:
                    # We only need x and y for the visualization
                    shared_data["lidar_points"] = [[p['x'], p['y']] for p in latest_points]

                # Broadcast data in the format the client expects: { points: [[x,y], ...], count: ... }
                socketio.emit('lidar_data', {
                    "points": shared_data["lidar_points"],
                    "count": len(latest_points)
                }, namespace='/lidar')

            # Control the update rate to about 20 FPS
            socketio.sleep(0.05) 

    except Exception as e:
        print(f"LiDAR thread error: {e}")
        traceback.print_exc()
        with data_lock:
            shared_data["status"] = "lidar_error"


def run_huskylens():
    """Background thread for HuskyLens."""
    global shared_data
    if not huskylens_handler:
        return
        
    if not huskylens_handler.connect():
        with data_lock:
            shared_data["status"] = "huskylens_error"
        return

    while True:
        try:
            objects = huskylens_handler.get_detections()
            with data_lock:
                shared_data["huskylens_objects"] = objects
            socketio.sleep(1.0)
        except Exception as e:
            print(f"HuskyLens error: {e}")
            socketio.sleep(2)

def run_ocr_simulator():
    """Simulate OCR detection."""
    global shared_data
    if not ocr_handler:
        return
        
    test_images = ["test_label1.png", "test_label2.png"]
    idx = 0
    while True:
        try:
            img_path = test_images[idx % len(test_images)]
            if os.path.exists(img_path):
                result = ocr_handler.process_image(img_path)
                if result:
                    with data_lock:
                        shared_data["latest_ocr"] = result
                    if db:
                        scan_id = db.create_scan(scan_type="ocr", note=f"OCR detection from {img_path}")
                        db.add_ocr_result(scan_id, result)
            idx += 1
            socketio.sleep(10)
        except Exception as e:
            print(f"OCR thread error: {e}")
            socketio.sleep(5)



# ----------------------------
# FLASK ROUTES
# ----------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/lidar')
def lidar_gui():
    return render_template('lidar_gui.html')

# --- Camera Stream ---
@app.route('/camera/stream')
def camera_stream():
    """This is the video streaming route. We will use this in our img src."""
    # This route now uses the real generate_frames function
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/camera/status')
def camera_status():
    cam_ok = camera is not None and camera.isOpened()
    return jsonify({'status': 'ok' if cam_ok else 'error'})

# --- Motor Control API ---
@app.route('/api/motor/connect', methods=['POST'])
def motor_connect():
    if not motor_controller:
        return jsonify({"status": "error", "message": "Motor controller not available"}), 500
    if motor_controller.is_connected:
        return jsonify({"status": "success", "message": "Already connected"})
    if motor_controller.connect():
        return jsonify({"status": "success", "message": "Motor controller connected"})
    else:
        return jsonify({"status": "error", "message": "Failed to connect to motor controller"}), 500

@app.route('/api/motor/disconnect', methods=['POST'])
def motor_disconnect():
    if not motor_controller:
        return jsonify({"status": "error", "message": "Motor controller not available"}), 500
    motor_controller.disconnect()
    return jsonify({"status": "success", "message": "Motor controller disconnected"})

@app.route('/api/motor/status', methods=['GET'])
def motor_status():
    if not motor_controller:
        return jsonify({"status": "error", "connected": False, "message": "Motor controller not available"}), 500
    return jsonify({"status": "success", "connected": motor_controller.is_connected})

@app.route('/api/motor/command/<command>', methods=['POST']) # Ensure POST method
def motor_command(command):
    if not motor_controller:
        return jsonify({"status": "error", "message": "Motor controller module not available"}), 500

    if not motor_controller.is_connected:
        # Attempt to connect on first command if not connected
        # Consider adding a timeout or retry limit here
        if not motor_controller.connect():
             return jsonify({"status": "error", "message": "Not connected and failed to connect to motor controller"}), 500

    # --- CRITICAL: Map API commands to MotorController methods ---
    # The MotorController methods (move_forward, etc.) are designed to send W, A, S, D, X
    # and handle the keep-alive internally. So we call the method that corresponds
    # to the command received.
    commands = {
        "W": motor_controller.move_forward,
        "A": motor_controller.turn_left,
        "S": motor_controller.move_backward,
        "D": motor_controller.turn_right,
        "X": motor_controller.stop
    }

    # --- CRITICAL: Ensure command case matches ---
    # The commands dictionary keys must match the case of the command received from the frontend.
    # The frontend sends 'W', 'A', 'S', 'D', 'X'.
    if command in commands:
        # Call the corresponding MotorController method
        success = commands[command]()
        if success:
            return jsonify({"status": "success", "command": command}), 200
        else:
            # Check if it failed due to disconnection
            if not motor_controller.is_connected:
                return jsonify({"status": "error", "message": "Command failed, motor controller disconnected"}), 500
            else:
                return jsonify({"status": "error", "message": f"Failed to execute command: {command}"}), 500
    else:
        return jsonify({"status": "error", "message": f"Unknown command: {command}"}), 400


# --- Sensor Data API ---
@app.route('/api/lidar')
def api_lidar():
    with data_lock:
        points = shared_data["lidar_points"][:]
    return jsonify({
        "points": [[p[0], p[1]] for p in points],
        "count": len(points),
        "timestamp": time.time()
    })

@app.route('/api/huskylens')
def api_huskylens():
    with data_lock:
        objects = shared_data["huskylens_objects"][:]
    return jsonify({
        "objects": objects,
        "count": len(objects),
        "timestamp": time.time()
    })

@app.route('/api/ocr')
def api_ocr():
    with data_lock:
        ocr_data = shared_data["latest_ocr"].copy()
    return jsonify(ocr_data if ocr_data else {"message": "No OCR result yet"})

# --- Database / Logs API ---
@app.route('/api/logs')
def api_logs():
    if not db:
        return jsonify({"error": "Database not available"}), 500
    scans = db.get_all_scans()
    return jsonify({"scans": scans})

@app.route('/api/scan/<int:scan_id>')
def api_scan(scan_id):
    if not db:
        return jsonify({"error": "Database not available"}), 500
    points = db.get_scan(scan_id)
    objects = db.get_objects_for_scan(scan_id)
    return jsonify({"scan_id": scan_id, "points": points, "objects": objects})

# --- System Status API ---
@app.route('/api/status')
def api_status():
    with data_lock:
        status = shared_data["status"]
    
    cam_ok = camera is not None
    if hasattr(camera, 'isOpened'):
        cam_ok = camera.isOpened()

    return jsonify({
        "status": status,
        "timestamp": time.time(),
        "modules": {
            "lidar": lidar_handler is not None,
            "huskylens": huskylens_handler is not None,
            "ocr": ocr_handler is not None,
            "motor": motor_controller is not None,
            "database": db is not None,
            "camera": cam_ok
        }
    })

# ----------------------------
# WEBSOCKET EVENTS
# ----------------------------
@socketio.on('connect', namespace='/lidar')
def lidar_connect():
    print(f'LiDAR client connected: {request.sid}')
    # Optionally send current status or latest scan on connect
    with data_lock:
        points = shared_data["lidar_points"][:]
    emit('lidar_data', {
        "points": [[p[0], p[1]] for p in points],
        "count": len(points)
    })

@socketio.on('disconnect', namespace='/lidar')
def lidar_disconnect():
    print(f'LiDAR client disconnected: {request.sid}')

# --- ADD THIS NEW HANDLER for the visualization clients ---
@socketio.on('connect', namespace='/lidar-vis')
def lidar_vis_connect():
    print(f'LiDAR visualizer client connected: {request.sid}')

@socketio.on('disconnect', namespace='/lidar-vis')
def lidar_vis_disconnect():
    print(f'LiDAR visualizer client disconnected: {request.sid}')
# --- END of new handler ---

# ----------------------------
# STARTUP & SHUTDOWN
# ----------------------------
def start_background_tasks():
    """Start all sensor and module threads."""
    if lidar_handler:
        socketio.start_background_task(run_lidar)
    if huskylens_handler:
        socketio.start_background_task(run_huskylens)
    if ocr_handler:
        socketio.start_background_task(run_ocr_simulator)
    
    with data_lock:
        shared_data["status"] = "running"
    print("All background tasks started.")

    # --- ADD THIS LINE to start the new visualizer thread ---
    socketio.start_background_task(run_lidar_visualization)
    # ---------------------------------------------------------
    with data_lock:
        shared_data["status"] = "running"
    print("All background tasks started.")    

def cleanup():
    """Cleanup resources on shutdown."""
    print("\nShutting down server and cleaning up resources...")
    if motor_controller:
        motor_controller.disconnect()
        print("Motor controller disconnected.")
    if lidar_handler:
        lidar_handler.disconnect()
        print("LiDAR handler disconnected.")
    # Add other cleanup logic here if needed
    print("Cleanup complete.")

# ----------------------------
# MAIN
# ----------------------------
if __name__ == '__main__':
    print("Starting Unified Parcel Robot API Server...")
    
    atexit.register(cleanup)
    start_background_tasks()

    print("\nAPI Server running on http://0.0.0.0:5000/")
    print("Access the main dashboard at: http://0.0.0.0:5000/dashboard")
    print("Access the LiDAR GUI at: http://0.0.0.0:5000/lidar\n")

    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        pass # Cleanup is handled by atexit
    except Exception as e:
        print(f"An unexpected server error occurred: {e}")
        traceback.print_exc()