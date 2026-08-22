"""Health router — component states degrade loudly, never silently (§5A).

/health/ready reports postgres | pgvector | redis | llm as ok | degraded | deterministic.
"""
from __future__ import annotations

import socket

from fastapi import APIRouter, Request

from ..config import settings
from ..envelope import ok

router = APIRouter(prefix="/health", tags=["health"])


def _check_pgvector() -> str:
    if settings.is_sqlite:
        return "unavailable (offline mode — hashing fallback active)"  # visible degraded state
    try:
        from sqlalchemy import text

        from ..db import engine

        with engine.connect() as conn:
            row = conn.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'")).fetchone()
            return "ok" if row else "degraded (extension not installed)"
    except Exception:
        return "degraded (check failed)"


def _check_redis() -> str:
    if not settings.redis_url:
        return "degraded (not configured — in-process fallbacks active)"
    try:
        parsed = settings.redis_url.replace("redis://", "").split(":")
        host = parsed[0]
        port = int(parsed[1].split("/")[0]) if len(parsed) > 1 else 6379
        with socket.create_connection((host, port), timeout=1.0):
            return "ok"
    except Exception:
        return "degraded (unreachable — in-process fallbacks active)"
    return "ok"


@router.get("/live")
def live(request: Request):
    return ok(request, {"status": "alive", "app": settings.app_name, "env": settings.env})


@router.get("/ready")
def ready(request: Request):
    db_state = "ok"
    db_kind = "postgres"
    if settings.is_sqlite:
        db_kind = "sqlite"
        db_state = "ok (offline documented fallback)"
    try:
        from sqlalchemy import text

        from ..db import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_state = "down"
    llm_state = "ok" if (settings.openai_api_key or settings.embedding_api_key) else "deterministic"
    components = {
        "database": {"kind": db_kind, "state": db_state},
        "pgvector": _check_pgvector(),
        "redis": _check_redis(),
        "llm": llm_state,
    }
    overall = "ready" if db_state.startswith("ok") else "unavailable"
    return ok(request, {"status": overall, "components": components, "demo_mode": settings.demo_mode})
