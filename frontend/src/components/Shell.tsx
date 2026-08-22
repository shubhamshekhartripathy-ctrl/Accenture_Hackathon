/** App shell: top navigation, identity, deterministic-mode state. */
import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { clearSession, getSession, subscribe, type SessionUser } from "@/auth/store";

const NAV: { to: string; label: string; tag?: string }[] = [
  { to: "/scenarios", label: "Scenarios" },
  { to: "/app", label: "Overview" },
  { to: "/kpis", label: "KPIs" },
  { to: "/transparency", label: "Ledger" },
  { to: "/memory", label: "Memory" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<SessionUser | null>(getSession()?.user ?? null);
  const navigate = useNavigate();

  // Persona switches from the DemoBar re-render the shell identity live.
  React.useEffect(
    () =>
      subscribe(() => {
        const session = getSession();
        setUser(session?.user ?? null);
      }),
    [],
  );

  const signOut = () => {
    clearSession();
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-ink-950/95 backdrop-blur">
        <div className="mx-auto flex h-12 w-full max-w-[1440px] items-center gap-6 px-4">
          <NavLink to="/scenarios" className="flex items-center gap-2">
            <span className="grid h-6 w-6 place-items-center rounded border border-gold/60 bg-gold-soft font-mono text-[11px] font-bold text-gold">
              R
            </span>
            <span className="text-[14px] font-semibold tracking-wide">ReasonFlow</span>
            <span className="hidden text-[11px] text-txt-muted md:inline">Governed KPI-to-Decision</span>
          </NavLink>
          <nav className="flex items-center gap-0.5" aria-label="Primary">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded px-2.5 py-1.5 text-[13px] transition ${
                    isActive ? "bg-ink-850 text-gold" : "text-txt-secondary hover:bg-ink-900 hover:text-txt-primary"
                  }`
                }
              >
                {item.label}
                {item.tag && <span className="ml-1 text-[10px] text-txt-muted">{item.tag}</span>}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden rounded border border-line bg-ink-900 px-2 py-1 text-[11px] text-txt-muted lg:inline">
              Deterministic Engine Active
            </span>
            {user && (
              <div className="flex items-center gap-2.5">
                <div className="text-right">
                  <p className="text-[12.5px] leading-tight text-txt-primary">{user.full_name}</p>
                  <p className="text-[11px] leading-tight text-txt-muted">{user.role}</p>
                </div>
                <button
                  onClick={signOut}
                  className="rounded border border-line px-2 py-1 text-[11px] text-txt-secondary transition hover:border-fail/50 hover:text-fail"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-5">{children}</main>
      {children && <div className="h-14" aria-hidden />}
    </div>
  );
}
