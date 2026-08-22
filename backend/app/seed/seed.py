"""Idempotent seed entrypoint — runs on app boot when SEED_ON_BOOT is set.

Installs: two tenants (Apex Foods demo + Meridian Retail isolation proof),
five personas, five heterogeneous sources, seven KPIs with governed contracts
(sources/drivers/thresholds/rights/entitlements/relations), three scenario
templates. Deterministic: identical every run.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..db import Base, SessionLocal, engine
from .fabric_kpis import ensure_contracts, ensure_kpis, ensure_relations
from .fabric_evidence import ensure_evidence
from .fabric_impacts import ensure_impacts
from .fabric_memory import ensure_memory
from .fabric_observations import ensure_observations
from .fabric_org import ensure_meridian, ensure_org, ensure_sources, ensure_users
from .fabric_scenarios import ensure_scenarios

log = logging.getLogger("reasonflow.seed")


def ensure_demo_artifacts(db: Session, org_id: str) -> dict:
    """Idempotent boot materialization: queue + first reconciliation per KPI.

    The Overview queue and the contract's reconcile/latest read STORED
    artifacts; without this, a fresh deployment shows an empty queue until
    someone runs an investigation. Deterministic engines, audited as system.
    """
    from ..domains.queue import service as queue_service
    from ..models.detection import DetectionResult

    out = {"queue": None}
    if db.query(DetectionResult).filter(DetectionResult.organization_id == org_id).count() == 0:
        out["queue"] = queue_service.refresh_queue(db, org_id, None, "SYSTEM")
    # NOTE: reconciliation is deliberately NOT run at seed time — the
    # ACTIVE→CONFLICTED transition on the hero contract is a governed act that
    # belongs to the demo itself (beat 3 runs it live), not to boot.
    db.flush()
    return out


def run_seed(db: Session | None = None) -> dict:
    own_session = db is None
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
    try:
        apex = ensure_org(db, "Apex Foods", "apex", "FMCG")
        users = ensure_users(db, apex)
        sources = ensure_sources(db, apex)
        owner = next((u for u in users if u.role == "KPI_OWNER"), users[0])
        kpis = ensure_kpis(db, apex.id)
        contracts = ensure_contracts(db, apex.id, kpis, sources, owner)
        ensure_relations(db, apex.id, contracts)
        ensure_observations(db, apex.id, kpis, sources)
        ensure_evidence(db, apex.id, sources)
        ensure_impacts(db, apex.id)
        ensure_memory(db, apex.id)
        from ..services.llm.policy import ensure_policies
        ensure_policies(db)
        templates = ensure_scenarios(db, apex.id)
        ensure_meridian(db)
        # S12: a fresh database must run the hero demo STANDALONE. Materialize the
        # Executive Queue (detect+triage) and the first reconciliation per governed
        # KPI at seed time — the same production engines, idempotent (skipped when
        # artifacts exist). No fabricated rows: the refresh IS the computation.
        ensure_demo_artifacts(db, apex.id)
        db.commit()
        log.info(
            "seed complete: org=%s users=%d sources=%d kpis=%d contracts=%d scenarios=%d",
            apex.slug, len(users), len(sources), len(kpis), len(contracts), len(templates),
        )
        return {"org": apex.slug, "users": len(users), "kpis": len(kpis), "scenarios": len(templates)}
    finally:
        if own_session:
            db.close()
