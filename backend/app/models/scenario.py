from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import JSONType
from .base import Base, IdMixin, OrgMixin

SCENARIO_STATUSES = ("DRAFT", "ACTIVE", "DEPRECATED")


class ScenarioTemplate(Base, OrgMixin):  # OrgMixin already provides id + timestamps + tenant
    """A configured business problem running on the ONE shared engine (AC18).

    A scenario changes data and configuration — never code paths. Provisioning
    is idempotent; POST /scenarios/{id}/start validates (every KPI has an
    ACTIVE contract, sources declared, guardrails exist — gaps listed loudly)
    and opens the workspace.
    """

    __tablename__ = "scenario_templates"

    scenario_id: Mapped[str] = mapped_column(String(80), unique=True)  # apex_revenue_decline_ne | apex_inventory_cover | apex_millet_launch
    industry: Mapped[str] = mapped_column(String(80))  # FMCG
    business_problem: Mapped[str] = mapped_column(String(300))
    primary_kpi_code: Mapped[str] = mapped_column(String(60))
    related_kpi_codes: Mapped[list] = mapped_column(JSONType, default=list)
    region: Mapped[str] = mapped_column(String(20), default="NE")
    scenario_description: Mapped[str] = mapped_column(Text, default="")
    source_configuration: Mapped[dict] = mapped_column(JSONType, default=dict)
    driver_configuration: Mapped[dict] = mapped_column(JSONType, default=dict)
    threshold_configuration: Mapped[dict] = mapped_column(JSONType, default=dict)
    materiality_configuration: Mapped[dict] = mapped_column(JSONType, default=dict)
    decision_options: Mapped[list] = mapped_column(JSONType, default=list)
    guardrail_configuration: Mapped[dict] = mapped_column(JSONType, default=dict)
    persona_configuration: Mapped[dict] = mapped_column(JSONType, default=dict)
    entitlement_configuration: Mapped[dict] = mapped_column(JSONType, default=dict)
    dataset_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expected_outcome_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    demo_priority: Mapped[int] = mapped_column(Integer, default=99)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
