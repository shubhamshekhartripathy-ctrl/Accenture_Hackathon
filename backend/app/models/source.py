from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import JSONType
from .base import Base, OrgMixin


class SourceSystem(Base, OrgMixin):
    """A declared enterprise source feed with its cadence/grain heterogeneity."""

    __tablename__ = "source_systems"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_source_org_code"),)

    code: Mapped[str] = mapped_column(String(40))  # erp | gl | pos | wms | scorecard
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(60))  # ERP | FinanceClose | RetailAudit | WMS | SupplierScorecard
    cadence: Mapped[str] = mapped_column(String(20))  # daily | weekly | monthly
    grain: Mapped[str] = mapped_column(String(120))  # e.g. SKU x DC
    publish_lag_days: Mapped[int] = mapped_column(Integer, default=0)
    # PUBLIC | INTERNAL | SENSITIVE | RESTRICTED — feeds the AI policy engine (S10)
    data_classification: Mapped[str] = mapped_column(String(20), default="INTERNAL")
    lineage_note: Mapped[str] = mapped_column(String(400), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
