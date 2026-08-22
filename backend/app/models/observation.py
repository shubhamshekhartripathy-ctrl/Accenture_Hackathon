from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, OrgMixin, TimestampMixin


class KpiObservation(Base, OrgMixin):
    """A source-fed KPI value at a fiscal period (D.1 object 3).

    Multi-source: the same kpi+period can carry different values from different
    sources (ERP invoiced vs GL recognized) — reconciliation reasons about these
    disagreements; nothing is silently merged.
    """

    __tablename__ = "kpi_observations"
    __table_args__ = (
        Index("ix_obs_kpi_period", "kpi_id", "period_key"),
        Index("ix_obs_source_period", "source_id", "period_key"),
    )

    kpi_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpis.id"))
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_systems.id"))
    period_key: Mapped[str] = mapped_column(String(20))  # P1..P14 (fiscal periods)
    calendar_key: Mapped[str] = mapped_column(String(30), default="")  # e.g. FY26-Q3-M3 / WEEK-2026-14
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[float] = mapped_column(Float)
    entity_id: Mapped[str] = mapped_column(String(60), default="ALL")  # canonical entity (region/DC/SKU family)
    grain: Mapped[str] = mapped_column(String(120), default="")
    freshness_age_days: Mapped[int] = mapped_column(Integer, default=0)  # age at ingest vs demo clock
    quality_state: Mapped[str] = mapped_column(String(20), default="OK")  # OK | STALE | PARTIAL
    checksum: Mapped[str] = mapped_column(String(64), default="")

    kpi = relationship("Kpi", lazy="joined")
    source = relationship("SourceSystem", lazy="joined")


class ObservationFact(Base, OrgMixin):
    """SKU×region price/quantity facts backing contribution analysis (arch H.2).

    The quantitative spine of decomposition: p0/q0 = pre-movement window panel,
    p1/q1 = current window panel. Components are pure SQL over these rows, so
    every decomposition number is inspectable back to a fact row.
    """

    __tablename__ = "observation_facts"
    __table_args__ = (Index("ix_fact_kpi_period", "kpi_id", "period_key"),)

    kpi_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpis.id"), index=True)
    period_key: Mapped[str] = mapped_column(String(20), index=True)
    baseline_period_key: Mapped[str] = mapped_column(String(20), default="")
    sku: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(30), default="NE")
    channel: Mapped[str] = mapped_column(String(30), default="GT")
    p0: Mapped[float] = mapped_column(Float)
    p1: Mapped[float] = mapped_column(Float)
    q0: Mapped[float] = mapped_column(Float)
    q1: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default="INR_M")
    note: Mapped[str] = mapped_column(String(200), default="")
