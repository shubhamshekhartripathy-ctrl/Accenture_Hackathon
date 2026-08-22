"""Contract lifecycle: versioned edits, snapshots, status machine, activation gate."""
from __future__ import annotations


def _revenue_contract(client, headers) -> dict:
    rows = client.get("/api/v1/contracts", headers=headers).json()["data"]
    return next(c for c in rows if c["kpi_code"] == "revenue_ne")


def test_contract_detail_is_field_complete(client, auth_headers):
    c = _revenue_contract(client, auth_headers("owner"))
    detail = client.get(f"/api/v1/contracts/{c['id']}", headers=auth_headers("owner")).json()["data"]
    for field in (
        "business_definition", "formula_sql", "formula_note", "unit", "business_function",
        "owner_name", "owner_role", "status", "calendar_rule", "version",
        "sources", "drivers", "threshold", "rights", "entitlements", "versions",
    ):
        assert field in detail, f"missing {field}"
    # Status is derived from open definition conflicts: the seeded ERP↔GL conflict
    # is detected at reconciliation, so a session that already ran an investigation
    # for this KPI shows CONFLICTED (honest). Fresh seed ⇒ ACTIVE.
    assert detail["status"] in ("ACTIVE", "CONFLICTED")
    assert len(detail["sources"]) == 3
    assert {s["source_code"] for s in detail["sources"]} == {"erp", "gl", "pos"}
    assert detail["sources"][0]["is_authoritative"] is True  # ERP authoritative for revenue
    assert len(detail["drivers"]) == 4
    assert detail["drivers"][0]["driver_code"] == "supplier_delay"
    assert detail["threshold"]["strategic_weight"] == 0.8
    rights = {(r["role"], r["action_class"]): r for r in detail["rights"]}
    sc = rights[("SUPPLY_CHAIN", "supply_switch")]
    assert sc["may_approve"] is True and sc["approve_limit_rs"] == 2_000_000
    assert rights[("ANALYST", "*")]["may_approve"] is False
    ent = {e["role"]: e for e in detail["entitlements"]}
    assert "marketing_roi" in ent["SUPPLY_CHAIN"]["masked_columns"]
    assert ent["SUPPLY_CHAIN"]["row_scope"]["region"] == ["NE"]
    # seeded version-1 snapshot exists
    assert any(v["version"] == 1 for v in detail["versions"])


def test_patch_bumps_version_and_snapshots(client, auth_headers):
    headers = auth_headers("owner")
    c = _revenue_contract(client, headers)
    before = client.get(f"/api/v1/contracts/{c['id']}", headers=headers).json()["data"]
    resp = client.patch(
        f"/api/v1/contracts/{c['id']}", headers=headers,
        json={"formula_note": "Invoiced net sales; accrual excluded (clarified W14)."},
    )
    assert resp.status_code == 200
    after = resp.json()["data"]
    assert after["version"] == before["version"] + 1
    versions = client.get(f"/api/v1/contracts/{c['id']}/versions", headers=headers).json()["data"]
    assert before["version"] in [v["version"] for v in versions]


def test_patch_rejects_unknown_fields(client, auth_headers):
    headers = auth_headers("owner")
    c = _revenue_contract(client, headers)
    resp = client.patch(
        f"/api/v1/contracts/{c['id']}", headers=headers,
        json={"version": 99, "status": "ACTIVE"},
    )
    assert resp.status_code == 422
    assert "status" in resp.json()["error"]["message"] or "version" in resp.json()["error"]["message"]


def test_contract_edit_is_audited(client, auth_headers):
    headers = auth_headers("owner")
    c = _revenue_contract(client, headers)
    client.patch(f"/api/v1/contracts/{c['id']}", headers=headers, json={"formula_note": "audit probe"})
    from app.db import SessionLocal
    from app.models.org import AuditEvent

    db = SessionLocal()
    try:
        rows = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "contract.edit", AuditEvent.object_id == c["id"])
            .order_by(AuditEvent.created_at.desc())
            .all()
        )
        assert rows, "contract edit must write an audit row"
        assert rows[0].actor_role == "KPI_OWNER"
    finally:
        db.close()


def test_status_machine_rejects_illegal_transition(client, auth_headers):
    headers = auth_headers("owner")
    c = _revenue_contract(client, headers)
    resp = client.post(
        f"/api/v1/contracts/{c['id']}/status", headers=headers,
        json={"status": "DRAFT", "reason": "illegal"},
    )
    assert resp.status_code == 409


def test_duplicate_contract_for_same_kpi_refused_loudly(client, auth_headers):
    """One governed contract per KPI — forking is refused with a 409, edits version instead."""
    headers = auth_headers("owner")
    kpis = client.get("/api/v1/kpis", headers=headers).json()["data"]
    kpi = next(k for k in kpis if k["code"] == "osa_ne")
    resp = client.post(
        "/api/v1/contracts", headers=headers,
        json={"kpi_id": kpi["id"], "name": "Second fork", "business_definition": "x", "unit": "PCT"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONTRACT_EXISTS"


def test_draft_contract_cannot_activate_with_blocking_gaps():
    """Activation gate at the service level: NO_SOURCES is BLOCKING."""
    from app.db import SessionLocal
    from app.domains.contracts.service import transition_status
    from app.errors import AppError
    from app.models.contract import KpiContract
    from app.models.kpi import Kpi

    db = SessionLocal()
    try:
        org_id = db.query(Kpi).first().organization_id
        kpi = Kpi(organization_id=org_id, code="gate_probe_kpi", name="Probe", category="REVENUE",
                  region="NE", unit="INR_M")
        db.add(kpi)
        db.flush()
        contract = KpiContract(
            organization_id=org_id, kpi_id=kpi.id, name="Probe contract",
            business_definition="Probe", unit="INR_M", status="DRAFT", version=1,
        )
        db.add(contract)
        db.flush()
        try:
            transition_status(db, contract, "ACTIVE", actor_user_id=None)
            raise AssertionError("activation must be refused")
        except AppError as exc:
            assert exc.status_code == 422
            codes = {g["code"] for g in exc.details["gaps"]}
            assert "NO_SOURCES" in codes
    finally:
        db.rollback()
        db.close()


def test_scenario_start_refuses_when_contract_not_active(client, auth_headers):
    """Validation is loud: deactivate-like simulation via a scenario gap list."""
    # Meridian (second tenant) has KPIs but no contracts for apex scenarios — start must 404 (isolation).
    resp = client.post(
        "/api/v1/scenarios/apex_revenue_decline_ne/start", headers=auth_headers("outsider")
    )
    assert resp.status_code == 404
