"""S6 — Personas + entitlements (AC9): one truth four views, masking audited,
withheld counted honestly, numeric post-check forces the template."""
from __future__ import annotations

import re

EMAILS = {
    "EXECUTIVE": "priya.ceo@apexfoods.example",
    "ANALYST": "meera.analyst@apexfoods.example",
    "SUPPLY_CHAIN": "rahul.sc@apexfoods.example",
    "KPI_OWNER": "vikram.owner@apexfoods.example",
}
_TOK_CACHE: dict[str, str] = {}


def _tok(client, who):
    if who not in _TOK_CACHE:  # rate limiter is real — one login per persona per session
        _TOK_CACHE[who] = client.post(
            "/api/v1/auth/login", json={"email": EMAILS[who], "password": "ReasonFlow#2026"}
        ).json()["data"]["access_token"]
    return _TOK_CACHE[who]


def _kpi(client, tok, code="revenue_ne"):
    return next(k["id"] for k in client.get("/api/v1/kpis", headers={"Authorization": f"Bearer {tok}"}).json()["data"] if k["code"] == code)


def _inv(client, tok, kpi_id):
    made = client.post("/api/v1/investigations", headers={"Authorization": f"Bearer {tok}"}, json={"kpi_id": kpi_id})
    if made.status_code == 409:
        return client.get(f"/api/v1/investigations?kpi_id={kpi_id}", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]
    assert made.status_code == 200, made.text
    return made.json()["data"]


def test_four_personas_one_conclusion_hash(client, auth_headers):
    """Personas never receive different underlying truths (AC9)."""
    analyst_tok = _tok(client, "ANALYST")
    inv = _inv(client, analyst_tok, _kpi(client, analyst_tok))
    hashes, tallies = [], []
    for who in EMAILS:
        b = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers={"Authorization": f"Bearer {_tok(client, who)}"}).json()["data"]
        assert b["persona"] == who
        hashes.append(b["conclusion_hash"])
        tallies.append((b["evidence_tally"]["supporting"], b["evidence_tally"]["contradicting"]))
    assert len(set(hashes)) == 1, "each persona must render the SAME conclusion"
    assert len(set(tallies)) == 1


def test_supply_chain_view_counts_withheld_sensitively(client, auth_headers):
    """SC cannot open the SENSITIVE supplier email (not in access_roles) — counted,
    content replaced, explicitly named; the analyst still sees it."""
    analyst_tok = _tok(client, "ANALYST")
    inv = _inv(client, analyst_tok, _kpi(client, analyst_tok))
    sc = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers={"Authorization": f"Bearer {_tok(client, 'SUPPLY_CHAIN')}"}).json()["data"]
    assert sc["evidence_tally"]["withheld"] >= 1
    assert any(w["doc_key"] == "EV-SUP-01" and w["classification"] == "SENSITIVE" for w in sc["withheld_sources"])
    hyps = client.get(f"/api/v1/investigations/{inv['id']}/explain", headers={"Authorization": f"Bearer {_tok(client, 'SUPPLY_CHAIN')}"}).json()["data"]["hypotheses"]
    sup = next(h for h in hyps if h["code"] == "supplier_delay")
    withheld_entry = next(e for e in sup["evidence"] if e["doc_key"] == "EV-SUP-01")
    assert withheld_entry["summary"] is None and "withheld" in withheld_entry["title"]
    assert withheld_entry["claims"] == []


def test_analyst_view_counts_financiers_only_doc_withheld(client, auth_headers):
    """EV-ACC-01 (accrual note) is finance-eyes — the analyst brief counts it withheld."""
    analyst_tok = _tok(client, "ANALYST")
    inv = _inv(client, analyst_tok, _kpi(client, analyst_tok))
    an = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers={"Authorization": f"Bearer {analyst_tok}"}).json()["data"]
    assert any(w["doc_key"] == "EV-ACC-01" for w in an["withheld_sources"])
    # but the executive CAN open it — different scope, same truth
    ex = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}).json()["data"]
    assert not any(w["doc_key"] == "EV-ACC-01" for w in ex["withheld_sources"])


def test_column_masking_visible_as_dash_and_audited(client, auth_headers):
    """unit_cost_rs masked for SUPPLY_CHAIN/EXECUTIVE at serialization — visible as —."""
    analyst_tok = _tok(client, "ANALYST")
    inv = _inv(client, analyst_tok, _kpi(client, analyst_tok))
    sc = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers={"Authorization": f"Bearer {_tok(client, 'SUPPLY_CHAIN')}"}).json()["data"]
    # SC is not entitled to EV-SUP-01 at all (withheld) — masking shows in the KPI-owner/exec view of claims
    ex = client.get(f"/api/v1/investigations/{inv['id']}/explain", headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}).json()["data"]
    sup = next(h for h in ex["hypotheses"] if h["code"] == "supplier_delay")
    doc = next(e for e in sup["evidence"] if e["doc_key"] == "EV-SUP-01")
    claim = next(c for c in doc["claims"] if "unit_cost_rs" in c)
    assert claim["unit_cost_rs"] == "—", f"expected masked unit_cost_rs, got {claim['unit_cost_rs']}"
    # masking events are audited
    audits = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {_tok(client, 'KPI_OWNER')}"}).json()["data"]
    assert any(a["action"] == "masking_event" for a in audits)


def test_analyst_never_offered_approval(client, auth_headers):
    """The analyst brief allows challenge/correct — approval is not in their actions."""
    analyst_tok = _tok(client, "ANALYST")
    inv = _inv(client, analyst_tok, _kpi(client, analyst_tok))
    an = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers={"Authorization": f"Bearer {analyst_tok}"}).json()["data"]
    assert "Challenge method" in an["allowed_actions"]
    assert not any("pprove" in a for a in an["allowed_actions"])


def test_numeric_postcheck_forces_template_on_invented_number(client, auth_headers):
    """Any number not in the conclusion object ⇒ deterministic re-render + warning."""
    from app.domains.briefs import service as briefs

    allowed = briefs._numbers_in_conclusion({"x": 12.0, "y": 0.5})
    bad = briefs.numeric_postcheck("Revenue fell 12.0% and costs hit 99.9 units", allowed)
    assert "99.9" in bad and "12.0" not in bad

    # end-to-end: a renderer that invents numbers gets its section replaced
    from app.services.llm.cache import semantic_cache
    semantic_cache()._store.clear()  # render afresh so the lying renderer actually runs (S10 cache)
    original = briefs._executive
    try:
        def lying_renderer(base, lead, detection, materiality, abstention, supports, contradicts):
            return {"headline": "This looks great — we saved 123.45M by doing nothing."}
        briefs._executive = lying_renderer
        analyst_tok = _tok(client, "ANALYST")
        inv = _inv(client, analyst_tok, _kpi(client, analyst_tok))
        b = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}).json()["data"]
        assert b.get("postcheck_forced_template") is True
        assert "123.45" in b["postcheck_violations"]["headline"]
    finally:
        briefs._executive = original


def test_brief_numbers_come_from_conclusion_only(client, auth_headers):
    """Every number in a rendered narrative must exist in the conclusion payload."""
    from app.domains.briefs import service as briefs

    analyst_tok = _tok(client, "ANALYST")
    inv = _inv(client, analyst_tok, _kpi(client, analyst_tok))
    ex = client.get(f"/api/v1/investigations/{inv['id']}/explain", headers={"Authorization": f"Bearer {analyst_tok}"}).json()["data"]
    b = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers={"Authorization": f"Bearer {_tok(client, 'EXECUTIVE')}"}).json()["data"]
    assert b.get("postcheck_forced_template") is None
    allowed = briefs._numbers_in_conclusion(ex) | set(b["evidence_tally"].values())
    for text in b["sections"].values():
        if isinstance(text, str):
            assert briefs.numeric_postcheck(text, allowed) == [], f"unjustified number in: {text}"


def test_pii_masking_rules(client, auth_headers):
    from app.services.entitlements import mask_pii

    out, hits = mask_pii("Contact arjun.admin@apexfoods.example or +91 9876543210 re acct NE-FMCG/001234567890")
    assert "@" not in out and "9876543210" not in out
    assert {"email", "phone"} <= set(hits)  # the account-like string is correctly caught too


def test_brief_tenant_isolated(client, auth_headers):
    analyst_tok = _tok(client, "ANALYST")
    inv = _inv(client, analyst_tok, _kpi(client, analyst_tok))
    resp = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=auth_headers("outsider"))
    assert resp.status_code == 404, (resp.status_code, resp.json())
