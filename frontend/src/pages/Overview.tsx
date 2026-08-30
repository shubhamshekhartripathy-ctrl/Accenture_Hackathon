/** Executive Overview — the materiality queue (landing beat) + portfolio health. */
import React from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import { getSession } from "@/auth/store";
import { Card, Chip, EmptyState, ErrorState, Skeleton, statusTone, TechnicalDetails } from "@/components/ui";
import { formatIdentifier } from "@/utils/formatters";
import type { QueueEntry } from "@/api/types";

const inr = (v: number | null) =>
  v == null ? "—" : v >= 1_000_000 ? `₹${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `₹${(v / 1_000).toFixed(0)}K` : `₹${v.toFixed(0)}`;

export function Overview() {
  const navigate = useNavigate();
  const [entries, setEntries] = React.useState<QueueEntry[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [refreshing, setRefreshing] = React.useState(false);
  const [expanded, setExpanded] = React.useState<string | null>(null);
  const user = getSession()?.user;
  const canRefresh = user && ["KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN"].includes(user.role);

  const load = React.useCallback(() => {
    setError(null);
    api
      .get<{ entries: QueueEntry[] }>("/queue")
      .then((d) => setEntries(d.entries))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load queue"));
  }, []);
  React.useEffect(() => {
    load();
    window.addEventListener("demo-refresh", load);
    return () => window.removeEventListener("demo-refresh", load);
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const d = await api.post<{ queue: QueueEntry[] }>("/queue/refresh");
      setEntries(d.queue);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const material = (entries ?? []).filter((e) => e.band !== "COLD START");
  const cold = (entries ?? []).filter((e) => e.band === "COLD START");

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[17px] font-semibold tracking-wide">Executive Overview</h1>
          <p className="mt-0.5 text-[13px] text-txt-secondary">
            Statistical significance × business impact — the attention queue, not a wall of charts.
          </p>
        </div>
        {canRefresh && (
          <button
            onClick={refresh}
            disabled={refreshing}
            className="rounded border border-gold/60 bg-gold-soft px-3 py-1.5 text-[12.5px] font-medium text-gold transition hover:bg-gold/20 disabled:opacity-50"
          >
            {refreshing ? "Running detect → triage…" : "Refresh queue"}
          </button>
        )}
      </div>

      {error && <ErrorState message={error} retry={load} />}
      {!entries && !error && <Skeleton className="h-64" />}
      {entries && entries.length === 0 && (
        <Card>
          <EmptyState title="No material movements — all KPIs within expected range">
            Run “Refresh queue” to execute the Detect → Triage stages over the seeded Apex Foods fabric.
          </EmptyState>
        </Card>
      )}

      {material.length > 0 && (
        <div className="space-y-2">
          {material.map((e, idx) => (
            <QueueCard
              key={e.kpi_id}
              entry={e}
              dominant={idx === 0 && e.band === "CRITICAL"}
              expanded={expanded === e.kpi_id}
              onToggle={() => setExpanded(expanded === e.kpi_id ? null : e.kpi_id)}
              onOpen={() => navigate(`/kpis/${e.kpi_id}`)}
            />
          ))}
        </div>
      )}

      {cold.length > 0 && (
        <Card title="Cold start — monitor-only" subtitle="Sparse history: no fabricated confidence">
          {cold.map((e) => (
            <button
              key={e.kpi_id}
              onClick={() => navigate(`/kpis/${e.kpi_id}`)}
              className="flex w-full items-center justify-between gap-3 rounded border border-line bg-ink-850 px-3 py-2 text-left transition hover:border-gold/40"
            >
              <span className="text-[13px] text-txt-primary">{formatIdentifier(e.kpi_name)}</span>
              <span className="flex items-center gap-2">
                <span className="num text-[12px] text-txt-muted">
                  {e.current_value.toFixed(2)} {e.unit} · wide CI [{e.ci[0].toFixed(1)}, {e.ci[1].toFixed(1)}]
                </span>
                <Chip tone="warn">COLD START</Chip>
              </span>
            </button>
          ))}
        </Card>
      )}
      <PortfolioCard />
    </div>
  );
}

interface Portfolio {
  active_decisions: { option_code: string; owner_role: string; expected_impact_rs: number;
    guardrail_status: string | null; collision_status: boolean; approval_status: string }[];
  combined_expected_benefit_rs: number;
  combined_benefit_range_rs: [number, number];
  unresolved_collisions: { severity: string; option_codes: string[]; affected_kpi: string }[];
  awaiting_approval: { option_code: string; requested_by: string }[];
  highest_cost_of_waiting: { level: string; note: string } | null;
  portfolio_health: { score: number; formula: string; inputs: Record<string, number> };
}

function PortfolioCard() {
  const [p, setP] = React.useState<Portfolio | null>(null);
  const load = React.useCallback(() => {
    api.get<Portfolio>("/decisions/portfolio")
      .then((d) => setP(Array.isArray((d as Portfolio)?.active_decisions) ? d : null))
      .catch(() => setP(null));
  }, []);
  
  React.useEffect(() => {
    load();
    window.addEventListener("demo-refresh", load);
    return () => window.removeEventListener("demo-refresh", load);
  }, [load]);
  if (!p) return null;
  return (
    <Card title="Decision portfolio" subtitle="Derived from stored decision artifacts only — never invented">
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 md:grid-cols-4">
        <Arith k="Active decisions" v={String(p.active_decisions.length)} />
        <Arith k="Combined benefit" v={`₹${(p.combined_expected_benefit_rs / 1e6).toFixed(1)}M`} 
               note={`range ₹${(p.combined_benefit_range_rs[0] / 1e6).toFixed(1)}–${(p.combined_benefit_range_rs[1] / 1e6).toFixed(1)}M (sum of bounds)`} />
        <Arith k="Unresolved collisions" v={String(p.unresolved_collisions.length)}
               note={p.unresolved_collisions.map((c) => `${c.severity}: ${c.option_codes.join("+")}`).join("; ") || "none"} />
        <Arith k="Health" v={p.portfolio_health.score.toFixed(2)} note={p.portfolio_health.formula} />
      </div>
      {p.awaiting_approval.length > 0 && (
        <p className="mt-2 text-[11.5px] text-warn">
          Awaiting approval: {p.awaiting_approval.map((a) => `${a.option_code} (${a.requested_by})`).join(" · ")}
        </p>
      )}
      {p.highest_cost_of_waiting && (
        <p className="mt-1 text-[11.5px] text-txt-muted">Highest cost of waiting: {p.highest_cost_of_waiting.level} — {String(p.highest_cost_of_waiting.note ?? "").slice(0, 120)}…</p>
      )}
    </Card>
  );
}

function QueueCard({
  entry, dominant, expanded, onToggle, onOpen,
}: {
  entry: QueueEntry;
  dominant: boolean;
  expanded: boolean;
  onToggle: () => void;
  onOpen: () => void;
}) {
  const a = (entry.arithmetic ?? {}) as Record<string, number | string | boolean>;
  return (
    <div
      className={`rounded-lg border bg-ink-900 shadow-card transition ${
        dominant ? "border-fail/50 ring-1 ring-fail/20" : "border-line"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <button onClick={onOpen} className="min-w-0 flex-1 text-left">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`truncate ${dominant ? "text-[15px]" : "text-[13.5px]"} font-semibold text-txt-primary`}>
              {formatIdentifier(entry.kpi_name)}
            </span>
            <Chip tone={statusTone(entry.band)}>{entry.band}</Chip>
            {entry.contract_status === "CONFLICTED" && <Chip tone="fail">INPUTS CONFLICT</Chip>}
            {entry.investigation_id && <Chip tone="info">{entry.workflow_state}</Chip>}
          </div>
          <p className="num mt-1 text-[12px] text-txt-muted">
            {entry.current_value.toFixed(1)} {entry.unit} vs expected baseline {entry.baseline.toFixed(1)} ·{" "}
            <span className={entry.deviation_pct < 0 ? "text-fail" : "text-pass"}>
              {entry.deviation_pct.toFixed(1)}% deviation
            </span>
            {entry.reliability != null && <> · reliability {entry.reliability.toFixed(2)}</>}
          </p>
        </button>
        <div className="flex items-center gap-5">
          {entry.exposure_rs != null && (
            <div className="text-right">
              <p className="text-[10.5px] uppercase tracking-wide text-txt-muted">Exposure</p>
              <p className="num text-[15px] font-semibold text-gold">{inr(entry.exposure_rs)}</p>
            </div>
          )}
          <button
            onClick={onToggle}
            className="rounded border border-line px-2 py-1 text-[11.5px] text-txt-secondary transition hover:border-gold/50 hover:text-gold"
          >
            Why {entry.band}?
          </button>
        </div>
      </div>
      {expanded && (
        <div className="border-t border-line bg-ink-950/60 px-4 py-3">
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-[12px] md:grid-cols-4">
            <Arith k="Deviation" v={`${entry.deviation_pct.toFixed(2)}%`} />
            <Arith k="Exposure" v={inr(Number(a.exposure_rs ?? 0))} />
            <Arith k="Exposure/pt" v={inr(Number(a.exposure_rs_per_point ?? 0))} />
            <Arith k="Significance" v={String(a.significance ?? "—")} />
          </div>
          
          {Boolean(a.floored) && (
            <p className="mt-2 text-[11.5px] text-warn">
              Governance policy elevated severity to "{String(a.floor_band)}" (Raw score: {String(a.raw_band)}).
            </p>
          )}

          <TechnicalDetails title="Technical Triage & Detection">
            <div className="space-y-1">
              <p>Method: {entry.detection_method} (v{entry.model_version})</p>
              <p>Statistical Deviation (robust_z): {entry.robust_z.toFixed(2)}σ</p>
              <p>Score Formula: {String(a.formula ?? "")}</p>
              <p>Significance Math: clamp((max(z,6a)−2)/4)</p>
              <div className="mt-2 grid grid-cols-2 gap-x-8 gap-y-1 md:grid-cols-4">
                <Arith k="Strategic wt" v={String(a.strategic_weight ?? "—")} />
                <Arith k="Margin wt" v={String(a.margin_weight ?? "—")} />
                <Arith k="Impact norm" v={String(a.impact_norm ?? "—")} note="clamp(log1p(impact)/10)" />
                <Arith k="Final Score" v={String(a.score ?? "—")} />
              </div>
            </div>
          </TechnicalDetails>
        </div>
      )}
    </div>
  );
}

function Arith({ k, v, note }: { k: string; v: string; note?: string }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-txt-muted">{k}</p>
      <p className="num text-txt-secondary">{v}</p>
      {note && <p className="text-[10px] text-txt-muted/70">{note}</p>}
    </div>
  );
}
