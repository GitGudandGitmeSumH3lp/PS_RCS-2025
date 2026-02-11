=== src/database/core.py ===
```python
"""Database engine and session management.

This module provides thread‑safe SQLAlchemy 2.0 synchronous setup with
connection pooling, WAL mode, and a transactional session context manager.
"""

import contextlib
from typing import Generator

from sqlalchemy import QueuePool, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from src.database.models import Base

# Module‑level state (initialised by init_db())
_engine = None
_SessionLocal = None  # scoped_session factory


def init_db(database_url: str = "sqlite:///data/database.db") -> None:
    """Initialise the database engine, session factory, and schema.

    Args:
        database_url: SQLAlchemy connection string (must be a valid SQLite URL).

    Raises:
        ValueError: If the database URL format is invalid.
        RuntimeError: If the database file cannot be created or accessed.
        sqlalchemy.exc.OperationalError: If SQLite pragma execution fails.
    """
    global _engine, _SessionLocal

    if not isinstance(database_url, str):
        raise ValueError("database_url must be a string")
    if not database_url.startswith("sqlite:///"):
        raise ValueError("database_url must be a SQLite URL (sqlite:///path)")

    try:
        # 1. Create engine with connection pool and thread‑safe settings
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )

        # 2. Enable WAL mode and set busy timeout
        with _engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=5000"))
            conn.commit()

        # 3. Create session factory and thread‑local scoped session
        session_factory = sessionmaker(bind=_engine, class_=Session)
        _SessionLocal = scoped_session(session_factory)

        # 4. Create tables (if they don't exist)
        Base.metadata.create_all(bind=_engine)

    except SQLAlchemyError as e:
        raise RuntimeError(f"Database initialisation failed: {e}") from e


@contextlib.contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session for the current thread.

    Yields:
        Thread‑local SQLAlchemy Session object.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: If any database error occurs.

    Behavior:
        - On normal exit: session.commit() is called.
        - On exception: session.rollback() is called and the exception is re‑raised.
        - Finally: session.close() and SessionLocal.remove() are always executed.
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")

    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        _SessionLocal.remove()