"""S5 — Certainty / abstention (AC8, AC9): state machine, six fields, cold start, waiting cost."""
from __future__ import annotations

import math


def _tok(client, email="meera.analyst@apexfoods.example"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": "ReasonFlow#2026"}).json()["data"]["access_token"]


def _kpi(client, tok, code):
    return next(k["id"] for k in client.get("/api/v1/kpis", headers={"Authorization": f"Bearer {tok}"}).json()["data"] if k["code"] == code)


def _investigation(client, tok, kpi_id):
    made = client.post("/api/v1/investigations", headers={"Authorization": f"Bearer {tok}"}, json={"kpi_id": kpi_id})
    if made.status_code == 409:
        return client.get(f"/api/v1/investigations?kpi_id={kpi_id}", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]
    assert made.status_code == 200, made.text
    return made.json()["data"]


def test_hero_case_lands_act_with_caution_at_071(client, auth_headers):
    """0.82×0.86 → 0.71 ≥ 0.70 but the ERP↔GL definition conflict is active → caution is MANDATORY."""
    tok = _tok(client)
    inv = _investigation(client, tok, _kpi(client, tok, "revenue_ne"))
    assert inv["workflow_state"] == "RIGHTS_CHECKED"
    assert inv["certainty_state"] == "ACT_WITH_CAUTION"
    assert math.isclose(inv["final_confidence"], 0.71, abs_tol=0.005)
    assert any("definition conflict" in r.lower() for r in inv["certainty_reasons"])


def test_south_case_abstains_with_all_six_fields(client, auth_headers):
    """0.44 final < 0.50 AND tie 0.027 ≤ 0.05 → ABSTAINED; AC8 six fields present together."""
    tok = _tok(client)
    inv = _investigation(client, tok, _kpi(client, tok, "sales_per_outlet_south"))
    assert inv["workflow_state"] == "ABSTAINED"
    assert inv["certainty_state"] == "ABSTAIN"
    ab = inv["abstention"]
    for key in ("why_it_cannot_conclude", "what_evidence_conflicts", "what_information_is_missing",
                "what_would_resolve_it", "who_should_provide_it", "is_waiting_safer"):
        assert ab.get(key), f"missing abstention field: {key}"
    assert "tied" in ab["why_it_cannot_conclude"].lower()
    assert "0.47" in ab["why_it_cannot_conclude"] or "0.45" in ab["why_it_cannot_conclude"]
    assert "WAIT" in ab["is_waiting_safer"]
    assert any("tie" in r.lower() or "tied" in r.lower() for r in inv["certainty_reasons"])
    # ABSTAINED is terminal-for-decisions: no action options will be generated (verified in S7)


def test_abstained_case_not_blocked_for_rerun_after_data_fix(client, auth_headers):
    """ABSTAINED leaves the ACTIVE set — a refreshed feed may restart the case (S12)."""
    tok = _tok(client)
    kpi_id = _kpi(client, tok, "sales_per_outlet_south")
    _investigation(client, tok, kpi_id)
    again = client.post("/api/v1/investigations", headers={"Authorization": f"Bearer {tok}"}, json={"kpi_id": kpi_id})
    assert again.status_code == 200, again.text  # abstained ⇒ re-runnable


def test_cold_start_is_behaviour_not_label(client, auth_headers):
    """Millet: <13 periods ⇒ monitor-only, confidence capped 0.45, unlock conditions named."""
    tok = _tok(client)
    inv = _investigation(client, tok, _kpi(client, tok, "millet_noodles_revenue"))
    assert inv["workflow_state"] == "CLARIFY"
    assert inv["cold_start_mode"] is True
    assert inv["final_confidence"] <= 0.45
    cl = inv["clarification"]
    assert cl["monitor_only"] is True
    assert any("13" in u for u in cl["unlock_conditions"])
    assert cl["routed_to_role"] == "KPI_OWNER"
    assert any("COLD START" in r for r in inv["certainty_reasons"])


def test_certainty_persisted_and_replayed_identically(client, auth_headers):
    tok = _tok(client)
    kpi_id = _kpi(client, tok, "sales_per_outlet_south")
    a = _investigation(client, tok, kpi_id)
    b = client.get(f"/api/v1/investigations?kpi_id={kpi_id}", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]
    assert a["certainty_state"] == b["certainty_state"]
    assert a["abstention"]["why_it_cannot_conclude"] == b["abstention"]["why_it_cannot_conclude"]
    assert b["stage_events"][-1]["to_state"] == "ABSTAINED"  # transition persisted


def test_certainty_events_on_sse_replay(client, auth_headers):
    tok = _tok(client)
    kpi_id = _kpi(client, tok, "sales_per_outlet_south")
    inv = _investigation(client, tok, kpi_id)
    with client.stream(
        "GET", f"/api/v1/investigations/{inv['id']}/events?replay=true",
        headers={"Authorization": f"Bearer {tok}"},
    ) as resp:
        assert resp.status_code == 200
        seen = []
        for line in resp.iter_lines():
            if line.startswith("event:"):
                seen.append(line.split(":", 1)[1].strip())
            if len(seen) > 40:
                break
    assert "certainty_state_determined" in seen
    assert "investigation_abstained" in seen
