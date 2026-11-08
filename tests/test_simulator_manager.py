"""STEP 12 (this session) — unit tests for the parts of apps/api/simulator_manager.py that don't
require asyncio or fastapi: the event-flattening and context-mapping helpers. The asyncio scheduling
loop itself is not covered here (see simulator_manager.py's module docstring)."""
import unittest

from apps.api.simulator_manager import flatten_vitals_event, patient_context_from_profile


class TestFlattenVitalsEvent(unittest.TestCase):
    def test_flattens_nested_vitals_to_top_level(self):
        ev = {"event_id": "d-1", "patient_id": "demo-ravi-kumar", "device_id": "d",
             "timestamp": "2026-01-01T00:00:00Z", "kind": "vitals", "connectivity": "online",
             "vitals": {"heart_rate": 82.0, "spo2": 97.0, "temperature": None}}
        flat = flatten_vitals_event(ev, "fever")
        self.assertEqual(flat["heart_rate"], 82.0)
        self.assertEqual(flat["spo2"], 97.0)
        self.assertIsNone(flat["temperature"])
        self.assertEqual(flat["scenario"], "fever")
        self.assertEqual(flat["patient_id"], "demo-ravi-kumar")
        self.assertNotIn("vitals", flat)
        self.assertNotIn("kind", flat)

    def test_defaults_connectivity_to_online_if_absent(self):
        ev = {"event_id": "d-2", "patient_id": "p", "device_id": "d", "timestamp": "t", "vitals": {}}
        flat = flatten_vitals_event(ev, "normal")
        self.assertEqual(flat["connectivity"], "online")


class TestPatientContextFromProfile(unittest.TestCase):
    def test_maps_known_flags_and_coerces_to_bool(self):
        ctx = patient_context_from_profile({"age": 67, "diabetes": True, "hypertension": True,
                                            "unrelated_extra_key": "ignored"})
        self.assertEqual(ctx["age"], 67)
        self.assertTrue(ctx["diabetes"])
        self.assertTrue(ctx["hypertension"])
        self.assertFalse(ctx["cardiac"])
        self.assertNotIn("unrelated_extra_key", ctx)

    def test_empty_profile_yields_all_false_flags(self):
        ctx = patient_context_from_profile({})
        self.assertEqual(ctx["age"], 60)  # safe default; None would crash the generator
        self.assertFalse(any(ctx[k] for k in ("hypertension", "diabetes", "cardiac", "copd",
                                              "post_surgery")))


if __name__ == "__main__":
    unittest.main()
