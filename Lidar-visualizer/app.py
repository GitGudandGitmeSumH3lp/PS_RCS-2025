# --- CRITICAL: Set Matplotlib Backend FIRST, before ANY other imports ---
import os
os.environ['MPLBACKEND'] = 'Agg' # Alternative way to set backend early
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend to prevent hangs
print("DEBUG: Matplotlib backend set to Agg") # Debug print

# --- Standard Imports (after backend is set) ---
print("DEBUG: Starting imports...") # Debug print
try:
    import ydlidar
    print("DEBUG: ydlidar imported")
    import time
    import sys
    import matplotlib.pyplot as plt # This should now use Agg
    print("DEBUG: matplotlib.pyplot imported")
    import numpy as np
    print("DEBUG: numpy imported")
    from flask import Flask, render_template
    print("DEBUG: flask imported")
    from flask_socketio import SocketIO
    print("DEBUG: flask_socketio imported")
    import base64
    from io import BytesIO
    from threading import Thread
    print("DEBUG: All imports successful")
except Exception as e:
    print(f"ERROR during imports: {e}")
    raise # Re-raise to see the full traceback

# --- Flask App and SocketIO Setup ---
print("DEBUG: Setting up Flask app...")
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_strong_secret_key_change_me'
print("DEBUG: Flask app created")

try:
    print("DEBUG: Setting up SocketIO...")
    socketio = SocketIO(app, cors_allowed_origins="*")
    print("DEBUG: SocketIO created")
except Exception as e:
    print(f"ERROR during SocketIO setup: {e}")
    raise

# --- LiDAR Configuration and Initialization ---
print("DEBUG: Configuring LiDAR...")
RMAX = 12.0  # S2PRO range
port = "/dev/ttyUSB1" # Double check this port

# Initialize laser
laser = ydlidar.CYdLidar()
laser.setlidaropt(ydlidar.LidarPropSerialPort, port)
laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, 115200)
laser.setlidaropt(ydlidar.LidarPropLidarType, 0) # TYPE_TOF
laser.setlidaropt(ydlidar.LidarPropDeviceType, 0) # DEVICE_TYPE_SERIAL
laser.setlidaropt(ydlidar.LidarPropScanFrequency, 5.0) # Adjust if needed
laser.setlidaropt(ydlidar.LidarPropSingleChannel, True) # S2 Pro is single channel
laser.setlidaropt(ydlidar.LidarPropMaxRange, RMAX)
laser.setlidaropt(ydlidar.LidarPropMinRange, 0.1)
laser.setlidaropt(ydlidar.LidarPropMaxAngle, 180.0)
laser.setlidaropt(ydlidar.LidarPropMinAngle, -180.0)

scan = ydlidar.LaserScan()
thread = None
print("DEBUG: LiDAR configured")

# --- Background Thread for LiDAR Scanning ---
def lidar_scan_thread():
    """
    Background thread that continuously gets data from the LiDAR
    and sends it to the client.
    """
    print("INFO: Starting LiDAR scan thread...")
    frame_count = 0
    
    # --- LiDAR Initialization ---
    print("INFO: Attempting to initialize LiDAR...")
    try:
        if laser.initialize():
            print("INFO: Lidar initialized successfully")
            time.sleep(1)
            
            # --- LiDAR Turn On ---
            print("INFO: Attempting to turn on LiDAR...")
            if laser.turnOn():
                print("INFO: Lidar turned on successfully!")
                
                # --- Main Scan Loop ---
                try:
                    while True:
                        # --- Get Scan Data ---
                        # print(f"DEBUG: Frame {frame_count}: Waiting for scan data...")
                        r = laser.doProcessSimple(scan)
                        
                        if r and len(scan.points) > 0:
                            frame_count += 1
                            # print(f"DEBUG: Frame {frame_count}: Received {len(scan.points)} points")
                            
                            # --- Extract Data ---
                            angle = []
                            ran = []
                            intensity = []
                            for point in scan.points:
                                angle.append(point.angle)
                                ran.append(point.range)
                                intensity.append(point.intensity)

                            # --- Create Plot in Memory ---
                            # print(f"DEBUG: Frame {frame_count}: Creating plot...")
                            fig = plt.figure(figsize=(8, 8))
                            lidar_polar = plt.subplot(polar=True)
                            lidar_polar.set_rmax(RMAX)
                            lidar_polar.grid(True)
                            lidar_polar.set_theta_zero_location('N')
                            lidar_polar.set_theta_direction(-1)
                            title = 'YDLidar S2PRO - Points: {} | Frame: {}'.format(
                                len(scan.points), frame_count
                            )
                            lidar_polar.set_title(title, pad=20)
                            lidar_polar.scatter(angle, ran, c=intensity, cmap='plasma', alpha=0.8, s=15)
                            
                            # --- Convert Plot to Image for Web ---
                            # print(f"DEBUG: Frame {frame_count}: Converting plot to image...")
                            buf = BytesIO()
                            fig.savefig(buf, format='png')
                            buf.seek(0)
                            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                            plt.close(fig) # Important: Close the figure to free memory
                            
                            # --- Emit Image to Client ---
                            # print(f"DEBUG: Frame {frame_count}: Emitting image to client...")
                            socketio.emit('lidar_update', {'image': image_base64})
                            
                        # Control the update rate
                        socketio.sleep(0.1) # Use socketio.sleep for background tasks
                        
                except Exception as e:
                    print(f"ERROR in LiDAR scan loop: {e}")
                finally:
                    # Ensure clean shutdown
                    print("INFO: Turning off LiDAR...")
                    laser.turnOff()
                    print("INFO: Disconnecting LiDAR...")
                    laser.disconnecting()
                    print("INFO: LiDAR scan thread finished.")
            else:
                print("ERROR: Failed to turn on lidar")
        else:
            print("ERROR: Failed to initialize lidar")
    except Exception as e:
        print(f"ERROR during LiDAR init/turnOn: {e}")
    finally:
        # Ensure clean shutdown if init/turn on fails
        try:
            laser.turnOff()
            laser.disconnecting()
        except:
            pass # Ignore errors during final cleanup
        print("INFO: LiDAR scan thread exited.")

# --- Flask Routes ---
@app.route('/')
def index():
    print("INFO: Client requested index page")
    return render_template('index.html')

@socketio.on('connect')
def connect():
    global thread
    print('INFO: Client connected')
    if thread is None:
        print("INFO: Starting new LiDAR background thread...")
        thread = socketio.start_background_task(target=lidar_scan_thread)

@socketio.on('disconnect')
def disconnect():
    print('INFO: Client disconnected')

# --- Main Application ---
if __name__ == '__main__':
    print("INFO: Starting Flask-SocketIO server...")
    # It's generally recommended to keep debug=False with threading
    try:
        socketio.run(app, host='0.0.0.0', port=5050, debug=False, allow_unsafe_werkzeug=True) # allow_unsafe_werkzeug might be needed on Pi
        # If you must use debug=True, consider using 'flask run --debug' command instead
        # or handle the reloader carefully.
    except KeyboardInterrupt:
        print("\nINFO: Server shutdown requested by user (Ctrl+C).")
    except Exception as e:
        print(f"ERROR in main application loop: {e}")
    finally:
        print("INFO: Performing final cleanup...")
        # Attempt to stop the lidar thread if it exists and is alive
        # Note: Thread management can be tricky. Ensure laser cleanup happens inside the thread.
        print("INFO: Server shutdown complete.")
