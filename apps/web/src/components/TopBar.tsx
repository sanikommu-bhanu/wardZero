import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useRealtime } from "../context/RealtimeContext";
import { alertsApi } from "../lib/api";

export function TopBar() {
  const { user, signOut } = useAuth();
  const { wsConnected } = useRealtime();
  const navigate = useNavigate();
  const [now, setNow] = useState(new Date());
  const [openAlerts, setOpenAlerts] = useState(0);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000 * 30);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    let mounted = true;
    alertsApi.list(true).then((a) => mounted && setOpenAlerts(a.length)).catch(() => {});
    return () => { mounted = false; };
  }, []);

  return (
    <header className="glass-panel" style={{
      position: "sticky", top: 0, zIndex: 20, borderRadius: 0, borderLeft: "none", borderRight: "none", borderTop: "none",
      display: "flex", alignItems: "center", gap: 16, padding: "12px 24px",
    }}>
      <form
        style={{ flex: 1, maxWidth: 380 }}
        onSubmit={(e) => {
          e.preventDefault();
          if (search.trim()) navigate(`/patients?q=${encodeURIComponent(search.trim())}`);
        }}
      >
        <input
          className="input-field focus-ring"
          placeholder="Search patients, alerts, rooms..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ padding: "9px 14px", fontSize: 13 }}
        />
      </form>

      <div className="flex items-center gap-8" title={wsConnected ? "Realtime connected" : "Realtime disconnected — reconnecting"}>
        <span className={`status-dot ${wsConnected ? "status-green" : "status-red"}`} />
        <span className="text-secondary" style={{ fontSize: 12.5 }}>{wsConnected ? "Live" : "Reconnecting..."}</span>
      </div>

      <button className="glass-btn glass-btn-sm focus-ring" onClick={() => navigate("/alerts")} style={{ position: "relative" }}>
        {"\u26A0"} Alerts
        {openAlerts > 0 && (
          <span style={{
            position: "absolute", top: -6, right: -6, background: "var(--red)", color: "#fff",
            borderRadius: 999, fontSize: 10, minWidth: 16, height: 16, display: "grid", placeItems: "center", padding: "0 4px",
          }}>{openAlerts}</span>
        )}
      </button>

      <div className="mono text-secondary" style={{ fontSize: 12 }}>
        {now.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })} · {now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
      </div>

      <div className="flex items-center gap-8">
        <div style={{
          width: 30, height: 30, borderRadius: "50%", background: "var(--bronze-dim)", color: "var(--bronze-soft)",
          display: "grid", placeItems: "center", fontWeight: 700, fontSize: 12.5,
        }}>{(user?.email || "?").charAt(0).toUpperCase()}</div>
        <div style={{ lineHeight: 1.15 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600 }}>{user?.email?.split("@")[0] || "User"}</div>
          <div className="text-tertiary" style={{ fontSize: 10.5, textTransform: "capitalize" }}>{user?.role}</div>
        </div>
        <button className="glass-btn glass-btn-sm focus-ring" onClick={signOut} title="Log out">{"\u23FB"}</button>
      </div>
    </header>
  );
}
