import React from "react";
import { api } from "@/api/client";
import { Card, Chip, TechnicalDetails } from "@/components/ui";

interface MemoryHit {
  id: string; title: string; period_label: string; kpi_code: string; action_taken: string;
  outcome_rs: number; within_band: boolean; lesson: string; similarity: number; explanation: string;
  entities: string[];
}
interface SearchOut { results: MemoryHit[]; degraded_note: string; withheld_by_entitlement: number; method_label: string }

export function MemorySearch() {
  const [q, setQ] = React.useState("");
  const [out, setOut] = React.useState<SearchOut | null>(null);
  const [busy, setBusy] = React.useState(false);
  const search = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setBusy(true);
    try { setOut(await api.get<SearchOut>(`/memory/search?q=${encodeURIComponent(q)}&limit=6`)); }
    finally { setBusy(false); }
  };
  return (
    <div className="space-y-3">
      <Card title="Institutional memory" subtitle="Similarity search → historical case → previous action → outcome → lesson">
        <form onSubmit={search} className="flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. supplier delay Guwahati, launch ramp, discount"
            className="flex-1 rounded border border-line bg-ink-950 px-3 py-1.5 text-[12.5px] text-txt-primary placeholder:text-txt-muted/60" />
          <button disabled={busy || q.trim().length < 3} className="rounded border border-gold/60 px-3 py-1.5 text-[12px] text-gold hover:bg-gold/10 disabled:opacity-40">
            Search
          </button>
        </form>
        {out && (
          <div className="mt-2 space-y-1.5">
            {out.results.length === 0 && <p className="text-[12px] text-txt-muted">No similar case — the search itself is honest about that.</p>}
            {out.results.map((m) => (
              <div key={m.id} className="rounded border border-line bg-ink-950/60 px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="num text-[11px] text-gold">Similarity score: {m.similarity.toFixed(2)}</span>
                  <span className="text-[12.5px] font-medium text-txt-primary">{m.title}</span>
                  <span className="num text-[11px] text-txt-muted">{m.period_label}</span>
                  <Chip tone={m.within_band ? "pass" : "fail"}>{m.outcome_rs >= 0 ? "+" : ""}₹{(m.outcome_rs / 1e6).toFixed(1)}M</Chip>
                </div>
                <p className="mt-0.5 text-[11.5px] text-txt-secondary">{m.action_taken}</p>
                <p className="mt-0.5 text-[11px] text-txt-muted">{m.explanation}</p>
              </div>
            ))}
            {out.withheld_by_entitlement > 0 && (
              <p className="num text-[10.5px] text-warn">{out.withheld_by_entitlement} hidden results (withheld by your permissions)</p>
            )}
            {out.degraded_note && (
              <p className="num text-[10.5px] text-warn">Offline Search Mode Active (Using deterministic fallback)</p>
            )}
            <TechnicalDetails title="Search Algorithm Specs">
              <p>Method: {out.method_label}</p>
              <p>Algorithmically blended similarity metric applied.</p>
              {out.degraded_note && <p>Raw diagnostic: {out.degraded_note}</p>}
            </TechnicalDetails>
          </div>
        )}
        {!out && !busy && <p className="mt-2 text-[12px] text-txt-muted">Search is entitlement-filtered with a written similarity explanation — never a black box.</p>}
      </Card>
    </div>
  );
}
