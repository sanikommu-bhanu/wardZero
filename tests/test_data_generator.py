import unittest
import numpy as np
from ml.data.generator import generate_dataset, group_split, _risk_class, HIGH_S, MEDIUM_S
from ml.features.engineering import FEATURE_NAMES


class TestGeneration(unittest.TestCase):
    def test_deterministic_given_same_seed(self):
        a = generate_dataset(n_patients_per_scenario=3, n_steps=60, seed=7)
        b = generate_dataset(n_patients_per_scenario=3, n_steps=60, seed=7)
        self.assertTrue(a.drop(columns=["patient_id"]).equals(b.drop(columns=["patient_id"])))

    def test_different_seed_changes_values(self):
        a = generate_dataset(n_patients_per_scenario=3, n_steps=60, seed=1)
        b = generate_dataset(n_patients_per_scenario=3, n_steps=60, seed=2)
        self.assertFalse(np.allclose(a["heart_rate_last"].values, b["heart_rate_last"].values))

    def test_all_scenarios_present_and_labeled(self):
        df = generate_dataset(n_patients_per_scenario=2, n_steps=60, seed=5)
        self.assertEqual(set(df["scenario"].unique()), {"normal", "fever", "breathing_deterioration",
                                                        "cardiac_stress", "post_surgery_recovery"})
        self.assertTrue(set(df["risk_class"].unique()) <= {"LOW", "MEDIUM", "HIGH"})

    def test_feature_columns_match_schema(self):
        df = generate_dataset(n_patients_per_scenario=2, n_steps=60, seed=5)
        for f in FEATURE_NAMES:
            self.assertIn(f, df.columns)

    def test_normal_scenario_mostly_low_risk(self):
        df = generate_dataset(n_patients_per_scenario=5, n_steps=60, seed=5)
        normal = df[df["scenario"] == "normal"]
        self.assertGreater((normal["risk_class"] == "LOW").mean(), 0.9)

    def test_severe_scenarios_reach_high_risk(self):
        df = generate_dataset(n_patients_per_scenario=5, n_steps=400, seed=5)
        for sc in ("breathing_deterioration", "cardiac_stress"):
            sub = df[df["scenario"] == sc]
            self.assertGreater((sub["risk_class"] == "HIGH").mean(), 0.2, sc)

    def test_risk_class_thresholds(self):
        self.assertEqual(_risk_class(0.0), "LOW")
        self.assertEqual(_risk_class(MEDIUM_S - 1e-9), "LOW")
        self.assertEqual(_risk_class(MEDIUM_S), "MEDIUM")
        self.assertEqual(_risk_class(HIGH_S - 1e-9), "MEDIUM")
        self.assertEqual(_risk_class(HIGH_S), "HIGH")

    def test_no_lookahead_in_feature_window(self):
        # a row's feature window must only use t_index <= its own t_index (verified via window_hours bound)
        df = generate_dataset(n_patients_per_scenario=2, n_steps=60, seed=3)
        max_span_hours = 30 * 15 / 60.0  # WINDOW readings * step size
        self.assertTrue((df["window_hours"] <= max_span_hours + 1e-6).all())

    def test_deterioration_labels_only_set_when_horizon_available(self):
        df = generate_dataset(n_patients_per_scenario=3, n_steps=60, seed=9)
        unavailable_24 = df[df["label_horizon_24h_available"] == 0]
        self.assertTrue((unavailable_24["deteriorates_24h"] == 0).all())

    def test_nontrivial_deterioration_rate_with_enough_horizon(self):
        df = generate_dataset(n_patients_per_scenario=6, n_steps=200, seed=11)
        self.assertGreater(df["deteriorates_24h"].sum(), 0)


class TestSplit(unittest.TestCase):
    def test_no_patient_in_two_splits(self):
        df = generate_dataset(n_patients_per_scenario=10, n_steps=40, seed=4)
        df = group_split(df, seed=4)
        by_patient = df.groupby("patient_id")["split"].nunique()
        self.assertTrue((by_patient == 1).all())

    def test_every_scenario_in_every_split(self):
        df = generate_dataset(n_patients_per_scenario=10, n_steps=40, seed=4)
        df = group_split(df, seed=4)
        for split in ("train", "val", "test"):
            scenarios = set(df[df["split"] == split]["scenario"].unique())
            self.assertEqual(len(scenarios), 5, split)

    def test_split_deterministic(self):
        df = generate_dataset(n_patients_per_scenario=10, n_steps=40, seed=4)
        a = group_split(df, seed=4)[["patient_id", "split"]].drop_duplicates()
        b = group_split(df, seed=4)[["patient_id", "split"]].drop_duplicates()
        self.assertTrue(a.reset_index(drop=True).equals(b.reset_index(drop=True)))

    def test_train_is_largest_split(self):
        df = generate_dataset(n_patients_per_scenario=10, n_steps=40, seed=4)
        df = group_split(df, seed=4)
        counts = df.groupby("split")["patient_id"].nunique()
        self.assertGreater(counts["train"], counts["val"])
        self.assertGreater(counts["train"], counts["test"])


if __name__ == "__main__":
    unittest.main()
