import sqlite3
from typing import Any, Dict, List, Optional
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from src.database.core import get_session
from src.database.models import ReceiptScan

class ReceiptRepository:
    @staticmethod
    def _row_to_dict(scan: ReceiptScan) -> Dict[str, Any]:
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
        if 'timestamp' not in fields or not fields['timestamp']:
            raise ValueError("fields must contain a non-empty 'timestamp'")
        timestamp_val = fields['timestamp']
        if not isinstance(timestamp_val, str) or not timestamp_val.strip():
            raise ValueError("timestamp cannot be empty")

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
                    timestamp=fields["timestamp"],
                    scan_datetime=fields.get("scan_datetime"),
                    processing_time_ms=fields.get("processing_time_ms"),
                )
                session.add(receipt)
            return True
        except SAIntegrityError as e:
            if "UNIQUE constraint failed: receipt_scans.scan_id" in str(e):
                raise sqlite3.IntegrityError(f"Scan ID {scan_id} already exists") from e
            raise RuntimeError(f"Database integrity error: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Database error: {e}") from e

    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        try:
            with get_session() as session:
                scan = session.query(ReceiptScan).filter_by(scan_id=scan_id).first()
                return self._row_to_dict(scan) if scan else None
        except Exception as e:
            raise RuntimeError(f"Database error: {e}") from e

    def get_scans_by_tracking(self, tracking_id: str) -> List[Dict[str, Any]]:
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