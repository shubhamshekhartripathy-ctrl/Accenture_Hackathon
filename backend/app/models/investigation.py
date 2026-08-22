from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import JSONType
from .base import Base, IdMixin, OrgMixin, TimestampMixin

# Workflow states (arch Q). S2 implements the prefix through TRIAGED; later
# slices extend into the certainty/decision branches without refactoring.
WORKFLOW_STATES = (
    "CONTRACT_READY", "RECONCILING", "RECONCILED", "DETECTING", "DETECTED",
    "TRIAGED", "EXPLAINING", "EXPLAINED", "CERTAINTY_DECISION",
    "CLARIFY", "ABSTAINED",
    "DECISION_OPTIONS_GENERATED", "SIMULATED", "GUARDRAILS_CHECKED",
    "SECOND_ORDER_ANALYZED", "COLLISIONS_CHECKED", "RIGHTS_CHECKED",
    "DECISION_RECORD_CREATED", "PORTFOLIO_UPDATED", "HUMAN_APPROVAL",
    "APPROVED", "REJECTED", "OVERRIDDEN", "MONITORING", "OUTCOME_RECORDED",
    "LEARNED", "DECISION_BLOCKED", "FAILED",
)

# Allowed transitions — the server-side rule book (a subset is reachable per slice).
WORKFLOW_TRANSITIONS: dict[tuple[str, str], str] = {
    ("CONTRACT_READY", "RECONCILING"): "reconcile_start",
    ("RECONCILING", "RECONCILED"): "reconcile_done",
    ("RECONCILED", "DETECTING"): "detect_start",
    ("DETECTING", "DETECTED"): "detect_done",
    ("DETECTED", "TRIAGED"): "triage_done",
    ("TRIAGED", "EXPLAINING"): "explain_start",
    ("EXPLAINING", "EXPLAINED"): "explain_done",
    ("EXPLAINED", "CERTAINTY_DECISION"): "certainty_start",
    # every state may fail; a representative set is declared and extended per slice
    ("CONTRACT_READY", "FAILED"): "stage_failure",
    ("RECONCILING", "FAILED"): "stage_failure",
    ("RECONCILED", "FAILED"): "stage_failure",
    ("DETECTING", "FAILED"): "stage_failure",
    ("DETECTED", "FAILED"): "stage_failure",
    ("TRIAGED", "FAILED"): "stage_failure",
    # Certainty branch (S5)
    ("CERTAINTY_DECISION", "CLARIFY"): "certainty_clarify",
    ("CERTAINTY_DECISION", "ABSTAINED"): "certainty_abstain",
    ("CERTAINTY_DECISION", "DECISION_OPTIONS_GENERATED"): "decision_options",
    # Decision branch (S7–S9)
    ("DECISION_OPTIONS_GENERATED", "SIMULATED"): "simulated",
    ("SIMULATED", "GUARDRAILS_CHECKED"): "guardrails_checked",
    ("GUARDRAILS_CHECKED", "SECOND_ORDER_ANALYZED"): "second_order",
    ("GUARDRAILS_CHECKED", "RIGHTS_CHECKED"): "rights_direct",  # S7 path; S8 inserts second-order+collisions
    ("SECOND_ORDER_ANALYZED", "COLLISIONS_CHECKED"): "collisions_checked",
    ("COLLISIONS_CHECKED", "RIGHTS_CHECKED"): "rights_checked",
    ("RIGHTS_CHECKED", "DECISION_RECORD_CREATED"): "decision_record",
    ("DECISION_RECORD_CREATED", "PORTFOLIO_UPDATED"): "portfolio_updated",
    ("PORTFOLIO_UPDATED", "HUMAN_APPROVAL"): "human_approval",
    ("HUMAN_APPROVAL", "APPROVED"): "approved",
    ("HUMAN_APPROVAL", "REJECTED"): "rejected",
    ("HUMAN_APPROVAL", "OVERRIDDEN"): "overridden",
    ("APPROVED", "MONITORING"): "monitoring",
    ("MONITORING", "OUTCOME_RECORDED"): "outcome_recorded",
    ("OUTCOME_RECORDED", "LEARNED"): "learned",
    ("CERTAINTY_DECISION", "DECISION_BLOCKED"): "all_options_blocked",
    ("CLARIFY", "EXPLAINING"): "clarify_resumed",
    ("EXPLAINING", "FAILED"): "stage_failure",
    ("EXPLAINED", "FAILED"): "stage_failure",
    ("CERTAINTY_DECISION", "FAILED"): "stage_failure",
}


class Investigation(Base, OrgMixin):
    """A bounded investigation of a KPI movement (D.1 object 7).

    Pins the contract version used so every conclusion is reproducible against
    its governing definition. Every workflow transition is a persisted row.
    """

    __tablename__ = "investigations"
    __table_args__ = (Index("ix_investigation_kpi_state", "kpi_id", "workflow_state"),)

    kpi_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpis.id"), index=True)
    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"))
    contract_version: Mapped[int] = mapped_column(Integer)  # pinned at creation (AC1 reproducibility)
    workflow_state: Mapped[str] = mapped_column(String(30), default="CONTRACT_READY", index=True)
    period_key: Mapped[str] = mapped_column(String(20), default="")
    reliability_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_cap_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)
    working_value_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)
    cold_start_mode: Mapped[bool] = mapped_column(default=False)
    certainty_state: Mapped[str | None] = mapped_column(String(30), nullable=True)  # ACT | ACT_WITH_CAUTION | CLARIFY | ABSTAIN
    final_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    lead_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    certainty_reasons: Mapped[list] = mapped_column(JSONType, default=list)
    abstention: Mapped[dict] = mapped_column(JSONType, default=dict)   # the six fields (AC8)
    clarification: Mapped[dict] = mapped_column(JSONType, default=dict)  # named gap + routed owner
    summary: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")

    kpi = relationship("Kpi", lazy="joined")
    stage_events = relationship(
        "InvestigationStageEvent", cascade="all, delete-orphan", lazy="selectin",
        order_by="InvestigationStageEvent.created_at",
    )


class InvestigationStageEvent(Base, IdMixin, TimestampMixin):
    """One persisted workflow transition — refresh never loses state (arch Q)."""

    __tablename__ = "investigation_stage_events"

    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id"), index=True)
    from_state: Mapped[str] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    stage_code: Mapped[str] = mapped_column(String(40))
    ok: Mapped[bool] = mapped_column(default=True)
    message: Mapped[str] = mapped_column(String(200), default="")  # SAFE operational text only
    artifact_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
