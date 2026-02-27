# src/api/server.py
"""
PS_RCS_PROJECT - API Server
Flask API server for the Parcel Robot System with OCR Scanner Enhancement.
Refactored for modularity and compliance.
"""

import logging
import os
import base64
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Generator, Tuple
from src.services import order_lookup
order_lookup.init_ground_truth('data/dictionaries/ground_truth.json')

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, render_template_string

from src.core.state import RobotState
from src.services.hardware_manager import HardwareManager
from src.services.vision_manager import VisionManager

# --- Module-level logger for import diagnostics ---
logger = logging.getLogger(__name__)

try:
    from src.services.ocr_processor import FlashExpressOCR
    from src.services.receipt_database import ReceiptDatabase
except ImportError as e:
    logger.error(f"Failed to import ReceiptDatabase or FlashExpressOCR: {e}")
    FlashExpressOCR = None  # type: ignore
    ReceiptDatabase = None  # type: ignore

# --- Enable console logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

class APIServer:
    """Main API Server class handling all HTTP endpoints."""
    
    def __init__(
        self,
        state: RobotState,
        hardware_manager: HardwareManager,
        template_folder: str = "frontend/templates",
        static_folder: str = "frontend/static"
    ) -> None:
        """Initialize server components and storage."""
        self.state = state
        self.hardware_manager = hardware_manager
        self.vision_manager = VisionManager()
        self.logger = logging.getLogger(__name__)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.captures_dir = os.path.join(script_dir, "..", "..", "data", "captures")
        os.makedirs(self.captures_dir, exist_ok=True)
        
        self.template_folder = os.path.abspath(template_folder)
        self.static_folder = os.path.abspath(static_folder)

        self.ocr_processor: Optional[FlashExpressOCR] = None
        self.receipt_db: Optional[ReceiptDatabase] = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="OCR_Worker")

        self._init_services()
        self._test_database()  # NEW: quick DB connectivity check
        
        # Start background threads
        self._start_background_tasks()

    def _init_services(self) -> None:
        """Initialize optional services safely."""
        if FlashExpressOCR:
            try:
                # Enable correction layer using the ground truth dictionary
                # Path relative to project root (where server runs)
                dict_path = os.path.join(os.path.dirname(__file__), '../../data/dictionaries/ground_truth_parcel_gen.json')
                
                self.ocr_processor = FlashExpressOCR(
                    use_paddle_fallback=False,
                    enable_correction=True,
                    correction_dict_path=dict_path,
                    debug_align=True 
                )
                self.logger.info("FlashExpressOCR initialized with correction layer (Tesseract only).")
            except Exception as e:
                self.logger.error(f"Failed to init OCR: {e}")

        if ReceiptDatabase:
            try:
                self.receipt_db = ReceiptDatabase()
                self.logger.info("ReceiptDatabase connected.")
            except Exception as e:
                self.logger.error(f"Failed to init Database: {e}")

    def _test_database(self) -> None:
        """Test database write/read and log result."""
        if not self.receipt_db:
            self.logger.warning("Database not available – OCR results will not persist.")
            return
        try:
            test_id = 999999
            # Use a valid timestamp for the test
            from datetime import datetime
            test_timestamp = datetime.now().isoformat()
            
            self.receipt_db.store_scan(
                scan_id=test_id,
                fields={'tracking_id': 'TEST', 'timestamp': test_timestamp},
                raw_text='test',
                confidence=0.5,
                engine='tesseract'
            )
            retrieved = self.receipt_db.get_scan(test_id)
            if retrieved and retrieved.get('scan_id') == test_id:
                self.logger.info("Database test PASSED – read/write OK.")
            else:
                self.logger.error("Database test FAILED – read after write failed.")
        except ValueError as ve:
            # Catch the specific timestamp validation error
            if "timestamp" in str(ve):
                self.logger.error(f"Database test EXCEPTION: {ve}")
                self.logger.warning("Database contains rows with missing timestamps. Run 'python scripts/clean_db_timestamps.py' to fix.")
            else:
                self.logger.error(f"Database test EXCEPTION: {ve}")
        except Exception as e:
            self.logger.error(f"Database test EXCEPTION: {e}")
            self.logger.warning("Database may contain corrupted data. Consider running 'python scripts/clean_db_timestamps.py'.")

    def _start_background_tasks(self) -> None:
        """Start background tasks such as LiDAR streaming."""
        # Note: In HardwareManager we already start a thread to update state.
        # This thread here is for any server-side specific logic, e.g., socketio emitting (future use)
        # or explicit callbacks if not handled by HardwareManager.
        # Based on integration notes:
        stream_thread = threading.Thread(target=self._lidar_stream_task, daemon=True)
        stream_thread.start()
        self.logger.info("Background LiDAR stream task started.")

    def _lidar_stream_task(self) -> None:
        """Background task to handle LiDAR data streaming/callbacks."""
        while True:
            # Check if lidar exists and has status
            if self.hardware_manager.lidar:
                try:
                    status = self.hardware_manager.lidar.get_status()
                    if status.get('scanning', False):
                        # Access callback if it exists (hook for Socket.IO later)
                        # For now, we rely on HardwareManager updating RobotState which endpoints read
                        if hasattr(self.hardware_manager.lidar, '_callback') and self.hardware_manager.lidar._callback:
                            data = self.hardware_manager.lidar.get_latest_scan()
                            try:
                                self.hardware_manager.lidar._callback(data)
                            except Exception as e:
                                self.logger.error(f"LiDAR callback raised: {e}")
                except Exception as e:
                    self.logger.error(f"Error in lidar stream task: {e}")
            time.sleep(0.05)  # 20 Hz

    def create_app(self) -> Flask:
        """Create and configure the Flask application."""
        app = Flask(
            __name__,
            template_folder=self.template_folder,
            static_folder=self.static_folder
        )
        self._register_routes(app)
        self._register_error_handlers(app)
        self._register_teardown(app)
        return app

    def _register_teardown(self, app: Flask) -> None:
        @app.teardown_appcontext
        def remove_session(exception=None):
            try:
                from src.database.core import SessionLocal
                if SessionLocal is not None:          # <-- ADD THIS CHECK
                    SessionLocal.remove()
            except ImportError:
                pass
            except Exception as e:
                self.logger.warning(f"Session cleanup failed: {e}")

    def _register_routes(self, app: Flask) -> None:
        """Register all API route handlers."""
        app.add_url_rule("/", view_func=self._handle_index)
        
        # Status & Hardware
        app.add_url_rule("/api/status", view_func=self._handle_status)
        app.add_url_rule("/api/motor/control", methods=["POST"], view_func=self._handle_motor)
        app.add_url_rule("/api/lidar/scan", view_func=self._handle_lidar)
        # NEW LiDAR routes
        app.add_url_rule("/api/lidar/status", methods=['GET'], view_func=self._handle_lidar_status)
        app.add_url_rule("/api/lidar/start", methods=['POST'], view_func=self._handle_lidar_start)
        app.add_url_rule("/api/lidar/stop", methods=['POST'], view_func=self._handle_lidar_stop)
        
        # Vision & OCR
        app.add_url_rule("/api/vision/stream", view_func=self._handle_stream)
        app.add_url_rule("/api/vision/scan", methods=['POST'], view_func=self._handle_scan)
        app.add_url_rule("/api/vision/last-scan", view_func=self._handle_last_scan)
        app.add_url_rule("/api/vision/results/<int:scan_id>", view_func=self._handle_results)
        app.add_url_rule("/api/vision/capture", methods=['POST'], view_func=self._handle_capture)
        app.add_url_rule("/api/camera/focus", methods=['POST'], view_func=self._handle_set_focus)
        app.add_url_rule("/api/camera/focus-status", methods=['GET'], view_func=self._handle_focus_status)
        
        # Analysis & History
        app.add_url_rule("/captures/<filename>", view_func=self._handle_serve_file)
        app.add_url_rule("/api/ocr/analyze", methods=['POST'], view_func=self._handle_analyze)
        app.add_url_rule("/api/ocr/analyze_batch", methods=['POST'], view_func=self._handle_analyze_batch)
        app.add_url_rule("/api/ocr/scans", view_func=self._handle_history)
        
        # Tracking
        app.add_url_rule("/track/<string:tracking>", view_func=self._handle_tracking)

    def _register_error_handlers(self, app: Flask) -> None:
        """Register HTTP error handlers."""
        @app.errorhandler(404)
        def not_found(error: Any) -> Tuple[Response, int]:
            return jsonify({"error": "Resource not found"}), 404

        @app.errorhandler(500)
        def internal_error(error: Any) -> Tuple[Response, int]:
            return jsonify({"error": "Internal server error"}), 500

    # --- Route Handlers ---
    def _handle_index(self) -> str:
        """Serve dashboard."""
        status = self.hardware_manager.get_status()
        return render_template("service_dashboard.html", initial_status=status, app_version="4.2")

    def _handle_status(self) -> Tuple[Response, int]:
        """Get system status."""
        try:
            cam_online = bool(self.vision_manager.stream)
            mode = getattr(self.state, 'mode', 'unknown')
            # Check LiDAR connection status safely
            lidar_conn = False
            if self.hardware_manager.lidar:
                lidar_status = self.hardware_manager.lidar.get_status()
                lidar_conn = lidar_status.get('connected', False)

            return jsonify({
                "mode": mode,
                "battery_voltage": getattr(self.state, 'battery_voltage', 0.0),
                "camera_connected": cam_online,
                "lidar_connected": lidar_conn, # Added field
                "timestamp": datetime.now().isoformat()
            }), 200
        except Exception as e:
            self.logger.error(f"Status error: {e}")
            return jsonify({"error": "Status check failed"}), 500

    def _handle_motor(self) -> Tuple[Response, int]:
        """Handle motor control."""
        if not request.is_json:
            return jsonify({"error": "JSON required"}), 400
        data = request.get_json() or {}
        try:
            if self.hardware_manager.send_motor_command(data.get("command"), data.get("speed", 150)):
                return jsonify({"success": True}), 200
            return jsonify({"error": "Hardware unavailable"}), 503
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    def _handle_lidar(self) -> Response:
        """Get Lidar data snapshot from state."""
        return jsonify(self.state.get_lidar_snapshot())

    # --- New LiDAR Control Handlers ---
    def _handle_lidar_status(self) -> Tuple[Response, int]:
        if not self.hardware_manager.lidar:
            return jsonify({"error": "LiDAR not available"}), 503
        return jsonify(self.hardware_manager.lidar.get_status()), 200

    def _handle_lidar_start(self) -> Tuple[Response, int]:
        if not self.hardware_manager.lidar:
            return jsonify({"error": "LiDAR not available"}), 503
        success = self.hardware_manager.lidar.start_scanning()
        return jsonify({'success': success}), 200

    def _handle_lidar_stop(self) -> Tuple[Response, int]:
        if not self.hardware_manager.lidar:
            return jsonify({"error": "LiDAR not available"}), 503
        success = self.hardware_manager.lidar.stop_scanning()
        return jsonify({'success': success}), 200

    def _handle_stream(self) -> Any:
        """Stream MJPEG."""
        if self.vision_manager.stream is None:
            return jsonify({"error": "Camera offline"}), 503
        
        def generate() -> Generator[bytes, None, None]:
            for frame in self.vision_manager.generate_mjpeg(quality=40):
                yield frame
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    def _handle_scan(self) -> Tuple[Response, int]:
        """Trigger OCR scan."""
        if not self.ocr_processor:
            return jsonify({'error': 'OCR engine unavailable'}), 503
        frame = self.vision_manager.get_frame()
        if frame is None:
            return jsonify({'error': 'No frame'}), 503
        
        scan_id = self._generate_scan_id()
        future = self.executor.submit(self._run_ocr_task, frame, scan_id)
        future.add_done_callback(self._on_ocr_complete)
        
        return jsonify({'success': True, 'scan_id': scan_id, 'status': 'processing'}), 202

    def _handle_last_scan(self) -> Response:
        return jsonify(self.state.vision.last_scan)

    def _handle_results(self, scan_id: int) -> Tuple[Response, int]:
        """Get scan results."""
        # 1. Check memory (state)
        mem_scan = self.state.vision.last_scan
        if mem_scan and str(mem_scan.get('scan_id')) == str(scan_id):
            self.logger.info(f"Results served from memory for scan {scan_id}")
            return jsonify({'status': 'completed', 'data': mem_scan}), 200
        
        # 2. Check database
        if self.receipt_db:
            try:
                db_scan = self.receipt_db.get_scan(scan_id)
                if db_scan:
                    self.logger.info(f"Results served from database for scan {scan_id}")
                    return jsonify({'status': 'completed', 'data': db_scan}), 200
            except Exception as e:
                self.logger.error(f"Database error in get_scan({scan_id}): {e}")
        
        self.logger.warning(f"Scan {scan_id} not found in memory or DB")
        return jsonify({'status': 'processing/not_found'}), 404

    def _handle_capture(self) -> Tuple[Response, int]:
        """Capture photo."""
        frame = self.vision_manager.get_frame()
        if frame is None:
            return jsonify({'error': 'No frame'}), 503
        
        fname = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        path = os.path.join(self.captures_dir, fname)
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        self._cleanup_captures()
        
        return jsonify({'success': True, 'download_url': f'/captures/{fname}'}), 200

    def _handle_set_focus(self) -> Tuple[Response, int]:
        """Adjust lens position for live manual focus tuning.

        Accepts JSON: { "lens_position": 3.0 }

        Valid range: 0.0 (infinity) to 10.0 (~10 cm).
        Distance: distance_cm ~ 100 / lens_position

        Common values:
            1.5 -> ~67 cm,  2.0 -> ~50 cm,  2.5 -> ~40 cm
            3.0 -> ~33 cm,  3.5 -> ~29 cm,  4.0 -> ~25 cm
        """
        data = request.get_json(silent=True) or {}
        raw = data.get('lens_position')

        if raw is None:
            return jsonify({"success": False, "error": "Missing 'lens_position' in request body"}), 400

        try:
            lens_position = float(raw)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "'lens_position' must be a number"}), 400

        try:
            ok = self.vision_manager.set_lens_position(lens_position)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        if not ok:
            return jsonify({"success": False, "error": "Camera not available or not a CSI camera"}), 503

        distance_cm = round(100 / lens_position) if lens_position > 0 else None
        self.logger.info(f"Focus set via API: LensPosition={lens_position} (~{distance_cm} cm)")
        return jsonify({
            "success": True,
            "lens_position": lens_position,
            "distance_cm": distance_cm,
        }), 200

    def _handle_focus_status(self) -> Tuple[Response, int]:
        """Return live FocusFoM and LensPosition metadata from the CSI camera.

        Used by the dashboard Focus Finder panel to display real-time sharpness
        so the operator can locate the fixed focal distance of a stuck VCM.

        Returns:
            JSON with keys: focus_fom (int), lens_position (float),
            exposure_time (int), status (str). 200 on success, 503 if
            camera or picam2 is unavailable.
        """
        provider = self.vision_manager.provider
        if provider is None or not hasattr(provider, 'picam2') or provider.picam2 is None:
            return jsonify({"status": "unavailable", "focus_fom": 0, "lens_position": 0.0}), 503

        try:
            meta = provider.picam2.capture_metadata()
            return jsonify({
                "status": "ok",
                "focus_fom": meta.get("FocusFoM", 0),
                "lens_position": meta.get("LensPosition", 0.0),
                "exposure_time": meta.get("ExposureTime", 0),
            }), 200
        except Exception as e:
            self.logger.error(f"focus-status error: {e}")
            return jsonify({"status": "error", "focus_fom": 0, "lens_position": 0.0}), 500

    def _handle_serve_file(self, filename: str) -> Any:
        return send_from_directory(self.captures_dir, filename)

    def _handle_analyze(self) -> Tuple[Response, int]:
        """Analyze uploaded image."""
        if not self.ocr_processor:
            return jsonify({'error': 'OCR engine unavailable'}), 503
        
        try:
            frame = self._decode_image_request(request)
            if frame is None:
                return jsonify({'error': 'Invalid image'}), 400
            
            scan_id = self._generate_scan_id()
            future = self.executor.submit(self._run_ocr_task, frame, scan_id)
            future.add_done_callback(self._on_ocr_complete)
            
            return jsonify({'success': True, 'scan_id': scan_id}), 202
        except Exception as e:
            self.logger.error(f"/api/ocr/analyze error: {e}")
            return jsonify({'error': str(e)}), 500

    def _handle_analyze_batch(self) -> Tuple[Response, int]:
            """
            Process multiple uploaded images in batch SEQUENTIALLY.
            Refactored to prevent Raspberry Pi RAM overflow.
            """
            # --- 1. Basic Validation ---
            if not self.ocr_processor:
                return jsonify({"error": "OCR engine unavailable"}), 503

            if 'images' not in request.files:
                return jsonify({"error": "No images part"}), 400

            files = request.files.getlist('images')
            if not files:
                return jsonify({"error": "No files selected"}), 400

            MAX_FILES = 10
            if len(files) > MAX_FILES:
                return jsonify({"error": f"Too many files. Max {MAX_FILES}"}), 400

            self.logger.info(f"Received batch request for {len(files)} files.")

            # --- 2. Sequential Processing Loop ---
            results = [None] * len(files)
            
            for idx, file in enumerate(files):
                if not file or not file.filename:
                    results[idx] = {"success": False, "error": "Invalid file"}
                    continue

                try:
                    self.logger.info(f"Processing batch file {idx + 1}/{len(files)}: {file.filename}...")
                    
                    # Read bytes and process immediately (No Threads!)
                    file_bytes = file.read()
                    result = self._process_single_image_bytes(file_bytes, idx)
                    results[idx] = result
                    
                except Exception as e:
                    self.logger.error(f"Error processing {file.filename}: {e}")
                    results[idx] = {"success": False, "error": str(e)}

            self.logger.info("Batch processing finished successfully.")
            return jsonify(results), 200

    def _process_single_image_bytes(self, image_bytes: bytes, idx: int) -> Dict[str, Any]:
            """
            Process a single image bytes with GRAYSCALE and RESIZING for maximum Pi speed.
            """
            try:
                # 1. Decode Image
                nparr = np.frombuffer(image_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is None:
                    return {"success": False, "error": "Invalid image format"}

                # --- OPTIMIZATION 1: GRAYSCALE CONVERSION ---
                # OCR engines work internally in B&W. Doing this here saves 
                # RAM and processing power immediately.
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # --- OPTIMIZATION 2: AGGRESSIVE RESIZING ---
                # Reduced from 1280 -> 1000. 
                # This is the "Sweet Spot" between speed and accuracy for labels.
                height, width = frame.shape[:2]
                max_dim = 1000 
                if width > max_dim or height > max_dim:
                    scale = max_dim / max(width, height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                
                # ----------------------------------------------

                # 2. Run OCR
                scan_id = self._generate_scan_id()
                result = self.ocr_processor.process_frame(frame, scan_id=scan_id)

                # 3. Save to DB if successful
                if result.get('success') and self.receipt_db:
                    try:
                        self.receipt_db.store_scan(
                            scan_id=result['scan_id'],
                            fields=result['fields'],
                            raw_text=result.get('raw_text', ''),
                            confidence=result['fields'].get('confidence', 0.0),
                            engine=result.get('engine', 'unknown')
                        )
                    except Exception as e:
                        self.logger.error(f"DB save failed: {e}")

                return result
            except Exception as e:
                self.logger.error(f"Single image failure: {e}")
                return {"success": False, "error": str(e)}

    def _handle_history(self) -> Tuple[Response, int]:
        """Get scan history."""
        if not self.receipt_db:
            return jsonify({'error': 'Database unavailable'}), 503
        try:
            limit = min(1000, max(1, request.args.get('limit', 50, type=int)))
            scans = self.receipt_db.get_recent_scans(limit)
            return jsonify({'success': True, 'scans': scans}), 200
        except Exception as e:
            self.logger.error(f"History error: {e}")
            return jsonify({'error': str(e)}), 500

    def _handle_tracking(self, tracking: str) -> Any:
        """Look up a receipt by tracking number and display its details."""
        if not self.receipt_db:
            return "Database unavailable", 503

        scan = self.receipt_db.get_scan_by_tracking(tracking)
        if not scan:
            return f"Tracking number {tracking} not found", 404

        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Receipt Details</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto; background: #f0f0f0; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .field { margin: 10px 0; border-bottom: 1px solid #eee; padding-bottom: 5px; }
                .label { font-weight: bold; display: inline-block; width: 120px; color: #555; }
                h1 { margin-top: 0; color: #333; }
                a { display: inline-block; margin-top: 20px; color: #0066cc; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Receipt Details</h1>
                <div class="field"><span class="label">Tracking:</span> {{ scan.tracking_id }}</div>
                <div class="field"><span class="label">Order ID:</span> {{ scan.order_id }}</div>
                <div class="field"><span class="label">RTS Code:</span> {{ scan.rts_code }}</div>
                <div class="field"><span class="label">Buyer:</span> {{ scan.buyer_name }}</div>
                <div class="field"><span class="label">Address:</span> {{ scan.buyer_address }}</div>
                <div class="field"><span class="label">Weight:</span> {{ scan.weight_g }}g</div>
                <div class="field"><span class="label">Quantity:</span> {{ scan.quantity }}</div>
                <div class="field"><span class="label">Payment:</span> {{ scan.payment_type }}</div>
                <div class="field"><span class="label">Timestamp:</span> {{ scan.timestamp }}</div>
                <a href="/">Back to Dashboard</a>
            </div>
        </body>
        </html>
        """
        return render_template_string(html_template, tracking=tracking, scan=scan)

    # --- Helpers ---
    def _decode_image_request(self, req: request) -> Optional[np.ndarray]:
        """Decode image from request files or JSON."""
        if 'image' in req.files:
            return cv2.imdecode(np.frombuffer(req.files['image'].read(), np.uint8), 1)
        if req.is_json and 'image_data' in req.json:
            data = req.json['image_data'].split(',', 1)[-1]
            return cv2.imdecode(np.frombuffer(base64.b64decode(data), np.uint8), 1)
        return None

    def _generate_scan_id(self) -> int:
        return int(datetime.now().timestamp() * 1000000)

    def _run_ocr_task(self, frame: np.ndarray, scan_id: int) -> Dict[str, Any]:
        """Worker task."""
        if not self.ocr_processor:
            raise RuntimeError("OCR unavailable")
        
        result = self.ocr_processor.process_frame(frame, scan_id=scan_id)
        if result['success'] and self.receipt_db:
            try:
                self.receipt_db.store_scan(
                    scan_id=result['scan_id'],
                    fields=result['fields'],
                    raw_text=result.get('raw_text', ''),
                    confidence=result['fields'].get('confidence', 0.0),
                    engine=result.get('engine', 'unknown')
                )
                self.logger.info(f"Scan {result['scan_id']} saved to database.")
            except Exception as e:
                self.logger.error(f"DB save failed for scan {scan_id}: {e}")
        return result

    def _on_ocr_complete(self, future: Future) -> None:
        """Callback for OCR task completion."""
        try:
            result = future.result()
            if not result.get('success'):
                self.logger.warning(f"OCR task returned success=False")
                return
            
            # Convert fields to snake_case and inject scan_id
            fields = result.get('fields', {})
            fields_snake = {camel_to_snake(k): v for k, v in fields.items()}
            fields_snake['scan_id'] = result.get('scan_id')
            
            # Update state memory
            self.state.update_scan_result(fields_snake)
            self.logger.info(f"OCR Complete: {fields_snake.get('tracking_id')} (ID: {result.get('scan_id')})")
        except Exception as e:
            self.logger.error(f"OCR callback failed: {e}")

    def _cleanup_captures(self) -> None:
        """Limit captures folder size."""
        try:
            files = sorted(
                [os.path.join(self.captures_dir, f) for f in os.listdir(self.captures_dir)],
                key=os.path.getmtime
            )
            for f in files[:-50]:
                os.remove(f)
        except Exception:
            pass

    # ================== NEW AUTO‑DETECTION METHODS ==================

    def _on_auto_capture(self, image_path: str) -> None:
        """
        Callback invoked by VisionManager when auto‑detection captures a high‑res image.
        Submits the image to the OCR executor and handles result storage.
        """
        self.logger.info(f"Auto‑capture triggered: {image_path}")
        future = self.executor.submit(self._process_auto_capture, image_path)
        future.add_done_callback(self._on_ocr_complete)   # reuse existing callback

    def _process_auto_capture(self, image_path: str) -> Dict[str, Any]:
        """
        Load an image from disk and run OCR on it.
        Returns the OCR result dictionary (same format as _run_ocr_task).
        """
        if not self.ocr_processor:
            self.logger.error("OCR processor not available for auto‑capture")
            return {"success": False, "error": "OCR unavailable"}

        try:
            # Read image using OpenCV
            frame = cv2.imread(image_path)
            if frame is None:
                raise ValueError(f"Could not read image: {image_path}")

            # Generate a scan ID and process
            scan_id = self._generate_scan_id()
            result = self.ocr_processor.process_frame(frame, scan_id=scan_id)

            # Store in database if successful (reuse logic from _run_ocr_task)
            if result.get('success') and self.receipt_db:
                try:
                    self.receipt_db.store_scan(
                        scan_id=result['scan_id'],
                        fields=result['fields'],
                        raw_text=result.get('raw_text', ''),
                        confidence=result['fields'].get('confidence', 0.0),
                        engine=result.get('engine', 'unknown')
                    )
                    self.logger.info(f"Auto‑capture scan {result['scan_id']} saved to DB.")
                except Exception as e:
                    self.logger.error(f"DB save failed for auto‑capture: {e}")

            return result

        except Exception as e:
            self.logger.error(f"Auto‑capture OCR failed: {e}")
            return {"success": False, "error": str(e)}

    # ================== RUN METHOD (UPDATED) ==================

    def run(self, host: str, port: int, debug: bool = False) -> None:
        """Start server and background tasks."""
        if self.vision_manager.start_capture():
            self.state.update_vision_status(True, self.vision_manager.camera_index)
            # Start auto‑detection with 1s interval, 3‑frame confirmation, and our callback
            self.vision_manager.start_auto_detection(
                interval=1.0,
                confirm_frames=3,
                detection_callback=self._on_auto_capture   # CORRECTED parameter name
            )
            self.logger.info("Auto‑detection started.")
        else:
            self.logger.error("Camera failed to start – auto‑detection not available.")

        app = self.create_app()
        app.run(host=host, port=port, debug=debug, threaded=True)

    def stop(self) -> None:
        """Stop server."""
        self.vision_manager.stop_capture()
        self.executor.shutdown(wait=False)