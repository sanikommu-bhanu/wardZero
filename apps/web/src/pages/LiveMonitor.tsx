import React, { useEffect, useMemo, useState } from "react";
import { GlassCard } from "../components/GlassCard";
import { RiskBadge } from "../components/StatusIndicator";
import { LiveChart } from "../components/LiveChart";
import { LoadingBlock, ErrorBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { patientsApi, type PatientSummary } from "../lib/api";
import { VITAL_META, fmtNum } from "../lib/format";

const SERIES_CHOICES = ["heart_rate", "spo2", "temperature", "resp_rate"];

export default function LiveMonitor() {
  const { getVitalsHistory, hydrateHistory, subscribe } = useRealtime();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [patientId, setPatientId] = useState<string>("");
  const [series, setSeries] = useState<string[]>(["heart_rate", "spo2"]);

  useEffect(() => {
    patientsApi.list().then((p) => { setPatients(p); if (p.length && !patientId) setPatientId(p[0].id); }).catch((e) => setError(e?.message || "Failed to load patients"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Charts load persisted history from GET /patients/{id}/readings, so they survive a page reload.
  useEffect(() => { if (patientId) hydrateHistory(patientId); }, [patientId, hydrateHistory]);

  const [, forceTick] = useState(0);
  useEffect(() => subscribe(() => forceTick((t) => t + 1)), [subscribe]);

  const patient = useMemo(() => patients?.find((p) => p.id === patientId) || null, [patients, patientId]);
  const history = patientId ? getVitalsHistory(patientId) : [];

  if (error && !patients) return <ErrorBlock detail={error} onRetry={() => window.location.reload()} />;
  if (!patients) return <LoadingBlock rows={4} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Live Monitor</div>
          <div className="page-subtitle">Real-time vitals streamed over WebSocket during an active simulation.</div>
        </div>
        <select className="input-field focus-ring" style={{ maxWidth: 260 }} value={patientId} onChange={(e) => setPatientId(e.target.value)} aria-label="Select patient">
          {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
        </select>
      </div>

      {patient && (
        <div className="grid grid-cols-4" style={{ marginBottom: 16 }}>
          {["heart_rate", "spo2", "temperature", "resp_rate"].map((k) => (
            <GlassCard key={k} style={{ padding: 14 }}>
              <div className="text-secondary" style={{ fontSize: 12 }}>{VITAL_META[k].icon} {VITAL_META[k].label}</div>
              <div className="vital-value">{fmtNum(patient.latest_reading?.[k], k === "temperature" ? 1 : 0)}<span className="vital-unit">{VITAL_META[k].unit}</span></div>
            </GlassCard>
          ))}
        </div>
      )}

      <GlassCard hover={false} style={{ marginBottom: 16 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
          <div className="flex items-center gap-8" style={{ flexWrap: "wrap" }}>
            {SERIES_CHOICES.map((k) => (
              <label key={k} className="chip focus-ring" style={{ cursor: "pointer", background: series.includes(k) ? "var(--bronze-dim)" : undefined, color: series.includes(k) ? "var(--bronze-soft)" : undefined }}>
                <input
                  type="checkbox" checked={series.includes(k)} style={{ marginRight: 6 }}
                  onChange={() => setSeries((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k]))}
                />
                {VITAL_META[k].label}
              </label>
            ))}
          </div>
          {patient && <RiskBadge level={patient.risk_level} />}
        </div>
        <LiveChart history={history} seriesKeys={series} height={340} />
      </GlassCard>
    </div>
  );
}
