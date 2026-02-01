"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/api/server.py
Description: Flask API server for robot control and telemetry.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from flask import Flask, Response, jsonify, render_template, request

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
        
        self.template_folder = os.path.abspath(template_folder)
        self.static_folder = os.path.abspath(static_folder)
        self.logger = logging.getLogger(__name__)

    def create_app(self) -> Flask:
        app = Flask(
            __name__,
            template_folder=self.template_folder,
            static_folder=self.static_folder
        )

        @app.route("/")
        def index():
            initial_status = self.hardware_manager.get_status()
            return render_template(
                "service_dashboard.html",
                initial_status=initial_status,
                app_version="4.0"
            )

        @app.route("/api/status", methods=["GET"])
        def get_status() -> Dict[str, Any]:
            status_data = self.state.get_status_snapshot()
            return jsonify(status_data)

        @app.route("/api/motor/control", methods=["POST"])
        def control_motor() -> Any:
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
                else:
                    return jsonify({"error": "Motor hardware unavailable"}), 503
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/api/lidar/scan", methods=["GET"])
        def get_lidar_scan() -> List[Dict[str, Any]]:
            scan_data = self.state.get_lidar_snapshot()
            return jsonify(scan_data)

        # Contract §5.1: Fix vision stream endpoint
        @app.route("/api/vision/stream")
        def vision_stream() -> Any:
            """Stream MJPEG video feed with optimized bandwidth."""
            if self.vision_manager.stream is None:
                return jsonify({'error': 'Camera not connected'}), 503

            # ✅ FIX: Change quality=80 → quality=40 (70% bandwidth reduction)
            return Response(
                self.vision_manager.generate_mjpeg(quality=40),  # Was 80
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

            def generate():
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
        def trigger_scan() -> Any:
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
        def get_last_scan() -> Any:
            return jsonify(self.state.vision.last_scan)

        @app.route("/api/vision/results/<scan_id>")
        def get_scan_results(scan_id: str) -> Any:
            scan_data = self.state.vision.last_scan
            if scan_data and scan_data.get('scan_id') == int(scan_id):
                return jsonify({
                    'status': 'completed',
                    'data': scan_data
                })
            return jsonify({'status': 'processing'})

        @app.errorhandler(404)
        def not_found(error: Any) -> Any:
            return jsonify({"error": "Resource not found"}), 404

        @app.errorhandler(500)
        def internal_error(error: Any) -> Any:
            return jsonify({"error": "Internal server error"}), 500

        return app

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