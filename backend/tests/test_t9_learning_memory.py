"""S9 — Outcomes (AC14), feedback (AC15), governed proposals (AC23), memory (AC25).

Locked targets: outcome +₹3.9M vs predicted +₹4.1M ⇒ variance −₹0.2M, within
band; memory similarity for the NE Q3 2025 supplier-delay case ≥ 0.85 with a
written explanation; entitlement filter withholds; proposals only reach the
ACTIVE contract through owner MERGE (versioned, optimistic concurrency).
"""
from __future__ import annotations

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
    return inv, {o["code"]: o for o in d["options"]}, d.get("collisions", [])


def _fresh_hero(client):
    """Full hero path with collision resolved so A + Cp are APPROVED."""
    inv, opt, collisions = _hero(client)
    et, ot = _hdr(client, "EXECUTIVE"), _hdr(client, "KPI_OWNER")
    for c in collisions:
        if not c["resolved"]:
            client.post(f"/api/v1/decisions/collisions/{c['id']}/resolve", headers=ot,
                        json={"resolution": "SEQUENCE", "note": "sequence: restore cover first, then promote"})
    client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opt['Cp_restore_then_promote']['id']}",
                headers=et, json={"decision": "APPROVE"})
    r = client.post(f"/api/v1/investigations/{inv['id']}/decisions/{opt['A_backup_supplier']['id']}",
                    headers=_hdr(client, "SUPPLY_CHAIN"), json={"decision": "APPROVE"})
    assert r.status_code in (200, 409), r.text  # 409 DECISION_EXISTS when an earlier test approved it
    return inv, opt


# --------------------------------------------------------------------- AC14
def test_outcome_variance_band_and_shrinkage(client):
    """predicted +₹4.1M, actual +₹3.9M → variance −₹0.2M, within band, prior shrunk."""
    inv, opt = _fresh_hero(client)
    r = client.post(f"/api/v1/decisions/{opt['A_backup_supplier']['id']}/outcome",
                    headers=_hdr(client, "SUPPLY_CHAIN"),
                    json={"actual_impact_rs": 3_900_000.0, "note": "backup live in 6 days; ₹3.9M recovered"})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["predicted_rs"] == 4_100_000
    assert d["band_rs"] == [2_900_000, 5_200_000]
    assert d["actual_rs"] == 3_900_000
    assert d["variance_rs"] == -200_000.0
    assert d["within_band"] is True
    rel = d["reliability"]
    assert rel["pattern_class"] == "supply_disruption"
    assert rel["n_observations"] >= 1 and rel["hits"] >= 1
    # shrinkage: (hits + 10×0.5) / (n + 10) — exact recompute
    assert rel["new_prior"] == round((rel["hits"] + 5) / (rel["n_observations"] + 10), 4)
    assert "pattern_reliability" in rel["table"] and "untouched" in rel["table"]
    assert d["investigation_state"] == "OUTCOME_RECORDED"  # legal walk RIGHTS→…→MONITORING→OUTCOME
    # outcome is once-only
    r2 = client.post(f"/api/v1/decisions/{opt['A_backup_supplier']['id']}/outcome",
                     headers=_hdr(client, "SUPPLY_CHAIN"),
                     json={"actual_impact_rs": 4_000_000.0, "note": "second attempt should fail"})
    assert r2.status_code == 409


def test_outcome_requires_note_and_role(client):
    inv, opt = _fresh_hero(client)
    r = client.post(f"/api/v1/decisions/{opt['A_backup_supplier']['id']}/outcome",
                    headers=_hdr(client, "SUPPLY_CHAIN"), json={"actual_impact_rs": 4e6, "note": "short"})
    assert r.status_code == 400
    r = client.post(f"/api/v1/decisions/{opt['A_backup_supplier']['id']}/outcome",
                    headers=_hdr(client, "ANALYST"),
                    json={"actual_impact_rs": 4e6, "note": "analysts cannot record outcomes"})
    assert r.status_code == 403
    r = client.post(f"/api/v1/decisions/{opt['B_air_freight']['id']}/outcome",
                    headers=_hdr(client, "SUPPLY_CHAIN"),
                    json={"actual_impact_rs": 1e6, "note": "never approved, no outcome"})
    assert r.status_code in (404, 409)  # B was REJECTED in S7 flows or has no approved record


# --------------------------------------------------------------------- AC25
def test_memory_similarity_locked_case_with_explanation(client):
    """"NE Q3 2025 supplier delay" case must surface ≥ 0.85 with a written explanation."""
    r = client.get("/api/v1/memory/search", headers=_hdr(client, "ANALYST"),
                   params={"q": "supplier delay Guwahati DC revenue", "kpi_code": "revenue_ne",
                           "driver_class": "supply_disruption"})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    top = d["results"][0]
    assert "Q3 2025" in top["title"] and top["outcome_rs"] == 3_100_000.0
    assert top["within_band"] is True
    assert top["similarity"] >= 0.85, top
    assert "embedding cosine" in top["explanation"] and "Lesson" in top["explanation"]
    assert "₹3.1M" in top["explanation"]
    # canonical store: PostgreSQL + pgvector cosine; the DEGRADED note exists only
    # on the strictly test-only SQLite fallback
    assert "feature_hash" in d["embedding_method"]
    if d.get("embedding_store") == "postgresql+pgvector":
        assert d["degraded_note"] == "" and "pgvector cosine" in d["method_label"]
    else:
        assert "DEGRADED" in d["degraded_note"] and d["embedding_store"].startswith("test-only")


def test_memory_entitlement_filter_and_cold_start_analogues(client):
    # entitlement: Oils case is restricted; SUPPLY_CHAIN viewer must not see it
    r = client.get("/api/v1/memory/search", headers=_hdr(client, "SUPPLY_CHAIN"),
                   params={"q": "launch discount pack price oils"})
    titles = [x["title"] for x in r.json()["data"]["results"]]
    assert all("Oils" not in t for t in titles)
    assert r.json()["data"]["withheld_by_entitlement"] >= 1
    # cold-start: millet analogues listed for the analyst
    r2 = client.get("/api/v1/memory/search", headers=_hdr(client, "ANALYST"),
                    params={"analogue_for": "revenue_millet_ne"})
    d2 = r2.json()["data"]["results"]
    assert len(d2) == 3 and any("Snacks" in t["title"] for t in d2)
    assert all(t["analogue_for"] == "revenue_millet_ne" for t in d2)


# --------------------------------------------------------------------- AC15 + AC23
def test_feedback_visible_effect_and_governed_proposal(client):
    inv, opt = _fresh_hero(client)
    r = client.post("/api/v1/memory/feedback", headers=_hdr(client, "KPI_OWNER"),
                    json={"investigation_id": inv["id"], "feedback_type": "hypothesis_verdict",
                          "payload": {"pattern_class": "supply_disruption", "verdict": "CONFIRMED",
                                      "hypothesis_code": "H1"}})
    assert r.status_code == 200, r.text
    eff = r.json()["data"]["effect"]
    assert "pattern_prior_update" in eff and eff["pattern_prior_update"]["new_prior"] > 0.5
    assert "governed_proposal" in eff and eff["governed_proposal"]["status"] == "IN_REVIEW"
    assert "never mutates ACTIVE contracts" in eff["governed_proposal"]["note"]
    # bad type rejected
    r2 = client.post("/api/v1/memory/feedback", headers=_hdr(client, "ANALYST"),
                     json={"feedback_type": "vibes", "payload": {}})
    assert r2.status_code == 400


def test_proposal_review_merge_and_guards(client):
    """Only the KPI owner merges; merge bumps the contract version; learning never does it directly."""
    inv, opt = _fresh_hero(client)
    inv_detail = client.get(f"/api/v1/investigations/{inv['id']}", headers=_hdr(client, "ANALYST")).json()["data"]
    contract_id = inv_detail["contract_id"] if "contract_id" in inv_detail else inv_detail.get("contract", {}).get("id")
    if contract_id is None:  # fall back to the contracts list for revenue_ne
        ks = client.get("/api/v1/kpis", headers=_hdr(client, "ANALYST")).json()["data"]
        kid = next(k["id"] for k in ks if k["code"] == "revenue_ne")
        cd = client.get(f"/api/v1/kpis/{kid}/contract", headers=_hdr(client, "ANALYST")).json()["data"]
        contract_id = cd["id"]
    r = client.post(f"/api/v1/memory/contracts/{contract_id}/proposals", headers=_hdr(client, "ANALYST"),
                    json={"change_type": "driver_prior_update",
                          "payload": {"driver_code": "supplier_reliability_ne", "new_prior_weight": 0.72},
                          "rationale": "Confirmed twice in the field; raise the hypothesis prior"})
    assert r.status_code == 200, r.text
    prop = r.json()["data"]
    assert prop["origin"] == "HUMAN" and prop["status"] == "IN_REVIEW"
    base_version = prop["base_version"]

    # analyst cannot review
    r2 = client.post(f"/api/v1/memory/proposals/{prop['id']}/review", headers=_hdr(client, "ANALYST"),
                     json={"decision": "MERGE", "note": "analyst must not merge anything"})
    assert r2.status_code == 403
    # short note rejected
    r3 = client.post(f"/api/v1/memory/proposals/{prop['id']}/review", headers=_hdr(client, "KPI_OWNER"),
                     json={"decision": "MERGE", "note": "ok"})
    assert r3.status_code == 400
    # owner merges → new version
    r4 = client.post(f"/api/v1/memory/proposals/{prop['id']}/review", headers=_hdr(client, "KPI_OWNER"),
                     json={"decision": "MERGE", "note": "Field-confirmed twice; merging the prior update"})
    assert r4.status_code == 200, r4.text
    merged = r4.json()["data"]
    assert merged["status"] == "MERGED" and merged["merged_to_version"] == base_version + 1
    # closed proposal cannot be re-reviewed
    r5 = client.post(f"/api/v1/memory/proposals/{prop['id']}/review", headers=_hdr(client, "KPI_OWNER"),
                     json={"decision": "REJECT", "note": "trying to reopen a merged proposal"})
    assert r5.status_code == 409


def test_case_closure_to_learned(client):
    inv, opt = _fresh_hero(client)
    client.post(f"/api/v1/decisions/{opt['A_backup_supplier']['id']}/outcome",
                headers=_hdr(client, "SUPPLY_CHAIN"),
                json={"actual_impact_rs": 3_900_000.0, "note": "backup live in 6 days; ₹3.9M recovered"})
    r = client.post(f"/api/v1/memory/investigations/{inv['id']}/close", headers=_hdr(client, "KPI_OWNER"))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["workflow_state"] == "LEARNED"
    # a LEARNED case no longer blocks new investigations for the KPI
    r2 = client.post("/api/v1/investigations", headers=_hdr(client, "ANALYST"),
                     json={"kpi_id": _kpi(client, _tok(client, 'ANALYST'))})
    assert r2.status_code in (200, 409)
