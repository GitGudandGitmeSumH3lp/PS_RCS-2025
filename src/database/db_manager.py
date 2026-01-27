"""Database interaction layer for storing scan sessions.

This module manages SQLite connections, handles schema creation,
and provides methods to save and retrieve scan data safely.
"""

import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List

from flask import abort


class DatabaseManager:
    """Manages the SQLite database connection and operations.
    
    Attributes:
        db_path: Filepath to the SQLite database.
    """
    
    def __init__(self, db_path: str) -> None:
        """Initialize the database manager and ensure schema exists.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT UNIQUE NOT NULL,
                    filepath TEXT NOT NULL,
                    point_count INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections with retry logic.
        
        Handles database locking issues by retrying connections.
        Automatically commits on success or rolls back on failure.
        
        Yields:
            A configured sqlite3.Connection object.
            
        Raises:
            sqlite3.OperationalError: If connection fails after retries.
        """
        retries = 3
        for attempt in range(retries):
            try:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                try:
                    yield conn
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.close()
                break
            except sqlite3.OperationalError as e:
                # Handle database lock by waiting briefly
                if "database is locked" in str(e) and attempt < retries - 1:
                    time.sleep(0.1)
                    continue
                raise
    
    def save_scan_session(
        self,
        session_name: str,
        scan_data_filepath: str,
        point_count: int
    ) -> int:
        """Records a new scan session in the database.
        
        Args:
            session_name: Unique name for the session.
            scan_data_filepath: Path to the raw data file.
            point_count: Number of data points in the scan.
        
        Returns:
            The primary key ID of the inserted row.
        
        Raises:
            sqlite3.IntegrityError: If session_name already exists.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO scan_sessions (session_name, filepath, point_count) VALUES (?, ?, ?)",
                    (session_name, scan_data_filepath, point_count)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise sqlite3.IntegrityError(f"Scan session '{session_name}' already exists")
    
    def get_scan_sessions(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieves a paginated list of scan sessions.
        
        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
        
        Returns:
            List of dictionaries containing session metadata.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, session_name, filepath, point_count, created_at FROM scan_sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            rows = cursor.fetchall()
        
        return [
            {
                "id": row["id"],
                "session_name": row["session_name"],
                "filepath": row["filepath"],
                "point_count": row["point_count"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]