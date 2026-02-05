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
    def __init__(
        self,
        state: RobotState,
        hardware_manager: HardwareManager,
        template_folder: str = "frontend/templates",
        static_folder: str = "frontend/static"
    ) -> None:
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

    def create_app(self) -> Flask:
        app = Flask(
            __name__,
            template_folder=self.template_folder,
            static_folder=self.static_folder
        )

        @app.route("/")
        def index() -> str:
            initial_status = self.hardware_manager.get_status()
            return render_template(
                "service_dashboard.html",
                initial_status=initial_status,
                app_version="4.0"
            )

        @app.route("/api/status", methods=["GET"])
        def get_status() -> Response:
            """Get system status with defensive error handling."""
            try:
                # Safely check camera status
                camera_online = False
                if hasattr(self, 'vision_manager') and self.vision_manager:
                    camera_online = hasattr(self.vision_manager, 'stream') and self.vision_manager.stream is not None
                
                # Safely get state attributes with defaults
                mode = getattr(self.state, 'mode', 'unknown') if self.state else 'unknown'
                battery_voltage = getattr(self.state, 'battery_voltage', 0.0) if self.state else 0.0
                last_error = getattr(self.state, 'last_error', None) if self.state else None
                motor_connected = getattr(self.state, 'motor_connected', False) if self.state else False
                lidar_connected = getattr(self.state, 'lidar_connected', False) if self.state else False
                
                return jsonify({
                    "mode": mode,
                    "battery_voltage": battery_voltage,
                    "last_error": last_error,
                    "motor_connected": motor_connected,
                    "lidar_connected": lidar_connected,
                    "camera_connected": camera_online,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"[APIServer] Status endpoint error: {e}", exc_info=True)
                # Return safe fallback response
                return jsonify({
                    "mode": "error",
                    "battery_voltage": 0.0,
                    "last_error": str(e),
                    "motor_connected": False,
                    "lidar_connected": False,
                    "camera_connected": False,
                    "timestamp": datetime.now().isoformat()
                }), 500

        @app.route("/api/motor/control", methods=["POST"])
        def control_motor() -> Response:
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
            scan_data = self.state.get_lidar_snapshot()
            return jsonify(scan_data)

        @app.route("/api/vision/stream")
        def vision_stream() -> Any:
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
            return jsonify(self.state.vision.last_scan)

        @app.route("/api/vision/results/<scan_id>")
        def get_scan_results(scan_id: str) -> Response:
            """Get scan results with robust ID handling."""
            try:
                scan_data = self.state.vision.last_scan if self.state and hasattr(self.state, 'vision') else None
                
                # Handle both string and int scan_id comparisons
                if scan_data and scan_data.get('scan_id'):
                    state_scan_id = str(scan_data['scan_id'])
                    requested_scan_id = str(scan_id)
                    
                    if state_scan_id == requested_scan_id:
                        return jsonify({
                            'status': 'completed',
                            'data': scan_data
                        })
                
                # Fallback: Check if scan exists regardless of ID match
                if scan_data and scan_data.get('tracking_id'):
                    return jsonify({
                        'status': 'completed',
                        'data': scan_data
                    })
                
                return jsonify({'status': 'processing'})
            except Exception as e:
                self.logger.error(f"[APIServer] Results endpoint error: {e}", exc_info=True)
                return jsonify({'status': 'error', 'message': str(e)}), 500

        @app.route("/api/vision/capture", methods=['POST'])
        def capture_photo() -> Response:
            frame = self.vision_manager.get_frame()
            if frame is None:
                return jsonify({'error': 'No frame available'}), 503
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            filepath = os.path.join(self.captures_dir, filename)
            
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

        @app.route('/captures/<filename>')
        def serve_capture(filename: str) -> Any:
            safe_filename = os.path.basename(filename)
            
            if not safe_filename.endswith(('.jpg', '.jpeg')):
                self.logger.warning(f"[APIServer] Invalid file type: {safe_filename}")
                return jsonify({'error': 'Invalid file type'}), 400
            
            filepath = os.path.join(self.captures_dir, safe_filename)
            
            if not os.path.exists(filepath):
                self.logger.warning(f"[APIServer] File not found: {filepath}")
                return jsonify({'error': 'File not found'}), 404
            
            return send_from_directory(self.captures_dir, safe_filename)
            
        @app.route("/api/ocr/analyze", methods=['POST'])
        def analyze_image() -> Response:
            frame = None
            
            try:
                if 'image' in request.files:
                    file = request.files['image']
                    
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > 5 * 1024 * 1024:
                        return jsonify({'error': 'File too large (max 5MB)'}), 400
                    
                    nparr = np.frombuffer(file.read(), np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                elif request.is_json and 'image_data' in request.json:
                    try:
                        img_data = base64.b64decode(request.json['image_data'])
                        nparr = np.frombuffer(img_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    except Exception as e:
                        self.logger.error(f"[APIServer] Base64 decode error: {e}")
                        return jsonify({'error': 'Invalid base64 image data'}), 400
                else:
                    return jsonify({'error': 'No image provided'}), 400
                
                if frame is None or frame.size == 0:
                    return jsonify({'error': 'Invalid image format'}), 400
                
                if frame.shape[0] != 480 or frame.shape[1] != 640:
                    frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
                    self.logger.debug(f"[APIServer] Resized image to 640x480")
                
                future = self.ocr_service.process_scan(frame)
                
                def update_state(fut: Any) -> None:
                    try:
                        result = fut.result()
                        self.state.update_scan_result(result)
                        self.logger.info(f"[APIServer] OCR completed: {result.get('tracking_id', 'N/A')}")
                    except Exception as e:
                        self.logger.error(f"[APIServer] OCR callback error: {e}")

                future.add_done_callback(update_state)
                
                return jsonify({
                    'success': True,
                    'scan_id': id(future),
                    'status': 'processing',
                    'message': 'Image submitted for analysis'
                }), 202
                
            except Exception as e:
                self.logger.error(f"[APIServer] OCR analyze error: {e}")
                return jsonify({'error': 'Image analysis failed'}), 500

        @app.route("/api/ocr/scan-image", methods=['POST'])
        def scan_uploaded_image() -> Response:
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
            return jsonify({"error": "Resource not found"}), 404

        @app.errorhandler(500)
        def internal_error(error: Any) -> Response:
            return jsonify({"error": "Internal server error"}), 500

        return app

    def _cleanup_old_captures(self, max_files: int = 50) -> None:
        try:
            if not os.path.exists(self.captures_dir):
                return
            
            files = [
                os.path.join(self.captures_dir, f) 
                for f in os.listdir(self.captures_dir) 
                if f.endswith(('.jpg', '.jpeg'))
            ]
            
            if len(files) > max_files:
                files.sort(key=os.path.getmtime)
                to_delete = files[:len(files) - max_files]
                for f in to_delete:
                    os.remove(f)
                    self.logger.debug(f"[APIServer] Deleted old capture: {f}")
        except Exception as e:
            self.logger.error(f"[APIServer] Cleanup failed: {e}")

    def run(self, host: str, port: int, debug: bool = False) -> None:
        if self.vision_manager.start_capture():
            self.state.update_vision_status(True, self.vision_manager.camera_index)
            self.logger.info(f"Camera initialized at index {self.vision_manager.camera_index}")
        else:
            self.logger.warning("No camera detected during startup")

        app = self.create_app()
        app.run(host=host, port=port, debug=debug, threaded=True)

    def stop(self) -> None:
        self.logger.info("Stopping APIServer services...")
        self.vision_manager.stop_capture()
        self.ocr_service.shutdown(wait=True)