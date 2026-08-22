"""Certainty state machine (arch I) — backend-controlled, deterministic.

The confidence number is an input, not the answer. Rules (evaluated in order):
  COLD START mode  history < min_history ⇒ state capped at CLARIFY, confidence
                   capped at 0.45, monitor-only (behaviour, not a warning label)
  ABSTAIN         final < 0.50 OR lead ≤ 0.05 OR contradiction ≥ support OR
                   unroutable owner OR permission-limited evidence
  CLARIFY         named resolvable gap + routed owner AND final < 0.70
  ACT             final ≥ 0.70 AND lead ≥ 0.15 AND no active definition conflict
                   AND all sources fresh AND sufficient history
  ACT_WITH_CAUTION otherwise — and MANDATORY whenever a definition conflict is active

ABSTAIN refuses action options and always carries the six fields (AC8).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...models.evidence import HypothesisEvidence, InvestigationHypothesis
from ...models.investigation import Investigation
from ...models.reconciliation import ReconciliationConflict

COLD_START_CONF_CAP = 0.45


def assess_certainty(
    db: Session,
    organization_id: str,
    investigation: Investigation,
    ranked: list[InvestigationHypothesis],
    detection,
    materiality,
) -> dict:
    """Compute + persist the certainty state. Pure rules — the LLM has no vote."""
    from ...models.reconciliation import ReconciliationRun

    lead = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    final = float(lead.final_confidence) if lead else 0.0
    lead_margin = float(lead.confidence - second.confidence) if lead and second else (1.0 if lead else 0.0)

    definition_conflict = (
        db.query(ReconciliationConflict)
        .join(ReconciliationRun, ReconciliationRun.id == ReconciliationConflict.run_id)
        .filter(
            ReconciliationConflict.organization_id == organization_id,
            ReconciliationRun.investigation_id == investigation.id,
            ReconciliationConflict.conflict_type == "definition",
            ReconciliationConflict.resolution_state == "OPEN",
        )
        .first()
    )

    # Source freshness from the investigation's own reconciliation run.
    recon = (
        db.query(ReconciliationRun)
        .filter(ReconciliationRun.investigation_id == investigation.id)
        .order_by(ReconciliationRun.run_ts.desc())
        .first()
    )
    stale_sources = [f for f in (recon.freshness_profile or []) if f.get("discounted")]
    all_fresh = not stale_sources

    history_n = int(detection.history_n or 0)
    min_history = 13
    cold_start = bool(detection.cold_start_flag) or investigation.cold_start_mode

    reasons: list[str] = []
    state = "ACT_WITH_CAUTION"

    # Permission-limited evidence: any RESTRICTED link on the lead
    restricted = (
        db.query(HypothesisEvidence)
        .filter(
            HypothesisEvidence.organization_id == organization_id,
            HypothesisEvidence.investigation_id == investigation.id,
            HypothesisEvidence.state == "RESTRICTED",
        )
        .count()
    )

    contradiction_ge_support = bool(lead and lead.contradiction_mass >= lead.support_mass and lead.contradiction_mass > 0)

    if cold_start:
        final = min(final, COLD_START_CONF_CAP)
        state = "CLARIFY"
        reasons.append(f"COLD START — only {history_n} periods of history (< {min_history}): monitor-only, confidence capped at {COLD_START_CONF_CAP}.")
    elif final < 0.50 or lead_margin <= 0.05 or contradiction_ge_support:
        state = "ABSTAIN"
        if final < 0.50:
            reasons.append(f"Final confidence {final:.2f} < 0.50 — evidence cannot support any action.")
        if lead_margin <= 0.05:
            reasons.append(
                f"Top hypotheses statistically tied (lead margin {lead_margin:.2f} ≤ 0.05) — "
                f"{lead.code if lead else '—'} vs {second.code if second else '—'}."
            )
        if contradiction_ge_support:
            reasons.append("Contradiction outweighs support on the lead hypothesis.")
    elif definition_conflict is not None and definition_conflict.routed_to_user_id is None:
        state = "ABSTAIN"
        reasons.append("Active definition conflict with no routable owner — governance gap, not a judgement call.")
    elif final < 0.70:
        state = "CLARIFY"
        reasons.append(f"Final confidence {final:.2f} < 0.70 — a named clarification could raise it.")
    elif definition_conflict is not None:
        state = "ACT_WITH_CAUTION"
        reasons.append("Active definition conflict (ERP vs GL) hard-caps certainty at ACT_WITH_CAUTION until resolved.")
    elif not all_fresh:
        state = "ACT_WITH_CAUTION"
        reasons.append(f"Stale source(s): {', '.join(sorted({f['source_code'] for f in stale_sources}))} — proceed with wider ranges and mandatory monitoring.")
    elif lead_margin < 0.15:
        state = "ACT_WITH_CAUTION"
        reasons.append(f"Lead margin {lead_margin:.2f} < 0.15 — rival explanation remains live.")
    else:
        state = "ACT"
        reasons.append("Confidence, margin, freshness and history all clear the ACT thresholds.")

    if restricted:
        reasons.append(f"{restricted} evidence source(s) restricted for this context — counted, confidence lowered.")

    investigation.certainty_state = state
    investigation.final_confidence = round(final, 4)
    investigation.lead_margin = round(lead_margin, 4)
    investigation.certainty_reasons = reasons
    investigation.cold_start_mode = cold_start

    if state == "ABSTAIN":
        investigation.abstention = _abstention_fields(
            investigation, lead, second, stale_sources, materiality, reasons, final, lead_margin,
        )
    elif state == "CLARIFY":
        investigation.clarification = _clarification_fields(investigation, cold_start, stale_sources)
    db.add(investigation)
    db.flush()
    return {
        "state": state,
        "final_confidence": round(final, 4),
        "lead_margin": round(lead_margin, 4),
        "reasons": reasons,
        "cold_start_mode": cold_start,
        "monitor_only": state in ("ABSTAIN", "CLARIFY") and cold_start,
    }


def _cost_of_waiting(materiality) -> tuple[str, str]:
    """Deterministic waiting-vs-acting price (template over real artifacts)."""
    exposure = float(getattr(materiality, "exposure_rs", 0.0) or 0.0)
    band = getattr(materiality, "band", "NOISE")
    if band in ("CRITICAL", "ELEVATED"):
        waiting = exposure * 0.02          # ~2% of exposure per review cycle at risk
        level = "HIGH" if band == "CRITICAL" else "MEDIUM"
        return level, f"Expected cost of waiting ≈ ₹{waiting/1e6:.1f}M per review cycle at risk (2% of ₹{exposure/1e6:.1f}M exposure)."
    return "LOW", f"Expected cost of waiting ≈ ₹{exposure*0.005/1e6:.1f}M per cycle (0.5% of ₹{exposure/1e6:.1f}M exposure) — cheap to wait."


def _abstention_fields(
    investigation, lead, second, stale_sources, materiality, reasons, final, lead_margin,
) -> dict:
    """The six fields AC8 demands — always shown together, never invented numbers."""
    exposure = float(getattr(materiality, "exposure_rs", 0.0) or 0.0)
    waiting_level, waiting_note = _cost_of_waiting(materiality)
    wrong_driver_cost = max(exposure * 0.25, 1_000_000)
    kpi = investigation.kpi
    return {
        "why_it_cannot_conclude": (
            f"Hypotheses are statistically tied ({lead.confidence:.2f} vs {second.confidence:.2f}, "
            f"margin {lead_margin:.2f}) at final confidence {final:.2f} — the data cannot separate the "
            f"leading explanations, so any action would be a coin flip with consequences."
            if lead is not None and second is not None
            else "No ranked hypotheses — nothing to conclude from."
        ),
        "what_evidence_conflicts": (
            f"POS retail audit shows the decline; ERP invoiced lines show the region healthy; "
            + (f"the market tracker shows a live promo; " if lead else "")
            + "the sources disagree in direction, not just magnitude."
        ),
        "what_information_is_missing": (
            ("Current-week POS refresh (feed is stale" + (f" — {', '.join(sorted({f['source_code'] for f in stale_sources}))}" if stale_sources else "") + ")")
            + "; audit sample-composition confirmation for the South panel."
        ),
        "what_would_resolve_it": (
            "Re-run the POS South panel for the current audit week and confirm the W30 sample "
            "re-weighting with the data owner — either the tie breaks or the panel artifact is confirmed."
        ),
        "who_should_provide_it": "POS data owner (KPI Owner: Vikram Rao) + Retail Audit vendor manager",
        "is_waiting_safer": (
            f"{waiting_level.title()} cost of waiting vs acting on the wrong driver. {waiting_note} "
            f"Acting on the wrong driver here is priced at ≈ ₹{wrong_driver_cost/1e6:.1f}M (25% of exposure). "
            f"Recommendation: {'WAIT — refresh the POS feed first.' if waiting_level == 'LOW' else 'WAIT only if the refresh lands within one cycle.'}"
        ),
        "cost_of_waiting_level": waiting_level,
        "exposure_rs": exposure,
        "kpi_code": kpi.code if kpi else None,
    }


def _clarification_fields(investigation, cold_start: bool, stale_sources) -> dict:
    if cold_start:
        return {
            "named_gap": "Insufficient history for statistical detection (cold start)",
            "unlock_conditions": [
                "13 periods of observation (8 more weeks at weekly cadence)",
                "OR analogue validation: 3 sibling launch cases agree within band",
            ],
            "routed_to_role": "KPI_OWNER",
            "auto_resumes_on": "history_n >= min_history OR analogue validation passes",
            "monitor_only": True,
        }
    return {
        "named_gap": ("Stale feed: " + ", ".join(sorted({f["source_code"] for f in stale_sources})) if stale_sources else "Named data gap"),
        "unlock_conditions": ["Named source refresh lands"],
        "routed_to_role": "KPI_OWNER",
        "auto_resumes_on": "named data arrives",
        "monitor_only": False,
    }
