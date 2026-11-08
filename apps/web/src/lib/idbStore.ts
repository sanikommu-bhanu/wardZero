import type { QueueStore, QueuedEvent } from "./queueCore";

// IndexedDB-backed QueueStore so queued readings survive tab close, reload and browser restart.
// Falls back to MemoryStore (see offline.ts) if IndexedDB is unavailable (private mode etc.).
export class IdbStore implements QueueStore {
  private dbp: Promise<IDBDatabase>;
  constructor(name = "wardzero-queue") {
    this.dbp = new Promise((resolve, reject) => {
      const req = indexedDB.open(name, 1);
      req.onupgradeneeded = () => req.result.createObjectStore("events", { keyPath: "event_id" });
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  private async tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    const db = await this.dbp;
    return new Promise((resolve, reject) => {
      const r = fn(db.transaction("events", mode).objectStore("events"));
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(r.error);
    });
  }
  async put(i: QueuedEvent) { await this.tx("readwrite", (s) => s.put(i)); }
  async get(id: string) { return (await this.tx("readonly", (s) => s.get(id))) as QueuedEvent | undefined; }
  async all() { return (await this.tx("readonly", (s) => s.getAll())) as QueuedEvent[]; }
  async delete(id: string) { await this.tx("readwrite", (s) => s.delete(id)); }
}
