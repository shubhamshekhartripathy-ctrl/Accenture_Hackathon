/** Contract tab — the governed definition, fully inspectable. */
import React from "react";
import { Card, Chip } from "@/components/ui";
import type { ContractDetail } from "./CaseFile";

const inr = (v: number) =>
  v >= 1_000_000 ? `₹${(v / 1_000_000).toFixed(2)}M` : v >= 1_000 ? `₹${(v / 1_000).toFixed(0)}K` : `₹${v}`;

export function ContractTab({ contract }: { contract: ContractDetail }) {
  const [showVersions, setShowVersions] = React.useState(false);
  const th = contract.threshold;

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card title="Definition" subtitle="Business meaning before mathematics">
        <p className="text-[13px] leading-relaxed text-txt-secondary">{contract.business_definition}</p>
        <div className="mt-3 space-y-1 rounded border border-line bg-ink-950 p-2.5">
          <p className="text-[11px] uppercase tracking-wide text-txt-muted">Formula (auditable SQL)</p>
          <code className="block break-alls whitespace-pre-wrap font-mono text-[11.5px] text-gold">
            {contract.formula_sql}
          </code>
          <p className="pt-1 text-[11.5px] text-txt-muted">{contract.formula_note}</p>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-[12.5px]">
          <Field k="Owner" v={`${contract.owner_name} (${contract.owner_role})`} />
          <Field k="Business function" v={contract.business_function} />
          <Field k="Unit" v={contract.unit} />
          <Field k="Calendar rule" v={contract.calendar_rule} />
        </div>
      </Card>

      <Card title="Sources & lineage" subtitle="Declared feeds, authority, and cadence heterogeneity">
        <div className="space-y-2">
          {contract.sources.map((s) => (
            <div key={s.id} className="rounded border border-line bg-ink-850 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[13px] font-medium text-txt-primary">{s.source_name}</span>
                {s.is_authoritative && <Chip tone="gold">authoritative</Chip>}
                <Chip tone={s.data_classification === "SENSITIVE" || s.data_classification === "RESTRICTED" ? "warn" : "neutral"}>
                  {s.data_classification}
                </Chip>
                <span className="ml-auto text-[11px] text-txt-muted">
                  {s.expected_cadence} · {s.expected_grain} · tol {s.tolerance_pct}%
                </span>
              </div>
              <code className="mt-1 block font-mono text-[11px] text-txt-muted">{s.lineage_path}</code>
            </div>
          ))}
          {contract.sources.length === 0 && (
            <p className="text-[12.5px] text-fail">No sources declared — NO_SOURCES is a blocking gap.</p>
          )}
        </div>
      </Card>

      <Card title="Drivers" subtitle="Ranked known drivers — they constrain the hypothesis space">
        <table className="w-full text-left text-[12.5px]">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-wide text-txt-muted">
              <th className="py-1 pr-3 font-medium">Driver</th>
              <th className="py-1 pr-3 font-medium">Class</th>
              <th className="py-1 pr-3 font-medium text-right">Direction</th>
              <th className="py-1 text-right font-medium">Prior</th>
            </tr>
          </thead>
          <tbody>
            {contract.drivers.map((d) => (
              <tr key={d.id} className="border-b border-line/50">
                <td className="py-1.5 pr-3 text-txt-primary">{d.name}</td>
                <td className="py-1.5 pr-3 text-[11px] text-txt-muted">{d.hypothesis_class}</td>
                <td className="num py-1.5 pr-3 text-right text-txt-secondary">
                  {d.direction < 0 ? "↓ pushes down" : "↑ pushes up"}
                </td>
                <td className="num py-1.5 text-right text-gold">{d.prior_weight.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {contract.drivers.length === 0 && (
          <p className="mt-2 text-[12.5px] text-warn">No drivers — hypothesis space shrinks; confidence capped.</p>
        )}
      </Card>

      <Card title="Thresholds & materiality rules" subtitle="Significance × business impact weights">
        {th ? (
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[12.5px]">
            <Field k="Expected range" v={th.expected_lo != null ? `${th.expected_lo} – ${th.expected_hi}` : "— (cold start)"} />
            <Field k="Warning / critical deviation" v={`${th.warning_deviation_pct ?? "—"}% / ${th.critical_deviation_pct ?? "—"}%`} />
            <Field k="Exposure per point" v={inr(th.exposure_rs_per_point)} />
            <Field k="Margin weight" v={th.margin_weight.toFixed(2)} />
            <Field k="Strategic weight" v={th.strategic_weight.toFixed(2)} />
            <Field k="Min history" v={`${th.min_history} periods`} />
            <Field k="Cold start" v={th.cold_start_flag ? "YES — monitor-only, cap 0.45" : "no"} />
          </div>
        ) : (
          <p className="text-[12.5px] text-warn">No thresholds — materiality degrades to statistical-only.</p>
        )}
      </Card>

      <Card title="Decision rights" subtitle="Who may recommend / simulate / approve, up to which limit">
        <table className="w-full text-left text-[12.5px]">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-wide text-txt-muted">
              <th className="py-1 pr-3 font-medium">Role</th>
              <th className="py-1 pr-3 font-medium">Action class</th>
              <th className="py-1 pr-3 font-medium">May</th>
              <th className="py-1 pr-3 font-medium text-right">Limit</th>
              <th className="py-1 text-right font-medium">Escalates</th>
            </tr>
          </thead>
          <tbody>
            {contract.rights.map((r) => (
              <tr key={r.id} className="border-b border-line/50">
                <td className="py-1.5 pr-3 text-txt-secondary">{r.role}</td>
                <td className="num py-1.5 pr-3 text-txt-primary">{r.action_class}</td>
                <td className="py-1.5 pr-3">
                  {r.may_recommend && <span className="mr-1"><Chip tone="neutral">recommend</Chip></span>}
                  {r.may_simulate && <Chip tone="neutral">simulate</Chip>}
                  {r.may_approve ? <Chip tone="pass">approve</Chip> : <span className="ml-1 text-txt-muted">—</span>}
                </td>
                <td className="num py-1.5 pr-3 text-right text-txt-secondary">
                  {r.may_approve ? inr(r.approve_limit_rs) : "—"}
                </td>
                <td className="py-1.5 text-right text-[11px] text-txt-muted">{r.escalate_to_role ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {contract.rights.length === 0 && (
          <p className="mt-2 text-[12.5px] text-warn">No rights defined — no action recommendations will be generated.</p>
        )}
      </Card>

      <Card
        title="Entitlements"
        subtitle="Server-enforced row / column / domain scopes per role"
        actions={
          <button
            onClick={() => setShowVersions((v) => !v)}
            className="rounded border border-line px-2 py-1 text-[11px] text-txt-secondary transition hover:border-gold/50 hover:text-gold"
          >
            {showVersions ? "Hide" : "Show"} versions ({contract.versions.length})
          </button>
        }
      >
        <div className="space-y-1.5">
          {contract.entitlements.map((e) => (
            <div key={e.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded border border-line bg-ink-850 px-3 py-1.5 text-[12px]">
              <span className="font-medium text-txt-primary">{e.role}</span>
              <span className="text-txt-muted">
                rows: <span className="num text-txt-secondary">{e.row_scope.region?.join(" · ") ?? "all"}</span>
              </span>
              <span className="text-txt-muted">
                masked: <span className="num text-fail">{e.masked_columns.join(", ") || "none"}</span>
              </span>
              <span className="text-txt-muted">
                domains: <span className="text-txt-secondary">{e.domains.join(", ") || "—"}</span>
              </span>
            </div>
          ))}
        </div>
        {showVersions && (
          <div className="mt-3 max-h-56 space-y-1 overflow-y-auto border-t border-line pt-2">
            {contract.versions.map((v) => (
              <div key={v.version} className="flex items-baseline justify-between gap-3 text-[12px]">
                <span className="num text-gold">v{v.version}</span>
                <span className="flex-1 truncate text-txt-secondary">{v.change_reason}</span>
                <span className="text-[11px] text-txt-muted">{v.created_at?.slice(0, 16).replace("T", " ")}</span>
                <Chip tone={v.status_in_snapshot === "ACTIVE" ? "pass" : "neutral"}>{v.status_in_snapshot ?? "—"}</Chip>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function Field({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line/50 py-1">
      <span className="text-[11px] text-txt-muted">{k}</span>
      <span className="num text-right text-txt-secondary">{v}</span>
    </div>
  );
}
