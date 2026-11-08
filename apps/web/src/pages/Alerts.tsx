import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCard } from "../components/AlertCard";
import { LoadingBlock, ErrorBlock, EmptyBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { useToast } from "../components/Toast";
import { alertsApi, patientsApi, type PatientSummary } from "../lib/api";

type Tab = "active" | "acknowledged" | "history";

export default function Alerts() {
  const { subscribe } = useRealtime();
  const { push } = useToast();
  const [alerts, setAlerts] = useState<any[] | null>(null);
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("active");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, p] = await Promise.all([alertsApi.list(false), patientsApi.list()]);
      setAlerts(a);
      setPatients(p);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to load alerts");
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => subscribe((msg) => { if (msg.type === "alert") load(); }), [subscribe, load]);

  const grouped = useMemo(() => {
    const g: Record<Tab, any[]> = { active: [], acknowledged: [], history: [] };
    (alerts || []).forEach((a) => {
      const s = (a.status || "").toUpperCase();
      if (s === "ALERTED" || s === "DETECTED" || s === "ESCALATED") g.active.push(a);
      else if (s === "ACKNOWLEDGED") g.acknowledged.push(a);
      else g.history.push(a);
    });
    Object.values(g).forEach((list) => list.sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()));
    return g;
  }, [alerts]);

  async function runAction(id: number, label: string, fn: () => Promise<any>) {
    setBusyId(id);
    try {
      await fn();
      push(label, "success");
      await load();
    } catch (e: any) {
      push(e?.message || `Failed to ${label.toLowerCase()}`, "error");
    } finally {
      setBusyId(null);
    }
  }

  if (error && !alerts) return <ErrorBlock detail={error} onRetry={load} />;
  if (!alerts) return <LoadingBlock rows={4} />;

  const list = grouped[tab];

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Alerts Center</div>
          <div className="page-subtitle">{grouped.active.length} active · {grouped.acknowledged.length} acknowledged</div>
        </div>
      </div>

      <div className="tab-row" style={{ marginBottom: 18 }} role="tablist">
        <button className={`tab-btn focus-ring ${tab === "active" ? "active" : ""}`} onClick={() => setTab("active")} role="tab" aria-selected={tab === "active"}>Active ({grouped.active.length})</button>
        <button className={`tab-btn focus-ring ${tab === "acknowledged" ? "active" : ""}`} onClick={() => setTab("acknowledged")} role="tab" aria-selected={tab === "acknowledged"}>Acknowledged ({grouped.acknowledged.length})</button>
        <button className={`tab-btn focus-ring ${tab === "history" ? "active" : ""}`} onClick={() => setTab("history")} role="tab" aria-selected={tab === "history"}>History ({grouped.history.length})</button>
      </div>

      {list.length === 0 ? (
        <EmptyBlock title={`No ${tab} alerts`} detail="You're all caught up." />
      ) : (
        <div className="flex flex-col gap-12">
          {list.map((a) => {
            const patientName = patients.find((p) => p.id === a.patient_id)?.full_name;
            return (
              <AlertCard
                key={a.id}
                alert={a}
                patientName={patientName}
                busy={busyId === a.id}
                onAcknowledge={() => runAction(a.id, "Acknowledged", () => alertsApi.acknowledge(a.id))}
                onEscalate={() => runAction(a.id, "Escalated", () => alertsApi.escalate(a.id))}
                onDismiss={(reason) => runAction(a.id, "Dismissed", () => alertsApi.dismiss(a.id, reason))}
                onRespond={(note) => runAction(a.id, "Marked responded", () => alertsApi.respond(a.id, note))}
                onResolve={(note) => runAction(a.id, "Resolved", () => alertsApi.resolve(a.id, note))}
                onAddNote={(note) => runAction(a.id, "Note added", () => alertsApi.addNote(a.id, note))}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
