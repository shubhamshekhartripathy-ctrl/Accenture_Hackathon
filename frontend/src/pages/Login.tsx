/** Login — real authentication against the API, clear error states. */
import React from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import { DEMO_PASSWORD, DEMO_PERSONAS, setSession, type Session } from "@/auth/store";

export function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = React.useState("priya.ceo@apexfoods.example");
  const [password, setPassword] = React.useState(DEMO_PASSWORD);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const submit = async (e: React.FormEvent, overrideEmail?: string) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await api.post<Session>("/auth/login", {
        email: overrideEmail ?? email,
        password: overrideEmail ? DEMO_PASSWORD : password,
      });
      setSession(data);
      navigate("/scenarios");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center bg-ink-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded border border-gold/60 bg-gold-soft font-mono text-sm font-bold text-gold">
            R
          </span>
          <div>
            <h1 className="text-[15px] font-semibold tracking-wide">ReasonFlow</h1>
            <p className="text-[11.5px] text-txt-muted">Where KPI movements become governed decisions</p>
          </div>
        </div>

        <form onSubmit={submit} className="rounded-lg border border-line bg-ink-900 p-5 shadow-card">
          <label className="mb-1 block text-xs text-txt-secondary" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mb-3 w-full rounded border border-line bg-ink-950 px-2.5 py-2 text-[13px] text-txt-primary outline-none transition focus:border-gold/60"
            required
          />
          <label className="mb-1 block text-xs text-txt-secondary" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mb-4 w-full rounded border border-line bg-ink-950 px-2.5 py-2 text-[13px] text-txt-primary outline-none transition focus:border-gold/60"
            required
          />
          {error && (
            <p role="alert" className="mb-3 rounded border border-fail/40 bg-fail/5 px-2.5 py-2 text-xs text-fail">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-gold px-3 py-2 text-[13px] font-semibold text-txt-inverse transition hover:brightness-110 disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>

          <div className="mt-4 border-t border-line pt-3">
            <p className="mb-2 text-[11px] text-txt-muted">Demo personas (password {DEMO_PASSWORD}):</p>
            <div className="grid grid-cols-2 gap-1.5">
              {DEMO_PERSONAS.map((p) => (
                <button
                  key={p.email}
                  type="button"
                  disabled={busy}
                  onClick={(e) => submit(e, p.email)}
                  className="rounded border border-line px-2 py-1.5 text-left text-[11px] text-txt-secondary transition hover:border-gold/50 hover:text-gold disabled:opacity-50"
                >
                  <span className="block font-medium">{p.label}</span>
                  <span className="text-[10px] text-txt-muted">{p.role}</span>
                </button>
              ))}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
