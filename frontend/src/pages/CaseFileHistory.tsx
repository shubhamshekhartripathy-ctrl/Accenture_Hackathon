import React from "react";
import { api, ApiError } from "@/api/client";
import { getSession } from "@/auth/store";
import { Card, Chip } from "@/components/ui";
import type { Investigation, MemoryHit, Proposal } from "@/api/types";

export function CaseFileHistory({ kpiId }: { kpiId: string }) {
  const [inv, setInv] = React.useState<Investigation | null>(null);
  
  const load = React.useCallback(() => {
    api.get<Investigation[]>(`/investigations?kpi_id=${kpiId}`)
      .then((rows) => setInv(rows[0] ?? null))
      .catch(() => setInv(null));
  }, [kpiId]);

  React.useEffect(() => {
    load();
    window.addEventListener("demo-refresh", load);
    return () => window.removeEventListener("demo-refresh", load);
  }, [load]);

  if (!inv) return null;
  return (
    <div className="space-y-4">
      <MemoryPanel inv={inv} />
      <ProposalsPanel />
    </div>
  );
}

export function MemoryPanel({ inv }: { inv: Investigation }) {
  const [rows, setRows] = React.useState<MemoryHit[] | null>(null);
  const [meta, setMeta] = React.useState<{ degraded_note: string; withheld_by_entitlement: number } | null>(null);
  const lead = (inv.hypotheses ?? [])[0];
  React.useEffect(() => {
    const kpiCode = inv.kpi?.code ?? "";
    const params = new URLSearchParams({ q: `${kpiCode} ${lead?.code ?? ""}`.slice(0, 120), kpi_code: kpiCode, limit: "3" });
    api.get<{ results: MemoryHit[]; degraded_note: string; withheld_by_entitlement: number }>(`/memory/search?${params}`)
      .then(setData).catch(() => setRows([]));
    function setData(d: { results: MemoryHit[]; degraded_note: string; withheld_by_entitlement: number }) { setRows(d.results); setMeta(d); }
  }, [inv.id, lead?.code, inv.kpi?.code]);
  if (!rows) return null;
  return (
    <Card title="Institutional memory" subtitle="Current case → similarity search → historical case → previous action → outcome → lesson">
      {rows.length === 0 ? (
        <p className="text-[12px] text-txt-muted">No similar historical case found — this outcome will become the first.</p>
      ) : (
        <div className="space-y-1.5">
          {rows.map((m) => (
            <div key={m.id} className="rounded border border-line bg-ink-950/60 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="num text-[11px] text-gold">similarity {m.similarity.toFixed(2)}</span>
                <span className="text-[12.5px] font-medium text-txt-primary">{m.title}</span>
                <span className="num text-[11px] text-txt-muted">{m.period_label}</span>
                <Chip tone={m.within_band ? "pass" : "fail"}>{m.outcome_rs >= 0 ? "+" : ""}₹{(m.outcome_rs / 1e6).toFixed(1)}M</Chip>
              </div>
              <p className="mt-0.5 text-[11.5px] text-txt-secondary">{m.action_taken}</p>
              <p className="mt-0.5 text-[11px] text-txt-muted">{m.explanation}</p>
            </div>
          ))}
        </div>
      )}
      {meta && meta.withheld_by_entitlement > 0 && (
        <p className="num mt-1.5 text-[10.5px] text-warn">{meta.withheld_by_entitlement} case(s) withheld by entitlement — retrieval is role-filtered, never silent</p>
      )}
      {meta && <p className="num mt-1 text-[10px] text-txt-muted/70">{meta.degraded_note}</p>}
    </Card>
  );
}

export function ProposalsPanel() {
  const user = getSession()?.user;
  const [rows, setRows] = React.useState<Proposal[] | null>(null);
  const [notes, setNotes] = React.useState<Record<string, string>>({});
  const [err, setErr] = React.useState<string | null>(null);
  const load = React.useCallback(() => {
    api.get<Proposal[]>("/memory/proposals").then(setRows).catch(() => setRows([]));
  }, []);
  React.useEffect(load, [load]);
  if (!rows || rows.length === 0) return null;
  const canReview = user && ["KPI_OWNER", "ADMIN"].includes(user.role);
  const review = async (p: Proposal, decision: string) => {
    setErr(null);
    try { await api.post(`/memory/proposals/${p.id}/review`, { decision, note: notes[p.id] ?? "" }); load(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Review failed"); }
  };
  return (
    <Card title="Contract change proposals" subtitle="Learning proposes — the owner disposes. ACTIVE contracts change only at MERGE (versioned)">
      <div className="space-y-1.5">
        {rows.map((p) => (
          <div key={p.id} className={`rounded border px-3 py-2 ${p.status === "MERGED" ? "border-pass/30 bg-pass/5" : p.status === "REJECTED" ? "border-fail/30 bg-fail/5" : "border-warn/30 bg-warn/5"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone={p.status === "MERGED" ? "pass" : p.status === "REJECTED" ? "fail" : "warn"}>{p.status}</Chip>
              <span className="text-[12px] text-txt-primary">{p.change_type.replace(/_/g, " ")}</span>
              {p.origin === "LEARNING_LOOP" && <Chip tone="info">LEARNING LOOP</Chip>}
              <span className="num text-[10.5px] text-txt-muted">base v{p.base_version}{p.merged_to_version ? ` → v${p.merged_to_version}` : ""} · by {p.proposed_by_role ?? "?"}</span>
            </div>
            <p className="mt-0.5 text-[11.5px] text-txt-secondary">{p.rationale}</p>
            {p.status === "IN_REVIEW" && canReview && (
              <div className="mt-1 flex flex-wrap gap-1.5">
                <input value={notes[p.id] ?? ""} onChange={(e) => setNotes({ ...notes, [p.id]: e.target.value })}
                  placeholder="review note (≥10 chars)" className="flex-1 rounded border border-line bg-ink-950 px-2 py-1 text-[11px] text-txt-primary placeholder:text-txt-muted/60" />
                <button onClick={() => review(p, "MERGE")} disabled={(notes[p.id] ?? "").trim().length < 10} className="rounded border border-pass/50 px-2 py-0.5 text-[10.5px] text-pass hover:bg-pass/10 disabled:opacity-40">MERGE</button>
                <button onClick={() => review(p, "REJECT")} disabled={(notes[p.id] ?? "").trim().length < 10} className="rounded border border-fail/50 px-2 py-0.5 text-[10.5px] text-fail hover:bg-fail/10 disabled:opacity-40">REJECT</button>
              </div>
            )}
            {p.review_note && <p className="mt-0.5 text-[10.5px] text-txt-muted">review: {p.review_note}</p>}
          </div>
        ))}
      </div>
      {err && <p className="mt-1 text-[11px] text-fail">{err}</p>}
    </Card>
  );
}