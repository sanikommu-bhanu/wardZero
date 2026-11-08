// Decorative-only: maps the 12 fixed seed patients (database/seed.py) to a stock portrait so the UI
// doesn't show blank circles. Patients are seeded server-side only (no POST /patients route exists),
// so this fixed map covers every patient the API can ever return; any unrecognized id still gets a
// deterministic fallback photo rather than breaking. This affects decorative art only — every clinical
// value on screen (vitals, risk, alerts) still comes from the real API/WS, never from this file.
const MALE_PORTRAIT = "https://images.unsplash.com/photo-1579406842270-ea87c39a8a12?auto=format&fit=crop&w=256&h=256&q=80";
const FEMALE_PORTRAIT = "https://images.unsplash.com/photo-1749189516333-168cfd97de0b?auto=format&fit=crop&w=256&h=256&q=80";

const GENDER_BY_ID: Record<string, "m" | "f"> = {
  "demo-ravi-kumar": "m",
  "demo-lakshmi-devi": "f",
  "demo-arjun-reddy": "m",
  "demo-saroja-amma": "f",
  "demo-krishna-rao": "m",
  "demo-meena-iyer": "f",
  "demo-suresh-babu": "m",
  "demo-kamala-bai": "f",
  "demo-venkat-rao": "m",
  "demo-padma-devi": "f",
  "demo-ramesh-chandra": "m",
  "demo-anitha-kumari": "f",
};

export function patientAvatarUrl(patientId: string): string {
  const g = GENDER_BY_ID[patientId] || (hashCode(patientId) % 2 === 0 ? "m" : "f");
  return g === "m" ? MALE_PORTRAIT : FEMALE_PORTRAIT;
}

export const ROOM_BG_URL = "https://images.unsplash.com/photo-1497074367201-25b8d28279e2?auto=format&fit=crop&w=1400&q=75";
export const AUTH_BG_URL = "https://images.unsplash.com/photo-1680965585463-386646047473?auto=format&fit=crop&w=1400&q=75";

function hashCode(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function initials(name?: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}
