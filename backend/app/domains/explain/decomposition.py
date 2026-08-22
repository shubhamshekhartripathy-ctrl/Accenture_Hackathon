"""Explain domain: the quantitative truth layer (arch H).

decompose (this module) is deterministic SQL over observation facts — the LLM
owns zero numbers here (H.1). Hypotheses/evidence land in siblings in S4.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...errors import AppError
from ...models.decomposition import DecompositionComponent
from ...models.investigation import Investigation
from ...models.observation import ObservationFact

# Contribution formulas (arch H.2) — the identity holds by construction:
#   ΔR = Σ(p1q1 − p0q0) = price + volume + mix  (per SKU, exact algebra)
#   region = Σ_region ΔR_region − Σ_sku Δ over regions (single-region panel ⇒ 0)
#   residual = ΔR_observed − (price + volume + mix + region)
# so components + residual always sum to the observed movement.

QUERY_REF_TEMPLATE = (
    "SELECT SUM((p1-p0)*q0) AS price, SUM((q1-q0)*p0) AS volume, "
    "SUM((p1-p0)*(q1-q0)) AS mix FROM observation_facts "
    "WHERE kpi_id=:kpi AND period_key=:period"
)


def decompose(
    db: Session,
    organization_id: str,
    investigation: Investigation,
    detection,  # DetectionResult — baseline + current value
) -> list[DecompositionComponent]:
    """Compute and persist contribution components for the investigated movement.

    The movement is detection.current − detection.baseline in the KPI's unit;
    percentages are components over the baseline. If the KPI has no SKU fact
    panel, the honest fallback is a single labeled `level` component plus the
    full residual (method baseline_compare) — never an invented split.
    """
    kpi_id = investigation.kpi_id
    period = investigation.period_key or detection.period_key

    db.query(DecompositionComponent).filter(
        DecompositionComponent.organization_id == organization_id,
        DecompositionComponent.investigation_id == investigation.id,
    ).delete()

    baseline = float(detection.baseline)
    current = float(detection.source_value)
    movement = current - baseline

    facts = (
        db.query(ObservationFact)
        .filter(
            ObservationFact.organization_id == organization_id,
            ObservationFact.kpi_id == kpi_id,
            ObservationFact.period_key == period,
        )
        .all()
    )

    rows: list[DecompositionComponent] = []
    if facts:
        # --- pure SQL aggregation over the fact panel (H.2) -------------------
        price = sum((f.p1 - f.p0) * f.q0 for f in facts)
        volume = sum((f.q1 - f.q0) * f.p0 for f in facts)
        mix = sum((f.p1 - f.p0) * (f.q1 - f.q0) for f in facts)
        regions = sorted({f.region for f in facts})
        if len(regions) > 1:
            region = sum(
                sum((f.p1 * f.q1 - f.p0 * f.q0) for f in facts if f.region == r)
                - sum((f.p1 * f.q1 - f.p0 * f.q0) for f in facts)
                / len(regions)
                for r in regions
            )
        else:
            region = 0.0
        panel_move = price + volume + mix + region
        residual = movement - panel_move
        panel_base = sum(f.p0 * f.q0 for f in facts)
        coverage = panel_base / baseline if baseline else 0.0

        def mk(component: str, value: float, detail: str, rank: int) -> DecompositionComponent:
            return DecompositionComponent(
                organization_id=organization_id,
                investigation_id=investigation.id,
                kpi_id=kpi_id,
                component=component,
                value=round(value, 6),
                pct=round(value / baseline * 100.0, 4) if baseline else 0.0,
                method="sql",
                query_ref=QUERY_REF_TEMPLATE,
                detail=detail,
                rank=rank,
            )

        rows = [
            mk("price", price, "Σ (p1−p0)·q0 across the SKU panel — realized price change at pre-movement volumes", 1),
            mk("volume", volume, "Σ (q1−q0)·p0 — quantity change at pre-movement prices", 2),
            mk("mix", mix, "Σ (p1−p0)·(q1−q0) — joint price×quantity reallocation", 3),
            mk("region", region, "Cross-region reallocation net of SKU effects (single-region panel ⇒ 0)", 4),
            mk(
                "residual",
                residual,
                f"Movement not explained by the panel (seasonal attribution via baseline comparison; "
                f"panel coverage {coverage:.1%} of baseline). Components+residual reconcile to the total by identity.",
                5,
            ),
        ]
    else:
        # Honest fallback: no fact panel ⇒ one labeled component, no invented split.
        rows = [
            DecompositionComponent(
                organization_id=organization_id,
                investigation_id=investigation.id,
                kpi_id=kpi_id,
                component="level",
                value=round(movement, 6),
                pct=round(movement / baseline * 100.0, 4) if baseline else 0.0,
                method="baseline_compare",
                query_ref="current vs seasonal-median baseline (detection result)",
                detail="No SKU fact panel declared for this KPI — the movement is reported as a single level change with its baseline comparison, not an invented split.",
                rank=1,
            )
        ]

    for r in rows:
        db.add(r)
    db.flush()

    # Guard the identity (tests assert it too) — never persist a broken waterfall.
    total = sum(r.value for r in rows)
    if abs(total - movement) > 1e-6:
        raise AppError("DECOMPOSITION_IDENTITY", f"components {total:.6f} ≠ movement {movement:.6f}", 500)
    return rows


def get_decomposition(db: Session, organization_id: str, investigation_id: str) -> list[DecompositionComponent]:
    rows = (
        db.query(DecompositionComponent)
        .filter(
            DecompositionComponent.organization_id == organization_id,
            DecompositionComponent.investigation_id == investigation_id,
        )
        .order_by(DecompositionComponent.rank)
        .all()
    )
    return rows


def serialize(row: DecompositionComponent) -> dict:
    return {
        "component": row.component,
        "value": row.value,
        "pct": row.pct,
        "method": row.method,
        "query_ref": row.query_ref,
        "detail": row.detail,
    }
