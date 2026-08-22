"""Detect + triage service: run engines, persist artifacts, record telemetry."""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from ...db import utcnow
from ...errors import AppError
from ...models.contract import KpiContract
from ...models.detection import DetectionResult, MaterialityScore
from ...models.observation import KpiObservation
from ...models.reconciliation import ReconciliationRun
from ...services.telemetry import record_stage
from ..reconcile import service as reconcile_service
from . import engine as detect_engine
from ..triage import engine as triage_engine


def _working_series(db: Session, contract: KpiContract) -> list[KpiObservation]:
    """Authoritative (reconciled working) source series, ordered by period."""
    org = contract.organization_id
    latest_recon = reconcile_service.latest_run(db, org, contract.id)
    working_source_id = latest_recon.working_source_id if latest_recon else next(
        (s.source_system_id for s in contract.sources if s.is_authoritative), None
    )
    if working_source_id is None:
        raise AppError("NO_SOURCES", "Contract has no authoritative source", 409)
    rows = (
        db.query(KpiObservation)
        .filter(
            KpiObservation.organization_id == org,
            KpiObservation.kpi_id == contract.kpi_id,
            KpiObservation.source_id == working_source_id,
        )
        .order_by(KpiObservation.occurred_at)  # chronological; period_key is a label, not a sort key
        .all()
    )
    if not rows:
        raise AppError("NO_OBSERVATIONS", "No observations for the working source", 409)
    return rows


def run_detect(
    db: Session,
    contract: KpiContract,
    run_id: str | None = None,
) -> DetectionResult:
    """DETECT stage: baseline/robust-z/CI on the working series. Pure stats; telemetry row."""
    t0 = time.perf_counter()
    rows = _working_series(db, contract)
    period_key = rows[-1].period_key
    history = [r.value for r in rows[:-1]]
    current = rows[-1].value
    thresholds = contract.threshold
    min_history = thresholds.min_history if thresholds else 13
    det = detect_engine.detect(history, current, min_history)

    detection = DetectionResult(
        organization_id=contract.organization_id,
        kpi_id=contract.kpi_id,
        contract_id=contract.id,
        period_key=period_key,
        source_value=current,
        baseline=det.baseline,
        expected_value=det.expected_value,
        ci_lo=det.ci_lo,
        ci_hi=det.ci_hi,
        deviation=det.deviation,
        deviation_pct=det.deviation_pct,
        robust_z=det.robust_z,
        anomaly_score=det.anomaly_score,
        statistical_significance=det.significance,
        history_n=det.history_n,
        cold_start_flag=det.cold_start,
        method=det.method,
        model_version=det.model_version,
        detected_at=utcnow(),
        run_id=run_id,
    )
    db.add(detection)
    db.flush()
    record_stage(
        db, contract.organization_id, run_id or f"detect-{detection.id[:8]}", "detect", "stats",
        latency_ms=int((time.perf_counter() - t0) * 1000), source_count=1, ok=True,
    )
    return detection


def run_triage(
    db: Session,
    contract: KpiContract,
    detection: DetectionResult,
    run_id: str | None = None,
) -> MaterialityScore:
    """TRIAGE stage: business materiality from contract weights; arithmetic stored in full."""
    t0 = time.perf_counter()
    th = contract.threshold
    threshold_comparison: dict = {}
    if th is None:
        # No thresholds ⇒ statistical-only materiality, low confidence, never CRITICAL (spec §7.3)
        tri = triage_engine.triage(
            significance=detection.statistical_significance,
            deviation_pct=detection.deviation_pct,
            exposure_rs_per_point=0.0, margin_weight=0.0, strategic_weight=0.0,
            cold_start=detection.cold_start_flag,
        )
        tri.arithmetic["statistical_only"] = True
    else:
        threshold_comparison = {
            "warning_deviation_pct": th.warning_deviation_pct,
            "critical_deviation_pct": th.critical_deviation_pct,
            "crosses_warning": (
                th.warning_deviation_pct is not None
                and detection.deviation_pct <= th.warning_deviation_pct
            ),
            "crosses_critical": (
                th.critical_deviation_pct is not None
                and detection.deviation_pct <= th.critical_deviation_pct
            ),
        }
        tri = triage_engine.triage(
            significance=detection.statistical_significance,
            deviation_pct=detection.deviation_pct,
            exposure_rs_per_point=th.exposure_rs_per_point,
            margin_weight=th.margin_weight,
            strategic_weight=th.strategic_weight,
            floor_band=th.floor_band,
            cold_start=detection.cold_start_flag,
            threshold_comparison=threshold_comparison,
        )

    score = MaterialityScore(
        organization_id=contract.organization_id,
        detection_id=detection.id,
        kpi_id=contract.kpi_id,
        contract_id=contract.id,
        period_key=detection.period_key,
        significance=tri.significance,
        exposure_rs=tri.exposure_rs,
        margin_weight=th.margin_weight if th else 0.0,
        strategic_weight=th.strategic_weight if th else 0.0,
        score=tri.score,
        band=tri.band,
        monitor_only=tri.monitor_only,
        arithmetic=tri.arithmetic,
        threshold_comparison=threshold_comparison,
        run_id=run_id,
    )
    db.add(score)
    db.flush()
    record_stage(
        db, contract.organization_id, run_id or f"triage-{score.id[:8]}", "triage", "rules",
        latency_ms=int((time.perf_counter() - t0) * 1000), source_count=0, ok=True,
    )
    return score


def run_detect_and_triage(
    db: Session,
    contract: KpiContract,
    run_id: str | None = None,
) -> tuple[DetectionResult, MaterialityScore]:
    detection = run_detect(db, contract, run_id=run_id)
    score = run_triage(db, contract, detection, run_id=run_id)
    return detection, score


def latest_detection(db: Session, organization_id: str, kpi_id: str) -> DetectionResult | None:
    return (
        db.query(DetectionResult)
        .filter(
            DetectionResult.organization_id == organization_id,
            DetectionResult.kpi_id == kpi_id,
        )
        .order_by(DetectionResult.detected_at.desc())
        .first()
    )


def latest_materiality(db: Session, organization_id: str, kpi_id: str) -> MaterialityScore | None:
    return (
        db.query(MaterialityScore)
        .filter(
            MaterialityScore.organization_id == organization_id,
            MaterialityScore.kpi_id == kpi_id,
        )
        .order_by(MaterialityScore.created_at.desc())
        .first()
    )
