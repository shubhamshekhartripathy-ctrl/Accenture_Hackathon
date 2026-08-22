"""Telemetry-wrapped deterministic stage runner (arch C.1).

Executes stages sequentially, records one stage_telemetry row per stage,
persists every workflow transition, and publishes safe SSE progress events.
Numeric stages are rules/SQL/stats only — the LLM-capable stages (hypothesize,
gather, narrate) join in later slices with deterministic template fallbacks.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from ...db import utcnow
from ...models.investigation import Investigation, InvestigationStageEvent, WORKFLOW_TRANSITIONS
from ...services import telemetry
from . import events


@dataclass
class RunContext:
    db: object
    investigation: Investigation
    organization_id: str = ""
    run_id: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class Stage:
    stage_code: str
    method_label: str               # sql | stats | rules | ml | retrieval | llm
    transition: tuple[str, str] | None   # (from_state, to_state)
    progress_event: str                  # safe SSE event name
    progress_message: str                # safe operational text
    fn: Callable[[RunContext], object]   # returns artifact; raises on failure
    source_count: int = 0


class IllegalTransition(RuntimeError):
    pass


def apply_transition(ctx: RunContext, stage: Stage, ok: bool, artifact_ref: str | None = None) -> None:
    inv = ctx.investigation
    if stage.transition is not None:
        expected_from, to_state = stage.transition
        if inv.workflow_state != expected_from:
            raise IllegalTransition(
                f"investigation {inv.id}: expected state {expected_from}, found {inv.workflow_state}"
            )
        key = (expected_from, to_state)
        if key not in WORKFLOW_TRANSITIONS:
            raise IllegalTransition(f"transition {key} is not allowed by the workflow rule book")
        event_row = InvestigationStageEvent(
            organization_id=ctx.organization_id,
            investigation_id=inv.id,
            from_state=expected_from,
            to_state=to_state if ok else "FAILED",
            stage_code=stage.stage_code,
            ok=ok,
            message=stage.progress_message if ok else f"{stage.stage_code} failed",
            artifact_ref=artifact_ref,
        )
        ctx.db.add(event_row)
        inv.workflow_state = to_state if ok else "FAILED"
        ctx.db.add(inv)
        ctx.db.flush()
    events.emit(ctx.run_id, stage.progress_event, stage.progress_message)


def run_stages(ctx: RunContext, stages: list[Stage]) -> RunContext:
    """Run sequentially; a failed stage marks the run FAILED with the last-good artifact."""
    for stage in stages:
        t0 = time.perf_counter()
        artifact = None
        ok = True
        try:
            artifact = stage.fn(ctx)
        except Exception as exc:  # noqa: BLE001 — failure semantics: DEGRADED/FAILED, never invented
            ok = False
            ctx.investigation.last_error = f"{stage.stage_code}: {exc}"
            ctx.db.add(ctx.investigation)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        artifact_ref = None
        if hasattr(artifact, "id"):
            artifact_ref = str(artifact.id)
        apply_transition(ctx, stage, ok, artifact_ref)
        telemetry.record_stage(
            ctx.db, ctx.organization_id, ctx.run_id, stage.stage_code, stage.method_label,
            latency_ms=latency_ms, source_count=stage.source_count, ok=ok,
        )
        if not ok:
            events.emit(ctx.run_id, "stage_failed", f"Stage {stage.stage_code} failed — run marked FAILED, retryable from last-good artifact")
            break
    return ctx
