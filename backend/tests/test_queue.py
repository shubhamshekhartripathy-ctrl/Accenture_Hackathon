"""Queue integration — the landing beat: CRITICAL vs WATCH, cold start pinned, honest arithmetic."""
from __future__ import annotations


def test_queue_refresh_and_landing_beat(client, auth_headers):
    headers = auth_headers("analyst")
    resp = client.post("/api/v1/queue/refresh", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["skipped"] == []

    entries = data["queue"]
    by_code = {e["kpi_code"]: e for e in entries}

    revenue = by_code["revenue_ne"]
    assert revenue["band"] == "CRITICAL"                          # locked
    assert abs(revenue["deviation_pct"] - (-12.0)) < 0.1
    assert abs(revenue["robust_z"] - 5.1) < 0.15
    assert abs(revenue["exposure_rs"] - 8_600_000) < 15_000       # ₹8.6M exposure
    assert revenue["arithmetic"]["formula"]                        # inspectable "why CRITICAL?"
    assert revenue["arithmetic"]["strategic_weight"] == 0.8
    assert revenue["reliability"] is None or revenue["reliability"] is not None  # present pre-investigation

    marketing = by_code["marketing_roi"]
    assert marketing["band"] == "WATCH"                            # locked (floored, honestly recorded)
    assert marketing["arithmetic"]["floored"] is True
    assert abs(marketing["deviation_pct"] - (-4.0)) < 0.1
    assert abs(marketing["robust_z"] - 2.1) < 0.15
    assert abs(marketing["exposure_rs"] - 200_000) < 2_000

    millet = by_code["millet_noodles_revenue"]
    assert millet["band"] == "COLD START"
    assert millet["monitor_only"] is True
    assert millet["cold_start"] is True

    assert by_code["osa_ne"]["band"] == "ELEVATED"
    assert by_code["inventory_cover_ne"]["band"] == "ELEVATED"
    assert by_code["supplier_reliability"]["band"] == "WATCH"
    assert by_code["sales_per_outlet_south"]["band"] == "NOISE"    # off the executive radar until opened

    # CRITICAL sorts first; cold-start pinned last
    assert entries[0]["kpi_code"] == "revenue_ne"
    assert entries[-1]["kpi_code"] == "millet_noodles_revenue"


def test_queue_get_reads_stored_artifacts_only(client, auth_headers):
    headers = auth_headers("executive")
    resp = client.get("/api/v1/queue", headers=headers)
    assert resp.status_code == 200
    entries = resp.json()["data"]["entries"]
    assert entries, "stored artifacts from the refresh are served"


def test_queue_refresh_is_audited(client, auth_headers):
    client.post("/api/v1/queue/refresh", headers=auth_headers("analyst"))
    from app.db import SessionLocal
    from app.models.org import AuditEvent

    db = SessionLocal()
    try:
        assert db.query(AuditEvent).filter(AuditEvent.action == "queue.refresh").count() >= 1
    finally:
        db.close()


def test_supply_chain_cannot_refresh_queue(client, auth_headers):
    resp = client.post("/api/v1/queue/refresh", headers=auth_headers("supply_chain"))
    assert resp.status_code == 403
