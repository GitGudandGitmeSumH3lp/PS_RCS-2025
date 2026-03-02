import os
from typing import Any, Dict, List, Optional

from src.database.core import init_db
from src.database.repository import ReceiptRepository

class ReceiptDatabase:
    def __init__(self, db_path: str = "data/database.db") -> None:
        if not isinstance(db_path, str):
            raise TypeError("db_path must be string")

        if not os.path.isabs(db_path):
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
        return self._repository.store_scan(
            scan_id, fields, raw_text, confidence, engine
        )

    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        return self._repository.get_scan(scan_id)

    def get_scans_by_tracking(self, tracking_id: str) -> List[Dict[str, Any]]:
        return self._repository.get_scans_by_tracking(tracking_id)

    def get_scan_by_tracking(self, tracking_number: str) -> Optional[Dict[str, Any]]:
        scans = self._repository.get_scans_by_tracking(tracking_number)
        if not scans:
            return None
        try:
            scans.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        except Exception:
            pass
        return scans[0]

    def get_recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._repository.get_recent_scans(limit)