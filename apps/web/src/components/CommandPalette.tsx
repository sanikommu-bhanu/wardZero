import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { patientsApi, type PatientSummary } from "../lib/api";

const ROUTES = [
  { to: "/", label: "Dashboard" }, { to: "/patients", label: "Patients" },
  { to: "/live-monitor", label: "Live Monitor" }, { to: "/digital-twin", label: "Digital Twin" },
  { to: "/alerts", label: "Alerts" }, { to: "/ai-risk", label: "AI Risk" },
  { to: "/iot-simulator", label: "IoT Simulator" }, { to: "/caregiver-notes", label: "Caregiver Notes" },
  { to: "/analytics", label: "Analytics" }, { to: "/caregivers", label: "Caregivers" },
  { to: "/devices", label: "Devices" }, { to: "/reports", label: "Reports" },
  { to: "/system-health", label: "System Health" }, { to: "/settings", label: "Settings" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery(""); setActive(0);
      setTimeout(() => inputRef.current?.focus(), 30);
      patientsApi.list().then(setPatients).catch(() => setPatients([]));
    }
  }, [open]);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const routeItems = ROUTES.map((r) => ({ kind: "route" as const, label: r.label, to: r.to }));
    const patientItems = patients.map((p) => ({ kind: "patient" as const, label: `${p.full_name} (patient)`, to: `/patients/${p.id}` }));
    const all = [...routeItems, ...patientItems];
    return q ? all.filter((i) => i.label.toLowerCase().includes(q)) : all;
  }, [query, patients]);

  function go(to: string) {
    navigate(to);
    setOpen(false);
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="cmdk-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}
        >
          <motion.div
            role="dialog" aria-modal="true" aria-label="Command palette"
            className="glass-panel-strong cmdk-panel"
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
          >
            <input
              ref={inputRef}
              className="input-field focus-ring"
              style={{ padding: "10px 14px", fontSize: 14, marginBottom: 8 }}
              placeholder="Jump to a page or patient..."
              aria-label="Command palette search"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setActive(0); }}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
                else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
                else if (e.key === "Enter" && items[active]) go(items[active].to);
              }}
            />
            {items.length === 0 && <div className="text-tertiary" style={{ padding: "10px 14px", fontSize: 13 }}>No matches</div>}
            {items.map((item, i) => (
              <div
                key={item.to + item.label}
                className={`cmdk-item focus-ring ${i === active ? "active" : ""}`}
                onMouseEnter={() => setActive(i)}
                onClick={() => go(item.to)}
                role="option"
                aria-selected={i === active}
              >
                <span>{item.label}</span>
                <span className="text-tertiary" style={{ fontSize: 11 }}>{item.kind === "patient" ? "Patient" : "Page"}</span>
              </div>
            ))}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
