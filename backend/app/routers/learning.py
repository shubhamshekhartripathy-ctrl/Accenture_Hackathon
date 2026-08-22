"""S9 API — memory search, outcomes, feedback, governed contract proposals.

POST /decisions/{option_id}/outcome   AC14  predicted vs actual → variance → band → reliability
POST /memory/feedback                 AC15  structured feedback, VISIBLE effect
POST /memory/contracts/{id}/proposals AC23  propose a governed contract change
POST /memory/proposals/{id}/review    AC23  owner reviews → MERGE (versioned) | REJECT
GET  /memory/proposals                AC23  list
GET  /memory/search                   AC25  entitlement-aware retrieval + written explanation
POST /memory/investigations/{id}/close     case closure → LEARNED
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..domains import learning, memory
from ..domains.investigations.service import get_investigation, serialize as serialize_inv
from ..envelope import ok
from ..errors import AppError
from ..models.decisions import DecisionOption, DecisionRecord
from ..models.investigation import Investigation
from ..models.memory import FeedbackEvent, ProposedContractChange
from ..models.org import User
from ..security.deps import require_roles

router = APIRouter(prefix="/decisions", tags=["decisions"])
mem_router = APIRouter(prefix="/memory", tags=["memory"])

_governed_guard = require_roles("KPI_OWNER", "EXECUTIVE", "SUPPLY_CHAIN", "ANALYST", "ADMIN")
_review_guard = require_roles("KPI_OWNER", "ADMIN")  # only the owner merges contract changes


# ---------------------------------------------------------------- outcomes (AC14)
class OutcomeIn(BaseModel):
    actual_impact_rs: float
    note: str


@router.post("/{option_id}/outcome")
def record_outcome(option_id: str, body: OutcomeIn, request: Request,
                   user: User = Depends(_governed_guard), db: Session = Depends(get_db)):
    if user.role == "ANALYST":
        raise AppError("FORBIDDEN", "Analysts record evidence, not business outcomes", 403)
    if len((body.note or "").strip()) < 10:
        raise AppError("BAD_REQUEST", "Outcome note (≥ 10 chars) is required — feeds the learning loop", 400)
    opt = (
        db.query(DecisionOption)
        .filter(DecisionOption.organization_id == user.organization_id, DecisionOption.id == option_id)
        .first()
    )
    if opt is None:
        raise AppError("NOT_FOUND", "Option not found", 404)
    record = learning.service.record_outcome(
        db, user.organization_id, opt, body.actual_impact_rs, body.note, user.id, user.role,
    )
    inv = db.query(Investigation).filter(
        Investigation.organization_id == user.organization_id, Investigation.id == opt.investigation_id
    ).first()
    if inv:
        learning.service.advance_to_monitoring(db, inv)
        if inv.workflow_state == "MONITORING":
            inv.workflow_state = "OUTCOME_RECORDED"
            db.add(inv)
    rel = getattr(record, "_reliability_update", None)
    return ok(request, {
        "option_code": opt.code,
        "predicted_rs": opt.expected_impact_rs,
        "band_rs": [opt.impact_lo_rs, opt.impact_hi_rs],
        "actual_rs": body.actual_impact_rs,
        "variance_rs": record.outcome_variance,
        "within_band": record.within_band,
        "reliability": rel,
        "investigation_state": inv.workflow_state if inv else None,
    })


# ---------------------------------------------------------------- feedback (AC15)
class FeedbackIn(BaseModel):
    investigation_id: str | None = None
    feedback_type: str
    payload: dict


@mem_router.post("/feedback")
def record_feedback(body: FeedbackIn, request: Request,
                    user: User = Depends(_governed_guard), db: Session = Depends(get_db)):
    inv = None
    if body.investigation_id:
        inv = get_investigation(db, user.organization_id, body.investigation_id)
    ev = learning.service.record_feedback(
        db, user.organization_id, inv, body.feedback_type, body.payload, user.id, user.role,
    )
    return ok(request, {"id": ev.id, "feedback_type": ev.feedback_type,
                        "effect": ev.effect, "visible": True})


# ---------------------------------------------------------------- proposals (AC23)
class ProposalIn(BaseModel):
    change_type: str
    payload: dict
    rationale: str


@mem_router.post("/contracts/{contract_id}/proposals")
def propose(contract_id: str, body: ProposalIn, request: Request,
            user: User = Depends(_governed_guard), db: Session = Depends(get_db)):
    row = learning.service.propose_change(
        db, user.organization_id, contract_id, body.change_type, body.payload,
        body.rationale, origin="HUMAN", proposed_by_user_id=user.id, proposed_by_role=user.role,
    )
    return ok(request, _proposal(row))


class ReviewIn(BaseModel):
    decision: str
    note: str


@mem_router.post("/proposals/{proposal_id}/review")
def review(proposal_id: str, body: ReviewIn, request: Request,
           user: User = Depends(_review_guard), db: Session = Depends(get_db)):
    row = learning.service.review_proposal(
        db, user.organization_id, proposal_id, body.decision, body.note, user.id, user.role,
    )
    return ok(request, _proposal(row))


@mem_router.get("/proposals")
def list_proposals(request: Request, contract_id: str | None = None,
                   user: User = Depends(_governed_guard), db: Session = Depends(get_db)):
    rows = learning.service.list_proposals(db, user.organization_id, contract_id)
    return ok(request, [_proposal(r) for r in rows])


def _proposal(r: ProposedContractChange) -> dict:
    return {"id": r.id, "contract_id": r.contract_id, "base_version": r.base_version,
            "change_type": r.change_type, "payload": r.payload, "rationale": r.rationale,
            "origin": r.origin, "proposed_by_role": r.proposed_by_role, "status": r.status,
            "review_note": r.review_note, "merged_to_version": r.merged_to_version,
            "created_at": r.created_at}


# ---------------------------------------------------------------- memory (AC25)
@mem_router.get("/search")
def memory_search(request: Request, q: str | None = None, kpi_code: str | None = None,
                  driver_class: str | None = None, analogue_for: str | None = None,
                  limit: int = 5, user: User = Depends(_governed_guard), db: Session = Depends(get_db)):
    res = memory.service.search(
        db, user.organization_id, user.role, kpi_code=kpi_code,
        driver_class=driver_class, query=q, analogue_for=analogue_for,
        limit=min(limit, 10),
    )
    return ok(request, res)


# ---------------------------------------------------------------- case closure
@mem_router.post("/investigations/{investigation_id}/close")
def close_case(investigation_id: str, request: Request,
               user: User = Depends(_governed_guard), db: Session = Depends(get_db)):
    """APPROVED → MONITORING → OUTCOME_RECORDED → LEARNED (case closure)."""
    inv = get_investigation(db, user.organization_id, investigation_id)
    opt_ids = [o.id for o in db.query(DecisionOption)
               .filter(DecisionOption.investigation_id == inv.id).all()]
    has_quant = (
        db.query(DecisionRecord)
        .filter(DecisionRecord.organization_id == user.organization_id,
                DecisionRecord.option_id.in_(opt_ids),
                DecisionRecord.actual_impact_rs.isnot(None))
        .count()
    ) > 0 if opt_ids else False
    if inv.workflow_state not in ("MONITORING", "OUTCOME_RECORDED"):
        raise AppError("BAD_REQUEST",
                       f"Case closes from MONITORING/OUTCOME_RECORDED (now {inv.workflow_state})", 400)
    if not has_quant:
        raise AppError("BAD_REQUEST", "Record at least one outcome before closing the case", 400)
    inv.workflow_state = "LEARNED"
    db.add(inv)
    from ..services.audit import record as audit
    audit(db, organization_id=user.organization_id, actor_user_id=user.id, actor_role=user.role,
          action="investigation.close", object_type="investigation", object_id=inv.id,
          details={"state": "LEARNED"})
    return ok(request, serialize_inv(db, inv, viewer_role=user.role))
