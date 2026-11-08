import unittest
from services.sync_engine.queue import OfflineQueue


def ev(eid, ts="2026-01-01T00:00:00Z"):
    return {"event_id": eid, "timestamp": ts, "vitals": {"heart_rate": 80}}


class TestEnqueue(unittest.TestCase):
    def setUp(self):
        self.q = OfflineQueue(":memory:")

    def test_enqueue_and_count(self):
        self.assertTrue(self.q.enqueue(ev("d1-1")))
        self.assertTrue(self.q.enqueue(ev("d1-2")))
        self.assertEqual(self.q.pending_count(), 2)

    def test_enqueue_idempotent_on_event_id(self):
        self.assertTrue(self.q.enqueue(ev("d1-1")))
        self.assertFalse(self.q.enqueue(ev("d1-1")))  # duplicate insert rejected
        self.assertEqual(self.q.pending_count(), 1)

    def test_missing_event_id_gets_synthetic_id_and_still_enqueues(self):
        self.assertTrue(self.q.enqueue({"timestamp": "t"}))
        self.assertEqual(self.q.pending_count(), 1)

    def test_stats_empty(self):
        self.assertEqual(self.q.stats(), {})


class TestFlush(unittest.TestCase):
    def setUp(self):
        self.q = OfflineQueue(":memory:")
        for i in range(1, 4):
            self.q.enqueue(ev(f"d1-{i}", ts=f"2026-01-01T00:0{i}:00Z"))

    def test_flush_all_accepted(self):
        res = self.q.flush(lambda e: {"status": "accepted"})
        self.assertEqual(res, {"sent": 3, "duplicates": 0, "rejected": 0, "remaining": 0, "interrupted": False})
        self.assertEqual(self.q.pending_count(), 0)
        self.assertEqual(self.q.stats(), {"sent": 3})

    def test_flush_sends_in_event_ts_order(self):
        order = []

        def sender(e):
            order.append(e["event_id"])
            return {"status": "accepted"}
        self.q.flush(sender)
        self.assertEqual(order, ["d1-1", "d1-2", "d1-3"])

    def test_flush_mixed_outcomes(self):
        outcomes = iter([{"status": "accepted"}, {"status": "duplicate"},
                         {"status": "rejected", "errors": ["bad spo2"]}])
        res = self.q.flush(lambda e: next(outcomes))
        self.assertEqual(res["sent"], 1)
        self.assertEqual(res["duplicates"], 1)
        self.assertEqual(res["rejected"], 1)
        self.assertEqual(res["remaining"], 0)
        self.assertEqual(self.q.stats(), {"sent": 2, "rejected": 1})

    def test_rejected_events_kept_for_audit_not_dropped(self):
        self.q.flush(lambda e: {"status": "rejected", "errors": ["malformed"]})
        row = self.q.db.execute(
            "SELECT status, last_error FROM sync_queue WHERE event_id='d1-1'").fetchone()
        self.assertEqual(row[0], "rejected")
        self.assertIn("malformed", row[1])

    def test_flush_stops_on_connection_error_no_data_loss(self):
        calls = []

        def sender(e):
            calls.append(e["event_id"])
            if e["event_id"] == "d1-2":
                raise ConnectionError("offline")
            return {"status": "accepted"}
        res = self.q.flush(sender)
        self.assertTrue(res["interrupted"])
        self.assertEqual(calls, ["d1-1", "d1-2"])  # d1-3 never attempted
        self.assertEqual(res["sent"], 1)
        self.assertEqual(res["remaining"], 2)  # d1-2 (retry) and d1-3 still pending
        stats = self.q.stats()
        self.assertEqual(stats.get("pending"), 2)

    def test_attempts_increment_on_failure(self):
        self.q.flush(lambda e: (_ for _ in ()).throw(TimeoutError("no net")))
        row = self.q.db.execute("SELECT attempts, last_error FROM sync_queue WHERE event_id='d1-1'").fetchone()
        self.assertEqual(row[0], 1)
        self.assertIn("no net", row[1])

    def test_retry_after_reconnect_sends_remaining(self):
        state = {"down": True}

        def sender(e):
            if state["down"]:
                raise ConnectionError("down")
            return {"status": "accepted"}
        res1 = self.q.flush(sender)
        self.assertTrue(res1["interrupted"])
        self.assertEqual(res1["sent"], 0)
        state["down"] = False
        res2 = self.q.flush(sender)
        self.assertFalse(res2["interrupted"])
        self.assertEqual(res2["sent"], 3)
        self.assertEqual(self.q.pending_count(), 0)

    def test_batch_limit(self):
        res = self.q.flush(lambda e: {"status": "accepted"}, batch=2)
        self.assertEqual(res["sent"], 2)
        self.assertEqual(res["remaining"], 1)


if __name__ == "__main__":
    unittest.main()
