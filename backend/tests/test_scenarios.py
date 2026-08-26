"""Scenario templates: three configs, one engine, loud validation, idempotent start."""
from __future__ import annotations


def test_three_scenarios_seeded(client, auth_headers):
    rows = client.get("/api/v1/scenarios", headers=auth_headers("executive")).json()["data"]
    assert len(rows) == 3
    assert {r["scenario_id"] for r in rows} == {
        "apex_revenue_decline_ne", "apex_inventory_cover", "apex_millet_launch",
    }
    # Every card declares the SAME engine — the AC18 story.
    assert all(r["engine"] == "reasonflow-core" for r in rows)
    hero = next(r for r in rows if r["scenario_id"] == "apex_revenue_decline_ne")
    assert hero["primary_kpi"] == "revenue_ne"
    assert set(hero["sources"]) == {"erp", "gl", "pos", "wms", "scorecard"}
    assert hero["demo_priority"] == 1


def test_scenario_detail_has_full_configuration(client, auth_headers):
    detail = client.get(
        "/api/v1/scenarios/apex_revenue_decline_ne", headers=auth_headers("analyst")
    ).json()["data"]
    for key in (
        "source_configuration", "driver_configuration", "threshold_configuration",
        "materiality_configuration", "decision_options", "guardrail_configuration",
        "persona_configuration", "entitlement_configuration", "dataset_ref", "expected_outcome_ref",
    ):
        assert key in detail
    guardrails = detail["guardrail_configuration"]["guardrails"]
    assert len(guardrails) == 4  # margin, cover, cash, SLA
    codes = {g["code"] for g in guardrails}
    assert codes == {"gross_margin", "inventory_cover", "cash_exposure", "customer_sla"}
    options = {o["option_code"] for o in detail["decision_options"]}
    assert "A_backup_supplier" in options and "B_air_freight" in options and "C_price_promotion" in options


def test_start_hero_scenario_opens_workspace(client, auth_headers):
    resp = client.post(
        "/api/v1/scenarios/apex_revenue_decline_ne/start", headers=auth_headers("analyst")
    )
    assert resp.status_code == 200
    ws = resp.json()["data"]
    assert ws["engine"] == "reasonflow-core"
    assert ws["validation"]["valid"] is True
    assert ws["validation"]["gaps"] == []
    codes = {c["kpi_code"] for c in ws["contracts"]}
    assert codes == {"revenue_ne", "osa_ne", "inventory_cover_ne", "marketing_roi", "supplier_reliability"}


def test_start_is_idempotent(client, auth_headers):
    headers = auth_headers("analyst")
    first = client.post("/api/v1/scenarios/apex_revenue_decline_ne/start", headers=headers).json()["data"]
    second = client.post("/api/v1/scenarios/apex_revenue_decline_ne/start", headers=headers).json()["data"]
    assert first["contracts"] == second["contracts"]
    assert first["scenario"] == second["scenario"]


def test_scenario2_validates_through_same_engine_path(client, auth_headers):
    """AC18 groundwork: S2 runs the identical validation/provisioning path with different config."""
    resp = client.post("/api/v1/scenarios/apex_inventory_cover/start", headers=auth_headers("analyst"))
    assert resp.status_code == 200
    ws = resp.json()["data"]
    assert ws["engine"] == "reasonflow-core"
    assert ws["scenario"]["primary_kpi"] == "inventory_cover_ne"
    assert ws["validation"]["valid"] is True


def test_scenario3_cold_start_startable(client, auth_headers):
    resp = client.post("/api/v1/scenarios/apex_millet_launch/start", headers=auth_headers("analyst"))
    assert resp.status_code == 200
    ws = resp.json()["data"]
    assert ws["scenario"]["primary_kpi"] == "millet_noodles_revenue"


def test_supply_chain_can_start_scenario(client, auth_headers):
    resp = client.post(
        "/api/v1/scenarios/apex_revenue_decline_ne/start", headers=auth_headers("supply_chain")
    )
    assert resp.status_code == 200


def test_start_audited(client, auth_headers):
    client.post("/api/v1/scenarios/apex_revenue_decline_ne/start", headers=auth_headers("analyst"))
    from app.db import SessionLocal
    from app.models.org import AuditEvent

    db = SessionLocal()
    try:
        rows = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "scenario.start", AuditEvent.object_id == "apex_revenue_decline_ne")
            .all()
        )
        assert rows
    finally:
        db.close()


def test_scenario_switch_same_pipeline_different_config(client, auth_headers):
    """AC18 (locked): S1 and S2 run the IDENTICAL pipeline code path — same
    stage sequence and method labels, config-only differences (S2 primary =
    inventory_cover_ne, its own drivers/actions/guardrails)."""
    analyst = auth_headers("analyst")
    # S1 baseline: hero prefix stages on revenue_ne
    s1 = client.post("/api/v1/scenarios/apex_revenue_decline_ne/start", headers=analyst)
    assert s1.status_code == 200
    kpis = client.get("/api/v1/kpis", headers=analyst).json()["data"]
    s1_kid = next(k["id"] for k in kpis if k["code"] == "revenue_ne")
    made = client.post("/api/v1/investigations", headers=analyst, json={"kpi_id": s1_kid})
    inv1 = made.json()["data"] if made.status_code == 200 else client.get(
        f"/api/v1/investigations?kpi_id={s1_kid}", headers=analyst).json()["data"][0]
    codes1 = [e["stage_code"] for e in inv1["stage_events"]]

    # switch to S2 and run the same pipeline on its primary KPI
    s2 = client.post("/api/v1/scenarios/apex_inventory_cover/start", headers=analyst)
    assert s2.status_code == 200
    assert s2.json()["data"]["scenario"]["primary_kpi"] == "inventory_cover_ne"
    kpis2 = client.get("/api/v1/kpis", headers=analyst).json()["data"]
    s2_kid = next(k["id"] for k in kpis2 if k["code"] == "inventory_cover_ne")
    made2 = client.post("/api/v1/investigations", headers=analyst, json={"kpi_id": s2_kid})
    assert made2.status_code in (200, 409), made2.text
    inv2 = made2.json()["data"] if made2.status_code == 200 else client.get(
        f"/api/v1/investigations?kpi_id={s2_kid}", headers=analyst).json()["data"][0]
    codes2 = [e["stage_code"] for e in inv2["stage_events"]]

    # identical engine path: the pipeline prefix (reconcile → … → decompose/
    # evidence/rank) is byte-identical; the CERTAINTY STATE MACHINE then branches
    # on the scenario's own data (config-only difference), which is the point of AC18
    assert len(codes1) >= 8 and len(codes2) >= 8
    assert codes1[:8] == codes2[:8]
    assert codes1[8] in ("generate_options", "certainty_abstain", "certainty_clarify")
    assert codes2[8] in ("generate_options", "certainty_abstain", "certainty_clarify")
    assert inv2["kpi"]["code"] == "inventory_cover_ne"
    # the switch itself is audited
    audit_rows = client.get("/api/v1/audit", headers=auth_headers("owner")).json()["data"]
    assert any(a["action"] == "scenario.start" for a in audit_rows)
    # restore S1 as the active scenario for later tests
    client.post("/api/v1/scenarios/apex_revenue_decline_ne/start", headers=analyst)
