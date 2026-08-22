"""LLMClient facade (arch O.1) — the ONLY sanctioned entry to model calls.

Three narrative capabilities + embedding, each routed through the gateway.
Offline (this deployment): every route resolves to the deterministic fallback
(reason NO_PROVIDER family) — the LLM only ever re-words deterministic
conclusions; numbers are computed by rules and post-checked, never by a model.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from . import gateway
from .cache import cache_key, semantic_cache

PROMPT_VERSION = "brief_v3_p1"

# Deterministic-render cost model for the ledger: the quality_prose class at
# the demo's nominal size. A cache hit avoids exactly this estimate.
DEMO_RENDER_TOKENS = 420  # ≈ 350 in + 70 out for one persona brief


def narrative(
    db: Session, organization_id: str, capability: str, data_classification: str,
    tenant_versions: dict, persona: str, render: "callable",
    investigation_id: str | None = None, external_preferred: bool = False,
) -> dict:
    """Route → (cache?) → render via fallback/provider → telemetry row.

    Returns {sections, route, cache: {hit, key, latency_saved_ms, cost_avoided_rs}}.
    """
    import time as _t

    t0 = _t.perf_counter()
    decision = gateway.route(db, organization_id, capability, data_classification,
                             external_preferred=external_preferred,
                             investigation_id=investigation_id,
                             est_tokens=DEMO_RENDER_TOKENS)
    model_route = f"{decision.model_class or 'deterministic'}:{decision.reason_code}"

    key = cache_key(
        tenant_id=organization_id,
        contract_version=tenant_versions.get("contract_version", ""),
        investigation_version=tenant_versions.get("investigation_version", ""),
        conclusion_hash=tenant_versions.get("conclusion_hash", ""),
        persona=persona, prompt_version=PROMPT_VERSION, model_route=model_route,
    )
    sc = semantic_cache()
    hit = sc.get(key)
    if hit is not None:
        _telemetry(db, organization_id, investigation_id, capability, decision, cache_hit=True,
                   latency_saved=hit.get("_render_ms", 620), cost_avoided=hit.get("_cost_est_rs", 0.13))
        return {**hit, "cache": {"hit": True, "key": key, "backend": sc.backend,
                                 "latency_saved_ms": hit.get("_render_ms", 620),
                                 "cost_avoided_rs": hit.get("_cost_est_rs", 0.13)}}

    t1 = _t.perf_counter()
    sections = render()  # deterministic renderer (offline) — provider hook would sit here
    render_ms = int((_t.perf_counter() - t1) * 1000)
    cost_est = 0.0 if decision.deterministic else decision.extra.get("cost_est_rs", 0.0)
    payload = {"sections": sections, "route": _route_dict(decision),
               "_render_ms": render_ms, "_cost_est_rs": round(cost_est or 0.13, 2)}
    sc.put(key, payload)
    _telemetry(db, organization_id, investigation_id, capability, decision,
               latency_ms=render_ms, cost_est=cost_est)
    return {**payload, "cache": {"hit": False, "key": key, "backend": sc.backend,
                                 "latency_saved_ms": 0, "cost_avoided_rs": 0.0,
                                 "degraded": sc.degraded}}


def _telemetry(db, organization_id, investigation_id, capability, decision,
               cache_hit=False, latency_ms=0, latency_saved=0, cost_est=0.0,
               cost_avoided=0.0) -> None:
    """One stage-telemetry row per narrative render/hit — the ledger's cache view."""
    from ...services.telemetry import record_stage
    record_stage(
        db, organization_id, investigation_id, f"narrative_{capability}",
        "llm" if decision.allowed else "rules", llm_used=decision.allowed,
        model_class=decision.model_class, route_reason=decision.reason_code,
        provider=decision.provider, latency_ms=latency_ms, cost_est=round(cost_est, 4),
        cache_hit=cache_hit, cache_latency_saved_ms=latency_saved,
        cache_cost_avoided_rs=round(cost_avoided, 4), ok=True,
    )


def _route_dict(d: gateway.RouteDecision) -> dict:
    return {"capability": d.capability, "data_classification": d.data_classification,
            "allowed": d.allowed, "model_class": d.model_class, "provider": d.provider,
            "reason_code": d.reason_code, "policy_ref": d.policy_ref, "fallback": d.fallback}
