import React from "react";
import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", icon: "\u25C8", end: true },
  { to: "/patients", label: "Patients", icon: "\u25A4" },
  { to: "/live-monitor", label: "Live Monitor", icon: "\u2248" },
  { to: "/digital-twin", label: "Digital Twin", icon: "\u2b21" },
  { to: "/alerts", label: "Alerts", icon: "\u26A0" },
  { to: "/ai-risk", label: "AI Risk", icon: "\u2726" },
  { to: "/iot-simulator", label: "IoT Simulator", icon: "\u21BB" },
  { to: "/caregiver-notes", label: "Caregiver Notes", icon: "\u270E" },
  { to: "/analytics", label: "Analytics", icon: "\u25A9" },
  { to: "/caregivers", label: "Caregivers", icon: "\u25CE" },
  { to: "/devices", label: "Devices", icon: "\u25A3" },
  { to: "/reports", label: "Reports", icon: "\u2637" },
  { to: "/system-health", label: "System Health", icon: "\u2299" },
  { to: "/settings", label: "Settings", icon: "\u2699" },
];

export function Sidebar() {
  return (
    <aside className="glass-panel-strong" style={{
      width: 232, minHeight: "100vh", position: "sticky", top: 0, borderRadius: 0,
      borderLeft: "none", borderTop: "none", borderBottom: "none", display: "flex", flexDirection: "column",
      padding: "20px 12px", flexShrink: 0,
    }}>
      <div className="flex items-center gap-12" style={{ padding: "6px 10px 22px" }}>
        <div style={{
          width: 34, height: 34, borderRadius: 10, display: "grid", placeItems: "center",
          background: "linear-gradient(135deg, var(--bronze-soft), var(--bronze))", color: "var(--on-bronze)", fontWeight: 800,
        }}>W</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>WardZero AI</div>
          <div className="text-tertiary" style={{ fontSize: 10.5 }}>Home-Care Monitoring</div>
        </div>
      </div>
      <nav style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1, overflowY: "auto" }}>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `focus-ring ${isActive ? "nav-active" : ""}`
            }
            style={({ isActive }) => ({
              display: "flex", alignItems: "center", gap: 12, padding: "9px 12px", borderRadius: 10,
              fontSize: 13.5, color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              background: isActive ? "var(--bronze-dim)" : "transparent",
              fontWeight: isActive ? 600 : 400,
            })}
          >
            <span style={{ width: 16, textAlign: "center", opacity: 0.85 }}>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="text-tertiary" style={{ fontSize: 10.5, padding: "10px 10px 0" }}>
        Synthetic demo data · not a diagnosis
      </div>
    </aside>
  );
}
