/** Investigation Workspace — three zones (arch §11A):
 *  LEFT hypotheses rail (~300px) · CENTER reasoning canvas (dominant) ·
 *  RIGHT evidence inspector (~360px). All data from the real pipeline. */
import React from "react";
import { api, ApiError } from "@/api/client";
import { getSession } from "@/auth/store";
import { Banner, Card, Chip, ErrorState, Skeleton } from "@/components/ui";
import type { EvidenceLink, DecompComponent, Investigation, Brief } from "@/api/types";


const STATE_TONE: Record<string, "pass" | "warn" | "fail" | "info" | "neutral"> = {
  EXPLAINING: "info", EXPLAINED: "info", CERTAINTY_DECISION: "info", TRIAGED: "info",
  ABSTAINED: "fail", CLARIFY: "warn",
  FAILED: "fail", RECONCILED: "neutral", DETECTED: "neutral", CONTRACT_READY: "neutral",
};

export function CaseFileInvestigation({ kpiId }: { kpiId: string }) {
  const [inv, setInv] = React.useState<Investigation | null>(null);
  const [none, setNone] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [live, setLive] = React.useState<string[]>([]);
  const [sel, setSel] = React.useState<string | null>(null); // selected hypothesis id
  const user = getSession()?.user;
  const canRun = user && ["ANALYST", "ADMIN"].includes(user.role);

  const load = React.useCallback(() => {
    setError(null); setNone(false);
    api.get<Investigation[]>(`/investigations?kpi_id=${kpiId}`)
      .then((rows) => { if (rows.length === 0) setNone(true); else { setInv(rows[0]); setSel((s) => s ?? rows[0].hypotheses?.[0]?.id ?? null); } })
      .catch((e) => setError(e.message));
  }, [kpiId]);

  React.useEffect(() => {
    load();
    window.addEventListener("demo-refresh", load);
    return () => window.removeEventListener("demo-refresh", load);
  }, [load]);

  const start = async () => {
    setBusy(true); setError(null); setLive([]);
    try {
      const data = await api.post<Investigation>("/investigations", { kpi_id: kpiId });
      setInv(data); setNone(false);
      try {
        const es = new EventSource(`/api/v1/investigations/${data.id}/events`);
        for (const name of ["reconciliation_complete", "decomposition_complete", "hypotheses_generated", "evidence_retrieved", "ranking_complete", "prefix_complete"]) {
          es.addEventListener(name, (ev) => setLive((l) => [...l, (ev as MessageEvent).data.slice(0, 110)]));
        }
        es.addEventListener("done", () => es.close());
        es.onerror = () => es.close();
      } catch { /* SSE optional — run already persisted */ }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to start investigation");
    } finally { setBusy(false); }
  };

  if (error && !inv) return <ErrorState message={error} retry={load} />;
  if (!inv && !none) return <Skeleton className="h-64" />;
  if (none) {
    return (
      <Card title="Investigation" subtitle="Contract → Reconcile → Detect → Triage → Decompose → Hypotheses → Evidence → Rank">
        <Banner tone="info" title="No investigation yet">
          {canRun ? "Start the pipeline: sources reconcile, the movement decomposes, competing hypotheses gather evidence and rank — deterministically." : "An analyst or admin starts investigations; every stage and method is visible afterwards."}
        </Banner>
        {canRun && (
          <button onClick={start} disabled={busy} className="mt-3 rounded border border-gold/60 bg-gold-soft px-3 py-1.5 text-[12.5px] font-medium text-gold transition hover:bg-gold/20 disabled:opacity-50">
            {busy ? "Running pipeline…" : "Run investigation"}
          </button>
        )}
        {error && <p className="mt-2 text-[12px] text-fail">{error}</p>}
      </Card>
    );
  }

  const hyps = inv!.hypotheses ?? [];
  const selected = hyps.find((h) => h.id === sel) ?? hyps[0] ?? null;
  const d = inv!.detection as Record<string, number> | null;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <Chip tone={STATE_TONE[inv!.workflow_state] ?? "neutral"}>{inv!.workflow_state}</Chip>
        <span className="num text-[12px] text-txt-muted">contract v{inv!.contract_version} pinned · period {inv!.period_key}</span>
        {inv!.reliability != null && (
          <span className="num text-[12px] text-txt-secondary">reliability {inv!.reliability.toFixed(2)} · cap {inv!.confidence_cap!.toFixed(2)}</span>
        )}
        {inv!.cold_start_mode && <Chip tone="warn">COLD START MODE</Chip>}
      </div>
      {inv!.last_error && <Banner tone="fail" title="Last error">{inv!.last_error}</Banner>}

      {inv!.certainty_state && (
        <div className={`rounded-lg border px-4 py-3 ${inv!.certainty_state === "ABSTAIN" ? "border-fail/50 bg-fail/5" : inv!.certainty_state === "ACT" ? "border-pass/40 bg-pass/5" : "border-warn/40 bg-warn/5"}`}>
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-[12px] font-semibold uppercase tracking-wide text-txt-muted">Certainty</span>
            <Chip tone={inv!.certainty_state === "ABSTAIN" ? "fail" : inv!.certainty_state === "ACT" ? "pass" : inv!.certainty_state === "CLARIFY" ? "warn" : "info"}>{inv!.certainty_state}</Chip>
            {inv!.final_confidence != null && <span className="num text-[13px] text-txt-secondary">final {inv!.final_confidence.toFixed(2)}</span>}
            {inv!.lead_margin != null && <span className="num text-[12px] text-txt-muted">margin {inv!.lead_margin.toFixed(2)}</span>}
          </div>
          <ul className="mt-1.5 space-y-0.5">
            {inv!.certainty_reasons.map((r, i) => (
              <li key={i} className="text-[12px] leading-relaxed text-txt-secondary">• {r}</li>
            ))}
          </ul>
        </div>
      )}

      {inv!.cold_start_mode && inv!.clarification && (
        <Card title="COLD START — monitor-only" subtitle="A mode of behaviour, not a warning label">
          <p className="text-[12.5px] text-txt-secondary">{String(inv!.clarification.named_gap ?? "")}</p>
          <p className="mt-1.5 text-[11px] font-semibold uppercase tracking-wide text-txt-muted">Unlock conditions</p>
          <ul className="space-y-0.5">
            {((inv!.clarification.unlock_conditions as string[]) ?? []).map((u, i) => (
              <li key={i} className="text-[12px] text-txt-secondary">• {u}</li>
            ))}
          </ul>
          <p className="num mt-1.5 text-[11px] text-txt-muted">
            confidence capped at 0.45 · routed to {String(inv!.clarification.routed_to_role)} · auto-resumes when {String(inv!.clarification.auto_resumes_on)}
          </p>
        </Card>
      )}

      {inv!.abstention && (
        <Card title="ABSTAINED — why we refuse to recommend" subtitle="Six fields, always shown together (AC8)">
          <div className="grid gap-3 md:grid-cols-2">
            {([
              ["Why it cannot conclude", inv!.abstention.why_it_cannot_conclude],
              ["What evidence conflicts", inv!.abstention.what_evidence_conflicts],
              ["What information is missing", inv!.abstention.what_information_is_missing],
              ["What would resolve it", inv!.abstention.what_would_resolve_it],
              ["Who should provide it", inv!.abstention.who_should_provide_it],
              ["Is waiting safer?", inv!.abstention.is_waiting_safer],
            ] as [string, string | number | null | undefined][]).map(([t, v]) => (
              <div key={t} className="rounded border border-line bg-ink-900 px-3 py-2">
                <p className="text-[10.5px] font-semibold uppercase tracking-wide text-txt-muted">{t}</p>
                <p className="mt-0.5 text-[12px] leading-relaxed text-txt-secondary">{String(v ?? "—")}</p>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11.5px] text-warn">No action options are offered for this case. Refreshing the named data may re-open it.</p>
        </Card>
      )}

      <div className="grid gap-3 lg:grid-cols-[300px_minmax(0,1fr)_360px]">
        {/* LEFT — hypotheses rail */}
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-txt-muted">Competing hypotheses</p>
          {hyps.length === 0 && <p className="text-[12.5px] text-txt-muted">No hypotheses yet — run the pipeline.</p>}
          {hyps.map((h) => (
            <button key={h.id} onClick={() => setSel(h.id)}
              className={`w-full rounded-lg border px-3 py-2.5 text-left transition ${selected?.id === h.id ? "border-gold/60 bg-gold-soft/40" : "border-line bg-ink-900 hover:border-gold/30"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[12.5px] font-medium text-txt-primary">{h.code.replace(/_/g, " ")}</span>
                <span className="num text-[15px] font-semibold text-gold">{h.confidence.toFixed(2)}</span>
              </div>
              <div className="mt-1.5 flex items-center gap-1.5">
                <span className="num text-[10.5px] text-pass">+{h.evidence_counts.supporting ?? 0}</span>
                <span className="num text-[10.5px] text-fail">−{h.evidence_counts.contradicting ?? 0}</span>
                {(h.evidence_counts.stale ?? 0) > 0 && <span className="num text-[10.5px] text-warn">~{h.evidence_counts.stale}</span>}
                {h.rank === 1 && <Chip tone="gold">LEAD {h.final_confidence.toFixed(2)}</Chip>}
              </div>
              <div className="mt-1.5 h-1 w-full rounded bg-ink-950">
                <div className={`h-1 rounded ${h.rank === 1 ? "bg-gold" : "bg-txt-muted/60"}`} style={{ width: `${Math.min(100, h.confidence * 100)}%` }} />
              </div>
            </button>
          ))}
          <Card title="Stage telemetry">
            <Stat k="Stages" v={String(inv!.telemetry.stages)} />
            <Stat k="LLM stages" v={String(inv!.telemetry.llm_stages)} tone="pass" />
            <Stat k="Numbers w/o LLM" v={`${inv!.telemetry.numbers_computed_without_llm_pct.toFixed(0)}%`} tone="pass" />
            <Stat k="Latency" v={`${inv!.telemetry.latency_ms_total} ms`} />
            {live.length > 0 && <p className="num border-t border-line pt-1 text-[10.5px] text-gold">{live[live.length - 1]}</p>}
          </Card>
        </div>

        {/* CENTER — reasoning canvas */}
        <div className="space-y-3">
          <BriefCard invId={inv!.id} />
          
          
          
          <Card title="Contribution decomposition" subtitle="Movement split into price / volume / mix / region / residual — deterministic SQL">
            <Decomposition invId={inv!.id} />
          </Card>
          {selected && (
            <Card title={`Reasoning — ${selected.code.replace(/_/g, " ")}`} subtitle="Confidence composition (rules + stats; the LLM has no vote)">
              <p className="text-[13px] leading-relaxed text-txt-secondary">{selected.statement}</p>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {selected.reasoning_path.map((n, i) => (
                  <React.Fragment key={i}>
                    {i > 0 && <span className={`text-[10px] font-mono ${i % 2 === 1 ? "text-gold/80" : "text-txt-muted"}`}>→</span>}
                    <span className={`rounded border px-1.5 py-0.5 text-[10.5px] ${i % 2 === 1 ? "border-gold/40 text-gold/90 font-mono" : "border-line text-txt-secondary"}`}>{n}</span>
                  </React.Fragment>
                ))}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-[12px] md:grid-cols-3">
                <Stat k="Balance" v={selected.balance.toFixed(3)} note="(S−C)/(S+C+1)" />
                <Stat k="Freshness" v={selected.freshness_avg.toFixed(3)} />
                <Stat k="Agreement" v={selected.source_agreement.toFixed(3)} />
                <Stat k="Pattern prior" v={selected.pattern_prior.toFixed(3)} />
                <Stat k="Confidence" v={selected.confidence.toFixed(3)} note="0.35b+0.20f+0.15a+0.30p" />
                <Stat k="Final (×cap)" v={selected.rank === 1 ? selected.final_confidence.toFixed(3) : "—"} tone="gold" />
              </div>
            </Card>
          )}
          {d && (
            <Card title="Detection & materiality" subtitle="Statistics first; business importance second">
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[12px] md:grid-cols-4">
                <Stat k="Current" v={`${Number(d.source_value).toFixed(1)}`} />
                <Stat k="Baseline" v={Number(d.baseline).toFixed(2)} />
                <Stat k="Deviation" v={`${Number(d.deviation_pct).toFixed(2)}%`} tone={Number(d.deviation_pct) < 0 ? "fail" : "pass"} />
                <Stat k="Robust z" v={`${Number(d.robust_z).toFixed(2)}σ`} />
                <Stat k="95% CI" v={`[${Number(d.ci_lo).toFixed(1)}, ${Number(d.ci_hi).toFixed(1)}]`} />
                <Stat k="Band" v={inv!.materiality?.band ?? "—"} tone={inv!.materiality?.band === "CRITICAL" ? "fail" : undefined} />
                <Stat k="Exposure" v={`₹${((inv!.materiality?.exposure_rs ?? 0) / 1e6).toFixed(1)}M`} tone="gold" />
                <Stat k="History" v={`${d.history_n} periods`} />
              </div>
            </Card>
          )}
          <Card title="Pipeline stages" subtitle="Every transition persisted — refresh never loses state">
            <ol className="space-y-1">
              {inv!.stage_events.map((e, i) => (
                <li key={i} className="flex items-center gap-2.5 text-[12px]">
                  <span className={`h-1.5 w-1.5 rounded-full ${e.ok ? "bg-pass" : "bg-fail"}`} aria-hidden />
                  <span className="num w-44 text-txt-secondary">{e.from_state} → {e.to_state}</span>
                  <span className="text-txt-muted">{e.message}</span>
                </li>
              ))}
            </ol>
          </Card>
        </div>

        {/* RIGHT — evidence inspector */}
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-txt-muted">Evidence — {selected ? selected.code.replace(/_/g, " ") : "case"}</p>
          {!selected && <p className="text-[12.5px] text-txt-muted">No hypotheses.</p>}
          {selected?.evidence.map((e) => <EvidenceCard key={e.doc_key} e={e} />)}
          {selected && selected.evidence.length === 0 && (
            <p className="rounded border border-dashed border-line px-3 py-4 text-center text-[12px] text-txt-muted">
              No evidence engaged for this hypothesis — confidence is prior-only, no free floor.
            </p>
          )}
        </div>
      </div>
      {error && <ErrorState message={error} />}
    </div>
  );
}

export function Stat({ k, v, tone, note }: { k: string; v: string; tone?: "pass" | "warn" | "fail" | "info" | "gold"; note?: string }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-txt-muted">{k}</p>
      <p className={`num ${tone ? `text-${tone}` : "text-txt-secondary"}`}>{v}</p>
      {note && <p className="text-[10px] text-txt-muted/70">{note}</p>}
    </div>
  );
}

export function BriefCard({ invId }: { invId: string }) {
  const [brief, setBrief] = React.useState<Brief | null>(null);
  const [expanded, setExpanded] = React.useState(false);

  React.useEffect(() => {
    api.get<Brief>(`/investigations/${invId}/brief`)
      .then(setBrief)
      .catch(() => setBrief(null));
  }, [invId]);

  if (!brief) return null;

  return (
    <Card title="Investigation Brief" subtitle="Synthesized context">
      <div className={`space-y-2 text-[12.5px] text-txt-secondary ${expanded ? "" : "line-clamp-3"}`}>
        {Object.entries(brief.sections).map(([k, v]) => (
          <div key={k}>
            <p className="font-semibold text-txt-primary">{k}</p>
            <p>{v}</p>
          </div>
        ))}
      </div>
      <button onClick={() => setExpanded(!expanded)} className="mt-2 text-[11px] text-gold hover:underline">
        {expanded ? "Show less" : "Show more"}
      </button>
    </Card>
  );
}

export function EvidenceCard({ e }: { e: EvidenceLink }) {
  return (
    <div className="rounded border border-line bg-ink-900 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12.5px] font-medium text-txt-primary">{e.title}</span>
        <Chip tone={e.state === "SUPPORTING" ? "pass" : e.state === "CONTRADICTING" ? "fail" : "neutral"}>{e.state}</Chip>
        {e.data_classification && <Chip tone="warn">{e.data_classification}</Chip>}
      </div>
      <p className="mt-1 text-[11.5px] text-txt-secondary">{e.summary}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        <span className="num text-[10px] text-txt-muted">weight {e.weight.toFixed(2)}</span>
        <span className="num text-[10px] text-txt-muted">freshness {e.freshness?.toFixed(2) ?? "—"}</span>
        <span className="text-[10px] text-txt-muted">source {e.source ?? "—"}</span>
      </div>
    </div>
  );
}

export function Decomposition({ invId }: { invId: string }) {
  const [comps, setComps] = React.useState<DecompComponent[]>([]);
  React.useEffect(() => {
    api.get<{ components: DecompComponent[] }>(`/investigations/${invId}/decomposition`)
      .then((d) => setComps(d.components))
      .catch(() => setComps([]));
  }, [invId]);
  if (comps.length === 0) return <p className="text-[12.5px] text-txt-muted">No decomposition available.</p>;
  return (
    <div className="space-y-1.5">
      {comps.map((c, i) => (
        <div key={i} className="flex flex-wrap items-center justify-between gap-2 rounded border border-line bg-ink-950/50 px-3 py-1.5">
          <span className="text-[12.5px] text-txt-primary">{c.component}</span>
          <span className="num text-[12.5px] text-txt-secondary">{c.pct >= 0 ? "+" : ""}{c.pct.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}
