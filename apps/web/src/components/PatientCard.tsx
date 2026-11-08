import React from "react";
import { GlassCard } from "./GlassCard";
import { RiskBadge, StatusIndicator } from "./StatusIndicator";
import { patientAvatarUrl } from "../lib/avatars";
import { VITAL_META, fmtNum } from "../lib/format";
import type { PatientSummary } from "../lib/api";

export function PatientCard({ patient, onClick }: { patient: PatientSummary; onClick?: () => void }) {
  const r = patient.latest_reading || {};
  const ringClass = `avatar-ring-${(patient.risk_level || "unknown").toLowerCase()}`;
  return (
    <GlassCard
      className="patient-card focus-ring"
      onClick={onClick}
      style={{ padding: 16 }}
    >
      <div className="patient-card-head">
        <img
          src={patientAvatarUrl(patient.id)}
          alt={`${patient.full_name} portrait`}
          className={`avatar ${ringClass}`}
          style={{ width: 44, height: 44 }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 650, fontSize: 14, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {patient.full_name}
          </div>
          <div className="text-tertiary" style={{ fontSize: 11.5 }}>
            Age {patient.age} · {patient.conditions.length ? patient.conditions.map((c) => c.replace(/_/g, " ")).join(", ") : "no conditions on file"}
          </div>
        </div>
        <RiskBadge level={patient.risk_level} />
      </div>

      <div className="patient-mini-vitals">
        {["heart_rate", "spo2", "temperature"].map((k) => (
          <span key={k} className="mini-vital">
            <span style={{ opacity: 0.8 }}>{VITAL_META[k].icon}</span>
            {fmtNum(r[k], k === "temperature" ? 1 : 0)}
            <span className="text-tertiary">{VITAL_META[k].unit}</span>
          </span>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <StatusIndicator status={patient.connectivity} />
        <div className="flex items-center gap-8">
          {patient.simulation_running && <span className="chip" title="A simulation is currently running for this patient">{"\u25CF"} simulating</span>}
          {patient.active_alert_count > 0 && (
            <span className="badge badge-high" style={{ fontSize: 10.5 }}>{patient.active_alert_count} alert{patient.active_alert_count > 1 ? "s" : ""}</span>
          )}
        </div>
      </div>
    </GlassCard>
  );
}
