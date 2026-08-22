"""Institutional memory + learning artifacts (AC14–16, AC23, AC25).

HistoricalCase: the seed fabric's real history (NE Q3 2025 supplier delay +
three sibling launches) with deterministic feature-hash embeddings (pgvector
in Docker mode; hashing fallback offline with a visible DEGRADED note).
ProposedContractChange: the ONLY path by which an ACTIVE contract evolves —
proposal → review → merge. The learning loop never mutates ACTIVE contracts.
FeedbackEvent: structured feedback with a VISIBLE effect, never silent.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, JSONType
from .base import IdMixin, TimestampMixin
from .org import OrgMixin

# Institutional memory lives in PostgreSQL + pgvector (canonical): the
# deterministic feature-hash vector (256-dim) is stored in a native VECTOR
# column and searched with pgvector cosine distance. The JSON variant exists
# only for the strictly test-only SQLite escape hatch (Python-side cosine).
from sqlalchemy import JSON

try:  # pgvector is a production dependency; guard keeps test-only sqlite importable
    from pgvector.sqlalchemy import Vector

    EMBEDDING_TYPE = JSON().with_variant(Vector(256), "postgresql")
except ImportError:  # pragma: no cover — requirements pin pgvector
    EMBEDDING_TYPE = JSON


class HistoricalCase(Base, OrgMixin, IdMixin, TimestampMixin):
    __tablename__ = "historical_cases"
    __table_args__ = (Index("ix_hist_cases_org_kpi", "organization_id", "kpi_code"),)

    title: Mapped[str] = mapped_column(String(200))
    period_label: Mapped[str] = mapped_column(String(40))        # "NE Q3 2025"
    kpi_code: Mapped[str] = mapped_column(String(60), index=True)
    driver_class: Mapped[str] = mapped_column(String(60), index=True)
    region: Mapped[str] = mapped_column(String(20), default="NE")
    action_taken: Mapped[str] = mapped_column(Text)
    outcome_rs: Mapped[float] = mapped_column(Float)             # signed impact
    within_band: Mapped[bool] = mapped_column(Boolean, default=True)
    lesson: Mapped[str] = mapped_column(Text)
    entities: Mapped[list] = mapped_column(JSONType, default=list)         # ["Guwahati DC", "backup supplier"] — JSON
    access_roles: Mapped[list] = mapped_column(JSONType, default=list)     # entitlement filter (empty ⇒ all) — JSON
    analogue_for: Mapped[str | None] = mapped_column(String(60), nullable=True)  # cold-start analogue target (millet)
    embedding: Mapped[list] = mapped_column(EMBEDDING_TYPE, default=list)  # pgvector VECTOR(256) on PostgreSQL
    embedding_method: Mapped[str] = mapped_column(String(40), default="feature_hash_v1")
    embedding_version: Mapped[str] = mapped_column(String(20), default="1.0.0")


class ProposedContractChange(Base, OrgMixin, IdMixin, TimestampMixin):
    """AC23 — proposal → review → merge. Learning output lands here, never on the contract."""
    __tablename__ = "proposed_contract_changes"
    __table_args__ = (Index("ix_proposals_org_contract", "organization_id", "contract_id"),)

    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    base_version: Mapped[int] = mapped_column(Integer)
    change_type: Mapped[str] = mapped_column(String(40))     # driver_prior_update | driver_correction | threshold | source | entitlement
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)      # the governed change — JSON
    rationale: Mapped[str] = mapped_column(Text, default="")
    origin: Mapped[str] = mapped_column(String(20), default="HUMAN")  # HUMAN | LEARNING_LOOP
    proposed_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    proposed_by_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="IN_REVIEW")  # IN_REVIEW | MERGED | REJECTED
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    merged_to_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class FeedbackEvent(Base, OrgMixin, IdMixin, TimestampMixin):
    """AC15 — structured feedback with a VISIBLE effect. Never RLHF, never autonomous retraining."""
    __tablename__ = "feedback_events"
    __table_args__ = (Index("ix_feedback_org_inv", "organization_id", "investigation_id"),)

    investigation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    feedback_type: Mapped[str] = mapped_column(String(40))  # hypothesis_verdict | driver_correction | evidence_rating | recommendation_rating | override_reason | action_outcome
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)     # JSON
    effect: Mapped[dict] = mapped_column(JSONType, default=dict)      # the visible effect (what changed / what was proposed) — JSON
