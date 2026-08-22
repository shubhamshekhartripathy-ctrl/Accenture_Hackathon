import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { setSession, clearSession } from "@/auth/store";
import { MemoryPanel, ProposalsPanel } from "@/pages/CaseFileHistory";

const hit = {
  id: "h1", title: "NE Q3 2025 — Supplier delay at Guwahati DC", period_label: "NE Q3 2025",
  kpi_code: "revenue_ne", action_taken: "activated the pre-qualified backup supplier",
  outcome_rs: 3_100_000, within_band: true, similarity: 0.89,
  lesson: "Decide FAST — every day of waiting cost ₹0.4M.",
  explanation: "Matched KPI revenue_ne; embedding cosine 0.54 (feature_hash_v1), blended score 0.89. Historical outcome +₹3.1M (within band). Lesson: Decide FAST",
};

const inv = { id: "i1", kpi: { code: "revenue_ne", name: "Revenue", unit: "INR_M" }, hypotheses: [], options: [] } as never;

describe("S9 — institutional memory + governed proposals", () => {
  beforeEach(() => {
    setSession({ access_token: "t", refresh_token: "r", user: { id: "u", email: "e", full_name: "E", role: "KPI_OWNER", job_title: "", region_scope: [], organization: "Apex Foods", organization_id: "o" } });
  });
  afterEach(() => { vi.unstubAllGlobals(); clearSession(); });

  it("memory panel shows similarity, outcome, lesson, and the degraded (hashing fallback) note", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ data: { results: [hit], degraded_note: "DEGRADED: pgvector unavailable — feature_hash_v1 active", withheld_by_entitlement: 1 }, meta: {} }), { status: 200 }))));
    render(<MemoryRouter><MemoryPanel inv={inv} /></MemoryRouter>);
    expect(await screen.findByText(/Supplier delay at Guwahati DC/i)).toBeInTheDocument();
    expect(screen.getByText(/similarity 0\.89/)).toBeInTheDocument();
    expect(screen.getAllByText(/\+₹3\.1M/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Decide FAST/i)).toBeInTheDocument();
    expect(screen.getByText(/DEGRADED: pgvector unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/1 case\(s\) withheld by entitlement/i)).toBeInTheDocument();
  });

  it("proposals panel lists learning-loop proposals and gates MERGE behind a review note", async () => {
    const proposal = { id: "p1", change_type: "driver_prior_update", rationale: "hypothesis_verdict CONFIRMED on H1", origin: "LEARNING_LOOP", status: "IN_REVIEW", base_version: 3, merged_to_version: null, review_note: null, proposed_by_role: "KPI_OWNER", payload: {} };
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ data: [proposal], meta: {} }), { status: 200 }))));
    render(<MemoryRouter><ProposalsPanel /></MemoryRouter>);
    expect(await screen.findByText(/LEARNING LOOP/i)).toBeInTheDocument();
    expect(screen.getByText(/driver prior update/i)).toBeInTheDocument();
    expect(screen.getByText(/base v3/i)).toBeInTheDocument();
    const merge = screen.getByRole("button", { name: "MERGE" }) as HTMLButtonElement;
    expect(merge.disabled).toBe(true); // no review note yet — governance requires it
  });
});
