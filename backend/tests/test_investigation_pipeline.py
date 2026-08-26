"""Investigation pipeline prefix: AC1 gate, workflow transitions, telemetry, SSE."""
from __future__ import annotations


def _revenue_kpi_id(client, headers) -> str:
    return next(k["id"] for k in client.get("/api/v1/kpis", headers=headers).json()["data"] if k["code"] == "revenue_ne")


def test_create_investigation_runs_prefix_to_explaining(client, auth_headers):
    """S3: the pipeline prefix now extends through decomposition (EXPLAINING)."""
    headers = auth_headers("analyst")
    kpi_id = _revenue_kpi_id(client, headers)
    resp = client.post("/api/v1/investigations", headers=headers, json={"kpi_id": kpi_id})
    if resp.status_code == 409:
        inv = client.get(f"/api/v1/investigations?kpi_id={kpi_id}", headers=headers).json()["data"][0]
    else:
        assert resp.status_code == 200, resp.text
        inv = resp.json()["data"]

    assert inv["workflow_state"] in ("RIGHTS_CHECKED", "DECISION_RECORD_CREATED", "PORTFOLIO_UPDATED", "HUMAN_APPROVAL", "APPROVED", "REJECTED", "OVERRIDDEN")
    assert inv["contract_version"] >= 1                          # pinned
    assert abs(inv["reliability"] - 0.76) < 0.005                # Moment 1 captured on the investigation
    assert abs(inv["confidence_cap"] - 0.86) < 0.005
    assert inv["working_value"] == 84.0
    assert inv["materiality"]["band"] == "CRITICAL"
    states = [e["to_state"] for e in inv["stage_events"]]
    prefix = ["RECONCILING", "RECONCILED", "DETECTING", "DETECTED", "TRIAGED", "EXPLAINING", "EXPLAINED", "CERTAINTY_DECISION", "DECISION_OPTIONS_GENERATED", "SIMULATED", "GUARDRAILS_CHECKED", "SECOND_ORDER_ANALYZED", "COLLISIONS_CHECKED", "RIGHTS_CHECKED"]
    assert states[: len(prefix)] == prefix  # a session-mate may already have approved
    assert all(e["ok"] for e in inv["stage_events"])

    # Telemetry: 7 stage rows, zero LLM — deterministic offline pipeline
    t = inv["telemetry"]
    assert t["stages"] >= 7
    assert t["llm_stages"] == 0
    assert t["numbers_computed_without_llm_pct"] == 100.0


def test_investigation_requires_governed_kpi(client, auth_headers):
    """AC1 end-to-end: a KPI without a governed contract cannot be investigated."""
    from app.db import SessionLocal
    from app.models.kpi import Kpi

    db = SessionLocal()
    try:
        org_id = db.query(Kpi).first().organization_id
        ghost = Kpi(organization_id=org_id, code="ungoverned_kpi", name="Ungoverned",
                    category="REVENUE", region="NE", unit="INR_M")
        db.add(ghost)
        db.commit()
        ghost_id = ghost.id
    finally:
        db.close()
    resp = client.post(
        "/api/v1/investigations", headers=auth_headers("analyst"), json={"kpi_id": ghost_id}
    )
    assert resp.status_code == 409
    body = resp.json()["error"]
    assert body["code"] == "CONTRACT_REQUIRED"
    assert "governed" in body["message"].lower()


def test_duplicate_active_investigation_refused(client, auth_headers):
    headers = auth_headers("analyst")
    kpi_id = _revenue_kpi_id(client, headers)
    first = client.post("/api/v1/investigations", headers=headers, json={"kpi_id": kpi_id})
    if first.status_code == 409:  # already created by an earlier test — also correct
        assert first.json()["error"]["code"] == "INVESTIGATION_EXISTS"
        return
    assert first.status_code == 200
    second = client.post("/api/v1/investigations", headers=headers, json={"kpi_id": kpi_id})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "INVESTIGATION_EXISTS"
    assert second.json()["error"]["details"]["investigation_id"] == first.json()["data"]["id"]


def test_supply_chain_can_create_investigation(client, auth_headers):
    headers = auth_headers("supply_chain")
    kpi_id = _revenue_kpi_id(client, auth_headers("analyst"))
    resp = client.post("/api/v1/investigations", headers=headers, json={"kpi_id": kpi_id})
    assert resp.status_code in (200, 409)  # 409 = investigation already exists (valid)


def test_sse_progress_events_safe_and_bounded(client, auth_headers):
    """SSE replays buffered events, includes safe stage messages, closes with done."""
    headers = auth_headers("analyst")
    kpi_id = _revenue_kpi_id(client, headers)
    created = client.post("/api/v1/investigations", headers=headers, json={"kpi_id": kpi_id})
    inv_id = created.json()["data"]["id"] if created.status_code == 200 else (
        client.get("/api/v1/investigations", headers=headers).json()["data"][0]["id"]
    )
    with client.stream(
        "GET", f"/api/v1/investigations/{inv_id}/events?follow=false", headers=headers
    ) as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        events = []
        for line in stream.iter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if line.startswith("event: done"):
                break
    assert "investigation_started" in events
    assert "reconciliation_complete" in events
    assert "detection_complete" in events
    assert "triage_complete" in events
    assert events[-1] == "done"
    # Safe operational messages only — no chain-of-thought vocabulary
    joined = " ".join(events).lower()
    for forbidden in ("thought", "prompt", "chain", "reasoning trace"):
        assert forbidden not in joined


def test_sse_replay_survives_process_restart(client, auth_headers):
    """After a restart the in-memory buffer is gone; replay must rebuild from the
    persisted stage-event log and still close with done (arch Q — refresh never
    loses state, deterministic replay preserved)."""
    from app.services.pipeline import events as bus

    headers = auth_headers("analyst")
    kpi_id = _revenue_kpi_id(client, headers)
    created = client.post("/api/v1/investigations", headers=headers, json={"kpi_id": kpi_id})
    inv_id = created.json()["data"]["id"] if created.status_code == 200 else (
        client.get("/api/v1/investigations", headers=headers).json()["data"][0]["id"]
    )

    bus._buffers.clear()  # simulate: new process, empty buffer

    with client.stream(
        "GET", f"/api/v1/investigations/{inv_id}/events?follow=false", headers=headers
    ) as stream:
        assert stream.status_code == 200
        events = []
        for line in stream.iter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if line.startswith("event: done"):
                break
    assert "investigation_started" in events
    assert "reconciliation_complete" in events
    assert "triage_complete" in events
    assert "prefix_complete" in events
    assert events[-1] == "done"
