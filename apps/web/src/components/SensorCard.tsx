import React from "react";
import { GlassCard } from "./GlassCard";
import { StatusIndicator } from "./StatusIndicator";
import type { Device } from "../lib/api";

// Honest connection label (PROMPT 4 section 4: the UI must distinguish REAL HARDWARE / SIMULATED
// DEVICE / OFFLINE / UNKNOWN). Falls back to deriving from is_simulated + connectivity when an older
// backend does not send connection_status, so this never claims real hardware it cannot know about.
function connectionLabel(d: Device): { text: string; color: string } {
  const st = d.connection_status
    ?? ((d.connectivity || "").toLowerCase() === "online" ? (d.is_simulated ? "simulated" : "real_hardware") : "offline");
  switch (st) {
    case "real_hardware": return { text: "REAL HARDWARE", color: "var(--green)" };
    case "simulated": return { text: "SIMULATED DEVICE", color: "var(--bronze-soft)" };
    case "offline": return { text: "OFFLINE", color: "var(--red)" };
    default: return { text: "UNKNOWN", color: "var(--text-tertiary)" };
  }
}

const DEVICE_ICON: Record<string, string> = {
  heart_rate: "\u2665", spo2: "\u2740", temperature: "\u2600", respiratory_rate: "\u2248",
  blood_pressure: "\u2b06", fall_detector: "\u26A0", default: "\u25A3",
};

export function SensorCard({ device, onClick, compact = false }: { device: Device; onClick?: () => void; compact?: boolean }) {
  const icon = DEVICE_ICON[device.device_type] || DEVICE_ICON.default;
  const conn = connectionLabel(device);
  const battery = device.battery_pct;
  const batteryColor = battery == null ? "var(--text-tertiary)" : battery < 20 ? "var(--red)" : battery < 50 ? "var(--amber)" : "var(--green)";
  return (
    <GlassCard className="sensor-card focus-ring" onClick={onClick} style={{ padding: compact ? 10 : 14 }}>
      <div className="sensor-swatch" style={{ background: "var(--bronze-dim)", color: "var(--bronze-soft)", fontSize: 15 }}>
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {device.device_type.replace(/_/g, " ")}
        </div>
        <div className="text-tertiary" style={{ fontSize: 11 }}>{device.location || "unassigned room"}</div>
        <div className="mono" style={{ fontSize: 10, letterSpacing: 0.4, color: conn.color, marginTop: 2 }}>{conn.text}</div>
        {!compact && device.device_model && (
          <div className="text-tertiary" style={{ fontSize: 10.5, marginTop: 2 }}>
            {device.device_model}{device.firmware_version ? ` \u00b7 fw ${device.firmware_version}` : ""}
          </div>
        )}
        {!compact && (
          <div className="text-tertiary" style={{ fontSize: 10.5 }}>
            {device.last_seen ? `last seen ${new Date(device.last_seen).toLocaleTimeString()}` : "never seen this session"}
          </div>
        )}
      </div>
      <div style={{ textAlign: "right" }}>
        <StatusIndicator status={device.connectivity} />
        <div className="mono" style={{ fontSize: 11, color: batteryColor, marginTop: 3 }}>
          {battery == null ? "battery n/a" : `${battery}% battery`}
        </div>
      </div>
    </GlassCard>
  );
}
