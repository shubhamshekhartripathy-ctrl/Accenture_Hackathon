"""Reconciliation engine units: penalty brackets, typing, reliability, verdicts, caps."""
from __future__ import annotations

import pytest

from app.domains.reconcile.engine import (
    PENALTY_DEFINITION,
    SourceReading,
    reliability,
    run_engine,
    stale_penalty,
)


def _reading(**kw) -> SourceReading:
    base = dict(
        source_code="erp", source_id="s-erp", value=100.0, period_key="P14", age_days=1,
        expected_cadence="daily", tolerance_days=2, tolerance_pct=1.0, grain="SKU x DC",
        expected_grain="SKU x DC", is_authoritative=True, calendar_key="FY26-P14",
    )
    base.update(kw)
    return SourceReading(**base)


class TestStalePenalties:
    def test_brackets(self):
        assert stale_penalty(0) == 0.00
        assert stale_penalty(2) == 0.00
        assert stale_penalty(3) == 0.06
        assert stale_penalty(5) == 0.06
        assert stale_penalty(6) == 0.12
        assert stale_penalty(9) == 0.12
        assert stale_penalty(10) == 0.15
        assert stale_penalty(40) == 0.15

    def test_pos_demo_case_lands_in_012_bracket(self):
        # weekly cadence (7d) + 2d tolerance, age 15d → 6d beyond → 0.12
        beyond = 15 - (7 + 2)
        assert stale_penalty(beyond) == 0.12


class TestReliability:
    def test_locked_hero_arithmetic(self):
        # definition 0.12 + stale 0.12 → 1 − 0.24 = 0.76 (locked)
        assert abs(reliability([0.12, 0.12]) - 0.76) < 1e-9

    def test_floor_clamp(self):
        assert reliability([0.5, 0.5, 0.5]) == 0.4

    def test_ceiling(self):
        assert reliability([]) == 1.0
        assert reliability([0.0]) == 1.0


class TestEngine:
    def test_definition_conflict_never_merges(self):
        result = run_engine(
            [
                _reading(source_code="erp", source_id="s-erp", value=84.0, tolerance_pct=1.0),
                _reading(source_code="gl", source_id="s-gl", value=87.0, tolerance_pct=3.0,
                         expected_cadence="monthly", calendar_key="FY26-M4-close",
                         is_authoritative=False),
            ],
            "P14", "INR_M",
        )
        assert result.verdict == "CONFLICTED"
        assert abs(result.reliability_score - 0.88) < 0.005  # definition only → 1 − 0.12
        assert abs(result.confidence_cap - 0.98) < 0.005
        assert result.working_value == 84.0  # authoritative ERP retained, GL NOT merged
        assert "not merged" in result.working_justification.lower()
        definition = [c for c in result.conflicts if c["conflict_type"] == "definition"]
        assert definition and definition[0]["severity"] == "HIGH"
        assert abs(definition[0]["confidence_impact"] + PENALTY_DEFINITION) < 1e-9

    def test_locked_moment1_full_case(self):
        # definition 0.12 + stale POS 0.12 → reliability 0.76, cap 0.86
        result = run_engine(
            [
                _reading(source_code="erp", source_id="s-erp", value=84.0),
                _reading(source_code="gl", source_id="s-gl", value=87.0, tolerance_pct=3.0,
                         expected_cadence="monthly", calendar_key="FY26-M4-close",
                         is_authoritative=False),
                _reading(source_code="pos", source_id="s-pos", value=None, age_days=15,
                         expected_cadence="weekly", tolerance_pct=5.0, grain="region x category",
                         expected_grain="region x category"),
            ],
            "P14", "INR_M",
        )
        assert result.verdict == "CONFLICTED"
        assert abs(result.reliability_score - 0.76) < 0.005
        assert abs(result.confidence_cap - 0.86) < 0.005
        assert result.penalties == {"definition": 0.12, "stale_source": 0.12}

    def test_consistent_when_within_tolerance(self):
        result = run_engine(
            [_reading(value=100.0), _reading(source_code="pos", source_id="s-pos", value=100.4, tolerance_pct=1.0, age_days=1, is_authoritative=False)],
            "P14", "PCT",
        )
        assert result.verdict == "CONSISTENT"
        assert result.conflicts == []

    def test_grain_mismatch_flags_information_loss(self):
        result = run_engine(
            [_reading(grain="region x category", expected_grain="SKU x DC")], "P14", "PCT"
        )
        assert any(c["conflict_type"] == "grain" and "information loss" in c["explanation"] for c in result.conflicts)
        assert result.reliability_score == 0.95

    def test_minor_verdict_when_no_definition_conflict(self):
        result = run_engine(
            [_reading(source_code="pos", source_id="s-pos", age_days=15, expected_cadence="weekly")],
            "P14", "PCT",
        )
        assert result.verdict == "MINOR"
        assert abs(result.reliability_score - 0.88) < 0.005

    def test_missing_value_source_flagged(self):
        # A declared source with no observation at all → coverage-grade staleness (999d → 0.15)
        result = run_engine(
            [_reading(), _reading(source_code="pos", source_id="s-pos", value=None, age_days=999)],
            "P14", "PCT",
        )
        assert result.reliability_score == 0.85
