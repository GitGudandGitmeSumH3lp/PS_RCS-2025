# API MAP LITE (V3.5)
**Purpose:** Token-efficient file index for AI Agents.
**Source:** `docs/API_MAP.md`

## 1. HARDWARE LAYER (`src/hardware/`)
*   `src/hardware/camera/discovery.py`
*   `src/hardware/camera/__init__.py`
*   `src/hardware/huskylens/client.py`
*   `src/hardware/huskylens/handler.py`
*   `src/hardware/huskylens/standalone_app.py`
*   `src/hardware/huskylens/__init__.py`
*   `src/hardware/lidar/discovery.py`
*   `src/hardware/lidar/handler.py`
*   `src/hardware/lidar/handler_v2.py`
*   `src/hardware/lidar/__init__.py`
*   `src/hardware/motor/controller.py`
*   `src/hardware/motor/__init__.py`
*   `src/hardware/ocr/handler.py`
*   `src/hardware/ocr/knowledge_base.py`
*   `src/hardware/ocr/ocr.py`
*   `src/hardware/ocr/ocr_simple.py`
*   `src/hardware/ocr/preprocessor.py`
*   `src/hardware/ocr/__init__.py`
*   `src/hardware/ocr/optimized/knowledge_base.py`
*   `src/hardware/ocr/optimized/ocr.py`
*   `src/hardware/ocr/optimized/__init__.py`

## 2. SERVICES LAYER (`src/services/`)
*   `src/services/api/server.py`
*   `src/services/api/routes/` (Pending)
*   `src/services/api/__init__.py`
*   `src/services/database/core.py`
*   `src/services/database/models/` (Pending)
*   `src/services/database/__init__.py`

## 3. FIRMWARE LAYER (`src/firmware/`)
*   `src/firmware/arduino/motor_control.ino`

## 4. WEB LAYER (`web/`)
### Client
*   `web/client/app.py`
*   `web/client/static/js/main.js`
*   `web/client/static/js/script.js`
*   `web/client/static/js/datatable.js`
*   `web/client/static/css/styles.css`
*   `web/client/templates/index.html`
*   `web/client/templates/dashboard.html`
*   `web/client/templates/control.html`

### Visualizers
*   `web/visualizers/camera/app.py`
*   `web/visualizers/camera/templates/index.html`
*   `web/visualizers/lidar/app.py`
*   `web/visualizers/lidar/templates/index.html`
*   `web/visualizers/lidar/templates/lidar_visualizer.html`
*   `web/visualizers/ocr/app.py`
*   `web/visualizers/ocr/templates/index.html`