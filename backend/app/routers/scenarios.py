"""Scenarios router — list/detail/start (arch P.2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..domains.scenarios import service as scenarios
from ..envelope import ok
from ..models.org import User
from ..security.deps import require_roles

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

_read_guard = require_roles("KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN")
_start_guard = require_roles("ANALYST", "ADMIN", "EXECUTIVE")


@router.get("")
def list_scenarios(request: Request, user: User = Depends(_read_guard), db: Session = Depends(get_db)):
    rows = scenarios.list_templates(db, user.organization_id)
    return ok(request, [scenarios.card(t) for t in rows])


@router.get("/{scenario_id}")
def get_scenario(
    request: Request,
    scenario_id: str,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    template = scenarios.get_template(db, user.organization_id, scenario_id)
    return ok(request, scenarios.detail(template))


@router.post("/{scenario_id}/start")
def start_scenario(
    request: Request,
    scenario_id: str,
    user: User = Depends(_start_guard),
    db: Session = Depends(get_db),
):
    template = scenarios.get_template(db, user.organization_id, scenario_id)
    ws = scenarios.start_scenario(db, user.organization_id, template, user.id, user.role)
    return ok(request, ws)
