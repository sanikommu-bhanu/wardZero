import React from "react";

export function riskClass(level?: string | null) {
  const l = (level || "").toLowerCase();
  if (l === "high") return "badge-high";
  if (l === "medium") return "badge-medium";
  if (l === "low" || l === "stable") return "badge-low";
  return "badge-unknown";
}

export function RiskBadge({ level }: { level?: string | null }) {
  const label = level ? level.charAt(0).toUpperCase() + level.slice(1) : "Unknown";
  return <span className={`badge ${riskClass(level)}`}>{label}</span>;
}

export function StatusIndicator({ status }: { status?: string | null }) {
  const s = (status || "").toLowerCase();
  const dot = s === "online" || s === "running" || s === "ok" ? "status-green"
    : s === "paused" || s === "degraded" ? "status-amber"
    : s === "offline" || s === "stopped" || s === "unavailable" ? "status-red" : "status-grey";
  return (
    <span className="flex items-center gap-8">
      <span className={`status-dot ${dot}`} />
      <span className="text-secondary" style={{ fontSize: 12.5, textTransform: "capitalize" }}>{status || "unknown"}</span>
    </span>
  );
}
