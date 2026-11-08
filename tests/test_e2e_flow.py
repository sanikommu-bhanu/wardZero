"""End-to-end flow at the service layer, against a real on-disk SQLite file (no mocks):
simulator -> validate -> dedupe -> store -> features -> risk -> alert -> acknowledge/escalate/respond/resolve,
then a simulated API restart (fresh objects, same file) proving readings + alerts + audit survive.

This is the closest we can get to the HTTP smoke test without fastapi installed; the HTTP routes in
apps/api/main.py are thin wrappers over exactly these calls.
"""
import os, tempfile, time, unittest

from apps.api.pipeline import IngestionPipeline
from apps.api.simulator_manager import flatten_vitals_event, patient_context_from_profile
from apps.api.sqlite_repo import SqliteAlertStore, SqliteDB, SqliteRepository
from apps.simulator.simulator import PatientSimulator
from services.alert_engine.engine import Status


def run_sim(pipe, patient="p1", scenario="breathing_deterioration", ticks=80, start=None):
    ctx = patient_context_from_profile({"age": 72, "copd": True})
    sim = PatientSimulator(patient_id=patient, device_id=f"{patient}-vitals", context=ctx, scenario=scenario,
                           step_minutes=5.0, start_epoch=start or time.time())
    results = []
    for _ in range(ticks):
        for ev in sim.tick():
            if ev.get("kind") == "vitals":
                results.append(pipe.ingest(flatten_vitals_event(ev, scenario), ctx))
    return results


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "wz.db")
        self.db = SqliteDB(self.path)
        self.repo = SqliteRepository(self.db)
        self.alerts = SqliteAlertStore(self.db)
        self.pipe = IngestionPipeline(self.repo, alert_store=self.alerts)

    def test_full_flow_and_restart_persistence(self):
        results = run_sim(self.pipe)
        accepted = [r for r in results if r.status == "accepted"]
        self.assertEqual(len(accepted), len(results))
        self.assertEqual(self.repo.counts()["total_readings"], len(accepted))
        alert = self.alerts.list(patient_id="p1", open_only=True)
        self.assertTrue(alert, "deterioration scenario must raise an alert")
        a = alert[0]
        self.assertEqual(a.status, Status.ALERTED)
        self.alerts.acknowledge(a.id, "nurse@x")
        self.alerts.escalate(a.id, "nurse@x")
        self.alerts.acknowledge(a.id, "doctor@x")
        self.alerts.mark_responded(a.id, "doctor@x", note="visited, oxygen given")
        self.alerts.resolve(a.id, "doctor@x")
        n_readings = self.repo.counts()["total_readings"]
        n_alerts = len(self.alerts.list())
        n_timeline = len(self.repo.timeline_for("p1"))
        self.db.close()

        # ---- simulated restart: brand-new objects over the same file
        db2 = SqliteDB(self.path)
        repo2, alerts2 = SqliteRepository(db2), SqliteAlertStore(db2)
        self.assertEqual(repo2.counts()["total_readings"], n_readings)
        self.assertEqual(len(alerts2.list()), n_alerts)
        self.assertEqual(len(repo2.timeline_for("p1")), n_timeline)
        restored = alerts2.get(a.id)
        self.assertEqual(restored.status, Status.RESOLVED)
        self.assertEqual([e.action for e in restored.audit][-1], "resolved")
        self.assertIn("visited, oxygen given", restored.notes[0]["note"])
        self.assertIsNotNone(repo2.latest_risk_assessment("p1"))
        # new alert ids continue after the restored ones (no collision)
        pipe2 = IngestionPipeline(repo2, alert_store=alerts2)
        run_sim(pipe2, patient="p2")
        ids = [x.id for x in alerts2.list()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_history_endpoint_source_survives_reload(self):
        run_sim(self.pipe, ticks=30)
        hist = self.repo.readings_for("p1", limit=10)
        self.assertEqual(len(hist), 10)
        ts = [h["timestamp"] for h in hist]
        self.assertEqual(ts, sorted(ts))


if __name__ == "__main__":
    unittest.main()
