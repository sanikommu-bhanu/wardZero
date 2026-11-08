import React from "react";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { GlassCard } from "./GlassCard";
import { isOutOfRange, fmtNum } from "../lib/format";

export function VitalCard({
  label, unit, icon, value, digits = 0, history, color = "var(--bronze-soft)", vitalKey, compact = false,
}: {
  label: string; unit: string; icon: string; value: number | null | undefined; digits?: number;
  history?: number[]; color?: string; vitalKey?: string; compact?: boolean;
}) {
  const outOfRange = vitalKey ? isOutOfRange(vitalKey, value) : false;
  let trend: "up" | "down" | "flat" = "flat";
  let trendPct: number | null = null;
  if (history && history.length >= 2) {
    const first = history[0];
    const last = history[history.length - 1];
    if (first !== 0) trendPct = ((last - first) / Math.abs(first)) * 100;
    trend = last > first ? "up" : last < first ? "down" : "flat";
  }

  return (
    <GlassCard className={`vital-card ${outOfRange ? "vital-out-of-range" : ""}`} style={{ padding: compact ? 14 : 18 }}>
      <div className="vital-icon-row">
        <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>
          <span style={{ marginRight: 6, color }}>{icon}</span>{label}
        </span>
        {outOfRange && <span className="badge badge-high" style={{ fontSize: 9.5, padding: "2px 7px" }}>Out of range</span>}
      </div>
      <div>
        <span className="vital-value">{fmtNum(value, digits)}</span>
        <span className="vital-unit">{unit}</span>
      </div>
      <div className="flex items-center justify-between" style={{ minHeight: 28 }}>
        {trendPct !== null ? (
          <span className={`mono vital-trend-${trend}`} style={{ fontSize: 11.5 }}>
            {trend === "up" ? "\u2191" : trend === "down" ? "\u2193" : "\u2192"} {Math.abs(trendPct).toFixed(1)}%
          </span>
        ) : <span />}
        {history && history.length >= 2 ? (
          <div style={{ width: 72, height: 26 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.map((v, i) => ({ i, v }))}>
                <YAxis hide domain={["dataMin - 1", "dataMax + 1"]} />
                <Line type="monotone" dataKey="v" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <span className="text-tertiary" style={{ fontSize: 10 }}>no live history yet</span>
        )}
      </div>
    </GlassCard>
  );
}
