"""
PS_RCS_PROJECT - API Server
Flask API server for the Parcel Robot System with OCR Scanner Enhancement.
Refactored for modularity and compliance.
"""

import logging
import os
import base64
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import Any, Dict, List, Optional, Generator, Tuple

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from src.core.state import RobotState
from src.services.hardware_manager import HardwareManager
from src.services.vision_manager import VisionManager

try:
    from src.services.ocr_processor import FlashExpressOCR
    from src.services.receipt_database import ReceiptDatabase
except ImportError:
    FlashExpressOCR = None  # type: ignore
    ReceiptDatabase = None  # type: ignore


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

    def _init_services(self) -> None:
        """Initialize optional services safely."""
        if FlashExpressOCR:
            try:
                self.ocr_processor = FlashExpressOCR(use_paddle_fallback=True)
                self.logger.info("FlashExpressOCR initialized.")
            except Exception as e:
                self.logger.error(f"Failed to init OCR: {e}")

        if ReceiptDatabase:
            try:
                self.receipt_db = ReceiptDatabase()
                self.logger.info("ReceiptDatabase connected.")
            except Exception as e:
                self.logger.error(f"Failed to init Database: {e}")

    def create_app(self) -> Flask:
        """Create and configure the Flask application."""
        app = Flask(
            __name__,
            template_folder=self.template_folder,
            static_folder=self.static_folder
        )
        self._register_routes(app)
        self._register_error_handlers(app)
        self._register_teardown(app)  # NEW: Clean thread‑local sessions
        return app

    def _register_teardown(self, app: Flask) -> None:
        """Register Flask teardown handler to remove thread‑local DB sessions."""
        @app.teardown_appcontext
        def remove_session(exception=None):
            try:
                from src.database.core import SessionLocal
                SessionLocal.remove()
            except ImportError:
                pass  # Database not yet initialised – safe to ignore
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
        
        # Analysis & History
        app.add_url_rule("/captures/<filename>", view_func=self._handle_serve_file)
        app.add_url_rule("/api/ocr/analyze", methods=['POST'], view_func=self._handle_analyze)
        app.add_url_rule("/api/ocr/scans", view_func=self._handle_history)

    def _register_error_handlers(self, app: Flask) -> None:
        """Register HTTP error handlers."""
        @app.errorhandler(404)
        def not_found(error: Any) -> Tuple[Response, int]:
            return jsonify({"error": "Resource not found"}), 404

        @app.errorhandler(500)
        def internal_error(error: Any) -> Tuple[Response, int]:
            return jsonify({"error": "Internal server error"}), 500

    # --- Route Handlers (unchanged) ---
    def _handle_index(self) -> str:
        """Serve dashboard."""
        status = self.hardware_manager.get_status()
        return render_template("service_dashboard.html", initial_status=status, app_version="4.2")

    def _handle_status(self) -> Tuple[Response, int]:
        """Get system status."""
        try:
            cam_online = bool(self.vision_manager.stream)
            mode = getattr(self.state, 'mode', 'unknown')
            return jsonify({
                "mode": mode,
                "battery_voltage": getattr(self.state, 'battery_voltage', 0.0),
                "camera_connected": cam_online,
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
        """Get Lidar data."""
        return jsonify(self.state.get_lidar_snapshot())

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
        mem_scan = self.state.vision.last_scan
        if mem_scan and str(mem_scan.get('scan_id')) == str(scan_id):
            return jsonify({'status': 'completed', 'data': mem_scan}), 200
        if self.receipt_db:
            db_scan = self.receipt_db.get_scan(scan_id)
            if db_scan:
                return jsonify({'status': 'completed', 'data': db_scan}), 200
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
            return jsonify({'error': str(e)}), 500

    def _handle_history(self) -> Tuple[Response, int]:
        """Get scan history."""
        if not self.receipt_db:
            return jsonify({'error': 'Database unavailable'}), 503
        try:
            limit = min(1000, max(1, request.args.get('limit', 50, type=int)))
            scans = self.receipt_db.get_recent_scans(limit)
            return jsonify({'success': True, 'scans': scans}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # --- Helpers (unchanged) ---
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
                    scan_id=result['scan_id'], fields=result['fields'],
                    raw_text=result.get('raw_text', ''),
                    confidence=result['fields'].get('confidence', 0.0),
                    engine=result.get('engine', 'unknown')
                )
            except Exception as e:
                self.logger.error(f"DB save failed: {e}")
        return result

    def _on_ocr_complete(self, future: Future) -> None:
        """Callback for OCR task completion."""
        try:
            result = future.result()
            self.state.update_scan_result(result['fields'])
            self.logger.info(f"OCR Complete: {result['fields'].get('tracking_id')}")
        except Exception as e:
            self.logger.error(f"OCR Task failed: {e}")

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

    def run(self, host: str, port: int, debug: bool = False) -> None:
        """Start server."""
        if self.vision_manager.start_capture():
            self.state.update_vision_status(True, self.vision_manager.camera_index)
        app = self.create_app()
        app.run(host=host, port=port, debug=debug, threaded=True)

    def stop(self) -> None:
        """Stop server."""
        self.vision_manager.stop_capture()
        self.executor.shutdown(wait=False)