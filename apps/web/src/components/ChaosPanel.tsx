import React, { useCallback, useEffect, useState } from "react";
import { GlassCard, GlassButton } from "./GlassCard";
import { chaos, flushQueue, queue, submitReading, type ChaosState } from "../lib/offline";

// Chaos / resilience panel: cut network, cut power (UPS battery drains, then device shuts down), sensor
// dropout, duplicate and late events. Every reading goes through the durable IndexedDB queue and is
// replayed idempotently, so the counters below demonstrate "no data loss" live.

let seq = 0;
function makeReading(patientId: string, ts = Date.now()) {
  seq += 1;
  return {
    event_id: `chaos-${patientId}-${ts}-${seq}`, patient_id: patientId, device_id: `${patientId}-vitals`,
    timestamp: new Date(ts).toISOString(), heart_rate: 70 + (seq % 6), spo2: 97, temperature: 36.8,
    resp_rate: 16, systolic_bp: 120, diastolic_bp: 78,
  };
}

export function ChaosPanel({ patientId }: { patientId: string }) {
  const [st, setSt] = useState<ChaosState>(chaos.get());
  const [q, setQ] = useState({ pending: 0, rejected: 0 });
  const [log, setLog] = useState<string[]>([]);
  const [sentTotal, setSentTotal] = useState(0);
  const [madeTotal, setMadeTotal] = useState(0);
  const [dropout, setDropout] = useState(false);

  const refresh = useCallback(async () => setQ(await queue.stats()), []);
  const note = (m: string) => setLog((l) => [`${new Date().toLocaleTimeString()}  ${m}`, ...l].slice(0, 8));

  useEffect(() => chaos.subscribe(() => setSt(chaos.get())), []);
  useEffect(() => { refresh(); }, [refresh, st.lastFlush]);
  useEffect(() => { const id = setInterval(() => chaos.tickPower(), 1000); return () => clearInterval(id); }, []);

  const flush = async () => {
    const r = await flushQueue();
    if (r) { setSentTotal((n) => n + r.sent); note(r.interrupted ? "link down - events kept in queue" : `replayed: ${r.sent} new, ${r.duplicates} duplicate`); }
    else note("device powered down - events kept in queue");
    refresh();
  };

  // auto-replay when the link or power comes back
  useEffect(() => { if (!st.networkCut && st.powerState !== "shutdown") { flushQueue().then(refresh); } }, [st.networkCut, st.powerState, refresh]);

  const emit = async (n = 1, opts: { dup?: number; late?: boolean } = {}) => {
    if (!patientId) return;
    if (dropout) { note("sensor dropout: reading not produced (gap will show in history)"); return; }
    if (st.powerState === "shutdown") { note("device is off: no reading produced"); return; }
    const base = Date.now();
    let evs = Array.from({ length: n }, (_, i) => makeReading(patientId, base - (n - i) * 300000));
    setMadeTotal((m) => m + evs.length);
    if (opts.late) evs = [...evs].reverse();
    for (const e of evs) { for (let k = 0; k <= (opts.dup ?? 0); k++) await submitReading(e, { age: 70 }); }
    note(`${evs.length} reading(s) recorded${opts.dup ? ` (each sent ${opts.dup + 1}x)` : ""}${opts.late ? " out of order" : ""}`);
    refresh();
  };

  const stateLabel = { mains: "Mains power", ups_battery: "On UPS battery", shutdown: "Device shut down" }[st.powerState];
  const batteryColor = st.batteryPct > 40 ? "var(--green, #4caf7d)" : st.batteryPct > 15 ? "var(--amber, #e0a030)" : "var(--red, #d9534f)";

  return (
    <GlassCard hover={false} style={{ marginTop: 20 }}>
      <div className="section-title">Resilience / chaos panel</div>
      <p className="text-tertiary" style={{ fontSize: 12, marginTop: 4 }}>
        Break things on purpose. Readings are written to a durable local queue first, then replayed idempotently.
      </p>

      <div role="status" aria-live="polite" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12, margin: "14px 0" }}>
        <div><div className="text-tertiary" style={{ fontSize: 11 }}>Network</div><strong>{st.networkCut ? "CUT" : "Connected"}</strong></div>
        <div><div className="text-tertiary" style={{ fontSize: 11 }}>Power</div><strong>{stateLabel}</strong></div>
        <div>
          <div className="text-tertiary" style={{ fontSize: 11 }}>UPS battery {Math.round(st.batteryPct)}%</div>
          <div style={{ height: 8, borderRadius: 4, background: "rgba(255,255,255,.12)", marginTop: 6 }} aria-hidden="true">
            <div style={{ width: `${st.batteryPct}%`, height: 8, borderRadius: 4, background: batteryColor, transition: "width .5s" }} />
          </div>
        </div>
        <div><div className="text-tertiary" style={{ fontSize: 11 }}>Queued (not yet sent)</div><strong>{q.pending}</strong></div>
        <div><div className="text-tertiary" style={{ fontSize: 11 }}>Produced / delivered</div><strong>{madeTotal} / {sentTotal}</strong></div>
        <div><div className="text-tertiary" style={{ fontSize: 11 }}>Rejected (kept for audit)</div><strong>{q.rejected}</strong></div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        <GlassButton onClick={() => (st.networkCut ? chaos.restoreNetwork() : chaos.cutNetwork())}>{st.networkCut ? "Restore network" : "Cut network"}</GlassButton>
        <GlassButton onClick={() => (st.mains ? chaos.cutPower() : chaos.restorePower())}>{st.mains ? "Cut power" : "Restore power"}</GlassButton>
        <GlassButton onClick={() => { setDropout((d) => !d); note(dropout ? "sensor back online" : "sensor dropout started"); }}>{dropout ? "End sensor dropout" : "Sensor dropout"}</GlassButton>
        <GlassButton onClick={() => emit(1)}>Send 1 reading</GlassButton>
        <GlassButton onClick={() => emit(10)}>Send 10 readings</GlassButton>
        <GlassButton onClick={() => emit(5, { dup: 2 })}>Duplicate burst (x3)</GlassButton>
        <GlassButton onClick={() => emit(8, { late: true })}>Late / out-of-order</GlassButton>
        <GlassButton onClick={flush}>Replay queue now</GlassButton>
      </div>

      <ul style={{ marginTop: 14, fontSize: 12, listStyle: "none", padding: 0 }} aria-label="Chaos event log">
        {log.length === 0 ? <li className="text-tertiary">No chaos events yet.</li> : log.map((l, i) => <li key={i} className="text-tertiary">{l}</li>)}
      </ul>
    </GlassCard>
  );
}
