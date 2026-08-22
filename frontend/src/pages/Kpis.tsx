/** KPI Intelligence — the contract portfolio with status chips. */
import React from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import { Card, Chip, EmptyState, ErrorState, Skeleton, statusTone } from "@/components/ui";
import type { KpiRow } from "@/api/types";

export function Kpis() {
  const navigate = useNavigate();
  const [kpis, setKpis] = React.useState<KpiRow[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    setError(null);
    api
      .get<KpiRow[]>("/kpis")
      .then(setKpis)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load KPIs"));
  }, []);
  React.useEffect(load, [load]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[17px] font-semibold tracking-wide">KPI Intelligence</h1>
        <p className="mt-0.5 text-[13px] text-txt-secondary">
          Every KPI is a governed object — definition, sources, drivers, thresholds, rights — before it is a
          number on a chart.
        </p>
      </div>
      {error && <ErrorState message={error} retry={load} />}
      {!kpis && !error && <Skeleton className="h-56" />}
      {kpis && kpis.length === 0 && (
        <Card>
          <EmptyState title="No KPIs in your scope">
            Start a scenario from the Scenario Selector to provision the governed KPI workspace.
          </EmptyState>
        </Card>
      )}
      {kpis && kpis.length > 0 && (
        <Card title={`Governed KPIs (${kpis.length})`}>
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wide text-txt-muted">
                <th className="py-1.5 pr-3 font-medium">KPI</th>
                <th className="py-1.5 pr-3 font-medium">Category</th>
                <th className="py-1.5 pr-3 font-medium">Region</th>
                <th className="py-1.5 pr-3 font-medium">Unit</th>
                <th className="py-1.5 pr-3 font-medium">Contract</th>
                <th className="py-1.5 pr-3 font-medium">Status</th>
                <th className="py-1.5 text-right font-medium">Version</th>
              </tr>
            </thead>
            <tbody>
              {kpis.map((k) => (
                <tr
                  key={k.id}
                  onClick={() => navigate(`/kpis/${k.id}`)}
                  className="cursor-pointer border-b border-line/50 transition hover:bg-ink-850"
                >
                  <td className="py-2 pr-3">
                    <span className="text-txt-primary">{k.name}</span>
                  </td>
                  <td className="py-2 pr-3 text-[12px] text-txt-muted">{k.category}</td>
                  <td className="py-2 pr-3 text-txt-secondary">{k.region}</td>
                  <td className="num py-2 pr-3 text-txt-secondary">{k.unit}</td>
                  <td className="py-2 pr-3 text-[12px] text-txt-secondary">{k.contract?.name ?? "—"}</td>
                  <td className="py-2 pr-3">
                    {k.contract ? (
                      <Chip tone={statusTone(k.contract.chip)}>{k.contract.chip}</Chip>
                    ) : (
                      <Chip tone="fail">NO CONTRACT</Chip>
                    )}
                  </td>
                  <td className="num py-2 text-right text-txt-secondary">
                    {k.contract ? `v${k.contract.version}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
