"""Gap report: designed degradation is loud and honest (spec §7.3)."""
from __future__ import annotations

import pytest

from app.db import SessionLocal
from app.domains.contracts.service import gap_report
from app.models.contract import KpiContract, KpiContractSource, KpiContractDriver, KpiContractThreshold, KpiContractRight
from app.models.kpi import Kpi


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _make_contract(db, **kw) -> tuple[KpiContract, Kpi]:
    org_id = db.query(Kpi).first().organization_id
    kpi = Kpi(organization_id=org_id, code=f"test_{kw.get('suffix', 'x')}", name="T", category="REVENUE",
              region="NE", unit="INR_M")
    db.add(kpi)
    db.flush()
    contract = KpiContract(
        organization_id=org_id, kpi_id=kpi.id, name="T", business_definition="T", unit="INR_M",
        status="DRAFT", version=1,
    )
    db.add(contract)
    db.flush()
    return contract, kpi


def test_no_sources_gap_blocks(db):
    contract, _ = _make_contract(db, suffix="nosrc")
    gaps = gap_report(db, contract)
    codes = {g["code"] for g in gaps}
    assert "NO_SOURCES" in codes
    no_src = next(g for g in gaps if g["code"] == "NO_SOURCES")
    assert no_src["severity"] == "BLOCKING"
    assert "reconciliation" in no_src["effect"].lower()


def test_no_thresholds_gap_means_statistical_only_materiality(db):
    contract, _ = _make_contract(db, suffix="noth")
    gaps = gap_report(db, contract)
    th = next(g for g in gaps if g["code"] == "NO_THRESHOLDS")
    assert "statistical-only" in th["effect"]


def test_no_drivers_shrinks_hypothesis_space(db):
    contract, _ = _make_contract(db, suffix="nodrv")
    gaps = gap_report(db, contract)
    drv = next(g for g in gaps if g["code"] == "NO_DRIVERS")
    assert "decomposition-derived" in drv["effect"]


def test_no_rights_means_no_action_recommendations(db):
    contract, _ = _make_contract(db, suffix="noright")
    gaps = gap_report(db, contract)
    rights = next(g for g in gaps if g["code"] == "NO_RIGHTS")
    assert "No action recommendations" in rights["effect"]


def test_no_owner_unroutable(db):
    contract, _ = _make_contract(db, suffix="noown")
    contract.owner_user_id = None
    contract.owner_role = None
    gaps = gap_report(db, contract)
    owner = next(g for g in gaps if g["code"] == "NO_OWNER")
    assert "unroutable" in owner["effect"].lower() or "cannot be routed" in owner["effect"]


def test_conflicted_status_raises_formula_conflict_gap(db):
    contract, _ = _make_contract(db, suffix="conf")
    contract.status = "CONFLICTED"
    gaps = gap_report(db, contract)
    # FORMULA_CONFLICT degrades certainty (hard cap ACT_WITH_CAUTION) but does not
    # block investigation — strong evidence on a conflicted picture still reasons.
    gap = next(g for g in gaps if g["code"] == "FORMULA_CONFLICT")
    assert gap["severity"] == "MAJOR"
    assert "capped" in gap["effect"].lower()


def test_healthy_hero_contract_has_no_gaps(client, auth_headers):
    rows = client.get("/api/v1/contracts", headers=auth_headers("owner")).json()["data"]
    revenue = next(c for c in rows if c["kpi_code"] == "revenue_ne")
    resp = client.get(f"/api/v1/contracts/{revenue['id']}/gaps", headers=auth_headers("owner"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    blocking = [g for g in data["gaps"] if g["severity"] == "BLOCKING"]
    assert blocking == []  # the governed hero contract is gap-free (blocking-wise)
    # NO_GUARDRAILS applies only when the scenario has no guardrail config — hero has 4.
    assert all(g["code"] != "NO_GUARDRAILS" for g in data["gaps"])


def test_millet_contract_flags_cold_start(client, auth_headers):
    rows = client.get("/api/v1/kpis", headers=auth_headers("owner")).json()["data"]
    millet = next(k for k in rows if k["code"] == "millet_noodles_revenue")
    assert millet["contract"]["chip"] == "COLD START"
