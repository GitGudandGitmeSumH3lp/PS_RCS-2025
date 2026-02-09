"""Receipt Database Manager.

This module handles persistent storage of OCR scan results using SQLite.
It ensures schema integrity, handles concurrent access via retries, and 
provides query methods for retrieval and analytics.

Typical usage example:
    db = ReceiptDatabase()
    db.store_scan(scan_id=123, fields={...}, raw_text="...", ...)
"""

import sqlite3
import threading
import time
from typing import Dict, Optional, Any, List, Union

from src.database.database_manager import DatabaseManager


class ReceiptDatabase:
    """Manages SQLite operations for receipt scans.
    
    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str = "data/database.db") -> None:
        """Initialize database connection and schema.

        Args:
            db_path: Filesystem path to the SQLite database.

        Raises:
            TypeError: If db_path is not a string.
        """
        if not isinstance(db_path, str):
            raise TypeError("db_path must be string")
        
        self.db_path: str = db_path
        self._lock: threading.Lock = threading.Lock()
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create tables and indexes if they do not exist.
        
        Ensures the 'receipt_scans' table exists with correct columns
        and CHECK constraints for data validity.
        """
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = self._get_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS receipt_scans (
                    scan_id INTEGER PRIMARY KEY,
                    tracking_id TEXT,
                    order_id TEXT,
                    rts_code TEXT,
                    rider_id TEXT,
                    buyer_name TEXT,
                    buyer_address TEXT,
                    weight_g INTEGER,
                    quantity INTEGER,
                    payment_type TEXT,
                    confidence REAL NOT NULL,
                    raw_text TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    scan_datetime TEXT,
                    processing_time_ms INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
                    CHECK (weight_g IS NULL OR weight_g >= 0),
                    CHECK (quantity IS NULL OR quantity >= 0),
                    CHECK (processing_time_ms IS NULL OR processing_time_ms >= 0)
                )
            """)
            
            # Create indexes for frequent query patterns
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracking_id ON receipt_scans(tracking_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rts_code ON receipt_scans(rts_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON receipt_scans(timestamp)")
            
            conn.commit()
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def store_scan(
        self,
        scan_id: int,
        fields: Dict[str, Any],
        raw_text: str,
        confidence: float,
        engine: str
    ) -> bool:
        """Store a new scan result in the database.

        Includes retry logic for SQLite locking issues.

        Args:
            scan_id: Unique integer ID for the scan.
            fields: Dictionary of extracted receipt fields.
            raw_text: Full raw text from OCR.
            confidence: Overall confidence score (0.0-1.0).
            engine: Engine name ('tesseract' or 'paddle').

        Returns:
            True if storage was successful, False otherwise.

        Raises:
            ValueError: For invalid input constraints (negative scan_id, etc.).
            sqlite3.IntegrityError: If scan_id already exists.
            RuntimeError: For database connection or execution failures.
        """
        if not isinstance(scan_id, int) or scan_id <= 0:
            raise ValueError("scan_id must be positive integer")
        
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {confidence}")
        
        if engine not in ['tesseract', 'paddle']:
            raise ValueError(f"engine must be 'tesseract' or 'paddle', got {engine}")
        
        conn: Optional[sqlite3.Connection] = None
        
        # Retry loop for database locks
        for attempt in range(3):
            try:
                conn = self._get_connection()
                cursor: sqlite3.Cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO receipt_scans 
                    (scan_id, tracking_id, order_id, rts_code, rider_id, buyer_name, 
                     buyer_address, weight_g, quantity, payment_type, confidence, 
                     raw_text, engine, timestamp, scan_datetime, processing_time_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scan_id,
                    fields.get('tracking_id'),
                    fields.get('order_id'),
                    fields.get('rts_code'),
                    fields.get('rider_id'),
                    fields.get('buyer_name'),
                    fields.get('buyer_address'),
                    fields.get('weight_g'),
                    fields.get('quantity'),
                    fields.get('payment_type'),
                    confidence,
                    raw_text,
                    engine,
                    fields.get('timestamp'),
                    fields.get('scan_datetime'),
                    fields.get('processing_time_ms')
                ))
                
                conn.commit()
                return True
                
            except sqlite3.IntegrityError:
                if conn:
                    conn.rollback()
                raise sqlite3.IntegrityError(f"Scan ID {scan_id} already exists")
            except sqlite3.OperationalError as e:
                # Handle database locked errors with backoff
                if "database is locked" in str(e) and attempt < 2:
                    time.sleep(0.1)
                    continue
                if conn:
                    conn.rollback()
                raise
            except Exception as e:
                if conn:
                    conn.rollback()
                raise RuntimeError(f"Database error: {str(e)}")
            finally:
                if conn:
                    conn.close()
        
        return False
    
    def _get_connection(self) -> sqlite3.Connection:
        """Helper to get a database connection via manager."""
        return DatabaseManager.get_connection(self.db_path)
    
    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific scan by ID.
        
        Args:
            scan_id: The ID to search for.
            
        Returns:
            Dictionary representation of the row, or None if not found.
        """
        conn: sqlite3.Connection = self._get_connection()
        cursor: sqlite3.Cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM receipt_scans WHERE scan_id = ?", (scan_id,))
        row: Optional[tuple] = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        columns: List[str] = [description[0] for description in cursor.description]
        result: Dict[str, Any] = dict(zip(columns, row))
        conn.close()
        
        return result
    
    def get_scans_by_tracking(self, tracking_id: str) -> List[Dict[str, Any]]:
        """Retrieve all scans for a given tracking ID.
        
        Args:
            tracking_id: The tracking ID to filter by.
            
        Returns:
            List of scan records sorted by timestamp descending.
        """
        conn: sqlite3.Connection = self._get_connection()
        cursor: sqlite3.Cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM receipt_scans WHERE tracking_id = ? ORDER BY timestamp DESC",
            (tracking_id,)
        )
        rows: List[tuple] = cursor.fetchall()
        
        if not rows:
            conn.close()
            return []
        
        columns: List[str] = [description[0] for description in cursor.description]
        results: List[Dict[str, Any]] = [dict(zip(columns, row)) for row in rows]
        conn.close()
        
        return results
    
    def get_recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve the most recent scans.
        
        Args:
            limit: Maximum number of records to return.
            
        Returns:
            List of scan records sorted by timestamp descending.
        """
        conn: sqlite3.Connection = self._get_connection()
        cursor: sqlite3.Cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM receipt_scans ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows: List[tuple] = cursor.fetchall()
        
        if not rows:
            conn.close()
            return []
        
        columns: List[str] = [description[0] for description in cursor.description]
        results: List[Dict[str, Any]] = [dict(zip(columns, row)) for row in rows]
        conn.close()
        
        return results