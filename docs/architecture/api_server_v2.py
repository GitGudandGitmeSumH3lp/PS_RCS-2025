# api_server.py
# Unified API server for Parcel Robot System with Integrated LiDAR WEB VISUALIZATION

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
    from lidar_handler import LiDARHandler
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

try:
    from frontend.gui import generate_frames, camera, lock
except Exception as e:
    print(f"  Camera stream not loaded: {e}")
    def generate_frames():
        while True:
            time.sleep(1)
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n\r\n'
    camera = None
    lock = threading.Lock()

# ----------------------------
# GLOBAL CONFIG
# ----------------------------
app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static')
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
        return

    try:
        if not lidar_handler.connect():
            with data_lock:
                shared_data["status"] = "lidar_error"
            print("Failed to connect to LiDAR.")
            return

        print("LiDAR connected and scanning started.")
        for scan in lidar_handler.start_scan():
            points = lidar_handler.process_scan(scan)
            with data_lock:
                shared_data["lidar_points"] = points
            
            # Broadcast data to WebSocket clients
            socketio.emit('lidar_data', {
                "points": [[p[0], p[1]] for p in points],
                "count": len(points)
            }, namespace='/lidar')
            socketio.sleep(0.1) # Yield to other tasks
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
    try:
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print(f"Camera stream error: {e}")
        return "Camera not available", 500

@app.route('/camera/status')
def camera_status():
    cam_ok = camera is not None
    if hasattr(camera, 'isOpened'):
        cam_ok = camera.isOpened()
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

@app.route('/api/motor/command/<command>', methods=['POST'])
def motor_command(command):
    if not motor_controller or not motor_controller.is_connected:
        return jsonify({"status": "error", "message": "Motor controller not connected"}), 500
    
    commands = {
        "forward": motor_controller.move_forward,
        "backward": motor_controller.move_backward,
        "left": motor_controller.turn_left,
        "right": motor_controller.turn_right,
        "stop": motor_controller.stop
    }
    if command in commands:
        if commands[command]():
            return jsonify({"status": "success", "command": command})
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