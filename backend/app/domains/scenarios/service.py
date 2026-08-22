"""Scenario domain — one engine, many business problems (AC18).

ScenarioTemplates are configurations over the shared engine. `start` validates
loudly (every KPI has an ACTIVE contract; sources declared; guardrails exist),
provisions idempotently, and opens the workspace. Zero per-scenario code paths.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...errors import AppError
from ...models.contract import KpiContract
from ...models.kpi import Kpi
from ...models.scenario import ScenarioTemplate, SCENARIO_STATUSES
from ...models.source import SourceSystem
from ...services.audit import record as audit
from ..contracts.service import gap_report, serialize as serialize_contract


def get_template(db: Session, organization_id: str, scenario_id: str) -> ScenarioTemplate:
    template = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.organization_id == organization_id,
            ScenarioTemplate.scenario_id == scenario_id,
        )
        .first()
    )
    if template is None:
        raise AppError("NOT_FOUND", "Scenario not found", 404)
    return template


def list_templates(db: Session, organization_id: str) -> list[ScenarioTemplate]:
    return (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.organization_id == organization_id)
        .order_by(ScenarioTemplate.demo_priority)
        .all()
    )


def card(template: ScenarioTemplate) -> dict[str, Any]:
    sources = template.source_configuration.get("sources", [])
    return {
        "scenario_id": template.scenario_id,
        "industry": template.industry,
        "business_problem": template.business_problem,
        "primary_kpi": template.primary_kpi_code,
        "related_kpis": template.related_kpi_codes,
        "region": template.region,
        "sources": [s.get("code") for s in sources],
        "demo_priority": template.demo_priority,
        "status": template.status,
        "scenario_description": template.scenario_description,
        "engine": "reasonflow-core",  # every card declares the SAME engine (AC18 story)
        "version": template.version,
    }


def detail(template: ScenarioTemplate) -> dict[str, Any]:
    data = card(template)
    data.update(
        {
            "source_configuration": template.source_configuration,
            "driver_configuration": template.driver_configuration,
            "threshold_configuration": template.threshold_configuration,
            "materiality_configuration": template.materiality_configuration,
            "decision_options": template.decision_options,
            "guardrail_configuration": template.guardrail_configuration,
            "persona_configuration": template.persona_configuration,
            "entitlement_configuration": template.entitlement_configuration,
            "dataset_ref": template.dataset_ref,
            "expected_outcome_ref": template.expected_outcome_ref,
        }
    )
    return data


def validate_scenario(db: Session, organization_id: str, template: ScenarioTemplate) -> dict[str, Any]:
    """Loud validation. Nothing is half-provisioned: a gap list comes back with valid=False."""
    gaps: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    kpi_codes = [template.primary_kpi_code] + list(template.related_kpi_codes or [])

    for code in kpi_codes:
        kpi = db.query(Kpi).filter(Kpi.organization_id == organization_id, Kpi.code == code).first()
        if kpi is None:
            gaps.append({"code": "KPI_MISSING", "kpi": code, "message": f"KPI {code} does not exist in this tenant"})
            continue
        contract = (
            db.query(KpiContract)
            .filter(KpiContract.organization_id == organization_id, KpiContract.kpi_id == kpi.id)
            .order_by(KpiContract.version.desc())
            .first()
        )
        if contract is None:
            gaps.append({"code": "CONTRACT_MISSING", "kpi": code, "message": f"KPI {code} has no contract — governance before reasoning (AC1)"})
        elif contract.status not in ("ACTIVE", "CONFLICTED"):
            gaps.append({"code": "CONTRACT_NOT_ACTIVE", "kpi": code, "message": f"KPI {code} contract status is {contract.status}"})
        elif contract.status == "CONFLICTED":
            # Loud but non-blocking: the scenario runs; certainty is capped downstream.
            warnings.append({
                "code": "CONTRACT_CONFLICTED", "kpi": code,
                "message": f"KPI {code} contract is CONFLICTED — reconciliation active, certainty will be capped",
            })
        else:
            contract_gaps = [g for g in gap_report(db, contract) if g["severity"] == "BLOCKING"]
            for g in contract_gaps:
                gaps.append({"code": g["code"], "kpi": code, "message": g["effect"]})

    for src in (template.source_configuration or {}).get("sources", []):
        system = db.query(SourceSystem).filter(
            SourceSystem.organization_id == organization_id, SourceSystem.code == src.get("code")
        ).first()
        if system is None:
            gaps.append({"code": "SOURCE_MISSING", "source": src.get("code"), "message": f"Source {src.get('code')} is declared but not provisioned"})

    guardrails = (template.guardrail_configuration or {}).get("guardrails")
    if not guardrails:
        gaps.append({"code": "GUARDRAILS_MISSING", "message": "No guardrail configuration — decision options would degrade to 'no guardrail coverage'"})

    if template.status not in SCENARIO_STATUSES:
        gaps.append({"code": "SCENARIO_STATUS_INVALID", "message": f"Scenario status {template.status}"})
    elif template.status == "DEPRECATED":
        gaps.append({"code": "SCENARIO_DEPRECATED", "message": "Scenario is deprecated"})

    return {"valid": len(gaps) == 0, "gaps": gaps, "warnings": warnings}


def workspace(db: Session, organization_id: str, template: ScenarioTemplate) -> dict[str, Any]:
    """Assemble the opened workspace: scenario, its contracts (serialized), gaps."""
    validation = validate_scenario(db, organization_id, template)
    kpi_codes = [template.primary_kpi_code] + list(template.related_kpi_codes or [])
    contracts = []
    for code in kpi_codes:
        kpi = db.query(Kpi).filter(Kpi.organization_id == organization_id, Kpi.code == code).first()
        if kpi is None:
            continue
        contract = (
            db.query(KpiContract)
            .filter(KpiContract.organization_id == organization_id, KpiContract.kpi_id == kpi.id)
            .order_by(KpiContract.version.desc())
            .first()
        )
        if contract is not None:
            contracts.append(serialize_contract(db, contract))
    return {
        "scenario": card(template),
        "engine": "reasonflow-core",
        "contracts": contracts,
        "validation": validation,
    }


def start_scenario(
    db: Session,
    organization_id: str,
    template: ScenarioTemplate,
    actor_user_id: str,
    actor_role: str,
) -> dict[str, Any]:
    """Validate -> provision (idempotent) -> open workspace. Audit-logged.

    Idempotency: starting an already-open scenario returns the same workspace
    state without duplicating anything.
    """
    from ...models.org import Organization

    validation = validate_scenario(db, organization_id, template)
    if not validation["valid"]:
        audit(
            db, organization_id, "scenario.start_denied", "scenario_template", template.scenario_id,
            actor_user_id, actor_role, outcome="denied", details={"gaps": validation["gaps"]},
        )
        raise AppError(
            "SCENARIO_INVALID",
            "Scenario cannot start — configuration gaps must be resolved (nothing was half-provisioned)",
            409,
            details=validation,
        )
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if org is None:
        raise AppError("NOT_FOUND", "Organization not found", 404)
    org.active_scenario_id = template.scenario_id
    audit(
        db, organization_id, "scenario.start", "scenario_template", template.scenario_id,
        actor_user_id, actor_role, details={"workspace_contracts": len(template.related_kpi_codes) + 1},
    )
    return workspace(db, organization_id, template)
