"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/hardware/camera/__init__.py
Description: Camera Hardware Abstraction Layer (HAL) package exports.

This package exposes the abstract CameraProvider base class, specific exceptions,
and a factory function for instantiating the appropriate camera provider
(USB or CSI) based on system configuration.
"""

from .base import (
    CameraProvider,
    CameraError,
    CameraInitializationError,
    CameraConfigurationError,
)
from .factory import get_camera_provider
from .usb_provider import UsbCameraProvider

# Default exports available on all platforms
__all__ = [
    'CameraProvider',
    'CameraError',
    'CameraInitializationError',
    'CameraConfigurationError',
    'get_camera_provider',
    'UsbCameraProvider',
]

# Conditionally export CSI provider if dependencies are met
try:
    from .csi_provider import CsiCameraProvider
    __all__.append('CsiCameraProvider')
except ImportError:
    # CsiCameraProvider not available on this platform (e.g., Windows/Mac)
    pass