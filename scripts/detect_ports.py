#!/usr/bin/env python3
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: scripts/detect_ports.py
Description: Auto-detects Arduino (motor) and LiDAR serial ports. Updates
             settings.json in-place when run with --write. Safe to run at any
             time; the main server does NOT need to be stopped first.

Usage:
    python detect_ports.py                  # Same as --check
    python detect_ports.py --check          # Print detections, no file writes
    python detect_ports.py --write          # Update settings.json if changed
    python detect_ports.py --force-rescan   # Skip by-id fast path, probe all ports
    python detect_ports.py --write --force-rescan
    python detect_ports.py --dry-run        # Show what --write would do without touching the file

Requirements:
    pip install pyserial
"""

import argparse
import glob
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("ERROR: pyserial is not installed. Run: pip install pyserial")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s"
)
logger = logging.getLogger("detect_ports")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# settings.json is at project root/config/settings.json by convention.
# Override with SETTINGS_PATH env variable if your layout differs.
DEFAULT_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "settings.json"
)

# USB descriptor substrings that identify each device (fast path).
# These come directly from the by-id symlink names observed in production.
ARDUINO_ID_SUBSTRINGS = [
    "1a86",          # QinHeng CH340/CH341 (most Uno clones)
    "FTDI",          # FTDI FT232 (genuine Arduino Uno R3)
    "Arduino",       # Official Arduino USB descriptor
]

LIDAR_ID_SUBSTRINGS = [
    "Silicon_Labs",  # CP2102 – RPLIDAR standard chip
    "CP210",         # Alternate CP210x descriptor string
    "CP2102",        # Explicit model match
]

# Baud rates used by each device
ARDUINO_BAUD = 9600
LIDAR_BAUD = 115200

# Serial probe timeouts (seconds)
ARDUINO_PROBE_TIMEOUT = 0.4
LIDAR_PROBE_TIMEOUT = 0.4

# RPLIDAR "Get Device Info" command (0xA5 0x50) and expected response prefix
LIDAR_PROBE_CMD = bytes([0xA5, 0x50])
LIDAR_RESPONSE_PREFIX = bytes([0xA5, 0x5A])  # Descriptor start marker

# Safe Arduino probe: stop command (2-byte protocol: cmd='X', speed=0x00)
# wheels.ino peeks the first byte; 'X' is a valid command so it is consumed
# cleanly. No motor movement occurs (stop is always a no-op).
ARDUINO_PROBE_CMD = b"X\x00"


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class DetectionResult:
    """Holds the outcome of a detection run."""
    arduino_port: Optional[str]
    lidar_port: Optional[str]
    arduino_method: str   # "by-id" | "probe" | "none"
    lidar_method: str
    warnings: list


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _list_by_id_ports() -> list[str]:
    """Return all symlinks under /dev/serial/by-id/ (Linux only)."""
    pattern = "/dev/serial/by-id/*"
    return glob.glob(pattern)


def _resolve_symlink(path: str) -> str:
    """Resolve a /dev/serial/by-id symlink to its real /dev/tty* path."""
    try:
        real = os.path.realpath(path)
        return real
    except OSError:
        return path


def _candidate_ports() -> list[str]:
    """Return all candidate serial ports on the system (ttyUSB* and ttyACM*)."""
    candidates = []
    for pattern in ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*"]:
        candidates.extend(glob.glob(pattern))
    # On Windows (dev/testing only) fall back to COM ports via pyserial
    if sys.platform.startswith("win"):
        import serial.tools.list_ports as lp
        candidates = [p.device for p in lp.comports()]
    return sorted(set(candidates))


# ---------------------------------------------------------------------------
# Fast path: /dev/serial/by-id/ descriptor matching
# ---------------------------------------------------------------------------

def _classify_by_id_path(
    path: str,
) -> tuple[bool, bool, str, str]:
    """Classify one /dev/serial/by-id path as Arduino, LiDAR, both, or neither.

    Args:
        path: Full /dev/serial/by-id/... symlink path.

    Returns:
        (is_arduino, is_lidar, real_path, name)
    """
    name = os.path.basename(path)
    real = _resolve_symlink(path)
    is_arduino = any(sub in name for sub in ARDUINO_ID_SUBSTRINGS)
    is_lidar   = any(sub in name for sub in LIDAR_ID_SUBSTRINGS)
    return is_arduino, is_lidar, real, name


def _resolve_single_match(
    matches: list[tuple[str, str]],
    role: str,
    warnings: list[str],
) -> Optional[str]:
    """Return the single matched port or append a warning if ambiguous.

    Args:
        matches: List of (real_path, name) tuples.
        role: Human-readable role label ('Arduino' or 'LiDAR').
        warnings: Mutable list to append warnings to.

    Returns:
        Resolved port string, or None if 0 or 2+ matches.
    """
    if len(matches) == 1:
        return matches[0][0]
    if len(matches) > 1:
        warnings.append(
            f"⚠️  Multiple {role}-signature ports found: "
            f"{[m[0] for m in matches]}. Falling through to behavioral probe."
        )
    return None


def _detect_by_id() -> tuple[Optional[str], Optional[str], list[str]]:
    """Scan /dev/serial/by-id/ and match known USB descriptor substrings.

    Returns:
        (arduino_port, lidar_port, warnings) — real /dev/tty* paths.
    """
    warnings: list[str] = []
    by_id_paths = _list_by_id_ports()

    if not by_id_paths:
        logger.debug("No /dev/serial/by-id/ entries found (normal on Windows).")
        return None, None, warnings

    arduino_matches: list[tuple[str, str]] = []
    lidar_matches:   list[tuple[str, str]] = []

    for path in by_id_paths:
        is_arduino, is_lidar, real, name = _classify_by_id_path(path)
        if is_arduino and is_lidar:
            warnings.append(
                f"⚠️  Port '{real}' matches BOTH Arduino and LiDAR signatures "
                f"(by-id: {name}). Manual assignment required."
            )
        elif is_arduino:
            arduino_matches.append((real, name))
            logger.debug(f"  Arduino candidate (by-id): {real}  [{name}]")
        elif is_lidar:
            lidar_matches.append((real, name))
            logger.debug(f"  LiDAR candidate  (by-id): {real}  [{name}]")

    arduino_port = _resolve_single_match(arduino_matches, "Arduino", warnings)
    lidar_port   = _resolve_single_match(lidar_matches, "LiDAR", warnings)
    return arduino_port, lidar_port, warnings


# ---------------------------------------------------------------------------
# Swap detection
# ---------------------------------------------------------------------------

def _check_for_swap(
    detected_arduino: Optional[str],
    detected_lidar: Optional[str],
    current_motor_port: str,
    current_lidar_port: str,
) -> list[str]:
    """
    Warn if the detected roles appear to be swapped vs. what settings.json says.

    A 'swap' is when the port currently assigned as MOTOR_PORT has LiDAR
    descriptor signatures, or vice versa.
    """
    warnings = []

    if detected_arduino and detected_lidar:
        # Resolve current settings paths to real device paths for comparison
        real_motor = _resolve_symlink(current_motor_port) if os.path.exists(current_motor_port) else current_motor_port
        real_lidar = _resolve_symlink(current_lidar_port) if os.path.exists(current_lidar_port) else current_lidar_port

        if detected_arduino == real_lidar and detected_lidar == real_motor:
            warnings.append(
                "🔴 SWAP DETECTED: The port currently assigned as MOTOR_PORT appears "
                "to be the LiDAR, and LIDAR_PORT appears to be the Arduino. "
                "The detected ports have been corrected in this run."
            )

    return warnings


# ---------------------------------------------------------------------------
# Behavioral probe: Arduino
# ---------------------------------------------------------------------------

def _probe_arduino(port: str) -> bool:
    """
    Probe a port to check if it is running wheels.ino.

    Sends the 2-byte stop command (X 0x00). The Arduino will parse it cleanly
    (no motor movement). We verify the port opens at 9600 baud without error.
    No response is expected — the probe is silent.

    Args:
        port: Device path, e.g. '/dev/ttyUSB0'.

    Returns:
        True if the port opened cleanly at Arduino baud rate.
    """
    try:
        with serial.Serial(
            port,
            baudrate=ARDUINO_BAUD,
            timeout=ARDUINO_PROBE_TIMEOUT,
            write_timeout=1,
            exclusive=True,
        ) as conn:
            time.sleep(0.1)  # Allow Arduino to finish reset after DTR pulse
            conn.reset_input_buffer()
            conn.write(ARDUINO_PROBE_CMD)
            conn.flush()
            # No response expected — success is simply opening without error
            logger.debug(f"  Arduino probe OK: {port}")
            return True
    except serial.SerialException as e:
        logger.debug(f"  Arduino probe FAIL ({port}): {e}")
        return False
    except Exception as e:
        logger.debug(f"  Arduino probe ERROR ({port}): {e}")
        return False


# ---------------------------------------------------------------------------
# Behavioral probe: RPLIDAR
# ---------------------------------------------------------------------------

def _probe_lidar(port: str) -> bool:
    """
    Probe a port to check if it is an RPLIDAR unit.

    Sends the 'Get Device Info' command (0xA5 0x50) and checks that the
    response starts with the RPLIDAR descriptor marker (0xA5 0x5A).

    Args:
        port: Device path, e.g. '/dev/ttyUSB1'.

    Returns:
        True if the RPLIDAR descriptor marker is received.
    """
    try:
        with serial.Serial(
            port,
            baudrate=LIDAR_BAUD,
            timeout=LIDAR_PROBE_TIMEOUT,
            write_timeout=1,
            exclusive=True,
        ) as conn:
            conn.reset_input_buffer()
            conn.write(LIDAR_PROBE_CMD)
            conn.flush()
            response = conn.read(2)
            matched = response == LIDAR_RESPONSE_PREFIX
            logger.debug(
                f"  LiDAR probe {'OK' if matched else 'FAIL'} ({port}): "
                f"got {response.hex() if response else 'nothing'}"
            )
            return matched
    except serial.SerialException as e:
        logger.debug(f"  LiDAR probe FAIL ({port}): {e}")
        return False
    except Exception as e:
        logger.debug(f"  LiDAR probe ERROR ({port}): {e}")
        return False


# ---------------------------------------------------------------------------
# Behavioral probe: full scan
# ---------------------------------------------------------------------------

def _probe_all_candidates(
    candidates: list[str],
    skip_real: list[str],
) -> tuple[list[str], list[str]]:
    """Probe candidate ports and classify as Arduino or LiDAR.

    Args:
        candidates: Device paths to probe.
        skip_real: Resolved real paths to skip (already identified).

    Returns:
        (arduino_candidates, lidar_candidates)
    """
    arduino_candidates: list[str] = []
    lidar_candidates:   list[str] = []
    for port in candidates:
        if _resolve_symlink(port) in skip_real:
            logger.debug(f"  Skipping already-identified port: {port}")
            continue
        logger.info(f"  Probing {port} ...")
        if _probe_lidar(port):
            lidar_candidates.append(port)
        elif _probe_arduino(port):
            arduino_candidates.append(port)
    return arduino_candidates, lidar_candidates


def _detect_by_probe(
    skip_ports: Optional[list[str]] = None,
) -> tuple[Optional[str], Optional[str], list[str]]:
    """Probe all candidate ports to identify Arduino and LiDAR.

    Args:
        skip_ports: Real device paths already identified (avoid double-open).

    Returns:
        (arduino_port, lidar_port, warnings)
    """
    warnings: list[str] = []
    skip_real = [_resolve_symlink(p) for p in (skip_ports or [])]
    candidates = _candidate_ports()

    if not candidates:
        warnings.append("No candidate serial ports found (/dev/ttyUSB*, /dev/ttyACM*).")
        return None, None, warnings

    arduino_candidates, lidar_candidates = _probe_all_candidates(candidates, skip_real)

    arduino_port = _resolve_single_match(arduino_candidates, "Arduino", warnings)
    lidar_port   = _resolve_single_match(lidar_candidates,  "LiDAR",   warnings)
    return arduino_port, lidar_port, warnings

def _run_fast_path(
    all_warnings: list[str],
) -> tuple[Optional[str], Optional[str], str, str]:
    """Run /dev/serial/by-id/ fast-path detection.

    Args:
        all_warnings: Mutable warning list to extend.

    Returns:
        (arduino_port, lidar_port, arduino_method, lidar_method)
    """
    logger.info("Step 1: Scanning /dev/serial/by-id/ ...")
    a, l, w = _detect_by_id()
    all_warnings.extend(w)
    arduino_port, arduino_method = (a, "by-id") if a else (None, "none")
    lidar_port,   lidar_method   = (l, "by-id") if l else (None, "none")
    if a:
        logger.info(f"  ✅ Arduino  → {a}  (by-id match)")
    if l:
        logger.info(f"  ✅ LiDAR    → {l}  (by-id match)")
    return arduino_port, lidar_port, arduino_method, lidar_method


def _run_probe_path(
    arduino_port: Optional[str],
    lidar_port: Optional[str],
    arduino_method: str,
    lidar_method: str,
    all_warnings: list[str],
) -> tuple[Optional[str], Optional[str], str, str]:
    """Run behavioral probe for any roles not yet assigned.

    Args:
        arduino_port: Already-detected Arduino port (or None).
        lidar_port: Already-detected LiDAR port (or None).
        arduino_method: Detection method string for Arduino.
        lidar_method: Detection method string for LiDAR.
        all_warnings: Mutable warning list to extend.

    Returns:
        Updated (arduino_port, lidar_port, arduino_method, lidar_method).
    """
    logger.info("Step 2: Behavioral probing unresolved ports ...")
    already_found = [p for p in [arduino_port, lidar_port] if p]
    pa, pl, pw = _detect_by_probe(skip_ports=already_found)
    all_warnings.extend(pw)
    if arduino_port is None and pa:
        arduino_port, arduino_method = pa, "probe"
        logger.info(f"  ✅ Arduino  → {pa}  (behavioral probe)")
    if lidar_port is None and pl:
        lidar_port, lidar_method = pl, "probe"
        logger.info(f"  ✅ LiDAR    → {pl}  (behavioral probe)")
    return arduino_port, lidar_port, arduino_method, lidar_method


def detect_ports(force_rescan: bool = False) -> DetectionResult:
    """Run the full port detection pipeline.

    Priority:
        1. /dev/serial/by-id/ substring match (fast, no comms).
        2. Behavioral probe on /dev/ttyUSB* / /dev/ttyACM* (fallback).

    Args:
        force_rescan: Skip the by-id fast path and probe all ports.

    Returns:
        DetectionResult with found ports, methods used, and warnings.
    """
    all_warnings: list[str] = []
    arduino_port: Optional[str] = None
    lidar_port:   Optional[str] = None
    arduino_method = "none"
    lidar_method   = "none"

    if not force_rescan:
        arduino_port, lidar_port, arduino_method, lidar_method = (
            _run_fast_path(all_warnings)
        )
    else:
        logger.info("Step 1: Skipped (--force-rescan active).")

    if arduino_port is None or lidar_port is None:
        arduino_port, lidar_port, arduino_method, lidar_method = _run_probe_path(
            arduino_port, lidar_port, arduino_method, lidar_method, all_warnings
        )

    if arduino_port is None:
        all_warnings.append(
            "🔴 Arduino not detected. Check USB and that wheels.ino is flashed."
        )
    if lidar_port is None:
        all_warnings.append("🔴 LiDAR not detected. Check USB connection and power.")

    return DetectionResult(
        arduino_port=arduino_port,
        lidar_port=lidar_port,
        arduino_method=arduino_method,
        lidar_method=lidar_method,
        warnings=all_warnings,
    )


# ---------------------------------------------------------------------------
# settings.json read / write
# ---------------------------------------------------------------------------

def load_settings(filepath: str) -> dict:
    """Load settings.json as a raw dict.

    Args:
        filepath: Path to settings.json.

    Returns:
        Parsed JSON dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is malformed.
    """
    with open(filepath, "r") as f:
        return json.load(f)


def write_settings(filepath: str, data: dict) -> None:
    """Write a settings dict back to settings.json atomically.

    Uses a temp file + rename to avoid corrupting the file on write failure.

    Args:
        filepath: Path to settings.json.
        data: Full settings dict to write.
    """
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=4)
        f.write("\n")  # trailing newline for POSIX compliance
    os.replace(tmp_path, filepath)  # atomic on POSIX


def _validate_settings_dict(data: dict) -> None:
    """
    Re-run config.py's validation logic on a settings dict before writing.

    This mirrors Settings.load_from_file() checks so we never write a config
    that the server would reject on startup.

    Args:
        data: Settings dict to validate.

    Raises:
        ValueError: If any field fails validation.
    """
    required_keys = [
        "MOTOR_PORT", "LIDAR_PORT", "DB_PATH", "SIMULATION_MODE",
        "MOTOR_BAUD_RATE", "LIDAR_BAUD_RATE", "API_HOST", "API_PORT"
    ]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key after patch: {key}")

    if not isinstance(data.get("SIMULATION_MODE"), bool):
        raise ValueError("SIMULATION_MODE must be bool")

    api_port = data.get("API_PORT")
    if not isinstance(api_port, int) or not (1024 <= api_port <= 65535):
        raise ValueError(f"API_PORT invalid: {api_port}")

    for baud_key in ("MOTOR_BAUD_RATE", "LIDAR_BAUD_RATE"):
        baud = data.get(baud_key)
        if not isinstance(baud, int) or baud <= 0:
            raise ValueError(f"{baud_key} must be a positive int")

    offset = data.get("LIDAR_ANGLE_OFFSET_DEG", 0.0)
    if not isinstance(offset, (int, float)) or not (-180.0 <= float(offset) <= 180.0):
        raise ValueError(f"LIDAR_ANGLE_OFFSET_DEG out of range: {offset}")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_device_rows(result: DetectionResult) -> None:
    """Print the detected device rows to stdout.

    Args:
        result: Detection result containing port assignments.
    """
    s = lambda p: "✅" if p else "❌"
    print(f"  {s(result.arduino_port)} Arduino  → "
          f"{result.arduino_port or 'NOT FOUND'}  [{result.arduino_method}]")
    print(f"  {s(result.lidar_port)}  LiDAR    → "
          f"{result.lidar_port or 'NOT FOUND'}  [{result.lidar_method}]")


def _print_change_summary(
    result: DetectionResult,
    current: dict,
    mode: str,
) -> None:
    """Print change summary and mode outcome line.

    Args:
        result: Detection result.
        current: Existing settings dict.
        mode: 'write', 'dry-run', or 'check'.
    """
    motor_changed = result.arduino_port and result.arduino_port != current.get("MOTOR_PORT")
    lidar_changed = result.lidar_port   and result.lidar_port   != current.get("LIDAR_PORT")
    if motor_changed or lidar_changed:
        print()
        print("  📝 Changes detected:")
        if motor_changed:
            print(f"     MOTOR_PORT : {current.get('MOTOR_PORT')}  →  {result.arduino_port}")
        if lidar_changed:
            print(f"     LIDAR_PORT : {current.get('LIDAR_PORT')}  →  {result.lidar_port}")
    else:
        print()
        print("  ✅ No changes needed — settings.json is already correct.")
    if result.warnings:
        print()
        print("  Warnings:")
        for w in result.warnings:
            print(f"    {w}")
    print()
    outcomes = {
        "write":   ("  💾 settings.json UPDATED.", "  💾 settings.json unchanged (already correct)."),
        "dry-run": ("  🔍 DRY RUN — no file was written. Use --write to apply.", "  🔍 DRY RUN — no changes would be made."),
    }
    if mode in outcomes:
        print(outcomes[mode][0] if (motor_changed or lidar_changed) else outcomes[mode][1])
    else:
        print("  ℹ️  CHECK mode — no file was written. Use --write to apply changes.")


def _print_report(
    result: DetectionResult,
    current: dict,
    settings_path: str,
    mode: str,
) -> None:
    """Print a human-readable detection report to stdout.

    Args:
        result: Detection result from detect_ports().
        current: Existing settings dict loaded from settings.json.
        settings_path: Path to settings.json (shown in header).
        mode: One of 'check', 'write', 'dry-run'.
    """
    print()
    print("=" * 60)
    print("  PS_RCS_PROJECT — Port Detection Report")
    print("=" * 60)
    print(f"\n  📄 Settings file : {settings_path}")
    print(f"  Current MOTOR_PORT : {current.get('MOTOR_PORT', '(not set)')}")
    print(f"  Current LIDAR_PORT : {current.get('LIDAR_PORT', '(not set)')}")
    print()
    _print_device_rows(result)
    _print_change_summary(result, current, mode)
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        description="Auto-detect Arduino and LiDAR serial ports for PS_RCS_PROJECT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--check", action="store_true",
                   help="Print detected ports without modifying settings.json (default).")
    p.add_argument("--write", action="store_true",
                   help="Update MOTOR_PORT and LIDAR_PORT in settings.json if changed.")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="Show what --write would do without touching the file.")
    p.add_argument("--force-rescan", action="store_true", dest="force_rescan",
                   help="Skip /dev/serial/by-id fast path; probe all ports behaviorally.")
    p.add_argument("--settings", default=DEFAULT_SETTINGS_PATH, metavar="PATH",
                   help=f"Path to settings.json (default: {DEFAULT_SETTINGS_PATH}).")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Enable DEBUG-level logging.")
    return p


def _apply_write(
    result: DetectionResult,
    current: dict,
    settings_path: str,
) -> int:
    """Patch and write settings.json with detected ports.

    Args:
        result: Detection result containing new port values.
        current: Existing settings dict.
        settings_path: File path to write to.

    Returns:
        0 on success, 2 on validation or IO error.
    """
    patched = dict(current)
    changed = False
    if result.arduino_port and result.arduino_port != current.get("MOTOR_PORT"):
        patched["MOTOR_PORT"] = result.arduino_port
        changed = True
    if result.lidar_port and result.lidar_port != current.get("LIDAR_PORT"):
        patched["LIDAR_PORT"] = result.lidar_port
        changed = True
    if not changed:
        return 0
    try:
        _validate_settings_dict(patched)
        write_settings(settings_path, patched)
    except ValueError as e:
        print(f"ERROR: Validation failed, settings.json not written: {e}")
        return 2
    except OSError as e:
        print(f"ERROR: Could not write settings.json: {e}")
        return 2
    return 0


def main() -> int:
    """CLI entry point.

    Returns:
        0 = both devices found, 1 = one or more missing, 2 = error.
    """
    args = _build_arg_parser().parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    if args.write and args.dry_run:
        print("ERROR: --write and --dry-run are mutually exclusive.")
        return 2

    mode = "write" if args.write else ("dry-run" if args.dry_run else "check")

    try:
        current = load_settings(args.settings)
    except FileNotFoundError:
        print(f"ERROR: settings.json not found at: {args.settings}")
        print("       Override with --settings <path>")
        return 2
    except json.JSONDecodeError as e:
        print(f"ERROR: Malformed settings.json: {e}")
        return 2

    logger.info("Starting port detection ...")
    result = detect_ports(force_rescan=args.force_rescan)
    result.warnings.extend(_check_for_swap(
        detected_arduino=result.arduino_port,
        detected_lidar=result.lidar_port,
        current_motor_port=current.get("MOTOR_PORT", ""),
        current_lidar_port=current.get("LIDAR_PORT", ""),
    ))

    _print_report(result, current, args.settings, mode)

    if mode == "write":
        rc = _apply_write(result, current, args.settings)
        if rc != 0:
            return rc

    return 0 if (result.arduino_port and result.lidar_port) else 1


if __name__ == "__main__":
    sys.exit(main())