"""Materiality engine — significance × business impact (arch G, §9).

score   = significance × clamp(log1p(impact)/10, 0, 1)
impact  = |deviation_pct| × exposure_rs_per_point + margin_weight × |deviation_pct| + strategic_weight
bands:  ≥0.70 CRITICAL · ≥0.40 ELEVATED · ≥0.15 WATCH · else NOISE
Contract thresholds may FLOOR a band (master §8.4) — recorded honestly in the
arithmetic (`floored: true`). Cold-start KPIs are monitor-only by design.
Every score stores its full arithmetic for the "why is this CRITICAL?" drill-down.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

BANDS = (("CRITICAL", 0.70), ("ELEVATED", 0.40), ("WATCH", 0.15), ("NOISE", 0.0))
BAND_ORDER = {"CRITICAL": 4, "ELEVATED": 3, "WATCH": 2, "NOISE": 1}


@dataclass
class TriageResult:
    significance: float
    exposure_rs: float
    impact: float
    impact_norm: float
    score: float
    raw_band: str
    band: str
    floored: bool
    monitor_only: bool
    arithmetic: dict


def band_for(score: float) -> str:
    for name, threshold in BANDS:
        if score >= threshold:
            return name
    return "NOISE"


def triage(
    *,
    significance: float,
    deviation_pct: float,
    exposure_rs_per_point: float,
    margin_weight: float,
    strategic_weight: float,
    risk_factor: float = 0.0,
    floor_band: str | None = None,
    cold_start: bool = False,
    threshold_comparison: dict | None = None,
) -> TriageResult:
    exposure = abs(deviation_pct) * exposure_rs_per_point
    impact = exposure + margin_weight * abs(deviation_pct) + strategic_weight + risk_factor
    impact_norm = max(0.0, min(1.0, math.log1p(impact) / 10.0))
    score = significance * impact_norm
    raw_band = band_for(score)
    band = raw_band
    floored = False
    if floor_band and floor_band in BAND_ORDER and BAND_ORDER[floor_band] > BAND_ORDER[raw_band]:
        band = floor_band
        floored = True
    monitor_only = cold_start  # cold start ⇒ monitor-only mode regardless of score
    arithmetic = {
        "formula": "significance × clamp(log1p(impact)/10, 0, 1)",
        "significance": round(significance, 4),
        "significance_note": "clamp((max(robust_z, 6×anomaly)−2)/4, 0, 1)",
        "deviation_pct": round(deviation_pct, 3),
        "exposure_rs_per_point": exposure_rs_per_point,
        "exposure_rs": round(exposure, 2),
        "margin_weight": margin_weight,
        "strategic_weight": strategic_weight,
        "risk_factor": risk_factor,
        "impact": round(impact, 2),
        "impact_norm": round(impact_norm, 4),
        "score": round(score, 4),
        "raw_band": raw_band,
        "floor_band": floor_band,
        "floored": floored,
        "monitor_only": monitor_only,
        "threshold_comparison": threshold_comparison or {},
    }
    return TriageResult(
        significance=significance,
        exposure_rs=round(exposure, 2),
        impact=round(impact, 2),
        impact_norm=round(impact_norm, 4),
        score=round(score, 4),
        raw_band=raw_band,
        band="COLD START" if monitor_only else band,
        floored=floored,
        monitor_only=monitor_only,
        arithmetic=arithmetic,
    )
