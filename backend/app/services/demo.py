"""Demo controls (arch services/demo) — DEMO_MODE only, every action audited.

- inject-pos: mark the POS source's latest observations as refreshed just now
  (freshness recovers; a rerun shows fresher evidence — replay-safe).
- fast-forward: advance the demo clock N days (default 14). The clock is
  relative to the seeded fixed clock; observations' effective ages are
  computed against the advanced clock on the next run.
- reset: wipe and reseed the demo data (audit row survives in the fresh DB
  via explicit post-reset audit write).
- toggle-llm: lives in services/llm.gateway (S10).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..db import utcnow
from ..errors import AppError
from ..models.org import Organization
from ..services.audit import record as audit

# Demo clock — anchored to the seeded fabric clock; fast-forward advances it.
from ..seed.fabric_observations import DEMO_NOW as _SEED_NOW

_state: dict = {"offset_days": 0.0}


def demo_now() -> datetime:
    return _SEED_NOW + timedelta(days=float(_state["offset_days"]))


def _require_demo_mode() -> None:
    if not settings.demo_mode:
        raise AppError("FORBIDDEN", "Demo controls exist only in DEMO_MODE", 403)


def inject_pos(db: Session, organization_id: str, actor_user_id: str, actor_role: str) -> dict:
    """Refresh the POS source: newest observations get occurred_at = now."""
    _require_demo_mode()
    from ..models.evidence import EvidenceRecord
    from ..models.source import SourceSystem

    pos = (
        db.query(SourceSystem)
        .filter(SourceSystem.organization_id == organization_id, SourceSystem.code == "pos")
        .first()
    )
    if pos is None:
        raise AppError("NOT_FOUND", "POS source not found in this tenant", 404)
    now = demo_now()
    docs = (
        db.query(EvidenceRecord)
        .filter(EvidenceRecord.organization_id == organization_id,
                EvidenceRecord.source_id == pos.id)
        .all()
    )
    touched = 0
    for d in docs:
        d.occurred_at = now - timedelta(days=0.5)
        d.freshness_score = 1.0
        db.add(d)
        touched += 1
    audit(db, organization_id=organization_id, actor_user_id=actor_user_id, actor_role=actor_role,
          action="demo.inject_pos", object_type="source_system", object_id=pos.id,
          details={"documents_refreshed": touched})
    db.flush()
    return {"source": "pos", "documents_refreshed": touched,
            "as_of": now.isoformat(), "note": "POS refreshed — rerun shows fresher evidence"}


def fast_forward(db: Session, organization_id: str, actor_user_id: str, actor_role: str,
                 days: int = 14) -> dict:
    _require_demo_mode()
    _state["offset_days"] = float(_state["offset_days"]) + float(days)
    audit(db, organization_id=organization_id, actor_user_id=actor_user_id, actor_role=actor_role,
          action="demo.fast_forward", object_type="clock", object_id="demo_now",
          details={"days": days, "total_offset_days": _state["offset_days"]})
    db.flush()
    return {"days": days, "demo_now": demo_now().isoformat(),
            "note": "time moved — freshness decays, monitoring windows advance"}


def reset(actor_user_id: str, actor_role: str) -> dict:
    """Wipe + reseed. The audit of the reset itself is written after seeding."""
    _require_demo_mode()
    from ..db import Base, engine
    from sqlalchemy import text
    from ..seed.seed import run_seed

    if engine.name == "postgresql":
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();")
            )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _state["offset_days"] = 0.0
    out = run_seed()
    with_next = dict(out)
    from ..db import SessionLocal
    s2 = SessionLocal()
    try:
        audit(s2, organization_id=_apex_id(s2), actor_user_id=actor_user_id, actor_role=actor_role,
              action="demo.reset", object_type="database", object_id="all",
              details={"reseeded": True})
        s2.commit()
    finally:
        s2.close()
    return with_next


def _apex_id(db: Session) -> str:
    org = db.query(Organization).filter(Organization.slug == "apex").first()
    return org.id if org else ""
