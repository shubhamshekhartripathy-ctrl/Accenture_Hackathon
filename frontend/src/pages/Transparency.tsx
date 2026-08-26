import React from "react";
import { api } from "@/api/client";
import { getSession } from "@/auth/store";
import { Banner, Card, Chip, Skeleton } from "@/components/ui";

interface StageRow {
  run_id: string; stage_code: string; method_label: string; llm_used: boolean;
  model_class: string | null; route_reason: string | null; provider: string | null;
  latency_ms: number; cost_est_rs: number; cache_hit: boolean; ok: boolean;
}
interface RouteRow {
  capability: string; data_classification: string; decision: string;
  model_class: string | null; provider: string | null; policy_ref: string | null;
  reason_code: string; fallback: string | null; cost_est_rs: number; created_at: string;
}
interface Ledger {
  stages: StageRow[]; routes: RouteRow[];
  summary: {
    n_stages: number; llm_stages: number; numbers_computed_without_llm_pct: number;
    n_routes: number; n_allowed: number; n_denied_or_fallback: number; denial_reasons: string[];
    cache_hits: number; tenant_cost_cap_rs: number; tenant_spend_rs: number; llm_enabled: boolean;
  };
}

const tone = (d: string) => (d === "ALLOWED" ? "pass" : d === "POLICY_DENIED" ? "fail" : "warn");

export function Transparency() {
  const user = getSession()?.user;
  const [l, setL] = React.useState<Ledger | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const load = React.useCallback(() => {
    api.get<Ledger>("/transparency").then(setL).catch((e) => setErr(e.message));
  }, []);
  React.useEffect(load, [load]);

  const toggle = async (enabled: boolean) => {
    setBusy(true);
    try { await api.post("/demo/toggle-llm", { enabled }); load(); window.dispatchEvent(new Event("demo-refresh")); } finally { setBusy(false); }
  };

  if (err) return <Banner tone="fail" title="Ledger unavailable">{err}</Banner>;
  if (!l) return <Skeleton className="h-64" />;
  const s = l.summary;
  const canToggle = user && ["ADMIN", "EXECUTIVE"].includes(user.role);

  return (
    <div className="space-y-3">
      <Card title="Transparency Ledger" subtitle="Every stage, every model route, every rupee — nothing hidden">
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 md:grid-cols-4">
          <div><p className="text-[10.5px] uppercase tracking-wide text-txt-muted">Stages</p>
            <p className="num text-txt-primary">{s.n_stages} <span className="text-[11px] text-txt-muted">({s.llm_stages} LLM)</span></p></div>
          <div><p className="text-[10.5px] uppercase tracking-wide text-txt-muted">Numbers w/o LLM</p>
            <p className="num text-pass">{s.numbers_computed_without_llm_pct.toFixed(0)}%</p></div>
          <div><p className="text-[10.5px] uppercase tracking-wide text-txt-muted">Tenant spend / cap</p>
            <p className="num text-txt-secondary">₹{s.tenant_spend_rs.toFixed(2)} / ₹{s.tenant_cost_cap_rs.toFixed(0)}</p></div>
          <div><p className="text-[10.5px] uppercase tracking-wide text-txt-muted">Cache hits</p>
            <p className="num text-txt-secondary">{s.cache_hits}</p></div>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Chip tone={s.llm_enabled ? "pass" : "warn"}>LLM {s.llm_enabled ? "ENABLED" : "DISABLED (demo)"}</Chip>
          <span className="num text-[11px] text-txt-muted">
            routes: {s.n_allowed} allowed · {s.n_denied_or_fallback} fallback/denied
            {s.denial_reasons.length > 0 && ` (${s.denial_reasons.join(", ")})`}
          </span>
          {canToggle && (
            <button disabled={busy} onClick={() => toggle(!s.llm_enabled)}
              className="rounded border border-gold/50 px-2 py-0.5 text-[10.5px] text-gold hover:bg-gold/10 disabled:opacity-40">
              {s.llm_enabled ? "Toggle LLM off (demo)" : "Toggle LLM on"}
            </button>
          )}
        </div>
        {!s.llm_enabled && (
          <div className="mt-2"><Banner tone="warn" title="DEGRADED — LLM disabled">
            Every route resolves to the deterministic fallback; conclusions and numbers are unchanged (rules compute them).
          </Banner></div>
        )}
      </Card>

      <Card title="Model routes" subtitle="capability × data classification → policy → route (reason codes on every row)">
        {l.routes.length === 0 ? (
          <p className="text-[12px] text-txt-muted">No model calls yet — briefs and narratives route here when opened.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[11.5px]">
              <thead className="text-[10px] uppercase tracking-wide text-txt-muted">
                <tr><th className="py-1 pr-3">capability</th><th className="pr-3">data class</th><th className="pr-3">decision</th>
                    <th className="pr-3">model class</th><th className="pr-3">reason</th><th className="pr-3">fallback</th><th className="num">₹ est</th></tr>
              </thead>
              <tbody className="num">
                {l.routes.slice(0, 30).map((r, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="py-1 pr-3 text-txt-secondary">{r.capability}</td>
                    <td className="pr-3 text-txt-muted">{r.data_classification}</td>
                    <td className="pr-3"><Chip tone={tone(r.decision)}>{r.decision}</Chip></td>
                    <td className="pr-3 text-txt-secondary">{r.model_class ?? "—"}</td>
                    <td className="pr-3 text-txt-muted">{r.reason_code}</td>
                    <td className="pr-3 text-txt-muted">{r.fallback ?? "—"}</td>
                    <td className="text-txt-secondary">{r.cost_est_rs.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Stage telemetry" subtitle="one row per pipeline stage — method label, LLM flag, latency">
        <div className="max-h-72 overflow-y-auto">
          <table className="w-full text-left text-[11.5px]">
            <thead className="sticky top-0 bg-ink text-[10px] uppercase tracking-wide text-txt-muted">
              <tr><th className="py-1 pr-3">stage</th><th className="pr-3">method</th><th className="pr-3">llm</th>
                  <th className="pr-3">reason</th><th className="num pr-3">ms</th><th className="num pr-3">cache</th><th>ok</th></tr>
            </thead>
            <tbody className="num">
              {l.stages.slice(0, 60).map((st, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="py-1 pr-3 text-txt-secondary">{st.stage_code}</td>
                  <td className="pr-3 text-txt-muted">{st.method_label}</td>
                  <td className="pr-3">{st.llm_used ? <Chip tone="info">llm</Chip> : <span className="text-txt-muted">rules</span>}</td>
                  <td className="pr-3 text-txt-muted">{st.route_reason ?? "—"}</td>
                  <td className="num pr-3 text-txt-secondary">{st.latency_ms}</td>
                  <td className="num pr-3 text-txt-muted">{st.cache_hit ? "hit" : "—"}</td>
                  <td>{st.ok ? <span className="text-pass">✓</span> : <span className="text-fail">✗</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
