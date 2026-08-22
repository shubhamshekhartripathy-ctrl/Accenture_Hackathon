"""Investigation lifecycle endpoints (arch P.1) — the pipeline's public surface."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..domains.explain import decomposition as explain_decomposition
from ..domains.investigations import service as investigations_service
from ..envelope import ok
from ..errors import AppError
from ..models.decisions import DecisionOption
from ..models.org import User
from ..security.deps import require_roles

router = APIRouter(tags=["investigations"])

_start_guard = require_roles("ANALYST", "ADMIN")
_read_guard = require_roles("KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN")


class CreateInvestigationIn(BaseModel):
    kpi_id: str


@router.post("/investigations")
def create_investigation(
    body: CreateInvestigationIn,
    request: Request,
    user: User = Depends(_start_guard),
    db: Session = Depends(get_db),
):
    inv = investigations_service.create_investigation(
        db, user.organization_id, body.kpi_id, user.id, user.role
    )
    return ok(request, investigations_service.serialize(db, inv))


@router.get("/investigations")
def list_investigations(
    request: Request,
    kpi_id: str | None = None,
    limit: int = 20,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    rows = investigations_service.list_for_user(db, user.organization_id, user, kpi_id=kpi_id, limit=limit)
    return ok(request, [investigations_service.serialize(db, r) for r in rows])


@router.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: str,
    request: Request,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    inv = investigations_service.get_investigation(db, user.organization_id, investigation_id)
    return ok(request, investigations_service.serialize(db, inv))


@router.get("/investigations/{investigation_id}/decomposition")
def get_decomposition(
    investigation_id: str,
    request: Request,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    inv = investigations_service.get_investigation(db, user.organization_id, investigation_id)
    rows = explain_decomposition.get_decomposition(db, user.organization_id, inv.id)
    baseline = inv.summary.get("detection_baseline") if inv.summary else None
    return ok(request, {
        "investigation_id": inv.id,
        "kpi_id": inv.kpi_id,
        "workflow_state": inv.workflow_state,
        "components": [explain_decomposition.serialize(r) for r in rows],
        "sum_value": round(sum(r.value for r in rows), 6),
        "sum_pct": round(sum(r.pct for r in rows), 4),
        "identity_note": "components + residual reconcile to the observed movement by construction",
    })


@router.get("/investigations/{investigation_id}/explain")
def get_explain(
    investigation_id: str,
    request: Request,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    """The structured conclusion object (H.1 quantitative truth layer)."""
    inv = investigations_service.get_investigation(db, user.organization_id, investigation_id)
    data = investigations_service.serialize(db, inv, viewer_role=user.role)
    return ok(request, {
        "investigation_id": inv.id,
        "workflow_state": inv.workflow_state,
        "summary": inv.summary,
        "reliability": inv.reliability_snapshot,
        "confidence_cap": inv.confidence_cap_snapshot,
        "hypotheses": data["hypotheses"],
        "detection": data["detection"],
        "materiality": data["materiality"],
        "telemetry": data["telemetry"],
    })


@router.get("/investigations/{investigation_id}/brief")
def get_brief(
    investigation_id: str,
    request: Request,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    """Persona brief (AC9): one conclusion object, a governed view per role."""
    from ..domains.briefs import service as briefs_service

    inv = investigations_service.get_investigation(db, user.organization_id, investigation_id)
    base = investigations_service.serialize(db, inv, viewer_role=user.role)
    brief = briefs_service.persona_view(db, user.organization_id, inv, user, base)
    db.commit()
    return ok(request, brief)


class DecideIn(BaseModel):
    decision: str  # APPROVE | REJECT | OVERRIDE
    override_reason: str | None = None


@router.get("/investigations/{investigation_id}/decisions")
def get_decisions(
    investigation_id: str,
    request: Request,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    """Options with simulation, guardrail verdicts, rights, and any decision records."""
    inv = investigations_service.get_investigation(db, user.organization_id, investigation_id)
    data = investigations_service.serialize(db, inv, viewer_role=user.role)
    return ok(request, {"investigation_id": inv.id, "workflow_state": inv.workflow_state,
                        "certainty_state": inv.certainty_state, "options": data["options"],
                        "collisions": data.get("collisions", [])})


@router.post("/investigations/{investigation_id}/decisions/{option_id}")
def decide_option(
    investigation_id: str,
    option_id: str,
    body: DecideIn,
    request: Request,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    """Human decision on an option (AC12): approve / reject / override(with reason)."""
    from ..domains.decisions import service as decisions_service
    from ..services.pipeline.runner import RunContext, Stage, run_stages

    inv = investigations_service.get_investigation(db, user.organization_id, investigation_id)
    option = (
        db.query(DecisionOption)
        .filter(DecisionOption.organization_id == user.organization_id,
                DecisionOption.id == option_id,
                DecisionOption.investigation_id == inv.id)
        .first()
    )
    if option is None:
        raise AppError("NOT_FOUND", "Option not found on this investigation", 404)

    record = decisions_service.decide(
        db, user.organization_id, inv, option, user.id, user.role,
        body.decision, override_reason=body.override_reason,
    )

    # Approval advances the governed workflow: record → portfolio → human gate → decided.
    if inv.workflow_state == "RIGHTS_CHECKED" and record.status in ("APPROVED", "REJECTED", "OVERRIDDEN"):
        stages = [
            Stage("decision_record", "rules", ("RIGHTS_CHECKED", "DECISION_RECORD_CREATED"),
                  "decision_recorded", f"Decision record created ({record.status})", lambda c: record),
            Stage("portfolio", "rules", ("DECISION_RECORD_CREATED", "PORTFOLIO_UPDATED"),
                  "portfolio_updated", "Decision portfolio updated", lambda c: None),
            Stage("human_approval", "rules", ("PORTFOLIO_UPDATED", "HUMAN_APPROVAL"),
                  "awaiting_formal_signoff" if record.status == "PENDING" else "human_decision_recorded",
                  f"{record.status} by {record.approved_by_role}", lambda c: None),
        ]
        terminal = {"APPROVED": ("approved", ("HUMAN_APPROVAL", "APPROVED"), "decision_approved", f"Option {option.code} APPROVED — monitoring plan active"),
                    "REJECTED": ("rejected", ("HUMAN_APPROVAL", "REJECTED"), "decision_rejected", f"Option {option.code} rejected"),
                    "OVERRIDDEN": ("overridden", ("HUMAN_APPROVAL", "OVERRIDDEN"), "decision_overridden", f"Option {option.code} overridden — reason recorded for learning")}[record.status]
        stages.append(Stage(terminal[0], "rules", terminal[1], terminal[2], terminal[3], lambda c: record))
        ctx = RunContext(db=db, investigation=inv, organization_id=user.organization_id, run_id=f"inv-{inv.id[:12]}")
        run_stages(ctx, stages)
    db.commit()
    return ok(request, decisions_service.serialize(option, record))
