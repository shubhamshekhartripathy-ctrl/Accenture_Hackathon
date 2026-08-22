from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OrgMixin


class Kpi(Base, OrgMixin):
    """The KPI identity object. Contracts govern it; observations feed it (S2)."""

    __tablename__ = "kpis"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_kpi_org_code"),)

    code: Mapped[str] = mapped_column(String(60))  # revenue_ne, osa_ne, inventory_cover_ne, ...
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40))  # REVENUE | AVAILABILITY | INVENTORY | MARKETING | SUPPLIER | LAUNCH
    region: Mapped[str] = mapped_column(String(20))  # NE | SOUTH | NATIONAL
    unit: Mapped[str] = mapped_column(String(20))  # INR_M | PCT | DAYS | RATIO | INDEX
    description: Mapped[str] = mapped_column(String(500), default="")
    scenario_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # owning scenario template
