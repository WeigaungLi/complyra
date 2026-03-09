"""
Database Connection Setup

This file sets up the connection between the Python application and the
database. It creates three things that the rest of the codebase uses:

1. Base — The parent class that all database table models inherit from.
   (See models.py, where every class starts with "class Foo(Base)".)

2. engine — The low-level database connection manager. It knows the
   database URL (e.g., SQLite file path or PostgreSQL address) and
   handles connection pooling (reusing connections for efficiency).

3. SessionLocal — A factory that creates database "sessions". A session
   is like a conversation with the database: you open one, run some
   queries, save your changes (commit), and then close it.

4. get_db() — A helper for FastAPI (the web framework) that provides
   a session to each incoming web request and ensures it is properly
   closed afterward.
"""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Every database table class in models.py inherits from this class.
    SQLAlchemy uses this to keep track of all table definitions and
    to generate the actual database schema (CREATE TABLE statements).
    """


def _create_engine():
    """Create and configure the SQLAlchemy database engine.

    The engine manages the actual connection(s) to the database.
    It reads the database URL from application settings and applies
    any database-specific configuration needed.
    """
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        # SQLite-specific: allow multiple threads to share the same connection.
        # SQLite normally restricts connections to a single thread, but our
        # web server uses multiple threads to handle requests concurrently.
        connect_args = {"check_same_thread": False}
        # Ensure the directory for the SQLite database file exists.
        # For example, if the database URL is "sqlite:///data/app.db",
        # this creates the "data/" directory if it doesn't exist yet.
        sqlite_path = settings.database_url.replace("sqlite:///", "", 1)
        if sqlite_path and sqlite_path != ":memory:":
            Path(sqlite_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        settings.database_url,
        # pool_pre_ping=True checks if a connection is still alive before
        # using it. This prevents errors from stale/broken connections.
        pool_pre_ping=True,
        # future=True enables SQLAlchemy 2.0-style usage patterns.
        future=True,
        connect_args=connect_args,
    )


# Create the engine once when this module is first imported.
# All parts of the application share this single engine instance.
engine = _create_engine()

# SessionLocal is a factory (a "session maker") that creates new database
# sessions on demand. Configuration:
#   - autocommit=False: Changes are NOT saved automatically; you must call
#     session.commit() explicitly. This gives you control over transactions.
#   - autoflush=False: Changes are NOT sent to the database automatically
#     before queries. This avoids surprising side effects.
#   - expire_on_commit=False: After committing, objects remain usable in
#     Python without triggering extra database reads. This is important
#     because our functions often return objects after committing.
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session to each request.

    Usage in a FastAPI route:
        @app.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    The "yield" pattern ensures the session is always closed after the
    request finishes, even if an error occurs. This prevents database
    connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
