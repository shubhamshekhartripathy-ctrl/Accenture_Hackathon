/** Minimal auth store — session in localStorage, React-friendly subscription. */

export interface SessionUser {
  id: string;
  email: string;
  full_name: string;
  role: "EXECUTIVE" | "ANALYST" | "SUPPLY_CHAIN" | "KPI_OWNER" | "ADMIN";
  job_title: string;
  region_scope: string[];
  organization: string;
  organization_id: string;
}

export interface Session {
  access_token: string;
  refresh_token: string;
  user: SessionUser;
}

const KEY = "rf.session";

type Listener = () => void;
const listeners = new Set<Listener>();

export function getSession(): Session | null {
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    localStorage.removeItem(KEY);
    return null;
  }
}

export function setSession(session: Session): void {
  localStorage.setItem(KEY, JSON.stringify(session));
  localStorage.setItem("rf.access_token", session.access_token);
  listeners.forEach((l) => l());
}

export function clearSession(): void {
  localStorage.removeItem(KEY);
  localStorage.removeItem("rf.access_token");
  listeners.forEach((l) => l());
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Demo personas offered by the DemoBar (demo mode only). */
export const DEMO_PERSONAS: { email: string; label: string; role: string }[] = [
  { email: "priya.ceo@apexfoods.example", label: "Priya Sharma", role: "EXECUTIVE" },
  { email: "rahul.sc@apexfoods.example", label: "Rahul Verma", role: "SUPPLY_CHAIN" },
  { email: "meera.analyst@apexfoods.example", label: "Meera Iyer", role: "ANALYST" },
  { email: "vikram.owner@apexfoods.example", label: "Vikram Rao", role: "KPI_OWNER" },
];

export const DEMO_PASSWORD = "ReasonFlow#2026";
