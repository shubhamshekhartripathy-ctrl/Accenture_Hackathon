"""Decision workspace API (arch §704) + portfolio (AC22).

GET  /decisions/{id}/impacts      — second-order effects + dependency paths
GET  /decisions/{id}/guardrails   — per-guardrail threshold vs projection
GET  /decisions/collisions        — detected collisions (investigation-scoped)
POST /decisions/collisions/{id}/resolve — humans resolve (never auto)
GET  /decisions/portfolio         — aggregation from stored artifacts ONLY
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..domains.decisions import service as decisions_service
from ..domains.decisions.collisions import resolve_collision, serialize_collision
from ..domains.investigations import service as investigations_service
from ..envelope import ok
from ..errors import AppError
from ..models.decisions import DecisionCollision, DecisionOption, DecisionRecord
from ..models.impacts import ImpactMetric
from ..models.investigation import Investigation
from ..models.org import User
from ..security.deps import require_roles

router = APIRouter(tags=["decisions"])

_read_guard = require_roles("KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN")
_resolve_guard = require_roles("KPI_OWNER", "EXECUTIVE", "ADMIN")  # governance act, humans only


def _option(db: Session, organization_id: str, option_id: str) -> tuple[Investigation, DecisionOption]:
    opt = (
        db.query(DecisionOption)
        .filter(DecisionOption.organization_id == organization_id, DecisionOption.id == option_id)
        .first()
    )
    if opt is None:
        raise AppError("NOT_FOUND", "Option not found", 404)
    inv = (
        db.query(Investigation)
        .filter(Investigation.organization_id == organization_id,
                Investigation.id == opt.investigation_id)
        .first()
    )
    if inv is None:
        raise AppError("NOT_FOUND", "Investigation not found", 404)
    return inv, opt


@router.get("/decisions/{option_id}/impacts")
def get_impacts(option_id: str, request: Request, user: User = Depends(_read_guard),
                db: Session = Depends(get_db)):
    """Direct + second-order effects with dependency paths (AC20)."""
    _, opt = _option(db, user.organization_id, option_id)
    sim = opt.simulation or {}
    metrics = {m.code: {"name": m.name, "unit": m.unit, "definition": m.definition,
                        "formula": m.formula, "provenance": m.provenance}
               for m in db.query(ImpactMetric)
               .filter(ImpactMetric.organization_id == user.organization_id).all()}
    return ok(request, {
        "option_id": opt.id, "code": opt.code,
        "method": "graph_elasticity",
        "direct_pct": (sim.get("inputs", {}).get("deltas", {}) or {}).get("direct_pct", {}),
        "second_order": sim.get("second_order", {}),
        "derived_metrics": metrics,
        "simulation_version": opt.simulation_version,
    })


@router.get("/decisions/{option_id}/guardrails")
def get_guardrails(option_id: str, request: Request, user: User = Depends(_read_guard),
                   db: Session = Depends(get_db)):
    """Per-guardrail status with threshold vs projection (AC19)."""
    _, opt = _option(db, user.organization_id, option_id)
    sim = opt.simulation or {}
    return ok(request, {
        "option_id": opt.id, "code": opt.code,
        "status": opt.guardrail_status,
        "reasons": opt.guardrail_reasons,
        "projection": sim.get("projected", {}),
        "arithmetic": sim.get("arithmetic", []),
    })


@router.get("/decisions/collisions")
def list_collisions(request: Request, investigation_id: str | None = None,
                    user: User = Depends(_read_guard), db: Session = Depends(get_db)):
    q = db.query(DecisionCollision).filter(
        DecisionCollision.organization_id == user.organization_id)
    if investigation_id:
        inv = investigations_service.get_investigation(db, user.organization_id, investigation_id)
        q = q.filter(DecisionCollision.investigation_id == inv.id)
    rows = q.order_by(DecisionCollision.created_at.asc()).all()
    return ok(request, [serialize_collision(r) for r in rows])


class ResolveIn(BaseModel):
    resolution: str  # SEQUENCE | ESCALATE_COMBINED | ABANDON_ONE
    note: str


@router.post("/decisions/collisions/{collision_id}/resolve")
def resolve(collision_id: str, body: ResolveIn, request: Request,
            user: User = Depends(_resolve_guard), db: Session = Depends(get_db)):
    """Humans resolve collisions; the system never auto-optimizes (AC21)."""
    row = resolve_collision(db, user.organization_id, collision_id, user.id, user.role,
                            body.resolution, body.note)
    db.commit()
    return ok(request, serialize_collision(row))


@router.get("/decisions/portfolio")
def portfolio(request: Request, user: User = Depends(_read_guard),
              db: Session = Depends(get_db)):
    """AC22 — derived from stored artifacts only. Never invents quantitative truth."""
    org = user.organization_id
    options = db.query(DecisionOption).filter(DecisionOption.organization_id == org).all()
    records = db.query(DecisionRecord).filter(DecisionRecord.organization_id == org).all()
    collisions = db.query(DecisionCollision).filter(DecisionCollision.organization_id == org).all()
    rec_by_option = {r.option_id: r for r in records}

    active = []
    for o in options:
        rec = rec_by_option.get(o.id)
        if rec is None or rec.status not in ("APPROVED", "OVERRIDDEN", "PENDING"):
            continue
        active.append({
            "option_code": o.code,
            "investigation_id": o.investigation_id,
            "owner_role": o.owner_role,
            "target_kpi": o.driver,
            "expected_impact_rs": o.expected_impact_rs,
            "guardrail_status": o.guardrail_status,
            "collision_status": any(not c.resolved and o.id in (c.option_ids or []) for c in collisions),
            "approval_status": rec.status,
            "monitoring_plan": rec.monitoring_plan,
        })

    approved = [a for a in active if a["approval_status"] in ("APPROVED", "OVERRIDDEN")]
    combined_benefit = sum(a["expected_impact_rs"] for a in approved)

    # honest arithmetic: range = sum of the stored bounds of the approved options
    approved_ids = {r.option_id for r in records if r.status in ("APPROVED", "OVERRIDDEN")}
    lo = sum(o.impact_lo_rs for o in options if o.id in approved_ids)
    hi = sum(o.impact_hi_rs for o in options if o.id in approved_ids)

    guardrail_pass = sum(1 for o in options if o.guardrail_status == "PASS")
    guardrail_evaluated = sum(1 for o in options if o.guardrail_status)
    unresolved = [c for c in collisions if not c.resolved]
    pending = [r for r in records if r.status == "PENDING"]

    # highest cost of waiting — from stored abstention artifacts only
    invs = db.query(Investigation).filter(Investigation.organization_id == org).all()
    wait_levels = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
    waiting = [
        {"investigation_id": i.id, "level": (i.abstention or {}).get("cost_of_waiting_level"),
         "note": (i.abstention or {}).get("is_waiting_safer")}
        for i in invs if (i.abstention or {}).get("cost_of_waiting_level")
    ]
    waiting.sort(key=lambda w: -wait_levels.get(w["level"], 0))

    g_rate = (guardrail_pass / guardrail_evaluated) if guardrail_evaluated else 1.0
    c_rate = 1 - (len(unresolved) / len(collisions)) if collisions else 1.0
    f_rate = (len(records) - len(pending)) / len(records) if records else 1.0
    health = round(0.4 * g_rate + 0.3 * c_rate + 0.3 * f_rate, 4)

    return ok(request, {
        "active_decisions": active,
        "combined_expected_benefit_rs": combined_benefit,
        "combined_benefit_range_rs": [lo, hi],
        "combined_benefit_arithmetic": "sum of stored impacts; range = sum of stored bounds",
        "guardrail_summary": {"pass": guardrail_pass, "evaluated": guardrail_evaluated},
        "unresolved_collisions": [serialize_collision(c) for c in unresolved],
        "awaiting_approval": [{"option_code": next(o.code for o in options if o.id == r.option_id),
                               "requested_by": r.requested_by_role} for r in pending],
        "highest_cost_of_waiting": waiting[0] if waiting else None,
        "portfolio_health": {
            "score": health,
            "formula": "0.4×guardrail_pass_rate + 0.3×collision_free + 0.3×approval_freshness",
            "inputs": {"guardrail_pass_rate": round(g_rate, 4), "collision_free": round(c_rate, 4),
                       "approval_freshness": round(f_rate, 4)},
        },
    })
