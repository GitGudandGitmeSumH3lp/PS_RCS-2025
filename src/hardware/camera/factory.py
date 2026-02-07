"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/camera/factory.py
Description: Factory module for camera provider selection.
"""

import logging
import os
from typing import Optional

from .base import CameraProvider
from .usb_provider import UsbCameraProvider

logger = logging.getLogger(__name__)

# Attempt to import CSI provider, set flag if successful
try:
    from .csi_provider import CsiCameraProvider
    _CSI_AVAILABLE = True
except ImportError:
    _CSI_AVAILABLE = False


def get_camera_provider(interface: Optional[str] = None) -> CameraProvider:
    """Factory function to select and instantiate a camera provider.

    Determines the appropriate provider based on the `interface` argument
    or the `CAMERA_INTERFACE` environment variable.

    Args:
        interface: Explicit provider request. Valid values are 'usb',
            'csi', 'auto', or None. If None, checks environment variables.

    Returns:
        An instance of a class implementing CameraProvider.

    Raises:
        ValueError: If the interface string is invalid.
        ImportError: If a specific interface ('csi') is requested but unavailable.
    """
    if interface is None:
        interface = os.getenv('CAMERA_INTERFACE', 'auto').lower()
    else:
        interface = interface.lower()

    if interface not in {'usb', 'csi', 'auto'}:
        raise ValueError(
            f"Invalid CAMERA_INTERFACE: '{interface}'. "
            "Must be 'usb', 'csi', or 'auto'."
        )

    if interface == 'usb':
        logger.info("Factory: Forcing USB camera provider")
        return UsbCameraProvider()

    if interface == 'csi':
        if not _CSI_AVAILABLE:
            raise ImportError(
                "CSI provider requested but picamera2 not available. "
                "Install via: sudo apt install python3-picamera2"
            )
        logger.info("Factory: Forcing CSI camera provider")
        return CsiCameraProvider()

    # Auto mode logic
    if interface == 'auto':
        if _CSI_AVAILABLE:
            logger.info("Factory: Auto mode, trying CSI provider first")
            try:
                # We instantiate to check basic viability (imports worked)
                # Actual hardware check happens at start()
                return CsiCameraProvider()
            except Exception as e:
                logger.warning(f"CSI provider init failed, falling back to USB: {e}")
        else:
            logger.info("Factory: Auto mode, CSI unavailable, using USB")

        return UsbCameraProvider()

    # Should be unreachable due to validation above
    raise ValueError(f"Unhandled interface: {interface}")