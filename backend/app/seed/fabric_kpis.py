"""Seed fabric: KPI identities + governed contracts with full satellites.

Seven Apex Foods KPIs (5 connected hero KPIs + the South abstention KPI + the
cold-start launch KPI) and their contracts, drivers, thresholds, rights,
entitlements, sources, and KPI relations (used by second-order impact in S8).
Locked demo configuration comes from the product spec §19 and architecture T.2.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.contract import (
    ContractVersion,
    KpiContract,
    KpiContractDriver,
    KpiContractEntitlement,
    KpiContractRight,
    KpiContractSource,
    KpiContractThreshold,
    KpiRelation,
)
from ..models.kpi import Kpi
from ..models.org import User
from ..models.source import SourceSystem

# --- KPI identities ----------------------------------------------------------
KPIS = [
    # code, name, category, region, unit, scenario_id, description
    ("revenue_ne", "Revenue — Northeast", "REVENUE", "NE", "INR_M", "apex_revenue_decline_ne",
     "Invoiced net sales for the Northeast region, all channels."),
    ("osa_ne", "On-Shelf Availability — Northeast", "AVAILABILITY", "NE", "PCT", "apex_revenue_decline_ne",
     "Share of store-audit SKUs found on shelf in the Northeast panel."),
    ("inventory_cover_ne", "Inventory Days-of-Cover — Northeast", "INVENTORY", "NE", "DAYS", "apex_revenue_decline_ne",
     "Forward days of demand covered by on-hand stock across NE DCs (primarily Guwahati)."),
    ("marketing_roi", "Marketing ROI", "MARKETING", "NATIONAL", "RATIO", "apex_revenue_decline_ne",
     "Incremental revenue per rupee of campaign spend, national."),
    ("supplier_reliability", "Supplier Reliability — NE Lane", "SUPPLIER", "NE", "PCT", "apex_revenue_decline_ne",
     "On-time-in-full delivery rate for NE-lane suppliers."),
    ("sales_per_outlet_south", "Sales per Outlet — South", "REVENUE", "SOUTH", "INR_K", "apex_revenue_decline_ne",
     "Average weekly sales per outlet in the South region (abstention demo case)."),
    ("millet_noodles_revenue", "Millet Noodles Revenue — Launch", "LAUNCH", "NATIONAL", "INR_M", "apex_millet_launch",
     "Revenue for the newly launched Millet Noodles line (5 weeks of history)."),
]

# --- Contract configurations ---------------------------------------------------
# Each entry configures one contract: definition, formula, sources, drivers,
# thresholds (incl. materiality weights), rights, entitlements.

DRIVERS_HERO = [
    # code, name, direction, prior_weight, hypothesis_class, rank
    ("supplier_delay", "Supplier delay at Guwahati DC lane", -1, 0.62, "supply_disruption", 1),
    ("competitor_promo", "Competitor promotion in NE", -1, 0.12, "competitor_action", 2),
    ("marketing_underperf", "Marketing underperformance", -1, 0.08, "internal_execution", 3),
    ("seasonality", "Seasonal demand shift", -1, 0.04, "seasonal", 4),
]

RIGHTS_HERO = [
    # role, action_class, may_recommend, may_simulate, may_approve, limit, escalate_to
    ("SUPPLY_CHAIN", "supply_switch", True, True, True, 2_000_000, "EXECUTIVE"),
    ("SUPPLY_CHAIN", "expedite", True, True, True, 2_000_000, "EXECUTIVE"),
    ("EXECUTIVE", "expedite", True, True, True, 10_000_000, None),
    ("EXECUTIVE", "promotion", True, True, True, 10_000_000, None),
    ("MARKETING", "promotion", True, True, False, 0, "EXECUTIVE"),
    ("EXECUTIVE", "phased_promotion", True, True, True, 10_000_000, None),
    ("MARKETING", "phased_promotion", True, True, False, 0, "EXECUTIVE"),
    ("ANALYST", "*", True, True, False, 0, None),
]

ENTITLEMENTS_HERO = [
    # role, row_scope, masked_columns, domains
    ("EXECUTIVE", {"region": ["NE", "SOUTH", "NATIONAL"]}, ["unit_cost_rs"], ["finance_summary"]),
    ("ANALYST", {"region": ["NE", "SOUTH", "NATIONAL"]}, ["customer_pii"], ["finance", "operations", "marketing"]),
    ("SUPPLY_CHAIN", {"region": ["NE"]}, ["unit_cost_rs", "marketing_roi"], ["operations"]),
    ("KPI_OWNER", {"region": ["NE", "SOUTH", "NATIONAL"]}, [], ["finance", "operations", "marketing", "governance"]),
]

THRESHOLDS_HERO_REVENUE = dict(
    expected_lo=88.0, expected_hi=104.0,  # ₹M seasonal band around baseline ~95.5
    warning_deviation_pct=-4.0, critical_deviation_pct=-8.0,
    exposure_rs_per_point=8_600_000 / 12.0,  # ₹8.6M exposure at −12% deviation → per-point ≈ ₹0.72M
    margin_weight=0.15, strategic_weight=0.8, min_history=13, cold_start_flag=False,
    quality_rules={"tolerance_pct": 1.0, "null_rule": "reject_row", "duplicate_rule": "latest_wins"},
)

CONTRACTS: list[dict] = [
    dict(
        kpi_code="revenue_ne",
        name="Revenue (Invoiced, Net) — Northeast",
        business_definition=(
            "Invoiced net sales revenue for the Northeast region across all channels, net of returns booked "
            "at invoicing but BEFORE the close-period returns accrual recognized in Finance. This is the "
            "operational trading view used for daily management; the GL recognized figure differs by design "
            "(accrual + calendar boundary)."
        ),
        formula_sql="SELECT SUM(net_amount_inr) FROM erp.sales_lines WHERE region='NE' AND fiscal_week BETWEEN :wk_lo AND :wk_hi",
        formula_note="Invoiced net sales; excludes the returns accrual posted only at GL close.",
        unit="INR_M", business_function="Commercial / Sales",
        owner_role="KPI_OWNER",
        calendar_rule="Fiscal weeks Mon–Sun; ERP daily sums roll to weeks; GL close covers calendar month (boundary offset flagged).",
        hierarchy_config={"region_map": {"NE-04": "NE", "Northeast Territory": "NE", "Region X": "NE"}},
        sources=[
            ("erp", "erp.sales_lines[region=NE]", True, "daily", "SKU x DC → period agg", 1.0),
            ("gl", "gl.revenue_accounts[company=APEX,account=4000]", False, "monthly", "company x account", 3.0),
            ("pos", "pos.audit_panel[region=NE]", False, "weekly", "region x category", 5.0),
        ],
        drivers=DRIVERS_HERO,
        thresholds=THRESHOLDS_HERO_REVENUE,
        rights=RIGHTS_HERO,
        entitlements=ENTITLEMENTS_HERO,
        scenario_id="apex_revenue_decline_ne",
    ),
    dict(
        kpi_code="osa_ne",
        name="On-Shelf Availability — Northeast",
        business_definition=(
            "Percentage of audited SKU-store combinations in the NE retail panel where the product was "
            "found on shelf during the audit visit. Leading indicator of revenue erosion from stockouts."
        ),
        formula_sql="SELECT 100.0 * SUM(CASE WHEN on_shelf THEN 1 ELSE 0 END) / COUNT(*) FROM pos.audit_panel WHERE region='NE' AND audit_week=:wk",
        formula_note="Store-audit panel measure; publish lag ~6 days.",
        unit="PCT", business_function="Sales / Field Operations",
        owner_role="KPI_OWNER",
        calendar_rule="Audit weeks (Mon-origin); 6-day publish lag tolerated to +2 days.",
        hierarchy_config={"region_map": {"NE-04": "NE"}},
        sources=[("pos", "pos.audit_panel[region=NE]", True, "weekly", "region x category", 2.0)],
        drivers=[
            ("inventory_cover_ne", "Inventory cover collapse upstream", -1, 0.55, "supply_chain", 1),
            ("supplier_delay", "Supplier delay at Guwahati DC lane", -1, 0.35, "supply_disruption", 2),
            ("audit_panel_shift", "Audit sample composition shift", -1, 0.05, "measurement", 3),
        ],
        thresholds=dict(
            expected_lo=90.0, expected_hi=97.0, warning_deviation_pct=-3.0, critical_deviation_pct=-6.0,
            exposure_rs_per_point=1_400_000, margin_weight=0.2, strategic_weight=0.6, min_history=13,
            cold_start_flag=False, quality_rules={"tolerance_pct": 2.0},
        ),
        rights=RIGHTS_HERO,
        entitlements=ENTITLEMENTS_HERO,
        scenario_id="apex_revenue_decline_ne",
    ),
    dict(
        kpi_code="inventory_cover_ne",
        name="Inventory Days-of-Cover — Northeast",
        business_definition=(
            "Forward-looking days of demand that current on-hand inventory at NE DCs (primarily Guwahati) "
            "can cover at forecast run-rate. Guardrail KPI: hard floor 5 days."
        ),
        formula_sql="SELECT SUM(on_hand_units) / NULLIF(AVG(daily_forecast_units),0) FROM wms.stock_positions WHERE dc_region='NE' AND snapshot_date=:d",
        formula_note="On-hand ÷ forecast daily demand; WMS end-of-day snapshot.",
        unit="DAYS", business_function="Supply Chain",
        owner_role="KPI_OWNER",
        calendar_rule="Daily snapshots; weekly rolling view used for triage.",
        hierarchy_config={"dc_map": {"Guwahati": "NE", "GHY-01": "NE"}},
        sources=[("wms", "wms.stock_positions[dc_region=NE]", True, "daily", "SKU x DC", 1.0)],
        drivers=[
            ("supplier_delay", "Inbound delay reducing cover", -1, 0.60, "supply_disruption", 1),
            ("demand_surge", "Demand surge (monsoon/season)", -1, 0.20, "demand_shift", 2),
            ("quality_returns", "Quality holds on returned lots", -1, 0.10, "quality", 3),
        ],
        thresholds=dict(
            expected_lo=9.0, expected_hi=16.0, warning_deviation_pct=-15.0, critical_deviation_pct=-30.0,
            exposure_rs_per_point=900_000, margin_weight=0.25, strategic_weight=0.7, min_history=13,
            cold_start_flag=False, quality_rules={"tolerance_pct": 1.0},
        ),
        rights=RIGHTS_HERO,
        entitlements=ENTITLEMENTS_HERO,
        scenario_id="apex_revenue_decline_ne",
    ),
    dict(
        kpi_code="marketing_roi",
        name="Marketing ROI — National",
        business_definition=(
            "Incremental revenue attributable to active campaigns divided by campaign spend, national "
            "rollup. Watch-list KPI: movement here is analyzed but historically rarely material."
        ),
        formula_sql="SELECT SUM(attributed_revenue_inr) / NULLIF(SUM(spend_inr),0) FROM erp.campaign_rollup WHERE week=:wk",
        formula_note="Attribution model v2 (last-touch, 7-day window).",
        unit="RATIO", business_function="Marketing",
        owner_role="KPI_OWNER",
        calendar_rule="Campaign weeks; national rollup.",
        hierarchy_config={},
        sources=[("erp", "erp.campaign_rollup[national]", True, "weekly", "campaign", 2.0)],
        drivers=[
            ("campaign_mix", "Campaign mix shift to low-yield channels", -1, 0.4, "internal_execution", 1),
            ("seasonality", "Seasonal response-rate shift", -1, 0.3, "seasonal", 2),
        ],
        thresholds=dict(
            expected_lo=2.6, expected_hi=3.6, warning_deviation_pct=-10.0, critical_deviation_pct=-25.0,
            exposure_rs_per_point=50_000, margin_weight=0.05, strategic_weight=0.1, min_history=13,
            cold_start_flag=False, floor_band="WATCH",  # watch-list KPI: governance floors the band (§8.4)
            quality_rules={"tolerance_pct": 3.0},
        ),
        rights=RIGHTS_HERO,
        entitlements=ENTITLEMENTS_HERO,
        scenario_id="apex_revenue_decline_ne",
    ),
    dict(
        kpi_code="supplier_reliability",
        name="Supplier Reliability — NE Lane",
        business_definition=(
            "On-time-in-full (OTIF) delivery rate for suppliers serving the NE lane. Upstream driver KPI: "
            "declines here propagate to cover, then OSA, then revenue (see relations)."
        ),
        formula_sql="SELECT 100.0 * SUM(CASE WHEN otif THEN 1 ELSE 0 END)/COUNT(*) FROM scorecard.otif WHERE lane='NE' AND week=:wk",
        formula_note="Supplier scorecard OTIF; SENSITIVE source (commercial terms).",
        unit="PCT", business_function="Procurement",
        owner_role="KPI_OWNER",
        calendar_rule="Supplier weeks (Sun-origin); 1-day publish lag.",
        hierarchy_config={"supplier_map": {"Apex Supplier": "SUP-001"}},
        sources=[("scorecard", "scorecard.otif[lane=NE]", True, "weekly", "supplier x region", 2.0)],
        drivers=[
            ("supplier_capacity", "Supplier capacity constraint", -1, 0.5, "supply_disruption", 1),
            ("transport_disruption", "Transport route disruption", -1, 0.3, "logistics", 2),
        ],
        thresholds=dict(
            expected_lo=88.0, expected_hi=99.0, warning_deviation_pct=-4.0, critical_deviation_pct=-10.0,
            exposure_rs_per_point=220_000, margin_weight=0.1, strategic_weight=0.5, min_history=13,
            cold_start_flag=False, quality_rules={"tolerance_pct": 1.0},
        ),
        rights=RIGHTS_HERO,
        entitlements=ENTITLEMENTS_HERO,
        scenario_id="apex_revenue_decline_ne",
    ),
    dict(
        kpi_code="sales_per_outlet_south",
        name="Sales per Outlet — South",
        business_definition=(
            "Average weekly sales per outlet in the South region. Demo case for abstention: signals are "
            "weak, sources stale, and hypotheses tie."
        ),
        formula_sql="SELECT AVG(weekly_sales_inr) FROM pos.outlet_sales WHERE region='SOUTH' AND week=:wk",
        formula_note="POS-panel derived; dependent on audit refresh cadence.",
        unit="INR_K", business_function="Commercial / Sales",
        owner_role="KPI_OWNER",
        calendar_rule="Audit weeks; 6-day publish lag.",
        hierarchy_config={"region_map": {"S-11": "SOUTH"}},
        sources=[
            ("pos", "pos.outlet_sales[region=SOUTH]", True, "weekly", "region x category", 5.0),
            ("erp", "erp.sales_lines[region=SOUTH]", False, "daily", "SKU x DC → period agg", 3.0),
        ],
        drivers=[
            ("audit_panel_shift", "Audit sample composition shift", -1, 0.45, "measurement", 1),
            ("competitor_promo", "Competitor promotion in South", -1, 0.47, "competitor_action", 2),
            ("seasonality", "Seasonal demand shift", -1, 0.05, "seasonal", 3),
        ],
        thresholds=dict(
            expected_lo=180.0, expected_hi=240.0, warning_deviation_pct=-6.0, critical_deviation_pct=-12.0,
            exposure_rs_per_point=120_000, margin_weight=0.05, strategic_weight=0.2, min_history=13,
            cold_start_flag=False, quality_rules={"tolerance_pct": 4.0},
        ),
        rights=RIGHTS_HERO,
        entitlements=ENTITLEMENTS_HERO,
        scenario_id="apex_revenue_decline_ne",
    ),
    dict(
        kpi_code="millet_noodles_revenue",
        name="Millet Noodles Revenue — Launch",
        business_definition=(
            "Weekly revenue for the Millet Noodles launch line. Five weeks of history — COLD START mode "
            "until week 13 or analogue validation (see unlock conditions)."
        ),
        formula_sql="SELECT SUM(net_amount_inr) FROM erp.sales_lines WHERE sku_family='MN' AND week=:wk",
        formula_note="Launch SKU family MN (MilletNoodles_120g / MN-120 alias resolved).",
        unit="INR_M", business_function="Innovation / Launch",
        owner_role="KPI_OWNER",
        calendar_rule="Launch weeks from W1 = national listing date.",
        hierarchy_config={"sku_alias": {"MilletNoodles_120g": "MN-120"}},
        sources=[("erp", "erp.sales_lines[sku_family='MN']", True, "daily", "SKU x DC → period agg", 1.0)],
        drivers=[
            ("distribution_build", "Distribution ramp pace", 1, 0.5, "launch_dynamics", 1),
            ("repeat_rate", "Repeat purchase rate", 1, 0.3, "launch_dynamics", 2),
        ],
        thresholds=dict(
            expected_lo=None, expected_hi=None, warning_deviation_pct=None, critical_deviation_pct=None,
            exposure_rs_per_point=90_000, margin_weight=0.1, strategic_weight=0.9, min_history=13,
            cold_start_flag=True,
            quality_rules={"tolerance_pct": 5.0},
        ),
        rights=RIGHTS_HERO,
        entitlements=ENTITLEMENTS_HERO,
        scenario_id="apex_millet_launch",
    ),
]

# Typed edges powering second-order propagation (arch K.3). Elasticity = effect
# multiplier per edge; confidence decays per hop; lag in days.
RELATIONS = [
    # a_kpi, b_kpi, relation, elasticity, confidence, lag_days
    ("supplier_reliability", "inventory_cover_ne", "IMPACTS", 0.18, 0.9, 7),
    ("inventory_cover_ne", "osa_ne", "IMPACTS", 0.55, 0.85, 3),
    ("osa_ne", "revenue_ne", "IMPACTS", 0.35, 0.9, 7),
    ("marketing_roi", "revenue_ne", "PRECEDES", 0.10, 0.6, 14),
    # Elasticity −2.25 is chain-derived from the locked AC20 demo (+8% revenue ⇒ −18% cover).
    ("revenue_ne", "inventory_cover_ne", "IMPACTS", -2.25, 0.7, 5),
]


def ensure_kpis(db: Session, org_id: str) -> dict[str, Kpi]:
    out = {}
    for code, name, category, region, unit, scenario_id, description in KPIS:
        kpi = db.query(Kpi).filter(Kpi.organization_id == org_id, Kpi.code == code).first()
        if kpi is None:
            kpi = Kpi(
                organization_id=org_id, code=code, name=name, category=category,
                region=region, unit=unit, description=description, scenario_id=scenario_id,
            )
            db.add(kpi)
            db.flush()
        out[code] = kpi
    return out


def ensure_contracts(
    db: Session, org_id: str, kpis: dict[str, Kpi], sources: dict[str, SourceSystem], owner: User
) -> dict[str, KpiContract]:
    out: dict[str, KpiContract] = {}
    for cfg in CONTRACTS:
        kpi = kpis[cfg["kpi_code"]]
        contract = (
            db.query(KpiContract)
            .filter(KpiContract.organization_id == org_id, KpiContract.kpi_id == kpi.id)
            .order_by(KpiContract.version.desc())
            .first()
        )
        if contract is not None:
            out[cfg["kpi_code"]] = contract
            continue
        contract = KpiContract(
            organization_id=org_id,
            kpi_id=kpi.id,
            scenario_id=cfg["scenario_id"],
            name=cfg["name"],
            business_definition=cfg["business_definition"],
            formula_sql=cfg["formula_sql"],
            formula_note=cfg["formula_note"],
            unit=cfg["unit"],
            business_function=cfg["business_function"],
            owner_user_id=owner.id,
            owner_role=cfg["owner_role"],
            status="ACTIVE",  # seeded fabric lands pre-governed (the demo opens mid-life)
            calendar_rule=cfg["calendar_rule"],
            hierarchy_config=cfg["hierarchy_config"],
            version=1,
        )
        db.add(contract)
        db.flush()
        for i, (src_code, lineage, authoritative, cadence, grain, tol) in enumerate(cfg["sources"]):
            db.add(KpiContractSource(
                contract_id=contract.id, source_system_id=sources[src_code].id, lineage_path=lineage,
                is_authoritative=authoritative, expected_cadence=cadence, expected_grain=grain,
                tolerance_pct=tol, rank=i,
            ))
        for code, name, direction, prior, hyp_class, rank in cfg["drivers"]:
            db.add(KpiContractDriver(
                contract_id=contract.id, driver_code=code, name=name, direction=direction,
                prior_weight=prior, hypothesis_class=hyp_class, rank=rank, source="config",
            ))
        th = dict(cfg["thresholds"])
        db.add(KpiContractThreshold(contract_id=contract.id, **th))
        for role, action_class, rec, sim, appr, limit, escalate in cfg["rights"]:
            db.add(KpiContractRight(
                contract_id=contract.id, role=role, action_class=action_class, may_recommend=rec,
                may_simulate=sim, may_approve=appr, approve_limit_rs=limit, escalate_to_role=escalate,
                scope={"region": "NE"} if role == "SUPPLY_CHAIN" else {},
            ))
        for role, row_scope, masked, domains in cfg["entitlements"]:
            db.add(KpiContractEntitlement(
                contract_id=contract.id, role=role, row_scope=row_scope, masked_columns=masked, domains=domains,
            ))
        db.flush()
        # version-1 snapshot so history is complete from the start
        from ..domains.contracts.service import snapshot_of

        db.add(ContractVersion(
            contract_id=contract.id, organization_id=org_id, version=1,
            snapshot=snapshot_of(contract), changed_by_user_id=owner.id,
            change_reason="initial governed definition (seed)",
        ))
        out[cfg["kpi_code"]] = contract
    db.flush()
    return out


def ensure_relations(db: Session, org_id: str, contracts: dict[str, KpiContract]) -> None:
    existing = db.query(KpiRelation).filter(KpiRelation.organization_id == org_id).count()
    if existing:
        return
    for a_code, b_code, relation, elasticity, confidence, lag in RELATIONS:
        db.add(KpiRelation(
            organization_id=org_id, a_contract_id=contracts[a_code].id, b_contract_id=contracts[b_code].id,
            relation=relation, elasticity=elasticity, confidence=confidence, lag_days=lag,
        ))
    db.flush()
