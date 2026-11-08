import { test } from "node:test";
import type { BatchSender } from "./queueCore.ts";
import assert from "node:assert/strict";
import { EventQueue, MemoryStore } from "./queueCore.ts";

// A fake server with the same contract as POST /readings/batch (idempotent on event_id).
function fakeServer() {
  const stored = new Set<string>();
  let up = true;
  const send: BatchSender = async (items) => {
    if (!up) throw new Error("network");
    return { results: items.map(({ event }) => {
      const id = String(event.event_id);
      if (!event.heart_rate) return { event_id: id, status: "rejected" };
      if (stored.has(id)) return { event_id: id, status: "duplicate" };
      stored.add(id); return { event_id: id, status: "accepted" };
    }) };
  };
  return { stored, send, setUp: (v: boolean) => { up = v; } };
}
const ev = (i: number) => ({ event_id: `e${i}`, timestamp: 1000 + i, heart_rate: 70 });

test("network cut: nothing lost, replay delivers every event exactly once", async () => {
  const q = new EventQueue(new MemoryStore()); const s = fakeServer();
  for (let i = 0; i < 50; i++) await q.enqueue(ev(i));
  s.setUp(false);
  const r1 = await q.flush(s.send);
  assert.equal(r1.interrupted, true); assert.equal(r1.remaining, 50); assert.equal(s.stored.size, 0);
  s.setUp(true);
  const r2 = await q.flush(s.send);
  assert.equal(r2.sent, 50); assert.equal(r2.remaining, 0); assert.equal(s.stored.size, 50);
});

test("duplicate enqueue and duplicate replay are idempotent", async () => {
  const q = new EventQueue(new MemoryStore()); const s = fakeServer();
  assert.equal(await q.enqueue(ev(1)), true); assert.equal(await q.enqueue(ev(1)), false);
  await q.flush(s.send);
  await q.enqueue(ev(1)); // re-queued after the server already has it
  const r = await q.flush(s.send);
  assert.equal(r.duplicates, 1); assert.equal(s.stored.size, 1);
});

test("late events are replayed in sensor-time order", async () => {
  const q = new EventQueue(new MemoryStore()); const order: string[] = [];
  for (const i of [5, 2, 9, 1]) await q.enqueue(ev(i));
  await q.flush(async (items) => { items.forEach((x) => order.push(String(x.event.event_id))); return { results: items.map((x) => ({ event_id: String(x.event.event_id), status: "accepted" })) }; });
  assert.deepEqual(order, ["e1", "e2", "e5", "e9"]);
});

test("rejected events are kept for audit, not dropped", async () => {
  const q = new EventQueue(new MemoryStore()); const s = fakeServer();
  await q.enqueue({ event_id: "bad", timestamp: 1 });
  await q.flush(s.send);
  assert.deepEqual(await q.stats(), { pending: 0, rejected: 1 });
});
