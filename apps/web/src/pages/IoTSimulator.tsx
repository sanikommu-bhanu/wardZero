import React, { useEffect, useState } from "react";
import { GlassCard, GlassButton } from "../components/GlassCard";
import { LoadingBlock, ErrorBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { useToast } from "../components/Toast";
import { patientsApi, simulatorApi, type PatientSummary, type SimStatus } from "../lib/api";
import { ChaosPanel } from "../components/ChaosPanel";
import { VITAL_META, fmtNum, titleCase } from "../lib/format";

const VITAL_TOGGLES = ["heart_rate", "spo2", "temperature", "resp_rate"];
const SPEEDS = [1, 2, 5];

export default function IoTSimulator() {
  const { subscribe } = useRealtime();
  const { push } = useToast();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [scenarios, setScenarios] = useState<{ name: string; description: string }[]>([]);
  const [patientId, setPatientId] = useState("");
  const [scenario, setScenario] = useState("normal");
  const [speed, setSpeed] = useState(1);
  const [status, setStatus] = useState<SimStatus | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([patientsApi.list(), simulatorApi.scenarios()]).then(([p, s]) => {
      setPatients(p); setScenarios(s);
      if (p.length) setPatientId(p[0].id);
    }).catch((e) => setError(e?.message || "Failed to load simulator data"));
  }, []);

  useEffect(() => {
    if (!patientId) return;
    simulatorApi.statusOne(patientId).then(setStatus).catch(() => setStatus(null));
    setEvents([]);
  }, [patientId]);

  useEffect(() => subscribe((msg) => {
    if (msg.patient_id !== patientId) return;
    if (msg.type === "sim_reading" || msg.type === "device_event") {
      setEvents((e) => [msg, ...e].slice(0, 40));
      simulatorApi.statusOne(patientId).then(setStatus).catch(() => {});
    }
  }), [subscribe, patientId]);

  async function run(label: string, fn: () => Promise<SimStatus>) {
    setBusy(true);
    try {
      const s = await fn();
      setStatus(s);
      push(label, "success");
    } catch (e: any) {
      push(e?.message || `Failed to ${label.toLowerCase()}`, "error");
    } finally {
      setBusy(false);
    }
  }

  if (error && !patients) return <ErrorBlock detail={error} onRetry={() => window.location.reload()} />;
  if (!patients) return <LoadingBlock rows={4} />;

  const patient = patients.find((p) => p.id === patientId) || null;
  const latest = events.find((e) => e.type === "sim_reading");

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">IoT Sensor Simulator</div>
          <div className="page-subtitle">Drives the real ingestion pipeline exactly like a physical device would.</div>
        </div>
      </div>

      <div className="two-col">
        <GlassCard hover={false}>
          <div className="flex flex-col gap-16">
            <div>
              <label className="field-label" htmlFor="sim-patient">Patient</label>
              <select id="sim-patient" className="input-field focus-ring" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
                {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="sim-scenario">Scenario</label>
              <select id="sim-scenario" className="input-field focus-ring" value={scenario} onChange={(e) => setScenario(e.target.value)}>
                {(scenarios.length ? scenarios : [{ name: "normal", description: "Normal vitals" }]).map((s) => (
                  <option key={s.name} value={s.name}>{titleCase(s.name)}</option>
                ))}
              </select>
              {scenarios.find((s) => s.name === scenario)?.description && (
                <div className="text-tertiary" style={{ fontSize: 11.5, marginTop: 6 }}>{scenarios.find((s) => s.name === scenario)?.description}</div>
              )}
            </div>
            <div>
              <label className="field-label">Speed</label>
              <div className="segmented">
                {SPEEDS.map((s) => (
                  <button key={s} className={speed === s ? "active" : ""} onClick={() => setSpeed(s)}>{s}x</button>
                ))}
              </div>
            </div>
            <div>
              <label className="field-label">Vitals streamed (display only — the simulator always drives every vital together; the API has no per-vital toggle)</label>
              <div className="flex flex-col gap-8">
                {VITAL_TOGGLES.map((k) => (
                  <div key={k} className="flex items-center justify-between">
                    <span style={{ fontSize: 13 }}>{VITAL_META[k].icon} {VITAL_META[k].label}</span>
                    <span className="toggle on" aria-hidden="true"><span className="toggle-knob" /></span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-8" style={{ flexWrap: "wrap" }}>
              <GlassButton variant="primary" disabled={busy} onClick={() => run("Simulation started", () => simulatorApi.start(patientId, scenario, speed))}>Start</GlassButton>
              <GlassButton disabled={busy} onClick={() => run("Simulation paused", () => simulatorApi.pause(patientId))}>Pause</GlassButton>
              <GlassButton disabled={busy} onClick={() => run("Simulation stopped", () => simulatorApi.stop(patientId))}>Stop</GlassButton>
              <GlassButton disabled={busy} onClick={() => run("Simulation reset", () => simulatorApi.reset(patientId, scenario, speed))}>Reset</GlassButton>
            </div>
            {status && (
              <div className="text-tertiary" style={{ fontSize: 11.5 }}>
                Status: <span className="text-secondary">{titleCase(status.status)}</span>{typeof status.tick_count === "number" ? ` · ${status.tick_count} ticks` : ""}
              </div>
            )}
          </div>
        </GlassCard>

        <div>
          <GlassCard hover={false} style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 12 }}>Live Simulation Data</div>
            {latest ? (
              <div className="grid grid-cols-4">
                {["heart_rate", "spo2", "temperature", "resp_rate"].map((k) => (
                  <div key={k}>
                    <div className="text-tertiary" style={{ fontSize: 11 }}>{VITAL_META[k].icon} {VITAL_META[k].label}</div>
                    <div className="vital-value" style={{ fontSize: 20 }}>{fmtNum(latest.reading?.[k], k === "temperature" ? 1 : 0)}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-tertiary" style={{ fontSize: 13 }}>No live reading yet for {patient?.full_name || "this patient"} — click Start.</div>
            )}
          </GlassCard>

          <GlassCard hover={false}>
            <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 12 }}>Live Event Stream (WebSocket)</div>
            {events.length === 0 ? (
              <div className="text-tertiary" style={{ fontSize: 13 }}>Events broadcast over /ws for this patient will appear here in real time.</div>
            ) : (
              <div className="flex flex-col gap-6" style={{ maxHeight: 320, overflowY: "auto" }}>
                {events.map((e, i) => (
                  <div key={i} className="mono" style={{ fontSize: 11.5, background: "rgba(255,255,255,0.03)", padding: "7px 10px", borderRadius: 8 }}>
                    <span className="chip" style={{ marginRight: 8 }}>{e.type}</span>
                    {e.type === "sim_reading" && `HR ${fmtNum(e.reading?.heart_rate)} · SpO2 ${fmtNum(e.reading?.spo2)}% · risk ${e.risk_assessment?.risk_level || "\u2014"}`}
                    {e.type === "device_event" && `${e.event?.device_event || "event"} on ${e.device_id}`}
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>
      </div>
      <ChaosPanel patientId={patientId} />
    </div>
  );
}
