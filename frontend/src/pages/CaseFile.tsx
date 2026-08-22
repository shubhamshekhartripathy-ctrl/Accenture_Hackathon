/** KPI Case File — the product's central experience.
 * Sticky status header + persistent tabs (Contract · Reconcile · Investigation ·
 * Decisions · History). S1 wired Contract; S2 wires Reconcile + Investigation prefix. */
import React from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import { Chip, ErrorState, Skeleton, statusTone, Tabs } from "@/components/ui";
import { ContractTab } from "./CaseFileContract";
import { CaseFileReconcile } from "./CaseFileReconcile";
import { CaseFileInvestigation } from "./CaseFileInvestigation";
import { CaseFileDecisions } from "./CaseFileDecisions";
import { CaseFileHistory } from "./CaseFileHistory";
import type { QueueEntry } from "@/api/types";

interface KpiDetail {
  id: string;
  code: string;
  name: string;
  category: string;
  region: string;
  unit: string;
  description: string;
  active_contract_id: string | null;
  active_contract_version: number | null;
}

export interface ContractDetail {
  id: string;
  kpi_code: string;
  kpi_name: string;
  name: string;
  business_definition: string;
  formula_sql: string;
  formula_note: string;
  unit: string;
  business_function: string;
  owner_name: string;
  owner_role: string;
  status: string;
  calendar_rule: string;
  hierarchy_config: Record<string, unknown>;
  version: number;
  sources: {
    id: string;
    source_code: string;
    source_name: string;
    lineage_path: string;
    is_authoritative: boolean;
    expected_cadence: string;
    expected_grain: string;
    tolerance_pct: number;
    data_classification: string;
  }[];
  drivers: { id: string; driver_code: string; name: string; direction: number; prior_weight: number; hypothesis_class: string; rank: number }[];
  threshold: {
    expected_lo: number | null;
    expected_hi: number | null;
    warning_deviation_pct: number | null;
    critical_deviation_pct: number | null;
    exposure_rs_per_point: number;
    margin_weight: number;
    strategic_weight: number;
    min_history: number;
    cold_start_flag: boolean;
  } | null;
  rights: {
    id: string;
    role: string;
    action_class: string;
    may_recommend: boolean;
    may_simulate: boolean;
    may_approve: boolean;
    approve_limit_rs: number;
    escalate_to_role: string | null;
  }[];
  entitlements: { id: string; role: string; row_scope: Record<string, string[]>; masked_columns: string[]; domains: string[] }[];
  versions: { version: number; change_reason: string; created_at: string | null; status_in_snapshot: string | null }[];
}

export interface Gap {
  code: string;
  severity: string;
  effect: string;
  banner: string;
}

const TABS = [
  { key: "contract", label: "Contract" },
  { key: "reconcile", label: "Reconciliation" },
  { key: "investigation", label: "Investigation" },
  { key: "decisions", label: "Decisions", tag: "S7" },
  { key: "history", label: "History", tag: "S9" },
];

export function CaseFile() {
  const { kpiId } = useParams<{ kpiId: string }>();
  const [kpi, setKpi] = React.useState<KpiDetail | null>(null);
  const [contract, setContract] = React.useState<ContractDetail | null>(null);
  const [gaps, setGaps] = React.useState<Gap[]>([]);
  const [queueEntry, setQueueEntry] = React.useState<QueueEntry | null>(null);
  const [certainty, setCertainty] = React.useState<{ certainty_state: string | null; final_confidence: number | null; workflow_state: string; cold_start_mode: boolean } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState("contract");

  const load = React.useCallback(() => {
    if (!kpiId) return;
    setError(null);
    api
      .get<KpiDetail>(`/kpis/${kpiId}`)
      .then((k) => {
        setKpi(k);
        if (k.active_contract_id) {
          api.get<ContractDetail>(`/contracts/${k.active_contract_id}`).then(setContract).catch(() => setContract(null));
          api.get<{ gaps: Gap[] }>(`/contracts/${k.active_contract_id}/gaps`).then((g) => setGaps(g.gaps)).catch(() => setGaps([]));
        }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load KPI"));
    api
      .get<{ entries: QueueEntry[] }>("/queue")
      .then((d) => setQueueEntry(d.entries.find((e) => e.kpi_id === kpiId) ?? null))
      .catch(() => setQueueEntry(null));
    api.get<{ certainty_state: string | null; final_confidence: number | null; workflow_state: string; cold_start_mode: boolean }[]>(`/investigations?kpi_id=${kpiId}`)
      .then((rows) => setCertainty(rows[0] ?? null))
      .catch(() => setCertainty(null));
  }, [kpiId]);

  React.useEffect(() => {
    load();
    window.addEventListener("demo-refresh", load);
    return () => window.removeEventListener("demo-refresh", load);
  }, [load]);

  if (error) return <ErrorState message={error} retry={load} />;
  if (!kpi) return <Skeleton className="h-72" />;

  const blocking = gaps.filter((g) => g.severity === "BLOCKING");
  const coldStart = contract?.threshold?.cold_start_flag ?? false;

  return (
    <div className="space-y-4">
      {/* Sticky status header (§11A) */}
      <div className="sticky top-12 z-10 -mx-4 border-b border-line bg-ink-950/95 px-4 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <div>
            <h1 className="text-[16px] font-semibold tracking-wide">{kpi.name}</h1>
            <p className="text-[11.5px] text-txt-muted">
              {kpi.code} · {kpi.category} · Region {kpi.region}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[12px]">
            <Stat
              label="Current value"
              value={
                queueEntry ? (
                  <span className="num">
                    {queueEntry.current_value.toFixed(1)} {kpi.unit}
                    <span className={queueEntry.deviation_pct < 0 ? "text-fail" : "text-pass"}>
                      {" "}({queueEntry.deviation_pct.toFixed(1)}%)
                    </span>
                  </span>
                ) : (
                  <span className="text-txt-muted">queue refresh → detect</span>
                )
              }
            />
            <Stat
              label="Materiality"
              value={
                queueEntry ? (
                  <Chip tone={statusTone(queueEntry.band)}>{queueEntry.band}</Chip>
                ) : (
                  <span className="text-txt-muted">—</span>
                )
              }
            />
            <Stat
              label="Certainty"
              value={
                certainty?.certainty_state ? (
                  <span className="inline-flex items-center gap-1.5">
                    <Chip tone={certainty.certainty_state === "ABSTAIN" ? "fail" : certainty.certainty_state === "ACT" ? "pass" : certainty.certainty_state === "CLARIFY" ? "warn" : "info"}>
                      {certainty.certainty_state}
                    </Chip>
                    {certainty.final_confidence != null && (
                      <span className="num text-txt-secondary">{certainty.final_confidence.toFixed(2)}</span>
                    )}
                  </span>
                ) : (
                  <span className="text-txt-muted">—</span>
                )
              }
            />
            {queueEntry?.reliability != null && (
              <Stat label="Reliability" value={<span className="num">{queueEntry.reliability.toFixed(2)}</span>} />
            )}
            <Stat
              label="Contract"
              value={
                contract ? (
                  <span className="inline-flex items-center gap-1.5">
                    <Chip tone={statusTone(coldStart ? "COLD START" : contract.status)}>
                      {coldStart ? "COLD START" : contract.status}
                    </Chip>
                    <span className="num text-txt-secondary">v{contract.version}</span>
                  </span>
                ) : (
                  <Chip tone="fail">NONE</Chip>
                )
              }
            />
          </div>
        </div>
      </div>

      {blocking.length > 0 && (
        <div className="rounded border border-fail/40 bg-fail/5 px-3.5 py-2.5" role="note">
          <p className="mb-0.5 text-xs font-semibold uppercase tracking-wide text-fail">Blocking governance gaps — reasoning is gated</p>
          <ul className="list-disc space-y-0.5 pl-4 text-[13px] text-txt-secondary">
            {blocking.map((g) => (
              <li key={g.code}>
                <span className="font-medium">{g.code}</span> — {g.effect}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "contract" &&
        (contract ? (
          <ContractTab contract={contract} />
        ) : (
          <div className="rounded border border-fail/40 bg-fail/5 px-3.5 py-2.5 text-[13px] text-txt-secondary" role="note">
            This KPI has no governed contract. ReasonFlow refuses to reason without one (AC1).
          </div>
        ))}
      {tab === "reconcile" &&
        (contract ? <CaseFileReconcile contractId={contract.id} unit={kpi.unit} /> : <p className="text-[13px] text-txt-muted">Contract required first (AC1).</p>)}
      {tab === "investigation" && <CaseFileInvestigation kpiId={kpi.id} />}
      {tab === "decisions" && (
        <CaseFileDecisions kpiId={kpi.id} />
      )}
      {tab === "history" && (
        <CaseFileHistory kpiId={kpi.id} />
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-[11px] uppercase tracking-wide text-txt-muted">{label}</span>
      <span className="text-[13px]">{value}</span>
    </div>
  );
}

