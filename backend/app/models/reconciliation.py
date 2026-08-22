from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import JSONType
from .base import Base, IdMixin, OrgMixin, TimestampMixin


class ReconciliationRun(Base, OrgMixin):
    """One RECONCILE cycle for a contract (D.1 object 4): verdict, reliability, working value."""

    __tablename__ = "reconciliation_runs"

    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    period_key: Mapped[str] = mapped_column(String(20))
    verdict: Mapped[str] = mapped_column(String(20))  # CONSISTENT | MINOR | CONFLICTED
    reliability_score: Mapped[float] = mapped_column(Float)
    confidence_cap: Mapped[float] = mapped_column(Float)
    working_value: Mapped[float] = mapped_column(Float)
    working_source_id: Mapped[str] = mapped_column(String(36))
    working_justification: Mapped[str] = mapped_column(Text, default="")
    freshness_profile: Mapped[list] = mapped_column(JSONType, default=list)
    penalties: Mapped[dict] = mapped_column(JSONType, default=dict)
    investigation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    conflicts = relationship(
        "ReconciliationConflict", cascade="all, delete-orphan", lazy="selectin"
    )


class ReconciliationConflict(Base, IdMixin, TimestampMixin):
    """A typed disagreement between sources (never silently merged)."""

    __tablename__ = "reconciliation_conflicts"

    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.id"), index=True)
    conflict_type: Mapped[str] = mapped_column(String(20))  # definition|refresh|grain|hierarchy|calendar|coverage|entity
    severity: Mapped[str] = mapped_column(String(10))  # HIGH | MEDIUM | LOW
    source_a_id: Mapped[str] = mapped_column(String(36))
    source_b_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    value_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_b: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="")
    confidence_impact: Mapped[float] = mapped_column(Float, default=0.0)  # negative
    penalty: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    routed_to_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    routed_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resolution_state: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN | RESOLVED | ACKNOWLEDGED
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
