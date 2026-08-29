"""Observation fabric — the planted, deterministic Apex Foods data (arch T.2).

Series are constructed analytically so the engines compute EXACTLY the locked
demo numbers (revenue −12% @ ~5.1σ, marketing −4% @ ~2.1σ, …):

    values = baseline + scale × base_deviations   (base: median 0, MAD 0.5)

which makes the pre-movement window's median and MAD exact by construction:
    MAD(values) = scale × 0.5  →  robust_sigma = 1.4826 × scale × 0.5
    robust_z    = |current − baseline| / robust_sigma

Freshness is anchored to the DEMO CLOCK (newest observation across sources) so
penalties (POS stale → 0.12 bracket) replay deterministically.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models.kpi import Kpi
from ..models.observation import KpiObservation, ObservationFact

# Base deviation shape: median 0, MAD exactly 0.5 (13 periods).
_BASE13 = [-2.0, -1.5, -1.0, -0.5, -0.5, -0.5, 0.0, 0.5, 0.5, 0.5, 1.0, 1.5, 2.0]

DEMO_NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)  # fixed clock — deterministic replay


def _series(baseline: float, robust_sigma_target: float) -> list[float]:
    scale = robust_sigma_target / (1.4826 * 0.5)
    return [round(baseline + scale * d, 4) for d in _BASE13]


def _mk(
    db: Session, org_id: str, kpi_id: str, source_id: str, period_key: str,
    value: float, occurred_at: datetime, grain: str, calendar_key: str = "",
    quality: str = "OK",
) -> None:
    import hashlib

    checksum = hashlib.sha1(f"{kpi_id}|{source_id}|{period_key}|{value}".encode()).hexdigest()[:16]
    db.add(KpiObservation(
        organization_id=org_id, kpi_id=kpi_id, source_id=source_id, period_key=period_key,
        calendar_key=calendar_key, occurred_at=occurred_at, value=value, entity_id="ALL",
        grain=grain, freshness_age_days=int((DEMO_NOW - occurred_at).total_seconds() // 86400),
        quality_state=quality, checksum=checksum,
    ))


def ensure_observations(db: Session, org_id: str, kpis: dict[str, Kpi], sources: dict) -> None:
    existing = db.query(KpiObservation).filter(KpiObservation.organization_id == org_id).count()
    if existing:
        return

    periods = [f"P{i}" for i in range(1, 15)]  # P1..P14 (P14 = current movement period)

    def add_full_series(kpi_code: str, source_code: str, baseline: float, current: float,
                        sigma: float, grain: str, calendar_fmt: str, lag_days: int = 1) -> None:
        kpi, src = kpis[kpi_code], sources[source_code]
        history = _series(baseline, sigma)
        for i, value in enumerate(history):
            _mk(db, org_id, kpi.id, src.id, periods[i], value,
                occurred_at=DEMO_NOW - timedelta(days=lag_days + (13 - i) * 7), grain=grain,
                calendar_key=calendar_fmt.format(i + 1))
        _mk(db, org_id, kpi.id, src.id, "P14", current,
            occurred_at=DEMO_NOW - timedelta(days=lag_days), grain=grain,
            calendar_key=calendar_fmt.format(14))

    # --- Revenue NE (hero): baseline 95.45, current 84.0 → −12.0% @ z≈5.15 -----
    # sigma target chosen so |84.0 − 95.45| / sigma = 5.1 → sigma = 2.2239 (MAD 1.5)
    add_full_series("revenue_ne", "erp", baseline=95.45, current=84.0, sigma=2.2239,
                    grain="SKU x DC → period agg", calendar_fmt="FY26-P{}")

    # GL recognized figure for the same period: 87.0 (definition conflict driver).
    # Monthly close calendar — different calendar boundary, published 'current'.
    _mk(db, org_id, kpis["revenue_ne"].id, sources["gl"].id, "P14", 87.0,
        occurred_at=DEMO_NOW - timedelta(days=1), grain="company x account",
        calendar_key="FY26-M4-close")

    # POS panel does not assert revenue values; its STALENESS still penalizes reliability
    # (Moment 1: definition conflict + stale POS). Age 15d vs clock (weekly 7d + 2d tol → 6d beyond → 0.12).
    _mk(db, org_id, kpis["revenue_ne"].id, sources["pos"].id, "P13", 96.1,
        occurred_at=DEMO_NOW - timedelta(days=0.5), grain="region x category",
        calendar_key="audit-wk-13", quality="OK")

    # --- OSA NE: baseline 90.8, current 71.4 → −21.3% @ z≈4.4 → ELEVATED -------
    # Panel publishes with its normal 6-day lag — current (within tolerance) per spec §19.1.
    add_full_series("osa_ne", "pos", baseline=90.8, current=71.4, sigma=4.42,
                    grain="region x category", calendar_fmt="audit-P{}", lag_days=0)

    # --- Inventory cover NE: baseline 11.6, current 5.1 → −56% @ z≈3.8 → ELEVATED
    add_full_series("inventory_cover_ne", "wms", baseline=11.6, current=5.1, sigma=1.71,
                    grain="SKU x DC", calendar_fmt="WMS-P{}")

    # --- Marketing ROI: baseline 3.10, current 2.976 → −4.0% @ z≈2.10 → WATCH (floored)
    add_full_series("marketing_roi", "erp", baseline=3.10, current=2.976, sigma=0.0592,
                    grain="campaign", calendar_fmt="camp-P{}")

    # --- Supplier reliability NE: baseline 94.0, current 81.2 → −13.6% @ z≈3.0 → WATCH
    add_full_series("supplier_reliability", "scorecard", baseline=94.0, current=81.2, sigma=4.27,
                    grain="supplier x region", calendar_fmt="supp-P{}")

    # --- Sales per outlet SOUTH (abstention case, S5): −4.9% @ z≈1.6 → NOISE (off exec radar)
    # The South POS panel has MISSED a refresh cycle (stale feed, age 15d → 0.12) — the
    # abstention story's freshness problem is planted here, not bolted on.
    add_full_series("sales_per_outlet_south", "pos", baseline=210.0, current=199.8, sigma=6.50,
                    grain="region x category", calendar_fmt="audit-P{}", lag_days=16)
    # ERP disagrees mildly on South (within tolerance) but at a different grain → grain 0.05
    _mk(db, org_id, kpis["sales_per_outlet_south"].id, sources["erp"].id, "P14", 202.9,
        occurred_at=DEMO_NOW - timedelta(days=1), grain="SKU x DC → period agg",
        calendar_key="FY26-P14")

    # --- Millet Noodles launch: only 5 periods of history → COLD START (<13)
    millet_trend = [2.10, 2.35, 2.62, 2.85, 2.66]  # launch ramp + P5 dip (wide CI, monitor-only)
    kpi, src = kpis["millet_noodles_revenue"], sources["erp"]
    for i, value in enumerate(millet_trend):
        _mk(db, org_id, kpi.id, src.id, f"P{i + 1}", value,
            occurred_at=DEMO_NOW - timedelta(days=(5 - i) * 7), grain="SKU x DC → period agg",
            calendar_key=f"launch-P{i + 1}")

    # --- SKU fact panel for contribution analysis (arch H.2) -------------------
    # Engineered so the SQL formulas produce EXACTLY the locked decomposition:
    #   price +1.8% · volume −9.5% · mix −0.9% · region 0.0% (single region)
    #   residual = −12.0% − (price+volume+mix) = −3.4%  (identity-checked in tests)
    # Panel baseline Σp0q0 = 95.4 (99.9% coverage of the 95.45 baseline).
    _FACTS = [  # sku, p0, p1, q0, q1 (price ₹/unit, volume M units), note
        ("Staples Atta 10kg", 40.00, 43.790, 0.800, 0.5733,
         "list +6% at wk10 + discount rollback → effective +9.47%; volume −28.3% (supplier-delay stockouts)"),
        ("Edible Oil 1L", 60.00, 60.000, 0.450, 0.4500, "stable"),
        ("Snacks 250g", 25.00, 24.000, 1.000, 1.0000, "promo price −4%, volume held"),
        ("Beverages 500ml", 30.00, 29.174, 0.380, 0.3800, "price −2.75%"),
    ]
    for sku, p0, p1, q0, q1, note in _FACTS:
        db.add(ObservationFact(
            organization_id=org_id, kpi_id=kpis["revenue_ne"].id, period_key="P14",
            baseline_period_key="P13", sku=sku, region="NE", channel="GT",
            p0=p0, p1=p1, q0=q0, q1=q1, unit="INR_M", note=note,
        ))

    db.flush()
