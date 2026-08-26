/** Scenario Selector — every card declares the SAME engine (AC18 made visible). */
import React from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import { getSession } from "@/auth/store";
import { Banner, Card, Chip, ErrorState, Skeleton } from "@/components/ui";

interface ScenarioCard {
  scenario_id: string;
  industry: string;
  business_problem: string;
  primary_kpi: string;
  related_kpis: string[];
  region: string;
  sources: string[];
  demo_priority: number;
  status: string;
  scenario_description: string;
  engine: string;
}

interface Workspace {
  scenario: ScenarioCard;
  engine: string;
  validation: { valid: boolean; gaps: { code: string; message: string }[] };
}

export function Scenarios() {
  const navigate = useNavigate();
  const [scenarios, setScenarios] = React.useState<ScenarioCard[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [starting, setStarting] = React.useState<string | null>(null);
  const [startError, setStartError] = React.useState<{ id: string; msg: string } | null>(null);
  const user = getSession()?.user;

  const load = React.useCallback(() => {
    setError(null);
    api
      .get<ScenarioCard[]>("/scenarios")
      .then(setScenarios)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load scenarios"));
  }, []);

  React.useEffect(load, [load]);

  const start = async (scenario: ScenarioCard) => {
    setStarting(scenario.scenario_id);
    setStartError(null);
    try {
      await api.post<Workspace>(`/scenarios/${scenario.scenario_id}/start`);
      const kpis = await api.get<{ id: string, code: string }[]>("/kpis");
      const kpi = kpis.find((k) => k.code === scenario.primary_kpi);
      if (!kpi) throw new Error("Primary KPI not found for scenario");
      
      await api.post("/investigations", { kpi_id: kpi.id });
      navigate(`/kpis/${kpi.id}`);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : (e as Error).message;
      setStartError({ id: scenario.scenario_id, msg });
    } finally {
      setStarting(null);
    }
  };

  const canStart = user && ["KPI_OWNER", "ANALYST", "EXECUTIVE", "SUPPLY_CHAIN", "ADMIN"].includes(user.role);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[17px] font-semibold tracking-wide">Scenarios</h1>
          <p className="mt-0.5 text-[13px] text-txt-secondary">
            One engine — <span className="text-gold">reasonflow-core</span> — configured for different business
            problems. A scenario changes data and configuration, never code paths.
          </p>
        </div>
        {!canStart && <Chip tone="warn" title="Only authenticated users can start scenarios">start: AUTHENTICATED</Chip>}
      </div>

      {error && <ErrorState message={error} retry={load} />}
      {!scenarios && !error && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      )}

      {scenarios && scenarios.length === 0 && (
        <Banner tone="info" title="No scenarios">
          No scenario templates are provisioned for your organization yet.
        </Banner>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {scenarios?.map((s) => (
          <Card
            key={s.scenario_id}
            title={s.business_problem}
            subtitle={`${s.industry} · Region ${s.region}`}
            actions={<Chip tone={s.demo_priority === 1 ? "gold" : "neutral"}>S{s.demo_priority} · {s.status}</Chip>}
            className="flex flex-col"
          >
            <div className="flex flex-1 flex-col gap-3">
              <p className="text-[12.5px] leading-relaxed text-txt-secondary">{s.scenario_description}</p>
              <div className="space-y-1.5 border-t border-line pt-2.5 text-xs">
                <Row k="Primary KPI" v={<span className="text-gold">{s.primary_kpi}</span>} />
                <Row k="Related" v={s.related_kpis.length ? s.related_kpis.join(" · ") : "—"} />
                <Row k="Sources" v={s.sources.join(" · ")} />
                <Row k="Engine" v={<span className="num text-txt-secondary">{s.engine}</span>} />
              </div>
              {startError?.id === s.scenario_id && (
                <p role="alert" className="rounded border border-fail/40 bg-fail/5 px-2 py-1.5 text-[11px] text-fail">
                  {startError.msg}
                </p>
              )}
              <button
                onClick={() => start(s)}
                disabled={!!starting || !canStart}
                className="mt-auto w-full rounded border border-gold/60 bg-gold-soft px-3 py-2 text-[13px] font-semibold text-gold transition hover:bg-gold/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {starting === s.scenario_id ? "Opening workspace…" : "Open Investigation"}
              </button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-txt-muted">{k}</span>
      <span className="text-right text-txt-primary">{v}</span>
    </div>
  );
}
