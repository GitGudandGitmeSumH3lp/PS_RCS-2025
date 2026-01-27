# CONTRACT: Configuration System
**Version:** 1.0  
**Last Updated:** 2026-01-21  
**Status:** Draft  
**File Location:** `src/config/settings.py`

---

## 1. PURPOSE
Provides type-safe, environment-aware configuration management using Pydantic Settings v2. Validates hardware ports, database connections, and system parameters before application startup. Enforces the "No Hardcoded Ports" constraint from system architecture.

---

## 2. PUBLIC INTERFACE

### Class: `Settings`
**Signature:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, PostgresDsn
from typing import Optional

class Settings(BaseSettings):
    """
    Application-wide configuration loaded from .env file.
    
    All hardware ports and database connections MUST be externalized
    per System Constraint 1: "Serial Ports must be loaded from Environment Variables."
    
    Attributes:
        DATABASE_URL: PostgreSQL connection string (required)
        LIDAR_PORT: Serial port for LiDAR sensor (required)
        HUSKY_PORT: Serial port for HuskyLens device (required)
        MOTOR_PORT: Serial port for Arduino motor controller (required)
        LOG_LEVEL: Python logging level (default: "INFO")
        HARDWARE_POLL_RATE_HZ: Sensor polling frequency (default: 10)
        DB_POOL_SIZE: Database connection pool size (default: 5)
        EMERGENCY_STOP_GPIO_PIN: Optional GPIO pin for E-stop button
        ENABLE_HARDWARE: Hardware mock toggle for testing (default: True)
    
    Raises:
        ValidationError: If required fields missing or validation fails
    """
    
    # Required Fields
    DATABASE_URL: PostgresDsn = Field(
        description="PostgreSQL connection string"
    )
    LIDAR_PORT: str = Field(
        description="Serial port for LiDAR (e.g., /dev/ttyUSB0)"
    )
    HUSKY_PORT: str = Field(
        description="Serial port for HuskyLens (e.g., /dev/ttyUSB1)"
    )
    MOTOR_PORT: str = Field(
        description="Serial port for Motor Controller (e.g., /dev/ttyACM0)"
    )
    
    # Optional with Defaults
    LOG_LEVEL: str = Field(default="INFO")
    HARDWARE_POLL_RATE_HZ: int = Field(default=10, ge=1, le=100)
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    EMERGENCY_STOP_GPIO_PIN: Optional[int] = Field(default=None, ge=0, le=27)
    ENABLE_HARDWARE: bool = Field(default=True)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    @field_validator("LIDAR_PORT", "HUSKY_PORT", "MOTOR_PORT")
    @classmethod
    def validate_serial_port(cls, v: str) -> str:
        """
        Validates serial port paths match expected pattern.
        
        Args:
            v: Port path string
        
        Returns:
            Validated port path
        
        Raises:
            ValueError: If port doesn't match /dev/tty* pattern
        """
        pass
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """
        Validates log level against Python logging standards.
        
        Args:
            v: Log level string
        
        Returns:
            Uppercase log level
        
        Raises:
            ValueError: If not in [DEBUG, INFO, WARNING, ERROR, CRITICAL]
        """
        pass
```

**Behavior Specification:**

**Input Validation:**
- All serial ports MUST match regex: `^/dev/tty[A-Z0-9]+$`
- `DATABASE_URL` must be valid PostgreSQL URI with schema `postgresql+asyncpg://`
- `HARDWARE_POLL_RATE_HZ` must be between 1-100 Hz inclusive
- `LOG_LEVEL` must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- If `EMERGENCY_STOP_GPIO_PIN` is set, value must be valid Raspberry Pi GPIO pin (0-27)

**Processing Logic:**
1. Load `.env` file from project root
2. Parse environment variables into typed fields
3. Run Pydantic validators on all fields
4. Raise `ValidationError` with detailed messages if any validation fails

**Output Guarantee:**
- Returns fully validated `Settings` instance
- All serial ports are guaranteed to match Linux device naming conventions
- Database URL is guaranteed to be parseable by SQLAlchemy

**Side Effects:**
- Reads `.env` file from filesystem
- No external I/O or network calls during initialization

---

## 3. ERROR HANDLING

**Error Case 1: Missing Required Field**
- **Condition:** `.env` file missing `DATABASE_URL`, `LIDAR_PORT`, `HUSKY_PORT`, or `MOTOR_PORT`
- **Behavior:** Raise `ValidationError` with message:
  ```
  Field required [type=missing, input_value={...}, input_type=dict]
  For further information visit https://errors.pydantic.dev/...
  ```

**Error Case 2: Invalid Serial Port Pattern**
- **Condition:** Port value doesn't start with `/dev/tty`
- **Behavior:** Raise `ValueError` with message:
  ```
  Serial port must match pattern /dev/tty* (received: {value})
  ```

**Error Case 3: Invalid Poll Rate**
- **Condition:** `HARDWARE_POLL_RATE_HZ < 1` or `> 100`
- **Behavior:** Raise `ValidationError` with message:
  ```
  Input should be greater than or equal to 1 [type=greater_than_equal]
  ```

**Error Case 4: Invalid Log Level**
- **Condition:** `LOG_LEVEL` not in allowed values
- **Behavior:** Raise `ValueError` with message:
  ```
  LOG_LEVEL must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL (received: {value})
  ```

---

## 4. PERFORMANCE REQUIREMENTS
- **Time Complexity:** O(1) - Single file read + validation pass
- **Space Complexity:** O(1) - Fixed number of configuration fields
- **Startup Time:** Must complete in < 100ms

---

## 5. DEPENDENCIES

**This module CALLS:**
- `pydantic_settings.BaseSettings` - Configuration base class
- `pydantic.Field` - Field metadata and validation
- `pydantic.field_validator` - Custom validation decorators
- Standard library: `os`, `typing`

**This module is CALLED BY:**
- `src/core/service_manager.py` - Loads config at startup
- `server.py` - Initializes Flask app with validated config
- Test suites - Validates config in CI/CD

---

## 6. DATA STRUCTURES

```python
# Example instantiation
settings = Settings()

# Access pattern
database_url: str = settings.DATABASE_URL
lidar_port: str = settings.LIDAR_PORT
poll_rate: int = settings.HARDWARE_POLL_RATE_HZ
```

**Environment Variable Example (`.env`):**
```env
DATABASE_URL=postgresql+asyncpg://robot:password@localhost:5432/robotics
LIDAR_PORT=/dev/ttyUSB0
HUSKY_PORT=/dev/ttyUSB1
MOTOR_PORT=/dev/ttyACM0
HARDWARE_POLL_RATE_HZ=20
LOG_LEVEL=DEBUG
ENABLE_HARDWARE=True
```

---

## 7. CONSTRAINTS (FROM SYSTEM RULES)

1. **Serial Ports Must Be Environment Variables** (System Constraint 1)
   - Enforced via Pydantic's `env_file` loading
   - NEVER allow hardcoded `/dev/ttyUSB0` in source code

2. **Python 3.9+ Type Hints** (System Constraint 3)
   - All fields use proper type annotations
   - Generic types from `typing` module

3. **No Config Files in Source Folders** (System Constraint 4)
   - Settings class lives in `src/config/` directory
   - Loads from `.env` at project root

---

## 8. ACCEPTANCE CRITERIA (Test Cases)

### Test Case 1: Valid Configuration Load
**Scenario:** All required environment variables present and valid

**Input (.env):**
```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
LIDAR_PORT=/dev/ttyUSB0
HUSKY_PORT=/dev/ttyUSB1
MOTOR_PORT=/dev/ttyACM0
```

**Expected Output:**
```python
settings = Settings()
assert settings.LIDAR_PORT == "/dev/ttyUSB0"
assert settings.HARDWARE_POLL_RATE_HZ == 10  # Default value
assert isinstance(settings.DATABASE_URL, str)
```

**Expected Behavior:** No exceptions raised, all defaults applied

---

### Test Case 2: Invalid Serial Port Pattern
**Scenario:** User provides Windows-style COM port

**Input (.env):**
```env
LIDAR_PORT=COM3
HUSKY_PORT=/dev/ttyUSB1
MOTOR_PORT=/dev/ttyACM0
DATABASE_URL=postgresql+asyncpg://localhost/db
```

**Expected Exception:** `ValueError`

**Expected Message Pattern:**
```
Serial port must match pattern /dev/tty* (received: COM3)
```

---

### Test Case 3: Missing Required Field
**Scenario:** `.env` file missing `DATABASE_URL`

**Input (.env):**
```env
LIDAR_PORT=/dev/ttyUSB0
HUSKY_PORT=/dev/ttyUSB1
MOTOR_PORT=/dev/ttyACM0
```

**Expected Exception:** `ValidationError`

**Expected Message Pattern:**
```
1 validation error for Settings
DATABASE_URL
  Field required
```

---

### Test Case 4: Out-of-Range Poll Rate
**Scenario:** User sets poll rate to 200 Hz

**Input (.env):**
```env
DATABASE_URL=postgresql+asyncpg://localhost/db
LIDAR_PORT=/dev/ttyUSB0
HUSKY_PORT=/dev/ttyUSB1
MOTOR_PORT=/dev/ttyACM0
HARDWARE_POLL_RATE_HZ=200
```

**Expected Exception:** `ValidationError`

**Expected Message Pattern:**
```
Input should be less than or equal to 100
```

---

## 9. IMPLEMENTATION NOTES

### For the Builder:
1. Use Pydantic v2 syntax (not v1 `Config` class)
2. Import from `pydantic_settings` not `pydantic`
3. Test with both missing `.env` and malformed values
4. Consider adding `model_dump()` method for debugging output
5. GPIO pin validation should check Raspberry Pi BCM pin ranges (0-27)

### Pydantic V2 Migration Notes:
- Use `model_config = SettingsConfigDict()` instead of `class Config`
- Validators use `@field_validator` decorator, not `@validator`
- Field constraints use `Field(ge=1)` syntax

---

**END OF CONTRACT**