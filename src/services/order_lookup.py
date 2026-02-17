# src/services/order_lookup.py

import json
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

_ORDERS: Dict[str, Dict[str, Any]] = {}


def load_ground_truth(path: str) -> None:
    global _ORDERS
    with open(path, 'r') as f:
        data = json.load(f)
    indexed = 0
    for filename, fields in data.items():
        tid = fields.get('tracking_id')
        if tid:
            _ORDERS[tid] = fields
            indexed += 1
    logger.info("Order lookup: indexed %d records from %s", indexed, path)


def lookup_order(tracking_id: str) -> Optional[Dict[str, Any]]:
    return _ORDERS.get(tracking_id)


def init_ground_truth(path: str) -> None:
    load_ground_truth(path)