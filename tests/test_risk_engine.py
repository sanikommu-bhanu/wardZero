import unittest
import json

from services.risk_engine import assess, ESCALATION_LEVELS
from services.risk_engine.rules import check_hard_thresholds, trend_from_features, rule_based_assessment
from ml.features.engineering import build_features
import ml.inference.predict as predict_mod


def _feats(hr=75, spo2=97, temp=36.7, rr=16, sbp=124, dbp=78, act=35, age=67, slope_hr=None, **ctx):
    readings = [{"t": i * 300.0, "heart_rate": hr, "spo2": spo2, "temperature": temp, "resp_rate": rr,
                "systolic_bp": sbp, "diastolic_bp": dbp, "activity": act} for i in range(10)]
    if slope_hr is not None:  # make heart_rate rise over the window at ~slope_hr bpm/hour
        for i, r in enumerate(readings):
            r["heart_rate"] = hr + slope_hr * (i * 300.0 / 3600.0)
    context = {"age": age, "hypertension": 1, "diabetes": 1, "cardiac": 0, "copd": 0, "post_surgery": 0, **ctx}
    feats, _ = build_features(readings, context)
    return feats


class TestHardThresholds(unittest.TestCase):
    def test_no_breach_on_normal_vitals(self):
        self.assertEqual(check_hard_thresholds(_feats()), [])

    def test_breach_on_low_spo2(self):
        b = check_hard_thresholds(_feats(spo2=80))
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0]["vital"], "spo2")

    def test_multiple_breaches(self):
        b = check_hard_thresholds(_feats(spo2=80, hr=160))
        self.assertEqual({x["vital"] for x in b}, {"spo2", "heart_rate"})


class TestTrend(unittest.TestCase):
    def test_stable_is_flat_trend(self):
        t = trend_from_features(_feats())
        self.assertEqual(t["overall"], "stable")

    def test_rising_heart_rate_detected_as_worsening_direction(self):
        t = trend_from_features(_feats(slope_hr=20))
        self.assertEqual(t["per_vital"]["heart_rate"]["direction"], "rising")
        self.assertGreater(t["deterioration_score"], 0)

    def test_falling_spo2_pushes_score_worse(self):
        readings = [{"t": i * 300.0, "heart_rate": 75, "spo2": 98 - i * 0.5, "temperature": 36.7,
                    "resp_rate": 16, "systolic_bp": 124, "diastolic_bp": 78, "activity": 35} for i in range(10)]
        feats, _ = build_features(readings, {"age": 67})
        t = trend_from_features(feats)
        self.assertEqual(t["per_vital"]["spo2"]["direction"], "falling")
        self.assertGreater(t["deterioration_score"], 0)


class TestRuleBasedAssessment(unittest.TestCase):
    def test_normal_is_low(self):
        r = rule_based_assessment(_feats())
        self.assertEqual(r["risk_level"], "LOW")

    def test_hard_breach_forces_high(self):
        r = rule_based_assessment(_feats(spo2=80))
        self.assertEqual(r["risk_level"], "HIGH")
        self.assertTrue(r["hard_threshold_breaches"])

    def test_note_signals_raise_score(self):
        f = _feats()
        f["note_fever"] = 1.0
        f["note_breathing_difficulty"] = 1.0
        low = rule_based_assessment(_feats())
        high = rule_based_assessment(f)
        self.assertGreater(high["score"], low["score"])

    def test_factors_sorted_descending(self):
        r = rule_based_assessment(_feats(spo2=80, hr=170))
        mags = [f["contribution"] for f in r["contributing_factors"]]
        self.assertEqual(mags, sorted(mags, reverse=True))


class TestAssessWithModel(unittest.TestCase):
    def test_normal_vitals_low_risk_via_model(self):
        r = assess(_feats())
        self.assertEqual(r.method, "model")
        self.assertEqual(r.risk_level, "LOW")
        self.assertEqual(r.recommended_escalation, "routine_monitoring")
        self.assertEqual(r.hard_threshold_breaches, [])
        self.assertIn("trained risk model", r.explanation)

    def test_severe_vitals_high_risk_via_model(self):
        r = assess(_feats(hr=132, spo2=91, temp=39.2, rr=28, sbp=95, act=5, cardiac=1, copd=1, age=82))
        self.assertEqual(r.risk_level, "HIGH")
        self.assertIn(r.recommended_escalation, ("escalate_to_doctor", "emergency"))
        self.assertTrue(r.contributing_factors)

    def test_forecast_present_and_bounded(self):
        r = assess(_feats())
        f = r.forecast
        self.assertIsInstance(f["deterioration_24h_probability"], float)
        self.assertTrue(0.0 <= f["deterioration_24h_probability"] <= 1.0)
        self.assertTrue(0.0 <= f["deterioration_48h_probability"] <= 1.0)

    def test_safety_override_forces_emergency_even_if_model_disagreed(self):
        # spo2 84 is a hard breach; even if the model doesn't say HIGH, escalation must be "emergency"
        r = assess(_feats(spo2=84))
        self.assertEqual(r.recommended_escalation, "emergency")
        self.assertTrue(r.hard_threshold_breaches)
        self.assertIn("SAFETY OVERRIDE", r.explanation)

    def test_to_dict_json_serializable_and_has_contract_fields(self):
        r = assess(_feats())
        d = r.to_dict()
        for key in ("risk_level", "probability", "contributing_factors", "explanation", "trend",
                   "recommended_escalation", "forecast"):
            self.assertIn(key, d)
        json.dumps(d)

    def test_disclaimer_present(self):
        r = assess(_feats())
        self.assertIn("not a medical diagnosis", r.disclaimer)


class TestAssessFallbackToRules(unittest.TestCase):
    """Force ModelUnavailable by pointing the singleton at a nonexistent artifact dir, then restore it."""

    def setUp(self):
        self._orig = predict_mod._default_model
        predict_mod._default_model = predict_mod.RiskModel(artifact_dir="ml/artifacts_missing_for_test")

    def tearDown(self):
        predict_mod._default_model = self._orig

    def test_falls_back_to_rules_when_model_unavailable(self):
        r = assess(_feats())
        self.assertEqual(r.method, "rules")
        self.assertEqual(r.risk_level, "LOW")
        self.assertIsNone(r.forecast["deterioration_24h_probability"])
        self.assertIn("rule-based scoring", r.explanation)

    def test_hard_breach_still_forces_emergency_without_model(self):
        r = assess(_feats(spo2=80))
        self.assertEqual(r.method, "rules")
        self.assertEqual(r.recommended_escalation, "emergency")


if __name__ == "__main__":
    unittest.main()
