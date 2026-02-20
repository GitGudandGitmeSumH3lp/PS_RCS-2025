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

try:
    from src.services.ocr_processor import FlashExpressOCR
    from src.services.receipt_database import ReceiptDatabase
except ImportError:
    FlashExpressOCR = None  # type: ignore
    ReceiptDatabase = None  # type:ignore

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
        self._test_database()

    def _init_services(self) -> None:
        """Initialize optional services safely."""
        if FlashExpressOCR:
            try:
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
            self.logger.warning("Database not available - OCR results will not persist.")
            return
        try:
            test_id = 999999
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
                self.logger.info("Database test PASSED - read/write OK.")
            else:
                self.logger.error("Database test FAILED - read after write failed.")
        except ValueError as ve:
            if "timestamp" in str(ve):
                self.logger.error(f"Database test EXCEPTION: {ve}")
                self.logger.warning("Database contains rows with missing timestamps. Run 'python scripts/clean_db_timestamps.py' to fix.")
            else:
                self.logger.error(f"Database test EXCEPTION: {ve}")
        except Exception as e:
            self.logger.error(f"Database test EXCEPTION: {e}")
            self.logger.warning("Database may contain corrupted data. Consider running 'python scripts/clean_db_timestamps.py'.")

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
        """Register Flask teardown handler to remove thread-local DB sessions."""
        @app.teardown_appcontext
        def remove_session(exception=None):
            try:
                from src.database.core import SessionLocal
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
        
        # Vision & OCR
        app.add_url_rule("/api/vision/stream", view_func=self._handle_stream)
        app.add_url_rule("/api/vision/scan", methods=['POST'], view_func=self._handle_scan)
        app.add_url_rule("/api/vision/last-scan", view_func=self._handle_last_scan)
        app.add_url_rule("/api/vision/results/<int:scan_id>", view_func=self._handle_results)
        app.add_url_rule("/api/vision/capture", methods=['POST'], view_func=self._handle_capture)
        app.add_url_rule("/api/vision/auto-detect", methods=["POST"], view_func=self._handle_auto_detect)
        app.add_url_rule("/api/vision/auto-captures/latest", view_func=self._handle_latest_auto_capture)
        
        # Analysis & History
        app.add_url_rule("/captures/<filename>", view_func=self._handle_serve_file)
        app.add_url_rule("/api/ocr/analyze", methods=['POST'], view_func=self._handle_analyze)
        app.add_url_rule("/api/ocr/analyze_batch", methods=['POST'], view_func=self._handle_analyze_batch)
        app.add_url_rule("/api/ocr/scans", view_func=self._handle_history)   # supports ?limit
        
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
            hw_status = self.hardware_manager.get_status()
            return jsonify({
                "mode": hw_status.get('mode', 'unknown'),
                "battery_voltage": hw_status.get('battery_voltage', 0.0),
                "camera_connected": cam_online,
                "motor_connected": hw_status.get('motor_connected', False),
                "lidar_connected": hw_status.get('lidar_connected', False),
                "timestamp": datetime.now().isoformat(),
                "auto_detect_enabled": getattr(self.vision_manager, '_detection_active', False)
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
        """Get Lidar data."""
        return jsonify(self.state.get_lidar_snapshot())

    def _handle_stream(self) -> Any:
        """Stream MJPEG with optional quality parameter."""
        if self.vision_manager.stream is None:
            return jsonify({"error": "Camera offline"}), 503
        
        try:
            quality = request.args.get('quality', 70, type=int)
            if not (1 <= quality <= 100):
                quality = 70
        except:
            quality = 70
        
        def generate() -> Generator[bytes, None, None]:
            for frame in self.vision_manager.generate_mjpeg(quality=quality):
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
        mem_scan = self.state.vision.last_scan
        if mem_scan and str(mem_scan.get('scan_id')) == str(scan_id):
            self.logger.info(f"Results served from memory for scan {scan_id}")
            return jsonify({'status': 'completed', 'data': mem_scan}), 200
        
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

    def _handle_auto_detect(self) -> Tuple[Response, int]:
        """
        POST /api/vision/auto-detect
        Enable or disable the auto‑detection loop.
        """
        if not request.is_json:
            return jsonify({"error": "JSON required"}), 400

        data = request.get_json() or {}
        if "enabled" not in data:
            return jsonify({"error": "Missing 'enabled' field"}), 400

        enabled = bool(data["enabled"])

        if enabled:
            # Extract optional parameters with defaults
            sensitivity = float(data.get("sensitivity", 0.08))
            interval = float(data.get("interval", 1.0))
            confirm_frames = int(data.get("confirm_frames", 3))

            try:
                self.vision_manager.start_auto_detection(
                    sensitivity=sensitivity,
                    interval=interval,
                    confirm_frames=confirm_frames,
                    detection_callback=self._process_auto_capture
                )
            except ValueError as e:
                return jsonify({"success": False, "error": str(e)}), 400
            except RuntimeError as e:
                return jsonify({"success": False, "error": str(e)}), 503
        else:
            self.vision_manager.stop_auto_detection()

        # Return current state
        state = self.vision_manager._detection_active
        return jsonify({
            "success": True,
            "auto_detect_enabled": state,
            "sensitivity": self.vision_manager._detection_sensitivity,
            "interval": self.vision_manager._detection_interval,
            "confirm_frames": self.vision_manager._detection_confirm_frames
        }), 200

    def _handle_latest_auto_capture(self) -> Tuple[Response, int]:
        """GET /api/vision/auto-captures/latest - returns the most recent auto‑captured filename."""
        try:
            filename = self.vision_manager.get_latest_auto_capture()
            if filename:
                return jsonify({"filename": filename}), 200
            return jsonify({"filename": None}), 200
        except Exception as e:
            self.logger.error(f"Error getting latest auto capture: {e}")
            return jsonify({"error": "Internal server error"}), 500

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

        results = [None] * len(files)
        
        for idx, file in enumerate(files):
            if not file or not file.filename:
                results[idx] = {"success": False, "error": "Invalid file"}
                continue

            try:
                self.logger.info(f"Processing batch file {idx + 1}/{len(files)}: {file.filename}...")
                file_bytes = file.read()
                result = self._process_single_image_bytes(file_bytes, idx)
                results[idx] = result
            except Exception as e:
                self.logger.error(f"Error processing {file.filename}: {e}")
                results[idx] = {"success": False, "error": str(e)}

        self.logger.info("Batch processing finished successfully.")
        return jsonify(results), 200

    def _process_single_image_bytes(self, image_bytes: bytes, idx: int) -> Dict[str, Any]:
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return {"success": False, "error": "Invalid image format"}

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            height, width = frame.shape[:2]
            max_dim = 1000 
            if width > max_dim or height > max_dim:
                scale = max_dim / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

            scan_id = self._generate_scan_id()
            result = self.ocr_processor.process_frame(frame, scan_id=scan_id)

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
            return {"success": False, "error": str(e)})

    def _handle_history(self) -> Tuple[Response, int]:
        """Get scan history."""
        if not self.receipt_db:
            return jsonify({'error': 'Database unavailable'}), 503
        try:
            # Accept ?limit parameter (default 50, max 1000)
            limit = request.args.get('limit', 50, type=int)
            limit = min(1000, max(1, limit))
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

    # --- Callback for auto‑captured images ---
    def _process_auto_capture(self, image_path: str) -> None:
        """
        Process an image that was automatically captured by VisionManager.
        Runs OCR on the file and stores the result in the database.
        """
        if not self.ocr_processor:
            self.logger.warning("OCR processor not available; auto‑capture image not analyzed.")
            return

        try:
            frame = cv2.imread(image_path)
            if frame is None:
                self.logger.error(f"Failed to read auto‑capture image: {image_path}")
                return

            result = self.ocr_processor.process_frame(frame, scan_id=None)

            if not result.get('success'):
                self.logger.warning(f"Auto‑capture OCR failed: {result.get('error', 'unknown')}")
                return

            if self.receipt_db:
                try:
                    self.receipt_db.store_scan(
                        scan_id=result['scan_id'],
                        fields=result['fields'],
                        raw_text=result.get('raw_text', ''),
                        confidence=result['fields'].get('confidence', 0.0),
                        engine=result.get('engine', 'unknown')
                    )
                    self.logger.info(f"Auto‑capture scan {result['scan_id']} saved to database.")
                except Exception as e:
                    self.logger.error(f"DB save failed for auto‑capture: {e}")

            # Update in‑memory last scan
            fields = result.get('fields', {})
            fields_snake = {camel_to_snake(k): v for k, v in fields.items()}
            fields_snake['scan_id'] = result.get('scan_id')
            self.state.update_scan_result(fields_snake)

        except Exception as e:
            self.logger.error(f"Auto‑capture processing failed: {e}")

    # --- Helpers ---
    def _decode_image_request(self, req: request) -> Optional[np.ndarray]:
        if 'image' in req.files:
            return cv2.imdecode(np.frombuffer(req.files['image'].read(), np.uint8), 1)
        if req.is_json and 'image_data' in req.json:
            data = req.json['image_data'].split(',', 1)[-1]
            return cv2.imdecode(np.frombuffer(base64.b64decode(data), np.uint8), 1)
        return None

    def _generate_scan_id(self) -> int:
        return int(datetime.now().timestamp() * 1000000)

    def _run_ocr_task(self, frame: np.ndarray, scan_id: int) -> Dict[str, Any]:
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
        try:
            result = future.result()
            if not result.get('success'):
                self.logger.warning(f"OCR task returned success=False")
                return
            
            fields = result.get('fields', {})
            fields_snake = {camel_to_snake(k): v for k, v in fields.items()}
            fields_snake['scan_id'] = result.get('scan_id')
            
            self.state.update_scan_result(fields_snake)
            self.logger.info(f"OCR Complete: {fields_snake.get('tracking_id')} (ID: {result.get('scan_id')})")
        except Exception as e:
            self.logger.error(f"OCR callback failed: {e}")

    def _cleanup_captures(self) -> None:
        try:
            files = sorted(
                [os.path.join(self.captures_dir, f) for f in os.listdir(self.captures_dir)],
                key=os.path.getmtime
            )
            for f in files[:-50]:
                os.remove(f)
        except Exception:
            pass

    def run(self, host: str, port: int, debug: bool = False) -> None:
        if self.vision_manager.start_capture():
            self.state.update_vision_status(True, self.vision_manager.camera_index)
        app = self.create_app()
        app.run(host=host, port=port, debug=debug, threaded=True)

    def stop(self) -> None:
        self.vision_manager.stop_capture()
        self.executor.shutdown(wait=False)