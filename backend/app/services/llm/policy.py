"""AI policy engine (arch O.2): (capability × data_classification × tenant) rules."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...models.aigov import (CAPABILITY_CLASS, AiPolicy)

# Default policy fabric (seeded once; tenant rows override by org).
# external_allowed=False ⇒ external/premium providers prohibited for that
# classification — the gateway must route to an approved in-class provider or
# fall back deterministically (never silently rerouted).
DEFAULTS: list[dict] = [
    dict(capability="extract_claims", data_classification="PUBLIC",
         allowed_model_classes=["fast_extract"], allowed_providers=[], external_allowed=True,
         cost_budget_rs=0.20, latency_budget_ms=2000, fallback_rule="DETERMINISTIC"),
    dict(capability="extract_claims", data_classification="INTERNAL",
         allowed_model_classes=["fast_extract"], allowed_providers=[], external_allowed=False,
         cost_budget_rs=0.20, latency_budget_ms=2000, fallback_rule="DETERMINISTIC"),
    dict(capability="extract_claims", data_classification="SENSITIVE",
         allowed_model_classes=["fast_extract"], allowed_providers=["in_process"], external_allowed=False,
         cost_budget_rs=0.20, latency_budget_ms=2000, fallback_rule="DETERMINISTIC"),
    dict(capability="extract_claims", data_classification="RESTRICTED",
         allowed_model_classes=[], allowed_providers=[], external_allowed=False,
         cost_budget_rs=0.0, latency_budget_ms=1000, fallback_rule="DETERMINISTIC"),
    dict(capability="draft_hypotheses", data_classification="PUBLIC",
         allowed_model_classes=["reasoning"], allowed_providers=[], external_allowed=True,
         cost_budget_rs=1.00, latency_budget_ms=8000, fallback_rule="DETERMINISTIC"),
    dict(capability="draft_hypotheses", data_classification="INTERNAL",
         allowed_model_classes=["reasoning"], allowed_providers=[], external_allowed=False,
         cost_budget_rs=1.00, latency_budget_ms=8000, fallback_rule="DETERMINISTIC"),
    dict(capability="draft_hypotheses", data_classification="SENSITIVE",
         allowed_model_classes=["reasoning"], allowed_providers=["in_process"], external_allowed=False,
         cost_budget_rs=1.00, latency_budget_ms=8000, fallback_rule="DETERMINISTIC"),
    dict(capability="draft_hypotheses", data_classification="RESTRICTED",
         allowed_model_classes=[], allowed_providers=[], external_allowed=False,
         cost_budget_rs=0.0, latency_budget_ms=1000, fallback_rule="DETERMINISTIC"),
    dict(capability="translate_narrative", data_classification="PUBLIC",
         allowed_model_classes=["quality_prose"], allowed_providers=[], external_allowed=True,
         cost_budget_rs=0.50, latency_budget_ms=6000, fallback_rule="TEMPLATE"),
    dict(capability="translate_narrative", data_classification="INTERNAL",
         allowed_model_classes=["quality_prose"], allowed_providers=[], external_allowed=False,
         cost_budget_rs=0.50, latency_budget_ms=6000, fallback_rule="TEMPLATE"),
    dict(capability="translate_narrative", data_classification="SENSITIVE",
         # SENSITIVE (e.g. supplier-cost evidence): approved class only —
         # external premium models prohibited (locked demo, arch O.2)
         allowed_model_classes=["quality_prose"], allowed_providers=["in_process"], external_allowed=False,
         cost_budget_rs=0.50, latency_budget_ms=6000, fallback_rule="TEMPLATE"),
    dict(capability="translate_narrative", data_classification="RESTRICTED",
         allowed_model_classes=[], allowed_providers=[], external_allowed=False,
         cost_budget_rs=0.0, latency_budget_ms=1000, fallback_rule="TEMPLATE"),
    dict(capability="embed_case", data_classification="PUBLIC",
         allowed_model_classes=["embedding"], allowed_providers=[], external_allowed=True,
         cost_budget_rs=0.02, latency_budget_ms=1000, fallback_rule="FEATURE_HASH"),
    dict(capability="embed_case", data_classification="INTERNAL",
         allowed_model_classes=["embedding"], allowed_providers=[], external_allowed=False,
         cost_budget_rs=0.02, latency_budget_ms=1000, fallback_rule="FEATURE_HASH"),
    dict(capability="embed_case", data_classification="SENSITIVE",
         allowed_model_classes=["embedding"], allowed_providers=["in_process"], external_allowed=False,
         cost_budget_rs=0.02, latency_budget_ms=1000, fallback_rule="FEATURE_HASH"),
    dict(capability="embed_case", data_classification="RESTRICTED",
         allowed_model_classes=["embedding"], allowed_providers=["in_process"], external_allowed=False,
         cost_budget_rs=0.02, latency_budget_ms=1000, fallback_rule="FEATURE_HASH"),
]


def ensure_policies(db: Session) -> int:
    """Seed the default rule set for every org (tenant-scoped rows; the org
    mixin forbids global NULL-org rows)."""
    from ...models.org import Organization
    n = 0
    orgs = db.query(Organization).all()
    have = {(p.capability, p.data_classification, p.organization_id) for p in db.query(AiPolicy).all()}
    for org in orgs:
        for d in DEFAULTS:
            if (d["capability"], d["data_classification"], org.id) in have:
                continue
            db.add(AiPolicy(organization_id=org.id, **d))
            n += 1
    db.flush()
    return n


def policy_for(db: Session, organization_id: str, capability: str, data_classification: str) -> AiPolicy | None:
    row = (
        db.query(AiPolicy)
        .filter(AiPolicy.organization_id == organization_id,
                AiPolicy.capability == capability,
                AiPolicy.data_classification == data_classification)
        .first()
    )
    if row is not None:
        return row
    return (
        db.query(AiPolicy)
        .filter(AiPolicy.organization_id.is_(None),
                AiPolicy.capability == capability,
                AiPolicy.data_classification == data_classification)
        .first()
    )


def capability_class(capability: str) -> str:
    return CAPABILITY_CLASS.get(capability, "reasoning")
