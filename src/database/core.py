import contextlib
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from src.database.models import Base

_engine = None
SessionLocal = None

def init_db(database_url: str = "sqlite:///data/database.db") -> None:
    global _engine, SessionLocal

    if not isinstance(database_url, str):
        raise ValueError("database_url must be a string")
    if not database_url.startswith("sqlite:///"):
        raise ValueError("database_url must be a SQLite URL (sqlite:///path)")

    try:
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )

        with _engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=5000"))
            conn.commit()

        session_factory = sessionmaker(bind=_engine, class_=Session)
        SessionLocal = scoped_session(session_factory)

        Base.metadata.create_all(bind=_engine)

    except SQLAlchemyError as e:
        raise RuntimeError(f"Database initialisation failed: {e}") from e


@contextlib.contextmanager
def get_session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        SessionLocal.remove()