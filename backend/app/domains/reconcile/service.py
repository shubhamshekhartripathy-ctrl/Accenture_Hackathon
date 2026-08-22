"""Reconcile service: gather readings → run engine → persist run/conflicts → route."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from ...db import utcnow
from ...errors import AppError
from ...models.contract import KpiContract
from ...models.kpi import Kpi
from ...models.observation import KpiObservation
from ...models.reconciliation import ReconciliationConflict, ReconciliationRun
from ...services.audit import record as audit
from ...services.telemetry import record_stage
from . import engine
from .engine import SourceReading


def demo_clock(db: Session, organization_id: str, kpi_id: str) -> object:
    """The newest observation timestamp across the KPI's sources — deterministic freshness base."""
    latest = (
        db.query(KpiObservation)
        .filter(KpiObservation.organization_id == organization_id, KpiObservation.kpi_id == kpi_id)
        .order_by(KpiObservation.occurred_at.desc())
        .first()
    )
    if latest is None:
        return utcnow()
    return latest.occurred_at


def _as_aware(dt: object) -> object:
    from datetime import timezone

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def gather_readings(db: Session, contract: KpiContract, period_key: str) -> list[SourceReading]:
    """Build normalized per-source readings for the KPI at a period (NORMALIZE step)."""
    clock = _as_aware(demo_clock(db, contract.organization_id, contract.kpi_id))
    readings: list[SourceReading] = []
    for link in contract.sources:
        src = link.source_system
        if src is None:
            continue
        obs = (
            db.query(KpiObservation)
            .filter(
                KpiObservation.organization_id == contract.organization_id,
                KpiObservation.kpi_id == contract.kpi_id,
                KpiObservation.source_id == src.id,
                KpiObservation.period_key == period_key,
            )
            .first()
        )
        # Freshness is a property of the FEED: age of the source's newest observation
        # for this KPI (a panel can be late for the current period yet still publish).
        newest = (
            db.query(KpiObservation)
            .filter(
                KpiObservation.organization_id == contract.organization_id,
                KpiObservation.kpi_id == contract.kpi_id,
                KpiObservation.source_id == src.id,
            )
            .order_by(KpiObservation.occurred_at.desc())
            .first()
        )
        if newest is not None:
            newest = _as_aware(newest.occurred_at)
            age_days = int((clock - newest).total_seconds() // 86400)
        else:
            age_days = 999
        readings.append(
            SourceReading(
                source_code=src.code,
                source_id=src.id,
                value=obs.value if obs else None,
                period_key=period_key,
                age_days=age_days,
                expected_cadence=link.expected_cadence or src.cadence,
                tolerance_days=_tolerance_days(link.expected_cadence or src.cadence),
                tolerance_pct=link.tolerance_pct or 0.0,
                grain=obs.grain if obs else src.grain,
                expected_grain=link.expected_grain or src.grain,
                is_authoritative=link.is_authoritative,
                calendar_key=obs.calendar_key if obs else "",
            )
        )
    return readings


def _tolerance_days(cadence: str) -> int:
    """Contract data-quality tolerance: +2d for daily/weekly feeds, +3d monthly close."""
    return 3 if cadence == "monthly" else 2


def run_reconciliation(
    db: Session,
    contract: KpiContract,
    period_key: str,
    actor_user_id: str | None = None,
    run_id: str | None = None,
    investigation_id: str | None = None,
) -> ReconciliationRun:
    import time as _time

    t0 = _time.perf_counter()
    readings = gather_readings(db, contract, period_key)
    kpi = db.query(Kpi).filter(Kpi.id == contract.kpi_id).first()
    result = engine.run_engine(readings, period_key, kpi.unit if kpi else "")

    conflicts_by_route_owner = _route_targets(db, contract, result.conflicts)
    run = ReconciliationRun(
        organization_id=contract.organization_id,
        contract_id=contract.id,
        period_key=period_key,
        verdict=result.verdict,
        reliability_score=result.reliability_score,
        confidence_cap=result.confidence_cap,
        working_value=result.working_value,
        working_source_id=result.working_source_id,
        working_justification=result.working_justification,
        freshness_profile=result.freshness_profile,
        penalties=result.penalties,
        investigation_id=investigation_id,
        run_ts=utcnow(),
    )
    db.add(run)
    db.flush()
    for c in result.conflicts:
        routed = conflicts_by_route_owner.get((c["route"], c["source_a_id"]))
        db.add(ReconciliationConflict(
            organization_id=contract.organization_id,
            run_id=run.id,
            conflict_type=c["conflict_type"],
            severity=c["severity"],
            source_a_id=c["source_a_id"],
            source_b_id=c["source_b_id"],
            value_a=c["value_a"],
            value_b=c["value_b"],
            unit=kpi.unit if kpi else "",
            confidence_impact=c["confidence_impact"],
            penalty=c["penalty"],
            explanation=c["explanation"],
            routed_to_user_id=routed,
            routed_role=c["routed_role"],
            resolution_state="OPEN",
        ))
    db.flush()

    # System transition: an active definition conflict flips the contract CONFLICTED (arch E).
    definition_open = any(
        c.conflict_type == "definition" and c.resolution_state == "OPEN"
        for c in run.conflicts
    )
    if definition_open and contract.status == "ACTIVE":
        from ..contracts.service import transition_status

        transition_status(
            db, contract, "CONFLICTED", actor_user_id=actor_user_id, system=True,
            reason=f"reconciliation detected a definition conflict at {period_key}",
        )

    record_stage(
        db, contract.organization_id, run_id or f"reconcile-{run.id[:8]}", "reconcile", "rules",
        latency_ms=int((_time.perf_counter() - t0) * 1000),
        confidence_impact=result.confidence_cap - 1.0,
        source_count=len(readings),
        ok=True,
    )
    if actor_user_id:
        audit(db, contract.organization_id, "reconcile.run", "kpi_contract", contract.id,
              actor_user_id, details={"verdict": result.verdict, "reliability": result.reliability_score,
                                      "period": period_key, "investigation_id": investigation_id})
    return run


def _route_targets(db: Session, contract: KpiContract, conflicts: list[dict]) -> dict[tuple[str, str], str]:
    """definition → KPI owner (contract owner); refresh/coverage → data owner (admin fallback)."""
    targets: dict[tuple[str, str], str] = {}
    for c in conflicts:
        if c["route"] == "kpi_owner" and contract.owner_user_id:
            targets[(c["route"], c["source_a_id"])] = contract.owner_user_id
    return targets


def latest_run(db: Session, organization_id: str, contract_id: str) -> ReconciliationRun | None:
    return (
        db.query(ReconciliationRun)
        .filter(
            ReconciliationRun.organization_id == organization_id,
            ReconciliationRun.contract_id == contract_id,
        )
        .order_by(ReconciliationRun.run_ts.desc())
        .first()
    )


def resolve_conflict(
    db: Session,
    organization_id: str,
    conflict: ReconciliationConflict,
    note: str,
    actor_user_id: str,
    actor_role: str,
) -> ReconciliationConflict:
    """Routed-owner resolution. Resolving the last OPEN definition conflict can restore ACTIVE."""
    if conflict.resolution_state != "OPEN":
        raise AppError("CONFLICT", f"Conflict already {conflict.resolution_state}", 409)
    conflict.resolution_state = "RESOLVED"
    conflict.resolution_note = note
    conflict.resolved_at = utcnow()
    db.add(conflict)
    db.flush()
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == conflict.run_id).first()
    still_open = any(
        c.conflict_type == "definition" and c.resolution_state == "OPEN"
        for c in (run.conflicts if run else [])
    )
    restored = False
    if not still_open and run is not None:
        contract = db.query(KpiContract).filter(KpiContract.id == run.contract_id).first()
        if contract is not None and contract.status == "CONFLICTED":
            from ..contracts.service import transition_status

            transition_status(db, contract, "ACTIVE", actor_user_id, actor_role,
                              reason="definition conflict resolved by routed owner")
            restored = True
    audit(db, organization_id, "reconcile.conflict_resolved", "reconciliation_conflict", conflict.id,
          actor_user_id, actor_role, details={"note": note, "contract_restored": restored})
    return conflict


def serialize_run(run: ReconciliationRun, db: Session) -> dict:
    from ...models.source import SourceSystem

    def src(code_id: str) -> dict | None:
        s = db.query(SourceSystem).filter(SourceSystem.id == code_id).first()
        return {"id": s.id, "code": s.code, "name": s.name} if s else None

    def user(uid: str | None) -> dict | None:
        if not uid:
            return None
        from ...models.org import User

        u = db.query(User).filter(User.id == uid).first()
        return {"id": u.id, "name": u.full_name, "role": u.role} if u else None

    return {
        "id": run.id,
        "contract_id": run.contract_id,
        "period_key": run.period_key,
        "verdict": run.verdict,
        "reliability_score": run.reliability_score,
        "confidence_cap": run.confidence_cap,
        "working_value": run.working_value,
        "working_source": src(run.working_source_id),
        "working_justification": run.working_justification,
        "penalties": run.penalties,
        "freshness_profile": run.freshness_profile,
        "run_ts": run.run_ts.isoformat() if run.run_ts else None,
        "conflicts": [
            {
                "id": c.id,
                "conflict_type": c.conflict_type,
                "severity": c.severity,
                "source_a": src(c.source_a_id),
                "source_b": src(c.source_b_id),
                "value_a": c.value_a,
                "value_b": c.value_b,
                "unit": c.unit,
                "confidence_impact": c.confidence_impact,
                "penalty": c.penalty,
                "explanation": c.explanation,
                "routed_to": user(c.routed_to_user_id),
                "routed_role": c.routed_role,
                "resolution_state": c.resolution_state,
                "resolution_note": c.resolution_note,
                "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
            }
            for c in run.conflicts
        ],
    }
