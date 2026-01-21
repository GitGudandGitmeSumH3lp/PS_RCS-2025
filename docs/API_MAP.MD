# API_MAP.md - V3.5 Robot System Architecture

**Version:** 3.5  
**Generated:** 2026-01-21  
**Status:** Post-Migration Documentation

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Summary](#architecture-summary)
3. [Module Hierarchy](#module-hierarchy)
4. [Hardware Layer](#hardware-layer)
5. [Services Layer](#services-layer)
6. [Web Layer](#web-layer)
7. [Firmware Layer](#firmware-layer)
8. [API Endpoints](#api-endpoints)
9. [Dependencies Map](#dependencies-map)
10. [Migration Notes](#migration-notes)

---

## System Overview

The V3.5 robot system follows a layered architecture pattern with clear separation of concerns:

- **Hardware Layer** (`src/hardware/`): Device drivers and hardware abstraction
- **Services Layer** (`src/services/`): Business logic, API, and data persistence
- **Web Layer** (`web/`): User interfaces and visualization tools
- **Firmware Layer** (`src/firmware/`): Embedded system code for microcontrollers

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│                     WEB LAYER                           │
│  ┌──────────────┐  ┌─────────────────────────────┐    │
│  │   Client     │  │      Visualizers            │    │
│  │  Dashboard   │  │  (Camera/LiDAR/OCR/Husky)   │    │
│  └──────────────┘  └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ HTTP/WebSocket
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   SERVICES LAYER                        │
│  ┌──────────────┐  ┌─────────────────────────────┐    │
│  │  API Server  │  │      Database Core          │    │
│  │   (Routes)   │  │      (Models)               │    │
│  └──────────────┘  └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ Function Calls
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   HARDWARE LAYER                        │
│  ┌────────┐ ┌────────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
│  │ Camera │ │HuskyLens│ │LiDAR │ │ OCR  │ │Motor │    │
│  └────────┘ └────────┘ └──────┘ └──────┘ └──────┘    │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ Serial/I2C/SPI
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   FIRMWARE LAYER                        │
│              Arduino Motor Control                      │
└─────────────────────────────────────────────────────────┘
```

---

## Module Hierarchy

### Root Structure

```
robot-v3.5/
├── src/                    # Core application code
│   ├── hardware/           # Hardware abstraction layer
│   ├── services/           # Business logic and APIs
│   └── firmware/           # Embedded firmware
└── web/                    # Web interfaces
    ├── client/             # Main dashboard/control interface
    └── visualizers/        # Component-specific visualizers
```

---

## Hardware Layer

**Location:** `src/hardware/`  
**Purpose:** Hardware abstraction and device driver implementations

### 📷 Camera Module
**Path:** `src/hardware/camera/`

| File | Purpose |
|------|---------|
| `discovery.py` | Camera device detection and enumeration |
| `__init__.py` | Module initialization and public API exports |

**Responsibilities:**
- Auto-detect available camera devices
- Provide unified camera interface
- Handle camera initialization and configuration

---

### 👁️ HuskyLens Module
**Path:** `src/hardware/huskylens/`

| File | Purpose |
|------|---------|
| `client.py` | Communication protocol implementation for HuskyLens AI camera |
| `handler.py` | High-level API for object detection and tracking |
| `standalone_app.py` | Independent application for testing HuskyLens functionality |
| `__init__.py` | Module exports |

**Responsibilities:**
- Interface with HuskyLens AI vision sensor
- Object detection, face recognition, color tracking
- Protocol handling (I2C/UART communication)
- Standalone testing and calibration

**Key Features:**
- Object detection and classification
- Face recognition
- Line tracking
- Tag recognition

---

### 🎯 LiDAR Module
**Path:** `src/hardware/lidar/`

| File | Purpose |
|------|---------|
| `discovery.py` | LiDAR device detection and port enumeration |
| `handler.py` | Legacy LiDAR data processing and interface |
| `handler_v2.py` | Improved LiDAR handler with enhanced features |
| `__init__.py` | Module exports |

**Responsibilities:**
- LiDAR sensor communication
- Point cloud data acquisition
- Distance measurement and obstacle detection
- Environmental mapping

**Migration Note:** `handler_v2.py` represents an improved implementation. Consider deprecating `handler.py` in future releases.

---

### ⚙️ Motor Module
**Path:** `src/hardware/motor/`

| File | Purpose |
|------|---------|
| `controller.py` | Motor control abstraction and movement primitives |
| `__init__.py` | Module exports |

**Responsibilities:**
- Motor speed and direction control
- Movement primitives (forward, backward, turn, stop)
- Communication with Arduino firmware
- PWM signal management

**Dependencies:** Requires `src/firmware/arduino/motor_control.ino` on Arduino

---

### 📝 OCR Module
**Path:** `src/hardware/ocr/`

| File | Purpose |
|------|---------|
| `handler.py` | Main OCR processing coordinator |
| `knowledge_base.py` | Domain-specific text recognition rules and patterns |
| `ocr.py` | Standard OCR implementation |
| `ocr_simple.py` | Lightweight OCR for resource-constrained scenarios |
| `preprocessor.py` | Image preprocessing for improved OCR accuracy |
| `__init__.py` | Module exports |

**Optimized Submodule:** `src/hardware/ocr/optimized/`

| File | Purpose |
|------|---------|
| `knowledge_base.py` | Performance-optimized pattern matching |
| `ocr.py` | Optimized OCR engine with improved accuracy |
| `__init__.py` | Optimized module exports |

**Responsibilities:**
- Text extraction from camera images
- Image preprocessing (binarization, noise removal, deskewing)
- Knowledge-based text validation
- Context-aware recognition

**Use Cases:**
- Sign reading
- Label detection
- Text-based navigation

---

## Services Layer

**Location:** `src/services/`  
**Purpose:** Business logic, API endpoints, and data management

### 🌐 API Service
**Path:** `src/services/api/`

| File/Directory | Purpose |
|----------------|---------|
| `server.py` | Main API server initialization and configuration |
| `routes/` | API endpoint definitions (currently empty, to be populated) |
| `__init__.py` | Service exports |

**Responsibilities:**
- RESTful API endpoint hosting
- Request routing and validation
- Hardware module orchestration
- WebSocket connections for real-time data

**Expected Endpoints (to be implemented in `routes/`):**
- `/api/camera/*` - Camera control and streaming
- `/api/motor/*` - Movement commands
- `/api/lidar/*` - LiDAR data retrieval
- `/api/ocr/*` - Text recognition requests
- `/api/huskylens/*` - AI vision operations

---

### 💾 Database Service
**Path:** `src/services/database/`

| File/Directory | Purpose |
|----------------|---------|
| `core.py` | Database connection management and query abstractions |
| `models/` | Data models and ORM definitions (currently empty) |
| `__init__.py` | Service exports |

**Responsibilities:**
- Persistent data storage
- Sensor data logging
- Configuration management
- Mission/task history

**Expected Models (to be implemented in `models/`):**
- Telemetry records
- Mission logs
- Calibration data
- User preferences

---

## Web Layer

**Location:** `web/`  
**Purpose:** User interfaces and data visualization

### 🖥️ Client Dashboard
**Path:** `web/client/`

| File | Purpose |
|------|---------|
| `app.py` | Main Flask/FastAPI application for robot control dashboard |

**Static Assets:** `web/client/static/`

| File | Purpose |
|------|---------|
| `css/styles.css` | Dashboard styling |
| `js/datatable.js` | Data table component for telemetry display |
| `js/main.js` | Core client-side logic |
| `js/script.js` | Additional UI interactions |
| `models/` | 3D models for visualization (currently empty) |

**Templates:** `web/client/templates/`

| File | Purpose |
|------|---------|
| `index.html` | Landing page |
| `dashboard.html` | Main telemetry and monitoring dashboard |
| `control.html` | Manual robot control interface |

**Responsibilities:**
- Unified control interface
- Real-time telemetry display
- Manual override controls
- System status monitoring

---

### 📊 Visualizers
**Path:** `web/visualizers/`  
**Purpose:** Component-specific debugging and monitoring tools

#### Camera Visualizer
**Path:** `web/visualizers/camera/`

| File | Purpose |
|------|---------|
| `app.py` | Flask app for camera stream visualization |
| `templates/index.html` | Camera feed display interface |

**Features:**
- Live camera feed
- Frame capture
- Camera settings adjustment

---

#### HuskyLens Visualizer
**Path:** `web/visualizers/huskylens/`

| File | Purpose |
|------|---------|
| `templates/` | HuskyLens detection visualization (app.py missing - to be implemented) |

**Expected Features:**
- Object detection bounding boxes
- Recognition confidence display
- Real-time tracking visualization

---

#### LiDAR Visualizer
**Path:** `web/visualizers/lidar/`

| File | Purpose |
|------|---------|
| `app.py` | Flask app for LiDAR point cloud visualization |
| `templates/index.html` | Main visualizer page |
| `templates/lidar_visualizer.html` | Interactive LiDAR data display |

**Features:**
- 2D/3D point cloud rendering
- Distance measurements
- Obstacle detection overlay
- Real-time scanning

---

#### OCR Visualizer
**Path:** `web/visualizers/ocr/`

| File | Purpose |
|------|---------|
| `app.py` | Flask app for OCR testing and debugging |
| `templates/index.html` | OCR result display interface |

**Features:**
- Live text detection
- Preprocessing stage visualization
- Confidence scoring
- Knowledge base matching results

---

#### Shared Resources
**Path:** `web/visualizers/shared/`

**Purpose:** Common UI components, CSS, and JavaScript libraries shared across visualizers

---

## Firmware Layer

**Location:** `src/firmware/`  
**Purpose:** Embedded system code for microcontrollers

### Arduino Motor Control
**Path:** `src/firmware/arduino/motor_control.ino`

**Responsibilities:**
- Low-level motor PWM control
- Serial command protocol implementation
- Emergency stop handling
- Hardware safety checks

**Communication Protocol:**
- Interface: Serial (USB/UART)
- Baud Rate: TBD (typically 9600 or 115200)
- Command Format: Binary or ASCII protocol

**Commands (inferred):**
- Motor speed control (0-255 PWM)
- Direction control (forward/reverse)
- Emergency stop
- Status query

---

## API Endpoints

**Base URL:** `http://<robot-ip>:<port>/api`

### Expected REST API Structure

#### Motor Control
```
POST   /api/motor/move
POST   /api/motor/stop
GET    /api/motor/status
PUT    /api/motor/speed
```

#### Camera
```
GET    /api/camera/stream
GET    /api/camera/capture
POST   /api/camera/settings
GET    /api/camera/list
```

#### LiDAR
```
GET    /api/lidar/scan
GET    /api/lidar/stream
GET    /api/lidar/point-cloud
POST   /api/lidar/calibrate
```

#### OCR
```
POST   /api/ocr/recognize
GET    /api/ocr/last-result
POST   /api/ocr/configure
```

#### HuskyLens
```
GET    /api/huskylens/detect
GET    /api/huskylens/track
POST   /api/huskylens/mode
GET    /api/huskylens/status
```

#### Database
```
GET    /api/data/telemetry
GET    /api/data/logs
POST   /api/data/mission
GET    /api/data/mission/:id
```

---

## Dependencies Map

### Hardware Layer Dependencies

```
hardware/motor/controller.py
  ├─→ firmware/arduino/motor_control.ino (Serial communication)
  └─→ pyserial (Python package)

hardware/camera/discovery.py
  └─→ opencv-python (cv2)

hardware/lidar/handler_v2.py
  ├─→ rplidar or ydlidar library
  └─→ numpy

hardware/ocr/ocr.py
  ├─→ pytesseract
  ├─→ opencv-python
  └─→ PIL/Pillow

hardware/huskylens/client.py
  └─→ smbus2 or pyserial (I2C/UART)
```

### Services Layer Dependencies

```
services/api/server.py
  ├─→ FastAPI or Flask
  ├─→ hardware/* modules
  └─→ services/database/core.py

services/database/core.py
  └─→ SQLAlchemy or SQLite3
```

### Web Layer Dependencies

```
web/client/app.py
  ├─→ Flask or FastAPI
  └─→ services/api/server.py

web/visualizers/*/app.py
  ├─→ Flask
  └─→ hardware/* modules (direct access for visualization)
```

---

## Migration Notes

### From Legacy to V3.5

#### Structural Changes

1. **Hardware Abstraction**
   - Legacy: Monolithic hardware drivers
   - V3.5: Modular `src/hardware/` with discovery patterns

2. **Service Layer Introduction**
   - Legacy: Direct hardware access from web layer
   - V3.5: Services layer provides API abstraction

3. **Web Reorganization**
   - Legacy: Single web application
   - V3.5: Separated client dashboard and component visualizers

4. **Firmware Isolation**
   - Legacy: Arduino code mixed with Python
   - V3.5: Clean separation in `src/firmware/`

#### Pending Implementations

**High Priority:**
- [ ] Implement API routes in `src/services/api/routes/`
- [ ] Define database models in `src/services/database/models/`
- [ ] Create HuskyLens visualizer app (`web/visualizers/huskylens/app.py`)
- [ ] Populate shared visualizer resources

**Medium Priority:**
- [ ] Add 3D models to `web/client/static/models/`
- [ ] Implement comprehensive error handling across all modules
- [ ] Add unit tests for each hardware module

**Low Priority:**
- [ ] Deprecate `src/hardware/lidar/handler.py` in favor of `handler_v2.py`
- [ ] Consolidate OCR implementations (standard vs. optimized)
- [ ] Create comprehensive API documentation

#### Breaking Changes from Legacy

1. **Import Paths:** All imports now use absolute paths from `src/`
2. **Configuration:** Centralized configuration (location TBD)
3. **API Interface:** RESTful API replaces direct function calls
4. **Database Schema:** New normalized schema in `services/database/`

---

## Quick Start Guide

### Running Individual Components

```bash
# Start API server
python -m src.services.api.server

# Run client dashboard
python -m web.client.app

# Launch LiDAR visualizer
python -m web.visualizers.lidar.app

# Test HuskyLens standalone
python -m src.hardware.huskylens.standalone_app
```

### Development Workflow

1. Hardware testing: Use standalone apps and visualizers
2. API development: Implement routes in `services/api/routes/`
3. Integration: Connect web client to API endpoints
4. Deployment: Package entire system for robot deployment

---

## Contact & Contributions

- **Architecture Questions:** Review this document and module docstrings
- **API Changes:** Update both code and this API_MAP.md
- **New Modules:** Follow existing patterns and update dependency map

**Last Updated:** 2026-01-21  
**Document Version:** 1.0  
**System Version:** 3.5