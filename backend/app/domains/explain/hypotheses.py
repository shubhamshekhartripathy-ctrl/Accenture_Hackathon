"""Hypothesis engine: competing explanations with deterministic scoring (arch H.3–H.5).

Stages: hypothesize (draft from contract drivers — LLM may word, templates are the
fallback) → gather (scoped evidence retrieval, claim links) → score_rank (rules+
stats only). The LLM owns zero numbers: every score below is computed from
evidence rows and the pattern-reliability table.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...errors import AppError
from ...models.evidence import EvidenceRecord, HypothesisEvidence, InvestigationHypothesis, PatternReliability
from ...models.investigation import Investigation

# Scoring (arch H.4, calibrated; weights/masses are seeded fabric facts):
#   balance = (support − contradiction) / (support + contradiction + 1)
#   confidence = 0.35·balance + gate·(0.20·freshness_avg + 0.15·source_agreement) + 0.30·pattern_prior
#   gate = 1 when support > 0 — no corroboration credit for evidence-less hypotheses.
W_BALANCE, W_FRESH, W_AGREE, W_PRIOR = 0.35, 0.20, 0.15, 0.30

# Deterministic statement templates (LLM drafting plugs in at S10; identical I/O).
_STATEMENTS = {
    "supply_disruption": "Supplier disruption on inbound supply (Guwahati DC) is driving the movement via fill-rate and OSA collapse.",
    "competitor_action": "A competitor promotion is diverting demand in the affected region.",
    "internal_execution": "Marketing underperformance (spend/weight vs plan) is suppressing demand.",
    "seasonal": "Seasonal demand shift explains the movement (no operational cause).",
    "measurement": "A measurement/panel-composition shift explains the movement (no real demand change).",
    "transport_delay": "Outbound transport delay from the DC is degrading availability.",
    "demand_surge": "An exogenous demand surge (e.g., monsoon pull-forward) is consuming stock.",
    "quality_returns": "Quality returns are removing sellable stock from the network.",
    "launch_ramp": "The launch ramp differs from the category analogue baseline.",
}

_PATHS = {
    "supply_disruption": ["Apex Supplier", "DELAYED_BY", "Guwahati DC", "IMPACTS", "Inventory Cover NE", "IMPACTS", "OSA NE", "IMPACTS", "Revenue NE"],
    "competitor_action": ["Market Tracker", "NO_NE_PROMO_SIGNAL", "POS NE"],
    "internal_execution": ["Campaign Report", "WITHIN_PLAN", "Marketing ROI", "WEAK_LINK", "Revenue NE"],
    "seasonal": ["Calendar", "NO_SEASONAL_EDGE", "Revenue NE"],
    "measurement": ["Audit Panel", "SAMPLE_REWEIGHTED", "POS South"],
    "transport_delay": ["Transport Desk", "DELAYED_BY", "Guwahati DC", "IMPACTS", "Inventory Cover NE", "IMPACTS", "OSA NE"],
    "demand_surge": ["Demand Forecast", "PULL_FORWARD", "Inventory Cover NE"],
    "quality_returns": ["Quality Desk", "RETURNS_BLOCK", "Sellable Stock", "IMPACTS", "Inventory Cover NE"],
    "launch_ramp": ["Launch Plan", "DEVIATES_FROM", "Category Analogue"],
}


def hypothesize(
    db: Session, organization_id: str, investigation: Investigation, contract
) -> list[InvestigationHypothesis]:
    """Draft k rival hypotheses from the scenario-configured contract drivers.

    Deterministic template wording (S10's gateway may draft phrasing through the
    same I/O); the hypothesis SET is always contract-driven — nothing invented.
    """
    drivers = sorted(contract.drivers, key=lambda d: d.rank)
    if not drivers:
        raise AppError("NO_DRIVERS", "Contract declares no drivers — hypothesis space shrunk; refuses to invent", 422)

    db.query(HypothesisEvidence).filter(
        HypothesisEvidence.organization_id == organization_id,
        HypothesisEvidence.investigation_id == investigation.id,
    ).delete()
    db.query(InvestigationHypothesis).filter(
        InvestigationHypothesis.organization_id == organization_id,
        InvestigationHypothesis.investigation_id == investigation.id,
    ).delete()

    rows = []
    for d in drivers:
        rows.append(InvestigationHypothesis(
            organization_id=organization_id,
            investigation_id=investigation.id,
            kpi_id=investigation.kpi_id,
            code=d.driver_code,
            statement=_STATEMENTS.get(d.hypothesis_class, f"{d.name} explains the movement."),
            driver_code=d.driver_code,
            pattern_class=d.hypothesis_class,
            reasoning_path=_PATHS.get(d.hypothesis_class, [d.name, "DECLARED_DRIVER", investigation.kpi.code if investigation.kpi else "KPI"]),
        ))
    db.add_all(rows)
    db.flush()
    return rows


def gather_evidence(
    db: Session, organization_id: str, investigation: Investigation,
    hypotheses: list[InvestigationHypothesis], retriever_role: str = "ANALYST",
) -> list[HypothesisEvidence]:
    """Scoped retrieval: link evidence documents to hypotheses by driver class.

    States: SUPPORTING / CONTRADICTING from the document polarity; STALE
    overrides when freshness has decayed below 0.5 (discounted, still counted);
    RESTRICTED marks documents the retrieving context may not open (counted
    honestly as withheld). No evidence without a declared source (H.5).
    """
    kpi = investigation.kpi
    links: list[HypothesisEvidence] = []
    for h in hypotheses:
        docs = (
            db.query(EvidenceRecord)
            .filter(
                EvidenceRecord.organization_id == organization_id,
                EvidenceRecord.kpi_code == kpi.code,
                EvidenceRecord.driver_class == h.pattern_class,
            )
            .all()
        )
        for doc in docs:
            if doc.access_roles and retriever_role not in doc.access_roles:
                # Withheld for this context: counted honestly, weight 0, lowers
                # nothing silently — surfaced as "n sources withheld" downstream.
                links.append(HypothesisEvidence(
                    organization_id=organization_id, investigation_id=investigation.id,
                    hypothesis_id=h.id, evidence_id=doc.id, state="RESTRICTED", weight=0.0,
                ))
                continue
            if doc.polarity == "SUPPORTS":
                state, weight = "SUPPORTING", doc.support_weight
            elif doc.polarity == "CONTRADICTS":
                state, weight = "CONTRADICTING", doc.contradiction_weight
            else:
                continue
            if doc.age_days > 14 and doc.freshness_score < 0.5:
                state = "STALE"
                weight = weight * 0.5  # stale evidence is discounted — visibly
            links.append(HypothesisEvidence(
                organization_id=organization_id,
                investigation_id=investigation.id,
                hypothesis_id=h.id,
                evidence_id=doc.id,
                state=state,
                weight=weight,
            ))
    db.add_all(links)
    db.flush()
    return links


def score_and_rank(
    db: Session, organization_id: str, investigation: Investigation,
    hypotheses: list[InvestigationHypothesis], confidence_cap: float,
) -> list[InvestigationHypothesis]:
    """Deterministic scoring (rules+stats; the LLM has no vote here)."""
    priors = {
        p.pattern_class: p.prior
        for p in db.query(PatternReliability).filter(PatternReliability.organization_id == organization_id).all()
    }
    for h in hypotheses:
        links = (
            db.query(HypothesisEvidence)
            .filter(HypothesisEvidence.hypothesis_id == h.id)
            .all()
        )
        supporting = [l for l in links if l.state in ("SUPPORTING", "STALE")]
        contradicting = [l for l in links if l.state == "CONTRADICTING"]
        restricted = [l for l in links if l.state == "RESTRICTED"]

        S = sum(l.weight for l in supporting)
        C = sum(l.weight for l in contradicting)
        freshness = (
            sum(l.evidence.freshness_score * l.weight for l in supporting) / S if S > 0 else 0.0
        )
        engaged = S + C
        agreement = (S / engaged) if engaged > 0 else 0.0
        balance = (S - C) / (S + C + 1.0)
        prior = priors.get(h.pattern_class, 0.05)
        gate = 1.0 if S > 0 else 0.0
        confidence = max(0.0, W_BALANCE * balance + gate * (W_FRESH * freshness + W_AGREE * agreement) + W_PRIOR * prior)
        # Restricted evidence honestly lowers confidence (withheld sources count).
        confidence *= max(0.5, 1.0 - 0.10 * len(restricted))

        h.support_mass = round(S, 4)
        h.contradiction_mass = round(C, 4)
        h.balance = round(balance, 4)
        h.freshness_avg = round(freshness, 4)
        h.source_agreement = round(agreement, 4)
        h.pattern_prior = round(prior, 4)
        h.confidence = round(confidence, 4)
        h.evidence_counts = {
            "supporting": len([l for l in supporting if l.state == "SUPPORTING"]),
            "stale": len([l for l in supporting if l.state == "STALE"]),
            "contradicting": len(contradicting),
            "restricted": len(restricted),
        }
        db.add(h)

    ranked = sorted(hypotheses, key=lambda h: (-h.confidence, h.code))
    for i, h in enumerate(ranked, start=1):
        h.rank = i
        # The case-level certainty carries the reconciliation cap: lead × cap
        # (arch I "0.47×0.93 = 0.44"; hero "0.82 × 0.86 → 0.71"). Others show raw.
        h.final_confidence = round(h.confidence * confidence_cap, 4) if i == 1 else h.confidence
        db.add(h)
    db.flush()
    return ranked


def for_investigation(db: Session, organization_id: str, investigation_id: str):
    return (
        db.query(InvestigationHypothesis)
        .filter(
            InvestigationHypothesis.organization_id == organization_id,
            InvestigationHypothesis.investigation_id == investigation_id,
        )
        .order_by(InvestigationHypothesis.rank)
        .all()
    )


def serialize(h: InvestigationHypothesis, links: list[HypothesisEvidence] | None = None) -> dict:
    return {
        "id": h.id,
        "code": h.code,
        "statement": h.statement,
        "pattern_class": h.pattern_class,
        "rank": h.rank,
        "status": h.status,
        "support_mass": h.support_mass,
        "contradiction_mass": h.contradiction_mass,
        "balance": h.balance,
        "freshness_avg": h.freshness_avg,
        "source_agreement": h.source_agreement,
        "pattern_prior": h.pattern_prior,
        "confidence": h.confidence,
        "final_confidence": h.final_confidence,
        "evidence_counts": h.evidence_counts,
        "reasoning_path": h.reasoning_path,
    }
