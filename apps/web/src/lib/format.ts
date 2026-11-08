// Pure formatting helpers. Vital keys/units/ranges mirror ml/features/schema.py exactly (VITALS,
// UNITS, RANGES) and services/risk_engine/rules.py HARD_THRESHOLDS, so "normal range" framing in the
// UI matches what the backend itself considers safe — not an invented clinical claim.
export const VITAL_META: Record<string, { label: string; unit: string; icon: string; safe: [number, number] }> = {
  heart_rate: { label: "Heart Rate", unit: "bpm", icon: "\u2665", safe: [40, 150] },
  spo2: { label: "SpO\u2082", unit: "%", icon: "\u2740", safe: [88, 101] },
  temperature: { label: "Temperature", unit: "\u00b0C", icon: "\u2600", safe: [35.0, 40.0] },
  resp_rate: { label: "Respiratory Rate", unit: "/min", icon: "\u2248", safe: [8, 30] },
  systolic_bp: { label: "Systolic BP", unit: "mmHg", icon: "\u2b06", safe: [85, 200] },
  diastolic_bp: { label: "Diastolic BP", unit: "mmHg", icon: "\u2b07", safe: [30, 160] },
  activity: { label: "Activity", unit: "idx", icon: "\u25CF", safe: [0, 100] },
};

export const VITAL_ORDER = ["heart_rate", "spo2", "temperature", "resp_rate", "systolic_bp", "diastolic_bp", "activity"];

export function isOutOfRange(key: string, value: number | null | undefined): boolean {
  if (value === null || value === undefined) return false;
  const meta = VITAL_META[key];
  if (!meta) return false;
  return value < meta.safe[0] || value > meta.safe[1];
}

export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "\u2014";
  return v.toFixed(digits);
}

export function timeAgo(iso?: string | number | null): string {
  if (!iso) return "\u2014";
  const t = typeof iso === "number" ? iso : new Date(iso).getTime();
  if (Number.isNaN(t)) return "\u2014";
  const diffSec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const m = Math.floor(diffSec / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function clock(iso?: string | number | null): string {
  if (!iso) return "\u2014";
  const d = typeof iso === "number" ? new Date(iso) : new Date(iso);
  if (Number.isNaN(d.getTime())) return "\u2014";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "\u2014";
  return `${(v * 100).toFixed(digits)}%`;
}

export function titleCase(s?: string | null): string {
  if (!s) return "";
  return s.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function escalationLabel(s?: string | null): string {
  const map: Record<string, string> = {
    routine_monitoring: "Routine Monitoring",
    caregiver_review: "Caregiver Review",
    escalate_to_doctor: "Escalate to Doctor",
    emergency: "Emergency",
  };
  return (s && map[s]) || titleCase(s || "");
}
