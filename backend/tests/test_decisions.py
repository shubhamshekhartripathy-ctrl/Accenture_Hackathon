"""S7 — Decision records (AC10–13): locked options, hard guardrail blocks, rights,
human approval, override discipline, abstention refusal, tenant isolation."""
from __future__ import annotations

_TOK: dict[str, str] = {}
EMAILS = {
    "EXECUTIVE": "priya.ceo@apexfoods.example",
    "ANALYST": "meera.analyst@apexfoods.example",
    "SUPPLY_CHAIN": "rahul.sc@apexfoods.example",
    "KPI_OWNER": "vikram.owner@apexfoods.example",
    "OUTSIDER": "sneha.exec@meridian.example",
}


def _tok(client, who):
    if who not in _TOK:
        _TOK[who] = client.post("/api/v1/auth/login", json={"email": EMAILS[who], "password": "ReasonFlow#2026"}).json()["data"]["access_token"]
    return _TOK[who]


def _kpi(client, tok, code="revenue_ne"):
    return next(k["id"] for k in client.get("/api/v1/kpis", headers={"Authorization": f"Bearer {tok}"}).json()["data"] if k["code"] == code)


def _inv(client, tok, kpi_id):
    made = client.post("/api/v1/investigations", headers={"Authorization": f"Bearer {tok}"}, json={"kpi_id": kpi_id})
    if made.status_code == 409:
        return client.get(f"/api/v1/investigations?kpi_id={kpi_id}", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]
    assert made.status_code == 200, made.text
    return made.json()["data"]


def _hero(client):
    tok = _tok(client, "ANALYST")
    inv = _inv(client, tok, _kpi(client, tok))
    return tok, inv


def _options(client, inv, who="ANALYST"):
    d = client.get(f"/api/v1/investigations/{inv['id']}/decisions", headers={"Authorization": f"Bearer {_tok(client, who)}"}).json()["data"]
    return {o["code"]: o for o in d["options"]}


def test_locked_options_with_guardrails_and_rights(client, auth_headers):
    _, inv = _hero(client)
    opts = _options(client, inv)
    assert inv["workflow_state"] == "RIGHTS_CHECKED"
    a, b, c, cp = opts["A_backup_supplier"], opts["B_air_freight"], opts["C_price_promotion"], opts["Cp_restore_then_promote"]
    assert a["expected_impact_rs"] == 4_100_000 and a["impact_lo_rs"] == 2_900_000 and a["impact_hi_rs"] == 5_200_000
    assert a["cost_rs"] == 1_600_000 and a["horizon_days"] == 42
    assert a["guardrail_status"] == "PASS" and a["rights_verdict"] == "AUTHORIZED"
    assert b["guardrail_status"] == "FAIL" and b["rights_verdict"] == "ESCALATE"
    assert any("cash_exposure FAIL" in r for r in b["guardrail_reasons"])
    assert any("inventory_cover FAIL" in r for r in b["guardrail_reasons"])  # cover 4.0 < 5 days
    assert c["guardrail_status"] == "NOT_SAFE"
    assert any("inventory_cover FAIL" in r for r in c["guardrail_reasons"])  # −18% inventory
    assert cp["guardrail_status"] == "PASS"
    assert cp["decision_health"] == "BETTER" and c["decision_health"] == "WORSE"  # explainable comparison
    assert a["simulation"]["projected"]["inventory_cover_ne"] == 6.4
    assert b["simulation"]["projected"]["inventory_cover_ne"] == 4.0
    assert a["scenario_id"] == "apex_revenue_decline_ne"  # config provenance (AC18)


def test_analyst_cannot_approve(client, auth_headers):
    _, inv = _hero(client)
    opts = _options(client, inv)
    resp = client.post(
        f"/api/v1/investigations/{inv['id']}/decisions/{opts['A_backup_supplier']['id']}",
        headers={"Authorization": f"Bearer {_tok(client, 'ANALYST')}"}, json={"decision": "APPROVE"},
    )
    assert resp.status_code == 403
    assert "may not approve" in resp.json()["error"]["message"]


def test_hard_guardrail_fail_blocks_everyone_including_executive(client, auth_headers):
    _, inv = _hero(client)
    opts = _options(client, inv)
    for who in ("EXECUTIVE", "SUPPLY_CHAIN", "KPI_OWNER"):
        resp = client.post(
            f"/api/v1/investigations/{inv['id']}/decisions/{opts['B_air_freight']['id']}",
            headers={"Authorization": f"Bearer {_tok(client, who)}"}, json={"decision": "APPROVE"},
        )
        assert resp.status_code == 409, (who, resp.status_code)
        assert resp.json()["error"]["code"] == "GUARDRAIL_BLOCK"
    # NOT_SAFE option: blocked by the HIGH collision first (AC21), then by its
    # own guardrail FAIL once the collision is resolved — never auto-substituted.
    resp = client.post(
        f"/api/v1/investigations/{inv['id']}/decisions/{opts['C_price_promotion']['id']}",
        headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}, json={"decision": "APPROVE"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] in ("COLLISION_BLOCK", "GUARDRAIL_BLOCK")


def test_supply_chain_approves_option_a_governed(client, auth_headers):
    _, inv = _hero(client)
    opts = _options(client, inv)
    resp = client.post(
        f"/api/v1/investigations/{inv['id']}/decisions/{opts['A_backup_supplier']['id']}",
        headers={"Authorization": f"Bearer {_tok(client, 'SUPPLY_CHAIN')}"}, json={"decision": "APPROVE"},
    )
    assert resp.status_code == 200, resp.text
    rec = resp.json()["data"]["record"]
    assert rec["status"] == "APPROVED" and rec["approved_by_role"] == "SUPPLY_CHAIN"
    plan = rec["monitoring_plan"]
    assert plan["metric"] == "revenue_ne" and plan["cadence"] == "weekly"
    assert plan["success_band"] == [2_900_000, 5_200_000]
    # workflow advanced through the governed chain to APPROVED, persisted
    inv2 = client.get(f"/api/v1/investigations?kpi_id={inv['kpi_id'] if 'kpi_id' in inv else _kpi(client, _tok(client, 'ANALYST'))}",
                      headers={"Authorization": f"Bearer {_tok(client, 'ANALYST')}"}).json()["data"][0]
    assert inv2["workflow_state"] == "APPROVED"
    states = [e["to_state"] for e in inv2["stage_events"]]
    for s in ("DECISION_RECORD_CREATED", "PORTFOLIO_UPDATED", "HUMAN_APPROVAL", "APPROVED"):
        assert s in states
    # decision audited
    audits = client.get("/api/v1/audit?action=decision.approve", headers={"Authorization": f"Bearer {_tok(client, 'KPI_OWNER')}"}).json()["data"]
    assert any(a["object_id"] == opts["A_backup_supplier"]["id"] for a in audits)


def test_duplicate_decision_refused(client, auth_headers):
    _, inv = _hero(client)
    opts = _options(client, inv)
    h = {"Authorization": f"Bearer {_tok(client, 'SUPPLY_CHAIN')}"}
    first = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opts['A_backup_supplier']['id']}", headers=h, json={"decision": "APPROVE"})
    if first.status_code == 200:
        # fresh option: a second decision on it must be refused
        second = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opts['A_backup_supplier']['id']}", headers=h, json={"decision": "REJECT"})
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "DECISION_EXISTS"
    else:
        # an earlier test already approved it in this session — same refusal, direct
        assert first.status_code == 409
        assert first.json()["error"]["code"] == "DECISION_EXISTS"


def test_override_requires_reason(client, auth_headers):
    _, inv = _hero(client)
    opts = _options(client, inv)
    h = {"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}
    resp = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opts['Cp_restore_then_promote']['id']}",
                       headers=h, json={"decision": "OVERRIDE"})
    assert resp.status_code == 400  # no reason
    resp = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opts['Cp_restore_then_promote']['id']}",
                       headers=h, json={"decision": "OVERRIDE", "override_reason": "Board-mandated launch window; monitoring doubled"})
    assert resp.status_code == 200
    assert resp.json()["data"]["record"]["status"] == "OVERRIDDEN"
    assert resp.json()["data"]["record"]["override_reason"].startswith("Board-mandated")


def test_abstained_case_offers_no_options(client, auth_headers):
    tok = _tok(client, "ANALYST")
    inv = _inv(client, tok, _kpi(client, tok, code="sales_per_outlet_south"))
    assert inv["workflow_state"] == "ABSTAINED"
    d = client.get(f"/api/v1/investigations/{inv['id']}/decisions", headers={"Authorization": f"Bearer {tok}"}).json()["data"]
    assert d["options"] == []
    # and no decision may be POSTed (nothing to decide on)
    resp = client.post(f"/api/v1/investigations/{inv['id']}/decisions/nonexistent", headers={"Authorization": f"Bearer {tok}"},
                       json={"decision": "APPROVE"})
    assert resp.status_code == 404


def test_options_deterministic_on_rerun(client, auth_headers):
    tok = _tok(client, "ANALYST")
    kid = _kpi(client, tok)
    _inv(client, tok, kid)
    a = client.get(f"/api/v1/investigations?kpi_id={kid}", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]
    sig = [(o["code"], o["guardrail_status"], o["rights_verdict"], o["simulation"]["projected"]["inventory_cover_ne"])
           for o in a["options"]]
    b = client.get(f"/api/v1/investigations/{a['id']}/decisions", headers={"Authorization": f"Bearer {tok}"}).json()["data"]
    assert sig == [(o["code"], o["guardrail_status"], o["rights_verdict"], o["simulation"]["projected"]["inventory_cover_ne"]) for o in b["options"]]


def test_decisions_tenant_isolated(client, auth_headers):
    _, inv = _hero(client)
    resp = client.get(f"/api/v1/investigations/{inv['id']}/decisions", headers={"Authorization": f"Bearer {_tok(client, 'OUTSIDER')}"})
    assert resp.status_code == 404
