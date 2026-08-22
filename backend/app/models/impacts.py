"""Derived downstream impact metrics + impact edges (AC20/AC21).

The architecture's primary governed KPI set (revenue_ne, osa_ne,
inventory_cover_ne, marketing_roi, supplier_reliability, + the South and
Millet cases) is UNCHANGED. `stockout_risk_ne` (PTS) and `complaints_rate_ne`
(PCT) are NOT primary KPIs and never get KPI contracts or investigations —
they are DERIVED DOWNSTREAM IMPACT METRICS: secondary business metrics that
only exist as propagation targets of `graph_elasticity`, with explicit units,
definitions, provenance and deterministic formulas.

Graph model: `kpi_relations` (contract ↔ contract, S2) remains the governed
KPI↔KPI edge set named by the architecture. `impact_edges` extends the SAME
propagation semantics (elasticity / confidence / lag_days) to nodes that are
not contracts — the derived metrics. The propagation engine walks the union
graph, node-keyed by code. No duplication: a KPI↔KPI edge lives only in
kpi_relations; an edge touching a derived metric lives only in impact_edges.

Locked demo derivation (nothing invented):
    revenue +8%  × elasticity −2.25 (kpi_relations)  ⇒ inventory −18%
    inventory −18% × elasticity −0.667 = 12/−18 (impact_edges) ⇒ stockout +12 pts
    stockout +12.006 pts × elasticity +0.583 = 7/12 ⇒ complaints +7%
"""
from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .base import IdMixin, TimestampMixin
from .org import OrgMixin


class ImpactMetric(Base, OrgMixin, IdMixin, TimestampMixin):
    """A derived downstream impact metric — never a primary governed KPI."""
    __tablename__ = "impact_metrics"
    __table_args__ = (Index("ix_impact_metrics_org_code", "organization_id", "code", unique=True),)

    code: Mapped[str] = mapped_column(String(60))            # stockout_risk_ne | complaints_rate_ne
    name: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str] = mapped_column(String(10))            # PTS | PCT
    kind: Mapped[str] = mapped_column(String(30), default="DERIVED_IMPACT")  # never KPI
    definition: Mapped[str] = mapped_column(Text)
    formula: Mapped[str] = mapped_column(Text)               # deterministic formula, plain math
    provenance: Mapped[str] = mapped_column(String(120))     # derived:<source edge chain>
    scenario_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # config provenance (AC18)


class ImpactEdge(Base, OrgMixin, IdMixin, TimestampMixin):
    """Propagation edge into (or between) derived impact metrics.

    Same semantics as kpi_relations (elasticity, confidence, lag_days) — this
    table exists only because derived metrics have no contract to point at.
    """
    __tablename__ = "impact_edges"
    __table_args__ = (Index("ix_impact_edges_org_parent", "organization_id", "parent_code"),)

    parent_code: Mapped[str] = mapped_column(String(60), index=True)
    child_code: Mapped[str] = mapped_column(String(60), index=True)
    relation: Mapped[str] = mapped_column(String(20), default="IMPACTS")
    elasticity: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    lag_days: Mapped[int] = mapped_column(Integer, default=7)
    derivation_note: Mapped[str] = mapped_column(Text, default="")  # where the number comes from
    scenario_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
