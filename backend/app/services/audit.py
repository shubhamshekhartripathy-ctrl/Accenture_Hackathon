"""Audit writer — every governed mutation records an immutable row."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models.org import AuditEvent


def record(
    db: Session,
    organization_id: str,
    action: str,
    object_type: str,
    object_id: str | None = None,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    outcome: str = "success",
    details: dict | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        object_type=object_type,
        object_id=object_id,
        outcome=outcome,
        details=details or {},
        request_id=request_id,
    )
    db.add(event)
    return event
