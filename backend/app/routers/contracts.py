"""Contracts router — CRUD, activation, versions, gap report (arch P)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..domains.contracts import service as contracts
from ..domains.scenarios import service as scenarios
from ..envelope import ok
from ..errors import AppError
from ..models.org import User
from ..security.deps import get_current_user, require_roles

router = APIRouter(prefix="/contracts", tags=["contracts"])

# Contract edits/activation are owner/governance operations.
_edit_guard = require_roles("KPI_OWNER", "ADMIN")
_read_guard = require_roles("KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN")


@router.get("")
def list_contracts(
    request: Request,
    status: str | None = None,
    scenario_id: str | None = None,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    rows = contracts.list_contracts(db, user.organization_id, status=status, scenario_id=scenario_id)
    return ok(request, [contracts.serialize(db, c) for c in rows])


@router.post("")
def create_contract(
    request: Request,
    body: dict[str, Any],
    user: User = Depends(_edit_guard),
    db: Session = Depends(get_db),
):
    from ..models.contract import KpiContract

    required = {"kpi_id", "name", "business_definition", "unit"}
    missing = required - set(body)
    if missing:
        raise AppError("VALIDATION", f"Missing required fields: {sorted(missing)}", 422)
    from ..models.kpi import Kpi

    kpi = db.query(Kpi).filter(Kpi.organization_id == user.organization_id, Kpi.id == body["kpi_id"]).first()
    if kpi is None:
        raise AppError("NOT_FOUND", "KPI not found", 404)
    existing = (
        db.query(KpiContract)
        .filter(KpiContract.organization_id == user.organization_id, KpiContract.kpi_id == kpi.id)
        .first()
    )
    if existing is not None:
        # One governed contract per KPI (one live row); edits version it — never fork it.
        raise AppError(
            "CONTRACT_EXISTS",
            f"KPI {kpi.code} already has a contract (v{existing.version}); edit it to create a new version",
            409,
            details={"contract_id": existing.id, "version": existing.version},
        )
    contract = KpiContract(
        organization_id=user.organization_id,
        kpi_id=body["kpi_id"],
        scenario_id=body.get("scenario_id"),
        name=body["name"],
        business_definition=body["business_definition"],
        formula_sql=body.get("formula_sql", ""),
        formula_note=body.get("formula_note", ""),
        unit=body["unit"],
        business_function=body.get("business_function", ""),
        owner_user_id=body.get("owner_user_id") or user.id,
        owner_role=body.get("owner_role") or user.role,
        calendar_rule=body.get("calendar_rule", ""),
        hierarchy_config=body.get("hierarchy_config", {}),
        status="DRAFT",
        version=1,
    )
    db.add(contract)
    db.flush()
    from ..services.audit import record as audit

    audit(db, user.organization_id, "contract.create", "kpi_contract", contract.id, user.id, user.role)
    return ok(request, contracts.serialize(db, contract, detail=True))


@router.get("/{contract_id}")
def get_contract(
    request: Request,
    contract_id: str,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    contract = contracts.get_contract(db, user.organization_id, contract_id)
    return ok(request, contracts.serialize(db, contract, detail=True))


@router.patch("/{contract_id}")
def patch_contract(
    request: Request,
    contract_id: str,
    body: dict[str, Any],
    user: User = Depends(_edit_guard),
    db: Session = Depends(get_db),
):
    contract = contracts.get_contract(db, user.organization_id, contract_id)
    contracts.patch_contract(db, contract, body, user.id, user.role)
    return ok(request, contracts.serialize(db, contract, detail=True))


@router.post("/{contract_id}/activate")
def activate_contract(
    request: Request,
    contract_id: str,
    user: User = Depends(_edit_guard),
    db: Session = Depends(get_db),
):
    contract = contracts.get_contract(db, user.organization_id, contract_id)
    contracts.transition_status(db, contract, "ACTIVE", user.id, user.role, reason="activated via API")
    return ok(request, contracts.serialize(db, contract, detail=True))


class StatusBody(BaseModel):
    status: str
    reason: str = ""


@router.post("/{contract_id}/status")
def set_status(
    request: Request,
    contract_id: str,
    body: StatusBody,
    user: User = Depends(_edit_guard),
    db: Session = Depends(get_db),
):
    contract = contracts.get_contract(db, user.organization_id, contract_id)
    contracts.transition_status(db, contract, body.status, user.id, user.role, reason=body.reason)
    return ok(request, contracts.serialize(db, contract, detail=True))


@router.get("/{contract_id}/versions")
def versions(
    request: Request,
    contract_id: str,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    contract = contracts.get_contract(db, user.organization_id, contract_id)
    data = contracts.serialize(db, contract, detail=True)
    return ok(request, data["versions"])


@router.get("/{contract_id}/gaps")
def gaps(
    request: Request,
    contract_id: str,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    contract = contracts.get_contract(db, user.organization_id, contract_id)
    report = contracts.gap_report(db, contract)
    return ok(request, {"contract_id": contract.id, "status": contract.status, "gaps": report})
