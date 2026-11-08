// Shared offline machinery: durable queue + chaos switches + simulated power, used by the chaos panel
// and any page that ingests readings from the browser.
import { EventQueue, MemoryStore, QueueStore, FlushResult } from "./queueCore";
import { IdbStore } from "./idbStore";
import { readingsApi } from "./api";

function makeStore(): QueueStore {
  try { if (typeof indexedDB !== "undefined") return new IdbStore(); } catch { /* fall through */ }
  return new MemoryStore();
}

export const queue = new EventQueue(makeStore());

export interface ChaosState {
  networkCut: boolean;
  mains: boolean;
  batteryPct: number;
  powerState: "mains" | "ups_battery" | "shutdown";
  lastFlush: FlushResult | null;
}

const DRAIN = 2;   // % per second while on battery (demo-speed; mirrors apps/simulator/chaos.py PowerModel)
const CHARGE = 1;
const SHUTDOWN_BELOW = 5;

let state: ChaosState = { networkCut: false, mains: true, batteryPct: 100, powerState: "mains", lastFlush: null };
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());

export const chaos = {
  get: () => state,
  subscribe: (f: () => void) => { subs.add(f); return () => { subs.delete(f); }; },
  set(patch: Partial<ChaosState>) { state = { ...state, ...patch }; emit(); },
  cutNetwork: () => chaos.set({ networkCut: true }),
  restoreNetwork: () => chaos.set({ networkCut: false }),
  cutPower: () => chaos.set({ mains: false, powerState: state.batteryPct <= SHUTDOWN_BELOW ? "shutdown" : "ups_battery" }),
  restorePower: () => chaos.set({ mains: true, powerState: "mains" }),
  /** advance the UPS model one second */
  tickPower() {
    const b = state.mains ? Math.min(100, state.batteryPct + CHARGE) : Math.max(0, state.batteryPct - DRAIN);
    const ps = state.mains ? "mains" : b <= SHUTDOWN_BELOW ? "shutdown" : "ups_battery";
    if (b !== state.batteryPct || ps !== state.powerState) chaos.set({ batteryPct: b, powerState: ps });
  },
  canTransmit: () => state.powerState !== "shutdown",
};

/** Sender used by queue.flush: honours the simulated network cut, else calls POST /readings/batch. */
export async function sendBatch(items: { event: Record<string, unknown>; context: Record<string, unknown> }[]) {
  if (state.networkCut || (typeof navigator !== "undefined" && navigator.onLine === false)) throw new Error("network_unreachable");
  return readingsApi.batch(items);
}

export async function flushQueue(): Promise<FlushResult | null> {
  if (!chaos.canTransmit()) return null;       // device is powered down: data stays safely queued
  const r = await queue.flush(sendBatch);
  chaos.set({ lastFlush: r });
  return r;
}

/** Record a reading durably first, then try to send. Never throws on network failure. */
export async function submitReading(event: Record<string, unknown>, context: Record<string, unknown> = {}) {
  await queue.enqueue(event, context);
  return flushQueue();
}
