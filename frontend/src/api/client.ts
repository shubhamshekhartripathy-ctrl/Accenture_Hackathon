/**
 * Envelope-aware API client. Backend envelope: {data, meta:{request_id,timestamp}}
 * or {error:{code,message,details}, meta}. JWT attached from the auth store;
 * 401 clears the session and routes to /login.
 */
export interface ApiEnvelope<T> {
  data: T;
  meta: { request_id: string; timestamp: string };
}

export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

const BASE = "/api/v1";

function authHeader(): Record<string, string> {
  const token = localStorage.getItem("rf.access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, {
      method,
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal: undefined,
    });
  } catch {
    throw new ApiError("NETWORK", "Cannot reach the ReasonFlow API — is the backend running?", 0);
  }
  let payload: { data?: T; error?: { code: string; message: string; details?: unknown } } | null = null;
  try {
    payload = await resp.json();
  } catch {
    payload = null;
  }
  if (!resp.ok) {
    if (resp.status === 401) {
      localStorage.removeItem("rf.access_token");
      localStorage.removeItem("rf.user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }
    throw new ApiError(
      payload?.error?.code ?? `HTTP_${resp.status}`,
      payload?.error?.message ?? `Request failed (${resp.status})`,
      resp.status,
      payload?.error?.details,
    );
  }
  return (payload?.data ?? null) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
};
