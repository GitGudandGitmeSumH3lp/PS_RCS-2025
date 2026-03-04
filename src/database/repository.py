# src/database/repository.py
"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/database/repository.py
Description: Synchronous repository for receipt scans using SQLAlchemy.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database.core import get_session
from src.database.models import ReceiptScan

logger = logging.getLogger(__name__)


class ReceiptDatabase:
    """Synchronous repository for receipt scan operations."""

    def __init__(self) -> None:
        """Initialize repository (no async setup needed)."""
        # Session management is handled via get_session()
        pass

    def store_scan(
        self,
        scan_id: int,
        fields: Dict[str, Any],
        raw_text: str,
        confidence: float,
        engine: str,
    ) -> bool:
        """Store a receipt scan in the database.

        Args:
            scan_id: Unique scan identifier.
            fields: Dictionary of extracted fields (must include timestamp).
            raw_text: Full raw OCR text.
            confidence: Overall confidence (0.0-1.0).
            engine: OCR engine used.

        Returns:
            True if stored successfully, False otherwise.
        """
        try:
            with get_session() as session:
                # Ensure timestamp exists and is valid
                timestamp_str = fields.get('timestamp')
                if not timestamp_str:
                    timestamp_str = datetime.utcnow().isoformat()

                # Create ReceiptScan instance
                scan = ReceiptScan(
                    scan_id=scan_id,
                    tracking_id=fields.get('tracking_id'),
                    order_id=fields.get('order_id'),
                    rts_code=fields.get('rts_code'),
                    rider_id=fields.get('rider_id'),
                    buyer_name=fields.get('buyer_name'),
                    buyer_address=fields.get('buyer_address'),
                    weight_g=fields.get('weight_g'),
                    quantity=fields.get('quantity'),
                    payment_type=fields.get('payment_type'),
                    raw_text=raw_text,
                    confidence=confidence,
                    engine=engine,
                    timestamp=timestamp_str,
                )
                session.add(scan)
                # commit handled by context manager
                logger.info(f"Stored scan {scan_id} in database.")
                return True
        except SQLAlchemyError as e:
            logger.error(f"Database error storing scan {scan_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing scan {scan_id}: {e}")
            return False

    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a scan by its ID.

        Args:
            scan_id: Scan identifier.

        Returns:
            Dictionary of scan fields, or None if not found.
        """
        try:
            with get_session() as session:
                scan = session.query(ReceiptScan).filter_by(scan_id=scan_id).first()
                if scan:
                    return {
                        'scan_id': scan.scan_id,
                        'tracking_id': scan.tracking_id,
                        'order_id': scan.order_id,
                        'rts_code': scan.rts_code,
                        'rider_id': scan.rider_id,
                        'buyer_name': scan.buyer_name,
                        'buyer_address': scan.buyer_address,
                        'weight_g': scan.weight_g,
                        'quantity': scan.quantity,
                        'payment_type': scan.payment_type,
                        'raw_text': scan.raw_text,
                        'confidence': scan.confidence,
                        'engine': scan.engine,
                        'timestamp': scan.timestamp,
                    }
                return None
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving scan {scan_id}: {e}")
            return None

    def get_recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve the most recent scans.

        Args:
            limit: Maximum number of scans to return.

        Returns:
            List of scan dictionaries (latest first).
        """
        try:
            with get_session() as session:
                scans = (
                    session.query(ReceiptScan)
                    .order_by(ReceiptScan.timestamp.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        'scan_id': s.scan_id,
                        'tracking_id': s.tracking_id,
                        'buyer_name': s.buyer_name,
                        'confidence': s.confidence,
                        'timestamp': s.timestamp,
                    }
                    for s in scans
                ]
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving recent scans: {e}")
            return []

    def get_scan_by_tracking(self, tracking_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a scan by its tracking ID.

        Args:
            tracking_id: Tracking number.

        Returns:
            Dictionary of scan fields, or None if not found.
        """
        try:
            with get_session() as session:
                scan = session.query(ReceiptScan).filter_by(tracking_id=tracking_id).first()
                if scan:
                    return {
                        'scan_id': scan.scan_id,
                        'tracking_id': scan.tracking_id,
                        'order_id': scan.order_id,
                        'rts_code': scan.rts_code,
                        'rider_id': scan.rider_id,
                        'buyer_name': scan.buyer_name,
                        'buyer_address': scan.buyer_address,
                        'weight_g': scan.weight_g,
                        'quantity': scan.quantity,
                        'payment_type': scan.payment_type,
                        'timestamp': scan.timestamp,
                    }
                return None
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving scan by tracking {tracking_id}: {e}")
            return None