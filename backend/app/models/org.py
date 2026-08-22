from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import JSONType
from .base import Base, IdMixin, OrgMixin, TimestampMixin


class Organization(Base, IdMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    industry: Mapped[str] = mapped_column(String(80), default="FMCG")
    # Workspace state: which scenario the org currently has open (set by POST /scenarios/{id}/start).
    active_scenario_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_cost_cap_rs: Mapped[float | None] = mapped_column(Float, default=50.0)  # S10: tenant LLM cost cap
    settings: Mapped[dict] = mapped_column(JSONType, default=dict)


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        # tenant-scoped uniqueness of emails within an organization
        None,
    )

    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    # RBAC roles: ADMIN | EXECUTIVE | ANALYST | SUPPLY_CHAIN | KPI_OWNER
    role: Mapped[str] = mapped_column(String(40))
    job_title: Mapped[str] = mapped_column(String(120), default="")
    # Row scope for region-level personas (e.g. SUPPLY_CHAIN -> ["NE"]); empty = all rows in scope
    region_scope: Mapped[list] = mapped_column(JSONType, default=list)
    password_hash: Mapped[str] = mapped_column(String(256))
    password_salt: Mapped[str] = mapped_column(String(64))
    pbkdf2_iterations: Mapped[int] = mapped_column(Integer, default=210_000)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", lazy="joined")


class AuditEvent(Base, IdMixin, TimestampMixin):
    """Immutable audit trail. Every governed mutation writes a row (spec §7, arch U)."""

    __tablename__ = "audit_events"

    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)  # e.g. auth.login, contract.patch
    object_type: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), default="success")  # success | denied | failure
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
