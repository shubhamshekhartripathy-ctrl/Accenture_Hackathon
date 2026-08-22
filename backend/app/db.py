"""Database engine/session and the tenant-scoping foundation.

PostgreSQL 16+ (with pgvector) is the canonical system of record — local dev,
Docker, demo and default tests all run on it. SQLite exists ONLY as an
explicitly-selected, test-only escape hatch (isolated unit runs without a
database); it is NEVER the runtime/demo default.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

if settings.is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    # Enable FK enforcement on SQLite (Postgres enforces natively).
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):  # pragma: no cover
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Portable JSON payload type: JSONB on PostgreSQL (binary, indexable), plain
# JSON elsewhere (test-only SQLite). All models use this for dict/list columns.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_db():
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def tenant_filter(model, db: Session, organization_id: str):
    """Mandatory tenant predicate. Raises 404-shaped semantics upstream if empty."""
    return db.query(model).filter(model.organization_id == organization_id)
