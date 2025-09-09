# app.py
from flask import Flask, render_template, jsonify, Response, request
# You will need to import libraries for:
# - Serial communication (pyserial)
# - HTTP requests (requests) if proxying the camera stream
# - Database access (sqlite3, psycopg2, mysql.connector, or an ORM like SQLAlchemy)
# Example imports (uncomment and install as needed):
# import serial
# import requests
# import sqlite3 # Or your chosen DB library

app = Flask(__name__)

# --- Configuration (consider moving to config.py later) ---
# CAMERA_STREAM_URL = "http://<ESP32_IP>/stream" # Replace with your ESP32-CAM stream URL
# SERIAL_PORT = '/dev/ttyUSB0' # Replace with your Arduino's serial port
# BAUD_RATE = 9600
# DATABASE_PATH = 'parcels.db' # Or your DB connection string

# --- Routes ---

@app.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('index.html')

# @app.route('/camera_stream')
# def camera_stream():
#     """
#     Proxy the MJPEG stream from the ESP32-CAM.
#     This is a basic example, might need adjustments for buffering/streaming.
#     """
#     try:
#         req = requests.get(CAMERA_STREAM_URL, stream=True, timeout=10)
#         return Response(req.iter_content(chunk_size=1024),
#                         content_type=req.headers['content-type'])
#     except requests.exceptions.RequestException as e:
#         app.logger.error(f"Error fetching camera stream: {e}")
#         return "Camera stream unavailable", 503

@app.route('/api/parcels')
def api_parcels():
    """API endpoint for parcel data (server-side DataTables)."""
    # --- DataTables Parameters ---
    draw = request.args.get('draw', 1, type=int)
    start = request.args.get('start', 0, type=int)
    length = request.args.get('length', 10, type=int)
    search_value = request.args.get('search[value]', '', type=str)

    # --- Database Interaction (Example with SQLite) ---
    # Replace this section with your actual database logic
    try:
        # conn = sqlite3.connect(DATABASE_PATH)
        # cursor = conn.cursor()

        # Base query
        query = "SELECT id, tracking_no, zone, status, time_processed FROM parcels"
        count_query = "SELECT COUNT(*) FROM parcels"
        params = []
        count_params = []

        # Add search filter if provided
        if search_value:
            search_filter = " WHERE tracking_no LIKE ? OR zone LIKE ?"
            query += search_filter
            count_query += search_filter
            like_term = f"%{search_value}%"
            params.extend([like_term, like_term])
            count_params.extend([like_term, like_term])

        # Add ordering (basic example, DataTables sends column index and direction)
        # You should parse request.args.get('order[0][column]') and request.args.get('order[0][dir]')
        # For simplicity, default sorting by ID desc is assumed in the frontend.
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([length, start])

        # Execute count query
        # cursor.execute(count_query, count_params)
        # records_total = cursor.fetchone()[0]
        # records_filtered = records_total # Simplified, adjust if filtering logic changes total count
        records_total = 100 # Placeholder
        records_filtered = 100 # Placeholder

        # Execute data query
        # cursor.execute(query, params)
        # rows = cursor.fetchall()
        # columns = [description[0] for description in cursor.description]
        # data = [dict(zip(columns, row)) for row in rows]

        # conn.close()

        # --- Mock Data for Testing ---
        # Remove this mock section and use the DB code above.
        mock_data = []
        for i in range(start + 1, start + length + 1):
             mock_data.append({
                 "id": i,
                 "tracking_no": f"TN{i:05d}XYZ",
                 "zone": f"Zone {chr(65 + (i % 5))}", # A, B, C, D, E
                 "status": "Processed" if i % 3 == 0 else ("Pending" if i % 3 == 1 else "Error"),
                 "time_processed": f"2024-05-{(i % 28) + 1:02d} 10:{i % 60:02d}:{(i*2) % 60:02d}"
             })
        data = mock_data
        # --- End Mock Data ---

        return jsonify({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': data
        })
    except Exception as e:
        app.logger.error(f"Error fetching parcel data: {e}")
        return jsonify({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': 'Database error'
        }), 500

@app.route('/control/<cmd>')
def control(cmd):
    """API endpoint to receive control commands."""
    print(f"Received command: {cmd}") # Replace with actual logic
    # --- Arduino Communication ---
    # try:
    #     ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    #     ser.write(cmd.encode() + b'\n') # Send command, ensure Arduino expects newline
    #     ser.close()
    #     success = True
    #     message = f"Command '{cmd}' sent successfully."
    # except serial.SerialException as e:
    #     app.logger.error(f"Serial communication error: {e}")
    #     success = False
    #     message = f"Failed to send command '{cmd}': Serial error."
    # except Exception as e:
    #     app.logger.error(f"Unexpected error sending command: {e}")
    #     success = False
    #     message = f"Failed to send command '{cmd}': Unexpected error."

    # Mock response for now
    success = True
    message = f"Command '{cmd}' processed (mock)."

    return jsonify({'success': success, 'message': message})

# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) # Adjust host/port as needed