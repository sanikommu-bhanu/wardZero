import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import { wsClient, WsMessage } from "../lib/ws";
import { useAuth } from "./AuthContext";
import { patientsApi } from "../lib/api";

interface QueuedAction { id: string; label: string; run: () => Promise<any>; queuedAt: number }

// One point of real, received vitals. Only ever pushed from an actual "sim_reading" WS broadcast
// (apps/api/simulator_manager.py) — never fabricated, interpolated or backfilled. Because the API has
// no GET-history-of-readings endpoint, this in-memory buffer is the only place multi-point vitals
// history exists at all; it starts empty on every page load / server restart, on purpose.
export interface VitalsPoint {
  t: number; heart_rate?: number; spo2?: number; temperature?: number; resp_rate?: number;
  systolic_bp?: number; diastolic_bp?: number; activity?: number;
}
const MAX_HISTORY_POINTS = 500;

// Sensor timestamps arrive as ISO strings or epoch seconds; fall back to receipt time only if absent.
export function readingTime(ts: unknown): number {
  if (typeof ts === "number") return ts < 1e12 ? ts * 1000 : ts;
  const parsed = typeof ts === "string" ? Date.parse(ts) : NaN;
  return Number.isFinite(parsed) ? parsed : Date.now();
}

function toPoint(r: Record<string, any>): VitalsPoint {
  return {
    t: readingTime(r.timestamp), heart_rate: r.heart_rate, spo2: r.spo2, temperature: r.temperature,
    resp_rate: r.resp_rate, systolic_bp: r.systolic_bp, diastolic_bp: r.diastolic_bp, activity: r.activity,
  };
}

// Merge by timestamp so WebSocket points and history fetched from GET /patients/{id}/readings never
// double-count, and late / out-of-order points land in order.
export function mergePoints(a: VitalsPoint[], b: VitalsPoint[]): VitalsPoint[] {
  const byT = new Map<number, VitalsPoint>();
  for (const p of [...a, ...b]) byT.set(p.t, p);
  return [...byT.values()].sort((x, y) => x.t - y.t).slice(-MAX_HISTORY_POINTS);
}

interface RealtimeContextValue {
  wsConnected: boolean;
  browserOnline: boolean;
  lastMessage: WsMessage | null;
  lastSyncAt: number | null;
  queuedActions: QueuedAction[];
  subscribe: (fn: (msg: WsMessage) => void) => () => void;
  enqueueAction: (label: string, run: () => Promise<any>) => void;
  vitalsHistory: Record<string, VitalsPoint[]>;
  getVitalsHistory: (patientId: string) => VitalsPoint[];
  hydrateHistory: (patientId: string, limit?: number) => Promise<void>;
  historyStatus: Record<string, "loading" | "ready" | "error">;
  riskAssessments: Record<string, any>;
  getRiskAssessment: (patientId: string) => any | null;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [wsConnected, setWsConnected] = useState(false);
  const [browserOnline, setBrowserOnline] = useState(navigator.onLine);
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const [lastSyncAt, setLastSyncAt] = useState<number | null>(null);
  const [queuedActions, setQueuedActions] = useState<QueuedAction[]>([]);
  const [vitalsHistory, setVitalsHistory] = useState<Record<string, VitalsPoint[]>>({});
  const [riskAssessments, setRiskAssessments] = useState<Record<string, any>>({});
  const [historyStatus, setHistoryStatus] = useState<Record<string, "loading" | "ready" | "error">>({});
  const subscribers = useRef(new Set<(msg: WsMessage) => void>());

  useEffect(() => {
    if (!user) return;
    wsClient.connect();
    const offMsg = wsClient.onMessage((msg) => {
      setLastMessage(msg);
      setLastSyncAt(Date.now());
      subscribers.current.forEach((fn) => fn(msg));
      if (msg.type === "sim_reading" && msg.patient_id && msg.reading) {
        const r = msg.reading as Record<string, any>;
        const point = toPoint(r);
        const pid = msg.patient_id as string;
        setVitalsHistory((h) => ({ ...h, [pid]: mergePoints(h[pid] || [], [point]) }));
        if (msg.risk_assessment) {
          setRiskAssessments((ra) => ({ ...ra, [pid]: msg.risk_assessment }));
        }
      }
    });
    const offConn = wsClient.onConnectionChange((c) => {
      setWsConnected(c);
      if (c) setLastSyncAt(Date.now());
    });
    return () => { offMsg(); offConn(); wsClient.disconnect(); };
  }, [user]);

  useEffect(() => {
    const on = () => setBrowserOnline(true);
    const off = () => setBrowserOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  // Drain the queue whenever we come back online.
  useEffect(() => {
    if (!browserOnline || queuedActions.length === 0) return;
    (async () => {
      for (const action of queuedActions) {
        try {
          await action.run();
        } catch {
          // leave it queued if it still fails
          return;
        }
      }
      setQueuedActions([]);
      setLastSyncAt(Date.now());
    })();
  }, [browserOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  const subscribe = useCallback((fn: (msg: WsMessage) => void) => {
    subscribers.current.add(fn);
    return () => subscribers.current.delete(fn);
  }, []);

  const enqueueAction = useCallback((label: string, run: () => Promise<any>) => {
    setQueuedActions((q) => [...q, { id: `${Date.now()}-${Math.random()}`, label, run, queuedAt: Date.now() }]);
  }, []);

  // Load persisted history from the API (SQLite-backed) so charts survive a page reload.
  const hydrateHistory = useCallback(async (patientId: string, limit = 300) => {
    setHistoryStatus((s) => ({ ...s, [patientId]: "loading" }));
    try {
      const res = await patientsApi.readings(patientId, limit);
      const pts = (res.readings || []).map(toPoint);
      setVitalsHistory((h) => ({ ...h, [patientId]: mergePoints(h[patientId] || [], pts) }));
      setHistoryStatus((s) => ({ ...s, [patientId]: "ready" }));
    } catch {
      setHistoryStatus((s) => ({ ...s, [patientId]: "error" }));
    }
  }, []);

  const getVitalsHistory = useCallback((patientId: string) => vitalsHistory[patientId] || [], [vitalsHistory]);
  const getRiskAssessment = useCallback((patientId: string) => riskAssessments[patientId] || null, [riskAssessments]);

  return (
    <RealtimeContext.Provider value={{
      wsConnected, browserOnline, lastMessage, lastSyncAt, queuedActions, subscribe, enqueueAction,
      vitalsHistory, getVitalsHistory, hydrateHistory, historyStatus, riskAssessments, getRiskAssessment,
    }}>
      {children}
    </RealtimeContext.Provider>
  );
}

export function useRealtime() {
  const ctx = useContext(RealtimeContext);
  if (!ctx) throw new Error("useRealtime must be used within RealtimeProvider");
  return ctx;
}
