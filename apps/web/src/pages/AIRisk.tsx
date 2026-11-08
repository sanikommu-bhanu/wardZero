import React, { useEffect, useState } from "react";
import { GlassCard } from "../components/GlassCard";
import { RiskBadge } from "../components/StatusIndicator";
import { AIExplanation } from "../components/AIExplanation";
import { ForecastChart } from "../components/ForecastChart";
import { LoadingBlock, ErrorBlock, EmptyBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { patientsApi, alertsApi, type PatientSummary } from "../lib/api";
import { pct } from "../lib/format";

function RiskGauge({ probability, level }: { probability: number | null; level: string }) {
  const p = probability ?? 0;
  const color = level === "high" ? "var(--red)" : level === "medium" ? "var(--amber)" : "var(--green)";
  const r = 60, c = 2 * Math.PI * r;
  return (
    <div className="risk-gauge-wrap">
      <svg width="148" height="148" viewBox="0 0 148 148">
        <circle cx="74" cy="74" r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="12" />
        <circle
          cx="74" cy="74" r={r} fill="none" stroke={color} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - p)} transform="rotate(-90 74 74)"
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <div className="risk-gauge-center">
        <div style={{ fontSize: 24, fontWeight: 700 }}>{probability != null ? pct(probability) : "\u2014"}</div>
        <div className="text-tertiary" style={{ fontSize: 10.5 }}>confidence</div>
      </div>
    </div>
  );
}

export default function AIRisk() {
  const { subscribe, getRiskAssessment } = useRealtime();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [patientId, setPatientId] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Fallback source: GET /patients only returns risk_level/risk_probability scalars, not the full
  // explainable assessment. If no live sim_reading has arrived yet this session, fall back to the
  // risk_assessment snapshot carried on the patient's most recent alert (still real backend state,
  // just from an earlier moment) rather than showing nothing at all.
  const [alertFallback, setAlertFallback] = useState<any | null>(null);

  useEffect(() => {
    patientsApi.list().then((p) => { setPatients(p); if (p.length) setPatientId(p[0].id); }).catch((e) => setError(e?.message || "Failed to load patients"));
  }, []);
  useEffect(() => subscribe(() => {
    patientsApi.list().then(setPatients).catch(() => {});
  }), [subscribe]);

  useEffect(() => {
    if (!patientId) return;
    setAlertFallback(null);
    alertsApi.list(false, patientId).then((alerts) => {
      const withAssessment = [...alerts].filter((a) => a.risk_assessment).sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime());
      if (withAssessment.length) setAlertFallback(withAssessment[0].risk_assessment);
    }).catch(() => {});
  }, [patientId]);

  if (error && !patients) return <ErrorBlock detail={error} onRetry={() => window.location.reload()} />;
  if (!patients) return <LoadingBlock rows={4} />;

  const patient = patients.find((p) => p.id === patientId) || null;
  const assessment = (patientId && getRiskAssessment(patientId)) || alertFallback;
  const level = (patient?.risk_level || "unknown").toLowerCase();

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">AI Risk Analysis</div>
          <div className="page-subtitle">Explainable risk scoring, contributing factors and short-horizon forecast.</div>
        </div>
        <select className="input-field focus-ring" style={{ maxWidth: 260 }} value={patientId} onChange={(e) => setPatientId(e.target.value)} aria-label="Select patient">
          {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
        </select>
      </div>

      {!patient ? (
        <EmptyBlock title="No patient selected" />
      ) : (
        <div className="two-col">
          <GlassCard hover={false}>
            <div className="flex items-center justify-between" style={{ marginBottom: 18 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>{patient.full_name}</div>
                <RiskBadge level={patient.risk_level} />
              </div>
              <RiskGauge probability={patient.risk_probability} level={level} />
            </div>
            <div className="divider" />
            {assessment ? <AIExplanation assessment={assessment} /> : (
              <EmptyBlock title="No detailed AI assessment available yet" detail="The full explanation only travels with a live simulator reading or an alert snapshot — start a simulation for this patient, or check back after their next alert." />
            )}
          </GlassCard>

          <div>
            <GlassCard hover={false} style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 14 }}>24h / 48h Forecast</div>
              <ForecastChart forecast={assessment?.forecast} />
            </GlassCard>
            <GlassCard hover={false} style={{ borderColor: "var(--border-glass-strong)" }}>
              <div style={{ fontWeight: 650, fontSize: 13, marginBottom: 6 }}>Clinical disclaimer</div>
              <div className="text-tertiary" style={{ fontSize: 12 }}>
                {assessment?.disclaimer || "This tool provides decision support only and does not replace clinical judgment. All demo data is synthetic."}
              </div>
            </GlassCard>
          </div>
        </div>
      )}
    </div>
  );
}
