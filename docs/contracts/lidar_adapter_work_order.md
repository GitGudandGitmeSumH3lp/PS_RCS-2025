# WORK ORDER FOR IMPLEMENTER

**Target File:** `backend/hardware/lidar_adapter.py`
**Contract Reference:** `docs/contracts/lidar_integration.md` v1.0
**Date:** 2026-02-20

---

## Strict Constraints (NON-NEGOTIABLE)

1. **No global `lidar_adapter` or `lidar_reader` variable.** Instance must live inside `HardwareManager`.
2. **No `asyncio`.** Use `threading` exclusively. Background thread must be `daemon=True`.
3. **No `serial` import in route files.** All serial access goes through this adapter.
4. **All public methods must have full type hints and Google-style docstrings.**
5. **No function body may exceed 50 executable lines.** Refactor private helpers if needed.
6. **All public methods must acquire `self._lock` before accessing shared state.**
7. **No method may raise to the caller** (except `__init__` on invalid config and `register_callback` on non-callable). All other errors: log + return `False` or empty structure.

---

## Memory Compliance (MANDATORY)

- No memory snippet provided. Follow `system_constraints.md` exclusively.

---

## Required Logic

1. **`__init__`:** Store config, initialize `self._lock = threading.Lock()`, set all state attrs to safe defaults. Do NOT instantiate `LiDARReader` here.
2. **`connect`:** Guard with `self._lock`. If `self._connected`, return `True` immediately. Otherwise instantiate `LiDARReader(self._port, self._baudrate)` and call `.connect()`. Set `self._connect_time = time.monotonic()` and `self._connected = True` on success.
3. **`disconnect`:** Guard with `self._lock`. Call `stop_scanning()` first if scanning. Call `self._reader.stop_scan()`. Set `self._connected = False`, `self._connect_time = None`.
4. **`start_scanning`:** Guard with `self._lock`. If not connected, call `connect()`; fail fast if that returns `False`. Call `self._reader.start_scan()`. Set `self._scanning = True` on success.
5. **`stop_scanning`:** Guard with `self._lock`. If not scanning, return `True`. Set `self._reader.is_scanning = False`. Join `self._reader.reader_thread` with `timeout=3`. Set `self._scanning = False`.
6. **`get_latest_scan`:** Guard with `self._lock`. Call `self._reader.get_latest_data(max_points=360)`. Compute obstacles (distance < 1000). Return full dict. On any error return empty structure.
7. **`get_status`:** Guard with `self._lock`. Compute uptime. Return status dict. Never raise.
8. **`register_callback`:** Validate callable. Acquire `self._lock` to store `self._callback`.

---

## Integration Points

- **Must be owned by:** `HardwareManager` — instantiate as `self.lidar = LiDARAdapter(config)`
- **Flask routes must call:** `hardware_manager.lidar.start_scanning()`, `.stop_scanning()`, `.get_status()`
- **Socket.IO streaming task must call:** `hardware_manager.lidar.get_latest_scan()` every 50ms (20 FPS target; consider 100ms / 10 FPS if Pi 4B struggles)
- **`/api/status` route:** Populate `lidar_connected` field from `hardware_manager.lidar.get_status()['connected']`

---

## File Header (MANDATORY per system_style.md §5)

```python
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: lidar_adapter.py
Description: HardwareManager-compliant LiDAR adapter wrapping legacy LiDARReader.
"""
```

---

## Import Whitelist

```python
import threading
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from queue import Empty

# Legacy wrapper (copy LiDARReader class or import from legacy path)
from hardware.lidar_reader import LiDARReader   # adjust path as needed
```

Do NOT import `flask`, `flask_socketio`, `asyncio`, or `serial` directly in this file. `serial` is used inside `LiDARReader` only.

---

## Success Criteria

- [ ] All 7 public methods match contract signatures exactly (type hints included)
- [ ] All 8 acceptance test cases pass
- [ ] `grep -n "lidar_reader\s*=" server.py` → no top-level hits
- [ ] No method body exceeds 50 lines
- [ ] `self._lock` acquired in every public method that reads or writes shared state
- [ ] Auditor approval required before merging