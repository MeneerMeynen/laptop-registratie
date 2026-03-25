from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


# Engine is created lazily so tests can override DATABASE_URL before import.
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        from app.config import settings

        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
