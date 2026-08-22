import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Overview } from "@/pages/Overview";

const entries = [
  {
    kpi_id: "k1", kpi_code: "revenue_ne", kpi_name: "Revenue — Northeast", region: "NE", unit: "INR_M",
    band: "CRITICAL", score: 0.79, deviation_pct: -12.0, robust_z: 5.1, current_value: 84.0,
    baseline: 95.45, ci: [91.1, 99.8], exposure_rs: 8_600_000, cold_start: false, monitor_only: false,
    arithmetic: { formula: "significance × clamp(log1p(impact)/10, 0, 1)", significance: 0.787, deviation_pct: -12.0, exposure_rs_per_point: 716667, exposure_rs: 8600000, strategic_weight: 0.8, margin_weight: 0.15, impact_norm: 1.0, score: 0.787, raw_band: "CRITICAL", floored: false, floor_band: null },
    detection_method: "seasonal_median_robust_z", model_version: "1.0.0", detected_at: "2026-08-10T00:00:00Z",
    contract_status: "CONFLICTED", contract_id: "c1", investigation_id: "i1", workflow_state: "TRIAGED", reliability: 0.76,
  },
  {
    kpi_id: "k2", kpi_code: "marketing_roi", kpi_name: "Marketing ROI", region: "NATIONAL", unit: "RATIO",
    band: "WATCH", score: 0.025, deviation_pct: -4.0, robust_z: 2.1, current_value: 2.976,
    baseline: 3.1, ci: [2.98, 3.22], exposure_rs: 200_000, cold_start: false, monitor_only: false,
    arithmetic: { formula: "…", score: 0.025, raw_band: "NOISE", floored: true, floor_band: "WATCH", significance: 0.025, exposure_rs: 200000, exposure_rs_per_point: 50000, strategic_weight: 0.1, margin_weight: 0.05, impact_norm: 1.0, deviation_pct: -4.0 },
    detection_method: "seasonal_median_robust_z", model_version: "1.0.0", detected_at: "2026-08-10T00:00:00Z",
    contract_status: "ACTIVE", contract_id: "c2", investigation_id: null, workflow_state: null, reliability: null,
  },
  {
    kpi_id: "k3", kpi_code: "millet_noodles_revenue", kpi_name: "Millet Noodles Revenue — Launch", region: "NATIONAL", unit: "INR_M",
    band: "COLD START", score: 0, deviation_pct: 7.0, robust_z: 0.5, current_value: 2.66,
    baseline: 2.49, ci: [1.76, 3.21], exposure_rs: null, cold_start: true, monitor_only: true,
    arithmetic: null, detection_method: "seasonal_median_robust_z", model_version: "1.0.0",
    detected_at: "2026-08-10T00:00:00Z", contract_status: "ACTIVE", contract_id: "c3",
    investigation_id: null, workflow_state: null, reliability: null,
  },
];

function withRouter(ui: React.ReactElement) {
  return <MemoryRouter>{ui}</MemoryRouter>;
}

describe("Overview — materiality queue", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    localStorage.setItem(
      "rf.session",
      JSON.stringify({ access_token: "t", user: { id: "u", email: "e", full_name: "E", role: "EXECUTIVE", job_title: "", region_scope: [], organization: "Apex Foods", organization_id: "o" } }),
    );
  });

  it("renders CRITICAL dominant, WATCH, and the pinned cold-start section", async () => {
    vi.stubGlobal(
      "fetch",
      // a fresh Response per call: several components fetch concurrently and a
      // Response body can be read only once
      vi.fn().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ data: { entries, count: 3 }, meta: {} }), { status: 200 }))
      ),
    );
    render(withRouter(<Overview />));
    expect(await screen.findByText(/Revenue — Northeast/i)).toBeInTheDocument();
    expect(screen.getAllByText("CRITICAL").length).toBeGreaterThan(0);
    expect(screen.getByText("INPUTS CONFLICT")).toBeInTheDocument();
    expect(screen.getByText("WATCH")).toBeInTheDocument();
    expect(screen.getByText(/cold start — monitor-only/i)).toBeInTheDocument();
    expect(screen.getByText(/₹8.6M/)).toBeInTheDocument(); // exposure in the dominant card
  });

  it("expands the 'Why CRITICAL?' arithmetic drill-down", async () => {
    vi.stubGlobal(
      "fetch",
      // a fresh Response per call: several components fetch concurrently and a
      // Response body can be read only once
      vi.fn().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ data: { entries, count: 3 }, meta: {} }), { status: 200 }))
      ),
    );
    render(withRouter(<Overview />));
    await screen.findByText(/Revenue — Northeast/i);
    await userEvent.click(screen.getByRole("button", { name: /why critical\?/i }));
    expect(screen.getAllByText(/significance/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("0.787").length).toBeGreaterThan(0);
  });

  it("shows the governance floor note on the watch-list KPI", async () => {
    vi.stubGlobal(
      "fetch",
      // a fresh Response per call: several components fetch concurrently and a
      // Response body can be read only once
      vi.fn().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ data: { entries, count: 3 }, meta: {} }), { status: 200 }))
      ),
    );
    render(withRouter(<Overview />));
    await screen.findByText(/Revenue — Northeast/i);
    await userEvent.click(screen.getByRole("button", { name: /why watch\?/i }));
    expect(screen.getByText(/governance floor/i)).toBeInTheDocument();
    expect(screen.getByText(/raw score landed in NOISE/i)).toBeInTheDocument();
  });
});
