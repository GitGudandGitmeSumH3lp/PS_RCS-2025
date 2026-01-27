"""
AsyncSQLAlchemy 2.0 database core with UUID support.

Provides async database connection management and ORM base models
for the Parcel Robot system with dual-key lookup (legacy ID + UUID).
"""

import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================


class DatabaseError(Exception):
    """Base exception for database operations."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class DatabaseSessionError(DatabaseError):
    """Raised when session creation/management fails."""

    pass


# ============================================================================
# BASE MODELS
# ============================================================================


class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    Provides common columns for dual-key lookup (legacy + UUID).
    """

    pass


class BaseMixin:
    """
    Mixin providing standard columns for all tables.
    Supports legacy integer IDs and modern UUIDs.
    """

    # Legacy ID (for backward compatibility)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Modern UUID (for new integrations)
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================================
# ORM MODELS
# ============================================================================


class Scan(Base, BaseMixin):
    """
    Represents a sensor scan session (LiDAR, HuskyLens, OCR).
    """

    __tablename__ = "scans"

    scan_type: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    points: Mapped[list["Point"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    objects: Mapped[list["DetectedObject"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    ocr_results: Mapped[list["OCRResult"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )


class Point(Base, BaseMixin):
    """
    Represents a single LiDAR scan point.
    """

    __tablename__ = "points"

    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
    )
    angle: Mapped[float] = mapped_column(Float, nullable=False)
    distance: Mapped[float] = mapped_column(Float, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationship
    scan: Mapped["Scan"] = relationship(back_populates="points")


class DetectedObject(Base, BaseMixin):
    """
    Represents an object detected by HuskyLens.
    """

    __tablename__ = "objects"

    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationship
    scan: Mapped["Scan"] = relationship(back_populates="objects")


class OCRResult(Base, BaseMixin):
    """
    Represents OCR extraction from parcel label.
    """

    __tablename__ = "ocr_results"

    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[str] = mapped_column(String(100), nullable=True)
    tracking_number: Mapped[str] = mapped_column(String(100), nullable=True)
    buyer_name: Mapped[str] = mapped_column(String(200), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=True)
    rts_code: Mapped[str] = mapped_column(String(100), nullable=True)

    # Relationship
    scan: Mapped["Scan"] = relationship(back_populates="ocr_results")


# ============================================================================
# DATABASE ENGINE
# ============================================================================


class AsyncDatabaseEngine:
    """
    Manages async SQLAlchemy engine and session lifecycle.

    Attributes:
        engine: AsyncEngine instance
        async_session_maker: Configured sessionmaker for async sessions
    """

    def __init__(
        self,
        database_url: str = "sqlite+aiosqlite:///robot_data.db",
    ) -> None:
        """
        Initialize the async database engine.

        Args:
            database_url: SQLAlchemy async database URL

        Raises:
            ValueError: If database_url is not an async URL (must contain '+aio')
        """
        # Validate URL contains async driver
        if "+aio" not in database_url:
            raise ValueError(
                "Database URL must be async (e.g., sqlite+aiosqlite://)"
            )

        self._database_url = database_url

        try:
            # Create async engine with connection pooling
            self.engine: AsyncEngine = create_async_engine(
                database_url,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,  # Verify connections before use
            )

            # Create async session factory
            self.async_session_maker = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except Exception as e:
            raise DatabaseConnectionError(
                f"Failed to create database engine: {e}"
            ) from e

    async def initialize(self) -> None:
        """
        Create all tables defined in Base.metadata.

        Raises:
            DatabaseConnectionError: If unable to connect to database
        """
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            raise DatabaseConnectionError(
                f"Failed to initialize database tables: {e}"
            ) from e

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provide an async database session via context manager.

        Yields:
            AsyncSession: Active database session

        Example:
            async with db.get_session() as session:
                result = await session.execute(select(Scan))

        Raises:
            DatabaseSessionError: If session creation fails
        """
        session: AsyncSession | None = None
        try:
            session = self.async_session_maker()
            yield session
            await session.commit()
        except Exception as e:
            if session:
                await session.rollback()
            raise DatabaseSessionError(
                f"Database session error: {e}"
            ) from e
        finally:
            if session:
                await session.close()

    async def close(self) -> None:
        """
        Dispose of the engine and close all connections.
        """
        await self.engine.dispose()


# ============================================================================
# GLOBAL ENGINE INSTANCE (SINGLETON PATTERN)
# ============================================================================


# Read database URL from environment with fallback
_database_url = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///robot_data.db",
)

# Create global engine instance
engine = AsyncDatabaseEngine(_database_url)