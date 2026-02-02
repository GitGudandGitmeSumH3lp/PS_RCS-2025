"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/api/server.py
Description: Flask API server for the Parcel Robot System.
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
        """Initialize the API Server.

        Args:
            state: Shared robot state.
            hardware_manager: Hardware controller instance.
            template_folder: Path to HTML templates.
            static_folder: Path to static assets.
        """
        self.state = state
        self.hardware_manager = hardware_manager
        
        self.vision_manager = VisionManager()
        self.ocr_service = OCRService(max_workers=2)
        
        # Contract §6.1: Compute absolute captures directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
        self.captures_dir = os.path.join(project_root, "data", "captures")
        os.makedirs(self.captures_dir, exist_ok=True)
        
        self.template_folder = os.path.abspath(template_folder)
        self.static_folder = os.path.abspath(static_folder)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"[APIServer] Captures directory: {self.captures_dir}")

    def create_app(self) -> Flask:
        """Create and configure the Flask application.

        Returns:
            Configured Flask application instance.
        """
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
                app_version="4.0"
            )

        @app.route("/api/status", methods=["GET"])
        def get_status() -> Response:
            """Get system status including camera connection state."""
            camera_online = bool(self.vision_manager and self.vision_manager.stream)
            
            return jsonify({
                "mode": self.state.mode,
                "battery_voltage": self.state.battery_voltage,
                "last_error": self.state.last_error,
                "motor_connected": self.state.motor_connected,
                "lidar_connected": self.state.lidar_connected,
                "camera_connected": camera_online,
                "timestamp": datetime.now().isoformat()
            })

        @app.route("/api/motor/control", methods=["POST"])
        def control_motor() -> Response:
            """Control motor with speed and direction commands."""
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400

            data = request.get_json()
            if not data or "command" not in data:
                return jsonify({"error": "Missing 'command' field"}), 400

            command = data.get("command")
            speed = data.get("speed", 150)

            try:
                success = self.hardware_manager.send_motor_command(command, speed)
                if success:
                    return jsonify({
                        "success": True,
                        "message": f"Motor command '{command}' sent"
                    })
                return jsonify({"error": "Motor hardware unavailable"}), 503
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/api/lidar/scan", methods=["GET"])
        def get_lidar_scan() -> Response:
            """Get LIDAR scan data."""
            scan_data = self.state.get_lidar_snapshot()
            return jsonify(scan_data)

        @app.route("/api/vision/stream")
        def vision_stream() -> Any:
            """Stream MJPEG video feed."""
            if self.vision_manager.stream is None:
                return jsonify({
                    "error": "Camera offline",
                    "message": "Vision system not initialized"
                }), 503

            def generate() -> Generator[bytes, None, None]:
                try:
                    self.logger.info('[API] Vision stream started')
                    for frame in self.vision_manager.generate_mjpeg(quality=40):
                        yield frame
                except Exception as e:
                    self.logger.error(f'[API] Stream error: {e}')
                finally:
                    self.logger.info('[API] Vision stream stopped')

            return Response(
                generate(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

        @app.route("/api/vision/scan", methods=['POST'])
        def trigger_scan() -> Response:
            """Trigger OCR scan on current camera frame."""
            frame = self.vision_manager.get_frame()
            if frame is None:
                return jsonify({'error': 'No frame available'}), 503

            try:
                future = self.ocr_service.process_scan(frame)

                def update_state(fut: Any) -> None:
                    try:
                        result = fut.result()
                        self.state.update_scan_result(result)
                    except Exception as e:
                        self.logger.error(f"OCR callback error: {e}")

                future.add_done_callback(update_state)

                return jsonify({
                    'success': True,
                    'scan_id': id(future),
                    'status': 'processing'
                }), 202
            except RuntimeError:
                return jsonify({'error': 'OCR service unavailable'}), 500

        @app.route("/api/vision/last-scan")
        def get_last_scan() -> Response:
            """Get the most recent scan results."""
            return jsonify(self.state.vision.last_scan)

        @app.route("/api/vision/results/<scan_id>")
        def get_scan_results(scan_id: str) -> Response:
            """Get scan results by ID."""
            scan_data = self.state.vision.last_scan
            if scan_data and scan_data.get('scan_id') == int(scan_id):
                return jsonify({
                    'status': 'completed',
                    'data': scan_data
                })
            return jsonify({'status': 'processing'})

        @app.route("/api/vision/capture", methods=['POST'])
        def capture_photo() -> Response:
            """Save high-resolution frame to disk."""
            # Contract §6.2: Use absolute path in capture endpoint
            frame = self.vision_manager.get_frame()
            if frame is None:
                return jsonify({'error': 'No frame available'}), 503
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            filepath = os.path.join(self.captures_dir, filename)  # ABSOLUTE PATH
            
            try:
                cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                self.logger.info(f"[APIServer] Saved capture: {filepath}")
                self._cleanup_old_captures()
                
                return jsonify({
                    'success': True,
                    'filename': filename,
                    'download_url': f'/captures/{filename}',
                    'resolution': f"{frame.shape[1]}x{frame.shape[0]}",
                    'timestamp': timestamp
                }), 200
            except Exception as e:
                self.logger.error(f"[APIServer] Capture failed: {e}")
                return jsonify({'error': str(e)}), 500

        # Contract §6.3: Updated serve_capture with absolute path and validation
        @app.route('/captures/<filename>')
        def serve_capture(filename: str) -> Any:
            """Serve captured image files."""
            safe_filename = os.path.basename(filename)
            
            if not safe_filename.endswith(('.jpg', '.jpeg')):
                self.logger.warning(f"[APIServer] Invalid file type: {safe_filename}")
                return jsonify({'error': 'Invalid file type'}), 400
            
            filepath = os.path.join(self.captures_dir, safe_filename)
            
            if not os.path.exists(filepath):
                self.logger.warning(f"[APIServer] File not found: {filepath}")
                return jsonify({'error': 'File not found'}), 404
            
            return send_from_directory(self.captures_dir, safe_filename)
            
        @app.route("/api/ocr/scan-image", methods=['POST'])
        def scan_uploaded_image() -> Response:
            """Process OCR on uploaded or pasted image."""
            if 'image' not in request.files and 'image_data' not in request.json:
                return jsonify({'error': 'No image provided'}), 400
            
            try:
                if 'image' in request.files:
                    file = request.files['image']
                    nparr = np.frombuffer(file.read(), np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                else:
                    img_data = base64.b64decode(request.json['image_data'])
                    nparr = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                future = self.ocr_service.process_scan(frame)
                
                def update_state(fut: Any) -> None:
                    try:
                        result = fut.result()
                        self.state.update_scan_result(result)
                    except Exception as e:
                        self.logger.error(f"OCR callback error: {e}")

                future.add_done_callback(update_state)
                
                return jsonify({'status': 'processing'}), 202
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @app.errorhandler(404)
        def not_found(error: Any) -> Response:
            """Handle 404 errors."""
            return jsonify({"error": "Resource not found"}), 404

        @app.errorhandler(500)
        def internal_error(error: Any) -> Response:
            """Handle 500 errors."""
            return jsonify({"error": "Internal server error"}), 500

        return app

    # Contract §6.4: Updated _cleanup_old_captures to use instance variable
    def _cleanup_old_captures(self, max_files: int = 50) -> None:
        """Keep only the N most recent captures."""
        try:
            if not os.path.exists(self.captures_dir):
                return
            
            files = [
                os.path.join(self.captures_dir, f) 
                for f in os.listdir(self.captures_dir) 
                if f.endswith(('.jpg', '.jpeg'))
            ]
            
            if len(files) > max_files:
                # Sort by modification time (oldest first)
                files.sort(key=os.path.getmtime)
                to_delete = files[:len(files) - max_files]
                for f in to_delete:
                    os.remove(f)
                    self.logger.debug(f"[APIServer] Deleted old capture: {f}")
        except Exception as e:
            self.logger.error(f"[APIServer] Cleanup failed: {e}")

    def run(self, host: str, port: int, debug: bool = False) -> None:
        """Start the API server.

        Args:
            host: Host address.
            port: Port number.
            debug: Enable debug mode.
        """
        if self.vision_manager.start_capture():
            self.state.update_vision_status(True, self.vision_manager.camera_index)
            self.logger.info(f"Camera initialized at index {self.vision_manager.camera_index}")
        else:
            self.logger.warning("No camera detected during startup")

        app = self.create_app()
        app.run(host=host, port=port, debug=debug, threaded=True)

    def stop(self) -> None:
        """Stop server services."""
        self.logger.info("Stopping APIServer services...")
        self.vision_manager.stop_capture()
        self.ocr_service.shutdown(wait=True)