"""Model Routing Gateway + AI policy engine + semantic cache + LLM facade.

Business modules never call providers directly (build-failure rule): they call
`LLMClient` (services/llm/client.py), which routes every request through the
gateway. The gateway consults the AI policy (capability × data classification
× tenant), applies the tenant cost cap and the runtime LLM toggle, and returns
a route record with a reason. Denials are never silently rerouted: they fall
back to the deterministic path with a visible reason code, and every decision
is logged to ai_route_log + stage telemetry.

Offline sandbox: no provider credentials ⇒ DETERMINISTIC MODE (every route
resolves to the deterministic fallback with reason NO_PROVIDER). Redis absent
⇒ semantic cache falls back to an in-process validity-aware store (DEGRADED
label; identical keys, identical semantics — documented deviation, plan S10).
"""
from . import cache, client, gateway, policy  # noqa: F401
