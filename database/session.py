"""Engine/session factory — STEP 9. WRITTEN BUT NOT EXECUTED (see models.py docstring: sqlalchemy
is not installed in this sandbox, no network access to install it).

WZ_DATABASE_URL (see .env.example) defaults to `sqlite:///./wardzero.db` for local development and
accepts any SQLAlchemy-compatible PostgreSQL URL for production, per the spec's "PostgreSQL-compatible
architecture, SQLite fallback for development" requirement. No code elsewhere should import a
DB-specific dialect directly — always go through `get_session()` here so swapping the URL is enough.
"""
from __future__ import annotations
import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

DEFAULT_URL = "sqlite:///./wardzero.db"


def make_engine(url: str | None = None):
    url = url or os.environ.get("WZ_DATABASE_URL", DEFAULT_URL)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


_engine = None
_SessionLocal = None


def init_db(url: str | None = None):
    """Create the engine + all tables (idempotent — CREATE TABLE IF NOT EXISTS semantics via
    checkfirst=True). Call once at app startup. Real deployments should use Alembic migrations
    (scripts/migrations/ — STEP 9) instead of create_all for anything beyond local dev."""
    global _engine, _SessionLocal
    _engine = make_engine(url)
    Base.metadata.create_all(_engine, checkfirst=True)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


@contextmanager
def get_session():
    if _SessionLocal is None:
        init_db()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
