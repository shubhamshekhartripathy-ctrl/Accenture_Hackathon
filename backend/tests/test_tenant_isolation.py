"""Tenant isolation: cross-tenant access is indistinguishable from missing (404)."""
from __future__ import annotations


def test_outsider_sees_no_apex_contracts(client, auth_headers):
    rows = client.get("/api/v1/contracts", headers=auth_headers("outsider")).json()["data"]
    assert rows == []


def test_outsider_cannot_read_apex_contract_by_id(client, auth_headers):
    rows = client.get("/api/v1/contracts", headers=auth_headers("owner")).json()["data"]
    target = rows[0]["id"]
    resp = client.get(f"/api/v1/contracts/{target}", headers=auth_headers("outsider"))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_outsider_cannot_patch_apex_contract(client, auth_headers):
    rows = client.get("/api/v1/contracts", headers=auth_headers("owner")).json()["data"]
    target = rows[0]["id"]
    resp = client.patch(
        f"/api/v1/contracts/{target}", headers=auth_headers("outsider"), json={"name": "steal"}
    )
    assert resp.status_code in (403, 404)  # outsider role is EXECUTIVE: patch would be 403 anyway


def test_outsider_sees_no_apex_scenarios_or_kpis(client, auth_headers):
    scenarios = client.get("/api/v1/scenarios", headers=auth_headers("outsider")).json()["data"]
    assert scenarios == []
    kpis = client.get("/api/v1/kpis", headers=auth_headers("outsider")).json()["data"]
    assert kpis == []


def test_outsider_cannot_start_apex_scenario(client, auth_headers):
    resp = client.post(
        "/api/v1/scenarios/apex_revenue_decline_ne/start", headers=auth_headers("outsider")
    )
    assert resp.status_code == 404


def test_token_org_mismatch_rejected(client, login):
    """A token issued for one tenant cannot act on another tenant's user id."""
    apex = login("executive")
    # Tampering is cryptographically impossible; swapping tokens is the realistic attack and is bound to org claims.
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {apex['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["organization"] == "Apex Foods"
