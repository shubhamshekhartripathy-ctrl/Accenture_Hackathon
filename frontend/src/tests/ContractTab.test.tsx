import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ContractTab } from "@/pages/CaseFileContract";
import type { ContractDetail } from "@/pages/CaseFile";

const contract: ContractDetail = {
  id: "c1",
  kpi_code: "revenue_ne",
  kpi_name: "Revenue — Northeast",
  name: "Revenue (Invoiced, Net) — Northeast",
  business_definition: "Invoiced net sales for the Northeast region before close accrual.",
  formula_sql: "SELECT SUM(net_amount_inr) FROM erp.sales_lines WHERE region='NE'",
  formula_note: "Excludes returns accrual posted at GL close.",
  unit: "INR_M",
  business_function: "Commercial / Sales",
  owner_name: "Vikram Rao",
  owner_role: "KPI_OWNER",
  status: "ACTIVE",
  calendar_rule: "Fiscal weeks Mon–Sun",
  hierarchy_config: {},
  version: 2,
  sources: [
    {
      id: "s1", source_code: "erp", source_name: "Apex ERP", lineage_path: "erp.sales_lines[region=NE]",
      is_authoritative: true, expected_cadence: "daily", expected_grain: "SKU x DC",
      tolerance_pct: 1.0, data_classification: "INTERNAL",
    },
    {
      id: "s2", source_code: "scorecard", source_name: "Supplier Scorecard", lineage_path: "scorecard.otif[lane=NE]",
      is_authoritative: false, expected_cadence: "weekly", expected_grain: "supplier x region",
      tolerance_pct: 2.0, data_classification: "SENSITIVE",
    },
  ],
  drivers: [
    { id: "d1", driver_code: "supplier_delay", name: "Supplier delay at Guwahati DC lane", direction: -1, prior_weight: 0.62, hypothesis_class: "supply_disruption", rank: 1 },
  ],
  threshold: {
    expected_lo: 88, expected_hi: 104, warning_deviation_pct: -4, critical_deviation_pct: -8,
    exposure_rs_per_point: 716667, margin_weight: 0.15, strategic_weight: 0.8, min_history: 13, cold_start_flag: false,
  },
  rights: [
    { id: "r1", role: "SUPPLY_CHAIN", action_class: "supply_switch", may_recommend: true, may_simulate: true, may_approve: true, approve_limit_rs: 2_000_000, escalate_to_role: "EXECUTIVE" },
    { id: "r2", role: "ANALYST", action_class: "*", may_recommend: true, may_simulate: true, may_approve: false, approve_limit_rs: 0, escalate_to_role: null },
  ],
  entitlements: [
    { id: "e1", role: "SUPPLY_CHAIN", row_scope: { region: ["NE"] }, masked_columns: ["unit_cost_rs", "marketing_roi"], domains: ["operations"] },
  ],
  versions: [
    { version: 2, change_reason: "contract_edit", created_at: "2026-08-20T10:00:00", status_in_snapshot: "ACTIVE" },
    { version: 1, change_reason: "initial governed definition (seed)", created_at: "2026-08-01T09:00:00", status_in_snapshot: "ACTIVE" },
  ],
};

describe("ContractTab", () => {
  it("renders the governed definition, formula, and lineage", () => {
    render(<ContractTab contract={contract} />);
    expect(screen.getByText(/invoiced net sales for the northeast/i)).toBeInTheDocument();
    expect(screen.getAllByText(/erp\.sales_lines/i).length).toBeGreaterThan(0); // formula + lineage both show it
    expect(screen.getByText(/apex erp/i)).toBeInTheDocument();
    expect(screen.getByText(/supplier scorecard/i)).toBeInTheDocument();
    expect(screen.getByText("authoritative")).toBeInTheDocument();
    expect(screen.getByText("SENSITIVE")).toBeInTheDocument();
  });

  it("renders drivers with priors and decision rights with limits", () => {
    render(<ContractTab contract={contract} />);
    expect(screen.getByText(/supplier delay at guwahati/i)).toBeInTheDocument();
    expect(screen.getByText("0.62")).toBeInTheDocument();
    expect(screen.getByText("₹2.00M")).toBeInTheDocument(); // SC approve limit
    expect(screen.getAllByText("approve").length).toBeGreaterThan(0);
  });

  it("shows masked columns per role and version history drawer", async () => {
    render(<ContractTab contract={contract} />);
    expect(screen.getByText(/unit_cost_rs, marketing_roi/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /show versions/i }));
    expect(screen.getByText(/initial governed definition/i)).toBeInTheDocument();
  });

  it("flags loud degradation when sources are missing", () => {
    const broken = { ...contract, sources: [], drivers: [], rights: [] };
    render(<ContractTab contract={broken} />);
    expect(screen.getByText(/no sources declared/i)).toBeInTheDocument();
    expect(screen.getByText(/hypothesis space shrinks/i)).toBeInTheDocument();
    expect(screen.getByText(/no action recommendations/i)).toBeInTheDocument();
  });
});
