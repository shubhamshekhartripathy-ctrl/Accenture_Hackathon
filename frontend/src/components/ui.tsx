/** Shared UI primitives — interaction language of the decision-OS (§10A). */
import React from "react";

export function Chip({
  tone = "neutral",
  children,
  title,
}: {
  tone?: "neutral" | "pass" | "warn" | "fail" | "gold" | "info";
  children: React.ReactNode;
  title?: string;
}) {
  const tones: Record<string, string> = {
    neutral: "border-line text-txt-secondary bg-ink-850",
    pass: "border-pass/40 text-pass bg-pass/10",
    warn: "border-warn/40 text-warn bg-warn/10",
    fail: "border-fail/40 text-fail bg-fail/10",
    gold: "border-gold/50 text-gold bg-gold-soft",
    info: "border-info/40 text-info bg-info/10",
  };
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function statusTone(status: string): "pass" | "warn" | "fail" | "gold" | "neutral" | "info" {
  switch (status) {
    case "ACTIVE":
    case "PASS":
    case "AUTHORIZED":
    case "APPROVED":
      return "pass";
    case "CONFLICTED":
    case "FAIL":
    case "BLOCKED":
    case "REJECTED":
      return "fail";
    case "UNDER_REVIEW":
    case "WARNING":
    case "ESCALATE":
    case "DRAFT":
    case "COLD START":
      return "warn";
    case "CRITICAL":
      return "fail";
    default:
      return "neutral";
  }
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-line bg-ink-900 shadow-card ${className}`}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-2.5">
          <div>
            {title && <h2 className="text-[13px] font-semibold tracking-wide text-txt-primary">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-txt-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="px-4 py-3">{children}</div>
    </section>
  );
}

export function Banner({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warn" | "fail" | "pass" | "gold";
  title?: string;
  children: React.ReactNode;
}) {
  const tones: Record<string, string> = {
    info: "border-info/40 bg-info/5",
    warn: "border-warn/40 bg-warn/5",
    fail: "border-fail/40 bg-fail/5",
    pass: "border-pass/40 bg-pass/5",
    gold: "border-gold/40 bg-gold-soft",
  };
  const titleTone: Record<string, string> = {
    info: "text-info",
    warn: "text-warn",
    fail: "text-fail",
    pass: "text-pass",
    gold: "text-gold",
  };
  return (
    <div className={`rounded border px-3.5 py-2.5 ${tones[tone]}`} role="note">
      {title && <p className={`mb-0.5 text-xs font-semibold uppercase tracking-wide ${titleTone[tone]}`}>{title}</p>}
      <div className="text-[13px] text-txt-secondary">{children}</div>
    </div>
  );
}

export function KeyValue({ items }: { items: { k: string; v: React.ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
      {items.map((it) => (
        <div key={it.k} className="flex items-baseline justify-between gap-3 border-b border-line/50 py-1">
          <dt className="text-xs text-txt-muted">{it.k}</dt>
          <dd className="num text-right text-[13px] text-txt-primary">{it.v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-ink-800 ${className}`} />;
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="rounded border border-fail/40 bg-fail/5 px-4 py-3" role="alert">
      <p className="text-[13px] font-medium text-fail">Something failed</p>
      <p className="mt-1 text-[13px] text-txt-secondary">{message}</p>
      {retry && (
        <button
          onClick={retry}
          className="mt-2 rounded border border-line-strong px-2.5 py-1 text-xs text-txt-secondary transition hover:border-gold/60 hover:text-gold"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="rounded border border-dashed border-line-strong px-4 py-6 text-center">
      <p className="text-[13px] font-medium text-txt-secondary">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-md text-xs text-txt-muted">{children}</p>}
    </div>
  );
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; disabled?: boolean; tag?: string }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div role="tablist" className="flex flex-wrap items-center gap-1 border-b border-line" aria-label="Case file tabs">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          disabled={t.disabled}
          onClick={() => onChange(t.key)}
          className={`-mb-px rounded-t border-b-2 px-3.5 py-2 text-[13px] transition ${
            active === t.key
              ? "border-gold text-gold"
              : t.disabled
                ? "cursor-not-allowed border-transparent text-txt-muted/50"
                : "border-transparent text-txt-secondary hover:text-txt-primary"
          }`}
        >
          {t.label}
          {t.tag && <span className="ml-1.5 rounded bg-ink-800 px-1 py-px text-[10px] text-txt-muted">{t.tag}</span>}
        </button>
      ))}
    </div>
  );
}
