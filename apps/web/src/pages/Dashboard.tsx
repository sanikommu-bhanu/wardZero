import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { GlassCard } from "../components/GlassCard";
import { PatientCard } from "../components/PatientCard";
import { LoadingBlock, ErrorBlock, EmptyBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { useAuth } from "../context/AuthContext";
import { patientsApi, analyticsApi, alertsApi, type PatientSummary } from "../lib/api";
import { timeAgo, titleCase } from "../lib/format";

const KPI_DEFS = [
  { key: "total", label: "Total Patients", icon: "\u25A4", bg: "var(--bronze-dim)", color: "var(--bronze-soft)" },
  { key: "high", label: "High Risk", icon: "\u26A0", bg: "var(--red-dim)", color: "var(--red-text)" },
  { key: "medium", label: "Medium Risk", icon: "\u25B2", bg: "var(--amber-dim)", color: "var(--amber-text)" },
  { key: "stable", label: "Stable", icon: "\u2713", bg: "var(--green-dim)", color: "var(--green-text)" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const { subscribe } = useRealtime();
  const navigate = useNavigate();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, s, a] = await Promise.all([patientsApi.list(), analyticsApi.summary(), alertsApi.list(false)]);
      setPatients(p);
      setSummary(s);
      setAlerts([...a].sort((x, y) => new Date(y.updated_at || 0).getTime() - new Date(x.updated_at || 0).getTime()).slice(0, 8));
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to load dashboard data");
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => subscribe(() => load()), [subscribe, load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  if (error && !patients) return <ErrorBlock detail={error} onRetry={load} />;
  if (!patients || !summary) return <LoadingBlock rows={4} />;

  const dist = summary.risk_distribution || {};
  const kpiValues: Record<string, number> = { total: summary.total_patients, high: dist.high, medium: dist.medium, stable: dist.low };
  const highRiskPatients = patients.filter((p) => (p.risk_level || "").toLowerCase() === "high");
  const overview = [...highRiskPatients, ...patients.filter((p) => (p.risk_level || "").toLowerCase() !== "high")].slice(0, 6);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Good {timeOfDay()}, {user?.email?.split("@")[0] || "there"} {"\u{1F44B}"}</div>
          <div className="page-subtitle">Here's what's happening with your patients today.</div>
        </div>
      </div>

      <div className="grid grid-cols-4" style={{ marginBottom: 20 }}>
        {KPI_DEFS.map((k) => (
          <GlassCard key={k.key} className="kpi-tile">
            <div className="kpi-icon" style={{ background: k.bg, color: k.color }}>{k.icon}</div>
            <div>
              <div className="kpi-value">{kpiValues[k.key] ?? "\u2014"}</div>
              <div className="kpi-label">{k.label}</div>
            </div>
          </GlassCard>
        ))}
      </div>

      <div className="two-col">
        <div>
          <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 650, fontSize: 15 }}>Live Patient Overview</div>
            <button className="link-btn focus-ring" onClick={() => navigate("/patients")}>View all {"\u2192"}</button>
          </div>
          {overview.length === 0 ? (
            <EmptyBlock title="No patients on file" />
          ) : (
            <div className="grid grid-cols-2">
              {overview.map((p) => <PatientCard key={p.id} patient={p} onClick={() => navigate(`/patients/${p.id}`)} />)}
            </div>
          )}

          <div style={{ fontWeight: 650, fontSize: 15, margin: "24px 0 12px" }}>Activity Stream</div>
          <GlassCard hover={false}>
            {alerts.length === 0 ? (
              <div className="text-tertiary" style={{ fontSize: 13 }}>No recent alert activity.</div>
            ) : (
              alerts.map((a) => {
                const p = patients.find((pp) => pp.id === a.patient_id);
                return (
                  <div key={a.id} className="activity-row">
                    <span style={{ opacity: 0.85 }}>{"\u26A0"}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13 }}>{titleCase(a.alert_type)} — {p?.full_name || a.patient_id}</div>
                      <div className="text-tertiary" style={{ fontSize: 11 }}>{titleCase(a.status)} · {timeAgo(a.updated_at)}</div>
                    </div>
                  </div>
                );
              })
            )}
          </GlassCard>
        </div>

        <div>
          <div style={{ fontWeight: 650, fontSize: 15, marginBottom: 12 }}>Quick Actions</div>
          <GlassCard hover={false} className="flex flex-col gap-8">
            <QuickAction label="Add Patient" icon="+" onClick={() => alert("Patients in this demo are fixed seed data — there is no create-patient endpoint in the API, so this action is intentionally disabled rather than faking a new record.")} />
            <QuickAction label="Simulate Sensor Data" icon={"\u21BB"} onClick={() => navigate("/iot-simulator")} />
            <QuickAction label="Generate Report" icon={"\u2637"} onClick={() => navigate("/reports")} />
            <QuickAction label="View Alerts" icon={"\u26A0"} onClick={() => navigate("/alerts")} badge={summary.active_alerts} />
          </GlassCard>
        </div>
      </div>
    </div>
  );
}

function QuickAction({ label, icon, onClick, badge }: { label: string; icon: string; onClick: () => void; badge?: number }) {
  return (
    <button className="glass-btn focus-ring" style={{ justifyContent: "space-between", width: "100%" }} onClick={onClick}>
      <span className="flex items-center gap-8"><span>{icon}</span>{label}</span>
      {!!badge && <span className="badge badge-high">{badge}</span>}
    </button>
  );
}

function timeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
