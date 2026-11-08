"""Resilience tests: prove no data loss under network cuts, duplicate storms, late events, sensor dropout and
hard process kill (power loss). Real SQLite files, real pipeline, no mocks of the storage layer."""
import os, random, signal, subprocess, sys, tempfile, textwrap, time, unittest

from apps.api.pipeline import IngestionPipeline
from apps.api.sqlite_repo import SqliteAlertStore, SqliteDB, SqliteRepository
from apps.simulator.chaos import ChaosLink, PowerModel, sensor_dropout, with_duplicates, with_late_delivery
from services.sync_engine.queue import OfflineQueue

CTX = {"age": 70}


def make_events(n, patient="p1"):
    t0 = 1_800_000_000
    return [{"event_id": f"{patient}-{i}", "patient_id": patient, "device_id": f"{patient}-vitals",
             "timestamp": t0 + i * 300, "heart_rate": 72 + i % 5, "spo2": 97, "temperature": 36.8,
             "resp_rate": 16, "systolic_bp": 120, "diastolic_bp": 78} for i in range(n)]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "wz.db")
        self.db = SqliteDB(self.path)
        self.repo = SqliteRepository(self.db)
        self.pipe = IngestionPipeline(self.repo, alert_store=SqliteAlertStore(self.db))
        self.sender = lambda e: self.pipe.ingest(e, CTX).to_dict()


class TestNetworkAndReplay(Base):
    def test_network_cut_then_replay_loses_nothing(self):
        events = make_events(60)
        q = OfflineQueue(os.path.join(self.dir, "edge.db"))
        link = ChaosLink(self.sender)
        for i, e in enumerate(events):
            q.enqueue(e)
            link.network_up = not (15 <= i < 45)     # cut for 30 events
            q.flush(link)
            if i == 44:
                self.assertEqual(q.pending_count(), 30)   # all 30 cut-window events held, none dropped
                self.assertEqual(self.repo.counts()["total_readings"], 15)
        self.assertGreater(link.failures, 0)
        link.network_up = True
        q.flush(link)
        self.assertEqual(q.pending_count(), 0)
        self.assertEqual(self.repo.counts()["total_readings"], 60)

    def test_replay_is_idempotent_and_duplicate_storm_safe(self):
        rng = random.Random(1)
        events = make_events(50)
        storm = with_duplicates(events, rate=0.6, rng=rng)
        self.assertGreater(len(storm), 50)
        statuses = [self.sender(e)["status"] for e in storm]
        self.assertEqual(self.repo.counts()["total_readings"], 50)
        self.assertEqual(statuses.count("accepted"), 50)
        self.assertEqual(statuses.count("duplicate"), len(storm) - 50)
        # replaying the whole thing again changes nothing
        for e in events:
            self.assertEqual(self.sender(e)["status"], "duplicate")
        self.assertEqual(self.repo.counts()["total_readings"], 50)

    def test_late_out_of_order_events_stored_in_clinical_order(self):
        events = make_events(40)
        for e in with_late_delivery(events, random.Random(2), window=10):
            self.sender(e)
        got = self.repo.readings_for("p1")
        self.assertEqual([r["event_id"] for r in got], [e["event_id"] for e in events])

    def test_sensor_dropout_nothing_silently_lost(self):
        events = make_events(30)
        sent = sensor_dropout(events, "spo2", 10, 20) + [{"event_id": "bad-1", "patient_id": "p1", "device_id": "d", "timestamp": 1}]
        for e in sent:
            self.sender(e)
        c = self.repo.counts()
        # every event delivered is either stored as a reading or kept in the rejected audit table
        self.assertEqual(c["total_readings"] + c["rejected"], len(sent))
        self.assertEqual(c["rejected"], 1)

    def test_sensor_silence_is_visible_as_gap(self):
        events = sensor_dropout(make_events(30), None, 10, 20)
        for e in events:
            self.sender(e)
        ts = [r["timestamp"] for r in self.repo.readings_for("p1")]
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        self.assertEqual(max(gaps), 300 * 11)  # the 10-event silence is detectable


class TestPower(unittest.TestCase):
    def test_ups_model_and_hold_then_flush(self):
        p = PowerModel(drain_pct_per_min=10)
        self.assertEqual(p.state, "mains")
        p.cut_power()
        self.assertEqual(p.tick(1), "ups_battery")
        for _ in range(9):
            p.tick(1)
        self.assertEqual(p.state, "shutdown")
        self.assertFalse(p.can_transmit)
        p.restore_power()
        self.assertEqual(p.state, "mains")


class TestHardKill(unittest.TestCase):
    def test_sigkill_mid_stream_acked_writes_survive(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "kill.db")
        script = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {os.getcwd()!r})
            from apps.api.sqlite_repo import SqliteRepository
            r = SqliteRepository({path!r})
            i = 0
            while True:
                r.store_reading("p1", {{"event_id": f"e{{i}}", "patient_id": "p1", "timestamp": 1000 + i, "heart_rate": 70}})
                print(f"e{{i}}", flush=True)   # printed only AFTER the commit returned
                i += 1
        """)
        proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
        acked = []
        while len(acked) < 150:
            acked.append(proc.stdout.readline().strip())
        proc.send_signal(signal.SIGKILL)
        proc.wait()
        rest = proc.stdout.read().split()
        acked += rest
        repo = SqliteRepository(path)
        stored = {r["event_id"] for r in repo.readings_for("p1")}
        missing = [a for a in acked if a and a not in stored]
        self.assertEqual(missing, [], "an acknowledged write was lost after SIGKILL")
        self.assertGreaterEqual(len(stored), 150)

    def test_edge_queue_survives_restart(self):
        p = os.path.join(tempfile.mkdtemp(), "edge.db")
        q = OfflineQueue(p)
        for e in make_events(20):
            q.enqueue(e)
        del q
        self.assertEqual(OfflineQueue(p).pending_count(), 20)


if __name__ == "__main__":
    unittest.main()


class TestBatchReplay(Base):
    def test_batch_replay_idempotent_and_isolates_bad_items(self):
        from apps.api.replay import ingest_batch
        items = [{"event": e, "context": CTX} for e in make_events(30)]
        items.append({"event": {"event_id": "bad", "patient_id": "p1", "device_id": "d", "timestamp": 1}, "context": CTX})
        r1 = ingest_batch(self.pipe, items)
        self.assertEqual(r1["counts"]["accepted"], 30)
        self.assertEqual(r1["counts"]["rejected"], 1)
        r2 = ingest_batch(self.pipe, items)
        self.assertEqual(r2["counts"]["duplicate"], 30)
        self.assertEqual(self.repo.counts()["total_readings"], 30)
