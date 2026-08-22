"""Entitlements — server-side row/column/domain masking (AC9, arch 8.10).

The frontend never enforces any of this. Column masking happens at
serialization: masked fields are visible as `—` and the masking event is
audited. Row scoping comes from contract predicates; domain-level route
guards join at the LLM gateway (S10).
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from .audit import record as audit

# role → fields that must never serialize for that role. Visible as "—", audited.
COLUMN_MASKS: dict[str, set[str]] = {
    "SUPPLY_CHAIN": {"unit_cost_rs", "standard_unit_cost_rs", "marketing_roi", "unit_economics"},
    "EXECUTIVE": {"unit_cost_rs", "standard_unit_cost_rs"},  # aggregates only — no cost columns
    "ANALYST": set(),
    "KPI_OWNER": set(),
    "ADMIN": set(),
}

MASK_SENTINEL = "—"

_PII_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("email", "[EMAIL]", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone", "[PHONE]", re.compile(r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)")),
    ("account", "[ACCT]", re.compile(r"\b[A-Z]{2,4}[-/]?\d{9,18}\b")),
]


def mask_columns(payload: Any, role: str) -> tuple[Any, list[str]]:
    """Recursively mask disallowed fields; returns (masked copy, masked field list)."""
    masked: list[str] = []
    banned = COLUMN_MASKS.get(role, set())

    def walk(node: Any, key: str | None = None) -> Any:
        if key in banned:
            masked.append(key)
            return MASK_SENTINEL
        if isinstance(node, dict):
            return {k: walk(v, k) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, key) for v in node]
        return node

    return walk(payload), masked


def mask_pii(text: str) -> tuple[str, list[str]]:
    """Rule-based PII scrub for anything heading to a model or a less-entitled view."""
    hits: list[str] = []
    out = text
    for name, token, pattern in _PII_PATTERNS:
        if pattern.search(out):
            hits.append(name)
            out = pattern.sub(token, out)
    return out, hits


def audit_masking(db: Session, organization_id: str, actor_user_id: str, masked_fields: list[str], context: str) -> None:
    if masked_fields:
        audit(db, organization_id=organization_id, actor_user_id=actor_user_id,
              action="masking_event", object_type="serialization", object_id=context,
              details={"masked_fields": sorted(set(masked_fields)), "count": len(masked_fields)})


def can_access_doc(doc, role: str) -> bool:
    """Evidence access scope: empty access_roles ⇒ org-internal, all roles see it."""
    return not doc.access_roles or role in doc.access_roles
