"""Learning loop (AC14–16, AC23) — outcomes, feedback, governed proposals.

Hard rules: the learning loop NEVER mutates an ACTIVE contract — pattern
priors live in PatternReliability (empirical, S4), and any contract-level
change lands as a ProposedContractChange for human review → merge. Feedback
effects are VISIBLE (stored on the event + returned). Outcome math is
deterministic: variance = actual − predicted; within-band vs the option's
stored [lo, hi]; reliability shrunk toward the prior when n is small:
    new_prior = (hits + 10 × 0.5) / (n_observations + 10)
Locked demo: predicted +₹4.1M, actual +₹3.9M → variance −₹0.2M → within band
→ supply_disruption prior shrinks (hits 14→15, n 22→23 ⇒ 0.6522).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...db import utcnow
from ...errors import AppError
from ...models.decisions import DecisionOption, DecisionRecord
from ...models.evidence import PatternReliability
from ...models.investigation import Investigation
from ...models.memory import FeedbackEvent, ProposedContractChange
from ...services import telemetry
from ...services.audit import record as audit

SHRINKAGE_M = 10
SHRINKAGE_PRIOR = 0.5


def record_outcome(db: Session, organization_id: str, option: DecisionOption,
                   actual_impact_rs: float, note: str, actor_user_id: str,
                   actor_role: str) -> DecisionRecord:
    """AC14 — predicted vs actual → variance → within-band → reliability update."""
    record = (
        db.query(DecisionRecord)
        .filter(DecisionRecord.organization_id == organization_id,
                DecisionRecord.option_id == option.id,
                DecisionRecord.status.in_(("APPROVED", "OVERRIDDEN")))
        .first()
    )
    if record is None:
        raise AppError("NOT_FOUND", "Only an approved/overridden decision can record an outcome", 404)

    predicted = float(option.expected_impact_rs)
    lo, hi = float(option.impact_lo_rs), float(option.impact_hi_rs)
    variance = actual_impact_rs - predicted
    within = lo <= actual_impact_rs <= hi
    if record.actual_impact_rs is not None:
        raise AppError("OUTCOME_EXISTS", "Outcome already recorded for this decision", 409)

    record.actual_impact_rs = actual_impact_rs
    record.outcome_variance = round(variance, 2)
    record.within_band = within
    record.outcome_note = note
    db.add(record)

    # Reliability shrinkage on the acted driver's pattern class (empirical table,
    # NOT the contract): hit = within band.
    pattern_class = _pattern_class_for(db, organization_id, option)
    reliability_update = None
    if pattern_class:
        rel = db.query(PatternReliability).filter(
            PatternReliability.organization_id == organization_id,
            PatternReliability.pattern_class == pattern_class,
        ).first()
        if rel is not None:
            rel.n_observations += 1
            if within:
                rel.hits += 1
            rel.prior = round((rel.hits + SHRINKAGE_M * SHRINKAGE_PRIOR) / (rel.n_observations + SHRINKAGE_M), 4)
            rel.last_feedback_at = utcnow()
            db.add(rel)
            reliability_update = {
                "pattern_class": pattern_class, "n_observations": rel.n_observations,
                "hits": rel.hits, "new_prior": rel.prior,
                "formula": f"(hits + {SHRINKAGE_M}×{SHRINKAGE_PRIOR}) / (n + {SHRINKAGE_M})",
                "table": "pattern_reliability (empirical) — the ACTIVE contract is untouched",
            }

    audit(db, organization_id=organization_id, actor_user_id=actor_user_id, actor_role=actor_role,
          action="decision.outcome", object_type="decision_option", object_id=option.id,
          details={"predicted": predicted, "actual": actual_impact_rs, "within_band": within})
    telemetry.record_stage(db, organization_id, record.investigation_id, "outcome", "stats", ok=True)
    db.flush()
    record._reliability_update = reliability_update  # surfaced to the API response
    return record


# Legal walk from the decision branch to MONITORING once a record is approved.
_MONITORING_CHAIN = ["DECISION_RECORD_CREATED", "PORTFOLIO_UPDATED", "HUMAN_APPROVAL",
                     "APPROVED", "MONITORING"]


def advance_to_monitoring(db: Session, inv: Investigation) -> Investigation:
    """Walk the investigation forward along the legal transition chain once a
    decision record exists (S7 leaves the header at RIGHTS_CHECKED; S9 closes
    the loop through APPROVED → MONITORING deterministically)."""
    from ...models.investigation import WORKFLOW_TRANSITIONS
    if inv.workflow_state in ("ABSTAINED", "MONITORING", "OUTCOME_RECORDED", "LEARNED"):
        return inv
    # walk to APPROVED along the legal chain, then into MONITORING
    if inv.workflow_state in _MONITORING_CHAIN:
        start = _MONITORING_CHAIN.index(inv.workflow_state) + 1
    else:
        start = 0
    for nxt in _MONITORING_CHAIN[start:]:
        if (inv.workflow_state, nxt) not in WORKFLOW_TRANSITIONS:
            continue
        inv.workflow_state = nxt
        db.add(inv)
    db.flush()
    return inv


def _pattern_class_for(db: Session, organization_id: str, option: DecisionOption) -> str | None:
    inv = db.query(Investigation).filter(
        Investigation.organization_id == organization_id, Investigation.id == option.investigation_id).first()
    if inv is None:
        return None
    from ...models.evidence import InvestigationHypothesis
    hyps = (
        db.query(InvestigationHypothesis)
        .filter(InvestigationHypothesis.investigation_id == inv.id)
        .order_by(InvestigationHypothesis.rank.asc())
        .all()
    )
    for h in hyps:
        if h.driver_code == option.driver or h.code == option.driver:
            return h.pattern_class
    # driver codes map to pattern classes via the contract's drivers
    from ...models.contract import KpiContractDriver
    d = (
        db.query(KpiContractDriver)
        .filter(KpiContractDriver.contract_id == inv.contract_id,
                KpiContractDriver.driver_code == option.driver)
        .first()
    )
    return d.hypothesis_class if d else None


FEEDBACK_TYPES = ("hypothesis_verdict", "driver_correction", "evidence_rating",
                  "recommendation_rating", "override_reason", "action_outcome")


def record_feedback(db: Session, organization_id: str, inv: Investigation | None,
                    feedback_type: str, payload: dict, actor_user_id: str,
                    actor_role: str) -> FeedbackEvent:
    """AC15 — structured feedback with a VISIBLE effect. Never silent, never RLHF."""
    if feedback_type not in FEEDBACK_TYPES:
        raise AppError("BAD_REQUEST", f"feedback_type must be one of {FEEDBACK_TYPES}", 400)
    effect: dict = {}

    if feedback_type == "hypothesis_verdict":
        verdict = payload.get("verdict")  # CONFIRMED | REFUTED
        pattern_class = payload.get("pattern_class")
        code = payload.get("hypothesis_code")
        if verdict not in ("CONFIRMED", "REFUTED") or not (pattern_class or code):
            raise AppError("BAD_REQUEST", "hypothesis_verdict needs verdict + (pattern_class | hypothesis_code)", 400)
        if not pattern_class and inv is not None:
            for h in inv.hypotheses:
                if h.code == code:
                    pattern_class = h.pattern_class
        rel = db.query(PatternReliability).filter(
            PatternReliability.organization_id == organization_id,
            PatternReliability.pattern_class == pattern_class,
        ).first()
        if rel is not None:
            rel.n_observations += 1
            if verdict == "CONFIRMED":
                rel.hits += 1
            rel.prior = round((rel.hits + SHRINKAGE_M * SHRINKAGE_PRIOR) / (rel.n_observations + SHRINKAGE_M), 4)
            rel.last_feedback_at = utcnow()
            db.add(rel)
            effect["pattern_prior_update"] = {
                "pattern_class": pattern_class, "n_observations": rel.n_observations,
                "hits": rel.hits, "new_prior": rel.prior,
            }
        # contract-level change goes through governance — proposal, never silent
        if inv is not None and payload.get("propose_prior_update", True):
            proposal = propose_change(
                db, organization_id, inv.contract_id, "driver_prior_update",
                {"driver_code": code or pattern_class, "pattern_class": pattern_class,
                 "new_prior_weight": rel.prior if rel else None},
                rationale=(f"hypothesis_verdict {verdict} on {code or pattern_class} "
                           f"(feedback, learning loop) — requires human review before merge"),
                origin="LEARNING_LOOP", proposed_by_user_id=actor_user_id, proposed_by_role=actor_role,
            )
            effect["governed_proposal"] = {"id": proposal.id, "status": proposal.status,
                                           "note": "learning never mutates ACTIVE contracts"}

    elif feedback_type == "driver_correction":
        if inv is None or not payload.get("driver_code") or not payload.get("corrected_pct"):
            raise AppError("BAD_REQUEST", "driver_correction needs investigation + driver_code + corrected_pct", 400)
        effect["decomposition_weight_correction"] = {
            "driver_code": payload["driver_code"], "observed_pct": payload.get("observed_pct"),
            "corrected_pct": payload["corrected_pct"],
        }
        proposal = propose_change(
            db, organization_id, inv.contract_id, "driver_correction",
            {"driver_code": payload["driver_code"], "corrected_pct": payload["corrected_pct"]},
            rationale=f"driver_correction from feedback: {payload.get('note', '')}",
            origin="LEARNING_LOOP", proposed_by_user_id=actor_user_id, proposed_by_role=actor_role,
        )
        effect["governed_proposal"] = {"id": proposal.id, "status": proposal.status}

    elif feedback_type == "evidence_rating":
        effect["retrieval_feature_weight"] = {
            "doc_key": payload.get("doc_key"), "rating": payload.get("rating"),
            "note": "retrieval ranking weight recorded — visible, no silent model change",
        }

    elif feedback_type == "recommendation_rating":
        effect["template_ordering"] = {
            "rating": payload.get("rating"),
            "note": "recommendation template ordering preference recorded",
        }

    elif feedback_type == "override_reason":
        effect["learning_input"] = {"note": "override reasons feed future pattern priors via governance only"}

    elif feedback_type == "action_outcome":
        effect["recorded"] = {"note": "see decision.outcome for the quantitative path"}

    ev = FeedbackEvent(
        organization_id=organization_id,
        investigation_id=inv.id if inv is not None else None,
        actor_user_id=actor_user_id, actor_role=actor_role,
        feedback_type=feedback_type, payload=payload, effect=effect,
    )
    db.add(ev)
    audit(db, organization_id=organization_id, actor_user_id=actor_user_id, actor_role=actor_role,
          action="feedback.record", object_type="feedback", object_id=None,
          details={"type": feedback_type, "effect_keys": sorted(effect.keys())})
    db.flush()
    return ev


def propose_change(db: Session, organization_id: str, contract_id: str, change_type: str,
                   payload: dict, rationale: str, origin: str = "HUMAN",
                   proposed_by_user_id: str | None = None, proposed_by_role: str | None = None,
                   base_version: int | None = None) -> ProposedContractChange:
    from ...models.contract import KpiContract
    contract = (
        db.query(KpiContract)
        .filter(KpiContract.organization_id == organization_id, KpiContract.id == contract_id)
        .first()
    )
    if contract is None:
        raise AppError("NOT_FOUND", "Contract not found", 404)
    row = ProposedContractChange(
        organization_id=organization_id, contract_id=contract_id,
        base_version=base_version or contract.version,
        change_type=change_type, payload=payload, rationale=rationale,
        origin=origin, proposed_by_user_id=proposed_by_user_id,
        proposed_by_role=proposed_by_role, status="IN_REVIEW",
    )
    db.add(row)
    db.flush()
    return row


def review_proposal(db: Session, organization_id: str, proposal_id: str,
                    decision: str, note: str, actor_user_id: str, actor_role: str) -> ProposedContractChange:
    """AC23 — proposal → review → merge. Only KPI_OWNER/ADMIN review and merge."""
    row = db.query(ProposedContractChange).filter(
        ProposedContractChange.organization_id == organization_id,
        ProposedContractChange.id == proposal_id).first()
    if row is None:
        raise AppError("NOT_FOUND", "Proposal not found", 404)
    if row.status != "IN_REVIEW":
        raise AppError("PROPOSAL_CLOSED", f"Proposal already {row.status}", 409)
    if decision not in ("MERGE", "REJECT"):
        raise AppError("BAD_REQUEST", "decision must be MERGE | REJECT", 400)
    if actor_role not in ("KPI_OWNER", "ADMIN"):
        raise AppError("FORBIDDEN", "Only the KPI owner (or admin) reviews and merges contract proposals", 403)
    if len((note or "").strip()) < 10:
        raise AppError("BAD_REQUEST", "A review note (≥ 10 chars) is required — governed change", 400)

    if decision == "REJECT":
        row.status = "REJECTED"
        row.review_note = note
        row.reviewed_by_user_id = actor_user_id
        db.add(row)
        return row

    # MERGE — the ONLY path that changes an ACTIVE contract (versioned, snapshotted)
    from ...models.contract import KpiContract
    contract = db.query(KpiContract).filter(
        KpiContract.organization_id == organization_id, KpiContract.id == row.contract_id).first()
    if contract.version != row.base_version:
        raise AppError("STALE_VERSION",
                       f"Proposal was made against v{row.base_version}; contract is now v{contract.version} — "
                       "re-propose against the current version (optimistic concurrency)", 409)
    _apply_payload(db, contract, row.payload)
    from ..contracts.service import _bump_version
    _bump_version(db, contract, actor_user_id, f"merge proposal {row.id}: {row.rationale[:80]}")
    row.status = "MERGED"
    row.review_note = note
    row.reviewed_by_user_id = actor_user_id
    row.merged_to_version = contract.version
    db.add(row)
    audit(db, organization_id=organization_id, actor_user_id=actor_user_id, actor_role=actor_role,
          action="contract.proposal_merge", object_type="contract", object_id=contract.id,
          details={"proposal_id": row.id, "new_version": contract.version})
    db.flush()
    return row


def _apply_payload(db: Session, contract, payload: dict) -> None:
    """Apply the governed change to the contract satellites (pre-version-bump)."""
    from ...models.contract import KpiContractDriver
    if "driver_code" in payload and payload.get("driver_code"):
        d = (
            db.query(KpiContractDriver)
            .filter(KpiContractDriver.contract_id == contract.id,
                    KpiContractDriver.driver_code == payload["driver_code"])
            .first()
        )
        if d is not None and payload.get("new_prior_weight") is not None:
            d.prior_weight = float(payload["new_prior_weight"])
            db.add(d)
        if d is not None and payload.get("corrected_pct") is not None:
            # the contract's driver weight is the governed knob (0..1); the
            # analyst's percentage correction is re-expressed as a weight
            d.prior_weight = round(min(1.0, max(0.0, float(payload["corrected_pct"]) / 100.0)), 4)
            db.add(d)


def list_proposals(db: Session, organization_id: str, contract_id: str | None = None) -> list[ProposedContractChange]:
    q = db.query(ProposedContractChange).filter(ProposedContractChange.organization_id == organization_id)
    if contract_id:
        q = q.filter(ProposedContractChange.contract_id == contract_id)
    return q.order_by(ProposedContractChange.created_at.desc()).all()
