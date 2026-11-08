import React, { useCallback, useEffect, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { GlassCard } from "../components/GlassCard";
import { LoadingBlock, ErrorBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { analyticsApi } from "../lib/api";

const RISK_COLORS: Record<string, string> = { high: "#f0554a", medium: "#f5a623", low: "#4ade80", unknown: "#7c7369" };

export default function Analytics() {
  const { subscribe } = useRealtime();
  const [summary, setSummary] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    analyticsApi.summary().then(setSummary).catch((e) => setError(e?.message || "Failed to load analytics"));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => subscribe(() => load()), [subscribe, load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  if (error && !summary) return <ErrorBlock detail={error} onRetry={load} />;
  if (!summary) return <LoadingBlock rows={4} />;

  const dist = summary.risk_distribution || {};
  const pieData = Object.entries(dist).map(([k, v]) => ({ name: k, value: v as number }));

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Analytics &amp; Reports</div>
          <div className="page-subtitle">Ward-wide numbers computed live from real backend state.</div>
        </div>
      </div>

      <div className="grid grid-cols-4" style={{ marginBottom: 20 }}>
        <GlassCard><div className="kpi-value">{summary.total_patients}</div><div className="kpi-label">Total Patients</div></GlassCard>
        <GlassCard><div className="kpi-value">{summary.active_alerts}</div><div className="kpi-label">Active Alerts</div></GlassCard>
        <GlassCard><div className="kpi-value">{summary.total_alerts}</div><div className="kpi-label">Total Alerts (all time)</div></GlassCard>
        <GlassCard><div className="kpi-value">{summary.simulations_running}</div><div className="kpi-label">Simulations Running</div></GlassCard>
      </div>

      <div className="two-col">
        <GlassCard hover={false}>
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 8 }}>Risk Distribution</div>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={2}>
                  {pieData.map((d) => <Cell key={d.name} fill={RISK_COLORS[d.name] || "#7c7369"} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "var(--bg-2)", border: "1px solid var(--border-glass-strong)", borderRadius: 10 }} />
                <Legend wrapperStyle={{ fontSize: 12, textTransform: "capitalize" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard hover={false}>
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 14 }}>Repository Counts</div>
          <div className="flex flex-col gap-10">
            <Row label="Patients with readings" value={summary.repo_counts?.patients_with_readings} />
            <Row label="Total readings ingested" value={summary.repo_counts?.total_readings} />
            <Row label="Readings rejected (validation)" value={summary.repo_counts?.rejected} />
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: any }) {
  return (
    <div className="flex items-center justify-between" style={{ fontSize: 13, borderBottom: "1px solid var(--border-glass)", paddingBottom: 8 }}>
      <span className="text-secondary">{label}</span>
      <span className="mono">{value ?? "\u2014"}</span>
    </div>
  );
}
