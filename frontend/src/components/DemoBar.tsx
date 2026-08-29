/**
 * DemoBar — demo-mode control strip (fixed bottom, audit-logged server-side).
 * S1: persona switcher (real re-auth), scenario switcher (real start).
 * Later slices wire Inject POS / Fast-forward / Toggle LLM / Reset (tags show slice).
 */
import React from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import { DEMO_PASSWORD, DEMO_PERSONAS, getSession, setSession, subscribe, type SessionUser } from "@/auth/store";

export function DemoBar() {
  const navigate = useNavigate();
  const [busy, setBusy] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  
  const triggerRefresh = () => {
    window.dispatchEvent(new Event("demo-refresh"));
  };
  const session = getSession();
  const [llmOn, setLlmOn] = React.useState(true);

  React.useEffect(() => subscribe(() => setNotice(null)), []);

  const switchPersona = async (email: string) => {
    setBusy(true);
    setNotice(null);
    try {
      const data = await api.post<{ access_token: string; refresh_token: string; user: SessionUser }>(
        "/auth/login",
        { email, password: DEMO_PASSWORD },
      );
      setSession({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        user: data.user,
      });
      setNotice(`Persona switched — ${data.user.full_name} (${data.user.role})`);
      window.location.reload();
    } catch (e) {
      setNotice(`Switch failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-ink-900/97 backdrop-blur">
      <div className="mx-auto flex h-11 w-full max-w-[1440px] items-center gap-2 px-4">
        <span className="rounded bg-gold-soft px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-gold">
          Demo
        </span>
        <span className="text-[11px] text-txt-muted">Persona</span>
        {DEMO_PERSONAS.map((p) => (
          <button
            key={p.email}
            disabled={busy}
            onClick={() => switchPersona(p.email)}
            className={`rounded border px-2 py-1 text-[11px] transition ${
              session?.user.email === p.email
                ? "border-gold/60 bg-gold-soft text-gold"
                : "border-line text-txt-secondary hover:border-gold/40 hover:text-txt-primary disabled:opacity-50"
            }`}
          >
            {p.role}
          </button>
        ))}
        <span className="mx-1 h-4 w-px bg-line" aria-hidden />
        <button
          disabled={busy}
          title="Refresh the POS feed — the next run sees fresher evidence (audited)"
          onClick={async () => {
            setBusy(true); setNotice(null);
            try {
              const out = await api.post<{ documents_refreshed: number }>("/demo/inject-pos");
              setNotice(`POS refreshed — ${out.documents_refreshed} documents, rerun shows fresher evidence`);
              triggerRefresh();
            } catch (e) { setNotice(`Inject failed: ${(e as Error).message}`); }
            finally { setBusy(false); }
          }}
          className="rounded border border-line px-2 py-1 text-[11px] text-txt-secondary transition hover:border-gold/40 hover:text-txt-primary disabled:opacity-40"
        >
          Inject POS refresh
        </button>
        <button
          disabled={busy}
          title="Advance the demo clock 14 days — freshness decays, monitoring windows advance (audited)"
          onClick={async () => {
            setBusy(true); setNotice(null);
            try {
              const out = await api.post<{ demo_now: string }>("/demo/fast-forward", { days: 14 });
              setNotice(`Fast-forwarded 14 days — demo now ${out.demo_now.slice(0, 10)}`);
              triggerRefresh();
            } catch (e) { setNotice(`Fast-forward failed: ${(e as Error).message}`); }
            finally { setBusy(false); }
          }}
          className="rounded border border-line px-2 py-1 text-[11px] text-txt-secondary transition hover:border-gold/40 hover:text-txt-primary disabled:opacity-40"
        >
          Fast-forward 14d
        </button>
        <button
          disabled={busy}
          title="Flip every model route to the deterministic fallback — visible in the Ledger"
          onClick={async () => {
            setBusy(true); setNotice(null);
            try {
              const out = await api.post<{ llm_enabled: boolean }>("/demo/toggle-llm", { enabled: !llmOn });
              setLlmOn(out.llm_enabled);
              setNotice(out.llm_enabled ? "LLM routes enabled" : "LLM OFF — deterministic fallback everywhere (audited)");
              triggerRefresh();
            } catch (e) { setNotice(`Toggle failed: ${(e as Error).message}`); }
            finally { setBusy(false); }
          }}
          className={`rounded border px-2 py-1 text-[11px] transition ${
            llmOn ? "border-line text-txt-secondary hover:border-gold/40" : "border-warn/60 bg-warn/10 text-warn"
          } hover:text-txt-primary disabled:opacity-40`}
        >
          Toggle LLM {llmOn ? "ON" : "OFF"}
        </button>
        <button
          disabled={busy}
          title="Wipe and reseed the demo data (audited) — reload to re-login"
          onClick={async () => {
            if (!window.confirm("Reset wipes and reseeds the demo database. Continue?")) return;
            setBusy(true); setNotice(null);
            try {
              await api.post("/demo/reset");
              setNotice("Demo reset — database reseeded; reloading…");
              window.setTimeout(() => window.location.assign("/login"), 1200);
            } catch (e) { setNotice(`Reset failed: ${(e as Error).message}`); }
            finally { setBusy(false); }
          }}
          className="rounded border border-fail/40 px-2 py-1 text-[11px] text-fail/90 transition hover:bg-fail/10 disabled:opacity-40"
        >
          Reset
        </button>
        {notice && <span className="ml-auto text-[11px] text-gold">{notice}</span>}
      </div>
    </div>
  );
}
