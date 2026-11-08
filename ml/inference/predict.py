"""Load trained artifacts (ml/artifacts/*) and score a single patient's feature vector.

This module has ONE job: turn a features dict (from ml.features.engineering.build_features) into model
outputs. It does not know about rules, alerts, or trends -- that composition happens in
services.risk_engine, which falls back to a rules engine if this module's artifacts are missing.
"""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import joblib

from ml.features.engineering import FEATURE_NAMES

ARTIFACT_DIR = Path("ml/artifacts")


class ModelUnavailable(Exception):
    """Raised when artifacts are missing/corrupt. Callers (services.risk_engine) must catch this and fall
    back to rules -- it is not a bug to swallow silently, but it is an expected, handled condition."""


@dataclass
class PredictionResult:
    risk_class: str
    risk_probabilities: dict[str, float]          # {"LOW":..,"MEDIUM":..,"HIGH":..}
    deterioration_24h_probability: float
    deterioration_48h_probability: float
    feature_vector: np.ndarray                     # scaled, for explainability reuse
    raw_features: dict[str, float]
    model_version: str


class RiskModel:
    """Loads once, reused across requests. Thread-safety: sklearn predict/predict_proba are read-only
    given a fitted estimator, so a single loaded instance is safe to share across requests."""

    def __init__(self, artifact_dir: Path | str = ARTIFACT_DIR):
        self.dir = Path(artifact_dir)
        self._loaded = False
        self.scaler = self.feature_names = self.risk_clf = None
        self.bin_clf = {}
        self.manifest = {}

    def load(self):
        if self._loaded:
            return
        try:
            self.scaler = joblib.load(self.dir / "scaler.joblib")
            self.feature_names = joblib.load(self.dir / "feature_names.joblib")
            self.risk_clf = joblib.load(self.dir / "risk_class_model.joblib")
            self.bin_clf["deteriorates_24h"] = joblib.load(self.dir / "deteriorates_24h_model.joblib")
            self.bin_clf["deteriorates_48h"] = joblib.load(self.dir / "deteriorates_48h_model.joblib")
            # Single-row inference: joblib thread-pool overhead dominates (measured ~90 ms/predict vs ~ms
            # with n_jobs=1), which made ingestion ~0.5 s/reading. Training keeps n_jobs=-1.
            for m in (self.risk_clf, *self.bin_clf.values()):
                if hasattr(m, "n_jobs"):
                    m.n_jobs = 1
            self.manifest = json.loads((self.dir / "manifest.json").read_text())
        except (FileNotFoundError, OSError, EOFError, KeyError) as e:
            raise ModelUnavailable(f"could not load artifacts from {self.dir}: {e}") from e
        if list(self.feature_names) != list(FEATURE_NAMES):
            raise ModelUnavailable("artifact feature schema does not match current ml.features.engineering "
                                   "(retrain required after a feature-engineering change)")
        self._loaded = True

    @property
    def is_available(self) -> bool:
        try:
            self.load()
            return True
        except ModelUnavailable:
            return False

    def _vector(self, features: dict) -> np.ndarray:
        missing = [f for f in self.feature_names if f not in features]
        if missing:
            raise ValueError(f"missing required features: {missing}")
        return np.array([[features[f] for f in self.feature_names]], dtype=float)

    def predict(self, features: dict) -> PredictionResult:
        self.load()
        x = self._vector(features)
        xs = self.scaler.transform(x)
        classes = list(self.risk_clf.classes_)
        proba = self.risk_clf.predict_proba(xs)[0]
        risk_probs = {c: float(p) for c, p in zip(classes, proba)}
        risk_class = classes[int(np.argmax(proba))]

        def bin_proba(target):
            clf = self.bin_clf[target]
            classes_ = list(clf.classes_)
            p = clf.predict_proba(xs)[0]
            return float(p[classes_.index(1)]) if 1 in classes_ else 0.0

        return PredictionResult(
            risk_class=risk_class, risk_probabilities=risk_probs,
            deterioration_24h_probability=bin_proba("deteriorates_24h"),
            deterioration_48h_probability=bin_proba("deteriorates_48h"),
            feature_vector=xs[0], raw_features=dict(features),
            model_version=self.manifest.get("seed", "unknown").__str__(),
        )


_default_model: RiskModel | None = None


def get_default_model() -> RiskModel:
    global _default_model
    if _default_model is None:
        _default_model = RiskModel()
    return _default_model
