"""Reconciliation engine — NORMALIZE → COMPARE → CLASSIFY → SCORE → ROUTE (arch F).

Deterministic penalties (locked):
    definition_conflict  0.12
    stale_source         0.00 / 0.06 / 0.12 / 0.15   (≤2d / 3–5d / 6–9d / ≥10d beyond tolerance)
    grain_mismatch       0.05
    coverage_gap         0.10
    hierarchy_unresolved 0.08
    calendar_mismatch    0.05
    entity_mismatch      0.05 (alias resolution failure)
    reliability = clamp(1 − Σ penalties, 0.4, 1.0)
    verdict: CONFLICTED if active definition conflict OR reliability < 0.75;
             MINOR if any penalty; else CONSISTENT
    confidence_cap = reliability + 0.10 (≤ 1.0)

Freshness is measured against the deterministic DEMO CLOCK (the newest
observation across the KPI's sources), so replays are reproducible.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

PENALTY_DEFINITION = 0.12
PENALTY_GRAIN = 0.05
PENALTY_COVERAGE = 0.10
PENALTY_HIERARCHY = 0.08
PENALTY_CALENDAR = 0.05
PENALTY_ENTITY = 0.05
STALE_BRACKETS = ((2, 0.00), (5, 0.06), (9, 0.12))  # days beyond tolerance → penalty (else 0.15)
STALE_MAX = 0.15
RELIABILITY_FLOOR = 0.4
CONFLICTED_BELOW = 0.75

CADENCE_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}


def stale_penalty(days_beyond_tolerance: int) -> float:
    for bound, penalty in STALE_BRACKETS:
        if days_beyond_tolerance <= bound:
            return penalty
    return STALE_MAX


def reliability(penalties: list[float]) -> float:
    return max(RELIABILITY_FLOOR, min(1.0, 1.0 - sum(penalties)))


@dataclass
class SourceReading:
    source_code: str
    source_id: str
    value: float | None
    period_key: str
    age_days: int
    expected_cadence: str
    tolerance_days: int
    tolerance_pct: float
    grain: str
    expected_grain: str
    is_authoritative: bool
    calendar_key: str = ""
    classification: str = "definition|refresh|grain|hierarchy|calendar|coverage|entity"


@dataclass
class ReconcileResult:
    verdict: str
    reliability_score: float
    confidence_cap: float
    working_value: float
    working_source_id: str
    working_justification: str
    penalties: dict = field(default_factory=dict)
    conflicts: list[dict] = field(default_factory=list)
    freshness_profile: list[dict] = field(default_factory=list)


def run_engine(readings: list[SourceReading], period_key: str, kpi_unit: str) -> ReconcileResult:
    """Pure engine: no DB. The service layer gathers readings and persists outputs."""
    conflicts: list[dict] = []
    penalties: dict[str, float] = {}

    def add_penalty(code: str, amount: float) -> None:
        penalties[code] = max(penalties.get(code, 0.0), amount)

    # --- FRESHNESS (all declared sources) ------------------------------------
    for r in readings:
        cadence_days = CADENCE_DAYS.get(r.expected_cadence, 7)
        beyond = max(0, r.age_days - (cadence_days + r.tolerance_days))
        penalty = stale_penalty(beyond) if r.age_days > 0 else 0.0
        if penalty > 0:
            add_penalty("stale_source", penalty)
            conflicts.append(
                _conflict(
                    "refresh", "MEDIUM" if penalty < 0.12 else "HIGH", r.source_id, None,
                    r.value, None, -penalty, penalty,
                    f"{r.source_code} is {r.age_days}d old — {beyond}d beyond its "
                    f"{r.expected_cadence} cadence + {r.tolerance_days}d tolerance; evidence discounted.",
                    route="data_owner",
                )
            )

    # --- COMPARE + CLASSIFY (value-asserting sources) -------------------------
    valued = [r for r in readings if r.value is not None]
    for i in range(len(valued)):
        for j in range(i + 1, len(valued)):
            a, b = valued[i], valued[j]
            if a.source_id == b.source_id:
                continue
            base = max(abs(a.value), abs(b.value)) or 1.0
            gap_pct = abs(a.value - b.value) / base * 100.0
            tol_pct = min(a.tolerance_pct, b.tolerance_pct) or max(a.tolerance_pct, b.tolerance_pct)
            if gap_pct <= tol_pct:
                continue
            # definition conflict: same KPI, different formula/config across sources
            if a.calendar_key and b.calendar_key and a.calendar_key != b.calendar_key:
                calendar_note = f" calendar boundaries differ ({a.calendar_key} vs {b.calendar_key})."
            else:
                calendar_note = ""
            conflicts.append(
                _conflict(
                    "definition", "HIGH", a.source_id, b.source_id, a.value, b.value,
                    -PENALTY_DEFINITION, PENALTY_DEFINITION,
                    f"{a.source_code} and {b.source_code} disagree by {gap_pct:.1f}% "
                    f"(> {tol_pct:.1f}% tolerance): different definitions of the same KPI."
                    f"{calendar_note} Not merged.",
                    route="kpi_owner",
                )
            )
            add_penalty("definition", PENALTY_DEFINITION)

    # --- GRAIN ---------------------------------------------------------------
    authoritative_ref = next((r for r in valued if r.is_authoritative), None)
    for r in readings:
        if r.expected_grain and r.grain and r.grain.strip().lower() != r.expected_grain.strip().lower():
            add_penalty("grain", PENALTY_GRAIN)
            conflicts.append(
                _conflict(
                    "grain", "LOW", r.source_id, None, r.value, None, -PENALTY_GRAIN, PENALTY_GRAIN,
                    f"{r.source_code} publishes at '{r.grain}' vs contract grain '{r.expected_grain}' — "
                    "aggregation performed with documented information loss.",
                    route="analyst_note",
                )
            )
    # Cross-source coarse-grain: a second value-asserting source at a different grain
    # than the authoritative one flags an information-loss comparison — UNLESS the pair
    # already raised a definition conflict (the definition penalty covers ERP-vs-GL).
    if authoritative_ref is not None:
        for r in valued:
            if r.source_id == authoritative_ref.source_id:
                continue
            grains_differ = r.grain.strip().lower() != authoritative_ref.grain.strip().lower()
            already_definition = any(
                c["conflict_type"] == "definition"
                and {c["source_a_id"], c["source_b_id"]} == {r.source_id, authoritative_ref.source_id}
                for c in conflicts
            )
            if grains_differ and not already_definition:
                add_penalty("grain", PENALTY_GRAIN)
                conflicts.append(
                    _conflict(
                        "grain", "LOW", r.source_id, authoritative_ref.source_id, r.value,
                        authoritative_ref.value, -PENALTY_GRAIN, PENALTY_GRAIN,
                        f"{r.source_code} ('{r.grain}') and {authoritative_ref.source_code} "
                        f"('{authoritative_ref.grain}') assert this KPI at different grains — "
                        "coarse-grain comparison flagged with documented information loss.",
                        route="analyst_note",
                    )
                )
                break  # one grain penalty per reconcile cycle

    # --- WORKING VALUE (authoritative source; never a silent merge) ----------
    authoritative = next((r for r in valued if r.is_authoritative), None)
    if authoritative is None:
        valued_sorted = sorted(valued, key=lambda r: r.source_code)
        authoritative = valued_sorted[0] if valued_sorted else None
    if authoritative is None:
        working_value = 0.0
        working_source_id = ""
        justification = "No value-asserting source available."
    else:
        working_value = authoritative.value
        working_source_id = authoritative.source_id
        dissenters = [
            f"{r.source_code} reports {r.value:.1f} {kpi_unit} (deferred, not merged)"
            for r in valued
            if r.source_id != authoritative.source_id and abs((r.value or 0) - working_value) > 1e-9
        ]
        justification = (
            f"Working value {working_value:.1f} {kpi_unit} ({authoritative.source_code}, authoritative, "
            f"{authoritative.expected_cadence})."
            + (" " + " ".join(dissenters) + " Deferred to close reconciliation." if dissenters else "")
        )

    rel = reliability(list(penalties.values()))
    verdict = "CONSISTENT" if not penalties else ("CONFLICTED" if _definition_active(conflicts) or rel < CONFLICTED_BELOW else "MINOR")
    cap = min(1.0, rel + 0.10)

    return ReconcileResult(
        verdict=verdict,
        reliability_score=round(rel, 4),
        confidence_cap=round(cap, 4),
        working_value=working_value,
        working_source_id=working_source_id,
        working_justification=justification,
        penalties={k: round(v, 4) for k, v in penalties.items()},
        conflicts=conflicts,
        freshness_profile=[
            {
                "source_id": r.source_id,
                "source_code": r.source_code,
                "age_days": r.age_days,
                "expected_cadence": r.expected_cadence,
                "tolerance_days": r.tolerance_days,
                "beyond_tolerance_days": max(0, r.age_days - (CADENCE_DAYS.get(r.expected_cadence, 7) + r.tolerance_days)),
                "discounted": r.age_days > (CADENCE_DAYS.get(r.expected_cadence, 7) + r.tolerance_days),
            }
            for r in readings
        ],
    )


def _definition_active(conflicts: list[dict]) -> bool:
    return any(c["conflict_type"] == "definition" and c["resolution_state"] == "OPEN" for c in conflicts)


def _conflict(
    ctype: str, severity: str, source_a, source_b, value_a, value_b,
    impact: float, penalty: float, explanation: str, route: str,
) -> dict:
    route_map = {"kpi_owner": ("KPI_OWNER",), "data_owner": ("KPI_OWNER", "ADMIN"), "analyst_note": ("ANALYST",)}
    return {
        "conflict_type": ctype,
        "severity": severity,
        "source_a_id": source_a,
        "source_b_id": source_b,
        "value_a": value_a,
        "value_b": value_b,
        "confidence_impact": round(impact, 4),
        "penalty": penalty,
        "explanation": explanation,
        "route": route,
        "routed_role": route_map.get(route, ("KPI_OWNER",))[0],
        "resolution_state": "OPEN",
    }
