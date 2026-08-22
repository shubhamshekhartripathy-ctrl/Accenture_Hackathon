"""Reconciliation integration — MOMENT 1 locked targets through the real API."""
from __future__ import annotations


def _revenue_contract_id(client, headers) -> str:
    rows = client.get("/api/v1/contracts", headers=headers).json()["data"]
    return next(c["id"] for c in rows if c["kpi_code"] == "revenue_ne")


def test_moment1_locked_targets(client, auth_headers):
    """ERP ₹84.0M vs GL ₹87.0M → typed definition conflict, reliability 0.76, impact −0.12."""
    headers = auth_headers("analyst")
    cid = _revenue_contract_id(client, headers)
    resp = client.post(f"/api/v1/contracts/{cid}/reconcile", headers=headers)
    assert resp.status_code == 200, resp.text
    run = resp.json()["data"]

    assert run["verdict"] == "CONFLICTED"
    assert abs(run["reliability_score"] - 0.76) < 0.005          # locked
    assert abs(run["confidence_cap"] - 0.86) < 0.005             # locked
    definition = [c for c in run["conflicts"] if c["conflict_type"] == "definition"]
    assert definition, "definition conflict must be typed"
    d = definition[0]
    assert abs(d["value_a"] - 84.0) < 0.01 or abs(d["value_b"] - 84.0) < 0.01
    assert abs(d["value_a"] - 87.0) < 0.01 or abs(d["value_b"] - 87.0) < 0.01
    assert d["severity"] == "HIGH"
    assert abs(d["confidence_impact"] + 0.12) < 0.005            # locked −0.12
    assert d["routed_to"]["role"] == "KPI_OWNER"                 # routed to the owner
    assert run["working_value"] == 84.0                          # ERP retained
    assert "deferred" in run["working_justification"].lower()
    assert "not merged" in run["working_justification"].lower() or "no merge" in run["working_justification"].lower()
    stale = [c for c in run["conflicts"] if c["conflict_type"] == "refresh"]
    assert stale and stale[0]["penalty"] == 0.12                 # POS 6–9d bracket


def test_reconcile_flips_contract_conflicted_and_gaps_loudly(client, auth_headers):
    headers = auth_headers("analyst")
    cid = _revenue_contract_id(client, headers)
    client.post(f"/api/v1/contracts/{cid}/reconcile", headers=headers)
    detail = client.get(f"/api/v1/contracts/{cid}", headers=headers).json()["data"]
    assert detail["status"] == "CONFLICTED"
    gaps = client.get(f"/api/v1/contracts/{cid}/gaps", headers=headers).json()["data"]["gaps"]
    assert any(g["code"] == "FORMULA_CONFLICT" for g in gaps)
    # The gap is degrading (MAJOR) but NOT blocking — investigation proceeds capped.
    assert all(g["severity"] != "BLOCKING" for g in gaps if g["code"] == "FORMULA_CONFLICT")


def test_telemetry_rows_are_real(client, auth_headers):
    headers = auth_headers("analyst")
    cid = _revenue_contract_id(client, headers)
    client.post(f"/api/v1/contracts/{cid}/reconcile", headers=headers)
    from app.db import SessionLocal
    from app.models.telemetry import StageTelemetry

    db = SessionLocal()
    try:
        rows = db.query(StageTelemetry).filter(StageTelemetry.stage_code == "reconcile").all()
        assert rows, "reconcile must write a stage telemetry row"
        row = rows[-1]
        assert row.method_label == "rules"
        assert row.llm_used is False                    # numbers without an LLM
        assert row.latency_ms >= 0 and row.ok is True
    finally:
        db.close()


def test_owner_resolution_restores_contract_active(client, auth_headers):
    analyst = auth_headers("analyst")
    owner = auth_headers("owner")
    cid = _revenue_contract_id(client, analyst)
    run = client.post(f"/api/v1/contracts/{cid}/reconcile", headers=analyst).json()["data"]
    definition = next(c for c in run["conflicts"] if c["conflict_type"] == "definition")

    resp = client.post(
        f"/api/v1/conflicts/{definition['id']}/resolve",
        headers=owner,
        json={"note": "Returns accrual confirmed with finance; calendar boundary documented. Working definition stands."},
    )
    assert resp.status_code == 200
    updated = resp.json()["data"]
    resolved = next(c for c in updated["conflicts"] if c["id"] == definition["id"])
    assert resolved["resolution_state"] == "RESOLVED"
    detail = client.get(f"/api/v1/contracts/{cid}", headers=analyst).json()["data"]
    assert detail["status"] == "ACTIVE"
    assert detail["version"] > 1  # audited version bump on the system transition + resolution


def test_analyst_cannot_resolve_conflicts(client, auth_headers):
    analyst = auth_headers("analyst")
    cid = _revenue_contract_id(client, analyst)
    run = client.post(f"/api/v1/contracts/{cid}/reconcile", headers=analyst).json()["data"]
    conflict_id = run["conflicts"][0]["id"]
    resp = client.post(
        f"/api/v1/conflicts/{conflict_id}/resolve", headers=analyst,
        json={"note": "attempt"},
    )
    assert resp.status_code == 403


def test_supply_chain_cannot_run_reconcile(client, auth_headers):
    headers = auth_headers("supply_chain")
    cid = _revenue_contract_id(client, auth_headers("analyst"))
    resp = client.post(f"/api/v1/contracts/{cid}/reconcile", headers=headers)
    assert resp.status_code == 403


def test_south_kpi_reliability_target(client, auth_headers):
    """Stale POS 0.12 + grain mismatch 0.05 → reliability 0.83 (arch South target)."""
    headers = auth_headers("analyst")
    rows = client.get("/api/v1/contracts", headers=headers).json()["data"]
    south = next(c for c in rows if c["kpi_code"] == "sales_per_outlet_south")
    resp = client.post(f"/api/v1/contracts/{south['id']}/reconcile", headers=headers)
    assert resp.status_code == 200
    run = resp.json()["data"]
    assert abs(run["reliability_score"] - 0.83) < 0.005
    types = {c["conflict_type"] for c in run["conflicts"]}
    assert "refresh" in types and "grain" in types
