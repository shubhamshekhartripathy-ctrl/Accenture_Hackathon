"""Reconciliation + queue + investigations routers (arch P.1 + S2 scope)."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..domains.contracts.service import get_contract
from ..domains.investigations import service as investigations_service
from ..domains.queue import service as queue_service
from ..domains.reconcile import service as reconcile_service
from ..envelope import ok
from ..errors import AppError
from ..models.org import User
from ..models.reconciliation import ReconciliationConflict
from ..models.investigation import InvestigationStageEvent
from ..security.deps import get_current_user, require_roles

router = APIRouter(tags=["reconcile-queue-investigations"])

_read_guard = require_roles("KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN")
_run_guard = require_roles("ANALYST", "ADMIN")
_resolve_guard = require_roles("KPI_OWNER", "ADMIN")


# --- Reconciliation ----------------------------------------------------------

class ReconcileBody(BaseModel):
    period_key: str | None = None


@router.post("/contracts/{contract_id}/reconcile")
def run_reconcile(
    request: Request,
    contract_id: str,
    body: ReconcileBody | None = None,
    user: User = Depends(_run_guard),
    db: Session = Depends(get_db),
):
    contract = get_contract(db, user.organization_id, contract_id)
    period_key = (body.period_key if body and body.period_key else None)
    if period_key is None:
        from ..models.observation import KpiObservation

        row = (
            db.query(KpiObservation)
            .filter(
                KpiObservation.organization_id == user.organization_id,
                KpiObservation.kpi_id == contract.kpi_id,
            )
            .order_by(KpiObservation.occurred_at.desc())
            .first()
        )
        period_key = row.period_key if row else "P14"
    run = reconcile_service.run_reconciliation(
        db, contract, period_key, actor_user_id=user.id, run_id=f"reconcile-api-{contract_id[:8]}"
    )
    return ok(request, reconcile_service.serialize_run(run, db))


@router.get("/contracts/{contract_id}/reconcile/latest")
def latest_reconcile(
    request: Request,
    contract_id: str,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    contract = get_contract(db, user.organization_id, contract_id)
    run = reconcile_service.latest_run(db, user.organization_id, contract_id)
    if run is None:
        raise AppError("NOT_FOUND", "No reconciliation run yet — run one first", 404)
    return ok(request, reconcile_service.serialize_run(run, db))


class ResolveBody(BaseModel):
    note: str


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(
    request: Request,
    conflict_id: str,
    body: ResolveBody,
    user: User = Depends(_resolve_guard),
    db: Session = Depends(get_db),
):
    if not body.note.strip():
        raise AppError("VALIDATION", "A resolution note is required", 422)
    conflict = (
        db.query(ReconciliationConflict)
        .filter(
            ReconciliationConflict.organization_id == user.organization_id,
            ReconciliationConflict.id == conflict_id,
        )
        .first()
    )
    if conflict is None:
        raise AppError("NOT_FOUND", "Conflict not found", 404)
    conflict = reconcile_service.resolve_conflict(
        db, user.organization_id, conflict, body.note.strip(), user.id, user.role
    )
    from ..models.reconciliation import ReconciliationRun

    run = (
        db.query(ReconciliationRun)
        .filter(
            ReconciliationRun.organization_id == user.organization_id,
            ReconciliationRun.id == conflict.run_id,
        )
        .first()
    )
    return ok(request, reconcile_service.serialize_run(run, db))


# --- Queue -------------------------------------------------------------------

@router.get("/queue")
def get_queue(request: Request, user: User = Depends(_read_guard), db: Session = Depends(get_db)):
    entries = queue_service.build_queue(db, user.organization_id)
    return ok(request, {"entries": entries, "count": len(entries)})


@router.post("/queue/refresh")
def refresh_queue(request: Request, user: User = Depends(_run_guard), db: Session = Depends(get_db)):
    result = queue_service.refresh_queue(db, user.organization_id, user.id, user.role)
    result["queue"] = queue_service.build_queue(db, user.organization_id)
    return ok(request, result)


# --- Investigation progress (SSE) — CRUD lives in routers/investigations.py ---

@router.get("/investigations/{investigation_id}/events")
async def investigation_events(
    investigation_id: str,
    follow: bool = True,
    user: User = Depends(_read_guard),
    db: Session = Depends(get_db),
):
    """SSE progress channel — SAFE operational status only (arch Q).

    Buffered events replay first (refresh never loses state), then optional
    live follow with keep-alives. `follow=false` streams the buffer, sends a
    terminal `done` event, and closes — used by tests and one-shot consumers.
    """
    inv = investigations_service.get_investigation(db, user.organization_id, investigation_id)
    run_id = f"inv-{investigation_id[:12]}"

    # Map persisted stage transitions to the same event names a live run emits, so
    # replay stays faithful after a process restart (the buffer is in-memory; the
    # stage-event log is durable). Deterministic replay preserved (arch Q).
    _PERSISTED_EVENT = {
        "RECONCILING": "reconcile_start",
        "RECONCILED": "reconciliation_complete",
        "DETECTING": "detect_start",
        "DETECTED": "detection_complete",
        "TRIAGED": "triage_complete",
        "EXPLAINING": "decompose_start",
        "FAILED": "stage_failed",
    }

    async def stream():
        from ..services.pipeline import events as bus

        sent = 0
        yield "retry: 3000\n\n"
        keepalive_every = 15.0
        last_ping = __import__("time").monotonic()
        while True:
            buffered = bus.buffered(run_id)
            if not buffered:
                # Process restarted (or the subscriber arrived after the run
                # finished): rebuild the replay from the durable stage log
                # instead of hanging on an empty buffer.
                rows = (
                    db.query(InvestigationStageEvent)
                    .filter(InvestigationStageEvent.investigation_id == investigation_id)
                    .order_by(InvestigationStageEvent.created_at, InvestigationStageEvent.id)
                    .all()
                )
                if rows:
                    yield 'event: investigation_started\ndata: {"message": "Investigation opened (replayed from persisted stage log)"}\n\n'
                    for i, row in enumerate(rows, start=1):
                        name = _PERSISTED_EVENT.get(row.to_state, "stage_event")
                        yield f'id: {i}\nevent: {name}\ndata: {json.dumps({"message": row.message})}\n\n'
                    _QUIESCENT = {
                        "TRIAGED", "EXPLAINING", "EXPLAINED", "CERTAINTY_DECISION", "CLARIFY",
                        "ABSTAINED", "FAILED", "DECISION_BLOCKED", "LEARNED", "REJECTED", "OVERRIDDEN",
                    }
                    if inv.workflow_state in _QUIESCENT:
                        yield 'event: prefix_complete\ndata: {"message": "Pipeline prefix complete (replayed)"}\n\n'
                    if inv.workflow_state in _QUIESCENT or inv.workflow_state.startswith(("DECISION", "PORTFOLIO", "HUMAN", "APPROVED", "MONITORING", "OUTCOME")):
                        yield "event: done\ndata: {}\n\n"
                        return
            while sent < len(buffered):
                e = buffered[sent]
                sent += 1
                payload = json.dumps({"message": e["message"], **e.get("data", {})})
                yield f"id: {e['id']}\nevent: {e['event']}\ndata: {payload}\n\n"
            terminal = any(x["event"] in ("prefix_complete", "stage_failed") for x in buffered)
            now = __import__("time").monotonic()
            if now - last_ping >= keepalive_every:
                last_ping = now
                yield ": keepalive\n\n"
            if terminal:
                # S2 pipeline prefix ends here; later slices keep the stream open
                # through the decision stages. Close cleanly once delivered.
                yield "event: done\ndata: {}\n\n"
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
