import React, { useState } from "react";
import { GlassCard, GlassButton } from "./GlassCard";
import { timeAgo, titleCase } from "../lib/format";

function sevBadgeClass(sev?: string) {
  if (sev === "critical") return "badge-high";
  if (sev === "warning") return "badge-medium";
  return "badge-unknown";
}

const TERMINAL = new Set(["RESOLVED", "DISMISSED"]);

export function AlertCard({ alert, patientName, onAcknowledge, onEscalate, onDismiss, onRespond, onResolve, onAddNote, busy }: {
  alert: any; patientName?: string;
  onAcknowledge?: () => void; onEscalate?: () => void; onDismiss?: (reason: string) => void;
  onRespond?: (note?: string) => void; onResolve?: (note?: string) => void; onAddNote?: (note: string) => void; busy?: boolean;
}) {
  const [showDismiss, setShowDismiss] = useState(false);
  const [dismissReason, setDismissReason] = useState("");
  const [showNote, setShowNote] = useState(false);
  const [noteText, setNoteText] = useState("");
  const status = (alert.status || "").toUpperCase();
  const terminal = TERMINAL.has(status);

  return (
    <GlassCard className={`alert-card sev-${alert.severity || "informational"}`} hover={false}>
      <div className="flex items-center justify-between" style={{ flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
        <div>
          <div style={{ fontWeight: 650, fontSize: 14 }}>
            {titleCase(alert.alert_type || "alert")}{patientName ? ` — ${patientName}` : ""}
          </div>
          <div className="text-tertiary" style={{ fontSize: 11.5 }}>
            Detected {timeAgo(alert.detected_at)} · Updated {timeAgo(alert.updated_at)}
          </div>
        </div>
        <div className="flex items-center gap-8">
          <span className={`badge ${sevBadgeClass(alert.severity)}`}>{titleCase(alert.severity)}</span>
          <span className="chip">{titleCase(status)}</span>
        </div>
      </div>

      {alert.risk_assessment?.explanation && (
        <div style={{ fontSize: 13, lineHeight: 1.55, marginBottom: 10 }}>{alert.risk_assessment.explanation}</div>
      )}

      {alert.dismiss_reason && (
        <div className="text-tertiary" style={{ fontSize: 12, marginBottom: 8 }}>Dismissed: {alert.dismiss_reason}</div>
      )}

      {Array.isArray(alert.audit) && alert.audit.length > 0 && (
        <div className="flex items-center gap-8" style={{ flexWrap: "wrap", marginBottom: 10, fontSize: 11 }}>
          {alert.audit.map((a: any, i: number) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="text-tertiary">{"\u2192"}</span>}
              <span className="chip" title={a.actor ? `by ${a.actor}` : undefined}>{titleCase(a.action)}</span>
            </React.Fragment>
          ))}
        </div>
      )}

      {Array.isArray(alert.notes) && alert.notes.length > 0 && (
        <div className="flex flex-col gap-4" style={{ marginBottom: 10 }}>
          {alert.notes.map((n: any, i: number) => (
            <div key={i} className="text-secondary" style={{ fontSize: 12, background: "rgba(255,255,255,0.03)", padding: "6px 10px", borderRadius: 8 }}>
              {typeof n === "string" ? n : n.note || JSON.stringify(n)}
            </div>
          ))}
        </div>
      )}

      {!terminal && (
        <div className="flex items-center gap-8" style={{ flexWrap: "wrap" }}>
          {status === "ALERTED" && onAcknowledge && <GlassButton size="sm" onClick={onAcknowledge} disabled={busy}>Acknowledge</GlassButton>}
          {(status === "ALERTED" || status === "ACKNOWLEDGED") && onEscalate && (
            <GlassButton size="sm" variant="danger" onClick={onEscalate} disabled={busy}>Escalate</GlassButton>
          )}
          {(status === "ACKNOWLEDGED" || status === "ESCALATED") && onRespond && (
            <GlassButton size="sm" onClick={() => onRespond()} disabled={busy}>Mark Responded</GlassButton>
          )}
          {status === "RESPONDED" && onResolve && (
            <GlassButton size="sm" onClick={() => onResolve()} disabled={busy}>Resolve</GlassButton>
          )}
          {(status === "ALERTED" || status === "ACKNOWLEDGED") && onDismiss && (
            <GlassButton size="sm" onClick={() => setShowDismiss((s) => !s)} disabled={busy}>Dismiss</GlassButton>
          )}
          {onAddNote && (
            <GlassButton size="sm" onClick={() => setShowNote((s) => !s)} disabled={busy}>Add Note</GlassButton>
          )}
        </div>
      )}

      {showDismiss && onDismiss && (
        <div className="flex items-center gap-8" style={{ marginTop: 10 }}>
          <input
            className="input-field focus-ring" style={{ padding: "8px 12px", fontSize: 12.5, flex: 1 }}
            placeholder="Reason for dismissing..." value={dismissReason}
            onChange={(e) => setDismissReason(e.target.value)} aria-label="Dismiss reason"
          />
          <GlassButton size="sm" variant="primary" disabled={!dismissReason.trim() || busy} onClick={() => { onDismiss(dismissReason.trim()); setDismissReason(""); setShowDismiss(false); }}>
            Confirm
          </GlassButton>
        </div>
      )}

      {showNote && onAddNote && (
        <div className="flex items-center gap-8" style={{ marginTop: 10 }}>
          <input
            className="input-field focus-ring" style={{ padding: "8px 12px", fontSize: 12.5, flex: 1 }}
            placeholder="Add a note for the care team..." value={noteText}
            onChange={(e) => setNoteText(e.target.value)} aria-label="Alert note"
          />
          <GlassButton size="sm" variant="primary" disabled={!noteText.trim() || busy} onClick={() => { onAddNote(noteText.trim()); setNoteText(""); setShowNote(false); }}>
            Save
          </GlassButton>
        </div>
      )}
    </GlassCard>
  );
}
