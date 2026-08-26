import React from "react";
import { api, ApiError } from "@/api/client";
import { getSession } from "@/auth/store";
import { Card, Chip } from "@/components/ui";
import type { Investigation, SecondOrderEffect, Collision, DecisionOption } from "@/api/types";

export function CaseFileDecisions({ kpiId }: { kpiId: string }) {
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
      <OptionsPanel inv={inv} />
    </div>
  );
}

function OptionsPanel({ inv }: { inv: Investigation }) {
  const user = getSession()?.user;
  const [busy, setBusy] = React.useState<string | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [invState, setInvState] = React.useState(inv);
  React.useEffect(() => { setInvState(inv); }, [inv]);
  const options = invState.options ?? [];
  const collisions = (invState as Investigation & { collisions?: Collision[] }).collisions ?? [];
  const coll = collisions;
  if (options.length === 0 && invState.certainty_state === "ABSTAIN") return null;

  const decide = async (opt: DecisionOption, decision: string) => {
    setBusy(opt.id); setErr(null);
    let reason: string | null = null;
    if (decision === "OVERRIDE") {
      reason = window.prompt("Override requires a reason (it feeds the learning loop):") ?? "";
      if (reason.trim().length < 10) { setBusy(null); setErr("Override cancelled — a reason of at least 10 characters is required."); return; }
    }
    try {
      await api.post(`/investigations/${invState.id}/decisions/${opt.id}`, { decision, override_reason: reason });
      window.dispatchEvent(new Event("demo-refresh"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Decision failed");
    } finally { setBusy(null); }
  };

  if (options.length === 0) return null;
  return (
    <Card title="Decision options" subtitle="From the active scenario configuration · simulated deterministically · guardrail FAIL blocks approval">
      {coll.filter((c) => !c.resolved && (c.severity === "HIGH" || c.severity === "MEDIUM")).length > 0 && (
        <div className="mb-1 space-y-1.5">
          {coll.filter((c) => !c.resolved).map((c) => (
            <div key={c.id} className={`rounded-lg border px-3 py-2 ${c.severity === "HIGH" ? "border-fail/60 bg-fail/5" : "border-warn/40 bg-warn/5"}`}>
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={c.severity === "HIGH" ? "fail" : "warn"}>{c.severity === "HIGH" ? "DECISION COLLISION DETECTED" : "collision"}</Chip>
                <span className="num text-[12px] text-txt-secondary">{c.option_codes.join(" + ")}</span>
                <span className="text-[12px] text-txt-secondary">on <b className="text-txt-primary">{c.affected_kpi.replace(/_/g, " ")}</b></span>
                <span className={`num text-[12px] ${c.combined_effect_pct < 0 ? "text-fail" : "text-pass"}`}>combined {c.combined_effect_pct >= 0 ? "+" : ""}{c.combined_effect_pct.toFixed(0)}%</span>
                <span className="text-[11px] text-txt-muted">owners: {c.owners.map((o) => o.replace(/_/g, " ")).join(", ")}</span>
              </div>
              {c.combined_note && <p className="num mt-0.5 text-[11px] text-warn">{c.combined_note}</p>}
              {c.severity === "HIGH" && <p className="mt-0.5 text-[11px] text-fail/90">Approval blocked until resolved — humans resolve, the platform never auto-optimizes.</p>}
              {user && ["KPI_OWNER", "EXECUTIVE", "ADMIN"].includes(user.role) ? (
                <ResolveControls c={c} onDone={async () => { window.dispatchEvent(new Event("demo-refresh")); }} />
              ) : (
                <p className="mt-0.5 text-[10.5px] text-txt-muted">Resolution: {c.resolution_options.join(" · ")}</p>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="grid gap-2 xl:grid-cols-2">
        {options.map((o) => (
          <div key={o.id} className={`rounded-lg border px-3 py-2.5 ${o.guardrail_status === "PASS" ? "border-line" : o.guardrail_status === "NOT_SAFE" ? "border-fail/60 bg-fail/5" : "border-warn/50 bg-warn/5"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-semibold text-txt-primary">{o.code.split("_")[0]} · {o.lever.replace(/_/g, " ")}</span>
              <Chip tone={o.guardrail_status === "PASS" ? "pass" : "fail"}>{o.guardrail_status === "PASS" ? "guardrails PASS" : o.guardrail_status}</Chip>
              {o.rights_verdict && <Chip tone={o.rights_verdict === "AUTHORIZED" ? "pass" : "warn"}>{o.rights_verdict}</Chip>}
              {o.decision_health && <Chip tone={o.decision_health === "BETTER" ? "gold" : "fail"}>health {o.decision_health}</Chip>}
              {o.record && <Chip tone={o.record.status === "APPROVED" ? "pass" : "info"}>{o.record.status}</Chip>}
            </div>
            <p className="mt-1 text-[12px] text-txt-secondary">{o.action}</p>
            <div className="num mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-txt-secondary">
              <span>impact <b className="text-pass">+₹{(o.expected_impact_rs / 1e6).toFixed(1)}M</b> [{(o.impact_lo_rs / 1e6).toFixed(1)}–{(o.impact_hi_rs / 1e6).toFixed(1)}]</span>
              <span>cost <b className={o.cash_exposure_rs > 2_000_000 ? "text-fail" : "text-txt-primary"}>₹{(o.cash_exposure_rs / 1e6).toFixed(1)}M</b></span>
              <span>horizon {o.horizon_days}d</span>
              <span>owner {o.owner_role.replace(/_/g, " ")}</span>
            </div>
            {o.guardrail_status !== "PASS" && (
              <ul className="mt-1.5 space-y-0.5 border-l-2 border-fail/40 pl-2">
                {o.guardrail_reasons.filter((r) => /FAIL|UNKNOWN/.test(r)).slice(0, 3).map((r, i) => (
                  <li key={i} className="text-[11px] text-fail/90">{r}</li>
                ))}
              </ul>
            )}
            {o.decision_health === "BETTER" && o.comparable_to === null && (
              <p className="mt-1 text-[11px] text-gold">Phased variant — same goal, guardrails intact. Compare with the base option.</p>
            )}
            {o.simulation?.second_order && o.simulation.second_order.effects.length > 0 && (
              <SecondOrderChain effects={o.simulation.second_order.effects} rule={o.simulation.second_order.rule} />
            )}
            {["APPROVED", "OVERRIDDEN", "MONITORING"].includes(o.record?.status ?? "") && (
              <OutcomeControls inv={invState} opt={o} canRecord={!!user && user.role !== "ANALYST"} />
            )}
            {o.record?.status ? (
              <p className="num mt-1.5 border-t border-line pt-1 text-[11px] text-txt-muted">
                {o.record.status} by {o.record.approved_by_role} · monitoring {String((o.record.monitoring_plan as Record<string, unknown>)?.metric ?? "—")} weekly, band [{String((o.record.monitoring_plan as Record<string, unknown>)?.success_band ?? "")}]
                {o.record.override_reason ? ` · override: ${o.record.override_reason}` : ""}
              </p>
            ) : (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {o.guardrail_status === "PASS" && user && ["SUPPLY_CHAIN", "EXECUTIVE", "KPI_OWNER", "MARKETING"].includes(user.role) && (
                  <button disabled={busy === o.id} onClick={() => decide(o, "APPROVE")}
                    className="rounded border border-pass/50 bg-pass/10 px-2.5 py-1 text-[11.5px] font-medium text-pass hover:bg-pass/20 disabled:opacity-50">Approve</button>
                )}
                {o.guardrail_status !== "PASS" && o.escalation_target && (
                  <span className="rounded border border-warn/40 px-2 py-1 text-[11px] text-warn">Blocked — escalate to {o.escalation_target.replace(/_/g, " ")}</span>
                )}
                <button disabled={busy === o.id} onClick={() => decide(o, "REJECT")}
                  className="rounded border border-line px-2.5 py-1 text-[11.5px] text-txt-secondary hover:border-fail/40 hover:text-fail disabled:opacity-50">Reject</button>
                {o.guardrail_status === "PASS" && user?.role === "EXECUTIVE" && (
                  <button disabled={busy === o.id} onClick={() => decide(o, "OVERRIDE")}
                    className="rounded border border-gold/40 px-2.5 py-1 text-[11.5px] text-gold hover:bg-gold/10 disabled:opacity-50">Override w/ reason</button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      {err && <p className="mt-2 text-[12px] text-fail">{err}</p>}
    </Card>
  );
}

function OutcomeControls({ inv, opt, canRecord }: { inv: Investigation; opt: DecisionOption; canRecord: boolean }) {
  const rec = opt.record;
  const [actual, setActual] = React.useState("");
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const [effect, setEffect] = React.useState<Record<string, unknown> | null>(null);
  const close = async () => {
    setBusy(true); setErr(null);
    try { await api.post(`/memory/investigations/${inv.id}/close`, {}); window.dispatchEvent(new Event("demo-refresh")); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Close failed"); }
    finally { setBusy(false); }
  };
  if (rec?.actual_impact_rs != null) {
    return (
      <div className="mt-1.5 rounded border border-pass/30 bg-pass/5 px-2 py-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone={rec.within_band ? "pass" : "fail"}>{rec.within_band ? "OUTCOME WITHIN BAND" : "OUTCOME OUTSIDE BAND"}</Chip>
          <span className="num text-[11.5px] text-txt-secondary">
            predicted ₹{(opt.expected_impact_rs! / 1e6).toFixed(1)}M · actual ₹{(rec.actual_impact_rs / 1e6).toFixed(1)}M · variance ₹{((rec.outcome_variance ?? 0) / 1e6).toFixed(1)}M
          </span>
        </div>
        {rec.outcome_note && <p className="mt-0.5 text-[10.5px] text-txt-muted">{rec.outcome_note}</p>}
        {inv.workflow_state === "OUTCOME_RECORDED" && canRecord && (
          <button disabled={busy} onClick={close} className="mt-1 rounded border border-gold/50 px-2 py-0.5 text-[10.5px] text-gold hover:bg-gold/10 disabled:opacity-50">
            Close case → LEARNED (feeds institutional memory)
          </button>
        )}
        {err && <p className="text-[10.5px] text-fail">{err}</p>}
      </div>
    );
  }
  if (!canRecord) return null;
  return (
    <div className="mt-1.5 space-y-1 border-t border-line pt-1.5">
      <div className="flex flex-wrap gap-1.5">
        <input value={actual} onChange={(e) => setActual(e.target.value)} placeholder="actual impact ₹ (e.g. 3900000)"
          className="num w-44 rounded border border-line bg-ink-950 px-2 py-1 text-[11px] text-txt-primary placeholder:text-txt-muted/60" />
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="outcome note (≥10 chars, feeds learning)"
          className="flex-1 rounded border border-line bg-ink-950 px-2 py-1 text-[11px] text-txt-primary placeholder:text-txt-muted/60" />
        <button disabled={busy || !actual || note.trim().length < 10} onClick={async () => {
          setBusy(true); setErr(null);
          try {
            const r = await api.post<Record<string, unknown>>(`/decisions/${opt.id}/outcome`,
              { actual_impact_rs: Number(actual), note });
            setEffect(r); window.dispatchEvent(new Event("demo-refresh"));
          } catch (e) { setErr(e instanceof ApiError ? e.message : "Outcome failed"); }
          finally { setBusy(false); }
        }} className="rounded border border-pass/50 px-2 py-1 text-[10.5px] text-pass hover:bg-pass/10 disabled:opacity-40">
          Record outcome
        </button>
      </div>
      {err && <p className="text-[10.5px] text-fail">{err}</p>}
      {effect && (
        <p className="num text-[10.5px] text-pass">
          variance ₹{((effect.variance_rs as number) / 1e6).toFixed(1)}M · {effect.within_band ? "within band" : "outside band"}
          {effect.reliability ? ` · prior ${(effect.reliability as Record<string, unknown>).new_prior} (${(effect.reliability as Record<string, unknown>).pattern_class})` : ""}
        </p>
      )}
    </div>
  );
}

function SecondOrderChain({ effects, rule }: { effects: SecondOrderEffect[]; rule: string }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="mt-1.5 border-t border-line pt-1.5">
      <button onClick={() => setOpen(!open)} className="text-[11px] font-medium text-gold/90 hover:text-gold">
        {open ? "▾" : "▸"} Second-order impacts · graph_elasticity ({effects.length} downstream)
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          <p className="text-[10px] text-txt-muted">{rule} — bounds widen per hop</p>
          {effects.map((e, i) => (
            <div key={i} className="rounded border border-line bg-ink-950/60 px-2 py-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className={`num text-[11.5px] ${e.effect_pct >= 0 ? "text-pass" : "text-fail"}`}>{e.effect_display}</span>
                <span className="text-[11.5px] text-txt-secondary">{e.kpi.replace(/_/g, " ")}</span>
                {e.node_kind === "DERIVED_IMPACT" && <Chip tone="neutral">derived</Chip>}
                <span className="num text-[10px] text-txt-muted">conf {e.confidence.toFixed(2)} · [{e.bounds_pct[0].toFixed(1)}, {e.bounds_pct[1].toFixed(1)}]</span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-1">
                {e.dependency_path.map((n, j) => (
                  <React.Fragment key={j}>
                    {j > 0 && <span className="text-[9px] text-gold/70">→</span>}
                    <span className="rounded border border-line px-1 py-px font-mono text-[9.5px] text-txt-muted">{n}</span>
                  </React.Fragment>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ResolveControls({ c, onDone }: { c: Collision; onDone: () => Promise<void> }) {
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const resolve = async (resolution: string) => {
    setBusy(true); setErr(null);
    try {
      await api.post(`/decisions/collisions/${c.id}/resolve`, { resolution, note });
      await onDone();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Resolution failed");
    } finally { setBusy(false); }
  };
  if (c.resolved) {
    return <p className="num mt-1 text-[10.5px] text-pass">resolved ({c.resolution}) — {c.resolution_note}</p>;
  }
  return (
    <div className="mt-1.5 space-y-1">
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="resolution note (required, feeds the audit trail)"
        className="w-full rounded border border-line bg-ink-950 px-2 py-1 text-[11px] text-txt-primary placeholder:text-txt-muted/60" />
      <div className="flex flex-wrap gap-1.5">
        {c.resolution_options.map((r, i) => {
          const kind = ["SEQUENCE", "ESCALATE_COMBINED", "ABANDON_ONE"][i];
          return (
            <button key={kind} disabled={busy || note.trim().length < 10} onClick={() => resolve(kind)} title={r}
              className="rounded border border-gold/40 px-2 py-0.5 text-[10.5px] text-gold hover:bg-gold/10 disabled:opacity-40">
              {kind.replace(/_/g, " ")}
            </button>
          );
        })}
      </div>
      {err && <p className="text-[10.5px] text-fail">{err}</p>}
    </div>
  );
}