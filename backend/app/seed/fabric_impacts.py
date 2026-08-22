"""Impact fabric — derived downstream metrics + edges for the locked AC20/AC21 demo.

Every number is chain-derived from the architecture's locked targets; nothing
is invented to make tests pass:
    stockout edge elasticity  −0.667 = 12 / −18   (−18% cover ⇒ +12 pts risk)
    complaints edge elasticity +0.583 = 7 / 12    (+12 pts ⇒ +7% complaints)
    joint collision stockout   +17 pts = 0.667 × (18 + 0.5×15)  (damped second contributor)
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.impacts import ImpactEdge, ImpactMetric

SCENARIO = "apex_revenue_decline_ne"

METRICS = [
    dict(
        code="stockout_risk_ne",
        name="Stockout Risk — Northeast",
        unit="PTS",
        definition=(
            "Composite stockout-risk score for the NE lane, in points. DERIVED DOWNSTREAM IMPACT "
            "METRIC — not a primary governed KPI: it has no KPI contract, is never investigated, "
            "and is computed only by graph_elasticity propagation from inventory_cover_ne."
        ),
        formula="stockout_delta_pts = inventory_cover_effect_pct × elasticity(−0.667)  # −18% ⇒ +12.0 pts",
        provenance="derived:graph_elasticity:inventory_cover_ne→stockout_risk_ne",
    ),
    dict(
        code="complaints_rate_ne",
        name="Complaints Rate — Northeast",
        unit="PCT",
        definition=(
            "Consumer complaints rate for NE, in percent. DERIVED DOWNSTREAM IMPACT METRIC — not a "
            "primary governed KPI: propagated from stockout_risk_ne; monitor-only business impact."
        ),
        formula="complaints_delta_pct = stockout_delta_pts × elasticity(+0.583)  # +12 pts ⇒ +7.0%",
        provenance="derived:graph_elasticity:stockout_risk_ne→complaints_rate_ne",
    ),
]

EDGES = [
    dict(
        parent_code="inventory_cover_ne", child_code="stockout_risk_ne",
        elasticity=-0.667, confidence=0.8, lag_days=7,
        derivation_note="elasticity = 12 pts / −18% cover — the locked AC20 chain value.",
    ),
    dict(
        parent_code="stockout_risk_ne", child_code="complaints_rate_ne",
        elasticity=0.583, confidence=0.75, lag_days=14,
        derivation_note="elasticity = 7% / 12 pts — the locked AC20 chain value.",
    ),
]


def ensure_impacts(db: Session, org_id: str) -> None:
    for m in METRICS:
        row = db.query(ImpactMetric).filter(
            ImpactMetric.organization_id == org_id, ImpactMetric.code == m["code"]
        ).first()
        if row is None:
            db.add(ImpactMetric(organization_id=org_id, scenario_id=SCENARIO, **m))
        else:
            row.name, row.unit, row.definition = m["name"], m["unit"], m["definition"]
            row.formula, row.provenance = m["formula"], m["provenance"]
            db.add(row)
    for e in EDGES:
        row = db.query(ImpactEdge).filter(
            ImpactEdge.organization_id == org_id,
            ImpactEdge.parent_code == e["parent_code"],
            ImpactEdge.child_code == e["child_code"],
        ).first()
        if row is None:
            db.add(ImpactEdge(organization_id=org_id, scenario_id=SCENARIO, **e))
        else:
            row.elasticity, row.confidence, row.lag_days = e["elasticity"], e["confidence"], e["lag_days"]
            row.derivation_note = e["derivation_note"]
            db.add(row)
    db.flush()
