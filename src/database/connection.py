"""
Database connection and session management for RevOps Orchestrator.

Provides:
- SQLAlchemy engine and session factory
- init_db() to create tables (used in startup + tests)
- get_db() dependency for FastAPI
- Context manager for scripts
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

# Global engine (created lazily)
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create the SQLAlchemy engine (singleton pattern)."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            _settings.database_url,
            echo=_settings.database_echo,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 10},
        )
        logger.info("Database engine created")
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    Usage: db: Session = Depends(get_db)
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for scripts, tests, and non-FastAPI code.
    Usage:
        with db_session() as db:
            db.query(...)
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(create_tables: bool = True) -> None:
    """
    Initialize database: create all tables if they do not exist.
    Safe to call multiple times.
    """
    from src.database.models import Base

    engine = get_engine()
    if create_tables:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")


def reset_db() -> None:
    """Dangerous: Drop all tables and recreate. Only for demo / test environments."""
    from src.database.models import Base

    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.warning("Database has been reset (all data lost)")


def check_connection() -> bool:
    """Quick health check for database connectivity."""
    try:
        with get_engine().connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
