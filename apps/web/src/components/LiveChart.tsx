import React, { useMemo, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { SegmentedFilter } from "./FilterBar";
import { VITAL_META } from "../lib/format";
import type { VitalsPoint } from "../context/RealtimeContext";

const RANGE_MS: Record<string, number> = {
  "5m": 5 * 60 * 1000, "1h": 60 * 60 * 1000, "6h": 6 * 60 * 60 * 1000,
  "12h": 12 * 60 * 60 * 1000, "24h": 24 * 60 * 60 * 1000,
};
const RANGE_OPTIONS = [
  { value: "5m", label: "5m" }, { value: "1h", label: "1h" }, { value: "6h", label: "6h" },
  { value: "12h", label: "12h" }, { value: "24h", label: "24h" },
];
const SERIES_COLORS: Record<string, string> = {
  heart_rate: "#f0554a", spo2: "#4a90d9", temperature: "#f5a623", resp_rate: "#7bd88f",
};

// Draws whatever real "sim_reading" points have actually landed in RealtimeContext's session buffer
// for this patient (see context/RealtimeContext.tsx). There is no historical-readings API to backfill
// from, so a freshly opened page — or a range wider than how long the simulator has been running —
// legitimately shows a short line, not a bug. We say so in the caption rather than padding the chart.
export function LiveChart({ history, seriesKeys = ["heart_rate", "spo2"], height = 260 }: {
  history: VitalsPoint[]; seriesKeys?: string[]; height?: number;
}) {
  const [range, setRange] = useState("1h");

  const data = useMemo(() => {
    const cutoff = Date.now() - RANGE_MS[range];
    return history.filter((p) => p.t >= cutoff).map((p) => ({ ...p, label: new Date(p.t).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }) }));
  }, [history, range]);

  const spanMinutes = data.length >= 2 ? Math.round((data[data.length - 1].t - data[0].t) / 60000) : 0;

  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
        <SegmentedFilter value={range} onChange={setRange} options={RANGE_OPTIONS} />
        <span className="text-tertiary" style={{ fontSize: 11 }}>
          {data.length >= 2
            ? `showing ~${spanMinutes} min of live session data (${data.length} points)`
            : "no live history yet — start the simulator for this patient to see live vitals"}
        </span>
      </div>
      {data.length >= 2 ? (
        <div style={{ width: "100%", height }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="var(--border-glass)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: "var(--text-tertiary)" }} minTickGap={40} />
              <YAxis tick={{ fontSize: 10, fill: "var(--text-tertiary)" }} />
              <Tooltip contentStyle={{ background: "var(--bg-2)", border: "1px solid var(--border-glass-strong)", borderRadius: 10, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} formatter={(v) => VITAL_META[v as string]?.label || v} />
              {seriesKeys.map((k) => (
                <Line key={k} type="monotone" dataKey={k} stroke={SERIES_COLORS[k] || "var(--bronze-soft)"} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="glass-panel empty-state" style={{ minHeight: height * 0.6 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>No live vitals streaming yet</div>
          <div className="text-tertiary" style={{ fontSize: 12.5 }}>Open the IoT Simulator and start a scenario for this patient to see a real-time chart here.</div>
        </div>
      )}
    </div>
  );
}
