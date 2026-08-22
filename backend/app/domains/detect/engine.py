"""Detection engine — seasonal baseline, robust z, CI, cold-start flag (arch G/§9.1).

Pure statistics; no LLM ever touches these numbers. Method and model version
are persisted per result.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

METHOD = "seasonal_median_robust_z"
MODEL_VERSION = "1.0.0"
ROBUST_Z_CONSTANT = 1.4826  # MAD → sigma consistency


@dataclass
class DetectResult:
    baseline: float
    expected_value: float
    ci_lo: float
    ci_hi: float
    deviation: float
    deviation_pct: float
    robust_z: float
    anomaly_score: float
    significance: float
    history_n: int
    cold_start: bool
    method: str = METHOD
    model_version: str = MODEL_VERSION


def median(xs: list[float]) -> float:
    return statistics.median(xs)


def mad(xs: list[float], center: float | None = None) -> float:
    c = median(xs) if center is None else center
    return median([abs(x - c) for x in xs])


def robust_sigma(xs: list[float], center: float | None = None) -> float:
    return ROBUST_Z_CONSTANT * mad(xs, center)


def detect(history: list[float], current: float, min_history: int) -> DetectResult:
    """Baseline = pre-movement window median; robust z vs MAD-sigma; 95% CI."""
    baseline = median(history)
    sigma = robust_sigma(history, center=baseline)
    sigma = sigma if sigma > 1e-9 else 1e-9  # degenerate guard for identical histories
    deviation = current - baseline
    deviation_pct = (deviation / baseline * 100.0) if baseline != 0 else 0.0
    z = abs(deviation) / sigma
    anomaly = min(1.0, z / 6.0)
    significance = max(0.0, min(1.0, (max(z, 6.0 * anomaly) - 2.0) / 4.0))
    ci_lo, ci_hi = baseline - 1.96 * sigma, baseline + 1.96 * sigma
    cold_start = len(history) < min_history
    return DetectResult(
        baseline=round(baseline, 4),
        expected_value=round(baseline, 4),
        ci_lo=round(ci_lo, 4),
        ci_hi=round(ci_hi, 4),
        deviation=round(deviation, 4),
        deviation_pct=round(deviation_pct, 3),
        robust_z=round(z, 3),
        anomaly_score=round(anomaly, 4),
        significance=round(significance, 4),
        history_n=len(history),
        cold_start=cold_start,
    )
