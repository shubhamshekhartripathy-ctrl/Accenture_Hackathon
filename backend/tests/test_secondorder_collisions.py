"""S8 — Second-order impact (AC20) + collisions (AC21) + portfolio (AC22).

Every asserted number is the architecture's locked target — the elasticities
are chain-derived (12/−18, 7/12), never tuned to pass.
"""
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


def _hero(client):
    tok = _tok(client, "ANALYST")
    made = client.post("/api/v1/investigations", headers={"Authorization": f"Bearer {tok}"}, json={"kpi_id": _kpi(client, tok)})
    if made.status_code == 409:
        inv = client.get(f"/api/v1/investigations?kpi_id={_kpi(client, tok)}", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]
    else:
        inv = made.json()["data"]
    d = client.get(f"/api/v1/investigations/{inv['id']}/decisions", headers={"Authorization": f"Bearer {tok}"}).json()["data"]
    return tok, inv, {o["code"]: o for o in d["options"]}, d.get("collisions", [])


def test_locked_second_order_chain_promotion(client, auth_headers):
    """promotion → revenue +8% → inventory −18% → stockout +12 pts → complaints +7%."""
    _, _, opts, _ = _hero(client)
    resp = client.get(f"/api/v1/decisions/{opts['C_price_promotion']['id']}/impacts",
                      headers={"Authorization": f"Bearer {_tok(client, 'ANALYST')}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["method"] == "graph_elasticity"
    assert data["direct_pct"] == {"revenue_ne": 8}  # percentage points

    by_kpi = {e["kpi"]: e for e in data["second_order"]["effects"]}
    inv = by_kpi["inventory_cover_ne"]
    assert abs(inv["effect_pct"] - (-18.0)) < 1e-6            # +8 × −2.25 pct pts
    assert inv["dependency_path"] == ["revenue_ne", "inventory_cover_ne"]

    stock = by_kpi["stockout_risk_ne"]
    assert abs(stock["effect_pct"] - 12.0) < 0.05             # −18% × −0.667 ⇒ +12 pts
    assert stock["node_kind"] == "DERIVED_IMPACT" and stock["unit"] == "PTS"
    assert stock["dependency_path"] == ["revenue_ne", "inventory_cover_ne", "stockout_risk_ne"]

    complaints = by_kpi["complaints_rate_ne"]
    assert abs(complaints["effect_pct"] - 7.0) < 0.05         # +12 pts × +0.583 ⇒ +7%
    assert complaints["unit"] == "PCT"

    # bounds widen per hop (20% relative, compounding) and confidence decays
    assert inv["bounds_pct"] == [-21.6, -14.4]                # ±20% at hop 1
    assert stock["bounds_pct"] == sorted([round(stock["effect_pct"] * 0.6, 4), round(stock["effect_pct"] * 1.4, 4)])  # ±40% at hop 2
    assert stock["confidence"] < inv["confidence"] < 1.0
    assert complaints["confidence"] < stock["confidence"]

    # derived metrics carry definitions + provenance (not silent magic numbers)
    assert "stockout_risk_ne" in data["derived_metrics"]
    assert data["derived_metrics"]["stockout_risk_ne"]["unit"] == "PTS"
    assert "graph_elasticity" in data["derived_metrics"]["stockout_risk_ne"]["provenance"]


def test_derived_metrics_are_not_primary_kpis(client, auth_headers):
    """The primary governed KPI set is unchanged — stockout/complaints are derived."""
    tok = _tok(client, "ANALYST")
    codes = {k["code"] for k in client.get("/api/v1/kpis", headers={"Authorization": f"Bearer {tok}"}).json()["data"]}
    assert "stockout_risk_ne" not in codes and "complaints_rate_ne" not in codes
    assert codes >= {"revenue_ne", "osa_ne", "inventory_cover_ne", "marketing_roi", "supplier_reliability"}


def test_phased_variant_suppresses_the_drain_edge(client, auth_headers):
    """Cp: stock restored first — the promo drain is absorbed (no −2.25 hop on cover)."""
    _, _, opts, _ = _hero(client)
    data = client.get(f"/api/v1/decisions/{opts['Cp_restore_then_promote']['id']}/impacts",
                      headers={"Authorization": f"Bearer {_tok(client, 'ANALYST')}"}).json()["data"]
    paths = [e["dependency_path"] for e in data["second_order"]["effects"]]
    assert not any(p[:2] == ["revenue_ne", "inventory_cover_ne"] for p in paths), "suppressed edge must not propagate"
    stock = next(e for e in data["second_order"]["effects"] if e["kpi"] == "stockout_risk_ne")
    assert stock["effect_pct"] < 0  # phased plan REDUCES stockout risk


def test_locked_collision_high_combined_minus_33_plus_17pts(client, auth_headers):
    """−15% (procurement) + −18% (promotion) ⇒ −33% cover ⇒ stockout +17 pts ⇒ HIGH."""
    _, _, opts, collisions = _hero(client)
    high = [c for c in collisions if c["severity"] == "HIGH"]
    assert len(high) == 1
    c = high[0]
    assert set(c["option_codes"]) == {"C_price_promotion", "X_reduce_safety_stock"}
    assert c["affected_kpi"] == "inventory_cover_ne"
    assert abs(c["combined_effect_pct"] - (-33.0)) < 1e-6
    assert "+17 pts" in c["combined_note"]
    assert "|-0.667| × (18 + 0.5 × 15)" in c["combined_note"]  # damped joint arithmetic shown
    assert set(c["owners"]) == {"MARKETING", "SUPPLY_CHAIN"}
    assert len(c["resolution_options"]) == 3
    assert c["resolved"] is False
    # the external proposal is a tracked, in-flight decision — not decidable here
    x = opts["X_reduce_safety_stock"]
    assert x["record"]["status"] == "PENDING"


def test_unresolved_high_blocks_then_human_resolution_unblocks(client, auth_headers):
    """COLLISION_BLOCK 409 → human resolves with note → block lifts (guardrail still
    blocks C; the phased variant approves cleanly)."""
    tok, inv, opts, collisions = _hero(client)
    c_id = next(c["id"] for c in collisions if c["severity"] == "HIGH")

    resp = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opts['C_price_promotion']['id']}",
                       headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}, json={"decision": "APPROVE"})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "COLLISION_BLOCK"
    assert "X_reduce_safety_stock" in resp.json()["error"]["message"]

    # resolution note is mandatory; the system never auto-resolves
    bad = client.post(f"/api/v1/decisions/collisions/{c_id}/resolve",
                      headers={"Authorization": f"Bearer {_tok(client, 'KPI_OWNER')}"},
                      json={"resolution": "SEQUENCE", "note": "short"})
    assert bad.status_code == 400
    # analysts surface but do not resolve governance
    denied = client.post(f"/api/v1/decisions/collisions/{c_id}/resolve",
                         headers={"Authorization": f"Bearer {_tok(client, 'ANALYST')}"},
                         json={"resolution": "SEQUENCE", "note": "sequence with checkpoint please"})
    assert denied.status_code == 403

    ok_resp = client.post(f"/api/v1/decisions/collisions/{c_id}/resolve",
                          headers={"Authorization": f"Bearer {_tok(client, 'KPI_OWNER')}"},
                          json={"resolution": "SEQUENCE",
                                "note": "Restore stock first (2 weeks), re-check cover ≥ 5 days, then promote"})
    assert ok_resp.status_code == 200
    assert ok_resp.json()["data"]["resolved"] is True

    # collision block lifted; C is still NOT_SAFE on its own guardrails (honest)
    resp = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opts['C_price_promotion']['id']}",
                       headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}, json={"decision": "APPROVE"})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "GUARDRAIL_BLOCK"
    assert "Cp_restore_then_promote" in resp.json()["error"]["message"]

    # the phased variant — the explainable resolution — approves
    if opts["Cp_restore_then_promote"]["record"] is None:
        appr = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opts['Cp_restore_then_promote']['id']}",
                           headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}, json={"decision": "APPROVE"})
        assert appr.status_code == 200
        assert appr.json()["data"]["record"]["status"] == "APPROVED"


def test_impacts_guardrails_endpoint_shapes(client, auth_headers):
    _, _, opts, _ = _hero(client)
    h = {"Authorization": f"Bearer {_tok(client, 'ANALYST')}"}
    g = client.get(f"/api/v1/decisions/{opts['A_backup_supplier']['id']}/guardrails", headers=h).json()["data"]
    assert g["status"] == "PASS" and "arithmetic" in g
    cols = client.get("/api/v1/decisions/collisions", headers=h).json()["data"]
    assert any(c["severity"] == "HIGH" for c in cols)


def test_portfolio_aggregates_stored_artifacts_only(client, auth_headers):
    """AC22 — sums of stored impacts/bounds; health formula; no invented truth."""
    tok = _tok(client, "ANALYST")
    inv, opts = _hero(client)[1], _hero(client)[2]
    # approve A if still open (session order tolerant)
    if opts["A_backup_supplier"]["record"] is None:
        r = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opts['A_backup_supplier']['id']}",
                        headers={"Authorization": f"Bearer {_tok(client, 'SUPPLY_CHAIN')}"}, json={"decision": "APPROVE"})
        assert r.status_code == 200
    p = client.get("/api/v1/decisions/portfolio", headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}).json()["data"]
    approved = [a for a in p["active_decisions"] if a["approval_status"] in ("APPROVED", "OVERRIDDEN")]
    assert any(a["option_code"] == "A_backup_supplier" for a in approved)
    assert p["combined_expected_benefit_rs"] == sum(a["expected_impact_rs"] for a in approved)
    all_opts = client.get(f"/api/v1/investigations/{inv['id']}/decisions",
                          headers={"Authorization": f"Bearer {tok}"}).json()["data"]["options"]
    by_code = {o["code"]: o for o in all_opts}
    lo = sum(by_code[a["option_code"]]["impact_lo_rs"] for a in approved)
    hi = sum(by_code[a["option_code"]]["impact_hi_rs"] for a in approved)
    assert p["combined_benefit_range_rs"] == [lo, hi]  # sum of stored bounds — honest arithmetic
    h = p["portfolio_health"]
    assert abs(h["score"] - (0.4 * h["inputs"]["guardrail_pass_rate"] + 0.3 * h["inputs"]["collision_free"]
                             + 0.3 * h["inputs"]["approval_freshness"])) < 1e-3
    # highest cost of waiting surfaces the South abstention artifact once it exists
    invs = client.get(f"/api/v1/investigations?kpi_id={_kpi(client, tok, 'sales_per_outlet_south')}",
                      headers={"Authorization": f"Bearer {tok}"}).json()["data"]
    if invs and invs[0]["workflow_state"] == "ABSTAINED":
        assert p["highest_cost_of_waiting"] is not None


def test_second_order_deterministic_on_rerun(client, auth_headers):
    _, _, opts, _ = _hero(client)
    a = client.get(f"/api/v1/decisions/{opts['C_price_promotion']['id']}/impacts",
                   headers={"Authorization": f"Bearer {_tok(client, 'ANALYST')}"}).json()["data"]["second_order"]
    b = client.get(f"/api/v1/decisions/{opts['C_price_promotion']['id']}/impacts",
                   headers={"Authorization": f"Bearer {_tok(client, 'ANALYST')}"}).json()["data"]["second_order"]
    assert a == b


def test_impacts_tenant_isolated(client, auth_headers):
    _, _, opts, _ = _hero(client)
    resp = client.get(f"/api/v1/decisions/{opts['A_backup_supplier']['id']}/impacts",
                      headers={"Authorization": f"Bearer {_tok(client, 'OUTSIDER')}"})
    assert resp.status_code == 404
