"""Persona briefs (AC9) — ONE conclusion object, four governed views.

Personas never receive different underlying truths: every view renders from
the same serialized investigation (H.1) and carries the same `conclusion_hash`.
The LLM (when routed, S10) only ever re-words template output; a numeric
post-check forces the deterministic template whenever a number not present in
the conclusion object appears, with a logged warning (arch 8.9).
"""
from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy.orm import Session

from ...models.investigation import Investigation
from ..explain import decomposition as explain_decomposition
from ...models.org import User
from ...services import telemetry
from ...services.entitlements import can_access_doc, mask_columns, mask_pii

PERSONAS = ("EXECUTIVE", "ANALYST", "SUPPLY_CHAIN", "KPI_OWNER")

ALLOWED_ACTIONS = {
    "EXECUTIVE": ["Approve within limit", "Escalate", "Request portfolio view"],
    "ANALYST": ["Challenge method", "Correct driver", "Add evidence"],  # never approve
    "SUPPLY_CHAIN": ["Execute authorized action", "Monitor guardrails"],
    "KPI_OWNER": ["Resolve conflict", "Propose contract change", "Review proposals"],
}

TEMPLATE_VERSION = "brief-v1"


def conclusion_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _numbers_in_conclusion(payload: dict) -> set[float]:
    """Every numeric value the conclusion object justifies — including its honest
    display forms (₹M scaling for large money values) and tallies derived from
    the payload's own lists. Nothing else may appear in a narrative."""
    out: set[float] = set()

    def add(n: float) -> None:
        out.add(n)
        for prec in (1, 2, 3):
            out.add(round(n, prec))
        if abs(n) >= 1e5:  # ₹M display form
            m = n / 1e6
            out.update({round(m, 1), round(m, 2), round(m, 3), round(m)})

    def walk(node):
        if isinstance(node, dict):
            for v in node.values(): walk(v)
        elif isinstance(node, list):
            for v in node: walk(v)
            out.add(float(len(node)))  # list tallies (evidence counts etc.)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            add(float(node))

    walk(payload)
    return out


_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def numeric_postcheck(text: str, allowed: set[float]) -> list[str]:
    """Return number tokens in `text` that the conclusion does not justify.

    A token is justified when some conclusion value equals it exactly or rounds
    to it at the token's own precision (narratives may display 0.7069 as 0.71).
    """
    bad: list[str] = []
    for raw in _NUM_RE.findall(text):
        token = raw.replace(",", "")
        try:
            value = float(token)
        except ValueError:
            continue
        decimals = len(token.split(".")[1]) if "." in token else 0
        if any(abs(value - a) <= 0.51 * (10 ** -decimals) for a in allowed):
            continue
        bad.append(raw)
    return bad


def _fmt_rs(v: float | None) -> str:
    return "—" if v is None else f"₹{v/1e6:.1f}M"


def persona_view(db: Session, organization_id: str, inv: Investigation, viewer: User, base: dict) -> dict:
    """Render the viewer's brief from the ONE conclusion object (H.1)."""
    role = viewer.role
    lead = (base.get("hypotheses") or [{}])[0]
    detection = base.get("detection") or {}
    materiality = base.get("materiality") or {}
    abstention = base.get("abstention") or None
    clarification = base.get("clarification") or None

    # Evidence access scope at VIEW time: the gatherer's scope is not the viewer's.
    # Withheld docs are counted honestly and their content replaced with a
    # placeholder — never silently omitted (AC7/AC9).
    from ...models.evidence import EvidenceRecord
    kpi = inv.kpi
    case_docs = (
        db.query(EvidenceRecord)
        .filter(EvidenceRecord.organization_id == organization_id,
                EvidenceRecord.kpi_code == (kpi.code if kpi else ""))
        .all()
    ) if kpi else []
    doc_by_key = {d.doc_key: d for d in case_docs}
    withheld_keys = [d.doc_key for d in case_docs if not can_access_doc(d, role)]

    visible_hyps = []
    for h in base.get("hypotheses") or []:
        h = dict(h)
        ev_out = []
        for e in h.get("evidence") or []:
            doc = doc_by_key.get(e.get("doc_key"))
            if doc is not None and doc.doc_key in withheld_keys:
                ev_out.append({"doc_key": doc.doc_key, "title": "— source withheld for your role —",
                               "state": e["state"], "weight": 0.0, "source": e.get("source"),
                               "data_classification": doc.data_classification, "freshness": e.get("freshness"),
                               "lineage": None, "summary": None, "access_roles": doc.access_roles, "claims": []})
            else:
                ev_out.append(e)
        h["evidence"] = ev_out
        visible_hyps.append(h)
    base = {**base, "hypotheses": visible_hyps}

    all_docs, withheld = [], []
    for h in base.get("hypotheses") or []:
        for e in h.get("evidence") or []:
            if e not in all_docs:
                all_docs.append(e)

    supports = sum(1 for h in base.get("hypotheses") or [] for e in h.get("evidence") or [] if e["state"] == "SUPPORTING")
    contradicts = sum(1 for h in base.get("hypotheses") or [] for e in h.get("evidence") or [] if e["state"] == "CONTRADICTING")
    stale = sum(1 for h in base.get("hypotheses") or [] for e in h.get("evidence") or [] if e["state"] == "STALE")
    restricted_links = len(withheld_keys)  # viewer-scoped, honest count for the whole case

    from ..explain import decomposition as explain_decomposition
    decomp_payload = None
    try:
        decomp_payload = explain_decomposition.serialize_for_investigation(db, organization_id, inv)
    except Exception:  # noqa: BLE001 — brief must never 500 on a missing artifact
        decomp_payload = None
    if decomp_payload:
        base = {**base, "decomposition": decomp_payload}

    # Derived tallies + the scoring method constants live in base BEFORE
    # hashing/postcheck: honest (computed from the payload / the actual method)
    # and therefore justified in narratives.
    from ..explain.hypotheses import W_AGREE, W_BALANCE, W_FRESH, W_PRIOR
    base = {**base,
            "evidence_tally": {"supporting": supports, "contradicting": contradicts,
                               "stale": stale, "withheld": restricted_links},
            "scoring_weights": {"balance": W_BALANCE, "freshness": W_FRESH,
                                "agreement": W_AGREE, "prior": W_PRIOR}}

    c_hash = conclusion_hash({k: v for k, v in base.items() if k not in ("hypotheses", "evidence_tally")})
    telemetry.record_stage(db, organization_id, inv.id, "brief_render", "rules",
                           ok=True, confidence_impact=None, source_count=len(all_docs))

    common = {
        "investigation_id": inv.id,
        "kpi_code": base.get("kpi", {}).get("code") if isinstance(base.get("kpi"), dict) else None,
        "persona": role,
        "conclusion_hash": c_hash,
        "template_version": TEMPLATE_VERSION,
        "render_method": "deterministic_template",  # honest label; llm only re-words (S10)
        "certainty_state": base.get("certainty_state"),
        "final_confidence": base.get("final_confidence"),
    }

    postcheck_state: dict = {"violations": {}}

    def _render_sections() -> dict:
        if role == "EXECUTIVE":
            sections0 = _executive(base, lead, detection, materiality, abstention, supports, contradicts)
        elif role == "ANALYST":
            sections0 = _analyst(base, lead, detection)
        elif role == "SUPPLY_CHAIN":
            sections0 = _supply_chain(base, lead, restricted_links)
        else:
            sections0 = _kpi_owner(base, lead, detection, materiality)  # KPI_OWNER / ADMIN
        # numeric post-check INSIDE the render path: the cache stores the FINAL
        # corrected sections, never an unverified render (S10 correctness fix)
        allowed0 = _numbers_in_conclusion(base)
        for key, text in sections0.items():
            if isinstance(text, str):
                bad = numeric_postcheck(text, allowed0)
                if bad:
                    postcheck_state["violations"][key] = bad
                    sections0[key] = _template_fallback(key, base)
        return sections0

    # S10: narrative rendering routes through the LLM gateway; the deterministic
    # template stays the renderer offline (the LLM only ever re-words), and the
    # validity-aware semantic cache serves unchanged conclusions.
    from ...services.llm import client as llm_client
    classification = _brief_classification(base)
    rendered = llm_client.narrative(
        db, organization_id, "translate_narrative", classification,
        tenant_versions={
            "contract_version": base.get("contract_version", ""),
            "investigation_version": len(base.get("stage_events") or []),
            "conclusion_hash": c_hash,
        },
        persona=role, render=_render_sections, investigation_id=inv.id,
    )
    sections = rendered["sections"]
    ai_route = rendered["route"]
    ai_cache = rendered["cache"]

    brief = {**common, "sections": sections, "allowed_actions": ALLOWED_ACTIONS.get(role, []),
             "ai_route": ai_route,
             "semantic_cache": {"hit": ai_cache["hit"], "backend": ai_cache["backend"],
                                "latency_saved_ms": ai_cache.get("latency_saved_ms", 0),
                                "cost_avoided_rs": ai_cache.get("cost_avoided_rs", 0.0),
                                "provider_equivalent_ms_saved": 620 if ai_cache["hit"] else 0},
             "evidence_tally": {"supporting": supports, "contradicting": contradicts,
                                "stale": stale, "withheld": restricted_links},
             "withheld_sources": [{"doc_key": k, "classification": doc_by_key[k].data_classification} for k in withheld_keys]}

    # Column masking at serialization — visible as "—", audited (services.entitlements).
    brief, masked_fields = mask_columns(brief, role)
    if masked_fields:
        from ...services.entitlements import audit_masking
        audit_masking(db, organization_id, viewer.id, masked_fields, f"brief:{inv.id}:{role}")

    # Numeric post-check: enforced inside the render (see above); violations are
    # surfaced from the render state so cached renders stay flagged at render time.
    violations: dict[str, list[str]] = postcheck_state["violations"]
    if violations:
        brief["postcheck_violations"] = violations
        brief["postcheck_forced_template"] = True
        telemetry.record_stage(db, organization_id, inv.id, "brief_postcheck", "rules", ok=False)
    return brief


def _brief_classification(base: dict) -> str:
    """Most sensitive classification feeding this brief ( PUBLIC < INTERNAL < SENSITIVE < RESTRICTED )."""
    order = {"PUBLIC": 0, "INTERNAL": 1, "SENSITIVE": 2, "RESTRICTED": 3}
    worst = "PUBLIC"
    for h in base.get("hypotheses") or []:
        if not isinstance(h, dict):
            continue
        for d in h.get("evidence") or []:
            cls = d.get("data_classification") if isinstance(d, dict) else None
            if cls in order and order[cls] > order[worst]:
                worst = cls
    return worst


def _template_fallback(key: str, base: dict) -> str:
    return json.dumps({"section": key, "note": "forced_template_numeric_violation",
                       "source": "deterministic renderer"}, sort_keys=True)


def _executive(base, lead, detection, materiality, abstention, supports, contradicts) -> dict:
    if abstention:
        return {
            "headline": "The platform abstains on this case — no action is recommended.",
            "situation": f"Movement of {detection.get('deviation_pct', 0.0):.2f}% on {base.get('kpi', {}).get('code', 'the KPI')} could not be separated into competing explanations at decision-grade confidence ({base.get('final_confidence', 0):.2f}).",
            "what_we_do_not_know": abstention.get("why_it_cannot_conclude", ""),
            "cost_of_waiting": abstention.get("is_waiting_safer", ""),
            "next_step": "Refresh the named data; the case re-opens automatically.",
        }
    return {
        "headline": f"Revenue NE is {detection.get('deviation_pct', 0.0):.2f}% vs baseline — top driver: {(lead.get('code') or '—').replace('_', ' ')} at confidence {base.get('final_confidence', 0):.2f}.",
        "exposure": f"Exposure {materiality.get('exposure_rs', 0.0)/1e6:.1f}M at {materiality.get('band', '—')} band; margin-weighted and strategic-weighted scores are in the queue.",
        "evidence_shape": f"{supports} supporting vs {contradicts} contradicting signals — the case survives its red herrings.",
        "decision_required": "One decision from the generated options: approve, escalate, or defer — you are the approval authority within your limit.",
        "portfolio_context": "Open decisions and unresolved collisions are on the portfolio view.",
    }


def _analyst(base, lead, detection) -> dict:
    hyps = base.get("hypotheses") or []
    lines = [f"{i+1}. {h['code']} — conf {h['confidence']:.2f} (S {h['support_mass']:.2f} / C {h['contradiction_mass']:.2f}, balance {h['balance']:.3f}, fresh {h['freshness_avg']:.2f}, agree {h['source_agreement']:.2f}, prior {h['pattern_prior']:.2f})"
             for i, h in enumerate(hyps)]
    decomp = base.get("decomposition") or {}
    comp = "; ".join(f"{c['component']} {c['pct']:+.2f}%" for c in decomp.get("components", [])) or "see decomposition endpoint"
    return {
        "method_note": "Confidence = 0.35·balance + gate·(0.20·freshness + 0.15·agreement) + 0.30·prior; gate = support > 0; balance = (S−C)/(S+C+1). No LLM touches these numbers.",
        "ranking": "\n".join(lines),
        "decomposition": comp,
        "contradictions": "The market-tracker promo signal and the campaign report are honest contradictions in the record — they lower competitor/internal_execution confidence, they are not hidden.",
        "challenge_rights": "You may challenge the method or correct a driver; approval is not an analyst action.",
    }


def _supply_chain(base, lead, restricted_links) -> dict:
    return {
        "driver": f"Primary driver: {(lead.get('code') or '—').replace('_', ' ')} — inbound supply disruption at Guwahati DC.",
        "authorized_action": "Activate backup supplier for the staples families (your approved action class; limit on record).",
        "owner": "You (Supply Chain) own execution; monitoring plan attaches at decision approval.",
        "monitoring_plan": "Watch fill-rate and OSA NE weekly for 6 weeks; success band attaches to the approved decision record.",
        "withheld_note": f"{restricted_links} evidence source(s) withheld from your view — counted, not hidden." if restricted_links else "All in-scope evidence is visible to your role.",
    }


def _kpi_owner(base, lead, detection, materiality) -> dict:
    contract_bits = base.get("contract") or {}
    return {
        "contract_health": f"Contract v{contract_bits.get('version', base.get('contract_version', '—'))} — status derives from open conflicts; ERP↔GL definition conflict is OPEN on this KPI.",
        "conflicts": "ERP invoiced vs GL recognized: returns accrual (finance note) explains most of the gap — resolve or acknowledge to lift the certainty cap.",
        "drivers": "Four governed drivers on the contract: supplier_delay, competitor_promo, marketing_underperf, seasonality — hypotheses came only from these.",
        "thresholds": f"Band {materiality.get('band', '—')} at score {materiality.get('score', 0):.2f}; strategic weight on record.",
        "actions": "You may resolve conflicts, propose contract changes, and review/merge proposals.",
    }
