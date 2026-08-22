from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OrgMixin


class StageTelemetry(Base, OrgMixin):
    """One row per stage per run — the Transparency Ledger's raw material (arch O.1).

    Full v3 schema is created now so later slices only write rows, never
    migrate. Real execution metadata only — never fabricated.
    """

    __tablename__ = "stage_telemetry"

    run_id: Mapped[str] = mapped_column(String(64), index=True)
    stage_code: Mapped[str] = mapped_column(String(40), index=True)
    method_label: Mapped[str] = mapped_column(String(20))  # sql | stats | rules | ml | retrieval | llm
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    model_class: Mapped[str | None] = mapped_column(String(40), nullable=True)  # fast | reasoning | quality | embedding
    route_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_est: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_latency_saved_ms: Mapped[int] = mapped_column(Integer, default=0)
    cache_cost_avoided_rs: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
