import unittest
from datetime import datetime, timedelta, timezone

from services.alert_engine.engine import (
    AlertStore, Severity, Status, severity_for, InvalidTransition, AlertEngineError,
)


def ra(escalation="caregiver_review", breaches=None):
    return {"risk_level": "MEDIUM", "probability": 0.7, "recommended_escalation": escalation,
           "hard_threshold_breaches": breaches or [], "explanation": "test"}


class FakeClock:
    def __init__(self, start=None):
        self.t = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


class TestSeverityMapping(unittest.TestCase):
    def test_maps_escalation_levels(self):
        self.assertEqual(severity_for("routine_monitoring"), Severity.INFORMATIONAL)
        self.assertEqual(severity_for("caregiver_review"), Severity.WARNING)
        self.assertEqual(severity_for("escalate_to_doctor"), Severity.HIGH_RISK)
        self.assertEqual(severity_for("emergency"), Severity.CRITICAL)

    def test_hard_breach_forces_critical(self):
        self.assertEqual(severity_for("routine_monitoring", ["spo2_critical_low"]), Severity.CRITICAL)


class TestDetectionAndDedup(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = AlertStore(clock=self.clock)

    def test_detect_creates_alerted_status(self):
        a = self.store.detect("p1", "risk_deterioration", ra())
        self.assertEqual(a.status, Status.ALERTED)
        self.assertEqual(a.severity, Severity.WARNING)
        self.assertEqual(len(a.audit), 2)  # detected + alerted

    def test_duplicate_detection_updates_not_duplicates(self):
        a1 = self.store.detect("p1", "risk_deterioration", ra())
        self.clock.advance(minutes=1)
        a2 = self.store.detect("p1", "risk_deterioration", ra())
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(len(self.store.list(patient_id="p1")), 1)
        self.assertEqual(a2.audit[-1].action, "duplicate_suppressed")

    def test_duplicate_upgrades_severity_but_not_downgrades(self):
        a = self.store.detect("p1", "risk_deterioration", ra("caregiver_review"))
        self.assertEqual(a.severity, Severity.WARNING)
        a = self.store.detect("p1", "risk_deterioration", ra("emergency", ["hr_critical"]))
        self.assertEqual(a.severity, Severity.CRITICAL)
        a = self.store.detect("p1", "risk_deterioration", ra("routine_monitoring"))
        self.assertEqual(a.severity, Severity.CRITICAL)  # does not downgrade

    def test_different_alert_type_is_independent(self):
        self.store.detect("p1", "risk_deterioration", ra())
        self.store.detect("p1", "device_offline", ra())
        self.assertEqual(len(self.store.list(patient_id="p1")), 2)

    def test_resolved_alert_does_not_dedup_new_detection(self):
        a1 = self.store.detect("p1", "risk_deterioration", ra())
        self.store.acknowledge(a1.id, "nurse1")
        self.store.mark_responded(a1.id, "nurse1")
        self.store.resolve(a1.id, "nurse1")
        a2 = self.store.detect("p1", "risk_deterioration", ra())
        self.assertNotEqual(a1.id, a2.id)


class TestLifecycleTransitions(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = AlertStore(clock=self.clock)
        self.alert = self.store.detect("p1", "risk_deterioration", ra())

    def test_full_happy_path(self):
        a = self.store.acknowledge(self.alert.id, "nurse1")
        self.assertEqual(a.status, Status.ACKNOWLEDGED)
        self.assertEqual(a.acknowledged_by, "nurse1")
        a = self.store.mark_responded(self.alert.id, "nurse1", note="checked on patient")
        self.assertEqual(a.status, Status.RESPONDED)
        self.assertEqual(a.notes[0]["note"], "checked on patient")
        a = self.store.resolve(self.alert.id, "nurse1")
        self.assertEqual(a.status, Status.RESOLVED)
        self.assertFalse(a.is_open())

    def test_escalate_then_acknowledge(self):
        self.store.escalate(self.alert.id, reason="manual escalation by supervisor")
        a = self.store.get(self.alert.id)
        self.assertEqual(a.status, Status.ESCALATED)
        a = self.store.acknowledge(self.alert.id, "doctor1")
        self.assertEqual(a.status, Status.ACKNOWLEDGED)

    def test_dismiss_requires_reason(self):
        with self.assertRaises(AlertEngineError):
            self.store.dismiss(self.alert.id, "nurse1", reason="")

    def test_dismiss_with_reason(self):
        a = self.store.dismiss(self.alert.id, "nurse1", reason="false positive - sensor recalibrated")
        self.assertEqual(a.status, Status.DISMISSED)
        self.assertFalse(a.is_open())

    def test_cannot_dismiss_escalated_or_responded_alert(self):
        self.store.escalate(self.alert.id, "nurse1")
        with self.assertRaises(InvalidTransition):
            self.store.dismiss(self.alert.id, "nurse1", reason="false alarm")
        self.assertEqual(self.store.get(self.alert.id).status, Status.ESCALATED)   # untouched by the refused call
        self.store.mark_responded(self.alert.id, "nurse1")
        with self.assertRaises(InvalidTransition):
            self.store.dismiss(self.alert.id, "nurse1", reason="false alarm")

    def test_acknowledged_alert_can_still_be_dismissed(self):
        self.store.acknowledge(self.alert.id, "nurse1")
        a = self.store.dismiss(self.alert.id, "nurse1", reason="sensor artefact")
        self.assertEqual(a.status, Status.DISMISSED)

    def test_responded_alert_can_be_resolved(self):
        self.store.acknowledge(self.alert.id, "nurse1")
        self.store.mark_responded(self.alert.id, "nurse1")
        a = self.store.resolve(self.alert.id, "nurse1", note="O2 started, SpO2 back to 95")
        self.assertEqual(a.status, Status.RESOLVED)
        self.assertEqual(a.notes[-1]["note"], "O2 started, SpO2 back to 95")

    def test_cannot_acknowledge_twice(self):
        self.store.acknowledge(self.alert.id, "nurse1")
        with self.assertRaises(InvalidTransition):
            self.store.acknowledge(self.alert.id, "nurse2")

    def test_cannot_respond_before_ack(self):
        with self.assertRaises(InvalidTransition):
            self.store.mark_responded(self.alert.id, "nurse1")

    def test_cannot_act_on_resolved_alert(self):
        self.store.acknowledge(self.alert.id, "nurse1")
        self.store.mark_responded(self.alert.id, "nurse1")
        self.store.resolve(self.alert.id, "nurse1")
        with self.assertRaises(InvalidTransition):
            self.store.acknowledge(self.alert.id, "nurse1")
        with self.assertRaises(InvalidTransition):
            self.store.dismiss(self.alert.id, "nurse1", reason="x")

    def test_add_note_any_time(self):
        a = self.store.add_note(self.alert.id, "nurse1", "keeping an eye on this")
        self.assertEqual(len(a.notes), 1)

    def test_unknown_alert_id_raises(self):
        with self.assertRaises(AlertEngineError):
            self.store.get(9999)


class TestTimeToAckTracking(unittest.TestCase):
    def test_time_to_ack_recorded(self):
        clock = FakeClock()
        store = AlertStore(clock=clock)
        a = store.detect("p1", "risk_deterioration", ra())
        clock.advance(minutes=3, seconds=30)
        store.acknowledge(a.id, "nurse1")
        ack_event = [e for e in a.audit if e.action == "acknowledged"][0]
        self.assertEqual(ack_event.detail["time_to_ack_seconds"], 210.0)


class TestAutoEscalation(unittest.TestCase):
    def test_critical_escalates_after_5_minutes(self):
        clock = FakeClock()
        store = AlertStore(clock=clock)
        a = store.detect("p1", "risk_deterioration", ra("emergency", ["spo2_critical_low"]))
        self.assertEqual(store.sweep_timeouts(), [])  # not yet due
        clock.advance(minutes=5)
        escalated = store.sweep_timeouts()
        self.assertEqual(len(escalated), 1)
        self.assertEqual(store.get(a.id).status, Status.ESCALATED)

    def test_warning_does_not_escalate_before_1_hour(self):
        clock = FakeClock()
        store = AlertStore(clock=clock)
        store.detect("p1", "risk_deterioration", ra("caregiver_review"))
        clock.advance(minutes=59)
        self.assertEqual(store.sweep_timeouts(), [])

    def test_informational_never_auto_escalates(self):
        clock = FakeClock()
        store = AlertStore(clock=clock)
        store.detect("p1", "risk_deterioration", ra("routine_monitoring"))
        clock.advance(days=10)
        self.assertEqual(store.sweep_timeouts(), [])

    def test_acknowledged_alert_not_swept(self):
        clock = FakeClock()
        store = AlertStore(clock=clock)
        a = store.detect("p1", "risk_deterioration", ra("emergency", ["x"]))
        store.acknowledge(a.id, "nurse1")
        clock.advance(hours=1)
        self.assertEqual(store.sweep_timeouts(), [])
        self.assertEqual(store.get(a.id).status, Status.ACKNOWLEDGED)

    def test_sweep_is_idempotent_no_double_escalate_events(self):
        clock = FakeClock()
        store = AlertStore(clock=clock)
        a = store.detect("p1", "risk_deterioration", ra("emergency", ["x"]))
        clock.advance(minutes=6)
        store.sweep_timeouts()
        escalated_again = store.sweep_timeouts()
        self.assertEqual(escalated_again, [])  # already ESCALATED, not ALERTED anymore


class TestListingAndFiltering(unittest.TestCase):
    def test_list_open_only(self):
        clock = FakeClock()
        store = AlertStore(clock=clock)
        a1 = store.detect("p1", "risk_deterioration", ra())
        a2 = store.detect("p2", "device_offline", ra())
        store.acknowledge(a2.id, "nurse1")
        store.mark_responded(a2.id, "nurse1")
        store.resolve(a2.id, "nurse1")
        open_alerts = store.list(open_only=True)
        self.assertEqual([a.id for a in open_alerts], [a1.id])

    def test_to_dict_is_json_serializable(self):
        import json
        clock = FakeClock()
        store = AlertStore(clock=clock)
        a = store.detect("p1", "risk_deterioration", ra())
        store.acknowledge(a.id, "nurse1")
        json.dumps(a.to_dict())  # must not raise


if __name__ == "__main__":
    unittest.main()
