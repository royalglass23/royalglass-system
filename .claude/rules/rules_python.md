# Python and FastAPI Rules

## Python Version

Inside Docker containers: Python 3.11 (set in Dockerfile).
Local machine: Python 3.12.

**Do not use passlib.** It has compatibility issues with newer bcrypt versions and Python 3.11+. Use bcrypt directly everywhere — both locally and inside Docker.

```python
import bcrypt

# Hash
hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# Verify
bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

## FastAPI Patterns

**Dependency injection for database sessions:**
```python
# Always use get_db() as a dependency — never create sessions manually
def my_endpoint(db: Session = Depends(get_db)):
    ...
```

**Dependency injection for auth:**
```python
# All protected endpoints must use get_current_user
def my_endpoint(user: dict = Depends(get_current_user)):
    ...user["email"], user["name"], user["role"]
```

**Raw SQL over ORM:**
Use `db.execute(text("..."), params)` for all queries. We use raw SQL, not SQLAlchemy ORM models. This keeps queries readable and close to what is in the database.

**Always use parameterised queries:**
```python
# CORRECT
db.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email})

# NEVER do this — SQL injection risk
db.execute(text(f"SELECT * FROM users WHERE email = '{email}'"))
```

**Response patterns:**
- Use Pydantic `BaseModel` for request bodies and response schemas
- Use `response_model=` on endpoints that return structured data
- Return plain dicts for simple success messages: `{"message": "...", "job_uuid": "..."}`

## Error Handling

```python
from fastapi import HTTPException

# 404 for missing records
raise HTTPException(status_code=404, detail="Item not found.")

# 401 for auth failures
raise HTTPException(status_code=401, detail="Invalid or expired token.")

# 403 for permission failures
raise HTTPException(status_code=403, detail="Account is disabled.")
```

## Database Commits

Always commit after writes:
```python
db.execute(text("INSERT ..."), params)
db.commit()
```

Always rollback on error if you catch exceptions manually.

## Change Log

Every data change (sync or manual) must write to `change_log`. Pattern:
```python
db.execute(text("""
    INSERT INTO change_log
        (table_name, record_uuid, field_name, old_value, new_value, change_source, changed_by)
    VALUES
        (:table, :uuid, :field, :old, :new, :source, :who)
"""), {...})
```

## File Organisation

- `app/config.py` — settings only, no logic
- `app/database.py` — engine and get_db() only
- `app/auth.py` — JWT and password utils only
- `app/routers/` — one file per logical group of endpoints
- Never put business logic in `main.py` — it only registers routers

## Imports

```python
# Standard library first
from datetime import datetime
from typing import Optional

# Third party second
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# Local last
from app.database import get_db
from app.auth import get_current_user
```
