"""AC1 — the KPI is governed BEFORE any reasoning.

The gate `assert_contract_ready` is the enforcement point investigations will
call (from S2 onward). It must refuse: no contract, non-ACTIVE contract,
blocking gaps.
"""
from __future__ import annotations

import pytest

from app.db import SessionLocal
from app.domains.contracts.service import assert_contract_ready
from app.errors import AppError
from app.models.kpi import Kpi


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def test_gate_passes_for_governed_hero_kpi(db):
    kpi = db.query(Kpi).filter(Kpi.code == "revenue_ne").first()
    contract = assert_contract_ready(db, kpi.organization_id, kpi.id)
    assert contract.status == "ACTIVE"
    assert contract.version >= 1


def test_gate_refuses_kpi_without_contract(db):
    kpi = db.query(Kpi).filter(Kpi.code == "revenue_ne").first()
    ghost = Kpi(organization_id=kpi.organization_id, code="ghost_kpi", name="Ghost",
                category="REVENUE", region="NE", unit="INR_M")
    db.add(ghost)
    db.flush()
    with pytest.raises(AppError) as exc:
        assert_contract_ready(db, ghost.organization_id, ghost.id)
    assert exc.value.code == "CONTRACT_REQUIRED"
    assert "governed" in exc.value.message.lower()
    db.delete(ghost)
    db.flush()


def test_gate_refuses_non_governed_contract_status(db):
    """DRAFT contracts are ungoverned → refused. CONFLICTED is governed-but-degraded → allowed (capped)."""
    from app.models.contract import KpiContract

    kpi = db.query(Kpi).filter(Kpi.code == "revenue_ne").first()
    contract = (
        db.query(KpiContract)
        .filter(KpiContract.kpi_id == kpi.id)
        .order_by(KpiContract.version.desc())
        .first()
    )
    original = contract.status
    for status in ("DRAFT", "UNDER_REVIEW"):
        contract.status = status
        db.flush()
        try:
            with pytest.raises(AppError) as exc:
                assert_contract_ready(db, kpi.organization_id, kpi.id)
            assert exc.value.code == "CONTRACT_NOT_ACTIVE"
        finally:
            pass
    contract.status = "CONFLICTED"
    db.flush()
    try:
        assert_contract_ready(db, kpi.organization_id, kpi.id)  # proceeds, certainty capped later
    finally:
        contract.status = original
        db.flush()
