import unittest

from apps.api.pipeline import IngestionPipeline
from apps.api.repository import InMemoryRepository
from apps.api.validation import validate_event, ALLOWED_READING_FIELDS
from services.alert_engine.engine import AlertStore, Status


CONTEXT = {"age": 67, "hypertension": 1, "diabetes": 1, "cardiac": 0, "copd": 0, "post_surgery": 0}


def reading(event_id, t, **overrides):
    base = {"event_id": event_id, "patient_id": "demo-ravi-kumar", "device_id": "dev-1", "timestamp": t,
           "heart_rate": 75, "spo2": 97, "temperature": 36.7, "resp_rate": 16, "systolic_bp": 124,
           "diastolic_bp": 78, "activity": 35, "device_state": "ok", "connectivity": "online"}
    base.update(overrides)
    return base


class TestValidation(unittest.TestCase):
    def test_strips_true_severity(self):
        raw = reading("e1", 0.0)
        raw["_true_severity"] = 0.92
        r = validate_event(raw)
        self.assertNotIn("_true_severity", r.clean)
        self.assertTrue(any("dropped_unrecognized_fields" in e for e in r.errors))

    def test_whitelist_drops_unknown_field(self):
        raw = reading("e1", 0.0)
        raw["admin_override"] = True
        r = validate_event(raw)
        self.assertNotIn("admin_override", r.clean)

    def test_missing_required_field_rejected(self):
        raw = reading("e1", 0.0)
        del raw["patient_id"]
        r = validate_event(raw)
        self.assertFalse(r.ok)
        self.assertIsNone(r.clean)

    def test_out_of_range_vital_dropped_but_event_kept(self):
        raw = reading("e1", 0.0, heart_rate=999)  # outside (20,250)
        r = validate_event(raw)
        self.assertTrue(r.ok)  # other vitals still valid
        self.assertIsNone(r.clean["heart_rate"])
        self.assertTrue(any("out_of_range:heart_rate" in e for e in r.errors))

    def test_all_vitals_invalid_rejects_event(self):
        raw = {"event_id": "e1", "patient_id": "p1", "device_id": "d1", "timestamp": 0.0,
              "heart_rate": 9999}
        r = validate_event(raw)
        self.assertFalse(r.ok)

    def test_non_numeric_vital_rejected(self):
        raw = reading("e1", 0.0, spo2="high")
        r = validate_event(raw)
        self.assertIsNone(r.clean["spo2"])
        self.assertTrue(any("non_numeric_vital:spo2" in e for e in r.errors))

    def test_allowed_fields_frozen_shape(self):
        self.assertIn("patient_id", ALLOWED_READING_FIELDS)
        self.assertNotIn("_true_severity", ALLOWED_READING_FIELDS)


class TestPipelineEndToEnd(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryRepository()
        self.pipeline = IngestionPipeline(self.repo, alert_store=AlertStore())

    def _feed_normal(self, n=5, start_id=0):
        last = None
        for i in range(n):
            last = self.pipeline.ingest(reading(f"e{start_id+i}", i * 300.0), CONTEXT)
        return last

    def test_normal_readings_accepted_no_alert(self):
        result = self._feed_normal(5)
        self.assertEqual(result.status, "accepted")
        self.assertIsNotNone(result.risk_assessment)
        self.assertIsNone(result.alert)
        self.assertEqual(result.notification["type"], "vitals_update")

    def test_duplicate_event_id_not_double_stored(self):
        self.pipeline.ingest(reading("dup1", 0.0), CONTEXT)
        r2 = self.pipeline.ingest(reading("dup1", 0.0), CONTEXT)
        self.assertEqual(r2.status, "duplicate")
        self.assertEqual(self.repo.counts()["total_readings"], 1)

    def test_malformed_event_stored_for_audit_not_dropped(self):
        raw = reading("bad1", 0.0)
        del raw["patient_id"]
        r = self.pipeline.ingest(raw, CONTEXT)
        self.assertEqual(r.status, "rejected")
        self.assertEqual(self.repo.counts()["rejected"], 1)

    def test_true_severity_never_reaches_repository(self):
        raw = reading("e1", 0.0)
        raw["_true_severity"] = 0.99
        self.pipeline.ingest(raw, CONTEXT)
        stored = self.repo.readings_for("demo-ravi-kumar")[0]
        self.assertNotIn("_true_severity", stored)

    def test_critical_vitals_trigger_alert_and_notification(self):
        self._feed_normal(5, start_id=0)
        result = self.pipeline.ingest(reading("crit1", 5 * 300.0, spo2=80, heart_rate=160), CONTEXT)
        self.assertEqual(result.status, "accepted")
        self.assertIsNotNone(result.alert)
        self.assertEqual(result.alert.status, Status.ALERTED)
        self.assertTrue(result.risk_assessment["hard_threshold_breaches"])
        self.assertEqual(result.notification["type"], "alert")

    def test_repeated_critical_readings_dedupe_to_one_open_alert(self):
        self._feed_normal(3, start_id=0)
        r1 = self.pipeline.ingest(reading("c1", 3 * 300.0, spo2=80), CONTEXT)
        r2 = self.pipeline.ingest(reading("c2", 4 * 300.0, spo2=79), CONTEXT)
        self.assertEqual(r1.alert.id, r2.alert.id)
        self.assertEqual(len(self.pipeline.alerts.list(patient_id="demo-ravi-kumar")), 1)

    def test_timeline_records_reading_and_risk_events(self):
        self._feed_normal(2)
        timeline = self.repo.timeline_for("demo-ravi-kumar")
        kinds = [e["kind"] for e in timeline]
        self.assertIn("reading_received", kinds)
        self.assertIn("risk_assessed", kinds)

    def test_notifier_receives_every_accepted_event(self):
        self._feed_normal(4)
        self.assertEqual(len(self.pipeline.outbox), 4)

    def test_custom_notifier_used_instead_of_default_outbox(self):
        received = []
        repo = InMemoryRepository()
        pipeline = IngestionPipeline(repo, notifier=received.append)
        pipeline.ingest(reading("e1", 0.0), CONTEXT)
        self.assertEqual(len(received), 1)
        self.assertEqual(len(pipeline.outbox), 0)  # default outbox unused

    def test_ai_failure_does_not_lose_the_reading(self):
        """If risk assessment raises unexpectedly, the reading must already be durably stored
        (STEP 12: 'If AI fails, data must still be retained') — verified by checking storage
        happens before the risk-assessment stage can throw."""
        repo = InMemoryRepository()
        pipeline = IngestionPipeline(repo)

        def boom(features):
            raise RuntimeError("simulated AI outage")
        pipeline_module_assess = pipeline.ingest.__globals__["assess"]
        pipeline.ingest.__globals__["assess"] = boom
        try:
            with self.assertRaises(RuntimeError):
                pipeline.ingest(reading("e1", 0.0), CONTEXT)
        finally:
            pipeline.ingest.__globals__["assess"] = pipeline_module_assess
        # the reading was stored in step 3, BEFORE risk assessment (step 5) blew up
        self.assertEqual(repo.counts()["total_readings"], 1)


class TestDeviceState(unittest.TestCase):
    """set_device_state()/device_state() had no dedicated test before this session — only exercised
    indirectly through apps/api/simulator_manager.py. Added when `last_seen` was added to close a
    PROMPT 4 device-registry gap, so the new field has direct coverage rather than only a manual check."""

    def test_unknown_device_has_no_state(self):
        repo = InMemoryRepository()
        self.assertIsNone(repo.device_state("never-seen-device"))

    def test_set_device_state_stores_connectivity_battery_and_last_seen(self):
        repo = InMemoryRepository()
        repo.set_device_state("dev-1", "online", 87)
        state = repo.device_state("dev-1")
        self.assertEqual(state["connectivity"], "online")
        self.assertEqual(state["battery"], 87)
        self.assertIsNotNone(state["last_seen"])
        # ISO-8601 with a timezone offset, not a naive/local timestamp
        self.assertRegex(state["last_seen"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")

    def test_last_seen_advances_on_repeated_updates(self):
        import time
        repo = InMemoryRepository()
        repo.set_device_state("dev-1", "online", 90)
        first = repo.device_state("dev-1")["last_seen"]
        time.sleep(0.01)
        repo.set_device_state("dev-1", "online", 89)
        second = repo.device_state("dev-1")["last_seen"]
        self.assertGreater(second, first)


if __name__ == "__main__":
    unittest.main()


class TestAbstainAndNews2(unittest.TestCase):
    def test_no_alert_on_first_normal_reading_and_news2_present(self):
        repo = InMemoryRepository(); pipe = IngestionPipeline(repo)
        r = pipe.ingest({"event_id": "a1", "patient_id": "p", "device_id": "d", "timestamp": 1_800_000_000, "heart_rate": 72,
                         "spo2": 97, "temperature": 36.8, "resp_rate": 16, "systolic_bp": 120}, {"age": 70})
        self.assertTrue(r.risk_assessment["abstained"])
        self.assertIsNone(r.alert)
        self.assertEqual(r.risk_assessment["news2"]["score"], 0)

    def test_hard_threshold_still_alerts_while_abstaining(self):
        repo = InMemoryRepository(); pipe = IngestionPipeline(repo)
        r = pipe.ingest({"event_id": "a2", "patient_id": "p", "device_id": "d", "timestamp": 1_800_000_000, "heart_rate": 72,
                         "spo2": 84, "temperature": 36.8, "resp_rate": 16, "systolic_bp": 120}, {"age": 70})
        self.assertTrue(r.risk_assessment["abstained"])
        self.assertIsNotNone(r.alert)
        self.assertEqual(r.alert.severity.value, "critical")

    def test_news2_raises_but_never_lowers_escalation(self):
        repo = InMemoryRepository(); pipe = IngestionPipeline(repo)
        r = pipe.ingest({"event_id": "a3", "patient_id": "p", "device_id": "d", "timestamp": 1_800_000_000, "heart_rate": 135,
                         "spo2": 93, "temperature": 36.8, "resp_rate": 26, "systolic_bp": 120}, {"age": 70})
        self.assertEqual(r.risk_assessment["news2"]["score"], 8)  # RR 3 + SpO2(93) 2 + HR 3
        self.assertEqual(r.risk_assessment["recommended_escalation"], "emergency")
        self.assertIsNotNone(r.alert)
