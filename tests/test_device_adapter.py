"""Tests for apps/api/device_adapter.py — added this session for PROMPT 4 section 3's requirement
that simulator data and "real" IoT data enter the SAME ingestion service, not parallel logic.

The strongest proof available here (real end-to-end, not a mock): drive SimulatedDeviceAdapter and
HttpDeviceAdapter through a genuine IngestionPipeline + InMemoryRepository (the same classes
apps/api/main.py uses) with equivalent input, and assert the resulting stored reading is identical
except for the field that's supposed to differ (event_id, since each transport assigns its own id).
"""
import unittest

from apps.api.device_adapter import (
    SimulatedDeviceAdapter, HttpDeviceAdapter, MqttDeviceAdapter, NormalizedEvent,
)
from apps.api.pipeline import IngestionPipeline
from apps.api.repository import InMemoryRepository
from apps.api.validation import validate_event


CONTEXT = {"age": 67, "hypertension": 1, "diabetes": 1, "cardiac": 0, "copd": 0, "post_surgery": 0}


def _sample_event(event_id: str) -> dict:
    return {"event_id": event_id, "patient_id": "demo-ravi-kumar", "device_id": "dev-1",
           "timestamp": 0.0, "heart_rate": 75, "spo2": 97, "temperature": 36.7, "resp_rate": 16,
           "systolic_bp": 124, "diastolic_bp": 78, "activity": 35, "device_state": "ok",
           "connectivity": "online"}


class TestSimulatedAndHttpAdaptersAreArchitecturallyEquivalent(unittest.TestCase):
    """The actual claim PROMPT 4 section 3 asks to be proven: a simulated device and an HTTP-posted
    "real" device produce the same stored result via the same pipeline — not two implementations that
    happen to look similar."""

    def setUp(self):
        self.repo = InMemoryRepository()
        self.pipeline = IngestionPipeline(self.repo)

    def test_both_adapters_reach_the_same_pipeline_and_produce_equivalent_stored_readings(self):
        sim_adapter = SimulatedDeviceAdapter(sink=lambda payload: self.pipeline.ingest(payload, CONTEXT))
        http_adapter = HttpDeviceAdapter(sink=lambda payload: self.pipeline.ingest(payload, CONTEXT))

        sim_adapter.emit(_sample_event("sim-e1"))
        http_adapter.emit(_sample_event("http-e1"))

        readings = self.repo.readings_for("demo-ravi-kumar")
        self.assertEqual(len(readings), 2)
        sim_reading, http_reading = readings[0], readings[1]
        # Identical on every field except event_id (each transport supplies its own).
        for field in ("heart_rate", "spo2", "temperature", "resp_rate", "systolic_bp", "diastolic_bp",
                      "patient_id", "device_id"):
            self.assertEqual(sim_reading[field], http_reading[field], field)
        self.assertEqual(sim_reading["event_id"], "sim-e1")
        self.assertEqual(http_reading["event_id"], "http-e1")

    def test_both_adapters_trigger_real_risk_assessment_not_just_storage(self):
        """Proves emit() drives the full pipeline (storage -> features -> risk), not merely storage —
        the same downstream effect POST /readings has in apps/api/main.py."""
        adapter = SimulatedDeviceAdapter(sink=lambda payload: self.pipeline.ingest(payload, CONTEXT))
        result = adapter.emit(_sample_event("e1"))
        self.assertIsNotNone(result.risk_assessment)
        # one reading is below MIN_READINGS_FOR_ML, so the AI abstains but NEWS2 baseline is still computed
        self.assertEqual(result.risk_assessment["risk_level"], "UNKNOWN")
        self.assertTrue(result.risk_assessment["abstained"])
        self.assertIn("score", result.risk_assessment["news2"])
        for i in range(2, 9):
            result = adapter.emit(_sample_event(f"e{i}"))
        self.assertIn(result.risk_assessment["risk_level"], ("LOW", "MEDIUM", "HIGH"))
        self.assertFalse(result.risk_assessment["abstained"])

    def test_normalize_is_pure_no_side_effects(self):
        """normalize() must not call sink or touch storage — only emit() does. Guards against an
        adapter accidentally implementing its own parallel ingestion instead of delegating."""
        repo = InMemoryRepository()
        pipeline = IngestionPipeline(repo)
        adapter = SimulatedDeviceAdapter(sink=lambda payload: pipeline.ingest(payload, CONTEXT))
        adapter.normalize(_sample_event("e1"))  # not emit()
        self.assertEqual(repo.counts()["total_readings"], 0)


class TestMqttAdapterNormalization(unittest.TestCase):
    """MqttDeviceAdapter.connect() is BLOCKED in this sandbox (see module docstring) — these tests
    cover only normalize(), which needs no broker and genuinely runs here."""

    def setUp(self):
        self.adapter = MqttDeviceAdapter(sink=lambda payload: payload)  # sink unused by these tests

    def test_connect_raises_not_implemented_with_honest_reason(self):
        with self.assertRaises(NotImplementedError) as ctx:
            self.adapter.connect()
        self.assertIn("not installed", str(ctx.exception))

    def test_normalizes_single_sensor_payload(self):
        raw = {"patient_id": "ravi-kumar", "device_id": "pulseox-ravi-01", "sensor_type": "spo2",
              "value": 96, "unit": "%", "timestamp": "2026-09-27T09:00:00Z", "sequence": 1234}
        event = self.adapter.normalize(raw)
        self.assertIsInstance(event, NormalizedEvent)
        self.assertEqual(event.source_protocol, "mqtt")
        self.assertEqual(event.payload["spo2"], 96)
        self.assertEqual(event.payload["patient_id"], "ravi-kumar")
        self.assertEqual(event.payload["event_id"], "pulseox-ravi-01-1234")

    def test_normalizes_multi_vital_payload(self):
        raw = {"patient_id": "ravi-kumar", "device_id": "bed-monitor-ravi-01",
              "timestamp": "2026-09-27T09:00:00Z", "sequence": 5,
              "vitals": {"heart_rate": 78, "spo2": 97, "temperature": 36.8, "respiratory_rate": 16,
                        "systolic_bp": 128, "diastolic_bp": 78}}
        event = self.adapter.normalize(raw)
        self.assertEqual(event.payload["heart_rate"], 78)
        self.assertEqual(event.payload["spo2"], 97)
        self.assertEqual(event.payload["resp_rate"], 16)  # renamed from respiratory_rate

    def test_normalized_mqtt_payload_passes_the_same_validation_every_other_transport_uses(self):
        raw = {"patient_id": "ravi-kumar", "device_id": "bed-monitor-ravi-01",
              "timestamp": "2026-09-27T09:00:00Z", "sequence": 5,
              "vitals": {"heart_rate": 78, "spo2": 97, "temperature": 36.8, "respiratory_rate": 16,
                        "systolic_bp": 128, "diastolic_bp": 78}}
        event = self.adapter.normalize(raw)
        result = validate_event(event.payload)
        self.assertTrue(result.ok, result.errors)

    def test_unknown_sensor_type_produces_no_vital_field_rather_than_a_guess(self):
        raw = {"patient_id": "ravi-kumar", "device_id": "dev-x", "sensor_type": "unknown_gas_sensor",
              "value": 42, "timestamp": "2026-09-27T09:00:00Z", "sequence": 1}
        event = self.adapter.normalize(raw)
        for vital in ("heart_rate", "spo2", "temperature", "resp_rate"):
            self.assertNotIn(vital, event.payload)


if __name__ == "__main__":
    unittest.main()
