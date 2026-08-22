"""Materiality queue — triage aggregation over STORED artifacts only.

GET /queue never fabricates: it reads persisted DetectionResult + MaterialityScore
rows. POST /queue/refresh runs the real detect+triage stages per KPI (telemetry
rows + audit) — the refresh IS the computation.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...db import new_id, utcnow
from ...errors import AppError
from ...models.contract import KpiContract
from ...models.detection import DetectionResult, MaterialityScore
from ...models.investigation import Investigation
from ...models.kpi import Kpi
from ...services.audit import record as audit
from ...services.telemetry import record_stage
from ..detect import service as detect_service

BAND_RANK = {"CRITICAL": 4, "ELEVATED": 3, "WATCH": 2, "NOISE": 1, "COLD START": 0}


def refresh_queue(db: Session, organization_id: str, actor_user_id: str, actor_role: str) -> dict:
    """Run detect+triage for every KPI with a governed contract + observations."""
    contracts = (
        db.query(KpiContract)
        .filter(
            KpiContract.organization_id == organization_id,
            KpiContract.status.in_(("ACTIVE", "CONFLICTED")),
        )
        .all()
    )
    run_id = f"queue-{new_id()[:10]}"
    refreshed, skipped = [], []
    for contract in contracts:
        try:
            detection, score = detect_service.run_detect_and_triage(db, contract, run_id=run_id)
            refreshed.append({"kpi_id": contract.kpi_id, "band": score.band, "score": score.score})
        except AppError as exc:
            skipped.append({"kpi_id": contract.kpi_id, "reason": exc.code, "message": exc.message})
    record_stage(db, organization_id, run_id, "queue_refresh", "rules", source_count=len(refreshed), ok=True)
    audit(db, organization_id, "queue.refresh", "queue", run_id, actor_user_id, actor_role,
          details={"refreshed": len(refreshed), "skipped": len(skipped)})
    return {"run_id": run_id, "refreshed": refreshed, "skipped": skipped, "as_of": utcnow().isoformat()}


def build_queue(db: Session, organization_id: str) -> list[dict]:
    """Queue from stored artifacts; newest detection+materiality per KPI."""
    kpis = db.query(Kpi).filter(Kpi.organization_id == organization_id).all()
    entries: list[dict] = []
    for kpi in kpis:
        detection = detect_service.latest_detection(db, organization_id, kpi.id)
        if detection is None:
            continue
        materiality = detect_service.latest_materiality(db, organization_id, kpi.id)
        contract = (
            db.query(KpiContract)
            .filter(KpiContract.organization_id == organization_id, KpiContract.kpi_id == kpi.id)
            .order_by(KpiContract.version.desc())
            .first()
        )
        investigation = (
            db.query(Investigation)
            .filter(
                Investigation.organization_id == organization_id,
                Investigation.kpi_id == kpi.id,
                Investigation.workflow_state.notin_(("FAILED", "LEARNED", "ABSTAINED")),
            )
            .order_by(Investigation.created_at.desc())
            .first()
        )
        band = (materiality.band if materiality else "NOISE")
        entries.append({
            "kpi_id": kpi.id,
            "kpi_code": kpi.code,
            "kpi_name": kpi.name,
            "region": kpi.region,
            "unit": kpi.unit,
            "band": band,
            "score": materiality.score if materiality else None,
            "deviation_pct": detection.deviation_pct,
            "robust_z": detection.robust_z,
            "current_value": detection.source_value,
            "baseline": detection.baseline,
            "ci": [detection.ci_lo, detection.ci_hi],
            "exposure_rs": materiality.exposure_rs if materiality else None,
            "cold_start": detection.cold_start_flag,
            "monitor_only": materiality.monitor_only if materiality else False,
            "arithmetic": materiality.arithmetic if materiality else None,
            "threshold_comparison": materiality.threshold_comparison if materiality else {},
            "detection_method": detection.method,
            "model_version": detection.model_version,
            "detected_at": detection.detected_at.isoformat() if detection.detected_at else None,
            "contract_status": contract.status if contract else None,
            "contract_id": contract.id if contract else None,
            "investigation_id": investigation.id if investigation else None,
            "workflow_state": investigation.workflow_state if investigation else None,
            "reliability": investigation.reliability_snapshot if investigation else None,
        })
    # Material first; cold-start pinned last (monitor-only, not an attention demand).
    entries.sort(key=lambda e: (-BAND_RANK.get(e["band"], 0), -(e["score"] or 0)))
    return entries
