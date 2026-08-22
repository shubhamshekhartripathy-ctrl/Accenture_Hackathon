from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, OrgMixin, TimestampMixin


class DecompositionComponent(Base, OrgMixin):
    """One contribution-analysis row: a named component of a KPI movement.

    Stored per investigation so the waterfall is replayable and inspectable:
    value, pct of baseline, method label, and the query reference that produced
    it. Components (including residual) always sum to the observed movement —
    the identity is asserted by the engine and by tests (AC5).
    """

    __tablename__ = "decomposition_components"
    __table_args__ = (Index("ix_decomp_inv", "investigation_id"),)

    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id"), index=True)
    kpi_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpis.id"), index=True)
    component: Mapped[str] = mapped_column(String(30))  # price | volume | mix | region | residual | level
    value: Mapped[float] = mapped_column(Float)          # absolute movement units
    pct: Mapped[float] = mapped_column(Float)            # % of baseline
    method: Mapped[str] = mapped_column(String(20), default="sql")  # sql | baseline_compare
    query_ref: Mapped[str] = mapped_column(String(200), default="")  # inspectable provenance
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # human-readable explanation
    rank: Mapped[int] = mapped_column(Integer, default=0)
