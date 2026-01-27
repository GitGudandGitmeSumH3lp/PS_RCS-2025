[From TECHNICAL DEBT ALERT]
**Constraint - Imports:** Moving files will break `from backend import X`. Mass search/replace required.

[From LEGACY CONSTRAINTS]
**Constraint - Backend:** Python 3.9+ (Flask).

[From TECHNICAL DEBT ALERT]
**Risk - API Duplication:** api_server.py, api_server2.py, etc. must be diffed before deletion.

[2024-01-15] **Decision:** Database layer must strictly use AsyncSQLAlchemy (v2.0 syntax) for all core connections to support the new async `server.py` structure.
[2024-01-20] **Constraint:** All schema definitions must decouple Pydantic models (DTOs) from ORM models. Do not mix them in `core.py`.
[2024-01-22] **Pattern:** Legacy integration requires mapping old integer IDs to new UUIDs during the consolidation phase; ensure the base model supports dual-key lookup if necessary.

[2024-01-15] **Decision/Pattern:** The database layer has migrated to fully asynchronous drivers. All core classes should be prefixed with `Async` (e.g., `AsyncDatabaseEngine`).
[2024-01-15] **Constraint:** Synchronous wrappers for the database are deprecated.