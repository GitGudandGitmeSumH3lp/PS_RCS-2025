=== src/database/models.py ===
```python
"""SQLAlchemy ORM models for the receipt_scans table.

Schema matches the existing table exactly; no migration required.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""
    pass


class ReceiptScan(Base):
    """ORM model for the receipt_scans table."""

    __tablename__ = "receipt_scans"

    # Primary key
    scan_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Extracted fields
    tracking_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    order_id: Mapped[Optional[str]] = mapped_column(String)
    rts_code: Mapped[Optional[str]] = mapped_column(String, index=True)
    rider_id: Mapped[Optional[str]] = mapped_column(String)
    buyer_name: Mapped[Optional[str]] = mapped_column(String)
    buyer_address: Mapped[Optional[str]] = mapped_column(String)
    weight_g: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    payment_type: Mapped[Optional[str]] = mapped_column(String)

    # OCR metadata
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[str] = mapped_column(String, index=True, nullable=False)
    scan_datetime: Mapped[Optional[str]] = mapped_column(String)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Audit timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Table‑level CHECK constraints
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="check_confidence_range"
        ),
        CheckConstraint(
            "weight_g IS NULL OR weight_g >= 0",
            name="check_weight_non_negative"
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity >= 0",
            name="check_quantity_non_negative"
        ),
        CheckConstraint(
            "processing_time_ms IS NULL OR processing_time_ms >= 0",
            name="check_processing_time_non_negative"
        ),
    )