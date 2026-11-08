import unittest
import numpy as np

from ml.explainability.explain import explain, SHAP_AVAILABLE
from ml.inference.predict import RiskModel
from ml.features.engineering import build_features, FEATURE_NAMES


def _sick_features():
    readings = [{"t": i * 300.0, "heart_rate": 132, "spo2": 83, "temperature": 39.4, "resp_rate": 31,
                "systolic_bp": 88, "diastolic_bp": 54, "activity": 4} for i in range(10)]
    context = {"age": 80, "hypertension": 1, "diabetes": 1, "cardiac": 1, "copd": 1, "post_surgery": 0}
    feats, _ = build_features(readings, context)
    return feats


class TestExplainability(unittest.TestCase):
    def setUp(self):
        self.model = RiskModel()
        self.model.load()
        self.feats = _sick_features()
        pred = self.model.predict(self.feats)
        self.xs = pred.feature_vector
        self.pred = pred

    def test_shap_confirmed_unavailable_in_this_sandbox(self):
        # documents the environment this was verified in; occlusion is the path actually exercised below
        self.assertFalse(SHAP_AVAILABLE)

    def test_occlusion_used_when_shap_missing(self):
        exp = explain(self.model.risk_clf, self.xs, self.model.feature_names, "HIGH", self.feats)
        self.assertEqual(exp.method, "occlusion")
        self.assertIn("not installed", exp.note)

    def test_top_factors_shape(self):
        exp = explain(self.model.risk_clf, self.xs, self.model.feature_names, "HIGH", self.feats, top_k=5)
        self.assertEqual(len(exp.top_factors), 5)
        for f in exp.top_factors:
            self.assertIn(f.feature, FEATURE_NAMES)
            self.assertIn(f.direction, ("increases_risk", "decreases_risk"))
            self.assertEqual(f.direction, "increases_risk" if f.contribution > 0 else "decreases_risk")

    def test_sorted_by_absolute_contribution(self):
        exp = explain(self.model.risk_clf, self.xs, self.model.feature_names, "HIGH", self.feats, top_k=8)
        mags = [abs(f.contribution) for f in exp.top_factors]
        self.assertEqual(mags, sorted(mags, reverse=True))

    def test_base_value_matches_model_probability(self):
        exp = explain(self.model.risk_clf, self.xs, self.model.feature_names, "HIGH", self.feats)
        self.assertAlmostEqual(exp.base_value, self.pred.risk_probabilities["HIGH"], places=6)

    def test_sick_patient_spo2_or_heart_rate_among_top_factors_for_high_risk(self):
        exp = explain(self.model.risk_clf, self.xs, self.model.feature_names, "HIGH", self.feats, top_k=10)
        names = {f.feature for f in exp.top_factors}
        self.assertTrue(names & {"spo2_last", "spo2_mean", "spo2_min", "heart_rate_last", "heart_rate_mean",
                                 "n_abnormal", "shock_index", "temperature_last"}, names)

    def test_binary_model_explanation(self):
        clf24 = self.model.bin_clf["deteriorates_24h"]
        exp = explain(clf24, self.xs, self.model.feature_names, 1, self.feats)
        self.assertEqual(exp.method, "occlusion")
        self.assertEqual(exp.target_class, "1")

    def test_invalid_target_label_raises(self):
        with self.assertRaises(ValueError):
            explain(self.model.risk_clf, self.xs, self.model.feature_names, "NOT_A_CLASS", self.feats)

    def test_to_dict_is_json_serializable(self):
        import json
        exp = explain(self.model.risk_clf, self.xs, self.model.feature_names, "HIGH", self.feats)
        json.dumps(exp.to_dict())  # must not raise


if __name__ == "__main__":
    unittest.main()
