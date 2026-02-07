"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/api/server.py
Description: Flask API server for the Parcel Robot System with OCR Scanner Enhancement.
"""
import logging
import os
import base64
from typing import Any, Dict, List, Optional, Generator
from datetime import datetime
import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from src.core.state import RobotState
from src.services.hardware_manager import HardwareManager
from src.services.ocr_service import OCRService
from src.services.vision_manager import VisionManager

class APIServer:
    """Main API Server class handling all HTTP endpoints."""
    
    def __init__(
        self,
        state: RobotState,
        hardware_manager: HardwareManager,
        template_folder: str = "frontend/templates",
        static_folder: str = "frontend/static"
    ) -> None:
        """Initialize the API Server with absolute path resolution."""
        self.state = state
        self.hardware_manager = hardware_manager
        self.vision_manager = VisionManager()
        self.ocr_service = OCRService(max_workers=2)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
        self.captures_dir = os.path.join(project_root, "data", "captures")
        os.makedirs(self.captures_dir, exist_ok=True)
        
        self.template_folder = os.path.abspath(template_folder)
        self.static_folder = os.path.abspath(static_folder)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"[APIServer] Captures directory: {self.captures_dir}")

    def _validate_ocr_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure OCR result contains required fields with correct types.
        
        Args:
            result: Raw OCR service output.
        
        Returns:
            Dictionary with normalized snake_case fields.
        """
        required_fields = ['tracking_id', 'order_id', 'rts_code', 'district', 'confidence', 'timestamp', 'scan_id']
        normalized = {}
        
        field_mappings = {
            'tracking_id': 'trackingId',
            'order_id': 'orderId',
            'rts_code': 'rtsCode'
        }
        
        for field in required_fields:
            camel_case = field_mappings.get(field)
            value = result.get(field)
            if value is None and camel_case:
                value = result.get(camel_case)
            normalized[field] = value

        try:
            conf = normalized.get('confidence')
            normalized['confidence'] = max(0.0, min(1.0, float(conf))) if conf is not None else 0.0
        except (ValueError, TypeError):
            normalized['confidence'] = 0.0
            
        if not isinstance(normalized.get('timestamp'), str):
            normalized['timestamp'] = datetime.now().isoformat()
            
        return normalized

    def create_app(self) -> Flask:
        """Create and configure the Flask application."""
        app = Flask(
            __name__,
            template_folder=self.template_folder,
            static_folder=self.static_folder
        )

        @app.route("/")
        def index() -> str:
            """Serve the main dashboard page."""
            initial_status = self.hardware_manager.get_status()
            return render_template(
                "service_dashboard.html",
                initial_status=initial_status,
                app_version="4.2"
            )

        @app.route("/api/status", methods=["GET"])
        def get_status() -> Response:
            """Get system status with defensive error handling."""
            try:
                camera_online = False
                if hasattr(self, 'vision_manager') and self.vision_manager:
                    camera_online = bool(self.vision_manager.stream)
                
                mode = getattr(self.state, 'mode', 'unknown')
                battery = getattr(self.state, 'battery_voltage', 0.0)
                
                return jsonify({
                    "mode": mode,
                    "battery_voltage": battery,
                    "last_error": getattr(self.state, 'last_error', None),
                    "motor_connected": getattr(self.state, 'motor_connected', False),
                    "lidar_connected": getattr(self.state, 'lidar_connected', False),
                    "camera_connected": camera_online,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"[APIServer] Status endpoint error: {e}", exc_info=True)
                return jsonify({"error": "Status check failed"}), 500

        @app.route("/api/motor/control", methods=["POST"])
        def control_motor() -> Response:
            """Control motor with speed and direction commands."""
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400
            data = request.get_json()
            if not data or "command" not in data:
                return jsonify({"error": "Missing 'command' field"}), 400
            
            try:
                success = self.hardware_manager.send_motor_command(
                    data.get("command"), 
                    data.get("speed", 150)
                )
                if success:
                    return jsonify({"success": True})
                return jsonify({"error": "Motor hardware unavailable"}), 503
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/api/lidar/scan", methods=["GET"])
        def get_lidar_scan() -> Response:
            """Get LIDAR scan data."""
            return jsonify(self.state.get_lidar_snapshot())

        @app.route("/api/vision/stream")
        def vision_stream() -> Any:
            """Stream MJPEG video feed."""
            if self.vision_manager.stream is None:
                return jsonify({"error": "Camera offline"}), 503
            
            def generate() -> Generator[bytes, None, None]:
                try:
                    for frame in self.vision_manager.generate_mjpeg(quality=40):
                        yield frame
                except Exception as e:
                    self.logger.error(f'[API] Stream error: {e}')
            
            return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

        @app.route("/api/vision/scan", methods=['POST'])
        def trigger_scan() -> Response:
            """Trigger OCR scan on current camera frame."""
            frame = self.vision_manager.get_frame()
            if frame is None:
                return jsonify({'error': 'No frame available'}), 503
            
            try:
                future = self.ocr_service.process_scan(frame)
                scan_id = id(future)
                
                def update_state(fut: Any) -> None:
                    try:
                        result = fut.result()
                        result['scan_id'] = scan_id
                        result = self._validate_ocr_result(result)
                        self.state.update_scan_result(result)
                        self.logger.info(f"[OCR] Completed: {result.get('tracking_id', 'N/A')}")
                    except Exception as e:
                        self.logger.error(f"[APIServer] OCR callback error: {e}")
                    
                future.add_done_callback(update_state)
                return jsonify({'success': True, 'scan_id': scan_id, 'status': 'processing'}), 202
            except RuntimeError:
                return jsonify({'error': 'OCR service unavailable'}), 500

        @app.route("/api/vision/last-scan")
        def get_last_scan() -> Response:
            """Get the most recent scan results."""
            return jsonify(self.state.vision.last_scan)

        @app.route("/api/vision/results/<scan_id>")
        def get_scan_results(scan_id: str) -> Response:
            """Get scan results by ID."""
            try:
                scan_data = self.state.vision.last_scan
                if scan_data and str(scan_data.get('scan_id')) == str(scan_id):
                    return jsonify({'status': 'completed', 'data': scan_data})
                
                # Fallback if ID matching fails but data exists
                if scan_data and scan_data.get('timestamp'):
                     return jsonify({'status': 'completed', 'data': scan_data})

                return jsonify({'status': 'processing'})
            except Exception as e:
                self.logger.error(f"[APIServer] Results error: {e}")
                return jsonify({'status': 'error'}), 500

        @app.route("/api/vision/capture", methods=['POST'])
        def capture_photo() -> Response:
            """Save high-resolution frame to disk."""
            frame = self.vision_manager.get_frame()
            if frame is None:
                return jsonify({'error': 'No frame available'}), 503
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            filepath = os.path.join(self.captures_dir, filename)
            
            try:
                cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                self._cleanup_old_captures()
                return jsonify({
                    'success': True,
                    'download_url': f'/captures/{filename}',
                    'filename': filename
                }), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @app.route('/captures/<filename>')
        def serve_capture(filename: str) -> Any:
            """Serve captured image files."""
            return send_from_directory(self.captures_dir, filename)

        @app.route("/api/ocr/analyze", methods=['POST'])
        def analyze_image() -> Response:
            """Analyze image from upload or paste."""
            frame = None
            try:
                if 'image' in request.files:
                    file = request.files['image']
                    nparr = np.frombuffer(file.read(), np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                elif request.is_json and 'image_data' in request.json:
                    img_data = base64.b64decode(request.json['image_data'])
                    nparr = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is None:
                    return jsonify({'error': 'Invalid image'}), 400
                
                if frame.shape[0] != 480 or frame.shape[1] != 640:
                    frame = cv2.resize(frame, (640, 480))
                
                future = self.ocr_service.process_scan(frame)
                scan_id = id(future)
                
                def update_state(fut: Any) -> None:
                    try:
                        result = fut.result()
                        result['scan_id'] = scan_id
                        result = self._validate_ocr_result(result)
                        self.state.update_scan_result(result)
                        self.logger.info(f"[OCR] Analyze complete: {result.get('tracking_id')}")
                    except Exception as e:
                        self.logger.error(f"[APIServer] Analyze callback error: {e}")
                
                future.add_done_callback(update_state)
                return jsonify({'success': True, 'scan_id': scan_id, 'status': 'processing'}), 202
                
            except Exception as e:
                self.logger.error(f"[APIServer] Analyze error: {e}")
                return jsonify({'error': 'Analysis failed'}), 500

        @app.errorhandler(404)
        def not_found(error: Any) -> Response:
            return jsonify({"error": "Resource not found"}), 404

        @app.errorhandler(500)
        def internal_error(error: Any) -> Response:
            return jsonify({"error": "Internal server error"}), 500
        
        return app

    def _cleanup_old_captures(self, max_files: int = 50) -> None:
        """Keep only the N most recent captures."""
        try:
            if not os.path.exists(self.captures_dir):
                return
            files = [os.path.join(self.captures_dir, f) for f in os.listdir(self.captures_dir)]
            if len(files) > max_files:
                files.sort(key=os.path.getmtime)
                for f in files[:len(files) - max_files]:
                    os.remove(f)
        except Exception as e:
            self.logger.error(f"[APIServer] Cleanup failed: {e}")

    def run(self, host: str, port: int, debug: bool = False) -> None:
        """Start the API server."""
        if self.vision_manager.start_capture():
            self.state.update_vision_status(True, self.vision_manager.camera_index)
        app = self.create_app()
        app.run(host=host, port=port, debug=debug, threaded=True)

    def stop(self) -> None:
        """Stop server services."""
        self.vision_manager.stop_capture()
        self.ocr_service.shutdown(wait=True)