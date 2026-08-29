"""Seed fabric: three ScenarioTemplates, one engine (arch T.1, AC18).

S1 — Apex Foods: Revenue Decline (NE) — the hero 12-step demo.
S2 — Apex Foods: Inventory / Availability — different primary KPI/drivers/actions/guardrails.
S3 — Apex Foods: New Product / Sparse History (Millet Noodles) — cold start.

Configuration only — no scenario ever gets a private code path.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.scenario import ScenarioTemplate

SCENARIOS = [
    dict(
        scenario_id="apex_revenue_decline_ne",
        industry="FMCG",
        business_problem="Revenue Decline — Northeast",
        primary_kpi_code="revenue_ne",
        related_kpi_codes=["osa_ne", "inventory_cover_ne", "marketing_roi", "supplier_reliability"],
        region="NE",
        scenario_description=(
            "Northeast revenue is down 12% vs seasonal baseline (5.1σ). Reconcile ERP ₹84.0M against "
            "Finance ₹87.0M first, decompose price/volume/mix, compete four driver hypotheses on "
            "evidence, then decide under guardrails and decision rights."
        ),
        demo_priority=1,
        source_configuration={
            "sources": [
                {"code": "erp", "role": "primary_trading"},
                {"code": "gl", "role": "close_reconciliation"},
                {"code": "pos", "role": "availability_panel"},
                {"code": "wms", "role": "inventory"},
                {"code": "scorecard", "role": "supplier_health"},
            ],
            "expected_conflicts": [],
        },
        driver_configuration={
            "drivers": [
                {"driver_code": "supplier_delay", "hypothesis_class": "supply_disruption", "prior": 0.62},
                {"driver_code": "competitor_promo", "hypothesis_class": "competitor_action", "prior": 0.12},
                {"driver_code": "marketing_underperf", "hypothesis_class": "internal_execution", "prior": 0.08},
                {"driver_code": "seasonality", "hypothesis_class": "seasonal", "prior": 0.04},
            ],
            "hypothesis_count": 4,
        },
        threshold_configuration={
            "revenue_ne": {"critical_deviation_pct": -8.0, "exposure_rs_per_point": 716_667, "strategic_weight": 0.8},
        },
        materiality_configuration={
            "bands": {"CRITICAL": 0.70, "ELEVATED": 0.40, "WATCH": 0.15},
            "formula": "significance x clamp(log1p(impact)/10, 0, 1)",
        },
        decision_options=[
            {
                "option_code": "A_backup_supplier",
                "driver": "supplier_delay",
                "lever": "supply_switch",
                "action": "Activate pre-qualified backup supplier for the Guwahati lane (6 weeks)",
                "expected_impact_pt_rs": 4_100_000, "impact_lo_rs": 2_900_000, "impact_hi_rs": 5_200_000,
                "cost_rs": 1_600_000, "horizon_days": 42, "owner_role": "SUPPLY_CHAIN",
                "cash_exposure_rs": 1_600_000,
                "sim": {"cover_days_delta": +1.3, "osa_pct_delta": +5.2, "osa_recovery_pct": 96.4, "margin_pct_delta": -0.3, "direct_pct": {"supplier_reliability": +7}},
            },
            {
                "option_code": "B_air_freight",
                "driver": "supplier_delay",
                "lever": "expedite",
                "action": "Air-freight expedite of 3 weeks of NE demand",
                "expected_impact_pt_rs": 4_600_000, "impact_lo_rs": 3_400_000, "impact_hi_rs": 5_800_000,
                "cost_rs": 3_400_000, "horizon_days": 21, "owner_role": "SUPPLY_CHAIN",
                "escalate_to": "EXECUTIVE",
                "cash_exposure_rs": 3_800_000,  # 3.4M cost + 0.4M working-capital during expedite
                "sim": {"cover_days_delta": -1.1, "osa_pct_delta": +4.4, "osa_recovery_pct": 95.6, "margin_pct_delta": -1.4, "direct_pct": {"supplier_reliability": +10}},
            },
            {
                "option_code": "C_price_promotion",
                "driver": "volume_decline",
                "lever": "promotion",
                "action": "Price promotion +10% in NE for 3 weeks",
                "expected_impact_pt_rs": 6_300_000, "impact_lo_rs": 4_800_000, "impact_hi_rs": 7_700_000,
                "cost_rs": 1_100_000, "horizon_days": 21, "owner_role": "MARKETING",
                "second_order_warning": "inventory -18% breaches cover guardrail",
                "cash_exposure_rs": 1_100_000,
                "sim": {"cover_days_delta": -0.92, "osa_pct_delta": -0.9, "osa_recovery_pct": 90.3, "margin_pct_delta": -2.1, "direct_pct": {"revenue_ne": +8}},  # −0.92d = −18% of 5.1d cover
                "comparable_to": "Cp_restore_then_promote",
            },
            {
                "option_code": "Cp_restore_then_promote",
                "driver": "volume_decline",
                "lever": "phased_promotion",
                "action": "Restore stock (2 wks), then promote +7% (3 wks)",
                "expected_impact_pt_rs": 5_500_000, "impact_lo_rs": 4_200_000, "impact_hi_rs": 6_600_000,
                "cost_rs": 1_900_000, "horizon_days": 56, "owner_role": "MARKETING",
                "cash_exposure_rs": 1_900_000,
                "sim": {"cover_days_delta": +0.204, "osa_pct_delta": +4.6, "osa_recovery_pct": 95.8, "margin_pct_delta": -0.9, "direct_pct": {"revenue_ne": +7, "inventory_cover_ne": +4}, "suppress_edges": [["revenue_ne", "inventory_cover_ne"]], "suppress_note": "phased: stock restored first; the promotion drain is absorbed by the restored buffer (net +4% cover)"},
            },
            {
                # External proposal already in flight (Procurement) — collides with the
                # promotion option on inventory (AC21 locked demo).
                "option_code": "X_reduce_safety_stock",
                "driver": "supplier_delay",
                "lever": "inventory_reduction",
                "action": "Reduce procurement safety stock on the NE lane (working-capital program)",
                "expected_impact_pt_rs": 2_200_000, "impact_lo_rs": 1_500_000, "impact_hi_rs": 2_900_000,
                "cost_rs": 0, "horizon_days": 30, "owner_role": "SUPPLY_CHAIN",
                "cash_exposure_rs": 0,
                "external_proposal": True,
                "sim": {"cover_days_delta": -0.765, "osa_pct_delta": -2.0, "osa_recovery_pct": 89.0, "margin_pct_delta": 0.2, "direct_pct": {"inventory_cover_ne": -15}},  # −0.765d = −15% of 5.1d cover
            },
        ],
        guardrail_configuration={
            "applies_to_kpis": ["revenue_ne", "osa_ne", "inventory_cover_ne"],
            "guardrails": [
                {"code": "gross_margin", "kpi": "margin_ne", "threshold_type": "min", "threshold_value": -1.0, "unit": "PCT", "hard": True},
                {"code": "inventory_cover", "kpi": "inventory_cover_ne", "threshold_type": "min", "threshold_value": 5.0, "unit": "DAYS", "hard": True},
                {"code": "cash_exposure", "kpi": "cash_exposure", "threshold_type": "max", "threshold_value": 2_000_000, "unit": "INR", "hard": True},
                {"code": "customer_sla", "kpi": "osa_ne", "threshold_type": "min", "threshold_value": 95.0, "unit": "PCT", "hard": True},
            ],
            "policy": {"UNKNOWN": "treat_as_WARNING_plus_escalation", "WARNING": "monitoring_plan_mandatory"},
        },
        persona_configuration={
            "briefs": ["EXECUTIVE", "ANALYST", "SUPPLY_CHAIN", "KPI_OWNER"],
            "executive_lines": 7,
        },
        entitlement_configuration={
            "row_level": {"SUPPLY_CHAIN": ["NE"]},
            "column_level": {"SUPPLY_CHAIN": ["unit_cost_rs", "marketing_roi"], "EXECUTIVE": ["unit_cost_rs"]},
            "domain_level": {"gl_values": ["EXECUTIVE", "KPI_OWNER", "ANALYST"]},
        },
        dataset_ref="seed:apex_hero_v2",
        expected_outcome_ref="ledger:apex_hero_v2",
    ),
    dict(
        scenario_id="apex_inventory_cover",
        industry="FMCG",
        business_problem="Inventory / Availability — Cover Collapse at Guwahati DC",
        primary_kpi_code="inventory_cover_ne",
        related_kpi_codes=["osa_ne", "revenue_ne", "supplier_reliability"],
        region="NE",
        scenario_description=(
            "Days-of-cover at the Guwahati DC is collapsing. Same engine as the revenue scenario — "
            "different primary KPI, drivers (transport delay / demand surge / quality returns), evidence, "
            "actions (alternate DC, selective air freight), and guardrails."
        ),
        demo_priority=2,
        source_configuration={
            "sources": [
                {"code": "wms", "role": "primary"},
                {"code": "erp", "role": "demand"},
                {"code": "scorecard", "role": "supplier_health"},
                {"code": "pos", "role": "availability"},
            ],
            "expected_conflicts": [{"pair": ["pos", "*"], "type": "refresh"}],
        },
        driver_configuration={
            "drivers": [
                {"driver_code": "supplier_delay", "hypothesis_class": "supply_disruption", "prior": 0.48},
                {"driver_code": "transport_delay", "hypothesis_class": "logistics", "prior": 0.22},
                {"driver_code": "demand_surge", "hypothesis_class": "demand_shift", "prior": 0.14},
                {"driver_code": "quality_returns", "hypothesis_class": "quality", "prior": 0.06},
            ],
            "hypothesis_count": 4,
        },
        threshold_configuration={
            "inventory_cover_ne": {"critical_deviation_pct": -30.0, "exposure_rs_per_point": 900_000},
        },
        materiality_configuration={
            "bands": {"CRITICAL": 0.70, "ELEVATED": 0.40, "WATCH": 0.15},
            "formula": "significance x clamp(log1p(impact)/10, 0, 1)",
        },
        decision_options=[
            {
                "option_code": "S2_alt_dc",
                "driver": "transport_delay",
                "lever": "network_shift",
                "action": "Shift 40% of NE replenishment to the alternate Kolkata DC",
                "expected_impact_pt_rs": 2_800_000, "impact_lo_rs": 2_100_000, "impact_hi_rs": 3_500_000,
                "cost_rs": 700_000, "horizon_days": 28, "owner_role": "SUPPLY_CHAIN",
            },
            {
                "option_code": "S2_selective_air",
                "driver": "supplier_delay",
                "lever": "expedite",
                "action": "Selective air freight for top-20 velocity SKUs only",
                "expected_impact_pt_rs": 1_900_000, "impact_lo_rs": 1_400_000, "impact_hi_rs": 2_400_000,
                "cost_rs": 1_100_000, "horizon_days": 14, "owner_role": "SUPPLY_CHAIN",
            },
        ],
        guardrail_configuration={
            "applies_to_kpis": ["inventory_cover_ne", "revenue_ne", "osa_ne"],
            "guardrails": [
                {"code": "revenue_floor", "kpi": "revenue_ne", "threshold_type": "min", "threshold_value": -2.0, "unit": "PCT", "hard": True},
                {"code": "gross_margin", "kpi": "margin_ne", "threshold_type": "min", "threshold_value": -1.0, "unit": "PCT", "hard": True},
                {"code": "customer_sla", "kpi": "osa_ne", "threshold_type": "min", "threshold_value": 95.0, "unit": "PCT", "hard": True},
            ],
            "policy": {"UNKNOWN": "treat_as_WARNING_plus_escalation", "WARNING": "monitoring_plan_mandatory"},
        },
        persona_configuration={"briefs": ["EXECUTIVE", "ANALYST", "SUPPLY_CHAIN", "KPI_OWNER"]},
        entitlement_configuration={
            "row_level": {"SUPPLY_CHAIN": ["NE"]},
            "column_level": {"SUPPLY_CHAIN": ["unit_cost_rs", "marketing_roi"]},
        },
        dataset_ref="seed:apex_hero_v2",
        expected_outcome_ref="ledger:apex_inventory_v2",
    ),
    dict(
        scenario_id="apex_millet_launch",
        industry="FMCG",
        business_problem="New Product Launch — Sparse History (Millet Noodles)",
        primary_kpi_code="millet_noodles_revenue",
        related_kpi_codes=[],
        region="NATIONAL",
        scenario_description=(
            "Five weeks of launch data. Cold-start mode: sibling analogues, benchmark bands, wide CIs, "
            "confidence capped at 0.45, monitor-only. Unlock at week 13 or on analogue validation."
        ),
        demo_priority=3,
        source_configuration={"sources": [{"code": "erp", "role": "primary"}]},
        driver_configuration={
            "drivers": [
                {"driver_code": "distribution_build", "hypothesis_class": "launch_dynamics", "prior": 0.5},
                {"driver_code": "repeat_rate", "hypothesis_class": "launch_dynamics", "prior": 0.3},
            ],
            "hypothesis_count": 2,
        },
        threshold_configuration={"millet_noodles_revenue": {"cold_start_flag": True, "min_history": 13}},
        materiality_configuration={
            "bands": {"CRITICAL": 0.70, "ELEVATED": 0.40, "WATCH": 0.15},
            "cold_start": {"confidence_cap": 0.45, "monitor_only": True,
                           "unlock": "week 13 with >= 2 complete audit cycles, or analogue validation at 8 weeks"},
        },
        decision_options=[
            {
                "option_code": "S3_monitor",
                "driver": "launch_dynamics",
                "lever": "monitor",
                "action": "Monitor-only until unlock conditions met (no actions offered by design)",
                "expected_impact_pt_rs": 0, "impact_lo_rs": 0, "impact_hi_rs": 0,
                "cost_rs": 0, "horizon_days": 56, "owner_role": "KPI_OWNER",
            }
        ],
        guardrail_configuration={
            "applies_to_kpis": ["millet_noodles_revenue"],
            "guardrails": [
                {"code": "launch_margin", "kpi": "millet_margin", "threshold_type": "min", "threshold_value": -3.0, "unit": "PCT", "hard": True},
            ],
            "policy": {"UNKNOWN": "treat_as_WARNING_plus_escalation", "WARNING": "monitoring_plan_mandatory"},
        },
        persona_configuration={"briefs": ["EXECUTIVE", "ANALYST", "KPI_OWNER"]},
        entitlement_configuration={},
        dataset_ref="seed:apex_millet_v2",
        expected_outcome_ref="ledger:apex_millet_v2",
    ),
]


def ensure_scenarios(db: Session, org_id: str) -> list[ScenarioTemplate]:
    out = []
    for cfg in SCENARIOS:
        template = db.query(ScenarioTemplate).filter(
            ScenarioTemplate.organization_id == org_id, ScenarioTemplate.scenario_id == cfg["scenario_id"]
        ).first()
        if template is None:
            template = ScenarioTemplate(organization_id=org_id, status="ACTIVE", version=1, **cfg)
            db.add(template)
            db.flush()
        out.append(template)
    return out
