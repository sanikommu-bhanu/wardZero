import unittest
from pathlib import Path
import numpy as np

from ml.inference.predict import RiskModel, ModelUnavailable, get_default_model
from ml.features.engineering import build_features, FEATURE_NAMES


def _sample_features(scenario_severity=0.0):
    # a plausible, roughly-normal reading window
    readings = [{"t": i * 300.0, "heart_rate": 75, "spo2": 97, "temperature": 36.7, "resp_rate": 16,
                "systolic_bp": 124, "diastolic_bp": 78, "activity": 35} for i in range(10)]
    context = {"age": 67, "hypertension": 1, "diabetes": 1, "cardiac": 0, "copd": 0, "post_surgery": 0}
    feats, _ = build_features(readings, context)
    return feats


def _sick_features():
    readings = [{"t": i * 300.0, "heart_rate": 130, "spo2": 84, "temperature": 39.2, "resp_rate": 30,
                "systolic_bp": 90, "diastolic_bp": 55, "activity": 5} for i in range(10)]
    context = {"age": 80, "hypertension": 1, "diabetes": 1, "cardiac": 1, "copd": 1, "post_surgery": 0}
    feats, _ = build_features(readings, context)
    return feats


class TestRiskModelLoading(unittest.TestCase):
    def test_loads_real_artifacts(self):
        m = RiskModel()
        self.assertTrue(m.is_available)

    def test_missing_artifact_dir_raises_model_unavailable(self):
        m = RiskModel(artifact_dir="ml/artifacts_does_not_exist")
        self.assertFalse(m.is_available)
        with self.assertRaises(ModelUnavailable):
            m.predict(_sample_features())

    def test_singleton_helper(self):
        self.assertIs(get_default_model(), get_default_model())


class TestPredict(unittest.TestCase):
    def setUp(self):
        self.model = RiskModel()
        self.model.load()

    def test_predict_shape(self):
        r = self.model.predict(_sample_features())
        self.assertIn(r.risk_class, ("LOW", "MEDIUM", "HIGH"))
        self.assertEqual(set(r.risk_probabilities), {"LOW", "MEDIUM", "HIGH"})
        self.assertAlmostEqual(sum(r.risk_probabilities.values()), 1.0, places=4)
        self.assertTrue(0.0 <= r.deterioration_24h_probability <= 1.0)
        self.assertTrue(0.0 <= r.deterioration_48h_probability <= 1.0)

    def test_normal_vitals_predict_low_risk(self):
        r = self.model.predict(_sample_features())
        self.assertEqual(r.risk_class, "LOW")

    def test_severe_vitals_predict_high_risk(self):
        r = self.model.predict(_sick_features())
        self.assertEqual(r.risk_class, "HIGH")
        self.assertGreater(r.risk_probabilities["HIGH"], r.risk_probabilities["LOW"])

    def test_missing_feature_raises(self):
        feats = _sample_features()
        del feats[FEATURE_NAMES[0]]
        with self.assertRaises(ValueError):
            self.model.predict(feats)

    def test_feature_vector_matches_scaler_dimensionality(self):
        r = self.model.predict(_sample_features())
        self.assertEqual(r.feature_vector.shape[0], len(FEATURE_NAMES))


if __name__ == "__main__":
    unittest.main()
