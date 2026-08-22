from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import JSONType
from .base import Base, IdMixin, OrgMixin, TimestampMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

# Contract status machine (spec §7.1, arch E):
# DRAFT -> ACTIVE -> CONFLICTED (set by reconcile on definition conflict) -> UNDER_REVIEW -> ACTIVE
CONTRACT_STATUSES = ("DRAFT", "ACTIVE", "CONFLICTED", "UNDER_REVIEW")


class KpiContract(Base, OrgMixin):
    """The primary governed object: what a KPI means and how it may be used.

    One live row per (org, kpi); every edit bumps `version` and writes a full
    snapshot into ContractVersion. Investigations (S2+) pin `contract_version`
    at investigation time so every conclusion is reproducible against its
    governing definition.
    """

    __tablename__ = "kpi_contracts"
    __table_args__ = (UniqueConstraint("organization_id", "kpi_id", "version", name="uq_contract_kpi_version"),)

    kpi_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpis.id"), index=True)
    scenario_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    business_definition: Mapped[str] = mapped_column(Text)
    formula_sql: Mapped[str] = mapped_column(Text, default="")
    formula_note: Mapped[str] = mapped_column(String(600), default="")
    unit: Mapped[str] = mapped_column(String(20))
    business_function: Mapped[str] = mapped_column(String(80), default="")
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    owner_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    calendar_rule: Mapped[str] = mapped_column(String(400), default="")
    hierarchy_config: Mapped[dict] = mapped_column(JSONType, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)

    kpi = relationship("Kpi", lazy="joined")
    owner = relationship("User", foreign_keys=[owner_user_id], lazy="joined")
    sources = relationship(
        "KpiContractSource", cascade="all, delete-orphan", lazy="selectin", order_by="KpiContractSource.rank"
    )
    drivers = relationship(
        "KpiContractDriver", cascade="all, delete-orphan", lazy="selectin", order_by="KpiContractDriver.rank"
    )
    threshold = relationship("KpiContractThreshold", cascade="all, delete-orphan", lazy="joined", uselist=False)
    rights = relationship("KpiContractRight", cascade="all, delete-orphan", lazy="selectin")
    entitlements = relationship("KpiContractEntitlement", cascade="all, delete-orphan", lazy="selectin")


class KpiContractSource(Base, IdMixin, TimestampMixin):
    """Contract satellite: per-source lineage and authority."""

    __tablename__ = "kpi_contract_sources"

    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    source_system_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_systems.id"))
    lineage_path: Mapped[str] = mapped_column(String(400))  # table/feed/transform reference
    is_authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    expected_cadence: Mapped[str] = mapped_column(String(20), default="daily")
    expected_grain: Mapped[str] = mapped_column(String(120), default="")
    tolerance_pct: Mapped[float] = mapped_column(Float, default=0.0)  # data-quality tolerance band
    rank: Mapped[int] = mapped_column(Integer, default=0)

    source_system = relationship("SourceSystem", lazy="joined")


class KpiContractDriver(Base, IdMixin, TimestampMixin):
    """Contract satellite: ranked known drivers — they constrain the hypothesis space."""

    __tablename__ = "kpi_contract_drivers"

    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    driver_code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    direction: Mapped[int] = mapped_column(Integer, default=-1)  # -1 pushes KPI down, +1 up
    prior_weight: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String(20), default="config")  # config | feedback
    hypothesis_class: Mapped[str] = mapped_column(String(60), default="generic")
    rank: Mapped[int] = mapped_column(Integer, default=0)


class KpiContractThreshold(Base, IdMixin, TimestampMixin):
    """Contract satellite: expected range, thresholds, and materiality weights."""

    __tablename__ = "kpi_contract_thresholds"

    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), unique=True, index=True)
    expected_lo: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_hi: Mapped[float | None] = mapped_column(Float, nullable=True)
    warning_deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    exposure_rs_per_point: Mapped[float] = mapped_column(Float, default=0.0)  # ₹ at risk per point of deviation
    margin_weight: Mapped[float] = mapped_column(Float, default=0.0)
    strategic_weight: Mapped[float] = mapped_column(Float, default=0.0)
    min_history: Mapped[int] = mapped_column(Integer, default=13)  # periods; below => cold start
    cold_start_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    # Contract thresholds may floor a materiality band (master §8.4): a watch-list
    # KPI whose raw score lands in NOISE can be floored to WATCH by governance rule.
    floor_band: Mapped[str | None] = mapped_column(String(20), nullable=True)  # CRITICAL|ELEVATED|WATCH|NOISE
    quality_rules: Mapped[dict] = mapped_column(JSONType, default=dict)  # tolerance bands / null / duplicate rules


class KpiContractRight(Base, IdMixin, TimestampMixin):
    """Contract satellite: decision rights per role (who may approve what, up to which limit)."""

    __tablename__ = "kpi_contract_rights"

    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    role: Mapped[str] = mapped_column(String(40))  # EXECUTIVE | SUPPLY_CHAIN | KPI_OWNER | ANALYST
    action_class: Mapped[str] = mapped_column(String(60))  # supply_switch | expedite | promotion | ...
    may_recommend: Mapped[bool] = mapped_column(Boolean, default=True)
    may_simulate: Mapped[bool] = mapped_column(Boolean, default=True)
    may_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    approve_limit_rs: Mapped[float] = mapped_column(Float, default=0.0)
    escalate_to_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scope: Mapped[dict] = mapped_column(JSONType, default=dict)  # e.g. {"region": "NE"}


class KpiContractEntitlement(Base, IdMixin, TimestampMixin):
    """Contract satellite: row/column/domain scopes per role — enforced server-side (S6 masks)."""

    __tablename__ = "kpi_contract_entitlements"

    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    role: Mapped[str] = mapped_column(String(40))
    row_scope: Mapped[dict] = mapped_column(JSONType, default=dict)  # {"region": ["NE"]}
    masked_columns: Mapped[list] = mapped_column(JSONType, default=list)  # ["unit_cost_rs", "marketing_roi"]
    domains: Mapped[list] = mapped_column(JSONType, default=list)  # ["finance", "marketing"]


class KpiRelation(Base, OrgMixin):
    """Typed edge between contracts — powers second-order impact propagation (S8)."""

    __tablename__ = "kpi_relations"

    a_contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    b_contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    relation: Mapped[str] = mapped_column(String(20))  # IMPACTS | PRECEDES | COMPONENT
    elasticity: Mapped[float] = mapped_column(Float, default=0.0)  # effect multiplier per edge
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    lag_days: Mapped[int] = mapped_column(Integer, default=0)


class ContractVersion(Base, IdMixin):
    """Full snapshot per contract edit — auditable, reversible, reproducible."""

    __tablename__ = "contract_versions"

    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpi_contracts.id"), index=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONType)
    changed_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    change_reason: Mapped[str] = mapped_column(String(400), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
