from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def _create_engine():
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # Ensure the local SQLite parent directory exists before first connect.
        sqlite_path = settings.database_url.replace("sqlite:///", "", 1)
        if sqlite_path and sqlite_path != ":memory:":
            Path(sqlite_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a transactional SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
