"""Durable, SQLite-backed offline event queue (edge/gateway side).

Guarantees: enqueue is idempotent on event_id; events are only removed from `pending` after the server
confirms accepted/duplicate; rejected (malformed) events are kept as `rejected` for audit, never dropped;
a network failure leaves everything pending and stops the flush (no data loss)."""
from __future__ import annotations
import json, sqlite3, time


class OfflineQueue:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS sync_queue(
            event_id TEXT PRIMARY KEY, payload TEXT NOT NULL, event_ts TEXT, enqueued_at REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT)""")
        self.db.commit()

    def enqueue(self, event: dict) -> bool:
        eid = str(event.get("event_id") or f"noid-{time.time_ns()}")
        try:
            self.db.execute("INSERT INTO sync_queue(event_id,payload,event_ts,enqueued_at) VALUES(?,?,?,?)",
                            (eid, json.dumps(event), str(event.get("timestamp")), time.time()))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # already queued

    def pending_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM sync_queue WHERE status='pending'").fetchone()[0]

    def stats(self) -> dict:
        rows = self.db.execute("SELECT status, COUNT(*) FROM sync_queue GROUP BY status").fetchall()
        return {k: v for k, v in rows}

    def flush(self, sender, batch: int = 500) -> dict:
        """sender(event)->{'status': 'accepted'|'duplicate'|'rejected'|'late'} ; raises ConnectionError if offline."""
        res = {"sent": 0, "duplicates": 0, "rejected": 0, "remaining": 0, "interrupted": False}
        rows = self.db.execute("SELECT event_id,payload FROM sync_queue WHERE status='pending' "
                               "ORDER BY event_ts, enqueued_at LIMIT ?", (batch,)).fetchall()
        for eid, payload in rows:
            try:
                r = sender(json.loads(payload))
            except (ConnectionError, TimeoutError, OSError) as e:
                self.db.execute("UPDATE sync_queue SET attempts=attempts+1,last_error=? WHERE event_id=?", (str(e), eid))
                self.db.commit(); res["interrupted"] = True
                break
            status = r.get("status")
            if status == "rejected":
                self.db.execute("UPDATE sync_queue SET status='rejected',last_error=? WHERE event_id=?",
                                (json.dumps(r.get("errors")), eid)); res["rejected"] += 1
            else:
                self.db.execute("UPDATE sync_queue SET status='sent' WHERE event_id=?", (eid,))
                res["duplicates" if status == "duplicate" else "sent"] += 1
        self.db.commit()
        res["remaining"] = self.pending_count()
        return res
