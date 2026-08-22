"""Evidence fabric — seeded documents with polarities, freshness, lineage,
data classification (arch T.2) and the pattern-reliability priors (M.1).

Weights/freshness are calibrated so the deterministic scoring engine produces
EXACTLY the locked hypothesis ordering (0.82 / 0.12 / 0.04 / 0.02, lead ×0.86
cap → 0.71) and the South tie (0.47 / 0.45, lead 0.03 → ABSTAIN). Every doc
belongs to a declared source; claims carry polarity + span (extract_claims I/O).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.evidence import EvidenceRecord, PatternReliability
from ..models.source import SourceSystem

# pattern_class → (n_observations, hits, prior) — empirical, feedback-updatable (S9)
PATTERNS = [
    ("supply_disruption", 14, 9, 0.64),
    ("competitor_action", 11, 3, 0.12),
    ("internal_execution", 9, 2, 0.08),
    ("seasonal", 12, 4, 0.0667),
    ("measurement", 6, 2, 0.10),
    ("transport_delay", 5, 3, 0.30),
    ("demand_surge", 4, 2, 0.20),
    ("quality_returns", 3, 1, 0.10),
    ("launch_ramp", 7, 4, 0.30),
]

# doc_key, title, kpi_code, driver_class, source, polarity, s_w, c_w, fresh, age, classification, access_roles, lineage, summary, claims
_DOCS = [
    # --- NE revenue case (hero) — supplier-delay story (4 supporting) ----------
    ("EV-SUP-01", "Supplier delay notice — Guwahati DC inbound lane", "revenue_ne", "supply_disruption",
     "scorecard", "SUPPORTS", 1.0, 0.0, 1.0, 5, "SENSITIVE", ["EXECUTIVE", "ANALYST", "ADMIN", "KPI_OWNER"],
     "supplier_portal.mail/guwahati-lane/2026-08-04.eml",
     "Supplier confirmed a 9-day inbound delay at Guwahati DC affecting staples families.",
     [{"claim": "Inbound delay of 9 days confirmed at Guwahati DC for ATTA/OIL families", "polarity": "SUPPORTS", "span": "body¶2"},
      {"claim": "Recovered expedite quote priced at unit_cost_rs 41.0 per case vs standard 24.5", "polarity": "SUPPORTS", "span": "attachment¶1", "unit_cost_rs": 41.0, "standard_unit_cost_rs": 24.5}]),
    ("EV-SUP-02", "Supplier reliability scorecard — weekly drop 94→81", "revenue_ne", "supply_disruption",
     "scorecard", "SUPPORTS", 1.0, 0.0, 1.0, 2, "INTERNAL", [],
     "scorecard.weekly/supplier_region/2026-W32",
     "Primary supplier OTIF fell from 94.0 to 81.2 over four weeks (NE lane).",
     [{"claim": "OTIF 94.0 → 81.2 over four weeks on the NE lane", "polarity": "SUPPORTS", "span": "tbl.row3"}]),
    ("EV-SUP-03", "WMS snapshot — days-of-cover collapse at Guwahati DC", "revenue_ne", "supply_disruption",
     "wms", "SUPPORTS", 1.0, 0.0, 1.0, 1, "INTERNAL", [],
     "wms.daily/sku_dc/2026-08-09",
     "NE days-of-cover fell 11.6 → 5.1 days; Guwahati DC below reorder point.",
     [{"claim": "Cover 11.6 → 5.1 days; Guwahati below reorder point", "polarity": "SUPPORTS", "span": "sheet.cover"}]),
    ("EV-SUP-04", "POS audit — OSA NE decline 90.8 → 71.4", "revenue_ne", "supply_disruption",
     "pos", "SUPPORTS", 1.0, 0.0, 1.0, 8, "INTERNAL", [],
     "pos.audit/region_category/2026-W32",
     "On-shelf availability in NE dropped 21 points, concentrated in staples.",
     [{"claim": "OSA NE 90.8 → 71.4, staples-led", "polarity": "SUPPORTS", "span": "fig.2"}]),
    # --- competitor promo (red herring: promo is in SOUTH, not NE) -------------
    ("EV-CMP-01", "Market tracker — competitor promo active (national read)", "revenue_ne", "competitor_action",
     "pos", "SUPPORTS", 0.7, 0.0, 0.82, 11, "INTERNAL", [],
     "syndicated.market_tracker/2026-W31",
     "A competitor promotion is active in the market (two audits back).",
     [{"claim": "Competitor promo running weeks 12–14", "polarity": "SUPPORTS", "span": "p.1"}]),
    ("EV-CMP-02", "Market tracker geo split — promo concentrated in SOUTH", "revenue_ne", "competitor_action",
     "pos", "CONTRADICTS", 0.0, 1.0, 1.0, 11, "INTERNAL", [],
     "syndicated.market_tracker/2026-W31/geo",
     "The promotion is concentrated in the SOUTH region; NE exposure minimal.",
     [{"claim": "Promo spend ~92% SOUTH; NE not exposed", "polarity": "CONTRADICTS", "span": "tbl.geo"}]),
    ("EV-CMP-03", "POS NE promo-price index — no competitor discounting in NE", "revenue_ne", "competitor_action",
     "pos", "CONTRADICTS", 0.0, 1.0, 1.0, 8, "INTERNAL", [],
     "pos.audit/promo_index/NE/2026-W32",
     "NE promo-price index flat — no competitor discounting observed in NE stores.",
     [{"claim": "NE promo index flat at 1.02 (±0.03)", "polarity": "CONTRADICTS", "span": "fig.4"}]),
    # --- marketing (contradicted by 'within plan' report; weak partial support) -
    ("EV-MKT-01", "Campaign mix note — NE weight reduced wks 12–13 vs plan", "revenue_ne", "internal_execution",
     "erp", "SUPPORTS", 0.35, 0.0, 0.37, 12, "INTERNAL", [],
     "erp.campaign/mix_plan/2026-W28",
     "NE campaign weight ran 8% under plan in weeks 12–13 (stale mix report).",
     [{"claim": "NE weight −8% vs plan wks 12–13", "polarity": "SUPPORTS", "span": "col.weight"}]),
    ("EV-MKT-02", "Campaign report — spend within plan, ROI in expected band", "revenue_ne", "internal_execution",
     "erp", "CONTRADICTS", 0.0, 1.0, 1.0, 3, "INTERNAL", [],
     "erp.campaign/weekly/2026-W32",
     "Campaign spend within plan; marketing ROI 2.98 inside the 2.8–3.4 band.",
     [{"claim": "Spend within plan; ROI 2.98 in band", "polarity": "CONTRADICTS", "span": "kpi.tbl"}]),
    # --- definition note (explains the ERP/GL gap; neutral, case-level) ---------
    ("EV-ACC-01", "Finance accrual note — returns accrual on the NE close", "revenue_ne", "definition_note",
     "gl", "NEUTRAL", 0.0, 0.0, 1.0, 4, "INTERNAL", ["EXECUTIVE", "ADMIN", "KPI_OWNER"],
     "gl.close/notes/FY26-M4#accrual",
     "Returns accrual (₹3.0M) recognized at close explains most of the invoiced-vs-recognized gap.",
     [{"claim": "Returns accrual ₹3.0M explains most of the 84.0 vs 87.0 gap", "polarity": "NEUTRAL", "span": "note.2"}]),
    # --- South case (abstention): tied hypotheses, stale POS -------------------
    ("EV-SOU-01", "Market tracker — competitor promo live in SOUTH", "sales_per_outlet_south", "competitor_action",
     "pos", "SUPPORTS", 1.0, 0.0, 1.0, 10, "INTERNAL", [],
     "syndicated.market_tracker/2026-W31/south",
     "Competitor promotion confirmed live across SOUTH catchments.",
     [{"claim": "Promo live in SOUTH catchments wks 12–14", "polarity": "SUPPORTS", "span": "p.1"}]),
    ("EV-SOU-02", "POS South promo-lift check — prior audit wave (stale)", "sales_per_outlet_south", "competitor_action",
     "pos", "SUPPORTS", 0.4, 0.0, 0.30, 18, "INTERNAL", [],
     "pos.audit/south/promo_lift/2026-W29",
     "Prior-wave promo-lift check consistent with demand diversion — two audit waves old.",
     [{"claim": "Promo lift visible in prior wave sample", "polarity": "SUPPORTS", "span": "fig.1"}]),
    ("EV-SOU-03", "ERP South — outlet sales healthy, no demand diversion", "sales_per_outlet_south", "competitor_action",
     "erp", "CONTRADICTS", 0.0, 0.25, 1.0, 1, "INTERNAL", [],
     "erp.sales_lines/region=SOUTH/2026-W32",
     "ERP South outlet sales steady — no diversion pattern in invoiced lines.",
     [{"claim": "South invoiced sales steady (±1.5%)", "polarity": "CONTRADICTS", "span": "tbl.outlet"}]),
    ("EV-SOU-04", "Audit methodology note — sample composition shifted in SOUTH", "sales_per_outlet_south", "measurement",
     "pos", "SUPPORTS", 0.8, 0.0, 0.55, 12, "INTERNAL", [],
     "pos.audit/method_change/2026-W30",
     "South panel sample re-weighted toward hypermarkets in W30 — level shift risk.",
     [{"claim": "Sample re-weighted toward hypermarkets (W30)", "polarity": "SUPPORTS", "span": "note.1"}]),
]


def ensure_evidence(db: Session, org_id: str, sources: dict[str, SourceSystem]) -> None:
    existing = db.query(PatternReliability).filter(PatternReliability.organization_id == org_id).count()
    if not existing:
        for cls, n, hits, prior in PATTERNS:
            db.add(PatternReliability(
                organization_id=org_id, pattern_class=cls, n_observations=n, hits=hits, prior=prior,
            ))

    existing_docs = db.query(EvidenceRecord).filter(EvidenceRecord.organization_id == org_id).count()
    if not existing_docs:
        for (key, title, kpi_code, dclass, src, polarity, sw, cw, fresh, age,
             classification, access, lineage, summary, claims) in _DOCS:
            db.add(EvidenceRecord(
                organization_id=org_id, doc_key=key, title=title, kpi_code=kpi_code,
                driver_class=dclass, source_id=sources[src].id, polarity=polarity,
                support_weight=sw, contradiction_weight=cw, freshness_score=fresh,
                age_days=age, occurred_at_days=age, data_classification=classification,
                access_roles=access, lineage=lineage, method="document",
                summary=summary, claims=claims,
            ))
    db.flush()
