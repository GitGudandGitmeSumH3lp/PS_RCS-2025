#!/usr/bin/env python3
"""Quick test for ReceiptDatabase initialization."""
import sys
import os
# Adjust path if needed (assumes running from project root)
sys.path.insert(0, os.path.abspath('.'))

from src.services.receipt_database import ReceiptDatabase

try:
    db = ReceiptDatabase()
    print(" ReceiptDatabase initialized successfully")
    # Try a simple operation
    scans = db.get_recent_scans(1)
    print(f"   Recent scans query returned {len(scans)} rows")
except Exception as e:
    print(f" Initialization failed: {e}")
    sys.exit(1)