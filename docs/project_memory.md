# PROJECT EPISODIC MEMORY
**Purpose:** Persistent storage of lessons and constraints.

## 🚫 LEGACY CONSTRAINTS (DO NOT BREAK)
*   **Hardware Stack:** Arduino (Motor), HuskyLens (Vision), LiDAR (Mapping), USB Camera.
*   **Communication:** Serial Ports are hardcoded (Risk: High).
*   **Frontend:** Vanilla JS + HTML Templates. (No React/Vue build step yet).
*   **Backend:** Python 3.9+ (Flask).

## 🛠️ TECHNICAL DEBT ALERT
*   **API Duplication:** `api_server.py`, `api_server2.py`, etc. must be diffed before deletion.
*   **Database:** Multiple SQLite DBs exist. Consolidate to `src/services/database/core.py`.
*   **Imports:** Moving files will break `from backend import X`. Mass search/replace required.