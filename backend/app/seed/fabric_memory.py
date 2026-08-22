"""Institutional memory seed (AC25) — the locked historical fabric.

Hero: NE Q3 2025 supplier delay at Guwahati DC, action = activate backup
supplier, outcome +₹3.1M within band — similarity ≥ 0.85 for the hero
investigation's search. Plus three sibling launch analogues for the
cold-start millet KPI. Embeddings: deterministic feature-hash (replay-safe).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..domains.memory.service import seed_embedding
from ..models.memory import HistoricalCase

CASES = [
    dict(
        title="NE Q3 2025 — Supplier delay at Guwahati DC (atata supply gap)",
        period_label="NE Q3 2025", kpi_code="revenue_ne", driver_class="supply_disruption",
        region="NE",
        action_taken=("Atta supply to NE fell 22% for 3 weeks after the Guwahati DC lead supplier "
                      "missed OTIF; activated the pre-qualified backup supplier (Kolkata) and paid "
                      "a 3% premium for expedited freight."),
        outcome_rs=3_100_000.0, within_band=True,
        lesson=("Backup supplier activation recovered revenue within 2 weeks; the 3% freight premium "
                "was < the revenue at risk. Decide FAST — every day of waiting cost ₹0.4M."),
        entities=["Guwahati DC", "backup supplier", "OTIF", "freight premium", "atata"],
        access_roles=[],  # visible to all roles in org
    ),
    dict(
        title="Atta Premium Launch 2024 — ramp underperformance, NE",
        period_label="NE Q4 2024", kpi_code="revenue_ne", driver_class="launch_ramp",
        region="NE",
        action_taken=("New premium atta SKU ramped at 61% of plan in month 1; fixed assortment "
                      "gaps in 180 stores and re-ran the launch media burst in week 5."),
        outcome_rs=1_400_000.0, within_band=True,
        lesson=("Assortment coverage, not awareness, was the ramp limiter; fix distribution before "
                "spending more on media."),
        entities=["assortment", "launch", "media burst"],
        access_roles=[],
        analogue_for="revenue_millet_ne",
    ),
    dict(
        title="Oils Blend Launch 2025 — margin vs volume trade-off",
        period_label="NE Q1 2025", kpi_code="revenue_ne", driver_class="launch_ramp",
        region="NE",
        action_taken=("Launch discounting (8%) lifted volume but eroded blend margin; re-priced at "
                      "+4% with a smaller pack introduction."),
        outcome_rs=900_000.0, within_band=False,
        lesson=("Discount-led launches buy volume at margin cost — set the guardrail BEFORE the "
                "promotion, not after."),
        entities=["launch", "discount", "pack price"],
        access_roles=["KPI_OWNER", "EXECUTIVE", "ADMIN", "ANALYST"],
        analogue_for="revenue_millet_ne",
    ),
    dict(
        title="Snacks Range Extension 2025 — supply-ready ramp",
        period_label="NE Q2 2025", kpi_code="revenue_ne", driver_class="launch_ramp",
        region="NE",
        action_taken=("Range extension launched with 3 weeks of safety stock pre-positioned; ramp "
                      "hit 88% of plan in month 1 with no stockouts."),
        outcome_rs=2_200_000.0, within_band=True,
        lesson=("Pre-positioned inventory is the cheapest launch insurance; ramp targets were hit "
                "without expediting."),
        entities=["safety stock", "launch", "range extension"],
        access_roles=[],
        analogue_for="revenue_millet_ne",
    ),
]


def ensure_memory(db: Session, organization_id: str) -> int:
    n = 0
    for c in CASES:
        exists = db.query(HistoricalCase).filter(
            HistoricalCase.organization_id == organization_id,
            HistoricalCase.title == c["title"],
        ).first()
        if exists:
            continue
        row = HistoricalCase(organization_id=organization_id, **c)
        seed_embedding(row)
        db.add(row)
        n += 1
    db.flush()
    return n
