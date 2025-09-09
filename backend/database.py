# database.py
# SQLite wrapper for robot system data logging

import sqlite3
import time
from datetime import datetime
from pathlib import Path
import logging

# ----------------------------
# CONFIGURATION
# ----------------------------
DB_PATH = "robot_data.db"

# SQL schema
CREATE_SCANS_TABLE = '''
CREATE TABLE IF NOT EXISTS scans (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    scan_type TEXT,
    note TEXT
);
'''

CREATE_POINTS_TABLE = '''
CREATE TABLE IF NOT EXISTS points (
    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER,
    angle REAL NOT NULL,
    distance REAL NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scans (scan_id) ON DELETE CASCADE
);
'''

CREATE_OBJECTS_TABLE = '''
CREATE TABLE IF NOT EXISTS objects (
    object_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER,
    label TEXT,
    x REAL,
    y REAL,
    width REAL,
    height REAL,
    algorithm TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_id) REFERENCES scans (scan_id) ON DELETE CASCADE
);
'''

CREATE_OCR_TABLE = '''
CREATE TABLE IF NOT EXISTS ocr_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER,
    order_id TEXT,
    tracking_number TEXT,
    buyer_name TEXT,
    address TEXT,
    weight INTEGER,
    quantity INTEGER,
    rts_code TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_id) REFERENCES scans (scan_id) ON DELETE CASCADE
);
'''

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        self._initialize()

    def _initialize(self):
        """Create database and tables if they don't exist."""
        self._execute_query(CREATE_SCANS_TABLE)
        self._execute_query(CREATE_POINTS_TABLE)
        self._execute_query(CREATE_OBJECTS_TABLE)
        self._execute_query(CREATE_OCR_TABLE)
        self.logger.info(f"Database initialized at {self.db_path.absolute()}")

    def _get_connection(self):
        """Create a new DB connection (thread-safe)."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn

    def _execute_query(self, query, params=()):
        """Execute a write query (INSERT, CREATE, etc.)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Database error: {e}")
            return None
        finally:
            conn.close()

    def _execute_read_query(self, query, params=()):
        """Execute a read query (SELECT)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Read error: {e}")
            return []
        finally:
            conn.close()

    # ----------------------------
    # SCAN METHODS
    # ----------------------------

    def create_scan(self, scan_type="unknown", note=""):
        """
        Start a new scan session.
        Returns scan_id.
        """
        query = "INSERT INTO scans (timestamp, scan_type, note) VALUES (?, ?, ?)"
        scan_id = self._execute_query(query, (datetime.now(), scan_type, note))
        return scan_id

    # ----------------------------
    # LIDAR POINTS METHODS
    # ----------------------------

    def add_point(self, scan_id, angle, distance, x, y):
        """
        Add a single LiDAR point to a scan.
        """
        query = '''
        INSERT INTO points (scan_id, angle, distance, x, y)
        VALUES (?, ?, ?, ?, ?)
        '''
        self._execute_query(query, (scan_id, angle, distance, x, y))

    def add_points_bulk(self, scan_id, points_list):
        """
        Add multiple points in one transaction.
        points_list = [(angle, distance, x, y), ...]
        """
        query = '''
        INSERT INTO points (scan_id, angle, distance, x, y)
        VALUES (?, ?, ?, ?, ?)
        '''
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            data = [(scan_id, a, d, x, y) for (a, d, x, y) in points_list]
            cursor.executemany(query, data)
            conn.commit()
        except Exception as e:
            self.logger.error(f"Bulk insert error: {e}")
        finally:
            conn.close()

    # ----------------------------
    # OBJECT DETECTION METHODS
    # ----------------------------

    def add_object(self, scan_id, label, x, y, width, height, algorithm):
        """
        Add detected object to database.
        """
        query = '''
        INSERT INTO objects (scan_id, label, x, y, width, height, algorithm)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        self._execute_query(query, (scan_id, label, x, y, width, height, algorithm))

    # ----------------------------
    # OCR METHODS
    # ----------------------------

    def add_ocr_result(self, scan_id, data):
        """
        Add OCR result to database.
        """
        query = '''
        INSERT INTO ocr_results 
        (scan_id, order_id, tracking_number, buyer_name, address, weight, quantity, rts_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        self._execute_query(query, (
            scan_id,
            data.get('order_id', ''),
            data.get('tracking_number', ''),
            data.get('buyer_name', ''),
            data.get('address', ''),
            data.get('weight', 0),
            data.get('quantity', 0),
            data.get('rts_code', '')
        ))

    # ----------------------------
    # QUERY METHODS
    # ----------------------------

    def get_latest_scan_id(self):
        """Get the most recent scan_id."""
        query = "SELECT scan_id FROM scans ORDER BY timestamp DESC LIMIT 1"
        result = self._execute_read_query(query)
        return result[0]["scan_id"] if result else None

    def get_scan(self, scan_id):
        """Get all points from a specific scan."""
        query = '''
        SELECT angle, distance, x, y FROM points
        WHERE scan_id = ?
        ORDER BY rowid
        '''
        rows = self._execute_read_query(query, (scan_id,))
        return [dict(row) for row in rows]

    def get_all_scans(self):
        """List all scan sessions."""
        query = "SELECT scan_id, timestamp, scan_type, note FROM scans ORDER BY timestamp DESC"
        rows = self._execute_read_query(query)
        return [dict(row) for row in rows]

    def get_objects_for_scan(self, scan_id):
        """Get all objects detected in a scan."""
        query = '''
        SELECT label, x, y, width, height, algorithm FROM objects
        WHERE scan_id = ?
        ORDER BY timestamp
        '''
        rows = self._execute_read_query(query, (scan_id,))
        return [dict(row) for row in rows]

    def get_latest_ocr_result(self):
        """Get the most recent OCR result."""
        query = '''
        SELECT * FROM ocr_results
        ORDER BY timestamp DESC LIMIT 1
        '''
        result = self._execute_read_query(query)
        return dict(result[0]) if result else None

    def delete_scan(self, scan_id):
        """Delete a scan and all associated data."""
        query = "DELETE FROM scans WHERE scan_id = ?"
        self._execute_query(query, (scan_id,))

    def clear_all_data(self):
        """⚠️ Delete all data."""
        self._execute_query("DELETE FROM ocr_results")
        self._execute_query("DELETE FROM objects")
        self._execute_query("DELETE FROM points")
        self._execute_query("DELETE FROM scans")
        # Reset autoincrement
        self._execute_query("DELETE FROM sqlite_sequence WHERE name='scans'")
        self._execute_query("DELETE FROM sqlite_sequence WHERE name='points'")
        self._execute_query("DELETE FROM sqlite_sequence WHERE name='objects'")
        self._execute_query("DELETE FROM sqlite_sequence WHERE name='ocr_results'")
        self.logger.info("All data cleared.")

# Example usage
if __name__ == "__main__":
    db = Database()
    
    # Create a new scan
    scan_id = db.create_scan(scan_type="test", note="Test scan")
    print(f"Created scan with ID: {scan_id}")
    
    # Add some sample data
    db.add_point(scan_id, 45.0, 1000.0, 707.1, 707.1)
    db.add_object(scan_id, "Box", 100, 150, 50, 30, "Object Detection")
    
    ocr_data = {
        'order_id': 'ABC123',
        'tracking_number': '9876543210',
        'buyer_name': 'John Doe',
        'address': '123 Main St',
        'weight': 500,
        'quantity': 2,
        'rts_code': 'RTS-BUL-SJDM-MZN1-A1'
    }
    db.add_ocr_result(scan_id, ocr_data)
    
    # Retrieve data
    points = db.get_scan(scan_id)
    objects = db.get_objects_for_scan(scan_id)
    ocr_result = db.get_latest_ocr_result()
    
    print("Points:", points)
    print("Objects:", objects)
    print("OCR Result:", ocr_result)