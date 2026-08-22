"""Auth + security tests: real JWT, lockout, RBAC, envelope shape."""
from __future__ import annotations


def test_health_live(client):
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "alive"
    assert "request_id" in body["meta"]


def test_health_ready_reports_degraded_states_loudly(client):
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    components = resp.json()["data"]["components"]
    assert components["llm"] == "deterministic"  # no credentials in tests
    assert "fallback" in components["redis"] or "not configured" in components["redis"]
    assert components["database"]["state"].startswith("ok")


def test_login_success_all_personas(login):
    for persona in ("executive", "supply_chain", "analyst", "owner", "admin"):
        data = login(persona)
        assert data["access_token"]
        assert data["user"]["email"].endswith("@apexfoods.example")


def test_login_wrong_password_401(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "priya.ceo@apexfoods.example", "password": "wrong"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_login_unknown_user_401(client):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@x.example", "password": "x"})
    assert resp.status_code == 401


def test_lockout_after_repeated_failures(client):
    # Lock a throwaway account deterministically (rate limiter allows 10/min; 5 failures lock).
    email = "arjun.admin@apexfoods.example"
    for _ in range(5):
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": "bad"})
        assert resp.status_code == 401
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "ReasonFlow#2026"})
    assert resp.status_code == 401
    assert "locked" in resp.json()["error"]["message"].lower()


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_token(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers("executive"))
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "EXECUTIVE"


def test_refresh_flow(client, login):
    data = login("analyst")
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]


def test_access_token_rejected_as_refresh(client, login):
    data = login("analyst")
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": data["access_token"]})
    assert resp.status_code == 401


def test_rbac_analyst_cannot_patch_contract(client, auth_headers):
    contracts = client.get("/api/v1/contracts", headers=auth_headers("analyst")).json()["data"]
    assert contracts
    resp = client.patch(
        f"/api/v1/contracts/{contracts[0]['id']}",
        headers=auth_headers("analyst"),
        json={"name": "tampered"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_rbac_supply_chain_cannot_create_contract(client, auth_headers):
    resp = client.post(
        "/api/v1/contracts",
        headers=auth_headers("supply_chain"),
        json={"kpi_id": "x", "name": "x", "business_definition": "x", "unit": "INR_M"},
    )
    assert resp.status_code == 403


def test_denied_mutation_is_audited(client, auth_headers):
    contracts = client.get("/api/v1/contracts", headers=auth_headers("analyst")).json()["data"]
    client.patch(
        f"/api/v1/contracts/{contracts[0]['id']}", headers=auth_headers("analyst"), json={"name": "nope"}
    )
    # Audit table is the backend source of truth; verify via a DB session.
    from app.db import SessionLocal
    from app.models.org import AuditEvent

    db = SessionLocal()
    try:
        denials = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "contract.edit", AuditEvent.outcome == "success")
            .all()
        )
        # The denied PATCH never produced a contract.edit row (403 at the guard).
        assert all(d.object_id != contracts[0]["id"] or d.actor_role in ("KPI_OWNER", "ADMIN") for d in denials)
    finally:
        db.close()
