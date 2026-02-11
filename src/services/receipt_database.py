"""Receipt Database Manager – Refactored (SQLAlchemy repository).

Maintains exact public API for backward compatibility.
Delegates all operations to the new thread‑safe ReceiptRepository.
"""

import os
from typing import Any, Dict, List, Optional

from src.database.core import init_db
from src.database.repository import ReceiptRepository


class ReceiptDatabase:
    """Compatibility facade for receipt database operations.

    All public methods retain their original signatures and error behaviour.
    Internal implementation now uses SQLAlchemy with thread‑local sessions.
    """

    def __init__(self, db_path: str = "data/database.db") -> None:
        """Initialise the database connection and repository.

        Args:
            db_path: Filesystem path to the SQLite database file.

        Raises:
            TypeError: If db_path is not a string.
        """
        if not isinstance(db_path, str):
            raise TypeError("db_path must be string")

        # Convert to absolute path if relative
        if not os.path.isabs(db_path):
            # Assume relative to project root; Flask will handle resolution
            db_path = os.path.abspath(db_path)

        database_url = f"sqlite:///{db_path}"
        init_db(database_url)

        self._repository = ReceiptRepository()

    def store_scan(
        self,
        scan_id: int,
        fields: Dict[str, Any],
        raw_text: str,
        confidence: float,
        engine: str,
    ) -> bool:
        """Store a new scan result – delegates to repository."""
        return self._repository.store_scan(
            scan_id, fields, raw_text, confidence, engine
        )

    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific scan by ID – delegates to repository."""
        return self._repository.get_scan(scan_id)

    def get_scans_by_tracking(self, tracking_id: str) -> List[Dict[str, Any]]:
        """Retrieve all scans for a given tracking ID – delegates to repository."""
        return self._repository.get_scans_by_tracking(tracking_id)

    def get_recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve the most recent scans – delegates to repository."""
        return self._repository.get_recent_scans(limit)