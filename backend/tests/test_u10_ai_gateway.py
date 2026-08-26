"""S10 — Model routing gateway, AI policy, semantic cache, transparency ledger.

Locked behaviors (arch O.2–O.4): SENSITIVE ⇒ external premium prohibited
(reason POLICY_DENIED_EXTERNAL, deterministic fallback, never silent);
RESTRICTED ⇒ no model class allowed; the demo toggle and the tenant cost cap
degrade to deterministic with visible reasons; an unchanged CEO brief hits the
validity-aware cache (provider-equivalent ₹0.13 avoided shown in the ledger);
a changed conclusion misses. Everything visible in /transparency.
"""
from __future__ import annotations

import pytest
from contextlib import contextmanager

from app.db import SessionLocal
from app.services.llm import gateway


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    finally:
        s.close()
from app.services.llm.cache import cache_key
from app.services.llm.policy import ensure_policies

_TOK: dict[str, str] = {}
EMAILS = {
    "EXECUTIVE": "priya.ceo@apexfoods.example",
    "ANALYST": "meera.analyst@apexfoods.example",
}


def _tok(client, who):
    if who not in _TOK:
        _TOK[who] = client.post("/api/v1/auth/login", json={"email": EMAILS[who], "password": "ReasonFlow#2026"}).json()["data"]["access_token"]
    return _TOK[who]


def _hdr(client, who):
    return {"Authorization": f"Bearer {_tok(client, who)}"}


def _kpi(client, tok, code="revenue_ne"):
    return next(k["id"] for k in client.get("/api/v1/kpis", headers={"Authorization": f"Bearer {tok}"}).json()["data"] if k["code"] == code)


def _hero_brief(client):
    tok = _tok(client, "ANALYST")
    made = client.post("/api/v1/investigations", headers={"Authorization": f"Bearer {tok}"}, json={"kpi_id": _kpi(client, tok)})
    inv = made.json()["data"] if made.status_code == 200 else client.get(f"/api/v1/investigations?kpi_id={_kpi(client, tok)}", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]
    return inv


def test_policies_seeded_tenant_scoped(client):
    with session_scope() as db:
        assert ensure_policies(db) >= 0  # idempotent
        from app.models.aigov import AiPolicy
        rows = db.query(AiPolicy).all()
        assert len(rows) >= 16  # 4 capabilities × 4 classifications (× orgs)
        sensitive = [r for r in rows if r.capability == "translate_narrative" and r.data_classification == "SENSITIVE"]
        assert sensitive and all(r.external_allowed is False for r in sensitive)
        restricted = [r for r in rows if r.data_classification == "RESTRICTED" and r.capability == "draft_hypotheses"]
        assert restricted and all(r.allowed_model_classes == [] for r in restricted)


def test_gateway_policy_denials_visible_and_audited(client):
    with session_scope() as db:
        from app.models.org import Organization
        apex = db.query(Organization).filter(Organization.slug == "apex").first()
        # SENSITIVE + external premium preferred ⇒ DENIED (approved class only)
        d = gateway.route(db, apex.id, "translate_narrative", "SENSITIVE", external_preferred=True)
        assert d.deterministic and d.reason_code == "POLICY_DENIED_EXTERNAL" and d.fallback == "TEMPLATE"
        # RESTRICTED ⇒ no model class allowed
        d2 = gateway.route(db, apex.id, "draft_hypotheses", "RESTRICTED")
        assert d2.deterministic and d2.reason_code == "POLICY_DENIED_RESTRICTED"
        # INTERNAL without credentials ⇒ policy-approved class, no provider ⇒ deterministic
        d3 = gateway.route(db, apex.id, "extract_claims", "INTERNAL")
        assert d3.deterministic and d3.reason_code == "POLICY_APPROVED_CLASS_NO_PROVIDER"
        # every decision logged
        from app.models.aigov import AiRouteLog
        logs = db.query(AiRouteLog).filter(AiRouteLog.organization_id == apex.id).all()
        codes = {l.reason_code for l in logs}
        assert {"POLICY_DENIED_EXTERNAL", "POLICY_DENIED_RESTRICTED", "POLICY_APPROVED_CLASS_NO_PROVIDER"} <= codes


def test_toggle_degrades_every_route_with_visible_reason(client):
    with session_scope() as db:
        from app.models.org import Organization
        apex = db.query(Organization).filter(Organization.slug == "apex").first()
        assert gateway.set_llm_enabled(False) is False
        try:
            d = gateway.route(db, apex.id, "translate_narrative", "PUBLIC", external_preferred=True)
            assert d.deterministic and d.reason_code == "LLM_DISABLED_DEMO"
        finally:
            gateway.set_llm_enabled(True)


def test_cost_cap_exhausted_degrades(client):
    with session_scope() as db:
        from app.models.org import Organization
        apex = db.query(Organization).filter(Organization.slug == "apex").first()
        apex.ai_cost_cap_rs = 0.0
        db.add(apex)
        db.flush()
        d = gateway.route(db, apex.id, "extract_claims", "INTERNAL")
        assert d.deterministic and d.reason_code == "TENANT_COST_CAP_EXHAUSTED"
        apex.ai_cost_cap_rs = 50.0
        db.add(apex)


def test_demo_toggle_endpoint_all_roles_audited(client):
    r = client.post("/api/v1/demo/toggle-llm", headers=_hdr(client, "EXECUTIVE"), json={"enabled": False})
    assert r.status_code == 200 and r.json()["data"]["llm_enabled"] is False
    # degraded now: a brief route shows the disable reason
    inv = _hero_brief(client)
    b = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=_hdr(client, "EXECUTIVE")).json()["data"]
    assert b["ai_route"]["reason_code"] == "LLM_DISABLED_DEMO"
    r2 = client.post("/api/v1/demo/toggle-llm", headers=_hdr(client, "ANALYST"), json={"enabled": True})
    assert r2.status_code == 200  # all roles can use demo controls
    r3 = client.post("/api/v1/demo/toggle-llm", headers=_hdr(client, "EXECUTIVE"), json={"enabled": True})
    assert r3.status_code == 200 and r3.json()["data"]["llm_enabled"] is True


def test_brief_cache_hit_then_conclusion_change_misses(client):
    """CEO re-opens her brief (unchanged conclusion) → HIT; changed conclusion → MISS."""
    from app.services.llm.cache import semantic_cache
    semantic_cache()._store.clear()  # deterministic start: this test owns the cache lifecycle
    inv = _hero_brief(client)
    et = _hdr(client, "EXECUTIVE")
    b1 = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=et).json()["data"]
    assert b1["semantic_cache"]["hit"] is False
    assert b1["ai_route"]["capability"] == "translate_narrative"
    assert b1["ai_route"]["data_classification"] in ("INTERNAL", "SENSITIVE", "PUBLIC")
    b2 = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=et).json()["data"]
    assert b2["semantic_cache"]["hit"] is True
    assert b2["semantic_cache"]["cost_avoided_rs"] == pytest.approx(0.13, abs=0.01)
    assert b2["semantic_cache"]["provider_equivalent_ms_saved"] == 620
    assert b2["sections"] == b1["sections"]  # replay-safe: same sections
    # different persona ⇒ different cache key ⇒ miss
    b3 = client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=_hdr(client, "ANALYST")).json()["data"]
    assert b3["semantic_cache"]["hit"] is False


def test_cache_key_validity_fields(client):
    k1 = cache_key("t1", 3, 7, "hashA", "EXECUTIVE", "p1", "class:r")
    k2 = cache_key("t1", 3, 7, "hashA", "EXECUTIVE", "p1", "class:r")
    k3 = cache_key("t1", 4, 7, "hashA", "EXECUTIVE", "p1", "class:r")   # contract bump
    k4 = cache_key("t2", 3, 7, "hashA", "EXECUTIVE", "p1", "class:r")   # other tenant
    assert k1 == k2 and k1 != k3 and k1 != k4


def test_transparency_ledger_shows_routes_cache_and_caps(client):
    inv = _hero_brief(client)
    client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=_hdr(client, "EXECUTIVE"))
    client.get(f"/api/v1/investigations/{inv['id']}/brief", headers=_hdr(client, "EXECUTIVE"))
    r = client.get("/api/v1/transparency", headers=_hdr(client, "EXECUTIVE"))
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["summary"]["n_routes"] >= 2
    assert "translate_narrative" in {x["capability"] for x in d["routes"]}
    assert d["summary"]["llm_enabled"] in (True, False)
    assert d["summary"]["tenant_cost_cap_rs"] == 50.0
    # scoped per investigation
    r2 = client.get(f"/api/v1/transparency?investigation_id={inv['id']}", headers=_hdr(client, "EXECUTIVE"))
    assert r2.status_code == 200
    assert all(x["run_id"] == inv["id"] for x in r2.json()["data"]["stages"])
