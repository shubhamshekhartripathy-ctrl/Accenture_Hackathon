"""Success-envelope helper. Every 2xx response is wrapped as
{"data": ..., "meta": {"request_id", "timestamp"}}."""
from __future__ import annotations

from typing import Any

from fastapi import Request


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def ok(request: Request, data: Any) -> dict:
    return {
        "data": data,
        "meta": {"request_id": getattr(request.state, "request_id", None), "timestamp": _utcnow_iso()},
    }
