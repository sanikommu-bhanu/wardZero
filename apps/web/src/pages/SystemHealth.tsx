import React, { useCallback, useEffect, useState } from "react";
import { GlassCard } from "../components/GlassCard";
import { StatusIndicator } from "../components/StatusIndicator";
import { LoadingBlock, ErrorBlock } from "../components/StateViews";
import { systemApi } from "../lib/api";
import { clock } from "../lib/format";

export default function SystemHealth() {
  const [health, setHealth] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    systemApi.health().then(setHealth).catch((e) => setError(e?.message || "Failed to load system health"));
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  if (error && !health) return <ErrorBlock detail={error} onRetry={load} />;
  if (!health) return <LoadingBlock rows={3} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">System Health</div>
          <div className="page-subtitle">Auto-refreshing every 5s · server time {clock(health.server_time)}</div>
        </div>
      </div>

      <div className="grid grid-cols-3" style={{ marginBottom: 16 }}>
        <GlassCard>
          <div className="text-tertiary" style={{ fontSize: 12, marginBottom: 6 }}>API</div>
          <StatusIndicator status={health.api === "ok" ? "online" : "offline"} />
        </GlassCard>
        <GlassCard>
          <div className="text-tertiary" style={{ fontSize: 12, marginBottom: 6 }}>Database</div>
          <StatusIndicator status={health.database === "ok" ? "online" : "offline"} />
        </GlassCard>
        <GlassCard>
          <div className="text-tertiary" style={{ fontSize: 12, marginBottom: 6 }}>AI Engine</div>
          <StatusIndicator status={health.ai_engine === "ok" ? "online" : "degraded"} />
        </GlassCard>
      </div>

      <div className="two-col">
        <GlassCard hover={false}>
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 14 }}>Realtime &amp; Simulator</div>
          <Row label="WebSocket connections" value={health.websocket_connections} />
          <Row label="Active simulator runs" value={health.simulator?.active_runs} />
        </GlassCard>
        <GlassCard hover={false}>
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 14 }}>Repository Counts</div>
          <Row label="Patients with readings" value={health.repo_counts?.patients_with_readings} />
          <Row label="Total readings ingested" value={health.repo_counts?.total_readings} />
          <Row label="Readings rejected (validation)" value={health.repo_counts?.rejected} />
        </GlassCard>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: any }) {
  return (
    <div className="flex items-center justify-between" style={{ fontSize: 13, borderBottom: "1px solid var(--border-glass)", padding: "8px 0" }}>
      <span className="text-secondary">{label}</span>
      <span className="mono">{value ?? "\u2014"}</span>
    </div>
  );
}
