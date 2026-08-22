"""AI policy + route log models (arch O.2–O.3).

`ai_policy`: (capability × data_classification) → allowed model classes,
providers, budgets, fallback rule. Tenant overrides keyed by organization.
No commercial model names anywhere — capability-based classes only.
`ai_route_log`: every gateway decision, allowed or denied — the ledger's
authoritative route record (Data Sensitivity → Model Policy → Routing →
Telemetry, end to end).
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy import JSON

from ..db import Base, JSONType
from .base import IdMixin, TimestampMixin
from .org import OrgMixin

CAPABILITIES = ("extract_claims", "draft_hypotheses", "translate_narrative", "embed_case")
DATA_CLASSES = ("PUBLIC", "INTERNAL", "SENSITIVE", "RESTRICTED")

# Model classes (capability-mapped, provider-agnostic)
CLASS_FAST = "fast_extract"
CLASS_REASONING = "reasoning"
CLASS_QUALITY = "quality_prose"
CLASS_EMBED = "embedding"

CAPABILITY_CLASS = {
    "extract_claims": CLASS_FAST,
    "draft_hypotheses": CLASS_REASONING,
    "translate_narrative": CLASS_QUALITY,
    "embed_case": CLASS_EMBED,
}


class AiPolicy(Base, OrgMixin, IdMixin, TimestampMixin):
    """Row = one (capability × data_classification) rule. organization_id NULL ⇒ default."""
    __tablename__ = "ai_policies"
    __table_args__ = (Index("ix_ai_policy_lookup", "capability", "data_classification"),)

    capability: Mapped[str] = mapped_column(String(40))
    data_classification: Mapped[str] = mapped_column(String(16))
    allowed_model_classes: Mapped[list] = mapped_column(JSONType, default=list)  # JSON
    allowed_providers: Mapped[list] = mapped_column(JSONType, default=list)       # JSON; empty ⇒ any in class
    external_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_budget_rs: Mapped[float] = mapped_column(Float, default=1.0)
    latency_budget_ms: Mapped[int] = mapped_column(Integer, default=4000)
    fallback_rule: Mapped[str] = mapped_column(String(40), default="DETERMINISTIC")


class AiRouteLog(Base, OrgMixin, IdMixin, TimestampMixin):
    __tablename__ = "ai_route_log"
    __table_args__ = (Index("ix_route_log_inv", "organization_id", "investigation_id"),)

    investigation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    capability: Mapped[str] = mapped_column(String(40))
    data_classification: Mapped[str] = mapped_column(String(16))
    decision: Mapped[str] = mapped_column(String(20))     # ALLOWED | POLICY_DENIED | COST_CAP | DISABLED
    model_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    policy_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(60))  # POLICY_APPROVED_CLASS | POLICY_DENIED_EXTERNAL | …
    fallback: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_est_rs: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
