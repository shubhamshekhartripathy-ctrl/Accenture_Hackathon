from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import JSONType
from .base import Base, OrgMixin


class DetectionResult(Base, OrgMixin):
    """DETECT artifact (D.1 object 5): statistical behavior, method + model version persisted."""

    __tablename__ = "detection_results"

    kpi_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpis.id"), index=True)
    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"))
    period_key: Mapped[str] = mapped_column(String(20))
    source_value: Mapped[float] = mapped_column(Float)  # the (reconciled working) value analyzed
    baseline: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    ci_lo: Mapped[float] = mapped_column(Float)
    ci_hi: Mapped[float] = mapped_column(Float)
    deviation: Mapped[float] = mapped_column(Float)  # absolute
    deviation_pct: Mapped[float] = mapped_column(Float)  # signed %
    robust_z: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float] = mapped_column(Float)  # clamp(|z|/6, 0, 1)
    statistical_significance: Mapped[float] = mapped_column(Float)  # clamp((max(z,6a)-2)/4, 0, 1)
    history_n: Mapped[int] = mapped_column(Integer, default=0)
    cold_start_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    method: Mapped[str] = mapped_column(String(80))  # seasonal_median_robust_z
    model_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MaterialityScore(Base, OrgMixin):
    """TRIAGE artifact (D.1 object 6): business importance with stored arithmetic.

    Separate stage, table, and ledger row from detection — significance (stats)
    never masquerades as materiality (business judgment).
    """

    __tablename__ = "materiality_scores"

    detection_id: Mapped[str] = mapped_column(String(36), ForeignKey("detection_results.id"), index=True)
    kpi_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpis.id"), index=True)
    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"))
    period_key: Mapped[str] = mapped_column(String(20))
    significance: Mapped[float] = mapped_column(Float)
    exposure_rs: Mapped[float] = mapped_column(Float)
    margin_weight: Mapped[float] = mapped_column(Float)
    strategic_weight: Mapped[float] = mapped_column(Float)
    risk_factor: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(20))  # CRITICAL | ELEVATED | WATCH | NOISE | COLD START
    monitor_only: Mapped[bool] = mapped_column(Boolean, default=False)
    arithmetic: Mapped[dict] = mapped_column(JSONType)  # full inspectable arithmetic ("why CRITICAL?")
    threshold_comparison: Mapped[dict] = mapped_column(JSONType, default=dict)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
