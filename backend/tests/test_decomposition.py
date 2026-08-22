"""S3 — Deterministic driver analysis (contribution decomposition, AC5 spine)."""
from __future__ import annotations

import math

from app.models.decomposition import DecompositionComponent


def _kpi_id(client, headers, code="revenue_ne"):
    return next(k["id"] for k in client.get("/api/v1/kpis", headers=headers).json()["data"] if k["code"] == code)


def _investigation(client, headers, kpi_id):
    made = client.post("/api/v1/investigations", headers=headers, json={"kpi_id": kpi_id})
    if made.status_code == 409:  # shared session DB: reuse the existing active investigation
        existing = client.get(f"/api/v1/investigations?kpi_id={kpi_id}", headers=headers).json()["data"]
        assert existing, made.text
        return existing[0]
    assert made.status_code == 200, made.text
    return made.json()["data"]


LOCKED = {"price": 1.8, "volume": -9.5, "mix": -0.9, "region": 0.0, "residual": -3.4}


def test_decomposition_hits_locked_targets(client, auth_headers):
    headers = auth_headers("analyst")
    inv = _investigation(client, headers, _kpi_id(client, headers))
    assert inv["workflow_state"] in ("RIGHTS_CHECKED", "DECISION_RECORD_CREATED", "PORTFOLIO_UPDATED", "HUMAN_APPROVAL", "APPROVED", "REJECTED", "OVERRIDDEN")

    resp = client.get(f"/api/v1/investigations/{inv['id']}/decomposition", headers=headers)
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    comps = {c["component"]: c for c in d["components"]}

    assert set(comps) == set(LOCKED), comps.keys()
    for name, want in LOCKED.items():
        assert math.isclose(comps[name]["pct"], want, abs_tol=0.05), f"{name}: {comps[name]['pct']} vs {want}"
        assert comps[name]["method"] == "sql"
        assert comps[name]["query_ref"], "query reference must be inspectable"

    # The identity: components + residual sum to the observed movement exactly (AC5)
    assert math.isclose(d["sum_pct"], -12.0, abs_tol=0.05), d["sum_pct"]
    assert math.isclose(d["sum_value"], 84.0 - 95.45, abs_tol=0.001), d["sum_value"]


def test_decomposition_persisted_and_replayable(client, auth_headers):
    headers = auth_headers("analyst")
    inv = _investigation(client, headers, _kpi_id(client, headers))
    got = client.get(f"/api/v1/investigations/{inv['id']}/decomposition", headers=headers).json()["data"]
    again = client.get(f"/api/v1/investigations/{inv['id']}/decomposition", headers=headers).json()["data"]
    assert got == again  # stored artifacts — refresh never loses state, identical replay


def test_investigation_pipeline_reaches_explaining_with_telemetry(client, auth_headers):
    headers = auth_headers("analyst")
    inv = _investigation(client, headers, _kpi_id(client, headers))
    states = [e["to_state"] for e in inv["stage_events"]]
    prefix = ["RECONCILING", "RECONCILED", "DETECTING", "DETECTED", "TRIAGED", "EXPLAINING", "EXPLAINED", "CERTAINTY_DECISION", "DECISION_OPTIONS_GENERATED", "SIMULATED", "GUARDRAILS_CHECKED", "SECOND_ORDER_ANALYZED", "COLLISIONS_CHECKED", "RIGHTS_CHECKED"]
    assert states[: len(prefix)] == prefix  # a session-mate may already have approved
    t = inv["telemetry"]
    assert t["llm_stages"] == 0  # decomposition is SQL — zero LLM
    assert t["numbers_computed_without_llm_pct"] == 100.0
    assert any(e["stage_code"] == "decompose" for e in inv["stage_events"])  # marker transition row exists


def test_decomposition_without_facts_is_honest_single_component(client, auth_headers):
    """No SKU panel ⇒ one labeled level component, never an invented split (osa_ne has none)."""
    headers = auth_headers("analyst")
    kpi_id = _kpi_id(client, headers, code="osa_ne")
    inv = _investigation(client, headers, kpi_id)
    d = client.get(f"/api/v1/investigations/{inv['id']}/decomposition", headers=headers).json()["data"]
    comps = d["components"]
    assert len(comps) == 1
    assert comps[0]["component"] == "level"
    assert comps[0]["method"] == "baseline_compare"
    assert "No SKU fact panel" in comps[0]["detail"]
    assert math.isclose(comps[0]["pct"], -21.3, abs_tol=0.2)  # full movement, honestly labeled


def test_decomposition_tenant_isolated(client, auth_headers):
    headers = auth_headers("analyst")
    inv = _investigation(client, headers, _kpi_id(client, headers))
    outsider = auth_headers("outsider")
    resp = client.get(f"/api/v1/investigations/{inv['id']}/decomposition", headers=outsider)
    assert resp.status_code == 404
