"""Model Routing Gateway (arch O.3).

route(capability, data_classification, ...) → RouteDecision. Checks, in order:
1. runtime LLM toggle (demo control, audited)        → DISABLED
2. tenant cost cap exhausted                        → COST_CAP
3. policy lookup (capability × classification × tenant)
     - no allowed classes (RESTRICTED)               → POLICY_DENIED
     - external provider wanted but prohibited       → POLICY_DENIED_EXTERNAL
4. provider availability (credentials)               → NO_PROVIDER → deterministic fallback
Allowed routes carry reason POLICY_APPROVED_CLASS + the policy reference.
Every decision is written to ai_route_log (never silently rerouted).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ...config import settings
from ...models.aigov import AiRouteLog
from ...models.org import Organization
from . import policy as policy_engine

# Runtime demo toggle (DEMO_MODE only; flipped via POST /demo/toggle-llm, audited)
_llm_enabled = True


def set_llm_enabled(value: bool) -> bool:
    global _llm_enabled
    _llm_enabled = value
    return _llm_enabled


def llm_enabled() -> bool:
    return _llm_enabled


# Documented indicative rates per model class (₹ per 1k tokens in+out) — used
# ONLY for ledger cost_est; the deterministic path costs ₹0.
RATES_RS_PER_KTOK = {"fast_extract": 0.05, "reasoning": 0.60, "quality_prose": 0.30, "embedding": 0.01}


@dataclass
class RouteDecision:
    capability: str
    data_classification: str
    allowed: bool
    model_class: str | None = None
    provider: str | None = None
    reason_code: str = ""
    policy_ref: str | None = None
    fallback: str | None = None
    cost_budget_rs: float = 0.0
    latency_budget_ms: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def deterministic(self) -> bool:
        return not self.allowed


def tenant_cost_cap_rs(db: Session, organization_id: str) -> float:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    return float(org.ai_cost_cap_rs) if org and org.ai_cost_cap_rs is not None else 50.0


def tenant_spend_rs(db: Session, organization_id: str) -> float:
    rows = db.query(AiRouteLog).filter(AiRouteLog.organization_id == organization_id).all()
    return sum(r.cost_est_rs or 0.0 for r in rows)


def route(
    db: Session, organization_id: str, capability: str, data_classification: str,
    external_preferred: bool = False, investigation_id: str | None = None,
    est_tokens: int = 0,
) -> RouteDecision:
    pol = policy_engine.policy_for(db, organization_id, capability, data_classification)
    pol_ref = f"ai_policy:{capability}:{data_classification}" + ("@tenant" if pol and pol.organization_id else "")

    def log(decision: str, reason: str, d: RouteDecision) -> RouteDecision:
        db.add(AiRouteLog(
            organization_id=organization_id, investigation_id=investigation_id,
            capability=capability, data_classification=data_classification,
            decision=decision, model_class=d.model_class, provider=d.provider,
            policy_ref=pol_ref, reason_code=reason, fallback=d.fallback,
            latency_ms=0, cost_est_rs=0.0,
        ))
        db.flush()
        return d

    if pol is None:
        return log("POLICY_DENIED", "NO_POLICY",
                   RouteDecision(capability, data_classification, False,
                                 fallback=pol.fallback_rule if pol else "DETERMINISTIC"))

    base = dict(capability=capability, data_classification=data_classification,
                policy_ref=pol_ref, cost_budget_rs=pol.cost_budget_rs,
                latency_budget_ms=pol.latency_budget_ms)

    if not llm_enabled():
        return log("DISABLED", "LLM_DISABLED_DEMO",
                   RouteDecision(allowed=False, fallback=pol.fallback_rule, reason_code="LLM_DISABLED_DEMO", **_kw(base)))
    if not pol.allowed_model_classes:
        return log("POLICY_DENIED", "POLICY_DENIED_RESTRICTED",
                   RouteDecision(allowed=False, fallback=pol.fallback_rule, reason_code="POLICY_DENIED_RESTRICTED", **_kw(base)))
    if external_preferred and not pol.external_allowed:
        return log("POLICY_DENIED", "POLICY_DENIED_EXTERNAL",
                   RouteDecision(allowed=False, fallback=pol.fallback_rule, reason_code="POLICY_DENIED_EXTERNAL", **_kw(base)))
    if tenant_spend_rs(db, organization_id) >= tenant_cost_cap_rs(db, organization_id):
        return log("COST_CAP", "TENANT_COST_CAP_EXHAUSTED",
                   RouteDecision(allowed=False, fallback=pol.fallback_rule, reason_code="TENANT_COST_CAP_EXHAUSTED", **_kw(base)))

    model_class = policy_engine.capability_class(capability)
    if model_class not in pol.allowed_model_classes:
        return log("POLICY_DENIED", "POLICY_CLASS_MISMATCH",
                   RouteDecision(allowed=False, fallback=pol.fallback_rule, reason_code="POLICY_CLASS_MISMATCH", **_kw(base)))

    # provider availability: no credentials in this deployment ⇒ deterministic
    provider = ("in_process" if pol.allowed_providers else _default_provider(model_class))
    if provider == "in_process" or not _provider_credentials():
        return log("ALLOWED", "POLICY_APPROVED_CLASS_NO_PROVIDER",
                   RouteDecision(allowed=False, model_class=model_class, provider=None,
                                 fallback=pol.fallback_rule, reason_code="POLICY_APPROVED_CLASS_NO_PROVIDER", **_kw(base)))

    cost_est = round(est_tokens / 1000.0 * RATES_RS_PER_KTOK.get(model_class, 0.3), 4)
    d = RouteDecision(allowed=True, model_class=model_class, provider=provider,
                      reason_code="POLICY_APPROVED_CLASS", cost_budget_rs=pol.cost_budget_rs,
                      latency_budget_ms=pol.latency_budget_ms, policy_ref=pol_ref,
                      capability=capability, data_classification=data_classification,
                      extra={"cost_est_rs": cost_est})
    db.add(AiRouteLog(
        organization_id=organization_id, investigation_id=investigation_id,
        capability=capability, data_classification=data_classification,
        decision="ALLOWED", model_class=model_class, provider=provider,
        policy_ref=pol_ref, reason_code="POLICY_APPROVED_CLASS", fallback=None,
        latency_ms=int(time.time() * 1000) % 1, cost_est_rs=cost_est,
    ))
    db.flush()
    return d


def _kw(base: dict) -> dict:
    return dict(capability=base["capability"], data_classification=base["data_classification"],
                policy_ref=base["policy_ref"], cost_budget_rs=base["cost_budget_rs"],
                latency_budget_ms=base["latency_budget_ms"])


def _default_provider(model_class: str) -> str:
    return "external_premium" if model_class in ("reasoning", "quality_prose") else "external_fast"


def _provider_credentials() -> bool:
    return bool(getattr(settings, "openai_api_key", None) or getattr(settings, "llm_api_key", None))
