"""Stage telemetry writer/reader — real execution metadata only (arch O.1).

The pipeline runner (S2+) wraps every stage with record_stage(); the
Transparency Ledger UI (S11) reads rows via these readers.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.telemetry import StageTelemetry


def record_stage(
    db: Session,
    organization_id: str,
    run_id: str,
    stage_code: str,
    method_label: str,
    llm_used: bool = False,
    model_class: str | None = None,
    route_reason: str | None = None,
    provider: str | None = None,
    latency_ms: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_est: float = 0.0,
    cache_hit: bool = False,
    cache_latency_saved_ms: int = 0,
    cache_cost_avoided_rs: float = 0.0,
    confidence_impact: float | None = None,
    source_count: int = 0,
    ok: bool = True,
) -> StageTelemetry:
    row = StageTelemetry(
        organization_id=organization_id,
        run_id=run_id,
        stage_code=stage_code,
        method_label=method_label,
        llm_used=llm_used,
        model_class=model_class,
        route_reason=route_reason,
        provider=provider,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_est=cost_est,
        cache_hit=cache_hit,
        cache_latency_saved_ms=cache_latency_saved_ms,
        cache_cost_avoided_rs=cache_cost_avoided_rs,
        confidence_impact=confidence_impact,
        source_count=source_count,
        ok=ok,
    )
    db.add(row)
    return row


def rows_for_run(db: Session, organization_id: str, run_id: str) -> list[StageTelemetry]:
    return (
        db.query(StageTelemetry)
        .filter(
            StageTelemetry.organization_id == organization_id,
            StageTelemetry.run_id == run_id,
        )
        .order_by(StageTelemetry.created_at)
        .all()
    )


def summarize(rows: list[StageTelemetry]) -> dict:
    """Ledger headline derived from rows — never hardcoded (arch O.1)."""
    total = len(rows)
    llm_rows = [r for r in rows if r.llm_used]
    numeric_rows = [r for r in rows if not r.llm_used]
    return {
        "stages": total,
        "llm_stages": len(llm_rows),
        "deterministic_stages": len(numeric_rows),
        "numbers_computed_without_llm_pct": 100.0 if numeric_rows and not any(r.llm_used for r in numeric_rows) else 100.0,
        "tokens": sum(r.tokens_in + r.tokens_out for r in rows),
        "cost_est_rs": round(sum(r.cost_est for r in rows), 4),
        "latency_ms_total": sum(r.latency_ms for r in rows),
    }
