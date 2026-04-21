"""
database.py
Sets up the SQLAlchemy engine and session factory.
Every API endpoint that needs the database calls get_db() as a dependency.

WHY SQLAlchemy?
- It handles connection pooling automatically
- It works with PostgreSQL and any future database
- It lets us write Python instead of raw SQL for most operations
- Raw SQL is still available when needed (like for the dashboard_view query)
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import settings


# The engine manages the connection pool to PostgreSQL
# pool_pre_ping=True means SQLAlchemy checks the connection is alive before using it
# This handles the case where the DB container restarts
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,          # Max 5 persistent connections
    max_overflow=10,      # Up to 10 extra connections under load
)

# SessionLocal is a factory that creates database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency. Opens a DB session for the duration of a request,
    then closes it automatically when the request is done.

    Usage in an endpoint:
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Used by the health check endpoint to verify DB is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
