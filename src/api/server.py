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
    """Manages the Flask application server for the robot's API and dashboard.

    This class encapsulates the Flask app creation, route definitions, and
    server execution logic. It bridges the web interface with the underlying
    RobotState, HardwareManager, and Vision services.

    Attributes:
        state: The shared RobotState instance for retrieving telemetry.
        hardware_manager: The HardwareManager instance for device control.
        vision_manager: Internal manager for camera and stream operations.
        ocr_service: Internal service for asynchronous text recognition.
        template_folder: Path to the HTML templates directory.
        static_folder: Path to the static assets directory.
        logger: Logger instance.
    """

    def __init__(
        self,
        state: RobotState,
        hardware_manager: HardwareManager,
        template_folder: str = "frontend/templates",
        static_folder: str = "frontend/static"
    ) -> None:
        """Initialize the APIServer.

        Args:
            state: The shared robot state object.
            hardware_manager: The interface for hardware control.
            template_folder: Directory containing HTML templates.
                Defaults to "frontend/templates".
            static_folder: Directory containing static files (CSS/JS).
                Defaults to "frontend/static".
        """
        self.state = state
        self.hardware_manager = hardware_manager
        
        # Initialize Vision Subsystems
        self.vision_manager = VisionManager()
        self.ocr_service = OCRService(max_workers=2)
        
        self.template_folder = os.path.abspath(template_folder)
        self.static_folder = os.path.abspath(static_folder)
        self.logger = logging.getLogger(__name__)

    def create_app(self) -> Flask:
        """Configures and returns the Flask application instance.

        Defines all API routes and error handlers.

        Returns:
            A fully configured Flask application object.
        """
        app = Flask(
            __name__,
            template_folder=self.template_folder,
            static_folder=self.static_folder
        )

        # ---------------------------------------------------------
        # FRONTEND ROUTES
        # ---------------------------------------------------------

        @app.route("/")
        def index():
            """Serves the Service Dashboard hub with initial telemetry."""
            initial_status = self.hardware_manager.get_status()
            return render_template(
                "service_dashboard.html",
                initial_status=initial_status,
                app_version="4.0"
            )

        # ---------------------------------------------------------
        # GENERAL TELEMETRY
        # ---------------------------------------------------------

        @app.route("/api/status", methods=["GET"])
        def get_status() -> Dict[str, Any]:
            """Retrieves the current robot state snapshot."""
            status_data = self.state.get_status_snapshot()
            return jsonify(status_data)

        # ---------------------------------------------------------
        # HARDWARE CONTROL (MOTOR / LIDAR)
        # ---------------------------------------------------------

        @app.route("/api/motor/control", methods=["POST"])
        def control_motor() -> Any:
            """Processes motor control commands."""
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
            """Retrieves the latest LIDAR scan data."""
            scan_data = self.state.get_lidar_snapshot()
            return jsonify(scan_data)

        # ---------------------------------------------------------
        # VISION & OCR ROUTES
        # ---------------------------------------------------------

        @app.route("/api/vision/stream")
        def vision_stream() -> Any:
            """Stream MJPEG video feed."""
            if self.vision_manager.stream is None:
                return jsonify({'error': 'Camera not connected'}), 503

            return Response(
                self.vision_manager.generate_mjpeg(quality=80),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

        @app.route("/api/vision/scan", methods=['POST'])
        def trigger_scan() -> Any:
            """Trigger an OCR scan on the current frame."""
            frame = self.vision_manager.get_frame()
            if frame is None:
                return jsonify({'error': 'No frame available'}), 503

            try:
                # Submit OCR job
                future = self.ocr_service.process_scan(frame)

                # Non-blocking callback to update state when done
                def update_state(fut: Any) -> None:
                    try:
                        result = fut.result()
                        self.state.update_scan_result(result)
                    except Exception as e:
                        self.logger.error(f"OCR callback error: {e}")

                future.add_done_callback(update_state)

                return jsonify({
                    'status': 'processing',
                    'message': 'Scan started'
                }), 202
            except RuntimeError:
                return jsonify({'error': 'OCR service unavailable'}), 500

        @app.route("/api/vision/last-scan")
        def get_last_scan() -> Any:
            """Retrieve the result of the last completed scan."""
            return jsonify(self.state.vision.last_scan)

        # ---------------------------------------------------------
        # ERROR HANDLERS
        # ---------------------------------------------------------

        @app.errorhandler(404)
        def not_found(error: Any) -> Any:
            return jsonify({"error": "Resource not found"}), 404

        @app.errorhandler(500)
        def internal_error(error: Any) -> Any:
            return jsonify({"error": "Internal server error"}), 500

        return app

    def run(self, host: str, port: int, debug: bool = False) -> None:
        """Starts the Flask web server and background services.

        Args:
            host: The interface to bind to (e.g., '0.0.0.0').
            port: The port number to listen on.
            debug: Whether to run in debug mode. Defaults to False.
        """
        # Start Vision System
        if self.vision_manager.start_capture():
            self.state.update_vision_status(True, self.vision_manager.camera_index)
            self.logger.info(f"Camera initialized at index {self.vision_manager.camera_index}")
        else:
            self.logger.warning("No camera detected during startup")

        app = self.create_app()
        # Threaded mode enabled for concurrent request handling
        app.run(host=host, port=port, debug=debug, threaded=True)

    def stop(self) -> None:
        """Gracefully shuts down background services."""
        self.logger.info("Stopping APIServer services...")
        self.vision_manager.stop_capture()
        self.ocr_service.shutdown(wait=True)