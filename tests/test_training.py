import unittest
import json
import shutil
import tempfile
from pathlib import Path
from ml.training.train import train_all


class TestTraining(unittest.TestCase):
    """Trains into a throwaway temp directory, never into ml/artifacts/ or evidence/metrics.json.

    Those real paths hold the full-size (n_patients_per_scenario=60, n_steps=200) production model
    that services/risk_engine and the API load at runtime. Earlier this test called train_all() with
    no artifact_dir override, which wrote a small toy model (n=8/150) straight into ml/artifacts/ as a
    side effect of merely running the test suite — silently degrading the real model any time tests
    ran. train_all() now accepts artifact_dir/evidence_path explicitly so this test can verify the
    training code path in full without touching production artifacts.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp(prefix="wardzero_test_training_")
        cls.artifact_dir = Path(cls._tmpdir) / "artifacts"
        cls.evidence_path = Path(cls._tmpdir) / "metrics.json"
        cls.metrics = train_all(n_patients_per_scenario=8, n_steps=400, seed=1,
                                artifact_dir=cls.artifact_dir, evidence_path=cls.evidence_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_artifacts_written(self):
        for f in ("risk_class_model.joblib", "deteriorates_24h_model.joblib",
                  "deteriorates_48h_model.joblib", "scaler.joblib", "manifest.json"):
            self.assertTrue((self.artifact_dir / f).exists(), f)

    def test_evidence_written_and_valid_json(self):
        self.assertTrue(self.evidence_path.exists())
        json.loads(self.evidence_path.read_text())

    def test_metrics_have_required_fields(self):
        rc = self.metrics["models"]["risk_class"]
        self.assertIn("confusion_matrix", rc)
        self.assertIn("macro_f1", rc)
        for target in ("deteriorates_24h", "deteriorates_48h"):
            b = self.metrics["models"][target]
            self.assertIn("roc_auc", b)
            self.assertIn("confusion_matrix", b)

    def test_risk_class_beats_random_baseline(self):
        # 3-class random guessing ~ 0.33 accuracy; the trained model must clear that by a wide margin
        self.assertGreater(self.metrics["models"]["risk_class"]["accuracy"], 0.6)


if __name__ == "__main__":
    unittest.main()
