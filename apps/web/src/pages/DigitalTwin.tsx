import React, { useCallback, useEffect, useState } from "react";
import { GlassCard } from "../components/GlassCard";
import { SensorCard } from "../components/SensorCard";
import { Drawer } from "../components/Modal";
import { LoadingBlock, ErrorBlock, EmptyBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { patientsApi, devicesApi, type PatientSummary, type Device } from "../lib/api";
import { ROOM_BG_URL } from "../lib/avatars";
import { VITAL_META, fmtNum } from "../lib/format";

// Fixed layout positions (percent of room-view box) per real device_type from database/seed.py's
// DEVICE_TYPES. Purely a floor-plan layout choice — the values/connectivity shown on each marker are
// always the real device + latest_reading data, never invented.
const LAYOUT: Record<string, { top: string; left: string }> = {
  heart_rate: { top: "58%", left: "44%" },
  spo2: { top: "40%", left: "68%" },
  temperature: { top: "22%", left: "80%" },
  respiratory_rate: { top: "72%", left: "70%" },
  blood_pressure: { top: "78%", left: "28%" },
};
const VITAL_FOR_DEVICE: Record<string, string> = {
  heart_rate: "heart_rate", spo2: "spo2", temperature: "temperature",
  respiratory_rate: "resp_rate", blood_pressure: "systolic_bp",
};

export default function DigitalTwin() {
  const { subscribe } = useRealtime();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [patientId, setPatientId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Device | null>(null);

  useEffect(() => {
    patientsApi.list().then((p) => { setPatients(p); if (p.length) setPatientId(p[0].id); }).catch((e) => setError(e?.message || "Failed to load patients"));
  }, []);

  const loadDevices = useCallback(async () => {
    if (!patientId) return;
    try {
      const d = await devicesApi.list(patientId);
      setDevices(d);
    } catch (e: any) {
      setError(e?.message || "Failed to load devices");
    }
  }, [patientId]);

  useEffect(() => { setDevices(null); loadDevices(); }, [loadDevices]);
  useEffect(() => subscribe((msg) => { if (msg.patient_id === patientId) loadDevices(); }), [subscribe, loadDevices, patientId]);

  const patient = patients?.find((p) => p.id === patientId) || null;

  if (error && !patients) return <ErrorBlock detail={error} onRetry={() => window.location.reload()} />;
  if (!patients) return <LoadingBlock rows={4} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Digital Twin — Patient Room</div>
          <div className="page-subtitle">2D live sensor layout, driven by real device state and readings.</div>
        </div>
        <select className="input-field focus-ring" style={{ maxWidth: 260 }} value={patientId} onChange={(e) => setPatientId(e.target.value)} aria-label="Select patient">
          {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
        </select>
      </div>

      <div className="two-col">
        <GlassCard hover={false} style={{ padding: 0, overflow: "hidden" }}>
          <div className="room-view" style={{ backgroundImage: `url(${ROOM_BG_URL})` }}>
            <div className="room-overlay" />
            {devices === null ? (
              <div style={{ position: "relative", padding: 20 }}><LoadingBlock rows={2} /></div>
            ) : (
              devices.map((d) => {
                const pos = LAYOUT[d.device_type] || { top: "50%", left: "50%" };
                const online = (d.connectivity || "").toLowerCase() === "online";
                const vitalKey = VITAL_FOR_DEVICE[d.device_type];
                const value = vitalKey ? patient?.latest_reading?.[vitalKey] : null;
                const risk = (patient?.risk_level || "").toLowerCase();
                const ringClass = !online ? "" : risk === "high" ? "crit" : risk === "medium" ? "warn" : "";
                return (
                  <button
                    key={d.id}
                    className="room-marker focus-ring"
                    style={{ top: pos.top, left: pos.left, background: "none", border: "none" }}
                    onClick={() => setSelected(d)}
                    aria-label={`Inspect ${d.device_type.replace(/_/g, " ")} sensor`}
                  >
                    <span
                      className={`room-pulse-ring ${ringClass} ${online ? "alive" : ""}`}
                      style={{ background: online ? (risk === "high" ? "var(--red)" : risk === "medium" ? "var(--amber)" : "var(--green)") : "var(--text-tertiary)" }}
                    />
                    <span className="chip room-chip glass-panel-strong">
                      {VITAL_META[vitalKey]?.icon} {vitalKey ? fmtNum(value, vitalKey === "temperature" ? 1 : 0) : ""} {vitalKey ? VITAL_META[vitalKey].unit : d.device_type.replace(/_/g, " ")}
                    </span>
                  </button>
                );
              })
            )}
            <div className="chip glass-panel-strong" style={{ position: "absolute", top: 14, right: 14 }} title="This system has no camera or motion sensor — shown honestly rather than faking one.">
              {"\u{1F4F7}"} Camera — not available (no camera sensor)
            </div>
          </div>
        </GlassCard>

        <div>
          <div style={{ fontWeight: 650, fontSize: 15, marginBottom: 12 }}>Sensors in this room</div>
          {devices === null ? <LoadingBlock rows={3} /> : devices.length === 0 ? (
            <EmptyBlock title="No devices registered" />
          ) : (
            <div className="flex flex-col gap-8">
              {devices.map((d) => <SensorCard key={d.id} device={d} onClick={() => setSelected(d)} />)}
            </div>
          )}
        </div>
      </div>

      <Drawer open={!!selected} onClose={() => setSelected(null)} title={selected ? selected.device_type.replace(/_/g, " ") : ""}>
        {selected && (
          <div className="flex flex-col gap-12">
            <SensorCard device={selected} />
            <div className="text-secondary" style={{ fontSize: 13 }}>Location: {selected.location || "unassigned"}</div>
            <div className="text-secondary" style={{ fontSize: 13 }}>Simulated device: {selected.is_simulated ? "Yes" : "No"}</div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 12.5, marginBottom: 6 }}>Recent events</div>
              {(!selected.recent_events || selected.recent_events.length === 0) ? (
                <div className="text-tertiary" style={{ fontSize: 12.5 }}>No recent events recorded for this sensor.</div>
              ) : (
                <div className="flex flex-col gap-6">
                  {selected.recent_events.map((ev: any, i: number) => (
                    <div key={i} className="text-secondary" style={{ fontSize: 12, background: "rgba(255,255,255,0.03)", padding: "6px 10px", borderRadius: 8 }}>
                      {typeof ev === "string" ? ev : JSON.stringify(ev)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
