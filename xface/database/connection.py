"""Database connection and session factory using SQLAlchemy for xFACE."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from xface.config import settings
from xface.database.models import Base

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Make sure the directory holding a file-based SQLite database exists
if _is_sqlite:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

# Create engine with thread-safe settings for SQLite
connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def init_db() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit/rollback."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
