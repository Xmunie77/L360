"""Database engine + session factory. Mirrors kitchentable/db.py."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from l360.config import DATABASE_URL
from l360.models import Base


engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables for local/SQLite dev + tests only. No-op on Postgres.

    The `l360` schema is owned by this app's Alembic migrations, run gated
    via workflow_dispatch — never mutated on boot.
    """
    if "postgresql" in str(engine.url):
        return
    Base.metadata.create_all(engine)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session():
    """FastAPI per-request session dependency."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
