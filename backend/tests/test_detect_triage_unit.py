"""Detection + materiality engine units — the locked demo arithmetic."""
from __future__ import annotations

from app.domains.detect.engine import detect, mad, median
from app.domains.triage.engine import band_for, triage


HERO_BASE13 = [-2.0, -1.5, -1.0, -0.5, -0.5, -0.5, 0.0, 0.5, 0.5, 0.5, 1.0, 1.5, 2.0]


def _hero_history() -> list[float]:
    scale = 2.2239 / (1.4826 * 0.5)
    return [95.45 + scale * d for d in HERO_BASE13]


class TestDetect:
    def test_median_and_mad_construction(self):
        h = _hero_history()
        assert abs(median(h) - 95.45) < 1e-6
        assert abs(mad(h) - 2.2239 / 1.4826) < 1e-3

    def test_locked_revenue_detection(self):
        h = _hero_history()
        d = detect(h, 84.0, min_history=13)
        assert abs(d.baseline - 95.45) < 1e-3
        assert abs(d.deviation_pct - (-12.0)) < 0.1          # −12% (locked)
        assert abs(d.robust_z - 5.1) < 0.15                   # 5.1σ (locked)
        assert 84.0 < d.ci_lo                                  # current is BELOW the CI band (real decline)
        assert d.history_n == 13
        assert d.cold_start is False
        assert d.method == "seasonal_median_robust_z"

    def test_marketing_detection(self):
        scale = 0.0592 / (1.4826 * 0.5)
        h = [3.10 + scale * d for d in HERO_BASE13]
        d = detect(h, 2.976, min_history=13)
        assert abs(d.deviation_pct - (-4.0)) < 0.1            # −4% (locked)
        assert abs(d.robust_z - 2.1) < 0.15                   # 2.1σ (locked)

    def test_cold_start_flag(self):
        d = detect([2.10, 2.35, 2.62, 2.85], 2.66, min_history=13)
        assert d.cold_start is True
        assert d.history_n == 4


class TestTriage:
    def test_bands(self):
        assert band_for(0.90) == "CRITICAL"
        assert band_for(0.70) == "CRITICAL"
        assert band_for(0.55) == "ELEVATED"
        assert band_for(0.40) == "ELEVATED"
        assert band_for(0.20) == "WATCH"
        assert band_for(0.05) == "NOISE"

    def test_locked_revenue_critical(self):
        # z=5.148 → significance (5.148−2)/4 = 0.787; exposure 12×716,667 = ₹8.6M → norm 1
        sig = max(0.0, min(1.0, (5.148 - 2) / 4))
        t = triage(
            significance=sig, deviation_pct=-11.996, exposure_rs_per_point=716_667,
            margin_weight=0.15, strategic_weight=0.8,
        )
        assert t.raw_band == "CRITICAL"
        assert abs(t.exposure_rs - 8_600_000) < 15_000        # ₹8.6M exposure (locked)
        assert t.floored is False
        assert "significance" in t.arithmetic and "exposure_rs" in t.arithmetic

    def test_marketing_watch_via_governance_floor(self):
        # 2.1σ → significance 0.025; impact ₹0.2M saturates norm → raw NOISE; floored to WATCH.
        sig = max(0.0, min(1.0, (2.10 - 2) / 4))
        t = triage(
            significance=sig, deviation_pct=-4.0, exposure_rs_per_point=50_000,
            margin_weight=0.05, strategic_weight=0.1, floor_band="WATCH",
        )
        assert t.raw_band == "NOISE"
        assert t.band == "WATCH"
        assert t.floored is True
        assert t.arithmetic["floored"] is True                # honestly recorded

    def test_cold_start_monitor_only(self):
        t = triage(significance=0.9, deviation_pct=-30, exposure_rs_per_point=90_000,
                   margin_weight=0.1, strategic_weight=0.9, cold_start=True)
        assert t.band == "COLD START"
        assert t.monitor_only is True

    def test_statistically_small_stays_noise_without_floor(self):
        t = triage(significance=0.025, deviation_pct=-4.0, exposure_rs_per_point=50_000,
                   margin_weight=0.05, strategic_weight=0.1)
        assert t.band == "NOISE" and t.floored is False
