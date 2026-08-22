/** Reconciliation tab — Moment 1: "Your inputs disagree." */
import React from "react";
import { api, ApiError } from "@/api/client";
import { getSession } from "@/auth/store";
import { Banner, Card, Chip, ErrorState, Skeleton } from "@/components/ui";

export interface ReconcileRun {
  id: string;
  period_key: string;
  verdict: string;
  reliability_score: number;
  confidence_cap: number;
  working_value: number;
  working_source: { id: string; code: string; name: string } | null;
  working_justification: string;
  penalties: Record<string, number>;
  freshness_profile: { source_code: string; age_days: number; expected_cadence: string; beyond_tolerance_days: number; discounted: boolean }[];
  run_ts: string | null;
  conflicts: {
    id: string;
    conflict_type: string;
    severity: string;
    source_a: { code: string; name: string } | null;
    source_b: { code: string; name: string } | null;
    value_a: number | null;
    value_b: number | null;
    unit: string;
    confidence_impact: number;
    penalty: number;
    explanation: string;
    routed_to: { id: string; name: string; role: string } | null;
    routed_role: string | null;
    resolution_state: string;
    resolution_note: string;
  }[];
}

export function CaseFileReconcile({ contractId, unit }: { contractId: string; unit: string }) {
  const [run, setRun] = React.useState<ReconcileRun | null>(null);
  const [missing, setMissing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [resolveNote, setResolveNote] = React.useState<Record<string, string>>({});
  const user = getSession()?.user;
  const canRun = user && ["ANALYST", "ADMIN"].includes(user.role);
  const canResolve = user && ["KPI_OWNER", "ADMIN"].includes(user.role);

  const load = React.useCallback(() => {
    setError(null);
    setMissing(false);
    api
      .get<ReconcileRun>(`/contracts/${contractId}/reconcile/latest`)
      .then(setRun)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setMissing(true);
        else setError(e.message);
      });
  }, [contractId]);

  React.useEffect(() => {
    load();
    window.addEventListener("demo-refresh", load);
    return () => window.removeEventListener("demo-refresh", load);
  }, [load]);

  const runReconcile = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await api.post<ReconcileRun>(`/contracts/${contractId}/reconcile`);
      setRun(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Reconciliation failed");
    } finally {
      setBusy(false);
    }
  };

  const resolve = async (conflictId: string) => {
    const note = (resolveNote[conflictId] ?? "").trim();
    if (!note) {
      setError("A resolution note is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = await api.post<ReconcileRun>(`/conflicts/${conflictId}/resolve`, { note });
      setRun(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Resolve failed");
    } finally {
      setBusy(false);
    }
  };

  if (error && !run) return <ErrorState message={error} retry={load} />;
  if (!run && !missing && !error) return <Skeleton className="h-64" />;
  if (missing) {
    return (
      <Card title="Reconciliation" subtitle="Reason about input reliability before reasoning about the business">
        <Banner tone="info" title="No reconciliation run yet">
          Run reconciliation to compare sources, type conflicts, and price input reliability into confidence.
        </Banner>
        {canRun && (
          <button
            onClick={runReconcile}
            disabled={busy}
            className="mt-3 rounded border border-gold/60 bg-gold-soft px-3 py-1.5 text-[12.5px] font-medium text-gold transition hover:bg-gold/20 disabled:opacity-50"
          >
            {busy ? "Reconciling…" : "Run reconciliation"}
          </button>
        )}
      </Card>
    );
  }

  const verdictTone = run!.verdict === "CONFLICTED" ? "fail" : run!.verdict === "MINOR" ? "warn" : "pass";

  return (
    <div className="space-y-4">
      {/* Verdict banner */}
      <div className={`rounded-lg border px-4 py-3 ${verdictTone === "fail" ? "border-fail/50 bg-fail/5" : verdictTone === "warn" ? "border-warn/40 bg-warn/5" : "border-pass/40 bg-pass/5"}`}>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <span className={`text-[15px] font-semibold ${verdictTone === "fail" ? "text-fail" : verdictTone === "warn" ? "text-warn" : "text-pass"}`}>
            {run!.verdict === "CONFLICTED" ? "Your inputs disagree." : run!.verdict}
          </span>
          <span className="num text-[12.5px] text-txt-secondary">
            reliability <span className="text-txt-primary">{run!.reliability_score.toFixed(2)}</span>
          </span>
          <span className="num text-[12.5px] text-txt-secondary">
            confidence cap <span className="text-gold">{run!.confidence_cap.toFixed(2)}</span>
          </span>
          <span className="num text-[12.5px] text-txt-muted">period {run!.period_key}</span>
          {canRun && (
            <button
              onClick={runReconcile}
              disabled={busy}
              className="ml-auto rounded border border-line px-2 py-1 text-[11.5px] text-txt-secondary transition hover:border-gold/50 hover:text-gold disabled:opacity-50"
            >
              {busy ? "…" : "Re-run"}
            </button>
          )}
        </div>
        {Object.keys(run!.penalties).length > 0 && (
          <p className="num mt-1.5 text-[11.5px] text-txt-muted">
            penalties: {Object.entries(run!.penalties).map(([k, v]) => `${k} −${v.toFixed(2)}`).join(" · ")}
          </p>
        )}
      </div>

      {/* Working value */}
      <Card title="Working value" subtitle="The justified number the pipeline reasons on — never a silent merge">
        <p className="num text-[18px] text-txt-primary">
          {run!.working_value.toFixed(1)} <span className="text-[12px] text-txt-muted">{unit}</span>
          {run!.working_source && <Chip tone="gold">{run!.working_source.code} · authoritative</Chip>}
        </p>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-txt-secondary">{run!.working_justification}</p>
      </Card>

      {/* Conflict cards */}
      <Card title={`Conflicts (${run!.conflicts.length})`} subtitle="Typed, priced in confidence, routed — never merged">
        {run!.conflicts.length === 0 ? (
          <p className="text-[12.5px] text-txt-muted">All declared sources agree within tolerance.</p>
        ) : (
          <div className="space-y-2.5">
            {run!.conflicts.map((c) => (
              <div key={c.id} className="rounded border border-line bg-ink-850 px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={c.conflict_type === "definition" ? "fail" : c.severity === "HIGH" ? "fail" : "warn"}>
                    {c.conflict_type}
                  </Chip>
                  <span className="text-[12px] text-txt-muted">{c.severity}</span>
                  {c.value_a != null && (
                    <span className="num ml-2 text-[13px]">
                      <span className="text-txt-primary">{c.source_a?.code} {c.value_a.toFixed(1)}</span>
                      <span className="text-txt-muted"> vs </span>
                      <span className={c.conflict_type === "definition" ? "text-fail" : "text-txt-primary"}>
                        {c.source_b?.code ?? "—"} {c.value_b?.toFixed(1) ?? "—"}
                      </span>{" "}
                      <span className="text-txt-muted">{c.unit}</span>
                    </span>
                  )}
                  <span className="num ml-auto text-[12px] text-fail">
                    confidence {c.confidence_impact.toFixed(2)}
                  </span>
                </div>
                <p className="mt-1.5 text-[12.5px] text-txt-secondary">{c.explanation}</p>
                <p className="mt-1 text-[11.5px] text-txt-muted">
                  routed to: {c.routed_to ? `${c.routed_to.name} (${c.routed_to.role})` : c.routed_role ?? "—"} · status{" "}
                  <span className={c.resolution_state === "RESOLVED" ? "text-pass" : "text-warn"}>{c.resolution_state}</span>
                </p>
                {c.resolution_state === "RESOLVED" && c.resolution_note && (
                  <p className="mt-1 rounded border border-pass/30 bg-pass/5 px-2 py-1 text-[11.5px] text-txt-secondary">
                    “{c.resolution_note}”
                  </p>
                )}
                {c.resolution_state === "OPEN" && canResolve && (
                  <div className="mt-2 flex gap-2">
                    <input
                      value={resolveNote[c.id] ?? ""}
                      onChange={(e) => setResolveNote({ ...resolveNote, [c.id]: e.target.value })}
                      placeholder="Resolution note (required) — e.g. accrual confirmed with finance"
                      className="min-w-0 flex-1 rounded border border-line bg-ink-950 px-2 py-1.5 text-[12px] outline-none focus:border-gold/60"
                    />
                    <button
                      onClick={() => resolve(c.id)}
                      disabled={busy}
                      className="rounded border border-pass/50 bg-pass/10 px-2.5 py-1 text-[11.5px] text-pass transition hover:bg-pass/20 disabled:opacity-50"
                    >
                      Resolve
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Freshness profile */}
      <Card title="Freshness profile" subtitle="Last refresh per source vs cadence; stale sources visibly discounted">
        <div className="space-y-1.5">
          {run!.freshness_profile.map((f) => (
            <div key={f.source_code} className="flex items-center gap-3 rounded border border-line bg-ink-850 px-3 py-1.5 text-[12.5px]">
              <span className="w-24 text-txt-primary">{f.source_code}</span>
              <span className="num text-txt-secondary">age {f.age_days >= 999 ? "no data" : `${f.age_days}d`}</span>
              <span className="text-txt-muted">cadence {f.expected_cadence}</span>
              <span className="ml-auto">
                {f.discounted ? (
                  <Chip tone="fail">discounted · {f.beyond_tolerance_days}d beyond</Chip>
                ) : (
                  <Chip tone="pass">current</Chip>
                )}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {error && <ErrorState message={error} />}
    </div>
  );
}
