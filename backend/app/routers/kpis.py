"""KPIs router — the contract portfolio behind /kpis (KPI Intelligence)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..domains.contracts import service as contracts
from ..envelope import ok
from ..models.contract import KpiContract
from ..models.kpi import Kpi
from ..models.org import User
from ..security.deps import require_roles

router = APIRouter(prefix="/kpis", tags=["kpis"])

_read_guard = require_roles("KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN")


@router.get("")
def list_kpis(request: Request, user: User = Depends(_read_guard), db: Session = Depends(get_db)):
    kpis = (
        db.query(Kpi)
        .filter(Kpi.organization_id == user.organization_id)
        .order_by(Kpi.code)
        .all()
    )
    contract_rows = db.query(KpiContract).filter(KpiContract.organization_id == user.organization_id).all()
    by_kpi: dict[str, KpiContract] = {}
    for c in contract_rows:
        current = by_kpi.get(c.kpi_id)
        if current is None or c.version > current.version:
            by_kpi[c.kpi_id] = c
    data = []
    for kpi in kpis:
        contract = by_kpi.get(kpi.id)
        thresholds = contract.threshold if contract else None
        cold_start = bool(thresholds and thresholds.cold_start_flag) if contract else False
        data.append(
            {
                "id": kpi.id,
                "code": kpi.code,
                "name": kpi.name,
                "category": kpi.category,
                "region": kpi.region,
                "unit": kpi.unit,
                "description": kpi.description,
                "scenario_id": kpi.scenario_id,
                "contract": (
                    {
                        "id": contract.id,
                        "name": contract.name,
                        "status": contract.status,
                        "version": contract.version,
                        "owner_user_id": contract.owner_user_id,
                        # COLD START chip is contract-derived, not hardcoded per KPI
                        "chip": "COLD START" if cold_start else contract.status,
                    }
                    if contract
                    else None
                ),
            }
        )
    return ok(request, data)


@router.get("/{kpi_id}")
def get_kpi(
    request: Request,
    kpi_id: str,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    kpi = (
        db.query(Kpi)
        .filter(Kpi.organization_id == user.organization_id, Kpi.id == kpi_id)
        .first()
    )
    if kpi is None:
        from ..errors import AppError

        raise AppError("NOT_FOUND", "KPI not found", 404)
    contract = contracts.get_active_contract(db, user.organization_id, kpi.id)
    return ok(
        request,
        {
            "id": kpi.id,
            "code": kpi.code,
            "name": kpi.name,
            "category": kpi.category,
            "region": kpi.region,
            "unit": kpi.unit,
            "description": kpi.description,
            "scenario_id": kpi.scenario_id,
            "active_contract_id": contract.id if contract else None,
            "active_contract_version": contract.version if contract else None,
        },
    )
