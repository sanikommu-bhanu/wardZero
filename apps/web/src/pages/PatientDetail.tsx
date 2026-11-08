import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { GlassCard, GlassButton } from "../components/GlassCard";
import { RiskBadge, StatusIndicator } from "../components/StatusIndicator";
import { VitalCard } from "../components/VitalCard";
import { LiveChart } from "../components/LiveChart";
import { Timeline } from "../components/Timeline";
import { LoadingBlock, ErrorBlock, EmptyBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { patientsApi, type PatientSummary } from "../lib/api";
import { patientAvatarUrl } from "../lib/avatars";
import { VITAL_ORDER, VITAL_META, timeAgo } from "../lib/format";

type Tab = "vitals" | "timeline" | "notes";

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { subscribe, getVitalsHistory, hydrateHistory } = useRealtime();
  const [patient, setPatient] = useState<PatientSummary | null>(null);
  const [timeline, setTimeline] = useState<any[] | null>(null);
  const [notes, setNotes] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("vitals");

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const p = await patientsApi.get(id);
      setPatient(p);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to load patient");
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (id) hydrateHistory(id); }, [id, hydrateHistory]);
  useEffect(() => subscribe((msg) => { if (msg.patient_id === id) load(); }), [subscribe, load, id]);

  useEffect(() => {
    if (!id || tab !== "timeline") return;
    patientsApi.timeline(id).then(setTimeline).catch(() => setTimeline([]));
  }, [id, tab]);

  useEffect(() => {
    if (!id || tab !== "notes") return;
    patientsApi.notes(id).then(setNotes).catch(() => setNotes([]));
  }, [id, tab]);

  if (error && !patient) return <ErrorBlock detail={error} onRetry={load} />;
  if (!patient || !id) return <LoadingBlock rows={4} />;

  const r = patient.latest_reading || {};
  const history = getVitalsHistory(id);

  return (
    <div>
      <button className="link-btn focus-ring" style={{ marginBottom: 14, display: "inline-block" }} onClick={() => navigate("/patients")}>{"\u2190"} Patients</button>

      <GlassCard hover={false} style={{ marginBottom: 20 }}>
        <div className="flex items-center gap-16" style={{ flexWrap: "wrap" }}>
          <img src={patientAvatarUrl(patient.id)} alt={`${patient.full_name} portrait`} className={`avatar avatar-ring-${(patient.risk_level || "unknown").toLowerCase()}`} style={{ width: 64, height: 64 }} />
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ fontWeight: 700, fontSize: 19 }}>{patient.full_name}</div>
            <div className="text-secondary" style={{ fontSize: 13 }}>
              Age {patient.age} · {patient.conditions.length ? patient.conditions.map((c) => c.replace(/_/g, " ")).join(", ") : "No conditions on file"}
            </div>
          </div>
          <RiskBadge level={patient.risk_level} />
          <StatusIndicator status={patient.connectivity} />
          {patient.active_alert_count > 0 && (
            <button className="badge badge-high focus-ring" style={{ border: "none", cursor: "pointer" }} onClick={() => navigate("/alerts")}>
              {patient.active_alert_count} active alert{patient.active_alert_count > 1 ? "s" : ""}
            </button>
          )}
        </div>
      </GlassCard>

      <div className="tab-row" style={{ marginBottom: 20 }} role="tablist">
        <button className={`tab-btn focus-ring ${tab === "vitals" ? "active" : ""}`} onClick={() => setTab("vitals")} role="tab" aria-selected={tab === "vitals"}>Live Vitals</button>
        <button className={`tab-btn focus-ring ${tab === "timeline" ? "active" : ""}`} onClick={() => setTab("timeline")} role="tab" aria-selected={tab === "timeline"}>Timeline</button>
        <button className={`tab-btn focus-ring ${tab === "notes" ? "active" : ""}`} onClick={() => setTab("notes")} role="tab" aria-selected={tab === "notes"}>Notes</button>
      </div>

      {tab === "vitals" && (
        <div>
          {!patient.latest_reading ? (
            <EmptyBlock title="No vitals received yet" detail="Start a simulation for this patient from the IoT Simulator page to see live readings." />
          ) : (
            <div className="grid grid-cols-4" style={{ marginBottom: 20 }}>
              {VITAL_ORDER.map((k) => {
                const meta = VITAL_META[k];
                const hist = history.map((h) => (h as any)[k]).filter((v) => typeof v === "number");
                return (
                  <VitalCard key={k} vitalKey={k} label={meta.label} unit={meta.unit} icon={meta.icon} value={r[k]} digits={k === "temperature" ? 1 : 0} history={hist.length >= 2 ? hist.slice(-30) : undefined} />
                );
              })}
            </div>
          )}
          <GlassCard hover={false}>
            <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 12 }}>Heart Rate &amp; SpO{"\u2082"} — Live Session</div>
            <LiveChart history={history} seriesKeys={["heart_rate", "spo2"]} />
          </GlassCard>
        </div>
      )}

      {tab === "timeline" && (
        <GlassCard hover={false}>
          {timeline === null ? <LoadingBlock rows={3} /> : <Timeline events={timeline} />}
        </GlassCard>
      )}

      {tab === "notes" && (
        <GlassCard hover={false}>
          <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
            <div style={{ fontWeight: 650, fontSize: 14 }}>Caregiver Notes</div>
            <GlassButton size="sm" onClick={() => navigate("/caregiver-notes")}>Add a note</GlassButton>
          </div>
          {notes === null ? (
            <LoadingBlock rows={2} />
          ) : notes.length === 0 ? (
            <div className="text-tertiary" style={{ fontSize: 13 }}>No caregiver notes recorded yet for this patient.</div>
          ) : (
            <div className="flex flex-col gap-12">
              {[...notes].reverse().map((n) => (
                <div key={n.id} style={{ borderBottom: "1px solid var(--border-glass)", paddingBottom: 12 }}>
                  <div style={{ fontSize: 13, marginBottom: 4 }}>{n.text}</div>
                  <div className="text-tertiary" style={{ fontSize: 11 }}>
                    {n.language ? `${n.language} · ` : ""}{timeAgo(n.created_at)}
                    {n.result?.present?.length ? ` · flagged: ${n.result.present.join(", ")}` : ""}
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      )}
    </div>
  );
}
