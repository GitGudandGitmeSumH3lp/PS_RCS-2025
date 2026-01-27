"""PS_RCS_PROJECT

This module implements the APIServer class, which configures and runs the
Flask-based web server for the robot. It handles both the serving of the
service dashboard and the JSON API endpoints for hardware control and telemetry.
"""

import os
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request

from src.core.state import RobotState
from src.services.hardware_manager import HardwareManager


class APIServer:
    """Manages the Flask application server for the robot's API and dashboard.

    This class encapsulates the Flask app creation, route definitions, and
    server execution logic. It bridges the web interface with the underlying
    RobotState and HardwareManager.

    Attributes:
        state: The shared RobotState instance for retrieving telemetry.
        hardware_manager: The HardwareManager instance for device control.
        template_folder: Path to the HTML templates directory.
        static_folder: Path to the static assets directory.
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
        self.template_folder = os.path.abspath(template_folder)
        self.static_folder = os.path.abspath(static_folder)

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

        @app.route("/")
        def index():
            """Serves the Service Dashboard hub with initial telemetry.

            Fetches the current hardware status and renders the dashboard template.

            Returns:
                The rendered HTML template for the service dashboard.
            """
            initial_status = self.hardware_manager.get_status()
            # Logic constraint: render_template arguments preserved exactly
            return render_template(
                "service_dashboard.html",
                initial_status=initial_status,
                app_version="4.0"
            )

        @app.route("/api/status", methods=["GET"])
        def get_status() -> Dict[str, Any]:
            """Retrieves the current robot state snapshot.

            Returns:
                A JSON dictionary containing the current state telemetry.
            """
            status_data = self.state.get_status_snapshot()
            return jsonify(status_data)

        @app.route("/api/motor/control", methods=["POST"])
        def control_motor() -> Any:
            """Processes motor control commands.

            Expects a JSON payload with a 'command' and optional 'speed'.

            Returns:
                A JSON response indicating success or failure.
            
            Status Codes:
                200: Command sent successfully.
                400: Invalid JSON or missing parameters.
                503: Hardware unavailable.
            """
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
            """Retrieves the latest LIDAR scan data.

            Returns:
                A JSON list of dictionaries representing scan points.
            """
            scan_data = self.state.get_lidar_snapshot()
            return jsonify(scan_data)

        @app.errorhandler(404)
        def not_found(error: Any) -> Any:
            """Handles 404 Not Found errors."""
            return jsonify({"error": "Resource not found"}), 404

        @app.errorhandler(500)
        def internal_error(error: Any) -> Any:
            """Handles 500 Internal Server errors."""
            return jsonify({"error": "Internal server error"}), 500

        return app

    def run(self, host: str, port: int, debug: bool = False) -> None:
        """Starts the Flask web server.

        Args:
            host: The interface to bind to (e.g., '0.0.0.0').
            port: The port number to listen on.
            debug: Whether to run in debug mode. Defaults to False.
        """
        app = self.create_app()
        # Threaded mode enabled for concurrent request handling
        app.run(host=host, port=port, debug=debug, threaded=True)