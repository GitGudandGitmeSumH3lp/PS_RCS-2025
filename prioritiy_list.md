**SYSTEM ONLINE. 🟢**

I have analyzed the directory structure of your **Legacy Robot Control System**. You are currently in **Scenario 4 (Legacy Integration)**.

Here is the architectural breakdown and your roadmap to V4.0 compliance.

### 1. 🏗️ THE CORE MONOLITH
**Target:** `backend/`
This is the "Brain" of your legacy system. It contains the database connection, hardware controllers, and the API layer.
*   **Evidence:** It houses `database.py`, `motor_controller.py`, and multiple versions of `api_server`. The `frontend/` appears to be a consumer of this backend, likely via Flask/HTTP.

### 2. 🛰️ THE SATELLITES (Standalone Tools)
These appear to be isolated debugging tools or simulators, likely developed to test hardware without the full robot.
1.  **`Camera-visualizer/`**: A standalone Flask app for camera feeds.
2.  **`Huskylens-visualizer/`**: A distinct utility for the AI camera.
3.  **`Lidar-visualizer/`**: Specific tool for Lidar mapping.
4.  **`OCR_sim/`**: A simulation environment for the OCR logic (likely for testing without the robot arm).

### 3. ⚠️ DUPLICATION RISK (High Severity)
Your codebase exhibits significant "Version-by-Filename" artifacting. This is dangerous and must be resolved by the **Architect** immediately.

**Critical Conflicts:**
*   **The API Split:** `backend/api_server.py` vs `backend/api_server2.py` vs `backend/api_serverbase.py`. *Which one is running in production?*
*   **Lidar Logic:** `backend/lidar_handler.py` vs `backend/lidar_handler2.py`.
*   **OCR Logic:** `OCR_sim/ocr.py` vs `ocr_optimized.py` vs `ocr_simple.py`.
*   **Frontend Clutter:** `dashboard.html` vs `dashboard copy.html`, `index.html` vs `index2.html`.

### 4. 📋 PRIORITY LIST (For V4.0 Contract Generation)
To bring this system under **Packet Prompting V4.0** control, we must reverse-engineer the "Source of Truth." Do not start with the satellites. Start with the Core.

**Ingest these files in this exact order to generate your core Contracts:**

1.  **`backend/database.py`**
    *   **Why:** This defines your data models (`robot_data.db`). We cannot build contracts without knowing the data structure.
2.  **`backend/api_server.py`** (and `api_server2.py` if different)
    *   **Why:** We need to extract the **Interface Contract**. What endpoints exist? What JSON do they return? We will merge these into a single `API_SPEC.md`.
3.  **`backend/motor_controller.py`**
    *   **Why:** This contains the core physical logic (movement). It likely needs a **Hardware Interface Contract**.
4.  **`backend/lidar_handler.py`**
    *   **Why:** Complex sensor logic often breeds bugs. We need to standardize how Lidar data is fetched and parsed.
5.  **`arduino/wheels/wheels.ino`**
    *   **Why:** The Python backend controls this firmware. We need to verify the Serial Protocol matches the Python code.

---

### 🛑 TOKEN EFFICIENCY WARNING
You pasted the entire `venv/` directory.
**Instruction:** In future prompts, use `ls -R -I venv` or similar to exclude library files. This wasted ~50% of your context window on irrelevant library metadata.

---

✅ **Orchestration Complete**
📍 **Current State:** Legacy Analysis Finished.
👉 **Next Move:** Load **[[00_analyst]]** (or **[[legacy_integrator]]**).
🔑 **Key Instruction:** "Paste the content of `backend/database.py` and `backend/api_server.py`. Ask the agent to generate a **Unified Data & API Contract**."