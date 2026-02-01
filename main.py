"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: main.py
Description: Entry point for the Parcel Robot System.
"""

import signal
import sys

# Import core modules
from src.api.server import APIServer
from src.core.config import Settings
from src.core.state import RobotState
from src.database.db_manager import DatabaseManager
from src.services.hardware_manager import HardwareManager

# Global references for shutdown
hardware_manager = None
api_server = None


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n[STOP] Shutdown signal received. Stopping hardware...")
    if hardware_manager:
        hardware_manager.shutdown()
    sys.exit(0)

def main():
    """Main application entry point."""
    global hardware_manager, api_server 

    # 1. Load Configuration
    try:
        settings = Settings.load_from_file()
        print(f"[OK] Configuration loaded. (Sim Mode: {settings.SIMULATION_MODE})")
    except Exception as e:
        print(f"[ERROR] Failed to load configuration: {e}")
        sys.exit(1)

    # 2. Initialize State & Database
    try:
        state = RobotState()
        db_manager = DatabaseManager(settings.DB_PATH)
        print("[OK] State and Database initialized.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize state/database: {e}")
        sys.exit(1)

    # 3. Initialize Hardware
    try:
        hardware_manager = HardwareManager(settings, state)
        status = hardware_manager.start_all_drivers()
        print(f"[OK] Hardware Status: Motor={status['motor']}, LiDAR={status['lidar']}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize hardware: {e}")
        sys.exit(1)

    # 4. Start API Server
    try:
        # Initialize APIServer with the state and hardware manager
        api_server = APIServer(state, hardware_manager)

        # Register signal handler for graceful exit
        signal.signal(signal.SIGINT, signal_handler)

        print(f"[START] Starting Server on {settings.API_HOST}:{settings.API_PORT}")
        print("Press Ctrl+C to stop the server.")

        api_server.run(
            host=settings.API_HOST,
            port=settings.API_PORT,
            debug=False
        )
    except KeyboardInterrupt:
        print("\n[STOP] Server stopped by user")
    except Exception as e:
        print(f"[ERROR] Server error: {e}")
    finally:
        if hardware_manager:
            hardware_manager.shutdown()
        print("[EXIT] Shutdown complete")


if __name__ == "__main__":
    main()