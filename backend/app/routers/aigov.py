"""S10 API — transparency ledger (routes + cache + caps) + demo LLM toggle.

GET  /transparency                 — aggregate ledger: stages, LLM routes,
                                     cache stats, tenant cost cap/spend, drift
POST /demo/toggle-llm              — DEMO_MODE only; flips every route to the
                                     deterministic fallback (audited, visible)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..domains.investigations.service import get_investigation
from ..envelope import ok
from ..errors import AppError
from ..models.aigov import AiPolicy, AiRouteLog
from ..models.org import User
from ..models.telemetry import StageTelemetry
from ..security.deps import require_roles
from ..security.jwt_auth import decode_token
from ..services import telemetry as telemetry_service
from ..services.audit import record as audit
from ..services.llm import gateway

router = APIRouter(tags=["ai-governance"])
_read_guard = require_roles("KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN")
_demo_guard = require_roles("KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN")
_reset_bearer = HTTPBearer(auto_error=False)


def _demo_reset_actor(credentials: HTTPAuthorizationCredentials | None = Depends(_reset_bearer)) -> dict:
    """Authorize reset without opening a DB session that would block drop_all()."""
    if credentials is None:
        raise AppError("UNAUTHORIZED", "Missing bearer token", 401)
    payload = decode_token(credentials.credentials)
    if payload.get("typ") != "access":
        raise AppError("UNAUTHORIZED", "Wrong token type", 401)
    role = payload.get("role")
    if role not in {"KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN"}:
        raise AppError("FORBIDDEN", f"Role {role} is not permitted for this operation", 403)
    return payload


@router.get("/transparency")
def transparency(request: Request, investigation_id: str | None = None,
                 user: User = Depends(_read_guard), db: Session = Depends(get_db)):
    """The Transparency Ledger aggregate (AC26): stages, routes, cache, caps."""
    q = db.query(StageTelemetry).filter(StageTelemetry.organization_id == user.organization_id)
    rq = db.query(AiRouteLog).filter(AiRouteLog.organization_id == user.organization_id)
    if investigation_id:
        inv = get_investigation(db, user.organization_id, investigation_id)
        q = q.filter(StageTelemetry.run_id == inv.id)
        rq = rq.filter(AiRouteLog.investigation_id == inv.id)
    stages = q.order_by(StageTelemetry.created_at.desc()).limit(200).all()
    routes = rq.order_by(AiRouteLog.created_at.desc()).limit(200).all()

    llm_routes = [r for r in routes if r.decision == "ALLOWED"]
    denials = [r for r in routes if r.decision != "ALLOWED"]
    cache_hits = sum(1 for s in stages if getattr(s, "cache_hit", False))
    cache_saved_ms = sum(s.cache_latency_saved_ms or 0 for s in stages)
    cache_avoided_rs = round(sum(s.cache_cost_avoided_rs or 0 for s in stages), 2)
    tokens = sum((s.tokens_in or 0) + (s.tokens_out or 0) for s in stages)
    return ok(request, {
        "stages": [{
            "run_id": s.run_id, "stage_code": s.stage_code, "method_label": s.method_label,
            "llm_used": s.llm_used, "model_class": s.model_class, "route_reason": s.route_reason,
            "provider": s.provider, "latency_ms": s.latency_ms,
            "tokens_in": getattr(s, "tokens_in", None), "tokens_out": getattr(s, "tokens_out", None),
            "cost_est_rs": s.cost_est or 0.0,
            "cache_hit": bool(getattr(s, "cache_hit", False)),
            "cache_latency_saved_ms": getattr(s, "cache_latency_saved_ms", 0) or 0,
            "cache_cost_avoided_rs": getattr(s, "cache_cost_avoided_rs", 0) or 0,
            "ok": s.ok,
        } for s in stages],
        "routes": [{
            "capability": r.capability, "data_classification": r.data_classification,
            "decision": r.decision, "model_class": r.model_class, "provider": r.provider,
            "policy_ref": r.policy_ref, "reason_code": r.reason_code, "fallback": r.fallback,
            "cost_est_rs": r.cost_est_rs, "created_at": r.created_at,
        } for r in routes],
        "summary": {
            "n_stages": len(stages),
            "llm_stages": sum(1 for s in stages if s.llm_used),
            "numbers_computed_without_llm_pct": round(100.0 * (1 - sum(1 for s in stages if s.llm_used) / len(stages)), 2) if stages else 100.0,
            "n_routes": len(routes),
            "n_allowed": len(llm_routes),
            "n_denied_or_fallback": len(denials),
            "denial_reasons": sorted({r.reason_code for r in denials}),
            "cache_hits": cache_hits,
            "cache_latency_saved_ms": cache_saved_ms,
            "cache_cost_avoided_rs": cache_avoided_rs,
            "tokens": tokens,
            "cost_per_insight": {
                # provider-equivalent model (arch locked target: 2-of-7 LLM-capable
                # stages, ~1,400 tokens, ≈ ₹0.19/insight ±30%). Offline this
                # deployment runs 0 real LLM stages — actuals stay ₹0 and the
                # estimate is labeled for exactly what it is.
                "provider_equivalent_rs": 0.19,
                "provider_equivalent_tokens": 1400,
                "llm_capable_stages": 2,
                "total_stages": 7,
                "actual_llm_stages_run": sum(1 for s in stages if s.llm_used),
                "actual_tokens": tokens,
                "actual_spend_rs": round(sum(s.cost_est or 0 for s in stages), 4),
                "note": "offline deployment: deterministic engines computed every number; "
                        "provider-equivalent figures show what the same run costs with LLM stages on",
            },
            "tenant_cost_cap_rs": gateway.tenant_cost_cap_rs(db, user.organization_id),
            "tenant_spend_rs": round(gateway.tenant_spend_rs(db, user.organization_id), 4),
            "llm_enabled": gateway.llm_enabled(),
        },
    })


@router.get("/ai/policies")
def ai_policies(request: Request, user: User = Depends(_read_guard), db: Session = Depends(get_db)):
    rows = db.query(AiPolicy).filter(
        (AiPolicy.organization_id == user.organization_id) | (AiPolicy.organization_id.is_(None))
    ).all()
    return ok(request, [{
        "capability": p.capability, "data_classification": p.data_classification,
        "allowed_model_classes": p.allowed_model_classes, "allowed_providers": p.allowed_providers,
        "external_allowed": p.external_allowed, "cost_budget_rs": p.cost_budget_rs,
        "latency_budget_ms": p.latency_budget_ms, "fallback_rule": p.fallback_rule,
        "tenant_scoped": p.organization_id is not None,
    } for p in rows])


class FFIn(BaseModel):
    days: int = 14


@router.post("/demo/inject-pos")
def demo_inject_pos(request: Request, user: User = Depends(_demo_guard), db: Session = Depends(get_db)):
    from ..services import demo as demo_service
    return ok(request, demo_service.inject_pos(db, user.organization_id, user.id, user.role))


@router.post("/demo/fast-forward")
def demo_fast_forward(body: FFIn, request: Request,
                      user: User = Depends(_demo_guard), db: Session = Depends(get_db)):
    from ..services import demo as demo_service
    return ok(request, demo_service.fast_forward(db, user.organization_id, user.id, user.role, body.days))


@router.post("/demo/reset")
def demo_reset(request: Request, actor: dict = Depends(_demo_reset_actor)):
    from ..services import demo as demo_service
    return ok(request, demo_service.reset(actor["sub"], actor["role"]))


class ToggleIn(BaseModel):
    enabled: bool


@router.post("/demo/toggle-llm")
def toggle_llm(body: ToggleIn, request: Request,
               user: User = Depends(_demo_guard), db: Session = Depends(get_db)):
    if not settings.demo_mode:
        raise AppError("FORBIDDEN", "Demo controls exist only in DEMO_MODE", 403)
    value = gateway.set_llm_enabled(body.enabled)
    audit(db, organization_id=user.organization_id, actor_user_id=user.id, actor_role=user.role,
          action="demo.toggle_llm", object_type="setting", object_id="llm_enabled",
          details={"enabled": value})
    return ok(request, {"llm_enabled": value,
                        "note": "every route now resolves to the deterministic fallback — visible in the ledger"})
