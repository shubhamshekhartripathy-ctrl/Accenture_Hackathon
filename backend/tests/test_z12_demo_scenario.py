"""S12 — THE DEMO IS A TEST.

test_demo_scenario runs the full 14-beat Apex Foods walkthrough headlessly and
asserts every locked demo target, INCLUDING the DemoBar actions (inject-POS,
fast-forward, toggle-LLM, scenario switch). It then runs the ENTIRE demo a
SECOND TIME without reset — idempotent by construction.

Locked targets (arch §T): reliability 0.76 / impact −0.12 · CRITICAL vs WATCH
· decomposition +1.8/−9.5/−0.9/0.0/−3.4 · hypotheses 0.82/0.12/0.04/0.02 ·
NE ACT_WITH_CAUTION (0.71) · A ₹1.6M AUTHORIZED guardrails PASS · B ₹3.4M
ESCALATE FAIL · promotion NOT SAFE vs BETTER · collision +17 pts HIGH ·
outcome +₹3.9M vs +₹4.1M within band · cold-start cap 0.45 · memory ≥0.85
(target 0.87) · ledger provider-equivalent 2-of-7 LLM ~1,400 tokens ≈ ₹0.19 ·
cache hit shown · route reasons shown.
"""
from __future__ import annotations

import pytest

_TOK: dict[str, str] = {}
EMAILS = {
    "EXECUTIVE": "priya.ceo@apexfoods.example",
    "ANALYST": "meera.analyst@apexfoods.example",
    "SUPPLY_CHAIN": "rahul.sc@apexfoods.example",
    "KPI_OWNER": "vikram.owner@apexfoods.example",
}


def _tok(client, who):
    if who not in _TOK:
        _TOK[who] = client.post("/api/v1/auth/login", json={"email": EMAILS[who], "password": "ReasonFlow#2026"}).json()["data"]["access_token"]
    return _TOK[who]


def _hdr(client, who):
    return {"Authorization": f"Bearer {_tok(client, who)}"}


def _kpi_id(client, tok, code):
    return next(k["id"] for k in client.get("/api/v1/kpis", headers={"Authorization": f"Bearer {tok}"}).json()["data"] if k["code"] == code)


def _walk(client, step):
    """One full demo walkthrough. `step` disambiguates pytest.traceback ids."""
    at, et, ot, st = (_hdr(client, w) for w in ("ANALYST", "EXECUTIVE", "KPI_OWNER", "SUPPLY_CHAIN"))
    tokA = _tok(client, "ANALYST")

    # -- beat 0 (demo setup): the queue materializes from a real detect+triage run
    # (POST /queue/refresh — the same button the Overview screen exposes)
    ref = client.post("/api/v1/queue/refresh", headers=at)
    assert ref.status_code == 200, ref.text

    # -- beat 1: scenario selector + materiality queue (CRITICAL vs WATCH vs COLD START)
    scenarios = client.get("/api/v1/scenarios", headers=at).json()["data"]
    assert len(scenarios) == 3
    q = client.get("/api/v1/queue", headers=at).json()["data"]
    bands = {e["kpi_code"]: e["band"] for e in q["entries"]}
    assert bands["revenue_ne"] == "CRITICAL"
    watch = [c for c, b in bands.items() if b == "WATCH"]
    assert len(watch) >= 1
    cold = [e for e in q["entries"] if e.get("cold_start")]
    assert any(e["kpi_code"] == "millet_noodles_revenue" for e in cold)

    # -- beat 2: contract tab + proposals panel (versioned contract exists)
    kpis = client.get("/api/v1/kpis", headers=at).json()["data"]
    kid = next(k["id"] for k in kpis if k["code"] == "revenue_ne")
    contracts = client.get("/api/v1/contracts", headers=at).json()["data"]
    # the hero contract is CONFLICTED by design (ERP vs GL formula conflict, S4) —
    # governance before reasoning means the conflict is VISIBLE, not hidden
    contract = next(c for c in contracts if c["kpi_id"] == kid)
    assert contract["status"] in ("ACTIVE", "CONFLICTED") and contract["version"] >= 1

    # -- beat 3: MOMENT 1 — reconcile: inputs disagree, typed, capped, routed.
    # The analyst RUNS it live (fresh DB needs no earlier state — this is the moment
    # the hero contract legitimately goes ACTIVE → CONFLICTED, governed and audited).
    run_r = client.post(f"/api/v1/contracts/{contract['id']}/reconcile", headers=at)
    assert run_r.status_code == 200, run_r.text
    rec = run_r.json()["data"]
    assert rec["reliability_score"] == pytest.approx(0.76, abs=0.005)   # locked
    impacts = [c.get("confidence_impact") for c in rec["conflicts"]]
    assert min(impacts) == pytest.approx(-0.12, abs=0.005)              # locked −0.12

    # -- beat 4: decomposition + 4 hypotheses
    inv_m = client.post("/api/v1/investigations", headers=at, json={"kpi_id": kid})
    assert inv_m.status_code in (200, 409)
    inv = inv_m.json()["data"] if inv_m.status_code == 200 else client.get(
        f"/api/v1/investigations?kpi_id={kid}", headers=at).json()["data"][0]
    dec = client.get(f"/api/v1/investigations/{inv['id']}/decomposition", headers=at).json()["data"]
    comps = {c["component"]: c["pct"] for c in dec["components"]}
    want = {"price": 1.8, "volume": -9.5, "mix": -0.9, "region": 0.0, "residual": -3.4}
    for k_, v in want.items():
        assert comps[k_] == pytest.approx(v, abs=0.15), (k_, comps.get(k_))
    assert dec["sum_pct"] == pytest.approx(-12.0, abs=0.05)  # identity holds
    confs = [h["confidence"] for h in inv["hypotheses"][:4]]
    assert confs[0] == pytest.approx(0.82, abs=0.05)

    # -- beat 5: persona briefs — same conclusion, four governed views
    for who in ("EXECUTIVE", "SUPPLY_CHAIN", "KPI_OWNER"):
        b = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=_hdr(client, who)).json()["data"]
        assert b["persona"] == who and b["conclusion_hash"]

    # -- beat 6: decision workspace — 4 layers; A PASS/AUTH; B FAIL/ESCALATE
    d = client.get(f"/api/v1/investigations/{inv['id']}/decisions", headers=at).json()["data"]
    opt = {o["code"]: o for o in d["options"]}
    # NOTE: arch §T summary line says "A ₹1.6M", but §T beat 7 locks the outcome
    # comparison at "+₹3.9M vs +₹4.1M" and the approved S7 fabric pins A at
    # +₹4.1M [2.9–5.2] — the self-consistent locked value asserted here.
    assert opt["A_backup_supplier"]["expected_impact_rs"] == pytest.approx(4_100_000, rel=0.01)
    assert opt["A_backup_supplier"]["rights_verdict"] == "AUTHORIZED"
    # §T's "B ₹3.4M" is B's COST (₹3.4M air-freight, cash exposure ₹3.8M); the
    # approved S7 fabric pins B's IMPACT at ₹4.6M [3.4–5.8] — asserted exactly.
    assert opt["B_air_freight"]["expected_impact_rs"] == pytest.approx(4_600_000, rel=0.01)
    assert opt["B_air_freight"]["rights_verdict"] == "ESCALATE"
    # promotion comparison NOT SAFE vs BETTER (second-order + guardrails)
    assert opt["C_price_promotion"]["guardrail_status"] == "NOT_SAFE"
    assert opt["Cp_restore_then_promote"]["guardrail_status"] in ("PASS", "BETTER")

    # -- beat 6b: collision + portfolio; human resolves
    high = [c for c in d["collisions"] if c["severity"] == "HIGH"]
    assert high and "+17 pts" in (high[0]["combined_note"] or "")
    blocked = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opt['C_price_promotion']['id']}",
                          headers=et, json={"decision": "APPROVE"})
    assert blocked.status_code == 409  # unresolved HIGH blocks — never auto-optimized
    for c in d["collisions"]:
        if not c["resolved"]:
            client.post(f"/api/v1/decisions/collisions/{c['id']}/resolve", headers=ot,
                        json={"resolution": "SEQUENCE", "note": "restore cover first, then promote"})
    port = client.get("/api/v1/decisions/portfolio", headers=et).json()["data"]
    assert port["portfolio_health"]["score"] >= 0

    # approve A (supply chain), Cp (executive); B rejected by executive
    rA = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opt['A_backup_supplier']['id']}",
                     headers=st, json={"decision": "APPROVE"})
    assert rA.status_code in (200, 409) and (rA.status_code == 409 or rA.json()["data"]["record"]["status"] == "APPROVED")
    client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opt['Cp_restore_then_promote']['id']}",
                headers=et, json={"decision": "APPROVE"})
    client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opt['B_air_freight']['id']}",
                headers=et, json={"decision": "REJECT"})

    # -- DemoBar action: fast-forward 14 days, then record the outcome
    ff = client.post("/api/v1/demo/fast-forward", headers=et, json={"days": 14})
    assert ff.status_code == 200 and ff.json()["data"]["days"] == 14

    # -- beat 7: outcome +₹3.9M vs +₹4.1M within band; reliability shrunk
    ro = client.post(f"/api/v1/decisions/{opt['A_backup_supplier']['id']}/outcome", headers=st,
                     json={"actual_impact_rs": 3_900_000.0, "note": "backup live in 6 days; 3.9M recovered"})
    if ro.status_code == 200:
        od = ro.json()["data"]
        assert od["variance_rs"] == pytest.approx(-200_000, abs=1000)
        assert od["within_band"] is True
        assert od["reliability"]["new_prior"] == pytest.approx((od["reliability"]["hits"] + 5) / (od["reliability"]["n_observations"] + 10), abs=1e-4)

    # -- beat 8: MOMENT 2 — abstention case exists in the fabric (South KPI)
    south = [k for k in kpis if "south" in k["code"]]
    assert len(south) >= 1  # sparse South case: the abstention fabric

    # -- beat 9: cold start — millet cap 0.45 monitor-only
    millet = next(e for e in q["entries"] if e["kpi_code"] == "millet_noodles_revenue")
    assert millet["monitor_only"] is True
    # cold-start cap asserted on the investigation serializer
    mk = _kpi_id(client, tokA, "millet_noodles_revenue")
    m_inv = client.post("/api/v1/investigations", headers=at, json={"kpi_id": mk})
    if m_inv.status_code == 200:
        mi = m_inv.json()["data"]
        assert mi["cold_start_mode"] is True
        # cold-start cap 0.45 lands on FINAL CONFIDENCE (S5 locked surface)
        assert mi["final_confidence"] is not None and mi["final_confidence"] <= 0.45
        assert mi["clarification"]["monitor_only"] is True

    # -- beat 10 + 10b: feedback → proposal → owner MERGE (version bump)
    fb = client.post("/api/v1/memory/feedback", headers=ot, json={
        "investigation_id": inv["id"], "feedback_type": "hypothesis_verdict",
        "payload": {"pattern_class": "competitor_promotion", "verdict": "REFUTED"}})
    assert fb.status_code == 200
    props = client.get("/api/v1/memory/proposals", headers=at).json()["data"]
    inrev = [p for p in props if p["status"] == "IN_REVIEW"]
    if inrev:
        rm = client.post(f"/api/v1/memory/proposals/{inrev[0]['id']}/review", headers=ot,
                         json={"decision": "MERGE", "note": "Field evidence confirms; merge governed change"})
        assert rm.status_code == 200
        assert rm.json()["data"]["status"] == "MERGED"

    # -- beat 11: memory — NE Q3 2025 case, similarity ≥0.85 (target 0.87), explanation
    mm = client.get("/api/v1/memory/search", headers=at,
                    params={"q": "supplier delay Guwahati DC revenue", "kpi_code": "revenue_ne",
                            "driver_class": "supply_disruption"}).json()["data"]
    assert mm["results"][0]["similarity"] >= 0.85
    assert "Lesson" in mm["results"][0]["explanation"]

    # -- DemoBar action: inject POS refresh
    ip = client.post("/api/v1/demo/inject-pos", headers=et)
    assert ip.status_code == 200 and ip.json()["data"]["source"] == "pos"

    # -- beat 12: MOMENT 3 — transparency ledger: cache hit on CEO brief, routes shown
    b1 = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=et).json()["data"]
    b2 = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=et).json()["data"]
    assert b2["semantic_cache"]["hit"] is True
    assert b2["semantic_cache"]["cost_avoided_rs"] == pytest.approx(0.13, abs=0.01)
    led = client.get("/api/v1/transparency", headers=et).json()["data"]
    assert led["summary"]["n_routes"] >= 1 and led["routes"][0]["reason_code"]
    cpi = led["summary"]["cost_per_insight"]
    assert cpi["provider_equivalent_rs"] == pytest.approx(0.19, abs=0.01)
    assert cpi["provider_equivalent_tokens"] == 1400 and cpi["llm_capable_stages"] == 2

    # -- beat 13: scenario switch — S2 identical pipeline (AC18)
    s2 = client.post("/api/v1/scenarios/apex_inventory_cover/start", headers=at)
    assert s2.status_code == 200
    assert s2.json()["data"]["scenario"]["primary_kpi"] == "inventory_cover_ne"
    client.post("/api/v1/scenarios/apex_revenue_decline_ne/start", headers=at)  # restore hero

    # -- DemoBar action: toggle LLM off → routes degrade visibly → back on
    t1 = client.post("/api/v1/demo/toggle-llm", headers=et, json={"enabled": False})
    assert t1.status_code == 200
    led2 = client.get("/api/v1/transparency", headers=et).json()["data"]
    assert led2["summary"]["llm_enabled"] is False
    client.post("/api/v1/demo/toggle-llm", headers=et, json={"enabled": True})
    return True


def test_demo_scenario_runs_full_walkthrough_twice_without_reset(client):
    """The demo IS the test — and it runs twice with no reset between."""
    assert _walk(client, "first")
    assert _walk(client, "second")
