"""Audit trail read API — governed mutations are inspectable (transparency)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..envelope import ok
from ..models.org import AuditEvent, User
from ..security.deps import require_roles

router = APIRouter(tags=["audit"])

_read_guard = require_roles("ADMIN", "KPI_OWNER", "EXECUTIVE")


@router.get("/audit")
def list_audit(
    request: Request,
    action: str | None = None,
    limit: int = 100,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    q = db.query(AuditEvent).filter(AuditEvent.organization_id == user.organization_id)
    if action:
        q = q.filter(AuditEvent.action == action)
    rows = q.order_by(AuditEvent.created_at.desc()).limit(min(limit, 500)).all()
    return ok(request, [
        {
            "id": r.id, "action": r.action, "object_type": r.object_type, "object_id": r.object_id,
            "actor_user_id": r.actor_user_id, "actor_role": r.actor_role, "outcome": r.outcome,
            "details": r.details, "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ])
