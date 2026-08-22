"""KPI Contract domain — the governed object at the center of the product.

Implements (spec §7, arch D/E):
  * field-complete contract + satellites (sources, drivers, thresholds, rights,
    entitlements, relations) with versioned snapshots,
  * the status machine DRAFT -> ACTIVE -> CONFLICTED -> UNDER_REVIEW -> ACTIVE,
  * the loud gap report (designed degradation — never fabricated),
  * the AC1 gate `assert_contract_ready` — no reasoning without a valid contract.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, joinedload

from ...errors import AppError
from ...models.contract import (
    CONTRACT_STATUSES,
    ContractVersion,
    KpiContract,
    KpiContractDriver,
    KpiContractEntitlement,
    KpiContractRight,
    KpiContractSource,
    KpiContractThreshold,
)
from ...models.kpi import Kpi
from ...services.audit import record as audit

# ---------------------------------------------------------------------------
# Status machine
# ---------------------------------------------------------------------------

# Explicit allowed transitions. System-set transitions (ACTIVE->CONFLICTED by
# reconcile) are guarded by `system=True` callers in later slices.
ALLOWED_TRANSITIONS: dict[tuple[str, str], str] = {
    ("DRAFT", "ACTIVE"): "activate",
    ("ACTIVE", "CONFLICTED"): "reconcile_definition_conflict",
    ("CONFLICTED", "ACTIVE"): "conflict_resolved",
    ("CONFLICTED", "UNDER_REVIEW"): "review_opened",
    ("UNDER_REVIEW", "ACTIVE"): "review_closed",
    ("ACTIVE", "UNDER_REVIEW"): "review_opened",
    ("UNDER_REVIEW", "ACTIVE"): "review_closed",  # duplicate kept explicit for readability
    ("DRAFT", "UNDER_REVIEW"): "review_opened",
}


def transition_status(
    db: Session,
    contract: KpiContract,
    new_status: str,
    actor_user_id: str | None,
    actor_role: str | None = None,
    system: bool = False,
    reason: str = "",
) -> KpiContract:
    if new_status not in CONTRACT_STATUSES:
        raise AppError("VALIDATION", f"Unknown status {new_status}", 422)
    key = (contract.status, new_status)
    if key not in ALLOWED_TRANSITIONS:
        raise AppError(
            "CONFLICT",
            f"Illegal contract transition {contract.status} -> {new_status}",
            409,
            details={"from": contract.status, "to": new_status},
        )
    if contract.status == "DRAFT" and new_status == "ACTIVE":
        gaps = gap_report(db, contract)
        blocking = [g for g in gaps if g["severity"] == "BLOCKING"]
        if blocking:
            raise AppError(
                "VALIDATION",
                "Contract cannot be activated: governance gaps must be resolved first",
                422,
                details={"gaps": blocking},
            )
    contract.status = new_status
    _bump_version(db, contract, actor_user_id, reason or ALLOWED_TRANSITIONS.get(key, "status_change"), system=system)
    audit(
        db,
        contract.organization_id,
        "contract.status_change",
        "kpi_contract",
        contract.id,
        actor_user_id,
        actor_role,
        details={"from": key[0], "to": new_status, "reason": reason},
    )
    return contract


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def snapshot_of(contract: KpiContract) -> dict[str, Any]:
    return {
        "name": contract.name,
        "business_definition": contract.business_definition,
        "formula_sql": contract.formula_sql,
        "formula_note": contract.formula_note,
        "unit": contract.unit,
        "business_function": contract.business_function,
        "owner_user_id": contract.owner_user_id,
        "owner_role": contract.owner_role,
        "status": contract.status,
        "calendar_rule": contract.calendar_rule,
        "hierarchy_config": contract.hierarchy_config,
        "scenario_id": contract.scenario_id,
        "sources": [
            {
                "source_system_id": s.source_system_id,
                "lineage_path": s.lineage_path,
                "is_authoritative": s.is_authoritative,
                "expected_cadence": s.expected_cadence,
                "expected_grain": s.expected_grain,
                "tolerance_pct": s.tolerance_pct,
            }
            for s in contract.sources
        ],
        "drivers": [
            {
                "driver_code": d.driver_code,
                "name": d.name,
                "direction": d.direction,
                "prior_weight": d.prior_weight,
                "source": d.source,
                "hypothesis_class": d.hypothesis_class,
                "rank": d.rank,
            }
            for d in contract.drivers
        ],
        "threshold": _threshold_dict(contract.threshold),
        "rights": [
            {
                "role": r.role,
                "action_class": r.action_class,
                "may_recommend": r.may_recommend,
                "may_simulate": r.may_simulate,
                "may_approve": r.may_approve,
                "approve_limit_rs": r.approve_limit_rs,
                "escalate_to_role": r.escalate_to_role,
            }
            for r in contract.rights
        ],
        "entitlements": [
            {"role": e.role, "row_scope": e.row_scope, "masked_columns": e.masked_columns, "domains": e.domains}
            for e in contract.entitlements
        ],
    }


def _threshold_dict(t: KpiContractThreshold | None) -> dict | None:
    if t is None:
        return None
    return {
        "expected_lo": t.expected_lo,
        "expected_hi": t.expected_hi,
        "warning_deviation_pct": t.warning_deviation_pct,
        "critical_deviation_pct": t.critical_deviation_pct,
        "exposure_rs_per_point": t.exposure_rs_per_point,
        "margin_weight": t.margin_weight,
        "strategic_weight": t.strategic_weight,
        "min_history": t.min_history,
        "cold_start_flag": t.cold_start_flag,
        "quality_rules": t.quality_rules,
    }


def _bump_version(
    db: Session,
    contract: KpiContract,
    actor_user_id: str | None,
    reason: str,
    system: bool = False,
) -> None:
    """Write the snapshot of the CURRENT state under the current version, then increment.

    Snapshot semantics: version N snapshot = the contract as it stood while it
    was version N. Investigations pin `contract_version` and can reproduce the
    governing definition from the snapshot.
    """
    snap = ContractVersion(
        contract_id=contract.id,
        organization_id=contract.organization_id,
        version=contract.version,
        snapshot=snapshot_of(contract),
        changed_by_user_id=actor_user_id,
        change_reason=reason,
    )
    db.add(snap)
    db.flush()
    contract.version += 1


# ---------------------------------------------------------------------------
# Gap report — designed degradation, loud and honest (spec §7.3)
# ---------------------------------------------------------------------------

GAP_EFFECTS = {
    "NO_THRESHOLDS": "TRIAGE will run statistical-only with low confidence — the movement can never be promoted to CRITICAL on business impact.",
    "NO_DRIVERS": "Hypothesis space shrinks to decomposition-derived drivers only; EXPLAIN confidence is capped.",
    "NO_RIGHTS": "No action recommendations will be generated — decision rights are undefined; KPI owner action required.",
    "NO_OWNER": "Conflicts and clarification requests cannot be routed — cases risk ABSTAIN with 'owner unassigned' as the blocking reason.",
    "FORMULA_CONFLICT": "Two sources define this KPI differently — contract status is CONFLICTED and certainty is capped.",
    "NO_GUARDRAILS": "Decision options downgrade to 'no guardrail coverage' — approval requires escalation.",
    "NO_SOURCES": "No source lineage declared — reconciliation cannot verify the picture; investigation blocked.",
}


def gap_report(db: Session, contract: KpiContract) -> list[dict]:
    gaps: list[dict] = []
    if not contract.sources:
        gaps.append(_gap("NO_SOURCES", "BLOCKING"))
    if contract.threshold is None:
        gaps.append(_gap("NO_THRESHOLDS", "MAJOR"))
    elif (
        contract.threshold.expected_lo is None
        and contract.threshold.expected_hi is None
        and contract.threshold.critical_deviation_pct is None
    ):
        gaps.append(_gap("NO_THRESHOLDS", "MAJOR"))
    if not contract.drivers:
        gaps.append(_gap("NO_DRIVERS", "MAJOR"))
    if not contract.rights:
        gaps.append(_gap("NO_RIGHTS", "MAJOR"))
    if not contract.owner_user_id and not contract.owner_role:
        gaps.append(_gap("NO_OWNER", "MAJOR"))
    if contract.status == "CONFLICTED" or _formula_conflict_present(contract):
        # Degrades certainty (hard cap ACT_WITH_CAUTION per arch F/I) — it does NOT
        # block investigation: strong evidence on a conflicted picture still reasons,
        # held back. Only the owner resolving the conflict restores full confidence.
        gaps.append(_gap("FORMULA_CONFLICT", "MAJOR"))
    if not _scenario_guardrails_present(db, contract):
        gaps.append(_gap("NO_GUARDRAILS", "MAJOR"))
    return gaps


def _gap(code: str, severity: str) -> dict:
    return {
        "code": code,
        "severity": severity,
        "effect": GAP_EFFECTS[code],
        "banner": _banner_text(code),
    }


def _banner_text(code: str) -> str:
    return {
        "NO_THRESHOLDS": "Materiality statistical-only — thresholds undefined on the contract.",
        "NO_DRIVERS": "Hypothesis space shrunk to decomposition-derived drivers; confidence capped.",
        "NO_RIGHTS": "Decision rights undefined; KPI owner action required — no action recommendations shown.",
        "NO_OWNER": "Owner unassigned — conflicts and clarifications are unroutable.",
        "FORMULA_CONFLICT": "Formula conflict — contract CONFLICTED, certainty capped.",
        "NO_GUARDRAILS": "No guardrail coverage — approval requires escalation.",
        "NO_SOURCES": "No declared sources — reasoning blocked until lineage exists.",
    }[code]


def _formula_conflict_present(contract: KpiContract) -> bool:
    """S2's reconcile sets status CONFLICTED; here we detect seed-level contradictions:
    multiple authoritative sources with conflicting formulas."""
    authoritative = [s for s in contract.sources if s.is_authoritative]
    return len(authoritative) > 1


def _scenario_guardrails_present(db: Session, contract: KpiContract) -> bool:
    if not contract.scenario_id:
        return False
    from ...models.scenario import ScenarioTemplate

    template = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.organization_id == contract.organization_id,
            ScenarioTemplate.scenario_id == contract.scenario_id,
        )
        .first()
    )
    if template is None:
        return False
    guardrails = template.guardrail_configuration or {}
    kpi_code = _kpi_code(db, contract)
    applies = guardrails.get("applies_to_kpis", [])
    return bool(guardrails.get("guardrails")) and (not applies or kpi_code in applies or "*" in applies)


def _kpi_code(db: Session, contract: KpiContract) -> str | None:
    kpi = db.query(Kpi).filter(Kpi.id == contract.kpi_id).first()
    return kpi.code if kpi else None


# ---------------------------------------------------------------------------
# AC1 gate — the KPI is governed BEFORE reasoning
# ---------------------------------------------------------------------------

def assert_contract_ready(db: Session, organization_id: str, kpi_id: str) -> KpiContract:
    """Raise unless the KPI has an ACTIVE contract with no BLOCKING gaps.

    This is the enforcement point mandated by AC1 — investigations (S2+) call
    it before any reasoning stage runs.
    """
    contract = (
        db.query(KpiContract)
        .filter(
            KpiContract.organization_id == organization_id,
            KpiContract.kpi_id == kpi_id,
        )
        .order_by(KpiContract.version.desc())
        .first()
    )
    if contract is None:
        raise AppError(
            "CONTRACT_REQUIRED",
            "No KPI contract exists for this KPI — the KPI must be governed before any reasoning can run (AC1)",
            409,
            details={"kpi_id": kpi_id, "gaps": [_gap("NO_SOURCES", "BLOCKING"), _gap("NO_OWNER", "MAJOR")]},
        )
    if contract.status not in ("ACTIVE", "CONFLICTED"):
        raise AppError(
            "CONTRACT_NOT_ACTIVE",
            f"KPI contract status is {contract.status} — reasoning requires a governed (ACTIVE or "
            "CONFLICTED) contract; CONFLICTED proceeds with certainty capped (AC1)",
            409,
            details={"status": contract.status},
        )
    blocking = [g for g in gap_report(db, contract) if g["severity"] == "BLOCKING"]
    if blocking:
        raise AppError(
            "CONTRACT_GAPS_BLOCKING",
            "Contract has blocking governance gaps — resolve them before investigating",
            409,
            details={"gaps": blocking},
        )
    return contract


def get_active_contract(db: Session, organization_id: str, kpi_id: str) -> KpiContract | None:
    """The governed live contract for a KPI. CONFLICTED counts as live-but-degraded
    (S2 semantics: reasoning proceeds with certainty capped), so the Case File and
    investigations can reference it; DRAFT/UNDER_REVIEW are not governed yet."""
    return (
        db.query(KpiContract)
        .filter(
            KpiContract.organization_id == organization_id,
            KpiContract.kpi_id == kpi_id,
            KpiContract.status.in_(["ACTIVE", "CONFLICTED"]),
        )
        .order_by(KpiContract.version.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Serialization (masking lands in S6; structure prepared)
# ---------------------------------------------------------------------------

def serialize(db: Session, contract: KpiContract, detail: bool = False) -> dict:
    kpi = db.query(Kpi).filter(Kpi.id == contract.kpi_id).first()
    owner_name = None
    if contract.owner_user_id:
        from ...models.org import User

        owner = db.query(User).filter(User.id == contract.owner_user_id).first()
        owner_name = owner.full_name if owner else None
    data = {
        "id": contract.id,
        "kpi_id": contract.kpi_id,
        "kpi_code": kpi.code if kpi else None,
        "kpi_name": kpi.name if kpi else None,
        "region": kpi.region if kpi else None,
        "category": kpi.category if kpi else None,
        "scenario_id": contract.scenario_id,
        "name": contract.name,
        "business_definition": contract.business_definition,
        "formula_sql": contract.formula_sql,
        "formula_note": contract.formula_note,
        "unit": contract.unit,
        "business_function": contract.business_function,
        "owner_user_id": contract.owner_user_id,
        "owner_name": owner_name,
        "owner_role": contract.owner_role,
        "status": contract.status,
        "calendar_rule": contract.calendar_rule,
        "hierarchy_config": contract.hierarchy_config,
        "version": contract.version,
    }
    if detail:
        data["sources"] = [
            {
                "id": s.id,
                "source_system_id": s.source_system_id,
                "source_code": s.source_system.code if s.source_system else None,
                "source_name": s.source_system.name if s.source_system else None,
                "lineage_path": s.lineage_path,
                "is_authoritative": s.is_authoritative,
                "expected_cadence": s.expected_cadence,
                "expected_grain": s.expected_grain,
                "tolerance_pct": s.tolerance_pct,
                "data_classification": s.source_system.data_classification if s.source_system else "INTERNAL",
            }
            for s in contract.sources
        ]
        data["drivers"] = [
            {
                "id": d.id,
                "driver_code": d.driver_code,
                "name": d.name,
                "direction": d.direction,
                "prior_weight": d.prior_weight,
                "source": d.source,
                "hypothesis_class": d.hypothesis_class,
                "rank": d.rank,
            }
            for d in contract.drivers
        ]
        data["threshold"] = _threshold_dict(contract.threshold)
        data["rights"] = [
            {
                "id": r.id,
                "role": r.role,
                "action_class": r.action_class,
                "may_recommend": r.may_recommend,
                "may_simulate": r.may_simulate,
                "may_approve": r.may_approve,
                "approve_limit_rs": r.approve_limit_rs,
                "escalate_to_role": r.escalate_to_role,
                "scope": r.scope,
            }
            for r in contract.rights
        ]
        data["entitlements"] = [
            {"id": e.id, "role": e.role, "row_scope": e.row_scope, "masked_columns": e.masked_columns, "domains": e.domains}
            for e in contract.entitlements
        ]
        versions = (
            db.query(ContractVersion)
            .filter(
                ContractVersion.contract_id == contract.id,
                ContractVersion.organization_id == contract.organization_id,
            )
            .order_by(ContractVersion.version.desc())
            .all()
        )
        data["versions"] = [
            {
                "version": v.version,
                "change_reason": v.change_reason,
                "changed_by": v.changed_by_user_id,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "status_in_snapshot": (v.snapshot or {}).get("status"),
            }
            for v in versions
        ]
    return data


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

EDITABLE_FIELDS = {
    "name", "business_definition", "formula_sql", "formula_note", "unit",
    "business_function", "owner_user_id", "owner_role", "calendar_rule",
    "hierarchy_config", "scenario_id",
}


def patch_contract(
    db: Session,
    contract: KpiContract,
    changes: dict[str, Any],
    actor_user_id: str,
    actor_role: str,
) -> KpiContract:
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise AppError("VALIDATION", f"Non-editable fields: {sorted(unknown)}", 422)
    if not changes:
        raise AppError("VALIDATION", "Empty patch", 422)
    for field, value in changes.items():
        setattr(contract, field, value)
    _bump_version(db, contract, actor_user_id, "contract_edit")
    audit(
        db,
        contract.organization_id,
        "contract.edit",
        "kpi_contract",
        contract.id,
        actor_user_id,
        actor_role,
        details={"fields": sorted(changes), "new_version": contract.version},
    )
    return contract


def get_contract(db: Session, organization_id: str, contract_id: str) -> KpiContract:
    contract = (
        db.query(KpiContract)
        .options(joinedload(KpiContract.kpi))
        .filter(
            KpiContract.organization_id == organization_id,
            KpiContract.id == contract_id,
        )
        .first()
    )
    if contract is None:
        # Cross-tenant or missing ids are indistinguishable by design.
        raise AppError("NOT_FOUND", "Contract not found", 404)
    return contract


def list_contracts(db: Session, organization_id: str, status: str | None = None, scenario_id: str | None = None) -> list[KpiContract]:
    q = db.query(KpiContract).filter(KpiContract.organization_id == organization_id)
    if status:
        q = q.filter(KpiContract.status == status)
    if scenario_id:
        q = q.filter(KpiContract.scenario_id == scenario_id)
    return q.order_by(KpiContract.created_at).all()
