# CONTRACT: Database Synchronization Refactor (SQLite Threading Fix)

**Version:** 1.0  
**Last Updated:** 2026-02-12  
**Status:** Draft - Awaiting Approval  
**Priority:** CRITICAL (Threading Violation)

---

## 1. PROBLEM STATEMENT

The current database layer violates `system_constraints.md` Section 1 threading requirements and creates race conditions under concurrent load. The `DatabaseManager` class uses raw `sqlite3` connections with `check_same_thread=False` and implements manual retry logic for lock contention. The `ReceiptDatabase` class attempts to call a non-existent static method `DatabaseManager.get_connection()`, indicating the architecture was never tested under real threading conditions. When `server.py` stores OCR results from `ThreadPoolExecutor` threads while Flask handles concurrent API requests, the system relies on SQLite's internal locking and retry loops—a fragile approach that risks data corruption and user-facing "database is locked" errors. This contract specifies a complete replacement using synchronous SQLAlchemy with thread-local sessions, connection pooling, and WAL mode to ensure thread-safe database operations without asyncio.

---

## 2. PROPOSED ARCHITECTURE

### 2.1 Core Components

**Module Structure:**
```
src/database/
├── __init__.py          # Package exports
├── core.py              # Engine, SessionLocal, init_db()
├── models.py            # SQLAlchemy ORM models
└── repository.py        # ReceiptRepository class
```

**Deprecated (to be removed after migration):**
- `src/database/database_manager.py`

**Modified:**
- `src/services/receipt_database.py` (refactored to use repository pattern)
- `src/api/server.py` (minimal changes for session lifecycle)

### 2.2 Technology Stack

- **ORM:** SQLAlchemy 2.0+ (synchronous API only)
- **Connection Pool:** QueuePool (default) with size=5, max_overflow=10
- **Session Scope:** `scoped_session` with thread-local registry
- **SQLite Optimizations:** WAL mode, `PRAGMA busy_timeout=5000`

### 2.3 Threading Model

```
┌─────────────────────────────────────────────┐
│          Flask Request Thread 1             │
│  ┌──────────────────────────────────────┐   │
│  │ scoped_session() → Thread-Local DB1  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│       ThreadPoolExecutor OCR Worker         │
│  ┌──────────────────────────────────────┐   │
│  │ scoped_session() → Thread-Local DB2  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│          Flask Request Thread 2             │
│  ┌──────────────────────────────────────┐   │
│  │ scoped_session() → Thread-Local DB3  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Key Principle:** Each thread receives its own session via `SessionLocal()`. Sessions are never shared. Flask teardown and repository context managers ensure proper cleanup.

---

## 3. PUBLIC INTERFACE

### Module: `src/database/core.py`

#### Function: `init_db`
**Signature:**
```python
def init_db(database_url: str = "sqlite:///data/database.db") -> None:
    """Initialize the database engine and create schema.
    
    Args:
        database_url: SQLAlchemy connection string.
        
    Side Effects:
        - Creates engine stored in module-level variable
        - Configures scoped_session factory
        - Executes CREATE TABLE IF NOT EXISTS via Base.metadata.create_all()
        - Enables SQLite WAL mode
        
    Thread Safety:
        Must be called once at application startup before any threads spawn.
    """
```

**Behavior Specification:**
- **Input Validation:** Must accept valid SQLite URL format. Default path must be `sqlite:///data/database.db`.
- **Processing Logic:**
  1. Create engine with `create_engine(url, connect_args={"check_same_thread": False}, poolclass=QueuePool, pool_size=5, max_overflow=10)`
  2. Execute `PRAGMA journal_mode=WAL` via engine connection
  3. Execute `PRAGMA busy_timeout=5000` via engine connection
  4. Create `sessionmaker(bind=engine)` and wrap in `scoped_session`
  5. Call `Base.metadata.create_all(engine)` to create tables
- **Output Guarantee:** After return, `SessionLocal()` is safe to call from any thread.
- **Side Effects:** Modifies module-level `engine` and `SessionLocal` variables.

**Error Handling:**
- **Invalid URL:** Raise `ValueError("Invalid database URL format")`
- **File permissions:** Raise `RuntimeError("Cannot create database file at <path>")`
- **SQLite errors:** Propagate `sqlalchemy.exc.OperationalError` with context

**Performance Requirements:**
- Time Complexity: O(1) after schema exists
- Space Complexity: O(1)

---

#### Function: `get_session`
**Signature:**
```python
@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session.
    
    Yields:
        Thread-local SQLAlchemy Session object.
        
    Behavior:
        - Auto-commits on successful exit
        - Rolls back on exception
        - Closes session in finally block
        - Removes thread-local registry entry
    """
```

**Behavior Specification:**
- **Input Validation:** None (no parameters)
- **Processing Logic:**
  1. Call `SessionLocal()` to get thread-local session
  2. Yield session to caller
  3. On normal exit: `session.commit()`
  4. On exception: `session.rollback()`, re-raise
  5. Always: `session.close()`, `SessionLocal.remove()`
- **Output Guarantee:** Caller receives a session bound to current thread.
- **Side Effects:** Database writes committed on success, rolled back on error.

**Error Handling:**
- **Database errors during commit:** Raise `sqlalchemy.exc.SQLAlchemyError` after rollback
- **All exceptions propagated** after cleanup

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1) per thread

---

### Module: `src/database/models.py`

#### Class: `ReceiptScan`
**Signature:**
```python
class ReceiptScan(Base):
    """SQLAlchemy model for receipt_scans table.
    
    Schema matches existing table exactly (no migration required).
    """
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
```

**Constraints (FROM SYSTEM RULES):**
- Primary key: `scan_id` (matches existing schema)
- Indexes: `tracking_id`, `rts_code`, `timestamp` (matches existing schema)
- CHECK constraints: Preserved exactly from `receipt_database.py` CREATE TABLE statement

---

### Module: `src/database/repository.py`

#### Class: `ReceiptRepository`

**Purpose:** Encapsulates all database operations for receipt scans. Replaces `ReceiptDatabase` internal logic while maintaining identical public API.

---

#### Method: `store_scan`
**Signature:**
```python
def store_scan(
    self,
    scan_id: int,
    fields: Dict[str, Any],
    raw_text: str,
    confidence: float,
    engine: str
) -> bool:
    """Store a new receipt scan.
    
    Args:
        scan_id: Unique positive integer ID.
        fields: Dictionary of extracted fields.
        raw_text: Full OCR text.
        confidence: Score between 0.0 and 1.0.
        engine: 'tesseract' or 'paddle'.
    
    Returns:
        True if stored successfully.
    
    Raises:
        ValueError: Invalid scan_id, confidence, or engine.
        IntegrityError: scan_id already exists.
        RuntimeError: Database operation failed.
    """
```

**Behavior Specification:**
- **Input Validation:**
  - `scan_id` must be `int > 0`, else raise `ValueError("scan_id must be positive integer")`
  - `confidence` must be `0.0 <= confidence <= 1.0`, else raise `ValueError("confidence must be between 0.0 and 1.0, got <value>")`
  - `engine` must be `'tesseract'` or `'paddle'`, else raise `ValueError("engine must be 'tesseract' or 'paddle', got <value>")`
- **Processing Logic:**
  1. Call `get_session()` context manager
  2. Create `ReceiptScan` instance from parameters
  3. Add to session via `session.add(receipt)`
  4. Commit via context manager exit (automatic)
  5. Return `True`
- **Output Guarantee:** Record inserted in database on `True` return.
- **Side Effects:** Inserts row into `receipt_scans` table.

**Error Handling:**
- **Duplicate scan_id:** Catch `sqlalchemy.exc.IntegrityError`, raise `sqlite3.IntegrityError(f"Scan ID {scan_id} already exists")` (preserves existing error type for backward compatibility)
- **Database errors:** Wrap in `RuntimeError(f"Database error: {str(e)}")`

**Performance Requirements:**
- Time Complexity: O(1)
- Space Complexity: O(1)

---

#### Method: `get_scan`
**Signature:**
```python
def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve scan by ID.
    
    Args:
        scan_id: The scan ID to query.
    
    Returns:
        Dictionary with all fields, or None if not found.
    """
```

**Behavior Specification:**
- **Input Validation:** None (accepts any int)
- **Processing Logic:**
  1. Call `get_session()` context manager
  2. Query: `session.query(ReceiptScan).filter_by(scan_id=scan_id).first()`
  3. If result is None, return None
  4. Convert ORM object to dict via `{c.name: getattr(receipt, c.name) for c in receipt.__table__.columns}`
  5. Return dict
- **Output Guarantee:** Dict keys match column names exactly.
- **Side Effects:** None (read-only).

**Error Handling:**
- **Database errors:** Wrap in `RuntimeError(f"Database error: {str(e)}")`

**Performance Requirements:**
- Time Complexity: O(1) with primary key lookup
- Space Complexity: O(1)

---

#### Method: `get_scans_by_tracking`
**Signature:**
```python
def get_scans_by_tracking(self, tracking_id: str) -> List[Dict[str, Any]]:
    """Retrieve all scans for a tracking ID.
    
    Args:
        tracking_id: The tracking ID to filter by.
    
    Returns:
        List of scan dicts, sorted by timestamp DESC.
    """
```

**Behavior Specification:**
- **Input Validation:** None (accepts any string)
- **Processing Logic:**
  1. Call `get_session()` context manager
  2. Query: `session.query(ReceiptScan).filter_by(tracking_id=tracking_id).order_by(ReceiptScan.timestamp.desc()).all()`
  3. Convert each ORM object to dict
  4. Return list
- **Output Guarantee:** List may be empty. Order guaranteed DESC by timestamp.
- **Side Effects:** None (read-only).

**Error Handling:**
- **Database errors:** Wrap in `RuntimeError(f"Database error: {str(e)}")`

**Performance Requirements:**
- Time Complexity: O(n) where n = matching records
- Space Complexity: O(n)

---

#### Method: `get_recent_scans`
**Signature:**
```python
def get_recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve most recent scans.
    
    Args:
        limit: Maximum records to return (default 50).
    
    Returns:
        List of scan dicts, sorted by timestamp DESC.
    """
```

**Behavior Specification:**
- **Input Validation:** None (accepts any int, negative treated as 0)
- **Processing Logic:**
  1. Call `get_session()` context manager
  2. Query: `session.query(ReceiptScan).order_by(ReceiptScan.timestamp.desc()).limit(limit).all()`
  3. Convert each ORM object to dict
  4. Return list
- **Output Guarantee:** List may be empty. Order guaranteed DESC by timestamp.
- **Side Effects:** None (read-only).

**Error Handling:**
- **Database errors:** Wrap in `RuntimeError(f"Database error: {str(e)}")`

**Performance Requirements:**
- Time Complexity: O(limit)
- Space Complexity: O(limit)

---

### Module: `src/services/receipt_database.py` (REFACTORED)

#### Class: `ReceiptDatabase`

**Purpose:** Compatibility wrapper around `ReceiptRepository`. Maintains existing public API used by `server.py`.

**Signature:**
```python
class ReceiptDatabase:
    """Facade for receipt database operations.
    
    Maintains backward compatibility with existing code while
    delegating to new SQLAlchemy repository layer.
    
    Attributes:
        _repository: Internal ReceiptRepository instance.
    """
    
    def __init__(self, db_path: str = "data/database.db") -> None:
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file.
        
        Raises:
            TypeError: If db_path is not a string.
        """
        if not isinstance(db_path, str):
            raise TypeError("db_path must be string")
        
        # Initialize SQLAlchemy core if not already done
        database_url = f"sqlite:///{db_path}"
        init_db(database_url)
        
        self._repository = ReceiptRepository()
    
    def store_scan(self, scan_id: int, fields: Dict[str, Any], 
                   raw_text: str, confidence: float, engine: str) -> bool:
        """Delegate to repository."""
        return self._repository.store_scan(scan_id, fields, raw_text, confidence, engine)
    
    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """Delegate to repository."""
        return self._repository.get_scan(scan_id)
    
    def get_scans_by_tracking(self, tracking_id: str) -> List[Dict[str, Any]]:
        """Delegate to repository."""
        return self._repository.get_scans_by_tracking(tracking_id)
    
    def get_recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Delegate to repository."""
        return self._repository.get_recent_scans(limit)
```

**API Compatibility Notes:**
- All public methods preserve **exact signatures** from current implementation
- Error types preserved (`ValueError`, `sqlite3.IntegrityError`, `RuntimeError`)
- Return types unchanged (`bool`, `Optional[Dict]`, `List[Dict]`)
- `db_path` parameter retained for backward compatibility
- **Breaking change:** `_get_connection()`, `_ensure_schema()`, `_lock` removed (were private, unused externally)

---

## 4. DEPENDENCIES

**This module CALLS:**
- `sqlalchemy.create_engine()` - Database connection
- `sqlalchemy.orm.sessionmaker()` - Session factory
- `sqlalchemy.orm.scoped_session()` - Thread-local sessions
- `sqlalchemy.orm.declarative_base()` - ORM base class

**This module is CALLED BY:**
- `src/api/server.py` - Via `ReceiptDatabase` facade
- `src/services/ocr_processor.py` - Indirectly via server OCR callbacks

---

## 5. DATA STRUCTURES

### SQLAlchemy Model Mapping
```python
# Existing table schema (preserved exactly):
receipt_scans (
    scan_id INTEGER PRIMARY KEY,
    tracking_id TEXT,  -- INDEXED
    order_id TEXT,
    rts_code TEXT,     -- INDEXED
    rider_id TEXT,
    buyer_name TEXT,
    buyer_address TEXT,
    weight_g INTEGER CHECK (weight_g IS NULL OR weight_g >= 0),
    quantity INTEGER CHECK (quantity IS NULL OR quantity >= 0),
    payment_type TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    raw_text TEXT NOT NULL,
    engine TEXT NOT NULL,
    timestamp TEXT NOT NULL,  -- INDEXED
    scan_datetime TEXT,
    processing_time_ms INTEGER CHECK (processing_time_ms IS NULL OR processing_time_ms >= 0),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**No schema migration required.** SQLAlchemy `Base.metadata.create_all()` will detect existing table and skip creation.

---

## 6. CONSTRAINTS (FROM SYSTEM RULES)

### From `system_constraints.md` Section 1:
- ✅ **No asyncio:** Solution uses synchronous SQLAlchemy only
- ✅ **Threading only:** `scoped_session` provides thread-local sessions for `threading.Thread` and `ThreadPoolExecutor`
- ✅ **Manager Pattern:** Repository encapsulates all database logic

### From `system_constraints.md` Section 4:
- ✅ **Type Hints:** All functions fully annotated
- ✅ **Docstrings:** Google-style docstrings for all public methods
- ✅ **Max Function Length:** All methods < 50 lines

---

## 7. MEMORY COMPLIANCE

**Applied Rules:**

**2026-02-12 Threading Requirement:** Contract ensures thread-safe database access via `scoped_session`. Each thread (Flask request handler or OCR worker) receives isolated session. No `check_same_thread=False` hacks. WAL mode + busy_timeout eliminate lock contention without retry loops.

**2026-02-12 API Stability:** Public interface of `ReceiptDatabase` unchanged. All existing `server.py` calls (`store_scan`, `get_scan`, `get_recent_scans`) work identically. Error types preserved for backward compatibility.

---

## 8. IMPLEMENTATION PLAN (FOR IMPLEMENTER)

### Step 1: Create `src/database/core.py`
```python
# Implementation requirements:
# - Module-level engine and SessionLocal variables
# - init_db() function matching signature above
# - get_session() context manager matching signature above
# - WAL mode + busy_timeout configuration
# - Connection pool: QueuePool with size=5, max_overflow=10
```

### Step 2: Create `src/database/models.py`
```python
# Implementation requirements:
# - Declarative Base instance
# - ReceiptScan class with exact column mapping
# - All indexes defined via index=True
# - All CHECK constraints defined via CheckConstraint()
```

### Step 3: Create `src/database/repository.py`
```python
# Implementation requirements:
# - ReceiptRepository class with 4 methods
# - All methods use get_session() context manager
# - ORM queries via session.query(ReceiptScan)
# - Dict conversion via column introspection
# - Error wrapping per contract specifications
```

### Step 4: Refactor `src/services/receipt_database.py`
```python
# Implementation requirements:
# - Keep ReceiptDatabase class name
# - Replace all internal logic with repository delegation
# - Call init_db() in __init__
# - Remove _get_connection, _ensure_schema, _lock, retry loops
# - Preserve exact public method signatures
```

### Step 5: Update `src/database/__init__.py`
```python
# Export public API:
from .core import init_db, get_session
from .models import ReceiptScan, Base
from .repository import ReceiptRepository

__all__ = ['init_db', 'get_session', 'ReceiptScan', 'Base', 'ReceiptRepository']
```

### Step 6: Modify `src/api/server.py` (Minimal Changes)
```python
# Required changes:
# 1. Import: from src.services.receipt_database import ReceiptDatabase  # No change
# 2. Initialization: self.receipt_db = ReceiptDatabase()  # No change
# 3. Usage: All existing calls work unchanged
# 4. Optional: Add Flask teardown to remove thread-local sessions:

@app.teardown_appcontext
def remove_session(exception=None):
    from src.database.core import SessionLocal
    SessionLocal.remove()
```

### Step 7: Deprecate `src/database/database_manager.py`
```python
# Add deprecation warning at top of file:
"""DEPRECATED: This module is replaced by src/database/core.py.
Do not use for new code. Will be removed in next release.
"""
# Do NOT delete yet (other modules may still import)
```

### Step 8: Integration Testing
```python
# Test script requirements:
# - Spawn 10 threads simultaneously calling store_scan()
# - Verify no "database is locked" errors
# - Verify all records inserted correctly
# - Verify get_recent_scans() returns correct count
# - Run for 60 seconds minimum
```

---

## 9. THREADING MODEL & SESSION LIFECYCLE

### Session Scoping Strategy

```python
# Thread 1 (Flask request):
with app.request_context():
    db = ReceiptDatabase()
    db.store_scan(...)  # Acquires thread-local session
    # Flask teardown removes session

# Thread 2 (OCR worker):
def ocr_callback(future):
    result = future.result()
    db = ReceiptDatabase()  # Different thread, different session
    db.store_scan(...)
    SessionLocal.remove()  # Explicit cleanup in worker threads
```

### Lifecycle Guarantee

| Event | Action | Responsibility |
|-------|--------|----------------|
| Flask request starts | `SessionLocal()` creates thread-local session | Automatic via scoped_session |
| Repository operation | Session used for query/insert | Repository method |
| Flask request ends | `SessionLocal.remove()` clears registry | Flask teardown handler |
| OCR thread starts | New session created on first `SessionLocal()` call | Automatic via scoped_session |
| OCR operation complete | Session closed via `get_session()` context manager | Repository method |
| OCR thread ends | `SessionLocal.remove()` in callback | Explicit in `_on_ocr_complete()` |

### Concurrency Safety Proof

1. **Isolation:** `scoped_session` uses `threading.local()` registry. Each thread ID maps to unique session.
2. **No Sharing:** Sessions never passed between threads. Each thread calls `SessionLocal()` independently.
3. **WAL Mode:** SQLite write-ahead log allows concurrent readers + single writer.
4. **Busy Timeout:** 5-second timeout prevents immediate lock errors if write contention occurs.
5. **Connection Pooling:** QueuePool reuses connections efficiently without `check_same_thread=False`.

---

## 10. API COMPATIBILITY NOTES

### Preserved Interfaces (ZERO BREAKING CHANGES)

**In `server.py`:**
```python
# Before (current):
self.receipt_db = ReceiptDatabase()
self.receipt_db.store_scan(scan_id, fields, raw_text, confidence, engine)
scan = self.receipt_db.get_scan(scan_id)
scans = self.receipt_db.get_recent_scans(limit=50)

# After (refactor):
self.receipt_db = ReceiptDatabase()  # ✅ Same
self.receipt_db.store_scan(scan_id, fields, raw_text, confidence, engine)  # ✅ Same
scan = self.receipt_db.get_scan(scan_id)  # ✅ Same
scans = self.receipt_db.get_recent_scans(limit=50)  # ✅ Same
```

**Error Compatibility:**
```python
# Existing code catches:
try:
    db.store_scan(...)
except sqlite3.IntegrityError:  # ✅ Still raised (wrapped from SQLAlchemy)
    pass
except ValueError:  # ✅ Still raised (validation errors)
    pass
except RuntimeError:  # ✅ Still raised (database errors)
    pass
```

### Internal Changes (NOT BREAKING - Private)

**Removed private methods (unused externally):**
- `ReceiptDatabase._get_connection()` - Was broken, replaced by repository
- `ReceiptDatabase._ensure_schema()` - Replaced by `init_db()`
- `ReceiptDatabase._lock` - Replaced by scoped_session thread isolation

**Removed module (deprecated, unused externally):**
- `src/database/database_manager.py` - Marked deprecated, will be removed after validation

---

## 11. RISK MITIGATION

### Data Safety Guarantees

1. **No Data Loss:** New schema identical to existing. `CREATE TABLE IF NOT EXISTS` logic preserved via SQLAlchemy metadata.
2. **No Downtime Required:** Refactor can be deployed without stopping service. Old and new code read same database.
3. **Rollback Path:** If issues detected, revert to original `receipt_database.py` (keep old file as `receipt_database_legacy.py` during transition).

### Testing Checkpoints

**Checkpoint 1: Unit Tests**
```python
# Required tests (implement in test_receipt_repository.py):
# - test_store_scan_success()
# - test_store_scan_duplicate_raises_integrity_error()
# - test_store_scan_invalid_confidence_raises_value_error()
# - test_get_scan_exists()
# - test_get_scan_not_found_returns_none()
# - test_get_recent_scans_ordering()
# - test_concurrent_inserts_no_lock_errors()  # 10 threads, 100 inserts each
```

**Checkpoint 2: Integration Tests**
```python
# Required tests (implement in test_server_ocr_integration.py):
# - test_ocr_scan_endpoint_stores_to_database()
# - test_concurrent_ocr_requests()  # 10 simultaneous POST /api/vision/scan
# - test_history_endpoint_after_scans()  # Verify GET /api/ocr/scans
```

**Checkpoint 3: Load Test**
```bash
# Simulate production load:
# - 100 OCR scans in 60 seconds (ThreadPoolExecutor)
# - 50 simultaneous history queries (Flask threads)
# - Monitor: No "database is locked" errors in logs
# - Monitor: CPU usage < 80%, memory < 1GB
```

### Rollback Plan

**If integration tests fail:**
1. Revert `receipt_database.py` to original (restore from `receipt_database_legacy.py`)
2. Comment out `init_db()` calls in `server.py`
3. Remove `src/database/core.py`, `models.py`, `repository.py`
4. System returns to original state (fragile but functional)

**If load test fails:**
1. Investigate SQLAlchemy session leaks via `SessionLocal.remove()` audit
2. Increase connection pool size if contention detected
3. Enable SQLAlchemy query logging: `echo=True` in `create_engine()`
4. If unfixable, execute rollback plan above

---

## 12. VALIDATION CHECKLIST (FOR AUDITOR)

### Compliance Audit (100/100 Required)

**System Constraints Compliance:**
- [ ] No `asyncio` imports anywhere in new modules (10 pts)
- [ ] No `check_same_thread=False` in new code (10 pts)
- [ ] All functions < 50 lines (10 pts)
- [ ] All functions have type hints (10 pts)
- [ ] All public methods have Google-style docstrings (10 pts)
- [ ] Uses `threading` module only (no async) (10 pts)

**Threading Safety:**
- [ ] `scoped_session` used for thread-local sessions (10 pts)
- [ ] Flask teardown handler removes sessions (5 pts)
- [ ] OCR callbacks explicitly call `SessionLocal.remove()` (5 pts)
- [ ] No raw `sqlite3.connect()` calls in new code (10 pts)

**API Compatibility:**
- [ ] `ReceiptDatabase.__init__(db_path)` signature unchanged (5 pts)
- [ ] `store_scan()` signature unchanged (5 pts)
- [ ] `get_scan()` signature unchanged (5 pts)
- [ ] `get_recent_scans()` signature unchanged (5 pts)
- [ ] Error types preserved (`ValueError`, `IntegrityError`, `RuntimeError`) (5 pts)

**Total:** 100 points

### Functional Validation

**Unit Tests:**
- [ ] All repository methods pass unit tests
- [ ] Concurrent insert test (10 threads) passes without errors
- [ ] Duplicate scan_id raises `IntegrityError`
- [ ] Invalid confidence raises `ValueError`

**Integration Tests:**
- [ ] `/api/vision/scan` endpoint stores to database
- [ ] `/api/vision/results/<id>` retrieves from database
- [ ] `/api/ocr/scans` returns recent scans
- [ ] Concurrent OCR requests (10 simultaneous) complete without errors

**Load Test:**
- [ ] 100 scans in 60 seconds: no "database is locked" errors
- [ ] 50 simultaneous history queries: response time < 500ms
- [ ] Memory usage stable (no leaks over 10-minute test)

---

## 13. ACCEPTANCE CRITERIA

### Test Case 1: Single Scan Storage
**Scenario:** Store one OCR result via Flask endpoint

**Input:**
```python
scan_id = 1234567890
fields = {'tracking_id': 'ABC123', 'order_id': 'ORD001', 'confidence': 0.95}
raw_text = "Flash Express Receipt..."
confidence = 0.95
engine = 'tesseract'
```

**Expected Output:**
- `store_scan()` returns `True`
- Database contains 1 row with `scan_id=1234567890`
- `get_scan(1234567890)` returns dict matching input

**Expected Behavior:**
- Session auto-commits via `get_session()` context manager
- No errors logged

---

### Test Case 2: Concurrent Storage (Thread Safety)
**Scenario:** 10 threads store scans simultaneously

**Input:**
```python
# Thread 1: scan_id=1, tracking_id='A1'
# Thread 2: scan_id=2, tracking_id='A2'
# ...
# Thread 10: scan_id=10, tracking_id='A10'
```

**Expected Output:**
- All 10 `store_scan()` calls return `True`
- Database contains 10 rows
- No "database is locked" errors
- No `IntegrityError` (unless duplicate scan_id intentional)

**Expected Behavior:**
- Each thread receives isolated session via `scoped_session`
- WAL mode allows concurrent writes to queue
- Busy timeout prevents immediate failures

---

### Test Case 3: Duplicate Scan ID Error
**Scenario:** Attempt to store same `scan_id` twice

**Input:**
```python
db.store_scan(999, {...}, "text", 0.9, 'tesseract')  # First call
db.store_scan(999, {...}, "text", 0.8, 'paddle')     # Second call
```

**Expected Exception:** `sqlite3.IntegrityError`  
**Expected Message:** `"Scan ID 999 already exists"`

**Expected Behavior:**
- First insert succeeds and commits
- Second insert rolls back via `get_session()` exception handler
- Database contains only first record

---

### Test Case 4: Invalid Confidence Value
**Scenario:** Call `store_scan()` with out-of-range confidence

**Input:**
```python
db.store_scan(1000, {...}, "text", 1.5, 'tesseract')  # confidence > 1.0
```

**Expected Exception:** `ValueError`  
**Expected Message:** `"confidence must be between 0.0 and 1.0, got 1.5"`

**Expected Behavior:**
- Exception raised before session creation
- No database interaction
- No rollback needed (validation fails early)

---

### Test Case 5: Recent Scans Query
**Scenario:** Retrieve last 50 scans after storing 100

**Input:**
```python
for i in range(100):
    db.store_scan(i, {...}, "text", 0.9, 'tesseract')
scans = db.get_recent_scans(limit=50)
```

**Expected Output:**
- `len(scans) == 50`
- `scans[0]['scan_id']` is largest (most recent)
- `scans[49]['scan_id']` is 50th largest
- All dicts contain keys: `scan_id`, `tracking_id`, `confidence`, etc.

**Expected Behavior:**
- Query uses `ORDER BY timestamp DESC LIMIT 50`
- Session auto-closes after query
- No memory leaks (session registry cleared)

---

## 14. POST-ACTION REPORT

```
✅ **Contract Created:** `docs/contracts/db_sync_refactor.md` v1.0
📋 **Work Order Generated:** See Section 8 (Implementation Plan)
🎯 **Compliance Target:** 100/100 audit score
⚠️  **Critical Path:** Must complete before Phase 8.0 deadline (2026-02-14)
```

---

## 15. APPENDIX: API MAP UPDATE

**⚠️ MANUAL ACTION REQUIRED:** Before proceeding to implementation, copy this snippet into `docs/API_MAP_lite.md` under the Database section:

```markdown
### Module: `database.core`
**Location:** `src/database/core.py`
**Status:** Designed (not yet implemented)
**Contract:** `docs/contracts/db_sync_refactor.md` v1.0

**Public Interface:**
- `init_db(database_url: str = "sqlite:///data/database.db") -> None`
  - Purpose: Initialize SQLAlchemy engine and session factory
  - See contract for full specification
- `get_session() -> Generator[Session, None, None]`
  - Purpose: Context manager for transactional database sessions
  - See contract for full specification

**Dependencies:**
- Imports: sqlalchemy
- Called by: ReceiptRepository, ReceiptDatabase

---

### Module: `database.models`
**Location:** `src/database/models.py`
**Status:** Designed (not yet implemented)
**Contract:** `docs/contracts/db_sync_refactor.md` v1.0

**Public Interface:**
- `ReceiptScan` (SQLAlchemy model class)
  - Purpose: ORM mapping for receipt_scans table
  - See contract for full schema

**Dependencies:**
- Imports: sqlalchemy.orm
- Called by: ReceiptRepository

---

### Module: `database.repository`
**Location:** `src/database/repository.py`
**Status:** Designed (not yet implemented)
**Contract:** `docs/contracts/db_sync_refactor.md` v1.0

**Public Interface:**
- `ReceiptRepository.store_scan(...) -> bool`
- `ReceiptRepository.get_scan(scan_id: int) -> Optional[Dict]`
- `ReceiptRepository.get_scans_by_tracking(tracking_id: str) -> List[Dict]`
- `ReceiptRepository.get_recent_scans(limit: int) -> List[Dict]`
  - Purpose: Thread-safe database operations for receipt scans
  - See contract for full specification

**Dependencies:**
- Imports: database.core, database.models
- Called by: ReceiptDatabase (facade)

---

### Module: `services.receipt_database` (REFACTORED)
**Location:** `src/services/receipt_database.py`
**Status:** Designed (refactor pending)
**Contract:** `docs/contracts/db_sync_refactor.md` v1.0

**Public Interface:** (UNCHANGED)
- `ReceiptDatabase.store_scan(...) -> bool`
- `ReceiptDatabase.get_scan(scan_id: int) -> Optional[Dict]`
- `ReceiptDatabase.get_scans_by_tracking(tracking_id: str) -> List[Dict]`
- `ReceiptDatabase.get_recent_scans(limit: int) -> List[Dict]`
  - Purpose: Compatibility facade over ReceiptRepository
  - See contract for backward compatibility notes

**Dependencies:**
- Imports: database.core, database.repository
- Called by: server.APIServer
```

---

## 16. HUMAN WORKFLOW CHECKPOINT

**Status:** Contract design complete. Ready for implementation phase.

**Files You Should Have:**
- ✅ `docs/contracts/db_sync_refactor.md` v1.0 - The formal contract
- ✅ Work order embedded in Section 8 - Instructions for implementer
- ✅ API Map snippet (Section 15) - Ready to paste

**Before Moving to Next Agent:**
1. **Review the contract** - Does it address threading violations?
2. **Update API_MAP_lite.md** - Paste the snippet from Section 15
3. **Save all files** - Ensure contract is saved
4. **Verify completeness** - All methods specified? Thread safety guaranteed?

**Next Agent to Invoke:** `02_implementer.md`

**Required Files for Implementer:**
- `docs/contracts/db_sync_refactor.md` v1.0
- `docs/system_constraints.md`
- `_STATE.MD`
- `src/services/receipt_database.py` (current version, to be refactored)
- `src/api/server.py` (current version, minimal changes required)

**Verification Command (copy-paste to Implementer):**
```
/verify-context: contracts/db_sync_refactor.md, system_constraints.md, _STATE.MD, receipt_database.py, server.py
```

**Ready to proceed?** If yes, invoke the Implementer agent with the files listed above.

---

## INTEGRATION NOTES

**Upstream Agents:** State Updater (provided problem statement)  
**Downstream Agents:** Implementer (will write code), Auditor (will validate)  
**Critical Dependencies:** system_constraints.md, existing receipt_database.py, server.py  
**Model Recommendation:** Claude Sonnet 4 (complex threading architecture)