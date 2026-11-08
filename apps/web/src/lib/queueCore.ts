// Offline event queue core: framework-free so it is unit-tested with plain Node (see queueCore.test.ts).
// Guarantees: enqueue is idempotent on event_id; an event leaves the queue only after the server confirms
// accepted/duplicate; a thrown network error stops the flush and keeps everything; rejected events are
// kept (status "rejected") for audit rather than dropped.

export interface QueuedEvent {
  event_id: string;
  timestamp: string | number;
  event: Record<string, unknown>;
  context: Record<string, unknown>;
  status: "pending" | "rejected";
  attempts: number;
  enqueuedAt: number;
}

export interface QueueStore {
  put(item: QueuedEvent): Promise<void>;
  get(id: string): Promise<QueuedEvent | undefined>;
  all(): Promise<QueuedEvent[]>;
  delete(id: string): Promise<void>;
}

export class MemoryStore implements QueueStore {
  private m = new Map<string, QueuedEvent>();
  async put(i: QueuedEvent) { this.m.set(i.event_id, { ...i }); }
  async get(id: string) { const v = this.m.get(id); return v ? { ...v } : undefined; }
  async all() { return [...this.m.values()].map((v) => ({ ...v })); }
  async delete(id: string) { this.m.delete(id); }
}

export type BatchSender = (items: { event: Record<string, unknown>; context: Record<string, unknown> }[]) =>
  Promise<{ results: { event_id: string; status: string }[] }>;

export interface FlushResult { sent: number; duplicates: number; rejected: number; remaining: number; interrupted: boolean }

export class EventQueue {
  private store: QueueStore;
  private now: () => number;
  constructor(store: QueueStore, now: () => number = Date.now) { this.store = store; this.now = now; }

  /** Returns false if this event_id is already queued (idempotent). */
  async enqueue(event: Record<string, unknown>, context: Record<string, unknown> = {}): Promise<boolean> {
    const id = String(event.event_id ?? "");
    if (!id) throw new Error("event_id required for idempotent replay");
    if (await this.store.get(id)) return false;
    await this.store.put({ event_id: id, timestamp: event.timestamp as any, event, context, status: "pending", attempts: 0, enqueuedAt: this.now() });
    return true;
  }

  async pending(): Promise<QueuedEvent[]> {
    return (await this.store.all()).filter((i) => i.status === "pending")
      .sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp), undefined, { numeric: true }) || a.enqueuedAt - b.enqueuedAt);
  }

  async stats() {
    const all = await this.store.all();
    return { pending: all.filter((i) => i.status === "pending").length, rejected: all.filter((i) => i.status === "rejected").length };
  }

  async flush(send: BatchSender, batchSize = 100): Promise<FlushResult> {
    const res: FlushResult = { sent: 0, duplicates: 0, rejected: 0, remaining: 0, interrupted: false };
    const items = await this.pending();
    for (let i = 0; i < items.length; i += batchSize) {
      const chunk = items.slice(i, i + batchSize);
      let out;
      try {
        out = await send(chunk.map((c) => ({ event: c.event, context: c.context })));
      } catch {
        for (const c of chunk) await this.store.put({ ...c, attempts: c.attempts + 1 });
        res.interrupted = true;
        break;
      }
      const byId = new Map(out.results.map((r) => [r.event_id, r.status]));
      for (const c of chunk) {
        const st = byId.get(c.event_id);
        if (st === "accepted") { await this.store.delete(c.event_id); res.sent++; }
        else if (st === "duplicate") { await this.store.delete(c.event_id); res.duplicates++; }
        else if (st === "rejected") { await this.store.put({ ...c, status: "rejected" }); res.rejected++; }
        // "error"/missing: stays pending, retried next flush (never dropped)
      }
    }
    res.remaining = (await this.stats()).pending;
    return res;
  }
}
