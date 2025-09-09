# api_server.py
# Unified API server for Parcel Robot System

import threading
import time
import json
import logging
from flask import Flask, render_template, Response, jsonify
import traceback
import sys
import os
# Ensure correct path imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import your modules
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

# Import camera stream
try:
    from frontend.gui import generate_frames, camera, lock
except Exception as e:
    print(f"  Camera stream not loaded: {e}")
    # Create dummy functions
    def generate_frames():
        while True:
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n\r\n'
    camera = None
    lock = threading.Lock()

# ----------------------------
# GLOBAL CONFIG
# ----------------------------
app = Flask(__name__, 
            template_folder='../frontend/templates',
            static_folder='../frontend/static')

# Shared data storage (thread-safe)
shared_data = {
    "lidar_points": [],
    "huskylens_objects": [],
    "latest_ocr": {},
    "status": "running"
}

data_lock = threading.Lock()

# ----------------------------
# BACKGROUND TASKS
# ----------------------------

def run_lidar():
    """Background thread for LiDAR scanning."""
    global shared_data
    if not lidar_handler:
        return
        
    try:
        if not lidar_handler.connect():
            shared_data["status"] = "lidar_error"
            return
            
        for scan in lidar_handler.start_scan():
            points = lidar_handler.process_scan(scan)
            with data_lock:
                shared_data["lidar_points"] = points
            time.sleep(0.1)  # ~10Hz
    except Exception as e:
        print(f"LiDAR thread error: {e}")
        shared_data["status"] = "lidar_error"

def run_huskylens():
    """Background thread for HuskyLens."""
    global shared_data
    if not huskylens_handler:
        return
        
    if not huskylens_handler.connect():
        shared_data["status"] = "huskylens_error"
        return

    while True:
        try:
            objects = huskylens_handler.get_detections()
            with data_lock:
                shared_data["huskylens_objects"] = objects
            time.sleep(1.0)
        except Exception as e:
            print(f"HuskyLens error: {e}")
            time.sleep(2)

def run_ocr_simulator():
    """Simulate OCR detection (replace with real image trigger later)."""
    global shared_data
    if not ocr_handler:
        return
        
    # For simulation, we'll use a test image
    test_images = ["test_label1.png", "test_label2.png"]  # Replace with real paths
    idx = 0
    while True:
        try:
            img = test_images[idx % len(test_images)]
            result = ocr_handler.process_image(img)
            if result:
                with data_lock:
                    shared_data["latest_ocr"] = result
                # Log to database
                if db:
                    scan_id = db.create_scan(scan_type="ocr", note="OCR detection")
                    db.add_ocr_result(scan_id, result)
            idx += 1
            time.sleep(10)  # Simulate new label every 10s
        except Exception as e:
            print(f"OCR thread error: {e}")
            time.sleep(5)

# ----------------------------
# FLASK ROUTES
# ----------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ——————————————————————————
# CAMERA STREAM
# ——————————————————————————
@app.route('/camera/stream')
def camera_stream():
    try:
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print(f"Camera stream error: {e}")
        return "Camera not available", 500

@app.route('/camera/status')
def camera_status():
    cam_ok = camera is not None and camera.isOpened()
    return {'status': 'ok' if cam_ok else 'error'}


# ----------------------------
# MOTOR CONTROL API ENDPOINTS
# ----------------------------
@app.route('/api/motor/connect', methods=['POST'])
def motor_connect():
    if not motor_controller:
        return jsonify({"status": "error", "message": "Motor controller module not available"}), 500

    if motor_controller.is_connected:
        return jsonify({"status": "success", "message": "Already connected"}), 200

    if motor_controller.connect():
        return jsonify({"status": "success", "message": "Motor controller connected"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to connect to motor controller"}), 500

@app.route('/api/motor/disconnect', methods=['POST'])
def motor_disconnect():
    if not motor_controller:
        return jsonify({"status": "error", "message": "Motor controller module not available"}), 500

    motor_controller.disconnect()
    return jsonify({"status": "success", "message": "Motor controller disconnected"}), 200

@app.route('/api/motor/status', methods=['GET'])
def motor_status():
    if not motor_controller:
        return jsonify({"status": "error", "connected": False, "message": "Motor controller module not available"}), 500
    return jsonify({"status": "success", "connected": motor_controller.is_connected}), 200

@app.route('/api/motor/command/<command>', methods=['POST'])
def motor_command(command):
    if not motor_controller:
        return jsonify({"status": "error", "message": "Motor controller module not available"}), 500

    if not motor_controller.is_connected:
        # Attempt to connect on first command if not connected
        if not motor_controller.connect():
             return jsonify({"status": "error", "message": "Not connected and failed to connect to motor controller"}), 500

    # Map API commands to MotorController methods
    commands = {
        "forward": motor_controller.move_forward,
        "backward": motor_controller.move_backward,
        "left": motor_controller.turn_left,
        "right": motor_controller.turn_right,
        "stop": motor_controller.stop
    }

    if command in commands:
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

# ——————————————————————————
# LiDAR ENDPOINTS
# ——————————————————————————
@app.route('/api/lidar')
def api_lidar():
    with data_lock:
        points = shared_data["lidar_points"][:]
    return jsonify({
        "points": [[p[0], p[1]] for p in points],
        "count": len(points),
        "timestamp": time.time()
    })

# ——————————————————————————
# HUSKYLENS ENDPOINTS
# ——————————————————————————
@app.route('/api/huskylens')
def api_huskylens():
    with data_lock:
        objects = shared_data["huskylens_objects"][:]
    return jsonify({
        "objects": objects,
        "count": len(objects),
        "timestamp": time.time()
    })

# ——————————————————————————
# OCR ENDPOINTS
# ——————————————————————————
@app.route('/api/ocr')
def api_ocr():
    with data_lock:
        ocr_data = shared_data["latest_ocr"].copy()
    return jsonify(ocr_data) if ocr_data else jsonify({"message": "No OCR result yet"})

# ——————————————————————————
# DATABASE / LOGS
# ——————————————————————————
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

# ——————————————————————————
# SYSTEM STATUS
# ——————————————————————————
@app.route('/api/status')
def api_status():
    with data_lock:
        status = shared_data["status"]
    return jsonify({
        "status": status,
        "timestamp": time.time(),
        "modules": {
            "lidar": lidar_handler is not None,
            "huskylens": huskylens_handler is not None,
            "ocr": ocr_handler is not None,
            "motor": motor_controller is not None,
            "camera": camera is not None and camera.isOpened()
        }
    })

# ----------------------------
# STARTUP
# ----------------------------
def start_background_tasks():
    """Start all sensor threads."""
    # Start LiDAR thread
    if lidar_handler:
        threading.Thread(target=run_lidar, daemon=True).start()

    # Start HuskyLens thread
    if huskylens_handler:
        threading.Thread(target=run_huskylens, daemon=True).start()

    # Start OCR thread
    if ocr_handler:
        threading.Thread(target=run_ocr_simulator, daemon=True).start()

    print(" Background tasks started.")

# ----------------------------
# MAIN
# ----------------------------
if __name__ == '__main__':
    print(" Starting API Server... Initializing modules...")
    start_background_tasks()

    print(" API Server running on http://0.0.0.0:5000/")
    try:
        app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
    except KeyboardInterrupt:
        print("\n Shutting down API server...")
    except Exception as e:
        print(f" Server error: {e}")
        traceback.print_exc()