import os
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Ensure the data directory exists before the engine tries to create the file.
# Skipped for in-memory databases (used in tests).
# ---------------------------------------------------------------------------
if "sqlite" in settings.DATABASE_URL and ":memory:" not in settings.DATABASE_URL:
    # Extract the file path from a URL like sqlite:///./data/dev.db
    _raw_path = settings.DATABASE_URL.split("sqlite:///")[-1]
    _db_dir = os.path.dirname(os.path.abspath(_raw_path))
    os.makedirs(_db_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Engine
# check_same_thread=False is required for SQLite in multi-threaded WSGI/ASGI.
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    """
    Run per-connection PRAGMAs.

    WAL mode:     allows concurrent reads alongside a single writer — important
                  even at small scale as it prevents SQLITE_BUSY errors.
    foreign_keys: SQLite disables FK enforcement by default; we always want it.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    # expire_on_commit=False means ORM objects stay usable after commit without
    # triggering lazy loads — critical since we return them from services after
    # committing and the session may be closed before the response is serialised.
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Yields a database session for the duration of a single request.
    FastAPI's dependency system caches this within a request, so all
    services/repos in a single request share the same session and transaction.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
