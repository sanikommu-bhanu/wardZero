import React from "react";
import { clock } from "../lib/format";

// Renders /patients/{id}/timeline events exactly as the backend stores them: {id, patient_id, kind,
// detail, ts}. `ts` (added in repository.py — real wall-clock time the event was recorded) is
// preferred; `detail.timestamp` (the sensor reading's own time, only present on "reading_received")
// is the fallback for any event recorded before that field existed. If genuinely neither is present,
// we fall back to id ordering rather than inventing a clock time — id ordering is monotonically
// chronological per patient (repository.py assigns ids from a single shared counter as events are
// appended).
const KIND_META: Record<string, { icon: string; label: (d: any) => string }> = {
  reading_received: { icon: "\u25CF", label: () => "Vitals reading received" },
  risk_assessed: { icon: "\u2726", label: (d) => `Risk assessed: ${(d?.risk_level || "unknown")}${d?.method ? ` (${d.method})` : ""}` },
  caregiver_note: { icon: "\u270E", label: (d) => `Caregiver note added${d?.present?.length ? ` — flagged: ${d.present.join(", ")}` : ""}` },
};

function eventMeta(kind: string, detail: any) {
  if (KIND_META[kind]) return KIND_META[kind];
  if (kind.startsWith("alert_")) {
    const status = kind.replace("alert_", "");
    return { icon: "\u26A0", label: () => `Alert ${status}${detail?.severity ? ` (${detail.severity})` : ""}` };
  }
  return { icon: "\u25CB", label: () => kind.replace(/_/g, " ") };
}

export function Timeline({ events }: { events: any[] }) {
  if (!events || events.length === 0) {
    return <div className="text-tertiary" style={{ fontSize: 13, padding: "12px 0" }}>No timeline events yet for this patient.</div>;
  }
  const ordered = [...events].sort((a, b) => (a.id ?? 0) - (b.id ?? 0)).reverse();
  return (
    <div className="timeline-list">
      {ordered.map((e) => {
        const meta = eventMeta(e.kind || "unknown", e.detail);
        const ts = e.ts || e.detail?.timestamp;
        return (
          <div key={e.id} className="timeline-item">
            <div className="flex items-center gap-8">
              <span style={{ opacity: 0.85 }}>{meta.icon}</span>
              <span style={{ fontSize: 13 }}>{meta.label(e.detail)}</span>
            </div>
            <div className="timeline-time">{ts ? clock(ts) : `event #${e.id}`}</div>
          </div>
        );
      })}
    </div>
  );
}
