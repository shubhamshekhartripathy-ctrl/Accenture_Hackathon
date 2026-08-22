"""Decision records (AC10–13): options → simulation → guardrails → rights → human approval."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, JSONType
from .base import IdMixin, TimestampMixin
from .org import OrgMixin


class DecisionOption(Base, OrgMixin, IdMixin, TimestampMixin):
    __tablename__ = "decision_options"
    __table_args__ = (Index("ix_dec_options_inv", "organization_id", "investigation_id"),)

    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id"), index=True)
    code: Mapped[str] = mapped_column(String(60))           # A_backup_supplier | B_air_freight | …
    driver: Mapped[str] = mapped_column(String(60))         # contract driver it acts on
    lever: Mapped[str] = mapped_column(String(60))          # controllable lever (action class)
    action: Mapped[str] = mapped_column(Text)               # plain-language action
    expected_impact_rs: Mapped[float] = mapped_column(Float)
    impact_lo_rs: Mapped[float] = mapped_column(Float)
    impact_hi_rs: Mapped[float] = mapped_column(Float)
    cost_rs: Mapped[float] = mapped_column(Float)
    cash_exposure_rs: Mapped[float] = mapped_column(Float, default=0.0)  # working capital incl.
    horizon_days: Mapped[int] = mapped_column(Integer, default=42)
    owner_role: Mapped[str] = mapped_column(String(40))

    # Deterministic simulation snapshot (method "config_sim_v1": deltas applied to
    # current KPI values; arithmetic fully recorded, never LLM).
    simulation: Mapped[dict] = mapped_column(JSONType, default=dict)
    guardrail_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # PASS | FAIL | NOT_SAFE
    guardrail_reasons: Mapped[list] = mapped_column(JSONType, default=list)
    rights_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)    # AUTHORIZED | ESCALATE | DENIED
    rights_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_target: Mapped[str | None] = mapped_column(String(40), nullable=True)
    comparable_to: Mapped[str | None] = mapped_column(String(60), nullable=True)     # C → C' compare
    external_proposal: Mapped[bool] = mapped_column(Boolean, default=False)  # in-flight decision from another team
    decision_health: Mapped[str | None] = mapped_column(String(30), nullable=True)   # BETTER | WORSE | EQUAL

    evidence_set: Mapped[list] = mapped_column(JSONType, default=list)  # doc keys
    scenario_id: Mapped[str | None] = mapped_column(String(80), nullable=True)       # config provenance
    simulation_version: Mapped[str] = mapped_column(String(20), default="config_sim_v1")


class DecisionRecord(Base, OrgMixin, IdMixin, TimestampMixin):
    __tablename__ = "decision_records"
    __table_args__ = (Index("ix_dec_records_inv", "organization_id", "investigation_id"),)

    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id"), index=True)
    option_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_options.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|APPROVED|REJECTED|OVERRIDDEN|ESCALATED
    requested_by_role: Mapped[str | None] = mapped_column(String(40), nullable=True)

    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # required on override (S9 learning)

    monitoring_plan: Mapped[dict] = mapped_column(JSONType, default=dict)  # metric, cadence, window, band
    evidence_set: Mapped[list] = mapped_column(JSONType, default=list)
    guardrail_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rights_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    simulation_version: Mapped[str] = mapped_column(String(20), default="config_sim_v1")

    # Outcome (S9)
    predicted_impact_rs: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_impact_rs: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_variance: Mapped[float | None] = mapped_column(Float, nullable=True)
    within_band: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    option = relationship("DecisionOption", lazy="joined")


class DecisionCollision(Base, OrgMixin, IdMixin, TimestampMixin):
    """AC21 — a detected collision between two decisions. Humans resolve."""
    __tablename__ = "decision_collisions"
    __table_args__ = (Index("ix_dec_collisions_inv", "organization_id", "investigation_id"),)

    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id"), index=True)
    option_ids: Mapped[list] = mapped_column(JSONType, default=list)
    option_codes: Mapped[list] = mapped_column(JSONType, default=list)
    affected_kpi: Mapped[str] = mapped_column(String(60))
    combined_effect_pct: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(10))           # HIGH | MEDIUM | LOW
    collision_type: Mapped[str] = mapped_column(String(20))     # OPPOSING | AMPLIFY | AMPLIFY_BREACH | OVERLAP
    owners: Mapped[list] = mapped_column(JSONType, default=list)
    combined_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_options: Mapped[list] = mapped_column(JSONType, default=list)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[str | None] = mapped_column(String(30), nullable=True)   # SEQUENCE | ESCALATE_COMBINED | ABANDON_ONE
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
