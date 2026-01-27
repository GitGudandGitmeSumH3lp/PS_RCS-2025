# CONTRACT: Database Core Module
**Version:** 4.0
**Last Updated:** 2024-01-21
**Status:** Draft - Awaiting Approval

## 1. PURPOSE
Provides async database connection management and ORM base models for the Parcel Robot system. This module serves as the foundational data layer, enforcing schema consistency across all hardware subsystems (LiDAR, HuskyLens, OCR) while supporting both legacy integer IDs and modern UUID-based identification during the migration phase.

## 2. PUBLIC INTERFACE

### Class: `AsyncDatabaseEngine`
**Signature:**
```python
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
from contextlib import asynccontextmanager

class AsyncDatabaseEngine:
    """
    Manages async SQLAlchemy engine and session lifecycle.
    
    Attributes:
        engine: AsyncEngine instance
        async_session_maker: Configured sessionmaker for async sessions
    """
    
    def __init__(self, database_url: str = "sqlite+aiosqlite:///robot_data.db"):
        """
        Initialize the async database engine.
        
        Args:
            database_url: SQLAlchemy async database URL
        
        Raises:
            ValueError: If database_url is not an async URL (must contain '+aio')
        """
    
    async def initialize(self) -> None:
        """
        Create all tables defined in Base.metadata.
        
        Raises:
            DatabaseConnectionError: If unable to connect to database
        """
    
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
    
    async def close(self) -> None:
        """
        Dispose of the engine and close all connections.
        """
```

**Behavior Specification:**
- **Input Validation:** 
  - `database_url` must contain `+aio` (e.g., `sqlite+aiosqlite://` or `postgresql+asyncpg://`)
  - Raises `ValueError` if synchronous URL is provided
- **Processing Logic:**
  - Creates engine with `echo=False` (no SQL logging to stdout)
  - Configures sessionmaker with `expire_on_commit=False` for better async performance
  - `initialize()` must be called before first use to create tables
- **Output Guarantee:**
  - `get_session()` yields a valid, uncommitted session
  - Session auto-commits on context exit if no exception
  - Session auto-rolls back on exception
- **Side Effects:**
  - Creates database file if it doesn't exist
  - Creates all tables on `initialize()`

**Error Handling:**
- **Invalid URL:** `database_url` without `+aio` → Raise `ValueError` with message "Database URL must be async (e.g., sqlite+aiosqlite://)"
- **Connection Failure:** Unable to connect → Raise `DatabaseConnectionError` with original exception details
- **Session Failure:** Session creation fails → Raise `DatabaseSessionError` with context

**Performance Requirements:**
- Time Complexity: O(1) for session creation
- Space Complexity: O(1) per session (connection pooling handled by SQLAlchemy)

---

### Class: `Base` (Declarative Base)
**Signature:**
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, func
from datetime import datetime
import uuid

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
        default=lambda: str(uuid.uuid4())
    )
    
    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
```

**Behavior Specification:**
- **Input Validation:** N/A (ORM model)
- **Processing Logic:**
  - All models inheriting from `BaseMixin` get dual-key support automatically
  - UUIDs are generated on object creation (before DB insertion)
  - Timestamps are server-side defaults (UTC)
- **Output Guarantee:**
  - Every record has both `id` (int) and `uuid` (str)
  - `created_at` is immutable after insertion
  - `updated_at` updates automatically on any column change

**Performance Requirements:**
- UUID generation: O(1)
- No additional indexes required (UUID has unique constraint)

---

### Class: `Scan` (ORM Model)
**Signature:**
```python
from sqlalchemy import String, Text
from sqlalchemy.orm import relationship

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
        cascade="all, delete-orphan"
    )
    objects: Mapped[list["DetectedObject"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan"
    )
    ocr_results: Mapped[list["OCRResult"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan"
    )
```

**Behavior Specification:**
- **Cascade Deletes:** Deleting a `Scan` deletes all related `Point`, `DetectedObject`, `OCRResult` records
- **Scan Types:** Expected values: `"lidar"`, `"huskylens"`, `"ocr"`, `"unknown"`

---

### Class: `Point` (ORM Model)
**Signature:**
```python
from sqlalchemy import Float, ForeignKey

class Point(Base, BaseMixin):
    """
    Represents a single LiDAR scan point.
    """
    
    __tablename__ = "points"
    
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    angle: Mapped[float] = mapped_column(Float, nullable=False)
    distance: Mapped[float] = mapped_column(Float, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Relationship
    scan: Mapped["Scan"] = relationship(back_populates="points")
```

---

### Class: `DetectedObject` (ORM Model)
**Signature:**
```python
class DetectedObject(Base, BaseMixin):
    """
    Represents an object detected by HuskyLens.
    """
    
    __tablename__ = "objects"
    
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Relationship
    scan: Mapped["Scan"] = relationship(back_populates="objects")
```

---

### Class: `OCRResult` (ORM Model)
**Signature:**
```python
class OCRResult(Base, BaseMixin):
    """
    Represents OCR extraction from parcel label.
    """
    
    __tablename__ = "ocr_results"
    
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    order_id: Mapped[str] = mapped_column(String(100), nullable=True)
    tracking_number: Mapped[str] = mapped_column(String(100), nullable=True)
    buyer_name: Mapped[str] = mapped_column(String(200), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=True)
    rts_code: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # Relationship
    scan: Mapped["Scan"] = relationship(back_populates="ocr_results")
```

---

## 3. DEPENDENCIES

**This module CALLS:**
- `sqlalchemy.ext.asyncio.create_async_engine()` - Engine creation
- `sqlalchemy.orm.sessionmaker()` - Session factory configuration
- `uuid.uuid4()` - UUID generation for new records

**This module is CALLED BY:**
- `src/services/api/server.py` - Main FastAPI app for dependency injection
- `src/hardware/lidar/handler.py` - Stores LiDAR scan data
- `src/hardware/huskylens/handler.py` - Stores object detection data
- `src/hardware/ocr/handler.py` - Stores OCR extraction data

---

## 4. DATA STRUCTURES

### Custom Exceptions
```python
class DatabaseError(Exception):
    """Base exception for database operations."""
    pass

class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass

class DatabaseSessionError(DatabaseError):
    """Raised when session creation/management fails."""
    pass
```

---

## 5. CONSTRAINTS (FROM SYSTEM RULES)

- **No hardcoded paths:** Database path must be configurable via environment variable `DATABASE_URL` (default: `sqlite+aiosqlite:///robot_data.db`)
- **Type hints required:** All public methods must have complete type annotations
- **Thread safety:** AsyncSQLAlchemy handles concurrency; no manual locking needed
- **Error handling:** Database failures must not crash callers; wrap operations in try/except

---

## 6. MEMORY COMPLIANCE (FROM PROJECT MEMORY)

**Applied Rules:**
- **[2024-01-15]** AsyncSQLAlchemy (v2.0): Entire module rewritten using `sqlalchemy.ext.asyncio` with async/await patterns
- **[2024-01-20]** Decoupled DTOs: ORM models remain in `core.py`; Pydantic DTOs will live in `src/services/database/schemas.py` (future contract)
- **[2024-01-22]** Dual-key lookup: `BaseMixin` provides both `id` (legacy int) and `uuid` (modern str) on all tables

---

## 7. ACCEPTANCE CRITERIA (Test Cases)

**Test Case 1:** Engine Initialization
- Input: `AsyncDatabaseEngine()`
- Expected Output: Engine created with `sqlite+aiosqlite` URL
- Expected Behavior: No errors, engine is not None

**Test Case 2:** Invalid URL Detection
- Input: `AsyncDatabaseEngine("sqlite:///test.db")` (missing `+aio`)
- Expected Exception: `ValueError`
- Expected Message: "Database URL must be async (e.g., sqlite+aiosqlite://)"

**Test Case 3:** Session Context Manager
- Input: Create session, execute query, commit
- Expected Output: Session yields, query executes, changes committed
- Expected Behavior: No errors, context exits cleanly

**Test Case 4:** Cascade Delete
- Input: Create `Scan` with 3 `Point` records, delete `Scan`
- Expected Output: All 4 records deleted
- Expected Behavior: No orphaned `Point` records remain

**Test Case 5:** Dual-Key Lookup
- Input: Create `Scan`, retrieve by both `id` and `uuid`
- Expected Output: Same record returned both ways
- Expected Behavior: Both keys unique and queryable

**Test Case 6:** Auto-Timestamp Updates
- Input: Create `Scan`, wait 1 second, update `scan_type`
- Expected Output: `updated_at` is later than `created_at`
- Expected Behavior: `created_at` unchanged, `updated_at` reflects change

---

## 8. IMPLEMENTATION NOTES

### Migration Path from Legacy Code:
1. **Phase 1 (This Contract):** Establish async ORM foundation
2. **Phase 2:** Create Pydantic schemas in `src/services/database/schemas.py`
3. **Phase 3:** Build repository layer with CRUD operations
4. **Phase 4:** Update hardware handlers to use new async API

### Dependencies to Install:
```bash
pip install sqlalchemy[asyncio] aiosqlite
```

### Environment Configuration:
```bash
# .env file
DATABASE_URL=sqlite+aiosqlite:///robot_data.db
# For PostgreSQL: postgresql+asyncpg://user:pass@localhost/dbname
```

### SQLAlchemy 2.0 Syntax Notes:
- Use `select()` instead of `Query.filter()`
- Use `Mapped[]` type hints for columns
- Use `relationship()` with string forward references for circular imports
```

---

## 📋 WORK ORDER (For the Builder)

**Target File:** `src/services/database/core.py`

**Objective:** Replace synchronous `sqlite3` implementation with AsyncSQLAlchemy 2.0, preserving all existing functionality while adding UUID support.

---

### STRICT CONSTRAINTS (NON-NEGOTIABLE):

1. **[system_constraints.md]** Must use absolute imports: `from src.services.database.core import ...`
2. **[system_constraints.md]** All functions must have complete type hints (PEP 484)
3. **[system_constraints.md]** Database path must come from `os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///robot_data.db')`
4. **[system_constraints.md]** No raw SQL strings - all queries via SQLAlchemy ORM
5. **[Memory]** Must use `sqlalchemy.ext.asyncio` - NO `sqlite3` module allowed
6. **[Memory]** ORM models ONLY in this file - no Pydantic models mixed in

---

### MEMORY COMPLIANCE (MANDATORY):

- **[2024-01-15] AsyncSQLAlchemy Mandate:**
  - Import `AsyncEngine`, `AsyncSession`, `create_async_engine` from `sqlalchemy.ext.asyncio`
  - All database methods must be `async def` with `await` on queries
  - Use `async with` for session management
  
- **[2024-01-20] DTO Decoupling:**
  - This file contains ONLY: `Base`, `BaseMixin`, `Scan`, `Point`, `DetectedObject`, `OCRResult`, `AsyncDatabaseEngine`
  - NO Pydantic `BaseModel` imports
  - NO JSON serialization logic in ORM models
  
- **[2024-01-22] Dual-Key Support:**
  - Every table must inherit `BaseMixin`
  - `BaseMixin` provides: `id` (int, primary key), `uuid` (str, unique), `created_at`, `updated_at`
  - Foreign keys reference `id` (legacy compat), but `uuid` available for new code

---

### REQUIRED LOGIC:

1. **Engine Setup:**
   - Read `DATABASE_URL` from environment (default: `sqlite+aiosqlite:///robot_data.db`)
   - Validate URL contains `+aio` substring
   - Create engine with `echo=False`
   - Create sessionmaker with `expire_on_commit=False`

2. **Base Models:**
   - Define `Base = DeclarativeBase()`
   - Define `BaseMixin` with `id`, `uuid`, `created_at`, `updated_at`
   - UUID default uses `lambda: str(uuid.uuid4())`

3. **ORM Models:**
   - `Scan`: `scan_type`, `note`, relationships to all child tables
   - `Point`: `scan_id` (FK), `angle`, `distance`, `x`, `y`
   - `DetectedObject`: `scan_id` (FK), `label`, `x`, `y`, `width`, `height`, `algorithm`
   - `OCRResult`: `scan_id` (FK), `order_id`, `tracking_number`, `buyer_name`, `address`, `weight`, `quantity`, `rts_code`
   - All relationships use `cascade="all, delete-orphan"`

4. **Engine Class:**
   - `__init__`: Store URL, create engine and sessionmaker
   - `initialize()`: Call `Base.metadata.create_all(bind=engine)` using async context
   - `get_session()`: `@asynccontextmanager` that yields session
   - `close()`: Dispose engine

5. **Error Handling:**
   - Wrap engine creation in try/except → raise `DatabaseConnectionError`
   - Wrap session creation in try/except → raise `DatabaseSessionError`
   - Validate URL format before engine creation

---

### INTEGRATION POINTS:

- **Must be imported by:** `src/services/api/server.py` (FastAPI lifespan dependency injection)
- **Will be called by:** All hardware handlers during async migration (Phase 2)

---

### FILES TO REFERENCE:

- Contract: `docs/contracts/database_core.md` (this document)
- Style Guide: `docs/system_style.md` (if exists)
- API Map: `docs/API_MAP_lite.md` (verify no conflicts)
- Memory: `_memory_snippet.txt` (for all three rules)

---

### SUCCESS CRITERIA:

✅ All methods have async signatures matching Contract  
✅ All ORM models inherit `BaseMixin` with dual keys  
✅ No `sqlite3` imports anywhere in file  
✅ URL validation raises `ValueError` for non-async URLs  
✅ `get_session()` is an async context manager  
✅ No Pydantic models in this file  
✅ Inspector approval required before commit  

---

## POST-ACTION REPORT:

✅ **Contract Created:** `docs/contracts/database_core.md`  
📋 **Work Order Generated** for Builder  
🔐 **Next Verification Command:**  
```
/verify-context: system_style.md, contracts/database_core.md, API_MAP_lite.md, _memory_snippet.txt, system_constraints.md