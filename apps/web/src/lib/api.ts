// Thin fetch wrapper around the real FastAPI backend in apps/api/main.py. Every function here maps
// 1:1 to an actual route in that file (including the STEP 12 additions this session: /patients,
// /devices, /caregivers, /analytics/summary, /system/health, /notes/analyze, /simulator/*,
// /scenarios, /reports/{id}). Nothing in this file invents data — every method returns exactly what
// the backend responds with, or throws.

const BASE = (import.meta as any).env?.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function token(): string | null {
  return localStorage.getItem("wz_token");
}

export function setToken(t: string | null) {
  if (t) localStorage.setItem("wz_token", t);
  else localStorage.removeItem("wz_token");
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(opts.headers as any) };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...opts, headers });
  } catch (e) {
    throw new ApiError(0, "network_unreachable");
  }
  if (res.status === 204) return undefined as unknown as T;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json().catch(() => null) : await res.text();
  if (!res.ok) {
    const detail = (body && (body as any).detail) || (typeof body === "string" ? body : res.statusText);
    throw new ApiError(res.status, detail || `request_failed_${res.status}`);
  }
  return body as T;
}

// -------------------------------------------------------------- auth (POST /auth/signup, /auth/signin)
export interface AuthResponse { access_token: string; token_type: string }
export const authApi = {
  signUp: (body: { full_name: string; email: string; password: string; role: string }) =>
    request<AuthResponse>("/auth/signup", { method: "POST", body: JSON.stringify(body) }),
  signIn: (body: { email: string; password: string }) =>
    request<AuthResponse>("/auth/signin", { method: "POST", body: JSON.stringify(body) }),
  me: () => request<{ id: string; email: string; role: string }>("/auth/me"),
};

// -------------------------------------------------------------- patients (GET /patients, /patients/{id})
export interface PatientProfile {
  hypertension: boolean; diabetes: boolean; cardiac: boolean; copd: boolean; post_surgery: boolean;
  preferred_language: string; notes: string;
}
export interface PatientSummary {
  id: string; full_name: string; age: number; is_synthetic_demo: boolean; conditions: string[];
  profile: PatientProfile; risk_level: string; risk_probability: number | null;
  latest_reading: Record<string, any> | null; active_alert_count: number; connectivity: string;
  simulation_running: boolean;
}
export const patientsApi = {
  list: () => request<PatientSummary[]>("/patients"),
  get: (id: string) => request<PatientSummary>(`/patients/${id}`),
  timeline: (id: string) => request<any[]>(`/patients/${id}/timeline`),
  notes: (id: string) => request<any[]>(`/patients/${id}/notes`),
  // GET /patients/{id}/readings — added this pass (apps/api/main.py:patient_readings). Real stored
  // reading history from the repository, not just whatever arrived over the WebSocket in this tab's
  // lifetime. Still process-local/in-memory on the backend (see repository.py), so it resets on API
  // restart — it is not yet a persisted database. See docs/limitations.md.
  readings: (id: string, limit = 200) => request<{ patient_id: string; readings: any[] }>(`/patients/${id}/readings?limit=${limit}`),
};

// -------------------------------------------------------------- devices (GET /devices)
export interface Device {
  id: string; patient_id: string; device_type: string; location: string; is_simulated: boolean;
  connectivity: string; battery_pct: number | null; recent_events: any[];
  // Device-registry fields (PROMPT 4 section 5), served by GET /devices. Optional so the UI degrades
  // honestly if a backend omits them rather than rendering "undefined".
  // connection_status distinguishes "real_hardware" | "simulated" | "offline" | "unknown". In this
  // build is_simulated is always true, so "real_hardware" is never actually returned.
  connection_status?: "real_hardware" | "simulated" | "offline" | "unknown";
  last_seen?: string | null; manufacturer?: string | null; device_model?: string | null;
  firmware_version?: string | null; protocol?: string | null; registered_at?: string | null;
}
export const devicesApi = {
  list: (patientId?: string) => request<Device[]>(`/devices${patientId ? `?patient_id=${patientId}` : ""}`),
};

// -------------------------------------------------------------- alerts (GET/POST /alerts/...)
export const alertsApi = {
  list: (openOnly = true, patientId?: string) => {
    const q = new URLSearchParams({ open_only: String(openOnly) });
    if (patientId) q.set("patient_id", patientId);
    return request<any[]>(`/alerts?${q.toString()}`);
  },
  acknowledge: (id: number) => request<any>(`/alerts/${id}/acknowledge`, { method: "POST" }),
  dismiss: (id: number, reason: string) =>
    request<any>(`/alerts/${id}/dismiss`, { method: "POST", body: JSON.stringify({ reason }) }),
  escalate: (id: number) => request<any>(`/alerts/${id}/escalate`, { method: "POST" }),
  respond: (id: number, note?: string) =>
    request<any>(`/alerts/${id}/respond`, { method: "POST", body: JSON.stringify({ note }) }),
  resolve: (id: number, note?: string) =>
    request<any>(`/alerts/${id}/resolve`, { method: "POST", body: JSON.stringify({ note }) }),
  addNote: (id: number, note: string) =>
    request<any>(`/alerts/${id}/note`, { method: "POST", body: JSON.stringify({ note }) }),
};

// -------------------------------------------------------------- caregivers (GET /caregivers)
export const caregiversApi = {
  list: () => request<any[]>("/caregivers"),
};

// -------------------------------------------------------------- analytics / system (STEP 12)
export const analyticsApi = {
  summary: () => request<any>("/analytics/summary"),
};
export const systemApi = {
  health: () => request<any>("/system/health"),
};

// -------------------------------------------------------------- caregiver notes / NLP (STEP 12)
export const notesApi = {
  analyze: (patient_id: string, text: string, language?: string) =>
    request<any>("/notes/analyze", { method: "POST", body: JSON.stringify({ patient_id, text, language }) }),
};

// -------------------------------------------------------------- simulator (STEP 12)
export interface SimStatus {
  patient_id: string; device_id?: string; scenario?: string; speed?: number;
  status: "running" | "paused" | "stopped"; tick_count?: number; recent_events?: any[];
}
export const simulatorApi = {
  scenarios: () => request<{ name: string; description: string }[]>("/scenarios"),
  start: (patientId: string, scenario: string, speed: number, custom?: any) =>
    request<SimStatus>(`/simulator/${patientId}/start`, { method: "POST", body: JSON.stringify({ scenario, speed, custom }) }),
  pause: (patientId: string) => request<SimStatus>(`/simulator/${patientId}/pause`, { method: "POST" }),
  stop: (patientId: string) => request<SimStatus>(`/simulator/${patientId}/stop`, { method: "POST" }),
  reset: (patientId: string, scenario: string, speed: number, custom?: any) =>
    request<SimStatus>(`/simulator/${patientId}/reset`, { method: "POST", body: JSON.stringify({ scenario, speed, custom }) }),
  statusAll: () => request<SimStatus[]>("/simulator/status"),
  statusOne: (patientId: string) => request<SimStatus>(`/simulator/${patientId}/status`),
};

// -------------------------------------------------------------- reports (STEP 12; PDF added this pass)
export const reportsApi = {
  get: (patientId: string) => request<any>(`/reports/${patientId}`),
  // GET /reports/{id}/pdf returns a real application/pdf body (apps/api/reports_pdf.py, rendered with
  // reportlab from the same data reportsApi.get() returns) — not JSON, so this bypasses request<T>'s
  // JSON/text handling and fetches+downloads the blob directly. Throws ApiError on failure so callers
  // can handle it the same way as every other method here.
  downloadPdf: async (patientId: string, patientName?: string) => {
    const headers: Record<string, string> = {};
    const t = token();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    let res: Response;
    try {
      res = await fetch(`${BASE}/reports/${patientId}/pdf`, { headers });
    } catch {
      throw new ApiError(0, "network_unreachable");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(res.status, (body && body.detail) || `request_failed_${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `wardzero-report-${(patientName || patientId).toLowerCase().replace(/\s+/g, "-")}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

// -------------------------------------------------------------- health (GET /health)
export const healthApi = {
  check: () => request<any>("/health"),
};

// -------------------------------------------------------------- idempotent batch ingest (POST /readings/batch)
export const readingsApi = {
  batch: (items: { event: Record<string, unknown>; context: Record<string, unknown> }[]) =>
    request<{ results: { event_id: string; status: string }[]; counts: Record<string, number> }>(
      "/readings/batch", { method: "POST", body: JSON.stringify({ items }) }),
};
