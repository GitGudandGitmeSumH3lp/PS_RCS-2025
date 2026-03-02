from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, Float, Text, DateTime, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class ReceiptScan(Base):
    __tablename__ = "receipt_scans"

    scan_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    order_id: Mapped[Optional[str]] = mapped_column(String)
    rts_code: Mapped[Optional[str]] = mapped_column(String, index=True)
    rider_id: Mapped[Optional[str]] = mapped_column(String)
    buyer_name: Mapped[Optional[str]] = mapped_column(String)
    buyer_address: Mapped[Optional[str]] = mapped_column(String)
    weight_g: Mapped[Optional[int]] = mapped_column(Integer, CheckConstraint('weight_g IS NULL OR weight_g >= 0'))
    quantity: Mapped[Optional[int]] = mapped_column(Integer, CheckConstraint('quantity IS NULL OR quantity >= 0'))
    payment_type: Mapped[Optional[str]] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, CheckConstraint('confidence >= 0.0 AND confidence <= 1.0'), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[str] = mapped_column(String, index=True, nullable=False)
    scan_datetime: Mapped[Optional[str]] = mapped_column(String)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, CheckConstraint('processing_time_ms IS NULL OR processing_time_ms >= 0'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)