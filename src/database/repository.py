"""Repository for receipt scan database operations.

Encapsulates all SQLAlchemy queries and provides thread‑safe methods
matching the original public API.
"""

import sqlite3
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.orm import Session

from src.database.core import get_session
from src.database.models import ReceiptScan


class ReceiptRepository:
    """Thread‑safe repository for receipt_scans table."""

    @staticmethod
    def _row_to_dict(scan: ReceiptScan) -> Dict[str, Any]:
        """Convert ORM instance to dictionary (column name → value)."""
        return {
            c.name: getattr(scan, c.name)
            for c in scan.__table__.columns
        }

    def store_scan(
        self,
        scan_id: int,
        fields: Dict[str, Any],
        raw_text: str,
        confidence: float,
        engine: str,
    ) -> bool:
        """Store a new receipt scan.

        Args:
            scan_id: Unique positive integer ID.
            fields: Dictionary of extracted fields.
            raw_text: Full OCR text.
            confidence: Score between 0.0 and 1.0.
            engine: 'tesseract' or 'paddle'.

        Returns:
            True if stored successfully.

        Raises:
            ValueError: If scan_id ≤ 0, confidence out of range, or engine invalid.
            sqlite3.IntegrityError: If scan_id already exists.
            RuntimeError: For any other database failure.
        """
        # --- Input validation ---
        if not isinstance(scan_id, int) or scan_id <= 0:
            raise ValueError("scan_id must be positive integer")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {confidence}"
            )
        if engine not in ("tesseract", "paddle"):
            raise ValueError(
                f"engine must be 'tesseract' or 'paddle', got {engine}"
            )

        # --- Database insert ---
        try:
            with get_session() as session:
                receipt = ReceiptScan(
                    scan_id=scan_id,
                    tracking_id=fields.get("tracking_id"),
                    order_id=fields.get("order_id"),
                    rts_code=fields.get("rts_code"),
                    rider_id=fields.get("rider_id"),
                    buyer_name=fields.get("buyer_name"),
                    buyer_address=fields.get("buyer_address"),
                    weight_g=fields.get("weight_g"),
                    quantity=fields.get("quantity"),
                    payment_type=fields.get("payment_type"),
                    confidence=confidence,
                    raw_text=raw_text,
                    engine=engine,
                    timestamp=fields.get("timestamp"),
                    scan_datetime=fields.get("scan_datetime"),
                    processing_time_ms=fields.get("processing_time_ms"),
                )
                session.add(receipt)
            return True
        except SAIntegrityError as e:
            # Duplicate scan_id -> translate to sqlite3.IntegrityError
            raise sqlite3.IntegrityError(f"Scan ID {scan_id} already exists") from e
        except Exception as e:
            raise RuntimeError(f"Database error: {e}") from e

    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a scan by its primary key.

        Args:
            scan_id: The scan ID to look up.

        Returns:
            Dictionary representation of the row, or None if not found.

        Raises:
            RuntimeError: If a database error occurs.
        """
        try:
            with get_session() as session:
                scan = session.query(ReceiptScan).filter_by(scan_id=scan_id).first()
                return self._row_to_dict(scan) if scan else None
        except Exception as e:
            raise RuntimeError(f"Database error: {e}") from e

    def get_scans_by_tracking(self, tracking_id: str) -> List[Dict[str, Any]]:
        """Retrieve all scans for a given tracking ID.

        Args:
            tracking_id: The tracking ID to filter by.

        Returns:
            List of scan dicts, sorted by timestamp descending (most recent first).

        Raises:
            RuntimeError: If a database error occurs.
        """
        try:
            with get_session() as session:
                scans = (
                    session.query(ReceiptScan)
                    .filter_by(tracking_id=tracking_id)
                    .order_by(ReceiptScan.timestamp.desc())
                    .all()
                )
                return [self._row_to_dict(s) for s in scans]
        except Exception as e:
            raise RuntimeError(f"Database error: {e}") from e

    def get_recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve the most recent scans.

        Args:
            limit: Maximum number of records to return (negative/zero treated as 0).

        Returns:
            List of scan dicts, sorted by timestamp descending.

        Raises:
            RuntimeError: If a database error occurs.
        """
        if limit < 0:
            limit = 0
        try:
            with get_session() as session:
                scans = (
                    session.query(ReceiptScan)
                    .order_by(ReceiptScan.timestamp.desc())
                    .limit(limit)
                    .all()
                )
                return [self._row_to_dict(s) for s in scans]
        except Exception as e:
            raise RuntimeError(f"Database error: {e}") from e